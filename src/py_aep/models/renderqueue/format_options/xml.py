from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from enum import IntEnum
from typing import TYPE_CHECKING, Dict, cast

from ....data.output_module_rules import CLAMP_DEPENDENTS
from ....enums import (
    AudioCodec,
    AudioInterleave,
    DnxResolution,
    MPEGAudioFormat,
    MPEGAudioLayer,
    MPEGMultiplexer,
    MPEGMuxStreamCompatibility,
    MPEGProfile,
    VideoCodec,
)
from ...descriptors import ChunkField
from ...validators import _validate_number, validate_enum, validate_int
from .base import FormatOptionsBase

if TYPE_CHECKING:
    from typing import Any

    from ....binary.render_chunks import RoptChunk
    from ..output_module import OutputModule

# Adobe stores FPS as ticks-per-frame with a 254016000000 tick base.
_ADOBE_TICKS_PER_SECOND = 254016000000

# -- Ropt body layout -------------------------------------------------------
# The body is a 34-byte header followed by the XML region. Two big-endian
# u32s in the header restate the sizes, and AE HONOURS them: it reads exactly
# `_LEN_BODY_OFFSET` bytes, so a stale value silently truncates the XML.
# Verified on all 129 AE-authored XML modules in the corpus - '.AVI' 15/15,
# 'H264' 31/31, 'MooV' 53/53, 'Mp3 ' 23/23, 'wao_' 7/7 - every one with a
# 34-byte header.
_LEN_BODY_OFFSET = 6
"""Offset of the u32 holding `len(body)`."""
_LEN_XML_OFFSET = 30
"""Offset of the u32 holding `len(xml region) - 2` (i.e. excluding the NULs)."""

_XML_DECLARATION = b'<?xml version="1.0" encoding="UTF-8"?>\n'
_XML_NULS = b"\x00\x00"
_XML_TERMINATOR = b"\n" + _XML_NULS
"""Every AE-authored body ends `>\\n\\x00\\x00`."""

#: An empty element with NO attributes; AE expands these (`<ParamName></ParamName>`)
#: while self-closing the ones that have attributes (`<Foo ObjectRef="1"/>`).
_EMPTY_ELEMENT_RE = re.compile(r"<([A-Za-z_][\w.-]*)/>")

# XML param -> rules key: params whose writes are gated by the module's
# format rules (and whose changes re-clamp dependents, see
# CLAMP_DEPENDENTS). Params not listed here (frame rate, VR fields, ...)
# validate locally only.
_PARAM_RULE_KEYS: dict[str, str] = {
    "ADBEAudioBitrate": "Audio Bitrate",
    "ADBEAudioCodec": "Audio Codec",
    "ADBEMPEGAudioFormat": "Audio Format",
    "ADBEMPEGMultiplexer": "Multiplexer",
    "ADBEVideoCodec": "Video Codec",
    "BitRate": "BitRate",
}


class _EnumParam:
    """Descriptor for XML enum parameters (read/write)."""

    def __init__(self, key: str, enum_cls: type[IntEnum]) -> None:
        self._key = key
        self._enum_cls = enum_cls

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __get__(
        self, obj: XmlFormatOptions | None, objtype: type | None = None
    ) -> object:
        if obj is None:
            return self
        return obj._enum_param(self._key, self._enum_cls)

    def __set__(self, obj: XmlFormatOptions, value: object) -> None:
        obj._set_enum_param(self._key, value, self._enum_cls)


class _ScalarParam:
    """Descriptor for plain integer XML parameters (read/write).

    Reads return `None` when the parameter is absent and fall back to
    the raw string when it is non-numeric (the binary is trusted, like
    `_try_enum_or_int` for enums). Writes require an `int`.
    """

    def __init__(self, key: str) -> None:
        self._key = key

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __get__(
        self, obj: XmlFormatOptions | None, objtype: type | None = None
    ) -> object:
        if obj is None:
            return self
        raw = obj.params.get(self._key, "")
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return raw

    def __set__(self, obj: XmlFormatOptions, value: object) -> None:
        if value is None:
            return
        validate_int(value)
        obj._check_param_rule(self._key, value)
        obj._set_param(self._key, str(value))
        obj._clamp_after_param(self._key)


