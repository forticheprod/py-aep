"""Build and parse the color-profile envelope embedded in `.aep` color chunks.

After Effects stores each color space (project working space, display color
space, footage media color space) as a compact JSON envelope inside a `Utf8`
chunk's `.value`:

    {"baseColorProfile":{"colorProfileData":"<base64>","colorProfileName":"<name>"},"baseProfileType":<1|2|3>}

`baseProfileType` (see `color-management-write-rev-eng` notes):

- `2` = Adobe ICC: `colorProfileData` is the raw ICC profile bytes (base64),
  `bytes[36:40] == b"acsp"`.
- `3` = OCIO: `colorProfileData` is base64 of a small JSON describing the OCIO
  color space (single color space, or a display + view pair).
- `1` = display-referred tag: an 8-byte `01000000ffffffff` blob (read-only).

This module is the single source of truth for that byte format so that
round-trips stay byte-identical. It is pure (`json` + `base64`); it performs no
I/O and imports nothing from `models/` or `binary/`.

AE writes compact JSON (separators `,` and `:`, no whitespace) with a fixed key
order; reproducing it exactly is required for byte-identical output.
"""

from __future__ import annotations

import base64
import json
from typing import NamedTuple

#: `baseProfileType` values.
PROFILE_TYPE_TAG = 1
"""Display-referred tag (8-byte blob); read-only, not a write target."""
PROFILE_TYPE_ICC = 2
"""Adobe ICC profile; `colorProfileData` is raw ICC bytes."""
PROFILE_TYPE_OCIO = 3
"""OCIO color space; `colorProfileData` is a small JSON."""

#: `ocioColorSpaceType` values inside an OCIO `colorProfileData` JSON.
OCIO_TYPE_DISPLAY = 1
"""A display + view pair (`colorSpace1` = display, `colorSpace2` = view)."""
OCIO_TYPE_COLORSPACE = 2
"""A single color space (`colorSpace1` only)."""


def _compact(obj: object) -> str:
    """Serialize `obj` exactly as AE does: compact, no whitespace.

    `ensure_ascii=False` so a non-ASCII profile/color-space name is emitted as
    raw UTF-8 (matching AE's `Utf8` chunk) rather than `\\uXXXX` escapes, which
    would break the byte-identical round-trip.
    """
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _envelope(color_profile_data_b64: str, name: str, profile_type: int) -> str:
    """Wrap pre-encoded `colorProfileData` in the outer envelope.

    Key order matches AE verbatim: `baseColorProfile` (`colorProfileData` then
    `colorProfileName`), then `baseProfileType`.
    """
    return _compact(
        {
            "baseColorProfile": {
                "colorProfileData": color_profile_data_b64,
                "colorProfileName": name,
            },
            "baseProfileType": profile_type,
        }
    )


def build_ocio_envelope(profile_name: str, profile_data: str) -> str:
    """Envelope for an OCIO color space from a resolved `(name, data)` pair.

    The pair depends on the selection KIND and so needs the `.ocio` config to
    resolve; see
    [ocio_color_profile_envelope][py_aep.color.ocio.ocio_color_profile_envelope],
    which is what callers should use. This function is the pure byte-format
    half, kept here with the rest of the envelope spec.

    Args:
        profile_name: The `colorProfileName` (e.g. `"ACES/ACEScg yo"`).
        profile_data: The `colorProfileData` JSON (e.g. `{"colorSpace1":"ACEScg yo"}`).
    """
    return _envelope(_b64(profile_data), profile_name, PROFILE_TYPE_OCIO)


