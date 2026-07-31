"""Classic 3D (`ADBE Escher`) render options."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....enums import ShadowMapResolution
from ...descriptors import ChunkField
from .render_options_base import RenderOptionsBase

if TYPE_CHECKING:
    from ....binary.misc_chunks import ClassicPrdaChunk

class ClassicRenderOptions(RenderOptionsBase):
    """Options for the Classic 3D renderer."""

    _body: ClassicPrdaChunk

    _SPEC = {"Shadow Map Resolution": ("shadow_map_resolution", ShadowMapResolution)}

    shadow_map_resolution = ChunkField.enum(
        ShadowMapResolution, "_body", "shadow_map_resolution"
    )
    """
    Resolution of the shadow map, as set in the Classic 3D Options dialog.
    Read / Write.
    """
