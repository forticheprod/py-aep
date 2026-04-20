from __future__ import annotations

import json
import typing
from io import BytesIO
from typing import Any

from kaitaistruct import KaitaiStream, ReadWriteKaitaiStruct

from .aep import Aep  # type: ignore[attr-defined]  # auto-generated

if typing.TYPE_CHECKING:
    from typing import Callable


class ChunkNotFoundError(Exception):
    """Raised when a required chunk is not found in the AEP file structure."""

    pass


def _find_chunk(
    chunks: list[Aep.Chunk],
    func: Callable[[Aep.Chunk], bool],
    description: str,
) -> Aep.Chunk:
    """Perform a basic find operation over a chunks list.

    Args:
        chunks: List of chunks to search.
        func: Predicate function to match chunks.
        description: Human-readable description for error message.

    Raises:
        ChunkNotFoundError: If no matching chunk is found.
    """
    for chunk in chunks:
        if func(chunk):
            return chunk
    raise ChunkNotFoundError(f"Missing {description}")


def find_by_type(
    chunks: list[Aep.Chunk],
    chunk_type: str,
) -> Aep.Chunk:
    """Return first chunk that has the provided chunk_type.

    Raises:
        ChunkNotFoundError: If no chunk with the given type is found.
    """
    return _find_chunk(
        chunks=chunks,
        func=lambda chunk: chunk.chunk_type == chunk_type,
        description=f"{chunk_type} chunk",
    )


def find_by_list_type(
    chunks: list[Aep.Chunk],
    list_type: str,
) -> Aep.Chunk:
    """Return first LIST chunk that has the provided list_type.

    Raises:
        ChunkNotFoundError: If no LIST chunk with the given list_type is found.
    """
    return _find_chunk(
        chunks=chunks,
        func=lambda chunk: (
            chunk.chunk_type == "LIST" and chunk.body.list_type == list_type
        ),
        description=f"LIST/{list_type} chunk",
    )


def _filter_chunks(
    chunks: list[Aep.Chunk], func: Callable[[Aep.Chunk], bool]
) -> list[Aep.Chunk]:
    """Perform a basic filter operation over a chunks list."""
    return list(filter(func, chunks))


def filter_by_list_type(chunks: list[Aep.Chunk], list_type: str) -> list[Aep.Chunk]:
    """Return LIST chunks that have the provided list_type."""
    return _filter_chunks(
        chunks=chunks,
        func=lambda chunk: (
            chunk.chunk_type == "LIST" and chunk.body.list_type == list_type
        ),
    )


def filter_by_type(chunks: list[Aep.Chunk], chunk_type: str) -> list[Aep.Chunk]:
    """Return chunks that have the provided chunk_type."""
    return _filter_chunks(
        chunks=chunks, func=lambda chunk: chunk.chunk_type == chunk_type
    )


def _find_anchor_index(
    chunks: list[Aep.Chunk],
    anchor_type: str,
) -> int:
    """Return the index of the first chunk matching *anchor_type*.

    *anchor_type* can be a plain chunk type (e.g. `"opti"`) or a LIST type
    prefixed with `"LIST:"` (e.g. `"LIST:Als2"`).

    Raises:
        ChunkNotFoundError: If no matching chunk is found.
    """
    if anchor_type.startswith("LIST:"):
        list_type = anchor_type[5:]
        for i, chunk in enumerate(chunks):
            if chunk.chunk_type == "LIST" and chunk.body.list_type == list_type:
                return i
        raise ChunkNotFoundError(f"Missing LIST/{list_type} chunk")

    for i, chunk in enumerate(chunks):
        if chunk.chunk_type == anchor_type:
            return i
    raise ChunkNotFoundError(f"Missing {anchor_type} chunk")


