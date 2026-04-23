"""AEP chunk hierarchy, recursive I/O, context resolvers, and file I/O.

Everything lives in one file to avoid import cycles between ListChunk and
the recursive reader/writer.
"""
from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from attrs import Factory, define

if TYPE_CHECKING:
    import os
    from typing import IO, Any, Callable

from py_aep.kaitai.bin_utils import (
    _HEADER_STRUCT,
    read_bytes,
    read_fmt,
    read_pad,
    write_bytes,
    write_fmt,
    write_pad,
)
from py_aep.kaitai.registry import CHUNK_TYPES

# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class Chunk:
    """Abstract base for all AEP chunks.

    Subclasses must implement `read()` and `write()`.
    """

    chunk_type: str

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        **kwargs: Any,
    ) -> Chunk:
        raise NotImplementedError

    def write(self, fp: IO[bytes]) -> int:
        raise NotImplementedError

    @classmethod
    def frombytes(cls, data: bytes | memoryview, **kwargs: Any) -> Chunk:
        """Parse a chunk body from raw bytes."""
        with BytesIO(data) as f:
            return cls.read(f, len(data), **kwargs)

    def tobytes(self) -> bytes:
        """Serialize the chunk body to bytes."""
        with BytesIO() as f:
            self.write(f)
            return f.getvalue()


# ---------------------------------------------------------------------------
# Concrete chunk classes
# ---------------------------------------------------------------------------


@define
class RawChunk(Chunk):
    """Chunk with unparsed body bytes.

    Handles all chunk types not registered with `@register`.
    """

    chunk_type: str = ""
    data: bytes = b""

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        *,
        chunk_type: str = "",
        **kwargs: Any,
    ) -> RawChunk:
        data = read_bytes(fp, size)
        return cls(chunk_type=chunk_type, data=data)

    def write(self, fp: IO[bytes]) -> int:
        return write_bytes(fp, self.data)


@define
class ListChunk(Chunk):
    """LIST or RIFX container chunk.

    Children are stored in `chunks`. The `list_type` is the 4-byte subtype
    (e.g. "Fold", "Layr", "Egg!"). For btdk lists, raw binary data is stored
    instead of parsed children.

    RIFX is structurally identical to LIST - same binary format (4-byte
    list_type + child chunks). The only difference is chunk_type="RIFX".
    """

    list_type: str = ""
    chunks: list[Chunk] = Factory(list)
    binary_data: bytes = b""
    chunk_type: str = "LIST"

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        *,
        chunk_type: str = "LIST",
        ctx: _ReadContext | None = None,
        **kwargs: Any,
    ) -> ListChunk:
        if size < 4:
            raise OSError(f"{chunk_type} body too small: {size}")
        if ctx is None:
            ctx = _ReadContext()
        list_type = read_fmt("4s", fp)[0].decode("ASCII")
        if list_type == "btdk":
            binary_data = read_bytes(fp, size - 4)
            return cls(
                list_type=list_type,
                binary_data=binary_data,
                chunk_type=chunk_type,
            )
        child_ctx = _ReadContext(
            parent_list_type=list_type,
            grandparent_list_type=ctx.parent_list_type,
        )
        chunks = read_chunks(fp, size - 4, ctx=child_ctx)
        return cls(
            list_type=list_type,
            chunks=chunks,
            chunk_type=chunk_type,
        )

    def write(self, fp: IO[bytes]) -> int:
        written = write_bytes(fp, self.list_type.encode("ASCII"))
        if self.list_type == "btdk":
            written += write_bytes(fp, self.binary_data)
        else:
            for chunk in self.chunks:
                written += write_chunk(fp, chunk)
        return written

    # -- Typed accessors (LIST:list) --

    @property
    def lhd3(self) -> Chunk | None:
        """chunks[0] when list_type == "list"."""
        if self.list_type != "list" or not self.chunks:
            return None
        return self.chunks[0]

    @property
    def ldat(self) -> Chunk | None:
        """chunks[1] when list_type == "list" and len(chunks) >= 2."""
        if self.list_type != "list" or len(self.chunks) < 2:
            return None
        return self.chunks[1]

    # -- Typed accessors (LIST:tdbs) --

    @property
    def tdsb(self) -> Chunk | None:
        """chunks[0] when list_type == "tdbs"."""
        if self.list_type != "tdbs" or not self.chunks:
            return None
        return self.chunks[0]

    @property
    def tdsn(self) -> Chunk | None:
        """chunks[1] when list_type == "tdbs"."""
        if self.list_type != "tdbs" or len(self.chunks) < 2:
            return None
        return self.chunks[1]

    @property
    def tdb4(self) -> Chunk | None:
        """chunks[2] when list_type == "tdbs"."""
        if self.list_type != "tdbs" or len(self.chunks) < 3:
            return None
        return self.chunks[2]


# ---------------------------------------------------------------------------
# Read context
# ---------------------------------------------------------------------------


@define
class _ReadContext:
    """Ancestor context passed through recursive chunk reading."""

    parent_list_type: str = ""
    grandparent_list_type: str = ""


# ---------------------------------------------------------------------------
# Context resolvers
# ---------------------------------------------------------------------------


def _resolve_cdat_context(
    siblings: list[Chunk],
    ctx: _ReadContext,
) -> dict[str, Any]:
    return {"is_le": ctx.grandparent_list_type == "otst"}


