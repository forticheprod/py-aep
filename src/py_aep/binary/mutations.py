"""Chunk tree mutation helpers for the binary I/O layer."""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from .chunk import ListChunk, read_chunks, write_chunk
from .ldat_chunks import GdtaChunk, Lhd3Chunk

if TYPE_CHECKING:
    from typing import Callable

    from .chunk import Chunk


def remove_chunks_by_type(
    chunks: list[Chunk],
    chunk_type: str,
) -> None:
    """Remove all chunks of `chunk_type` from the list in-place."""
    i = len(chunks) - 1
    while i >= 0:
        if chunks[i].chunk_type == chunk_type:
            del chunks[i]
        i -= 1


def toggle_flag_chunk(
    chunks: list[Chunk],
    chunk_type: str,
    enable: bool,
    factory: Callable[[], Chunk],
) -> None:
    """Add or remove a single-byte flag chunk.

    When `enable` is true and no chunk of `chunk_type` exists, call
    `factory()` to create one and append it. When false, remove all
    matching chunks.
    """
    has = any(c.chunk_type == chunk_type for c in chunks)
    if enable and not has:
        chunks.append(factory())
    elif not enable and has:
        remove_chunks_by_type(chunks, chunk_type)


def _unflag_markers(
    parent_chunks: list[Chunk],
    target: ListChunk,
) -> None:
    """Clear the `synthetic` flag on tdmn chunks adjacent to `target`."""
    idx = None
    for i, c in enumerate(parent_chunks):
        if c is target:
            idx = i
            break
    if idx is None:
        return
    if idx > 0 and parent_chunks[idx - 1].chunk_type == "tdmn":
        parent_chunks[idx - 1].synthetic = False
    if idx + 1 < len(parent_chunks) and parent_chunks[idx + 1].chunk_type == "tdmn":
        parent_chunks[idx + 1].synthetic = False


def clone_chunk_tree(chunk: Chunk) -> Chunk:
    """Deep-copy a chunk tree via serialize/deserialize round-trip.

    Synthetic chunks are excluded during serialization, so the clone
    contains only real (non-synthetic) chunks.
    """
    buf = BytesIO()
    size = write_chunk(buf, chunk)
    buf.seek(0)
    return read_chunks(buf, size)[0]


def build_gide_list() -> tuple[ListChunk, Lhd3Chunk, ListChunk]:
    """Build an empty `LIST:Gide` guide container.

    Returns:
        (gide, lhd3, inner) - the outer Gide list, header chunk,
        and inner `LIST:list`.  Callers can append an `LdatChunk`
        to *inner* when guide data is needed.
    """
    lhd3 = Lhd3Chunk(item_size=16, item_type_raw=2)
    inner = ListChunk(list_type="list", chunks=[lhd3])
    gide = ListChunk(list_type="Gide", chunks=[GdtaChunk(), inner])
    return gide, lhd3, inner
