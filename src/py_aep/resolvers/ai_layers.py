"""Enumerate the layers of an Illustrator/PDF file (PDF Optional Content Groups).

After Effects imports a layered `.ai`/`.pdf` as a composition with one footage
layer per Illustrator layer. The layers map to PDF Optional Content Groups
(OCGs); the order of the catalog's `/OCProperties` `/OCGs` array is the
document order (bottom layer first). Only PDF-compatible files expose OCGs;
Illustrator files saved without PDF compatibility store their artwork in a
compressed PGF block and are not supported.
"""

from __future__ import annotations

import io
import re
import zlib
from pathlib import Path
from typing import TYPE_CHECKING

from ..color.icc import icc_profile_description
from ..cos import CosParser, IndirectObject, IndirectReference

if TYPE_CHECKING:
    import os
    from typing import Any


class UnsupportedAiLayersError(ValueError):
    """Raised when a `.ai`/`.pdf` file's layers cannot be enumerated."""


_OBJ_RE = re.compile(rb"(\d+)[ \t\r\n]+(\d+)[ \t\r\n]+obj\b")


def _object_offsets(data: bytes) -> dict[int, int]:
    """Map each indirect object number to its byte offset (last definition wins)."""
    offsets: dict[int, int] = {}
    for match in _OBJ_RE.finditer(data):
        offsets[int(match.group(1))] = match.start()
    return offsets


def _parse_object_at(data: bytes, offset: int) -> Any:
    """Parse the single indirect object starting at `offset`, returning its value."""
    parser = CosParser(io.BytesIO(data[offset:]))
    parser.lex()
    value = parser.parse_value()
    return value.data if isinstance(value, IndirectObject) else value


def _resolve(value: Any, data: bytes, offsets: dict[int, int]) -> Any:
    """Follow an indirect reference to its object; pass other values through."""
    if isinstance(value, IndirectReference):
        offset = offsets.get(value.object_number)
        return None if offset is None else _parse_object_at(data, offset)
    return value


def read_ai_layers(
    file: str | os.PathLike[str], data: bytes | None = None
) -> list[str]:
    """Return the Illustrator/PDF layer names in document order.

    Args:
        file: Path to a `.ai` or `.pdf` file.
        data: The file's bytes, if the caller already read them.

    Returns:
        Layer names in document (OCG) order, bottom layer first.

    Raises:
        UnsupportedAiLayersError: If the file is not a PDF-compatible document
            or has no Optional Content Groups (layers).
    """
    name = Path(file).name
    if data is None:
        data = Path(file).read_bytes()
    if not data.startswith(b"%PDF"):
        raise UnsupportedAiLayersError(
            f"{name}: not a PDF-compatible file; layered import requires an "
            "Illustrator/PDF file saved with PDF compatibility."
        )
    marker = data.find(b"/OCProperties")
    if marker < 0:
        raise UnsupportedAiLayersError(
            f"{name}: no layers (the file has no PDF Optional Content Groups)."
        )
    offsets = _object_offsets(data)
    parser = CosParser(io.BytesIO(data[marker + len(b"/OCProperties") :]))
    parser.lex()
    oc_properties = _resolve(parser.parse_value(), data, offsets)
    if not isinstance(oc_properties, dict):
        raise UnsupportedAiLayersError(f"{name}: unreadable /OCProperties.")
    ocgs = _resolve(oc_properties.get("OCGs"), data, offsets)
    names: list[str] = []
    if isinstance(ocgs, list):
        for ref in ocgs:
            ocg = _resolve(ref, data, offsets)
            if isinstance(ocg, dict) and "Name" in ocg:
                names.append(str(ocg["Name"]))
    if not names:
        raise UnsupportedAiLayersError(f"{name}: no named layers found.")
    return names


_STREAM_RE = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)


def _find_ai_icc(
    file: str | os.PathLike[str], data: bytes | None = None
) -> bytes | None:
    """Return the embedded ICC profile body from a PDF-compatible file.

    Inflates each deflate stream and returns the first one that is an ICC
    profile (`acsp` signature at offset 36). `None` when the file is not
    PDF-compatible or has no embedded profile.
    """
    if data is None:
        data = Path(file).read_bytes()
    if not data.startswith(b"%PDF"):
        return None
    for match in _STREAM_RE.finditer(data):
        body = match.group(1)
        if len(body) > 8_000_000:
            continue
        try:
            profile = zlib.decompress(body)
        except zlib.error:
            continue
        if len(profile) >= 132 and profile[36:40] == b"acsp":
            return profile
    return None


def read_ai_color_info(
    file: str | os.PathLike[str], data: bytes | None = None
) -> tuple[str | None, str | None]:
    """Return `(data color space, profile name)` from the embedded ICC profile.

    Reads and inflates the file once. Prefer this over calling
    `read_ai_color_space` and `read_ai_color_profile` separately, which each
    re-scan the file. Both values are `None` when the file is not
    PDF-compatible or has no embedded profile.

    The data color space is the ICC header signature (bytes 16-19): `RGB `,
    `CMYK`, `GRAY`, or `Lab `. The profile name comes from the `desc` tag.

    Args:
        file: Path to a `.ai` or `.pdf` file.
        data: The file's bytes, if the caller already read them.
    """
    icc = _find_ai_icc(file, data)
    if icc is None:
        return None, None
    color_space = icc[16:20].decode("latin-1").strip() or None
    return color_space, icc_profile_description(icc)


def read_ai_color_profile(file: str | os.PathLike[str]) -> str | None:
    """Return the embedded ICC color profile name, or `None`.

    After Effects records a PDF-compatible Illustrator/PDF file's embedded
    color profile name (e.g. `Coated FOGRA39 (ISO 12647-2:2004)`) in the
    footage item, read here from the ICC `desc` tag. Returns `None` when the
    file is not PDF-compatible or has no embedded profile.

    Args:
        file: Path to a `.ai` or `.pdf` file.
    """
    return read_ai_color_info(file)[1]


def read_ai_color_space(file: str | os.PathLike[str]) -> str | None:
    """Return the embedded ICC profile's data color space, or `None`.

    The ICC header's data-color-space signature (bytes 16-19) is `RGB `,
    `CMYK`, `GRAY`, or `Lab `. AE encodes it in the footage `opti`. Returns
    `None` when the file has no embedded profile.

    Args:
        file: Path to a `.ai` or `.pdf` file.
    """
    return read_ai_color_info(file)[0]
