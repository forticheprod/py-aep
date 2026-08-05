"""Classic 3D (`ADBE Escher`) render options."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....enums import ShadowMapResolution
from ...descriptors import ChunkField
from .renderer_options_base import RendererOptionsBase

if TYPE_CHECKING:
    from ....binary.misc_chunks import ClassicPrdaChunk


class ClassicRendererOptions(RendererOptionsBase):
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
