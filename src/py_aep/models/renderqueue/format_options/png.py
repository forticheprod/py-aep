from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from ....enums import Hdr10ColorPrimaries, PngCompression
from ...descriptors import ChunkField, enum_or_raw
from ...validators import validate_enum, validate_one_of, validate_positive_number
from .base import FormatOptionsBase

if TYPE_CHECKING:
    from ....binary.render_chunks import PngRoptChunk
    from ....binary.scalar_chunks import Utf8Chunk


class PngFormatOptions(FormatOptionsBase):
    """PNG format-specific render options.

    These settings correspond to the PNG Options dialog in After Effects,
    accessible when the output format is set to PNG Sequence.

    The Ropt body for PNG contains a fixed-size binary block (typically 318
    bytes) with width, height, and bit depth at known offsets. HDR10 metadata
    is stored separately in a JSON `Utf8` chunk alongside the Ropt chunk.

    Example:
        ```python
        from py_aep import PngFormatOptions, parse

        app = parse("project.aep")
        om = app.project.render_queue.items[0].output_modules[0]
        if isinstance(om.format_options, PngFormatOptions):
            print(om.format_options.compression)
        ```
    """

    def __init__(
        self,
        *,
        _body: PngRoptChunk,
        _hdr10_utf8: Utf8Chunk | None = None,
    ) -> None:
        self._body = _body
        self._hdr10_utf8 = _hdr10_utf8
        self._hdr10_meta: dict[str, Any] = {}
        if _hdr10_utf8 is not None:
            try:
                parsed = json.loads(_hdr10_utf8.value)
                if isinstance(parsed, dict):
                    self._hdr10_meta = parsed
            except (json.JSONDecodeError, ValueError):
                pass

    width = ChunkField[int]("_body", "width", read_only=True)
    """The output width in pixels. Read-only."""

    height = ChunkField[int]("_body", "height", read_only=True)
    """The output height in pixels. Read-only."""

    bit_depth = ChunkField[int](
        "_body", "bit_depth", validate=validate_one_of([8, 16, 32])
    )
    """
    The output bit depth per channel.
    Common values are `8` and `16`. Read / Write.
    """

    compression = ChunkField.enum(
        PngCompression,
        "_body",
        "compression",
        allow_out_of_enum_values=True,
    )
    """
    The PNG compression / interlace mode. Corresponds to the
    `Compression` dropdown in the PNG Options dialog. An out-of-enum
    stored value reads back as a raw `int` (the binary is trusted).
    Read / Write.
    """

    def _sync_hdr10(self) -> None:
        """Serialize `_hdr10_meta` back to the Utf8 chunk body."""
        if self._hdr10_utf8 is not None:
            self._hdr10_utf8.value = json.dumps(self._hdr10_meta, separators=(",", ":"))

    @property
    def include_hdr10_metadata(self) -> bool:
        """
        Whether HDR10 metadata is embedded in the PNG output.
        Corresponds to the `Include HDR10 Metadata` checkbox in the PNG
        Options dialog. Only available for 16-bit output. Read / Write.
        """
        return bool(self._hdr10_meta.get("colorMetadataPresent", False))

    @include_hdr10_metadata.setter
    def include_hdr10_metadata(self, value: bool) -> None:
        self._hdr10_meta["colorMetadataPresent"] = bool(value)
        self._sync_hdr10()

    @property
    def color_primaries(self) -> Hdr10ColorPrimaries | int:
        """
        The color primaries used for HDR10 metadata. Corresponds to the
        `Color Primaries` dropdown in the PNG Options dialog.
        Only meaningful when `include_hdr10_metadata` is `True`. An
        out-of-enum stored value reads back as a raw `int` (the binary
        is trusted). Read / Write.
        """
        raw = self._hdr10_meta.get("displayPrimaries")
        if raw is None:
            return Hdr10ColorPrimaries.P3_D65
        return cast(
            "Hdr10ColorPrimaries | int",
            enum_or_raw(lambda v: Hdr10ColorPrimaries(int(v)))(raw),
        )

    @color_primaries.setter
    def color_primaries(self, value: Hdr10ColorPrimaries) -> None:
        validate_enum(Hdr10ColorPrimaries)(value)
        self._hdr10_meta["displayPrimaries"] = int(value)
        self._sync_hdr10()

    @property
    def luminance_min(self) -> float | None:
        """
        The minimum display luminance in nits for HDR10 metadata, or
        `None` if not explicitly set. Corresponds to the
        `Luminance Minimum` field in the PNG Options dialog. Read / Write.
        """
        raw = self._hdr10_meta.get("minLuminance")
        return float(raw) if raw is not None else None

    @luminance_min.setter
    def luminance_min(self, value: float | None) -> None:
        if value is None:
            self._hdr10_meta.pop("minLuminance", None)
        else:
            validate_positive_number(value)
            self._hdr10_meta["minLuminance"] = value
        self._sync_hdr10()

    @property
    def luminance_max(self) -> float | None:
        """
        The maximum display luminance in nits for HDR10 metadata, or
        `None` if not explicitly set. Corresponds to the
        `Luminance Maximum` field in the PNG Options dialog. Read / Write.
        """
        raw = self._hdr10_meta.get("maxLuminance")
        return float(raw) if raw is not None else None

    @luminance_max.setter
    def luminance_max(self, value: float | None) -> None:
        if value is None:
            self._hdr10_meta.pop("maxLuminance", None)
        else:
            validate_positive_number(value)
            self._hdr10_meta["maxLuminance"] = value
        self._sync_hdr10()

    @property
    def content_light_max(self) -> float | None:
        """
        The maximum content light level in nits for HDR10 metadata, or
        `None` if not explicitly set. Corresponds to the
        `Content Light Maximum` field in the PNG Options dialog. Read / Write.
        """
        raw = self._hdr10_meta.get("maxContentLightLevel")
        return float(raw) if raw is not None else None

    @content_light_max.setter
    def content_light_max(self, value: float | None) -> None:
        if value is None:
            self._hdr10_meta.pop("maxContentLightLevel", None)
        else:
            validate_positive_number(value)
            self._hdr10_meta["maxContentLightLevel"] = value
        self._sync_hdr10()

    @property
    def content_light_average(self) -> float | None:
        """
        The maximum frame average light level in nits for HDR10 metadata,
        or `None` if not explicitly set. Corresponds to the
        `Content Light Average` field in the PNG Options dialog. Read / Write.
        """
        raw = self._hdr10_meta.get("maxFrameAverageLightLevel")
        return float(raw) if raw is not None else None

    @content_light_average.setter
    def content_light_average(self, value: float | None) -> None:
        if value is None:
            self._hdr10_meta.pop("maxFrameAverageLightLevel", None)
        else:
            validate_positive_number(value)
            self._hdr10_meta["maxFrameAverageLightLevel"] = value
        self._sync_hdr10()
