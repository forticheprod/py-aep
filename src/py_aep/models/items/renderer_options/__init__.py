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
from .advanced import AdvancedRendererOptions
from .cinema_4d import Cinema4DRendererOptions
from .classic import ClassicRendererOptions
from .ray_traced import RayTracedRendererOptions
from .renderer_options_base import RendererOptionsBase

if TYPE_CHECKING:
    from ....binary.chunk import Chunk
    from ..composition import CompItem

RendererOptions = Union[
    AdvancedRendererOptions,
    Cinema4DRendererOptions,
    ClassicRendererOptions,
    RayTracedRendererOptions,
    # Unrecognised prda variants fall back to the empty base wrapper.
    RendererOptionsBase,
]

_WRAPPERS: dict[type, type[RendererOptionsBase]] = {
    ClassicPrdaChunk: ClassicRendererOptions,
    AdvancedPrdaChunk: AdvancedRendererOptions,
    Cinema4DPrdaChunk: Cinema4DRendererOptions,
    RayTracedPrdaChunk: RayTracedRendererOptions,
}


def renderer_options_for(body: Chunk, comp: CompItem) -> RendererOptions:
    """Wrapper for a comp's `prda` chunk.

    Falls back to an empty `RendererOptionsBase` for an unrecognised chunk,
    so a future renderer reads as "no options exposed" rather than raising.
    """
    wrapper_cls = _WRAPPERS.get(type(body), RendererOptionsBase)
    return wrapper_cls(body=body, comp=comp)


__all__ = [
    "AdvancedRendererOptions",
    "Cinema4DRendererOptions",
    "ClassicRendererOptions",
    "RayTracedRendererOptions",
    "RendererOptions",
    "RendererOptionsBase",
    "renderer_options_for",
]
