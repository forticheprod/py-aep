"""Chunk tree navigation helpers for the binary I/O layer."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, TypeVar, cast

from .chunk import Chunk, ListChunk
from .scalar_chunks import Utf8Chunk

if TYPE_CHECKING:
    from typing import Any, Sequence

_T = TypeVar("_T")


class ChunkNotFoundError(Exception):
    """Raised when a required chunk is not found in the AEP chunk tree."""


#: Sentinel value indicating an undefined frame number in the binary format.
UNDEFINED_FRAME = 0xFFFFFFFF


def find_by_type(chunks: list[Chunk], chunk_type: str) -> Chunk:
    """Return first chunk matching `chunk_type`.

    Raises:
        ChunkNotFoundError: If no matching chunk is found.
    """
    for c in chunks:
        if c.chunk_type == chunk_type:
            return c
    raise ChunkNotFoundError(f"Missing {chunk_type} chunk")


def find_by_list_type(chunks: list[Chunk], list_type: str) -> ListChunk:
    """Return first ListChunk with matching `list_type`.

    Raises:
        ChunkNotFoundError: If no matching LIST chunk is found.
    """
    for c in chunks:
        if isinstance(c, ListChunk) and c.list_type == list_type:
            return c
    raise ChunkNotFoundError(f"Missing LIST/{list_type} chunk")


def filter_by_type(chunks: list[Chunk], chunk_type: str) -> list[Chunk]:
    """Return all chunks matching `chunk_type`."""
    return [c for c in chunks if c.chunk_type == chunk_type]


def filter_by_list_type(chunks: list[Chunk], list_type: str) -> list[ListChunk]:
    """Return all ListChunks with matching `list_type`."""
    return [c for c in chunks if isinstance(c, ListChunk) and c.list_type == list_type]


def index_by_identity(chunks: Sequence[_T], target: object) -> int:
    """Index of `target` in `chunks` by object identity.

    attrs `@define` chunks compare structurally, so `list.index()` can
    match a different, byte-equal chunk; identity avoids that.

    Raises:
        ValueError: If `target` is not found in `chunks`.
    """
    for i, c in enumerate(chunks):
        if c is target:
            return i
    raise ValueError("target chunk not found in chunk list")


def block_slice(
    chunks: list[Chunk],
    target: Chunk,
    boundary_list_types: frozenset[str],
) -> tuple[int, int]:
    """Return `(start, end)` indices of a contiguous block starting at `target`.

    Scans forward from `target` until a `ListChunk` whose `list_type` is
    in `boundary_list_types`, or the end of the list.  Uses identity
    comparison (`is`) to locate `target`.

    Args:
        chunks: The chunk list to search.
        target: The chunk that starts the block (matched by identity).
        boundary_list_types: `list_type` values that mark the beginning of
            the next block.

    Raises:
        ValueError: If `target` is not found in `chunks`.
    """
    start = index_by_identity(chunks, target)
    for end in range(start + 1, len(chunks)):
        c = chunks[end]
        if isinstance(c, ListChunk) and c.list_type in boundary_list_types:
            return start, end
    return start, len(chunks)


def _find_anchor_index(chunks: list[Chunk], anchor_type: str) -> int:
    """Return the index of the first chunk matching `anchor_type`.

    `anchor_type` can be a plain chunk type (e.g. `"opti"`) or a LIST type
    prefixed with `"LIST:"` (e.g. `"LIST:Als2"`).

    Raises:
        ChunkNotFoundError: If no matching chunk is found.
    """
    if anchor_type.startswith("LIST:"):
        lt = anchor_type[5:]
        for i, c in enumerate(chunks):
            if getattr(c, "list_type", None) == lt:
                return i
        raise ChunkNotFoundError(f"Missing LIST/{lt} chunk")

    for i, c in enumerate(chunks):
        if c.chunk_type == anchor_type:
            return i
    raise ChunkNotFoundError(f"Missing {anchor_type} chunk")


def find_chunks_before(
    chunks: list[Chunk],
    chunk_type: str,
    before_type: str,
) -> list[Chunk]:
    """Return consecutive chunks of `chunk_type` immediately before `before_type`.

    Scans `chunks` for the first occurrence of `before_type`, then collects the
    uninterrupted run of `chunk_type` chunks that directly precede it.

    `before_type` can be a plain chunk type (e.g. `"opti"`) or a LIST type
    prefixed with `"LIST:"` (e.g. `"LIST:Als2"`).

    Raises:
        ChunkNotFoundError: If no chunk with `before_type` is found.
    """
    anchor = _find_anchor_index(chunks, before_type)
    result: list[Chunk] = []
    for i in range(anchor - 1, -1, -1):
        if chunks[i].chunk_type == chunk_type:
            result.insert(0, chunks[i])
        else:
            break
    return result


def find_chunks_after(
    chunks: list[Chunk],
    chunk_type: str,
    after_type: str,
) -> list[Chunk]:
    """Return consecutive chunks of `chunk_type` immediately after `after_type`.

    Scans `chunks` for the first occurrence of `after_type`, then collects the
    uninterrupted run of `chunk_type` chunks that directly follow it.

    `after_type` can be a plain chunk type (e.g. `"opti"`) or a LIST type
    prefixed with `"LIST:"` (e.g. `"LIST:Als2"`).

    Raises:
        ChunkNotFoundError: If no chunk with `after_type` is found.
    """
    anchor = _find_anchor_index(chunks, after_type)
    result: list[Chunk] = []
    for i in range(anchor + 1, len(chunks)):
        if chunks[i].chunk_type == chunk_type:
            result.append(chunks[i])
        else:
            break
    return result


def group_chunks(
    chunks: list[Chunk],
    start_type: str,
    end_type: str,
) -> list[list[Chunk]]:
    """Split `chunks` into groups bounded by `start_type` ... `end_type` (inclusive).

    Chunks that fall outside any group are ignored.
    """
    groups: list[list[Chunk]] = []
    current: list[Chunk] | None = None
    for chunk in chunks:
        if chunk.chunk_type == start_type and current is None:
            current = [chunk]
        elif current is not None:
            current.append(chunk)
            if chunk.chunk_type == end_type:
                groups.append(current)
                current = None
    return groups


def split_on_type(
    chunks: list[Chunk],
    chunk_type: str,
) -> list[list[Chunk]]:
    """Split `chunks` into groups starting at each occurrence of `chunk_type`.

    Every time a chunk with `chunk_type` is encountered a new group begins.
    Chunks that appear before the first occurrence are discarded.
    """
    groups: list[list[Chunk]] = []
    current: list[Chunk] | None = None
    for chunk in chunks:
        if chunk.chunk_type == chunk_type:
            if current is not None:
                groups.append(current)
            current = [chunk]
        elif current is not None:
            current.append(chunk)
    if current is not None:
        groups.append(current)
    return groups


def parse_alas_data(parent_chunks: list[Chunk]) -> dict[str, Any]:
    """Parse path information from an Als2/alas chunk structure.

    Returns:
        Dictionary with alas data (fullpath, target_is_folder, etc.),
        or empty dict if not found or invalid.
    """
    try:
        als2_chunk = find_by_list_type(chunks=parent_chunks, list_type="Als2")
    except ChunkNotFoundError:
        return {}
    try:
        alas_chunk = find_by_type(chunks=als2_chunk.chunks, chunk_type="alas")
    except ChunkNotFoundError:
        return {}
    alas_text = cast("Utf8Chunk", alas_chunk).value
    if not alas_text:
        return {}
    result = json.loads(alas_text)
    return result if isinstance(result, dict) else {}


def build_als2_list(
    fullpath: str,
    *,
    target_is_folder: bool,
) -> ListChunk:
    """Build a `LIST:Als2 -> alas` chunk holding a footage source path.

    Inverse of `parse_alas_data`. AE locates the file via the absolute
    `fullpath`; `ascendcount_*` (relative-path resolution depth) are set
    equal so no relative offset is applied.

    Args:
        fullpath: Absolute path to the file, or the containing folder for
            an image sequence.
        target_is_folder: `True` when `fullpath` is a sequence folder.
    """
    data = {
        "ascendcount_base": 0,
        "ascendcount_target": 0,
        "fullpath": fullpath,
        "platform": 1,  # 1 = Windows
        "server_name": "",
        "server_volume_name": "",
        "target_is_folder": target_is_folder,
    }
    text = json.dumps(data, sort_keys=True, separators=(",", ":"))
    alas = Utf8Chunk(chunk_type="alas", value=text)
    return ListChunk(list_type="Als2", chunks=[alas])


def chunk_tree(
    chunks: list[Chunk],
    depth: int = -1,
    indent: int = 0,
) -> str:
    """Return a text tree representation of chunks for debugging.

    Args:
        chunks: List of chunks to visualize.
        depth: Max depth to recurse (-1 for unlimited).
        indent: Current indentation level (used internally).
    """
    lines: list[str] = []
    prefix = "  " * indent
    for chunk in chunks:
        lt = getattr(chunk, "list_type", None)
        children = getattr(chunk, "chunks", None)
        size = len(getattr(chunk, "data", b""))
        if lt is not None:
            label = f"LIST:{lt}"
            lines.append(f"{prefix}{label}")
            if depth != 0 and children is not None:
                lines.append(chunk_tree(children, depth - 1, indent + 1))
        else:
            lines.append(f"{prefix}{chunk.chunk_type} ({size} B)")
    return "\n".join(lines)


def toggle_flag_chunk(
    container: ListChunk,
    chunk_type: str,
    enable: bool,
    *,
    after_types: tuple[str, ...] = (),
) -> None:
    """Add or remove a flag chunk from a ListChunk container.

    Flag chunks are tiny (1-byte body `b"\\x01"`) presence/absence
    markers.

    Some flag chunks are positional: After Effects reads them in a fixed
    slot and rejects the file ("missing data") when they appear elsewhere.
    Pass `after_types` to insert the new chunk immediately after the last
    chunk of one of those types (e.g. `("cpid",)` for `lnrb`); when none of
    them is present, or `after_types` is empty, the chunk is appended.
    """
    from .chunk import Chunk

    existing = [i for i, c in enumerate(container.chunks) if c.chunk_type == chunk_type]
    if enable and not existing:
        new_chunk = Chunk(chunk_type=chunk_type, data=b"\x01")
        anchors = [
            i for i, c in enumerate(container.chunks) if c.chunk_type in after_types
        ]
        if anchors:
            container.chunks.insert(anchors[-1] + 1, new_chunk)
        else:
            container.chunks.append(new_chunk)
    elif not enable and existing:
        for i in reversed(existing):
            container.chunks.pop(i)


def recursive_find(
    chunks: list[Chunk],
    chunk_type: str | None = None,
    list_type: str | None = None,
) -> list[Chunk]:
    """Recursively search the chunk tree for matching chunks.

    At least one of `chunk_type` or `list_type` must be given.

    Returns:
        All matching chunks across the entire tree, in DFS order.
    """
    if chunk_type is None and list_type is None:
        raise ValueError("At least one of chunk_type or list_type is required")
    results: list[Chunk] = []
    for chunk in chunks:
        if list_type is not None:
            if getattr(chunk, "list_type", None) == list_type:
                results.append(chunk)
        elif chunk.chunk_type == chunk_type:
            results.append(chunk)
        children = getattr(chunk, "chunks", None)
        if children is not None:
            results.extend(recursive_find(children, chunk_type, list_type))
    return results
