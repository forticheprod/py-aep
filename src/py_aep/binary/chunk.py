"""AEP chunk hierarchy, recursive I/O, context resolvers, and file I/O.

Everything lives in one file to avoid import cycles between ListChunk and
the recursive reader/writer.
"""

from __future__ import annotations

import struct
from io import BytesIO
from typing import TYPE_CHECKING, cast

from attrs import Factory, define, field

from .bin_utils import (
    _HEADER_STRUCT,
    read_bytes,
    read_fmt,
    read_pad,
    write_bytes,
    write_fmt,
    write_pad,
)
from .fmt_field import FmtItem, _decode_fields, _encode_value, _struct_info
from .registry import CHUNK_TYPES, register

if TYPE_CHECKING:
    from typing import IO, Any, Callable, Iterator

# ---------------------------------------------------------------------------
# Chunk base (also serves as fallback for unregistered types)
# ---------------------------------------------------------------------------


@define
class Chunk:
    """Concrete base for all AEP chunks.

    Stores unparsed body bytes in `data`. Typed subclasses override
    `read()` / `write()` to interpret the body.
    """

    chunk_type: str = ""
    data: bytes = b""
    synthetic: bool = field(default=False, repr=False)
    _trailing: bytes = field(default=b"", repr=False, eq=False, init=False)

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        *,
        chunk_type: str = "",
        **kwargs: Any,
    ) -> Chunk:
        # Get fields
        info = _struct_info(cls)
        if info is None:
            data = read_bytes(fp, size)
            return cls(chunk_type=chunk_type, data=data)
        (
            fmt,
            data_fields,
            encodings,
            optional_start,
            endians,
            items_info,
            coerces,
            init_names,
            simple,
            expected,
        ) = info
        mixed_endian = bool(endians)

        if simple and size >= expected:
            # Fast path: no string encodings, endian overrides, optional
            # fields, or items. dict(zip()) replaces the _decode_fields
            # Python loop. Coerces (e.g. bool_field) are handled inline.
            kw: dict[str, Any] = dict(zip(init_names, read_fmt(fmt, fp)))
            kw["chunk_type"] = chunk_type
            for i, crc in coerces.items():
                name = init_names[i]
                kw[name] = crc(kw[name])
            trailing_size = size - expected
            if trailing_size > 0:
                extra = read_bytes(fp, trailing_size)
                instance = cls(**kw)
                object.__setattr__(instance, "_trailing", extra)
                return instance
            return cls(**kw)

        if mixed_endian:
            # Per-field read: each field may have its own endian prefix
            values: list[Any] = []
            remaining_me = size
            for i, f in enumerate(data_fields):
                fe = endians.get(i, ">")
                ff = f.metadata["fmt"]
                f_size = struct.calcsize(fe + ff)
                if remaining_me >= f_size:
                    (v,) = struct.unpack(fe + ff, fp.read(f_size))
                    values.append(v)
                    remaining_me -= f_size
                elif i < optional_start:
                    raise OSError(
                        f"{chunk_type} body too short: expected >= "
                        f"{size - remaining_me + f_size} bytes, got {size}"
                    )
                else:
                    break
            while len(values) < len(data_fields):
                values.append(None)
            items_start = size - remaining_me
        elif size >= expected:
            # Fast path: all bytes present (common case)
            values = list(read_fmt(fmt, fp)) if fmt else []
            items_start = expected
        else:
            # Build required-only format
            req_parts = [f.metadata["fmt"] for f in data_fields[:optional_start]]
            req_fmt = "".join(req_parts)
            req_size = struct.calcsize(">" + req_fmt) if req_parts else 0
            if size < req_size:
                raise OSError(
                    f"{chunk_type} body too short: expected >= {req_size} "
                    f"bytes, got {size}"
                )
            values = list(read_fmt(req_fmt, fp)) if req_parts else []
            remaining = size - req_size
            for f in data_fields[optional_start:]:
                f_size = struct.calcsize(">" + f.metadata["fmt"])
                if remaining >= f_size:
                    values.extend(read_fmt(f.metadata["fmt"], fp))
                    remaining -= f_size
                else:
                    break
            # Remaining optional fields get None (absent)
            while len(values) < len(data_fields):
                values.append(None)
            items_start = size - remaining

        kw2: dict[str, Any] = {"chunk_type": chunk_type}
        kw2.update(_decode_fields(data_fields, values, encodings, coerces, init_names))
        extra_trailing: bytes | None = None
        if items_info is not None:
            items_name, item_cls, item_size = items_info
            items_bytes = size - items_start
            count = items_bytes // item_size
            fmt_cls = cast("type[FmtItem]", item_cls)
            kw2[items_name] = [
                fmt_cls.frombytes(fp.read(item_size)) for _ in range(count)
            ]
            rest = items_bytes - count * item_size
            if rest > 0:
                extra_trailing = read_bytes(fp, rest)
        elif size > items_start:
            extra_trailing = read_bytes(fp, size - items_start)
        instance = cls(**kw2)
        if extra_trailing is not None:
            object.__setattr__(instance, "_trailing", extra_trailing)
        return instance

    def write(self, fp: IO[bytes]) -> int:
        info = _struct_info(type(self))
        if info is None:
            return write_bytes(fp, self.data)
        (
            fmt,
            data_fields,
            encodings,
            optional_start,
            endians,
            items_info,
            coerces,
            _init_names,
            _simple,
            _expected,
        ) = info
        mixed_endian = bool(endians)

        # Find last non-None optional field to determine write boundary
        last_idx = len(data_fields)
        if optional_start < len(data_fields):
            last_idx = optional_start
            for i in range(len(data_fields) - 1, optional_start - 1, -1):
                if getattr(self, data_fields[i].name) is not None:
                    last_idx = i + 1
                    break

        written: int
        if mixed_endian:
            # Per-field write: each field may have its own endian prefix
            written = 0
            for i in range(last_idx):
                f = data_fields[i]
                fe = endians.get(i, ">")
                value = getattr(self, f.name)
                value = _encode_value(
                    value, i, encodings, coerces, fe, f.metadata["fmt"]
                )
                written += write_bytes(fp, struct.pack(fe + f.metadata["fmt"], value))
        else:
            # Build format for fields we're writing
            write_parts = [data_fields[i].metadata["fmt"] for i in range(last_idx)]
            w_fmt = "".join(write_parts)

            write_values: list[Any] = []
            for i in range(last_idx):
                f = data_fields[i]
                value = getattr(self, f.name)
                value = _encode_value(
                    value, i, encodings, coerces, ">", f.metadata["fmt"]
                )
                write_values.append(value)
            written = write_fmt(fp, w_fmt, *write_values) if write_parts else 0

        if items_info is not None:
            items_name = items_info[0]
            for item in getattr(self, items_name):
                written += write_bytes(fp, item.tobytes())
        if self._trailing:
            written += write_bytes(fp, self._trailing)
        return written

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