def _extract_params(
    root: ET.Element,
) -> tuple[dict[str, str], dict[str, ET.Element], dict[str, ET.Element]]:
    """Extract parameter key-value pairs from a PremiereData XML tree.

    Parses `ExporterParam` elements regardless of child-tag order and
    returns a mapping of identifier to value, plus a mapping of identifier
    to `ParamValue` element for O(1) writes, plus a mapping of identifier
    to the owning `ExporterParam` element.

    An `ExporterParam` with no `ParamValue` child is an UNSET parameter -
    AE's encoding for e.g. the H.264 `Baseline` profile. It is left out of
    the params dict (so it reads as absent) but kept in the element map, so
    a later write can restore its value in place instead of appending a
    duplicate element.

    Args:
        root: The parsed XML root element.

    Returns:
        Tuple of (params dict, value-elements dict, param-elements dict).
    """
    params: dict[str, str] = {}
    value_elements: dict[str, ET.Element] = {}
    param_elements: dict[str, ET.Element] = {}
    for elem in root.iter("ExporterParam"):
        id_elem = elem.find("ParamIdentifier")
        if id_elem is None or id_elem.text is None:
            continue
        identifier = id_elem.text
        if identifier.isdigit():
            continue
        param_elements[identifier] = elem
        val_elem = elem.find("ParamValue")
        if val_elem is None:
            continue
        params[identifier] = val_elem.text or ""
        value_elements[identifier] = val_elem
    return params, value_elements, param_elements


def _try_enum_or_int(enum_cls: type[IntEnum], raw_str: str) -> object:
    """Try to parse an int, then map to an enum; fall back to int."""
    try:
        raw_value = int(raw_str)
    except ValueError:
        return None
    try:
        return enum_cls(raw_value)
    except ValueError:
        return raw_value


class ParamsDict(Dict[str, str]):
    """Dict subclass that syncs mutations back to the XML tree.

    `dict.update` / `setdefault` / `pop` / `clear` / `popitem` / `|=` are
    C-level and do NOT call `__setitem__` / `__delitem__`, so every one of
    them is overridden to route through them - otherwise they would mutate
    the dict (and so the typed accessors' reads) while leaving the XML, and
    therefore the saved file, unchanged.
    """

    # A class default, not a bare annotation: `update` and friends below
    # reach `self._owner` through `__setitem__`, so a `ParamsDict` built
    # before `_owner` is assigned would raise AttributeError.
    _owner: XmlFormatOptions | None = None

    def __setitem__(self, key: str, value: str) -> None:
        super().__setitem__(key, value)
        if self._owner is not None:
            self._owner._on_param_changed(key, value)

    def __delitem__(self, key: str) -> None:
        super().__delitem__(key)
        if self._owner is not None:
            self._owner._on_param_removed(key)

    def update(self, *args: Any, **kwargs: str) -> None:  # type: ignore[override]
        for key, value in dict(*args, **kwargs).items():
            self[key] = value

    def setdefault(self, key: str, default: str = "") -> str:
        if key not in self:
            self[key] = default
        return self[key]

    def pop(self, key: str, *default: str) -> str:  # type: ignore[override]
        try:
            value = self[key]
        except KeyError:
            if default:
                return default[0]
            raise
        del self[key]
        return value

    def popitem(self) -> tuple[str, str]:
        key, value = super().popitem()
        if self._owner is not None:
            self._owner._on_param_removed(key)
        return key, value

    def clear(self) -> None:
        for key in list(self):
            del self[key]

    # `|` (__or__) needs no override: it returns a new plain dict rather
    # than mutating, so it cannot desync the XML. Only `|=` does.
    def __ior__(self, other: Any) -> ParamsDict:  # type: ignore[override,misc]
        self.update(other)
        return self


