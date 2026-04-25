"""AEP chunk hierarchy, recursive I/O, context resolvers, and file I/O.

Everything lives in one file to avoid import cycles between ListChunk and
the recursive reader/writer.
"""
from __future__ import annotations

import struct
from io import BytesIO
from typing import TYPE_CHECKING

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
from .fmt_field import _init_name, _struct_info
from .registry import CHUNK_TYPES, register

if TYPE_CHECKING:
    from typing import IO, Any, Callable

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
        info = _struct_info(cls)  # type: ignore[arg-type]
        if info is None:
            data = read_bytes(fp, size)
            return cls(chunk_type=chunk_type, data=data)
        fmt, data_fields, trailing_field, encodings, optional_start, endians, items_info = info
        mixed_endian = bool(endians)
        expected = struct.calcsize(">" + fmt) if fmt else 0

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
            items_start = size  # no trailing/items in the optional-fields slow path

        kw: dict[str, Any] = {"chunk_type": chunk_type}
        for i, (fld, value) in enumerate(zip(data_fields, values)):
            enc = encodings.get(i)
            if enc is not None and value is not None:
                nul = value.find(b"\x00")
                value = value[:nul].decode(enc) if nul >= 0 else value.decode(enc)
            kw[_init_name(fld.name)] = value
        if items_info is not None:
            items_name, item_cls, item_size = items_info
            items_bytes = size - items_start
            count = items_bytes // item_size
            kw[items_name] = [
                item_cls.frombytes(fp.read(item_size))
                for _ in range(count)
            ]
            rest = items_bytes - count * item_size
            if trailing_field and rest > 0:
                kw[_init_name(trailing_field.name)] = read_bytes(fp, rest)
        elif trailing_field and size > items_start:
            kw[_init_name(trailing_field.name)] = read_bytes(
                fp, size - items_start
            )
        return cls(**kw)

    def write(self, fp: IO[bytes]) -> int:
        info = _struct_info(type(self))  # type: ignore[arg-type]
        if info is None:
            return write_bytes(fp, self.data)
        fmt, data_fields, trailing_field, encodings, optional_start, endians, items_info = info
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
                enc = encodings.get(i)
                if enc is not None:
                    field_size = struct.calcsize(fe + f.metadata["fmt"])
                    encoded = value.encode(enc)[:field_size]
                    value = encoded + b"\x00" * (field_size - len(encoded))
                written += write_bytes(fp, struct.pack(fe + f.metadata["fmt"], value))
        else:
            # Build format for fields we're writing
            write_parts = [data_fields[i].metadata["fmt"] for i in range(last_idx)]
            w_fmt = "".join(write_parts)

            write_values: list[Any] = []
            for i in range(last_idx):
                f = data_fields[i]
                value = getattr(self, f.name)
                enc = encodings.get(i)
                if enc is not None:
                    # Encode str to null-padded bytes of the fixed field size.
                    field_size = struct.calcsize(">" + f.metadata["fmt"])
                    encoded = value.encode(enc)[:field_size]
                    value = encoded + b"\x00" * (field_size - len(encoded))
                write_values.append(value)
            written = write_fmt(fp, w_fmt, *write_values) if write_parts else 0

        if items_info is not None:
            items_name = items_info[0]
            for item in getattr(self, items_name):
                written += write_bytes(fp, item.tobytes())
        if trailing_field:
            t = getattr(self, trailing_field.name)
            if t:
                written += write_bytes(fp, t)
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
        ctx: _ReadContext | None = None,
        **kwargs: Any,
    ) -> ListChunk:
        if size < 4:
            raise OSError(f"{chunk_type} body too small: {size}")
        if ctx is None:
            ctx = _ReadContext()
        list_type = read_fmt("4s", fp)[0].decode("ASCII")
        if list_type == "btdk":
            data = read_bytes(fp, size - 4)
            return cls(
                list_type=list_type,
                data=data,
                chunk_type=chunk_type,
            )
        parent_result = kwargs.get("parent_result")
        child_ctx = _ReadContext(
            parent_list_type=list_type,
            grandparent_list_type=ctx.parent_list_type,
            parent_siblings=parent_result,
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
            written += write_bytes(fp, self.data)
        else:
            for chunk in self.chunks:
                written += write_chunk(fp, chunk)
        return written


@register("tdsn", "fnam", "pdnm", "RCom")
@define
class ContainerChunk(Chunk):
    """Non-LIST chunk whose body contains child chunks without a list_type.

    Used for tdsn, fnam, pdnm, RCom - wrapper chunks that hold a single
    Utf8 child (or similar). Unlike ListChunk, there is no 4-byte list_type
    prefix in the binary data.
    """

    chunks: list[Chunk] = Factory(list)

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        *,
        chunk_type: str = "",
        ctx: _ReadContext | None = None,
        **kwargs: Any,
    ) -> ContainerChunk:
        if ctx is None:
            ctx = _ReadContext()
        # Pass-through context (no list_type level change)
        chunks = read_chunks(fp, size, ctx=ctx)
        return cls(chunk_type=chunk_type, chunks=chunks)

    def write(self, fp: IO[bytes]) -> int:
        written = 0
        for chunk in self.chunks:
            written += write_chunk(fp, chunk)
        return written