@register("LIST", "RIFX")
@define
class ListChunk(Chunk):
    """LIST or RIFX container chunk.

    Children are stored in `chunks`. The `list_type` is the 4-byte subtype
    (e.g. "Fold", "Layr", "Egg!"). For btdk lists, raw binary data is stored
    in inherited `data` instead of parsed children.

    RIFX is structurally identical to LIST - same binary format (4-byte
    list_type + child chunks). The only difference is chunk_type="RIFX".
    """

    list_type: str = ""
    chunks: list[Chunk] = Factory(list)
    chunk_type: str = "LIST"

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        *,
        chunk_type: str = "LIST",
        ctx: ReadContext | None = None,
        defer_list_types: frozenset[str] | None = None,
        **kwargs: Any,
    ) -> ListChunk:
        if size < 4:
            raise OSError(f"{chunk_type} body too small: {size}")
        if ctx is None:
            ctx = EMPTY_CTX
        list_type = read_fmt("4s", fp)[0].decode("ASCII")
        if list_type == "btdk":
            data = read_bytes(fp, size - 4)
            return cls(
                list_type=list_type,
                data=data,
                chunk_type=chunk_type,
            )
        parent_result = kwargs.get("parent_result")
        child_ctx = ReadContext(
            parent_list_type=list_type,
            grandparent_list_type=ctx.parent_list_type,
            parent_siblings=parent_result,
        )
        if defer_list_types and list_type in defer_list_types:
            raw_body = fp.read(size - 4)
            return DeferredListChunk(
                chunk_type=chunk_type,
                list_type=list_type,
                raw_body=raw_body,
                raw_ctx=child_ctx,
            )
        chunks = read_chunks(
            fp,
            size - 4,
            ctx=child_ctx,
            defer_list_types=defer_list_types,
        )
        return cls(
            list_type=list_type,
            chunks=chunks,
            chunk_type=chunk_type,
        )

    def __iter__(self) -> Iterator[Chunk]:
        return iter(self.chunks)

    def __len__(self) -> int:
        return len(self.chunks)

    def write(self, fp: IO[bytes]) -> int:
        written = write_bytes(fp, self.list_type.encode("ASCII"))
        if self.list_type == "btdk":
            written += write_bytes(fp, self.data)
        else:
            for chunk in self.chunks:
                if chunk.synthetic:
                    continue
                written += write_chunk(fp, chunk)
        return written