def find_chunks_before(
    chunks: list[Aep.Chunk],
    chunk_type: str,
    before_type: str,
) -> list[Aep.Chunk]:
    """Return consecutive chunks of `chunk_type` immediately before `before_type`.

    Scans *chunks* for the first occurrence of *before_type*, then collects the
    uninterrupted run of *chunk_type* chunks that directly precede it.

    *before_type* can be a plain chunk type (e.g. `"opti"`) or a LIST type
    prefixed with `"LIST:"` (e.g. `"LIST:Als2"`).

    Args:
        chunks: List of chunks to search.
        chunk_type: The type of chunks to collect.
        before_type: The anchor chunk type that follows the desired run.

    Raises:
        ChunkNotFoundError: If no chunk with *before_type* is found.
    """
    anchor_index = _find_anchor_index(chunks, before_type)

    result: list[Aep.Chunk] = []
    for i in range(anchor_index - 1, -1, -1):
        if chunks[i].chunk_type == chunk_type:
            result.insert(0, chunks[i])
        else:
            break
    return result


def find_chunks_after(
    chunks: list[Aep.Chunk],
    chunk_type: str,
    after_type: str,
) -> list[Aep.Chunk]:
    """Return consecutive chunks of `chunk_type` immediately after `after_type`.

    Scans *chunks* for the first occurrence of *after_type*, then collects the
    uninterrupted run of *chunk_type* chunks that directly follow it.

    *after_type* can be a plain chunk type (e.g. `"opti"`) or a LIST type
    prefixed with `"LIST:"` (e.g. `"LIST:Als2"`).

    Args:
        chunks: List of chunks to search.
        chunk_type: The type of chunks to collect.
        after_type: The anchor chunk type that precedes the desired run.

    Raises:
        ChunkNotFoundError: If no chunk with *after_type* is found.
    """
    anchor_index = _find_anchor_index(chunks, after_type)

    result: list[Aep.Chunk] = []
    for i in range(anchor_index + 1, len(chunks)):
        if chunks[i].chunk_type == chunk_type:
            result.append(chunks[i])
        else:
            break
    return result


def group_chunks(
    chunks: list[Aep.Chunk],
    start_type: str,
    end_type: str,
) -> list[list[Aep.Chunk]]:
    """Split *chunks* into groups bounded by *start_type* … *end_type* (inclusive).

    Chunks that fall outside any group are ignored.

    Args:
        chunks: Flat list of chunks to scan.
        start_type: Chunk type that begins a new group.
        end_type: Chunk type that closes the current group.
    """
    groups: list[list[Aep.Chunk]] = []
    current: list[Aep.Chunk] | None = None
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
    chunks: list[Aep.Chunk],
    chunk_type: str,
) -> list[list[Aep.Chunk]]:
    """Split *chunks* into groups starting at each occurrence of *chunk_type*.

    Every time a chunk with *chunk_type* is encountered a new group begins.
    Chunks that appear before the first occurrence are discarded.

    Args:
        chunks: Flat list of chunks to scan.
        chunk_type: Chunk type that starts a new group.
    """
    groups: list[list[Aep.Chunk]] = []
    current: list[Aep.Chunk] | None = None
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


def str_contents(chunk: Aep.Chunk) -> str:
    """Return the string contents of a chunk whose chunk_type is Utf8."""
    text: str = chunk.body.contents
    return text.split("\x00")[0]


#: Sentinel value indicating an undefined frame number in the binary format.
UNDEFINED_FRAME = 0xFFFFFFFF


def parse_alas_data(parent_chunks: list[Aep.Chunk]) -> dict[str, Any]:
    """Parse path information from an Als2/alas chunk structure.

    The Als2 LIST chunk contains an alas chunk with JSON data including:
    - fullpath: The folder or file path
    - target_is_folder: Whether fullpath is a folder (`True`) or file (`False`)

    Args:
        parent_chunks: List of chunks that may contain an Als2 LIST chunk.

    Returns:
        Dictionary with alas data (fullpath, target_is_folder, etc.),
        or empty dict if not found or invalid.
    """
    try:
        als2_chunk = find_by_list_type(chunks=parent_chunks, list_type="Als2")
    except ChunkNotFoundError:
        return {}
    try:
        alas_chunk = find_by_type(chunks=als2_chunk.body.chunks, chunk_type="alas")
    except ChunkNotFoundError:
        return {}
    alas_text = str_contents(alas_chunk)
    if not alas_text:
        return {}
    result = json.loads(alas_text)
    return result if isinstance(result, dict) else {}


