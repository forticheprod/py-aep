from __future__ import annotations

import xml.etree.ElementTree as ET
from enum import IntEnum
from typing import TYPE_CHECKING, Dict

from ....enums import (
    AudioCodec,
    MPEGAudioFormat,
    MPEGMultiplexer,
    MPEGMuxStreamCompatibility,
    VideoCodec,
)
from ...descriptors import ChunkField
from ...validators import _validate_number

if TYPE_CHECKING:
    from ....binary.render_chunks import RoptChunk

# Adobe stores FPS as ticks-per-frame with a 254016000000 tick base.
_ADOBE_TICKS_PER_SECOND = 254016000000


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


def _extract_params(
    root: ET.Element,
) -> tuple[dict[str, str], dict[str, ET.Element]]:
    """Extract parameter key-value pairs from a PremiereData XML tree.

    Parses `ExporterParam` elements regardless of child-tag order and
    returns a mapping of identifier to value, plus a mapping of
    identifier to `ParamValue` element for O(1) writes.

    Args:
        root: The parsed XML root element.

    Returns:
        Tuple of (params dict, value-elements dict).
    """
    params: dict[str, str] = {}
    elements: dict[str, ET.Element] = {}
    for elem in root.iter("ExporterParam"):
        id_elem = elem.find("ParamIdentifier")
        val_elem = elem.find("ParamValue")
        if id_elem is None or id_elem.text is None:
            continue
        if val_elem is None:
            continue
        identifier = id_elem.text
        if identifier.isdigit():
            continue
        params[identifier] = val_elem.text or ""
        elements[identifier] = val_elem
    return params, elements


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
    """Dict subclass that syncs writes back to the XML tree."""

    _owner: XmlFormatOptions | None

    def __setitem__(self, key: str, value: str) -> None:
        super().__setitem__(key, value)
        if self._owner is not None:
            self._owner._on_param_changed(key, value)


class XmlFormatOptions:
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
        self.params: ParamsDict = ParamsDict()
        self.params._owner = None
        xml_start = raw.find(b"<?xml")
        if xml_start >= 0:
            self._xml_header = raw[:xml_start]
            xml_text = (
                raw[xml_start:].decode("utf-8", errors="replace").split("\x00")[0]
            )
            self._xml_root = ET.fromstring(xml_text)
            data, self._val_elements = _extract_params(self._xml_root)
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
        if self._xml_root is None:
            return
        val_elem = self._val_elements.get(key)
        if val_elem is not None:
            val_elem.text = str_value
        else:
            ep = ET.SubElement(self._xml_root, "ExporterParam")
            ET.SubElement(ep, "ParamIdentifier").text = key
            val = ET.SubElement(ep, "ParamValue")
            val.text = str_value
            self._val_elements[key] = val
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
        self._set_param(key, str(int_value))

    def _sync_xml(self) -> None:
        """Re-serialize the XML tree back to the raw body."""
        if self._xml_root is None or self._xml_header is None:
            return
        xml_bytes = b"<?xml version='1.0' encoding='UTF-8'?>\n" + ET.tostring(
            self._xml_root, encoding="unicode"
        ).encode("utf-8")  # NOTE Use xml_declaration when 3.7 is dropped
        self._body.data = self._xml_header + xml_bytes

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
    """The MPEG audio format as an [MPEGAudioFormat][] FourCC integer
    value extracted from the `ADBEMPEGAudioFormat` parameter, or
    `None` when the parameter is absent. Falls back to a plain `int`
    when the value is not in the [MPEGAudioFormat][] enum.
    Read / Write."""

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