class DeferredListChunk(ListChunk):
    """A LIST chunk whose children are parsed lazily from stored raw bytes.

    Inherits from `ListChunk` so all isinstance checks pass. The `chunks`
    property triggers parsing on first access. If the chunks are never
    accessed, `write()` writes the raw bytes directly (no parse needed).
    """

    __slots__ = ("_raw_body", "_raw_ctx", "_parsed_chunks")

    _raw_body: bytes
    _raw_ctx: ReadContext | None
    _parsed_chunks: list[Chunk] | None

    def __init__(
        self,
        *,
        chunk_type: str = "LIST",
        list_type: str = "",
        raw_body: bytes = b"",
        raw_ctx: ReadContext | None = None,
    ) -> None:
        object.__setattr__(self, "chunk_type", chunk_type)
        object.__setattr__(self, "list_type", list_type)
        object.__setattr__(self, "data", b"")
        object.__setattr__(self, "synthetic", False)
        object.__setattr__(self, "_raw_body", raw_body)
        object.__setattr__(self, "_raw_ctx", raw_ctx)
        object.__setattr__(self, "_parsed_chunks", None)

    @property  # type: ignore[override]
    def chunks(self) -> list[Chunk]:
        parsed = self._parsed_chunks
        if parsed is None:
            body = self._raw_body
            ctx = self._raw_ctx or EMPTY_CTX
            parsed = read_chunks(BytesIO(body), len(body), ctx=ctx)
            object.__setattr__(self, "_parsed_chunks", parsed)
            object.__setattr__(self, "_raw_body", b"")
            object.__setattr__(self, "_raw_ctx", None)
        return parsed

    @chunks.setter
    def chunks(self, value: list[Chunk]) -> None:
        object.__setattr__(self, "_parsed_chunks", value)
        object.__setattr__(self, "_raw_body", b"")

    def write(self, fp: IO[bytes]) -> int:
        written = write_bytes(fp, self.list_type.encode("ASCII"))
        if self._parsed_chunks is None:
            # Never accessed - write raw bytes directly (fast path).
            written += write_bytes(fp, self._raw_body)
        else:
            for chunk in self._parsed_chunks:
                if chunk.synthetic:
                    continue
                written += write_chunk(fp, chunk)
        return written


@register("fnam", "pdnm", "RCom")
@define
class ContainerChunk(Chunk):
    """Non-LIST chunk whose body contains child chunks without a list_type.

    Used for fnam, pdnm, RCom (and tdsn via the `TdsnChunk` subclass) -
    wrapper chunks that hold a single Utf8 child (or similar). Unlike
    ListChunk, there is no 4-byte list_type prefix in the binary data.
    """

    chunks: list[Chunk] = Factory(list)

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        *,
        chunk_type: str = "",
        ctx: ReadContext | None = None,
        **kwargs: Any,
    ) -> ContainerChunk:
        if ctx is None:
            ctx = EMPTY_CTX
        defer = kwargs.get("defer_list_types")
        # Pass-through context (no list_type level change)
        chunks = read_chunks(fp, size, ctx=ctx, defer_list_types=defer)
        return cls(chunk_type=chunk_type, chunks=chunks)

    def __iter__(self) -> Iterator[Chunk]:
        return iter(self.chunks)

    def __len__(self) -> int:
        return len(self.chunks)

    def write(self, fp: IO[bytes]) -> int:
        written = 0
        for chunk in self.chunks:
            if chunk.synthetic:
                continue
            written += write_chunk(fp, chunk)
        return written


# ---------------------------------------------------------------------------
# Read context
# ---------------------------------------------------------------------------


class ReadContext:
    """Ancestor context passed through recursive chunk reading."""

    __slots__ = ("parent_list_type", "grandparent_list_type", "parent_siblings")

    def __init__(
        self,
        parent_list_type: str = "",
        grandparent_list_type: str = "",
        parent_siblings: list[Chunk] | None = None,
    ) -> None:
        self.parent_list_type = parent_list_type
        self.grandparent_list_type = grandparent_list_type
        self.parent_siblings = parent_siblings


EMPTY_CTX = ReadContext()


# ---------------------------------------------------------------------------
# Context resolvers
# ---------------------------------------------------------------------------


def _resolve_cdat_context(
    siblings: list[Chunk],
    ctx: ReadContext,
) -> dict[str, bool]:
    return {"is_le": ctx.grandparent_list_type == "otst"}


def _resolve_ldat_context(
    siblings: list[Chunk],
    ctx: ReadContext,
) -> dict[str, int | bool]:
    # Deferred import: ldat_chunks subclasses Chunk, so a top-level import
    # would be circular.
    from .ldat_chunks import Lhd3Chunk

    if not siblings:
        return {}
    lhd3 = siblings[0]
    if not isinstance(lhd3, Lhd3Chunk):
        return {}
    result: dict[str, int | bool] = {
        "item_type": lhd3.item_type,
        "item_size": lhd3.item_size,
        "count": lhd3.count,
    }
    # Check spatial flag for potential three_d -> three_d_spatial promotion
    if (
        ctx.grandparent_list_type == "tdbs"
        and ctx.parent_siblings is not None
        and len(ctx.parent_siblings) > 2
    ):
        tdb4_sibling = ctx.parent_siblings[2]
        if hasattr(tdb4_sibling, "is_spatial"):
            result["is_spatial"] = tdb4_sibling.is_spatial
    return result


