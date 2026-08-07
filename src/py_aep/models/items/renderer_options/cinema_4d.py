"""Cinema 4D (`ADBE Ernst`) render options."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...descriptors import ChunkField
from ...validators import validate_cinema_4d_quality
from .renderer_options_base import RendererOptionsBase

if TYPE_CHECKING:
    from ....binary.misc_chunks import Cinema4DPrdaChunk


class Cinema4DRendererOptions(RendererOptionsBase):
    """Options for the Cinema 4D renderer."""

    _body: Cinema4DPrdaChunk

    _SPEC = {"Quality": ("quality", None)}

    quality = ChunkField[int]("_body", "quality", validate=validate_cinema_4d_quality)
    """Renderer quality, `1` to `99`. Read / Write."""
