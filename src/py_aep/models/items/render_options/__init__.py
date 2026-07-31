"""Per-renderer 3D render options.

One wrapper class per renderer, selected from the `prda` chunk variant dispatch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

from ....binary.misc_chunks import (
    AdvancedPrdaChunk,
    Cinema4DPrdaChunk,
    ClassicPrdaChunk,
    RayTracedPrdaChunk,
)
from .advanced import AdvancedRenderOptions
from .cinema_4d import Cinema4DRenderOptions
from .classic import ClassicRenderOptions
from .ray_traced import RayTracedRenderOptions
from .render_options_base import RenderOptionsBase

if TYPE_CHECKING:
    from ....binary.chunk import Chunk
    from ..composition import CompItem

RenderOptions = Union[
    AdvancedRenderOptions,
    Cinema4DRenderOptions,
    ClassicRenderOptions,
    RayTracedRenderOptions,
]

_WRAPPERS: dict[type, type[RenderOptionsBase]] = {
    ClassicPrdaChunk: ClassicRenderOptions,
    AdvancedPrdaChunk: AdvancedRenderOptions,
    Cinema4DPrdaChunk: Cinema4DRenderOptions,
    RayTracedPrdaChunk: RayTracedRenderOptions,
}


def render_options_for(body: Chunk, comp: CompItem) -> RenderOptionsBase:
    """Wrapper for a comp's `prda` chunk.

    Falls back to an empty `RenderOptionsBase` for an unrecognised chunk,
    so a future renderer reads as "no options exposed" rather than raising.
    """
    wrapper_cls = _WRAPPERS.get(type(body), RenderOptionsBase)
    return wrapper_cls(body=body, comp=comp)


__all__ = [
    "AdvancedRenderOptions",
    "Cinema4DRenderOptions",
    "ClassicRenderOptions",
    "RayTracedRenderOptions",
    "RenderOptions",
    "RenderOptionsBase",
    "render_options_for",
]