def chunk_tree(
    chunks: list[Aep.Chunk],
    depth: int = -1,
    indent: int = 0,
) -> str:
    """Return a text tree representation of chunks for debugging.

    Args:
        chunks: List of chunks to visualize.
        depth: Max depth to recurse (-1 for unlimited).
        indent: Current indentation level (used internally).

    Example::

        >>> print(chunk_tree(root.chunks, depth=2))
        LIST:Fold (12345 B)
          tdsn (4 B)
          Utf8 (12 B)
          LIST:Layr (8000 B)
            ...
    """
    lines: list[str] = []
    prefix = "  " * indent
    for chunk in chunks:
        if chunk.chunk_type == "LIST":
            label = f"LIST:{chunk.body.list_type}"
            lines.append(f"{prefix}{label} ({chunk.len_body} B)")
            if depth != 0 and hasattr(chunk.body, "chunks"):
                lines.append(chunk_tree(chunk.body.chunks, depth - 1, indent + 1))
        else:
            lines.append(f"{prefix}{chunk.chunk_type} ({chunk.len_body} B)")
    return "\n".join(lines)


def recursive_find(
    chunks: list[Aep.Chunk],
    chunk_type: str | None = None,
    list_type: str | None = None,
) -> list[Aep.Chunk]:
    """Recursively search the chunk tree for matching chunks.

    At least one of *chunk_type* or *list_type* must be given.

    Args:
        chunks: List of chunks to search.
        chunk_type: Match chunks with this chunk_type (e.g. `"cdta"`).
        list_type: Match LIST chunks with this list_type (e.g. `"Layr"`).
            When provided, only LIST chunks are matched.

    Returns:
        All matching chunks across the entire tree, in DFS order.
    """
    if chunk_type is None and list_type is None:
        raise ValueError("At least one of chunk_type or list_type is required")
    results: list[Aep.Chunk] = []
    for chunk in chunks:
        if list_type is not None:
            if chunk.chunk_type == "LIST" and chunk.body.list_type == list_type:
                results.append(chunk)
        elif chunk.chunk_type == chunk_type:
            results.append(chunk)
        # Recurse into LIST children
        if chunk.chunk_type == "LIST" and hasattr(chunk.body, "chunks"):
            results.extend(recursive_find(chunk.body.chunks, chunk_type, list_type))
    return results


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

# 4-byte chunk_type + 4-byte len_body.
CHUNK_HEADER_SIZE = 8

# Extra bytes added to the current len_body when allocating a write buffer,
# so that a body whose size grows slightly still fits without reallocation.
WRITE_BUFFER_HEADROOM = 8096


def toggle_flag_chunk(
    container: ReadWriteKaitaiStruct,
    chunk_type: str,
    body_cls_name: str,
    enable: bool,
) -> None:
    """Add or remove a flag chunk from a Chunks container."""
    chunks = container.chunks
    existing = [i for i, c in enumerate(chunks) if c.chunk_type == chunk_type]

    if enable and not existing:
        create_chunk(container, chunk_type, body_cls_name, _unnamed0=b"\x01")
    elif not enable and existing:
        delta = 0
        for i in reversed(existing):
            c = chunks.pop(i)
            delta -= CHUNK_HEADER_SIZE + c.len_body + len(c.pad_byte)
        _update_len_chain(container._parent, delta)


