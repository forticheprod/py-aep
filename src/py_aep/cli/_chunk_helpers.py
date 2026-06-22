"""Shared helpers for AEP CLI tools.

Provides chunk labeling, path building, tree walking, and hex formatting
used by both `aep-compare` and `aep-inspect`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..binary.chunk import ListChunk, read_aep

if TYPE_CHECKING:
    from typing import Iterator

    from ..binary.chunk import Chunk


def chunk_label(chunk: Chunk) -> str:
    """Return a human-readable label for a chunk.

    Args:
        chunk: A parsed chunk object.

    Returns:
        `LIST:<list_type>` for list chunks, otherwise the chunk type string.
    """
    chunk_type = str(chunk.chunk_type)
    if chunk_type == "LIST" and hasattr(chunk, "list_type"):
        return f"LIST:{chunk.list_type}"
    return chunk_type


def build_chunk_path(
    parent_path: str,
    identifier: str,
    counters: dict[str, int],
) -> str:
    """Build a chunk path with duplicate indexing.

    Tracks how many times each identifier has been seen at a given level
    and appends `[N]` when a duplicate is encountered.

    Args:
        parent_path: Parent chunk path prefix.
        identifier: Chunk identifier (e.g. `ldta`, `LIST:Fold`).
        counters: Mutable counter dict tracking duplicates at this level.

    Returns:
        Full chunk path string.
    """
    counter_key = parent_path + "/" + identifier if parent_path else identifier

    if counter_key not in counters:
        counters[counter_key] = 0
    else:
        counters[counter_key] += 1

    if counters[counter_key] > 0:
        return (
            f"{parent_path}/{identifier}[{counters[counter_key]}]"
            if parent_path
            else f"{identifier}[{counters[counter_key]}]"
        )
    return f"{parent_path}/{identifier}" if parent_path else identifier


def walk_chunks(
    chunks: list[Chunk],
    parent_path: str = "",
    depth: int = 0,
) -> Iterator[tuple[str, str, int, int, bool]]:
    """Walk a chunk tree yielding metadata for each node.

    Args:
        chunks: List of chunk objects.
        parent_path: Parent chunk path prefix.
        depth: Current nesting depth.

    Yields:
        Tuples of `(full_path, identifier, raw_data_size, depth, is_list)`.
    """
    counters: dict[str, int] = {}

    for chunk in chunks:
        identifier = chunk_label(chunk)
        current_path = build_chunk_path(parent_path, identifier, counters)

        size = len(chunk.tobytes()) if chunk.chunk_type != "LIST" else 0
        is_list = isinstance(chunk, ListChunk) and chunk.chunks is not None
        yield current_path, identifier, size, depth, is_list

        if isinstance(chunk, ListChunk) and chunk.chunks is not None:
            yield from walk_chunks(chunk.chunks, current_path, depth + 1)


def _extract_chunks_recursive(
    chunks: list[Chunk],
    parent_path: str,
    result: dict[str, bytes],
    counters: dict[str, int] | None = None,
    typed: dict[str, Chunk] | None = None,
) -> None:
    """Recursively extract leaf chunk data with paths.

    Stores raw data for all non-LIST (leaf) chunks, including empty ones.
    LIST chunks are traversed but their aggregate raw data is not stored,
    so diff output only appears at the deepest chunk level. When `typed`
    is provided, the decoded leaf `Chunk` objects are stored alongside the
    raw bytes (used for float-tolerant comparison).
    """
    if counters is None:
        counters = {}

    for chunk in chunks:
        identifier = chunk_label(chunk)
        current_path = build_chunk_path(parent_path, identifier, counters)

        if isinstance(chunk, ListChunk):
            if chunk.chunks:
                child_counters: dict[str, int] = {}
                _extract_chunks_recursive(
                    chunk.chunks, current_path, result, child_counters, typed
                )
        else:
            # Store all leaf chunks, including empty ones, so missing
            # empty chunks (e.g. Utf8 with no content) are detected
            result[current_path] = chunk.tobytes()
            if typed is not None:
                typed[current_path] = chunk


def extract_leaf_chunks(file_path: Path) -> dict[str, bytes]:
    """Parse an AEP file and extract leaf chunk data with paths.

    Args:
        file_path: Path to the `.aep` file.

    Returns:
        Dict mapping chunk paths to their raw binary data.
        Only leaf chunks (non-LIST) are included.
    """
    return extract_leaf_chunks_typed(file_path)[0]


def extract_leaf_chunks_typed(
    file_path: Path,
) -> tuple[dict[str, bytes], dict[str, Chunk]]:
    """Like `extract_leaf_chunks`, but also return the decoded leaf chunks.

    Returns:
        A tuple `(raw_bytes_by_path, typed_chunk_by_path)`. The typed
        chunks let callers compare numeric fields (e.g. float coordinates)
        with tolerance instead of byte-exactly.
    """
    with open(file_path, "rb") as f:
        rifx, _xmp = read_aep(f)
    result: dict[str, bytes] = {}
    typed: dict[str, Chunk] = {}
    _extract_chunks_recursive(rifx.chunks, "", result, typed=typed)
    return result, typed


def format_hex_dump(data: bytes, bytes_per_line: int = 16) -> str:
    """Format binary data as a hex dump with ASCII representation.

    Args:
        data: Raw bytes to format.
        bytes_per_line: Number of bytes per output line.

    Returns:
        Multi-line hex dump string.
    """
    lines: list[str] = []
    mid = bytes_per_line // 2

    for i in range(0, len(data), bytes_per_line):
        chunk = data[i : i + bytes_per_line]

        left_bytes = chunk[:mid]
        right_bytes = chunk[mid:]
        left = " ".join(f"{b:02X}" for b in left_bytes)
        right = " ".join(f"{b:02X}" for b in right_bytes)

        if right:
            hex_str = f"{left}  {right}"
        else:
            hex_str = left

        full_width = (mid * 3 - 1) + 2 + (mid * 3 - 1)
        hex_str = hex_str.ljust(full_width)

        ascii_str = "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in chunk)
        lines.append(f"{i:04X}: {hex_str}  {ascii_str}")

    return "\n".join(lines)
