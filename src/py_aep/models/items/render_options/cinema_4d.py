"""Cinema 4D (`ADBE Ernst`) render options."""

from __future__ import annotations

from ...descriptors import ChunkField
from ...validators import validate_cinema_4d_quality
from .render_options_base import RenderOptionsBase


class Cinema4DRenderOptions(RenderOptionsBase):
    """Options for the Cinema 4D renderer."""

    _SPEC = {"Quality": ("quality", None)}

    quality = ChunkField[int](
        "_body", "quality", validate=validate_cinema_4d_quality
    )
    """Renderer quality, `1` to `99`. Read / Write."""
