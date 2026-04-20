from __future__ import annotations

import json
import typing
from typing import Any

from ....enums import Hdr10ColorPrimaries, PngCompression
from ....kaitai.descriptors import ChunkField
from ....kaitai.utils import propagate_check
from ...validators import validate_one_of

if typing.TYPE_CHECKING:
    from ....kaitai import Aep


class PngFormatOptions:
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
        _body: Aep.PngRoptData,
        _hdr10_utf8: Aep.Utf8Body | None = None,
    ) -> None:
        self._body = _body
        self._hdr10_utf8 = _hdr10_utf8
        self._hdr10_meta: dict[str, Any] = {}
        if _hdr10_utf8 is not None:
            text = _hdr10_utf8.contents.split("\x00")[0]
            try:
                parsed = json.loads(text)
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

    compression = ChunkField[PngCompression](
        "_body",
        "compression",
        transform=PngCompression,
        reverse_seq_field=int,
    )
    """
    The PNG compression / interlace mode. Corresponds to the
    `Compression` dropdown in the PNG Options dialog. Read / Write.
    """

    def _sync_hdr10(self) -> None:
        """Serialize `_hdr10_meta` back to the Utf8 chunk body."""
        if self._hdr10_utf8 is not None:
            self._hdr10_utf8.contents = json.dumps(
                self._hdr10_meta, separators=(",", ":")
            )
            propagate_check(self._hdr10_utf8)

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
        self._hdr10_meta["colorMetadataPresent"] = value
        self._sync_hdr10()

    @property
    def color_primaries(self) -> Hdr10ColorPrimaries:
        """
        The color primaries used for HDR10 metadata. Corresponds to the
        `Color Primaries` dropdown in the PNG Options dialog.
        Only meaningful when `include_hdr10_metadata` is `True`. Read / Write.
        """
        raw = self._hdr10_meta.get("displayPrimaries")
        if raw is None:
            return Hdr10ColorPrimaries.P3_D65
        return Hdr10ColorPrimaries(int(raw))

    @color_primaries.setter
    def color_primaries(self, value: Hdr10ColorPrimaries) -> None:
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
            self._hdr10_meta["maxFrameAverageLightLevel"] = value
        self._sync_hdr10()
