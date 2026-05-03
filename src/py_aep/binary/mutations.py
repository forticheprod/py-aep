"""Chunk tree mutation helpers for the binary I/O layer."""
from __future__ import annotations

from typing import TYPE_CHECKING

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
    target: Chunk,
) -> None:
    """Clear the `synthetic` flag on tdmn chunks adjacent to *target*."""
    idx = None
    for i, c in enumerate(parent_chunks):
        if c is target:
            idx = i
            break
    if idx is None:
        return
    if idx > 0 and parent_chunks[idx - 1].chunk_type == "tdmn":
        parent_chunks[idx - 1].synthetic = False
    if (
        idx + 1 < len(parent_chunks)
        and parent_chunks[idx + 1].chunk_type == "tdmn"
    ):
        parent_chunks[idx + 1].synthetic = False