# ---------------------------------------------------------------------------
# Read context
# ---------------------------------------------------------------------------


@define
class _ReadContext:
    """Ancestor context passed through recursive chunk reading."""

    parent_list_type: str = ""
    grandparent_list_type: str = ""
    parent_siblings: list[Chunk] | None = field(default=None, repr=False)


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
    if not siblings:
        return {}
    lhd3 = siblings[0]
    try:
        result: dict[str, Any] = {
            "item_type": lhd3.item_type,
            "item_size": lhd3.item_size,
            "count": lhd3.count,
        }
    except AttributeError:
        return {}
    # Check spatial flag for potential three_d -> three_d_spatial promotion
    if (
        ctx.grandparent_list_type == "tdbs"
        and ctx.parent_siblings is not None
        and len(ctx.parent_siblings) > 2
    ):
        try:
            result["is_spatial"] = ctx.parent_siblings[2].is_spatial
        except AttributeError:
            pass
    return result


def _resolve_tdum_context(
    siblings: list[Chunk],
    ctx: _ReadContext,
) -> dict[str, Any]:
    if len(siblings) > 2:
        tdb4 = siblings[2]
        try:
            return {"is_color": tdb4.color, "is_integer": tdb4.integer}
        except AttributeError:
            pass
    return {}


_CONTEXT_RESOLVERS: dict[str, Callable[..., dict[str, Any]]] = {
    "cdat": _resolve_cdat_context,
    "ldat": _resolve_ldat_context,
    "tdum": _resolve_tdum_context,
    "tduM": _resolve_tdum_context,
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
        cls = CHUNK_TYPES.get(chunk_type, Chunk)
        kwargs = _resolve_context(chunk_type, result, ctx)
        chunk = cls.read(
            fp, len_body, chunk_type=chunk_type, ctx=ctx,
            parent_result=result, **kwargs,
        )
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


# ---------------------------------------------------------------------------
# Trigger registration of typed chunk classes
# ---------------------------------------------------------------------------
import py_aep.binary.composition_chunks  # noqa: F401, E402
import py_aep.binary.footage_chunks  # noqa: F401, E402
import py_aep.binary.item_chunks  # noqa: F401, E402
import py_aep.binary.layer_chunks  # noqa: F401, E402
import py_aep.binary.ldat_chunks  # noqa: F401, E402
import py_aep.binary.misc_chunks  # noqa: F401, E402
import py_aep.binary.property_chunks  # noqa: F401, E402
import py_aep.binary.render_chunks  # noqa: F401, E402
import py_aep.binary.scalar_chunks  # noqa: F401, E402