def build_ocio_colorspace_envelope(colorspace: str) -> str:
    """Envelope for an OCIO color space selected by ROLE or ALIAS.

    `colorProfileName` is the role's target (or the alias) itself, and the
    data carries `ocioColorSpaceType: 2`.

    Warning:
        This is only one of the four selection kinds. A DIRECT colorspace
        pick uses `colorProfileName = "<family>/<name>"` and omits
        `ocioColorSpaceType` - passing a direct colorspace name here
        produces an envelope AE would not write. Prefer
        [ocio_color_profile_envelope][py_aep.color.ocio.ocio_color_profile_envelope],
        which resolves the kind against the config.

    Args:
        colorspace: The OCIO role target or alias name.
    """
    inner = _compact(
        {"colorSpace1": colorspace, "ocioColorSpaceType": OCIO_TYPE_COLORSPACE}
    )
    return _envelope(_b64(inner), colorspace, PROFILE_TYPE_OCIO)


def build_ocio_display_envelope(display: str, view: str) -> str:
    """Envelope for an OCIO display color space (a display + view pair).

    `colorProfileName` is `"<display>/<view>"`.

    Args:
        display: The OCIO display name (e.g. `"sRGB - Display"`).
        view: The OCIO view name (e.g. `"ACES 1.0 - SDR Video"`).
    """
    inner = _compact(
        {
            "colorSpace1": display,
            "colorSpace2": view,
            "ocioColorSpaceType": OCIO_TYPE_DISPLAY,
        }
    )
    return _envelope(_b64(inner), f"{display}/{view}", PROFILE_TYPE_OCIO)


def build_icc_envelope(name: str, icc_bytes: bytes) -> str:
    """Envelope for an Adobe ICC color space.

    Used for the project working/display space and footage media color space in
    Adobe CMS mode.

    Args:
        name: The profile description (e.g. `"ProPhoto RGB"`).
        icc_bytes: The raw ICC profile bytes to embed.
    """
    return _envelope(
        base64.b64encode(icc_bytes).decode("ascii"), name, PROFILE_TYPE_ICC
    )


class ColorProfile(NamedTuple):
    """A decoded color-profile envelope."""

    name: str
    """`colorProfileName` (e.g. `"ACEScg"`, `"ACES/sRGB"`, `"ProPhoto RGB"`)."""

    profile_type: int
    """`baseProfileType`: one of `PROFILE_TYPE_TAG/ICC/OCIO`."""

    data: bytes
    """Decoded `colorProfileData`: raw ICC bytes, OCIO JSON bytes, or tag blob."""

    @property
    def is_ocio(self) -> bool:
        """Whether this is an OCIO profile (`baseProfileType == 3`)."""
        return self.profile_type == PROFILE_TYPE_OCIO

    @property
    def is_icc(self) -> bool:
        """Whether this is an Adobe ICC profile (`baseProfileType == 2`)."""
        return self.profile_type == PROFILE_TYPE_ICC

    @property
    def ocio_color_spaces(self) -> tuple[str, ...]:
        """The OCIO `(colorSpace1[, colorSpace2])` names, or `()` if not OCIO."""
        if not self.is_ocio:
            return ()
        inner = json.loads(self.data)
        names = [inner["colorSpace1"]]
        if "colorSpace2" in inner:
            names.append(inner["colorSpace2"])
        return tuple(names)


def parse_envelope(envelope_json: str) -> ColorProfile:
    """Decode a color-profile envelope `Utf8` value into a `ColorProfile`.

    Args:
        envelope_json: The raw `Utf8` chunk value (the outer JSON string).
    """
    outer = json.loads(envelope_json)
    base = outer["baseColorProfile"]
    return ColorProfile(
        name=base["colorProfileName"],
        profile_type=outer["baseProfileType"],
        data=base64.b64decode(base["colorProfileData"]),
    )


def envelope_profile_name(envelope_json: str) -> str:
    """The envelope's `colorProfileName`, or `"None"` when the envelope is
    empty (`{}`, e.g. an unset `pdvc` display chunk) or carries no name.

    Unlike `parse_envelope`, this does not require `colorProfileData`.
    """
    outer = json.loads(envelope_json)
    return str(outer.get("baseColorProfile", {}).get("colorProfileName", "None"))