def _resolve_tdum_context(
    siblings: list[Chunk],
    ctx: ReadContext,
) -> dict[str, bool]:
    if len(siblings) > 2:
        tdb4 = siblings[2]
        if hasattr(tdb4, "color") and hasattr(tdb4, "integer"):
            return {"is_color": tdb4.color, "is_integer": tdb4.integer}
    return {}


def _resolve_prda_context(
    siblings: list[Chunk],
    ctx: ReadContext,
) -> dict[str, str]:
    # Deferred import: misc_chunks subclasses Chunk, so a top-level import
    # would be circular.
    from .misc_chunks import PrinChunk

    for sibling in siblings:
        if isinstance(sibling, PrinChunk):
            return {"renderer_match_name": sibling.match_name}
    return {}


_CONTEXT_RESOLVERS: dict[str, Callable[..., dict[str, Any]]] = {
    "cdat": _resolve_cdat_context,
    "ldat": _resolve_ldat_context,
    "prda": _resolve_prda_context,
    "tdum": _resolve_tdum_context,
    "tduM": _resolve_tdum_context,
}


def _resolve_context(
    chunk_type: str,
    siblings: list[Chunk],
    ctx: ReadContext,
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
        raise OSError(f"Short read on chunk header: expected 8 bytes, got {len(data)}")
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
    ctx: ReadContext = EMPTY_CTX,
    defer_list_types: frozenset[str] | None = None,
) -> list[Chunk]:
    """Read child chunks until `size` bytes are consumed."""
    end = fp.tell() + size
    result: list[Chunk] = []
    pos = end - size
    while pos < end:
        chunk_type, len_body = read_header(fp)
        cls = CHUNK_TYPES.get(chunk_type, Chunk)

        resolver = _CONTEXT_RESOLVERS.get(chunk_type)
        ctx_kw = resolver(result, ctx) if resolver else {}
        chunk = cls.read(
            fp,
            len_body,
            chunk_type=chunk_type,
            ctx=ctx,
            parent_result=result,
            defer_list_types=defer_list_types,
            **ctx_kw,
        )
        result.append(chunk)

        # Consume pad byte if len_body is odd
        read_pad(fp, len_body)
        pos += 8 + len_body + (len_body & 1)

    if pos != end:
        raise OSError(f"Chunk reader drifted: expected offset {end}, got {pos}")

    return result


# ---------------------------------------------------------------------------
# AEP file I/O
# ---------------------------------------------------------------------------


def read_aep(
    fp: IO[bytes],
    *,
    defer_list_types: frozenset[str] | None = None,
) -> tuple[ListChunk, str]:
    """Read an AEP file: RIFX root chunk + trailing XMP packet."""
    raw_type = read_bytes(fp, 4)
    chunk_type = raw_type.decode("ASCII")
    if chunk_type != "RIFX":
        raise ValueError(f"Expected RIFX, got {chunk_type!r}")
    (len_body,) = read_fmt("I", fp)
    rifx = ListChunk.read(
        fp,
        len_body,
        chunk_type="RIFX",
        defer_list_types=defer_list_types,
    )
    xmp = fp.read().decode("UTF-8")
    return rifx, xmp


def write_aep(fp: IO[bytes], rifx: ListChunk, xmp: str) -> int:
    """Write an AEP file: RIFX root chunk + trailing XMP packet."""
    written = write_chunk(fp, rifx)
    xmp_bytes = xmp.encode("UTF-8")
    written += write_bytes(fp, xmp_bytes)
    return written


# ---------------------------------------------------------------------------
# Trigger registration of typed chunk classes
# ---------------------------------------------------------------------------
import py_aep.binary.composition_chunks  # noqa: F401, E402
import py_aep.binary.footage_chunks  # noqa: F401, E402
import py_aep.binary.item_chunks  # noqa: F401, E402
import py_aep.binary.layer_chunks  # noqa: F401, E402
import py_aep.binary.ldat_chunks  # noqa: F401, E402
import py_aep.binary.misc_chunks  # noqa: F401, E402
import py_aep.binary.project_chunks  # noqa: F401, E402
import py_aep.binary.property_chunks  # noqa: F401, E402
import py_aep.binary.render_chunks  # noqa: F401, E402
import py_aep.binary.scalar_chunks  # noqa: F401, E402