def _resolve_ldat_context(
    siblings: list[Chunk],
    ctx: _ReadContext,
) -> dict[str, Any]:
    # Phase 1: siblings[0] is RawChunk, can't extract typed fields.
    # Phase 2: will extract item_type, item_size, count from Lhd3Chunk.
    return {}


def _resolve_tdum_context(
    siblings: list[Chunk],
    ctx: _ReadContext,
) -> dict[str, Any]:
    # Phase 1: siblings[2] is RawChunk, can't extract typed fields.
    # Phase 2: will extract is_color, is_integer from Tdb4Chunk.
    return {}


def _resolve_otda_context(
    siblings: list[Chunk],
    ctx: _ReadContext,
) -> dict[str, Any]:
    return {"is_le": False}


_CONTEXT_RESOLVERS: dict[str, Callable[..., dict[str, Any]]] = {
    "cdat": _resolve_cdat_context,
    "ldat": _resolve_ldat_context,
    "tdum": _resolve_tdum_context,
    "tduM": _resolve_tdum_context,
    "otda": _resolve_otda_context,
}


def _resolve_context(
    chunk_type: str,
    siblings: list[Chunk],
    ctx: _ReadContext,
) -> dict[str, Any]:
    """Compute kwargs for parameterized chunk types."""
    resolver = _CONTEXT_RESOLVERS.get(chunk_type)
    if resolver is None:
        return {}
    return resolver(siblings, ctx)


# ---------------------------------------------------------------------------
# Chunk header I/O
# ---------------------------------------------------------------------------


def read_header(fp: IO[bytes]) -> tuple[str, int]:
    """Read the 8-byte chunk header: (chunk_type, len_body)."""
    data = fp.read(8)
    if len(data) < 8:
        raise OSError(
            f"Short read on chunk header: expected 8 bytes, got {len(data)}"
        )
    raw_type, len_body = _HEADER_STRUCT.unpack(data)
    chunk_type = raw_type.decode("ASCII")
    return chunk_type, len_body


def write_chunk(fp: IO[bytes], chunk: Chunk) -> int:
    """Write a complete chunk: header + body + pad byte.

    Backpatches len_body after the body is written.
    """
    written = write_bytes(fp, chunk.chunk_type.encode("ASCII"))
    len_pos = fp.tell()
    fp.seek(4, 1)  # skip 4 bytes for len_body placeholder
    written += 4

    body_size = chunk.write(fp)
    written += body_size

    # Backpatch len_body
    current = fp.tell()
    fp.seek(len_pos)
    write_fmt(fp, "I", body_size)
    fp.seek(current)

    # Pad to even boundary
    written += write_pad(fp, body_size)

    return written


# ---------------------------------------------------------------------------
# Recursive reader
# ---------------------------------------------------------------------------


def read_chunks(
    fp: IO[bytes],
    size: int,
    *,
    ctx: _ReadContext,
) -> list[Chunk]:
    """Read child chunks until `size` bytes are consumed."""
    end = fp.tell() + size
    result: list[Chunk] = []
    while fp.tell() < end:
        chunk_type, len_body = read_header(fp)

        if chunk_type in ("LIST", "RIFX"):
            chunk: Chunk = ListChunk.read(
                fp, len_body, chunk_type=chunk_type, ctx=ctx
            )
        elif len_body == 0:
            chunk = RawChunk(chunk_type=chunk_type, data=b"")
        else:
            cls = CHUNK_TYPES.get(chunk_type, RawChunk)
            kwargs = _resolve_context(chunk_type, result, ctx)
            chunk = cls.read(fp, len_body, chunk_type=chunk_type, **kwargs)
        result.append(chunk)

        # Consume pad byte if len_body is odd
        read_pad(fp, len_body)

    if fp.tell() != end:
        raise OSError(
            f"Chunk reader drifted: expected offset {end}, got {fp.tell()}"
        )

    return result


# ---------------------------------------------------------------------------
# AEP file I/O
# ---------------------------------------------------------------------------


def read_aep(fp: IO[bytes]) -> tuple[ListChunk, str]:
    """Read an AEP file: RIFX root chunk + trailing XMP packet."""
    raw_type = read_bytes(fp, 4)
    chunk_type = raw_type.decode("ASCII")
    if chunk_type != "RIFX":
        raise ValueError(f"Expected RIFX, got {chunk_type!r}")
    (len_body,) = read_fmt("I", fp)
    root_ctx = _ReadContext()
    rifx = ListChunk.read(fp, len_body, chunk_type="RIFX", ctx=root_ctx)
    xmp = fp.read().decode("UTF-8")
    return rifx, xmp


def write_aep(fp: IO[bytes], rifx: ListChunk, xmp: str) -> int:
    """Write an AEP file: RIFX root chunk + trailing XMP packet."""
    written = write_chunk(fp, rifx)
    xmp_bytes = xmp.encode("UTF-8")
    written += write_bytes(fp, xmp_bytes)
    return written


def read_aep_file(path: str | os.PathLike[str]) -> tuple[ListChunk, str]:
    """Open and parse an AEP file from disk."""
    with open(path, "rb") as fp:
        return read_aep(fp)


def write_aep_file(
    path: str | os.PathLike[str],
    rifx: ListChunk,
    xmp: str,
) -> int:
    """Write an AEP file to disk."""
    with open(path, "wb") as fp:
        return write_aep(fp, rifx, xmp)