def create_chunk(
    container: ReadWriteKaitaiStruct,
    chunk_type: str,
    body_cls_name: str,
    *body_args: Any,
    index: int | None = None,
    **body_attrs: Any,
) -> Aep.Chunk:
    """Create a new Kaitai Chunk, insert it into *container* and propagate.

    Args:
        container: The Chunks container that will hold this chunk.
        chunk_type: 4-character chunk type identifier (e.g. `"lnrb"`).
        body_cls_name: Name of the Kaitai body class (e.g. `"Utf8Body"`).
        *body_args: Positional arguments for parameterized body classes
            (e.g. `is_le` for `CdatBody`).
        index: Position in `container.chunks` to insert at. `None`
            (default) appends to the end.
        **body_attrs: Attributes to set on the newly created body.
    """
    root = container._root
    body = getattr(Aep, body_cls_name)(*body_args)
    for attr, value in body_attrs.items():
        setattr(body, attr, value)

    chunk = Aep.Chunk(_parent=container, _root=root)
    chunk.chunk_type = chunk_type
    chunk.len_body = 0
    chunk._raw_body = b""
    chunk.pad_byte = b""
    chunk.body = body

    body._parent = chunk
    body._root = root

    if index is None:
        container.chunks.append(chunk)
    else:
        container.chunks.insert(index, chunk)

    if isinstance(body, Aep.CdatBody):
        # CdatBody._check() validates array length against
        # _parent.len_body, so we handle size propagation directly
        # instead of going through propagate_check (which would call
        # _check() while len_body is still 0).
        vals = body.value_be or body.value_le or []
        chunk.len_body = len(vals) * 8
        body._check()
        pad = chunk.len_body % 2
        chunk.pad_byte = b"\x00" if pad else b""
        chunk._check()
        _update_len_chain(container._parent, CHUNK_HEADER_SIZE + chunk.len_body + pad)
    else:
        propagate_check(body)
        _update_len_chain(container._parent, CHUNK_HEADER_SIZE)
    return chunk


def create_tdsb_chunk(
    container: ReadWriteKaitaiStruct,
    proxy_tdsb: Any,
) -> Aep.Chunk:
    """Create a tdsb chunk, copying flags from a proxy if available.

    Used during materialization of synthesized properties and groups.
    """
    return create_chunk(
        container,
        "tdsb",
        "TdsbBody",
        roto_bezier=getattr(proxy_tdsb, "roto_bezier", 0),
        _unnamed1=b"\x00",
        _unnamed2=0,
        locked_ratio=getattr(proxy_tdsb, "locked_ratio", 0),
        _unnamed4=0,
        _unnamed5=0,
        dimensions_separated=getattr(proxy_tdsb, "dimensions_separated", 0),
        enabled=getattr(proxy_tdsb, "enabled", 1),
    )


def propagate_check(body: ReadWriteKaitaiStruct) -> None:
    """Call `_check()` bottom-up from *body* to root, updating `len_body`.

    1. `body._check()` clears the body's `_dirty` flag.
    2. The owning `Chunk` is located (skipping intermediate parents).
    3. For variable-size bodies the new size is measured; for fixed-size
       bodies the existing `len_body` is kept.
    4. `_update_len_chain` propagates any delta from the chunk upward,
       fixing pad_byte and `len_body` on every ancestor.
    """
    body._check()

    # Walk up to the nearest Chunk that owns len_body.
    chunk = body._parent
    if chunk is None:
        return
    while not hasattr(chunk, "len_body"):
        chunk = chunk._parent

    if hasattr(body, "_recompute_size"):
        new_size = body._recompute_size()
    elif chunk.len_body == 0:
        # Newly created chunk -- must serialize to measure.
        if hasattr(body, "chunks") and not body.chunks:
            # Empty container.  ListBody still has its 4-byte list_type.
            new_size = 4 if isinstance(body, Aep.ListBody) else 0
        else:
            saved_io = body._io
            buf = BytesIO(bytearray(WRITE_BUFFER_HEADROOM))
            body._write__seq(KaitaiStream(buf))
            new_size = buf.tell()
            body._io = saved_io
    else:
        # Fixed-size body -- size unchanged.
        new_size = chunk.len_body

    _update_len_chain(chunk, new_size - chunk.len_body)


def _update_len_chain(start: Any, delta: int) -> None:
    """Walk up from *start*, adding *delta* to each `len_body`.

    At each `Aep.Chunk`, pad_byte is resynchronised and any padding-size
    change is folded into *delta* so that ancestors see the correct total.
    Stops early when *delta* reaches 0.
    """
    obj: Any = start
    while obj is not None:
        if hasattr(obj, "len_body"):
            obj.len_body += delta
            if isinstance(obj, Aep.Chunk):
                old_pad = len(getattr(obj, "pad_byte", b""))
                new_pad: int = obj.len_body % 2
                obj.pad_byte = b"\x00" if new_pad else b""
                delta += new_pad - old_pad
            obj._check()
            if not delta:
                break
        obj = getattr(obj, "_parent", None)