class XmlFormatOptions(FormatOptionsBase):
    """XML-based format-specific render options.

    Shared by output formats that store their settings as a binary header
    followed by a `PremiereData` XML block containing `ExporterParam`
    elements. Applicable formats include AVI (`.AVI`), H.264 (`H264`),
    MP3 (`Mp3 `), QuickTime (`MooV`), and WAV (`wao_`).

    Individual parameters are stored in the `params` dictionary, keyed by
    their Adobe parameter identifier (e.g. `"ADBEVideoCodec"`).

    Example:
        ```python
        from py_aep import XmlFormatOptions, parse

        app = parse("project.aep")
        om = app.project.render_queue.items[0].output_modules[0]
        if isinstance(om.format_options, XmlFormatOptions):
            print(om.format_options.video_codec)
        ```
    """

    params: dict[str, str]
    """
    All `ExporterParam` key-value pairs extracted from the embedded XML
    `PremiereData` block. Keys are Adobe parameter identifiers such as
    `"ADBEVideoCodec"`, `"ADBEVideoQuality"`,
    `"ADBEAudioInterleave"`, etc. Values are the raw string
    representations from the XML. Read / Write.

    Writes through this dict are the documented low-level escape hatch:
    they bypass the typed accessors' format-rule validation and clamps.
    Item assignment (`params[key] = value`), `update` and `setdefault`
    all sync back to the XML. Removal (`pop`/`del`) only mutates the
    dict: the `ExporterParam` element stays in the file.
    """

    def __init__(
        self,
        *,
        _body: RoptChunk,
    ) -> None:
        self._body = _body

        raw = _body.data
        self._xml_root: ET.Element | None = None
        self._xml_header: bytes | None = None
        self._val_elements: dict[str, ET.Element] = {}
        self._param_elements: dict[str, ET.Element] = {}
        self.params: ParamsDict = ParamsDict()
        self.params._owner = None
        xml_start = raw.find(b"<?xml")
        if xml_start >= 0:
            self._xml_header = raw[:xml_start]
            xml_text = (
                raw[xml_start:].decode("utf-8", errors="replace").split("\x00")[0]
            )
            self._xml_root = ET.fromstring(xml_text)
            data, self._val_elements, self._param_elements = _extract_params(
                self._xml_root
            )
            self.params.update(data)
        self.params._owner = self

    format_code = ChunkField[str](
        "_body",
        "format_code",
        read_only=True,
    )
    """
    The 4-character format identifier from the Ropt chunk header
    (e.g. `".AVI"`, `"H264"`, `"Mp3 "`, `"MooV"`, `"wao_"`).
    Read-only.
    """

    # -- write helpers -----------------------------------------------------

    def _set_param(self, key: str, str_value: str) -> None:
        """Update a parameter in the XML tree and sync to the raw body."""
        self.params[key] = str_value

    def _on_param_changed(self, key: str, str_value: str) -> None:
        """Sync a param change to the XML tree and raw body."""
        # Every `params` mutation funnels through here by design, so this is
        # where a detached wrapper's raw-dict writes are caught - `params`
        # is a `__setitem__` surface, which `__setattr__` cannot see.
        self._check_attached()
        if self._xml_root is None:
            return
        val_elem = self._val_elements.get(key)
        if val_elem is not None:
            val_elem.text = str_value
            self._sync_xml()
            return
        param_elem = self._param_elements.get(key)
        if param_elem is not None:
            # An existing but UNSET param: restore its value in place rather
            # than appending a duplicate element. AE writes `ParamValue` as
            # the element's first child; its tail carries the indentation
            # that used to precede the (currently first) next sibling, which
            # is what the element's own `text` holds.
            val = ET.Element("ParamValue")
            val.text = str_value
            val.tail = param_elem.text
            param_elem.insert(0, val)
            self._val_elements[key] = val
        else:
            ep = ET.SubElement(self._xml_root, "ExporterParam")
            ET.SubElement(ep, "ParamIdentifier").text = key
            val = ET.SubElement(ep, "ParamValue")
            val.text = str_value
            self._val_elements[key] = val
            self._param_elements[key] = ep
        self._sync_xml()

    def _on_param_removed(self, key: str) -> None:
        """Unset a parameter by dropping only its `ParamValue` child.

        AE encodes an unset parameter (e.g. the H.264 `Baseline` profile)
        by removing the `ParamValue` and KEEPING the `ExporterParam`
        element - its `ObjectID` is referenced by the PremiereData object
        graph. Both encodings decode identically (the param reads as absent
        either way), so only a raw-XML comparison against an AE-saved
        `Baseline` module distinguishes them.
        """
        self._check_attached()
        if self._xml_root is None:
            return
        self._val_elements.pop(key, None)
        param_elem = self._param_elements.get(key)
        if param_elem is None:
            return
        val = param_elem.find("ParamValue")
        if val is not None:
            param_elem.remove(val)
        self._sync_xml()

    def _set_enum_param(
        self, key: str, value: object, enum_cls: type[IntEnum] | None = None
    ) -> None:
        """Set an Adobe parameter from an enum or int value."""
        if value is None:
            return
        if not isinstance(value, int):
            raise TypeError(
                f"expected an int or IntEnum for {key!r}, got {type(value).__name__}"
            )
        # int() normalizes IntEnum members so str() yields the numeric form.
        int_value = int(value)
        if enum_cls is not None and int_value not in enum_cls._value2member_map_:
            members = ", ".join(f"{m.name} ({m.value})" for m in enum_cls)
            raise ValueError(
                f"Invalid value {value!r} for {key!r}. "
                f"Valid {enum_cls.__name__} values: {members}"
            )
        checked = enum_cls(int_value) if enum_cls is not None else int_value
        self._check_param_rule(key, checked)
        self._set_param(key, str(int_value))
        # NOTE: Rouu.video_codec is NOT synced here - it holds a constant
        # per-output-plugin handler tag ('DOVT' for QuickTime, 'CTXF' for
        # AVI/H.264), not the codec 4cc; every corpus sample confirms it
        # never varies with the selected codec.
        self._clamp_after_param(key)

    def _require_om(self) -> OutputModule:
        """The owning output module. A format options object always belongs
        to one; a missing back-reference is a wiring bug, not a permissive
        case. (Detachment is a separate condition, caught by
        `_check_attached` on every write path.)
        """
        om = self._parent_om
        if om is None:
            # Explicit raise (not assert) so the wiring bug stays loud
            # under `python -O` too.
            raise RuntimeError("format options have no owning output module")
        return om

    def _check_param_rule(self, param_key: str, value: object) -> None:
        """Gate a rules-covered param write on the module's format rules.

        Params outside `_PARAM_RULE_KEYS` are not format-gated.
        """
        rule_key = _PARAM_RULE_KEYS.get(param_key)
        if rule_key is None:
            return
        self._require_om()._check_format_rule(rule_key, value)

    def _clamp_after_param(self, param_key: str) -> None:
        """Re-resolve dependent settings after a context param write."""
        rule_key = _PARAM_RULE_KEYS.get(param_key)
        if rule_key is None:
            return
        self._require_om()._apply_singleton_clamps(CLAMP_DEPENDENTS.get(rule_key, ()))

    def _sync_xml(self) -> None:
        """Re-serialize the XML tree back to the raw body, as AE writes it.

        The `Ropt` header embeds the body's own lengths and **After Effects
        honours them**: it reads exactly `_LEN_BODY_OFFSET` bytes and
        discards the rest. Leaving them stale made AE silently truncate the
        XML mid-element on open and re-save the corruption (probed on AE
        26.3: an 87-byte-longer body was cut back to the stale length, losing
        `</PremiereData>`). So the lengths MUST be repatched here.

        The rest matches AE's serializer byte-for-byte so that a no-op sync
        is the identity - see `tests/roundtrip/test_xml_sync_fidelity.py`.

        Note:
            Byte-identity needs Python 3.8+: 3.7's `ET.tostring` sorts each
            element's attributes alphabetically instead of keeping document
            order, so a 3.7 write reorders them. The result is the same
            length and semantically identical XML that AE reads correctly -
            only the bytes differ from AE's. Parsing and saving without a
            write never calls this, so round-trip idempotency is unaffected.
        """
        if self._xml_root is None or self._xml_header is None:
            return
        text = ET.tostring(self._xml_root, encoding="unicode")
        # `ET` writes `<Foo a="1" />`; AE writes `<Foo a="1"/>`.
        text = text.replace(" />", "/>")
        # `ET` self-closes every empty element; AE only does so when the
        # element has attributes, and expands the attribute-less ones.
        text = _EMPTY_ELEMENT_RE.sub(r"<\1></\1>", text)
        xml_bytes = _XML_DECLARATION + text.encode("utf-8") + _XML_TERMINATOR
        body = bytearray(self._xml_header + xml_bytes)
        # Back-patch the two self-describing lengths AE honours (a stale one
        # silently truncates the XML). These stay here rather than becoming
        # an `XmlRoptChunk` in `binary/render_chunks.py` alongside the other
        # `_ROPT_VARIANTS`: a typed variant never writes `Chunk.data`, so the
        # variable-length XML payload would have to move to `_trailing`,
        # which is `eq=False` - two modules with different render settings
        # would then compare equal, and any missed `.data` write would drop
        # the payload silently.
        body[_LEN_BODY_OFFSET : _LEN_BODY_OFFSET + 4] = len(body).to_bytes(4, "big")
        body[_LEN_XML_OFFSET : _LEN_XML_OFFSET + 4] = (
            len(xml_bytes) - len(_XML_NULS)
        ).to_bytes(4, "big")
        self._body.data = bytes(body)

    # -- read helpers ------------------------------------------------------

    def _enum_param(self, key: str, enum_cls: type) -> object:
        """Look up an Adobe param and convert to an enum or int.

        Returns `None` when the param is absent or non-numeric.
        """
        raw = self.params.get(key, "")
        if not raw:
            return None
        return _try_enum_or_int(enum_cls, raw)

    video_codec = _EnumParam("ADBEVideoCodec", VideoCodec)
    """The video codec as a [VideoCodec][] FourCC integer value extracted
    from the `ADBEVideoCodec` parameter, or `None` for audio-only
    formats (MP3, WAV). Falls back to a plain `int` when the codec is
    not in the [VideoCodec][] enum.
    Read / Write."""

    audio_codec = _EnumParam("ADBEAudioCodec", AudioCodec)
    """The audio codec as an [AudioCodec][] integer value extracted from
    the `ADBEAudioCodec` parameter, or `None` when the parameter is
    absent. Falls back to a plain `int` when the codec is not in the
    [AudioCodec][] enum.
    Read / Write."""

    @property
    def frame_rate(self) -> float | None:
        """
        The output frame rate in frames per second, derived from the
        `ADBEVideoFPS` parameter. Adobe stores this as ticks per frame
        using a time base of 254,016,000,000 ticks/second, so
        `frame_rate = 254016000000 / ADBEVideoFPS`.
        `None` for audio-only formats (MP3, WAV).
        Read / Write.
        """
        fps_str = self.params.get("ADBEVideoFPS", "")
        if not fps_str:
            return None
        try:
            ticks = int(fps_str)
            if ticks > 0:
                return _ADOBE_TICKS_PER_SECOND / ticks
        except ValueError:
            pass
        return None

    @frame_rate.setter
    def frame_rate(self, value: float | None) -> None:
        if value is None:
            return
        _validate_number(min=1 / _ADOBE_TICKS_PER_SECOND)(value)
        ticks = round(_ADOBE_TICKS_PER_SECOND / value)
        self._set_param("ADBEVideoFPS", str(ticks))

    mpeg_audio_format = _EnumParam("ADBEMPEGAudioFormat", MPEGAudioFormat)
    """The dialog's top-level `Audio Format` (AAC / MPEG / PCM) as an
    [MPEGAudioFormat][] FourCC integer value extracted from the
    `ADBEMPEGAudioFormat` parameter, or `None` when the parameter is
    absent. Despite the parameter's `MPEG` prefix it selects among all
    three families. Falls back to a plain `int` when the value is not
    in the [MPEGAudioFormat][] enum.
    Read / Write."""

    mpeg_audio_layer = _EnumParam("ADBEMPEGAudioLayer", MPEGAudioLayer)
    """The MPEG-1 audio layer as an [MPEGAudioLayer][] value extracted
    from the `ADBEMPEGAudioLayer` parameter, or `None` when the
    parameter is absent. Only meaningful when `mpeg_audio_format` is
    `MPEGAudioFormat.MPEG`. Read / Write."""

    audio_interleave = _EnumParam("ADBEAudioInterleave", AudioInterleave)
    """The AVI audio interleave interval as an [AudioInterleave][] value
    extracted from the `ADBEAudioInterleave` parameter. The dialog's
    `None` choice stores no parameter, so reads return `None` for it.
    Read / Write."""

    bitrate = _ScalarParam("BitRate")
    """The MP3 audio bitrate in kbps, from the `BitRate` parameter
    (note: not ADBE-prefixed), or `None` when absent. Read / Write."""

    audio_bitrate = _ScalarParam("ADBEAudioBitrate")
    """The H.264 audio bitrate in kbps, from the `ADBEAudioBitrate`
    parameter, or `None` when absent. Read / Write."""

    @property
    def profile(self) -> MPEGProfile | int:
        """The H.264 encoding profile as an [MPEGProfile][] value from the
        `ADBEVideoMPEGProfile` parameter. Read / Write.

        After Effects stores NO parameter for `Baseline`, so an absent
        parameter reads back as `MPEGProfile.BASELINE` and assigning
        `BASELINE` removes the parameter (AE-validated: the result matches
        an AE-saved Baseline module's parameters exactly). The dropdown's
        `Auto` is resolved at save time and reads back as `MAIN`. Falls
        back to a plain `int` when the stored value is not in the
        [MPEGProfile][] enum.
        """
        raw = self.params.get("ADBEVideoMPEGProfile", "")
        if not raw:
            return MPEGProfile.BASELINE
        result = _try_enum_or_int(MPEGProfile, raw)
        # A non-numeric param is as good as absent.
        if result is None:
            return MPEGProfile.BASELINE
        return cast("MPEGProfile | int", result)

    @profile.setter
    def profile(self, value: MPEGProfile | int) -> None:
        validate_enum(MPEGProfile)(value)
        if MPEGProfile(value) is MPEGProfile.BASELINE:
            self.params.pop("ADBEVideoMPEGProfile", "")
            return
        self._set_param("ADBEVideoMPEGProfile", str(int(value)))

    level = _ScalarParam("ADBEVideoMPEGProfileLevel")
    """The H.264 encoding level as the raw integer from the
    `ADBEVideoMPEGProfileLevel` parameter (level x 10, e.g. `41` for
    4.1; `100` is Unrestricted), or `None` when absent. Read / Write."""

    resolution = _EnumParam("ADBEVideoResolution", DnxResolution)
    """The DNxHR/DNxHD resolution preset as a [DnxResolution][] value
    extracted from the `ADBEVideoResolution` parameter, or `None` when
    the parameter is absent. Only meaningful when `video_codec` is
    `VideoCodec.DNXHR_DNXHD`; the param survives codec changes (stale
    under other codecs). Falls back to a plain `int` when the value is
    not in the [DnxResolution][] enum. Read / Write."""

    dnx_alpha_type = _ScalarParam("ADBEDNxHDAlphaType")
    """The DNxHR/DNxHD `Alpha` choice from the `ADBEDNxHDAlphaType`
    parameter: `1` = Compressed, `None` (param absent) = None. Only
    meaningful when `video_codec` is `VideoCodec.DNXHR_DNXHD`.
    (`ADBEVideoAlphaType` is unrelated - it reads `true` on every
    sampled module.) Read / Write."""

    mpeg_multiplexer = _EnumParam("ADBEMPEGMultiplexer", MPEGMultiplexer)
    """The MPEG multiplexer as an [MPEGMultiplexer][] FourCC integer
    value extracted from the `ADBEMPEGMultiplexer` parameter, or
    `None` when the parameter is absent. Falls back to a plain `int`
    when the value is not in the [MPEGMultiplexer][] enum.
    Read / Write."""

    mpeg_mux_stream_compatibility = _EnumParam(
        "ADBEMPEGMuxStreamCompatibility", MPEGMuxStreamCompatibility
    )
    """The MPEG mux stream compatibility as an
    [MPEGMuxStreamCompatibility][] FourCC integer value extracted from
    the `ADBEMPEGMuxStreamCompatibility` parameter, or `None` when the
    parameter is absent. Falls back to a plain `int` when the value
    is not in the [MPEGMuxStreamCompatibility][] enum.
    Read / Write."""
