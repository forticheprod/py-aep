from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..binary.footage_chunks import OptiChunk, SspcChunk
from ..binary.scalar_chunks import U1Chunk
from ..binary.utils import (
    ChunkNotFoundError,
    find_by_list_type,
    find_by_type,
)
from ..models.sources.file import FileSource
from ..models.sources.placeholder import PlaceholderSource
from ..models.sources.solid import SolidSource

if TYPE_CHECKING:
    from ..binary.chunk import ListChunk


def parse_source(
    pin_chunk: ListChunk,
) -> FileSource | SolidSource | PlaceholderSource:
    """Parse a `LIST:Pin` chunk into a footage source.

    Args:
        pin_chunk: A `LIST:Pin` chunk containing sspc + opti sub-chunks.
    """
    pin_child_chunks = pin_chunk.chunks
    sspc_chunk = cast(
        "SspcChunk", find_by_type(chunks=pin_child_chunks, chunk_type="sspc")
    )
    opti_chunk = cast(
        "OptiChunk", find_by_type(chunks=pin_child_chunks, chunk_type="opti")
    )

    try:
        clrs = find_by_list_type(chunks=pin_child_chunks, list_type="CLRS")
        try:
            linl: U1Chunk | None = cast(
                "U1Chunk", find_by_type(chunks=clrs.chunks, chunk_type="linl")
            )
        except ChunkNotFoundError:
            linl = None
    except ChunkNotFoundError:
        clrs = None
        linl = None

    asset_type = getattr(opti_chunk, "asset_type", "")

    if not asset_type and hasattr(opti_chunk, "placeholder_name"):
        return PlaceholderSource(
            _sspc=sspc_chunk,
            _opti=opti_chunk,
            _clrs=clrs,
            _linl=linl,
        )
    if asset_type.startswith("Soli"):
        return SolidSource(_sspc=sspc_chunk, _opti=opti_chunk, _clrs=clrs, _linl=linl)
    return FileSource(
        _pin=pin_chunk,
        _sspc=sspc_chunk,
        _opti=opti_chunk,
        _linl=linl,
        _clrs=clrs,
    )
