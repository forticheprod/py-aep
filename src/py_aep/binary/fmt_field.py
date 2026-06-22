"""Declarative field-format binding for chunk I/O.

Each field declares its struct format via `fmt_field("B")`.
`_struct_info()` introspects attrs metadata to derive the combined
format string and field list.  Generic `Chunk.read()` / `write()`
use this to handle all fixed-layout chunks with zero per-class I/O code.
"""

from __future__ import annotations

import struct
from functools import lru_cache
from typing import TYPE_CHECKING, cast

from attrs import Attribute, Factory, field, fields

if TYPE_CHECKING:
    from typing import Any, Callable

    _StructInfo = tuple[
        str,
        tuple[Attribute, ...],
        dict[int, str],
        int,
        dict[int, str],
        "tuple[str, type, int] | None",
        dict[int, type],
        tuple[str, ...],
        bool,
        int,
    ]

_UNSET = object()


def fmt_field(
    fmt: str,
    *,
    default: Any = _UNSET,
    repr: bool = True,
    encoding: str | None = None,
    optional: bool = False,
    endian: str | None = None,
    coerce: type | None = None,
) -> Any:
    """Declare an attrs field with its struct format in metadata.

    Args:
        fmt: struct format character(s) (e.g. `"B"`, `"48s"`).
        default: Default value for the field.  When omitted, bytes
            formats (`"Ns"`) default to `b"\\x00" * N` and all
            other formats default to `0`.
        repr: Whether to include this field in `repr()`.
        encoding: When set, the raw `bytes` from `struct.unpack`
            are decoded to `str` (stripping trailing NUL bytes),
            and on write the `str` is encoded back and NUL-padded
            to fill the fixed size.
        optional: When `True`, the field may be absent in older
            binary versions. Use `default=None` so that `None`
            means "not present" (preserves round-trip fidelity).
            Optional fields must come after all required fields.
        endian: Per-field byte-order override (e.g. `"<"` for
            little-endian). When `None` (default), the chunk-level
            big-endian default is used. Triggers per-field I/O in
            `Chunk.read()` / `Chunk.write()`.
        coerce: Type callable applied after unpacking (e.g. `bool`).
            On write, the inverse is applied (e.g. `int` for `bool`).
    """
    if default is _UNSET:
        if encoding is not None:
            default = ""
        elif fmt.endswith("s"):
            n = int(fmt[:-1]) if len(fmt) > 1 else 1
            default = b"\x00" * n
        else:
            # Coerce so constructed chunks hold the read-time type
            # (e.g. bool_field defaults to False, not 0).
            default = coerce(0) if coerce is not None else 0
    md: dict[str, Any] = {"fmt": fmt}
    if encoding is not None:
        md["encoding"] = encoding
    if optional:
        md["optional"] = True
    if endian == "<":
        md["endian"] = endian
    if coerce is not None:
        md["coerce"] = coerce
    return field(default=default, repr=repr, metadata=md)


def items_field(
    item_cls: type,
    item_size: int,
) -> Any:
    """Declare a list-of-items field that fills the remaining body bytes.

    The item count is inferred at read time: `count = remaining // item_size`.
    Item classes must use `fmt_field()` for their fields (with `endian`
    and `encoding` as needed) so that `_struct_info()` can auto-serialize
    them.

    Args:
        item_cls: Class used to deserialize each item.
        item_size: Fixed byte size of each serialized item.
    """
    md: dict[str, Any] = {
        "items": True,
        "item_cls": item_cls,
        "item_size": item_size,
    }
    return field(default=Factory(list), metadata=md)


# ---------------------------------------------------------------------------
# Semantic aliases for common struct formats
# ---------------------------------------------------------------------------


def u1_field(**kw: Any) -> Any:
    """Unsigned 1-byte integer field (`struct.unpack("B")`)."""
    return fmt_field("B", **kw)


def u2_field(**kw: Any) -> Any:
    """Unsigned 2-byte integer field (`struct.unpack("H")`)."""
    return fmt_field("H", **kw)


def u4_field(**kw: Any) -> Any:
    """Unsigned 4-byte integer field (`struct.unpack("I")`)."""
    return fmt_field("I", **kw)


def u8_field(**kw: Any) -> Any:
    """Unsigned 8-byte integer field (`struct.unpack("Q")`)."""
    return fmt_field("Q", **kw)


def s2_field(**kw: Any) -> Any:
    """Signed 2-byte integer field (`struct.unpack("h")`)."""
    return fmt_field("h", **kw)


def s4_field(**kw: Any) -> Any:
    """Signed 4-byte integer field (`struct.unpack("i")`)."""
    return fmt_field("i", **kw)


def f4_field(**kw: Any) -> Any:
    """4-byte IEEE 754 float field (`struct.unpack("f")`)."""
    return fmt_field("f", **kw)


def f8_field(**kw: Any) -> Any:
    """8-byte IEEE 754 double field (`struct.unpack("d")`)."""
    return fmt_field("d", **kw)


def bytes_field(n: int, **kw: Any) -> Any:
    """Fixed-size raw bytes field (`struct.unpack("Ns")`)."""
    return fmt_field(f"{n}s", **kw)


def str_field(n: int, *, encoding: str = "utf-8", **kw: Any) -> Any:
    """Fixed-size string field, decoded via `encoding`."""
    return fmt_field(f"{n}s", encoding=encoding, **kw)


def ascii_field(n: int, **kw: Any) -> Any:
    """Fixed-size ASCII string field."""
    return fmt_field(f"{n}s", encoding="ascii", **kw)


def bool_field(**kw: Any) -> Any:
    """1-byte boolean field (`struct.unpack("B")`, coerced to `bool`)."""
    return fmt_field("B", coerce=bool, **kw)


def _struct_info_uncached(cls: type) -> _StructInfo | None:
    """Derive struct layout metadata for a chunk class.

    Returns a 10-tuple `(fmt, data_fields, encodings,
    optional_start, endians, items_info, coerces, init_names, simple,
    expected_size)` or `None` for raw-bytes chunks that have neither
    `fmt_field` nor `items_field` fields.

    - `encodings`: field-index -> encoding name.
    - `optional_start`: index of first optional field.
    - `endians`: field-index -> endian override (`"<"` or `">"`);
      non-empty triggers per-field I/O in `Chunk.read()` / `Chunk.write()`.
    - `items_info`: `(init_param_name, item_cls, item_size)` or `None`.
    - `coerces`: field-index -> type callable (e.g. `bool`).
    - `simple`: `True` when the chunk has no string encodings, endian
      overrides, optional fields, or items, so `_decode_fields` can be
      replaced with `dict(zip(init_names, values))` plus inline coerce
      and trailing-bytes handling.
    - `expected_size`: pre-computed `struct.calcsize('>' + fmt)`.
    """
    from .chunk import Chunk

    base_names: frozenset[str] = (
        frozenset(f.name for f in fields(Chunk))
        if issubclass(cls, Chunk)
        else frozenset()
    )
    fmt_parts: list[str] = []
    data_fields: list[Attribute] = []
    encodings: dict[int, str] = {}
    endians: dict[int, str] = {}
    coerces: dict[int, type] = {}
    optional_start: int | None = None
    items_info: tuple[str, type, int] | None = None

    for f in fields(cls):
        if f.name in base_names:
            continue
        if f.metadata.get("items"):
            items_info = (
                _init_name(f.name),
                f.metadata["item_cls"],
                f.metadata["item_size"],
            )
            continue
        fmt_char = f.metadata.get("fmt")
        if fmt_char is not None:
            is_opt = f.metadata.get("optional", False)
            if is_opt:
                if optional_start is None:
                    optional_start = len(data_fields)
            elif optional_start is not None:
                raise ValueError(
                    f"{cls.__name__}.{f.name}: required field after optional"
                )
            enc = f.metadata.get("encoding")
            if enc is not None:
                encodings[len(data_fields)] = enc
            end = f.metadata.get("endian")
            if end is not None:
                endians[len(data_fields)] = end
            crc = f.metadata.get("coerce")
            if crc is not None:
                coerces[len(data_fields)] = crc
            fmt_parts.append(fmt_char)
            data_fields.append(f)

    if not fmt_parts and items_info is None:
        return None

    if optional_start is None:
        optional_start = len(data_fields)

    if fmt_parts:
        # Validate format/field count match at cache time
        combined = "".join(fmt_parts)
        n_values = len(
            struct.unpack(">" + combined, b"\x00" * struct.calcsize(">" + combined))
        )
        if n_values != len(data_fields):
            raise ValueError(
                f"{cls.__name__}: struct format yields {n_values} values "
                f"but has {len(data_fields)} fmt_field fields"
            )
    else:
        combined = ""

    init_names = tuple(_init_name(f.name) for f in data_fields)
    # Simple chunks have no string encodings, endian overrides, optional
    # fields, or items. Coerces are handled inline in the fast path.
    simple = (
        not encodings
        and not endians
        and items_info is None
        and optional_start == len(data_fields)
    )
    expected_size = struct.calcsize(">" + combined) if combined else 0

    return (
        combined,
        tuple(data_fields),
        encodings,
        optional_start,
        endians,
        items_info,
        coerces,
        init_names,
        simple,
        expected_size,
    )


# attrs `@define` sets `__hash__ = None` in class stubs, so type objects
# fail lru_cache's `Hashable` parameter check even though they are always
# hashable at runtime. The cast restores the precise signature for callers.
_struct_info = cast(
    "Callable[[type], _StructInfo | None]",
    lru_cache(maxsize=None)(_struct_info_uncached),
)


def _init_name(name: str) -> str:
    """Convert attrs field name to init parameter name.

    attrs strips the leading underscore from private field names for
    the `__init__` signature: `_trailing` -> `trailing=`.
    """
    return name.lstrip("_") if name.startswith("_") else name


def _decode_fields(
    data_fields: tuple[Attribute, ...] | list[Attribute],
    values: list[Any],
    encodings: dict[int, str],
    coerces: dict[int, type],
    init_names: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Decode raw struct values into init keyword arguments.

    Applies encoding (bytes > str) and coerce (e.g. int > bool) transforms
    declared via `fmt_field()`. Shared by `Chunk.read()` and
    `FmtItem.frombytes()`.
    """
    kw: dict[str, Any] = {}
    for i, (fld, value) in enumerate(zip(data_fields, values)):
        enc = encodings.get(i)
        if enc is not None and value is not None:
            nul = value.find(b"\x00")
            # surrogateescape keeps byte-exact round-trips even for
            # legacy non-UTF-8 bytes in old files.
            value = (
                value[:nul].decode(enc, "surrogateescape")
                if nul >= 0
                else value.decode(enc, "surrogateescape")
            )
        crc = coerces.get(i)
        if crc is not None and value is not None:
            value = crc(value)
        kw[init_names[i] if init_names is not None else _init_name(fld.name)] = value
    return kw


def _encode_value(
    value: Any,
    idx: int,
    encodings: dict[int, str],
    coerces: dict[int, type],
    endian: str,
    fmt_str: str,
) -> Any:
    """Encode a single field value for struct packing.

    Applies encoding (str > null-padded bytes) and coerce reversal
    (bool > int) transforms. Shared by `Chunk.write()` and
    `FmtItem.tobytes()`.
    """
    enc = encodings.get(idx)
    if enc is not None:
        field_size = struct.calcsize(endian + fmt_str)
        encoded = value.encode(enc, "surrogateescape")[:field_size]
        return encoded + b"\x00" * (field_size - len(encoded))
    if idx in coerces:
        return int(value)
    return value


class FmtItem:
    """Base for item types whose fields are declared with `fmt_field`."""

    @classmethod
    def frombytes(cls, data: bytes) -> FmtItem:
        """Construct an item from bytes using its `_struct_info` metadata."""
        info = _struct_info(cls)
        if info is None:
            raise TypeError(f"{cls.__name__} has no fmt_field metadata")
        (
            fmt,
            data_fields,
            encodings,
            _,
            endians,
            _,
            coerces,
            init_names,
            simple,
            expected,
        ) = info
        if endians:
            values: list[Any] = []
            pos = 0
            for i, f in enumerate(data_fields):
                fe = endians.get(i, ">")
                ff = f.metadata["fmt"]
                f_size = struct.calcsize(fe + ff)
                (v,) = struct.unpack(fe + ff, data[pos : pos + f_size])
                values.append(v)
                pos += f_size
        else:
            values = list(struct.unpack(">" + fmt, data[:expected]))
        if simple:
            kw = dict(zip(init_names, values))
            for i, crc in coerces.items():
                name = init_names[i]
                kw[name] = crc(kw[name])
        else:
            kw = _decode_fields(data_fields, values, encodings, coerces, init_names)
        return cls(**kw)

    def tobytes(self) -> bytes:
        """Serialize an item to bytes using its `_struct_info` metadata."""
        info = _struct_info(type(self))
        if info is None:
            raise TypeError(f"{type(self).__name__} has no fmt_field metadata")
        fmt, data_fields, encodings, _, endians, _, coerces, _, _simple, _ = info
        if endians:
            parts: list[bytes] = []
            for i, f in enumerate(data_fields):
                fe = endians.get(i, ">")
                value = getattr(self, f.name)
                value = _encode_value(
                    value, i, encodings, coerces, fe, f.metadata["fmt"]
                )
                parts.append(struct.pack(fe + f.metadata["fmt"], value))
            return b"".join(parts)
        values: list[Any] = []
        for i, f in enumerate(data_fields):
            value = getattr(self, f.name)
            value = _encode_value(value, i, encodings, coerces, ">", f.metadata["fmt"])
            values.append(value)
        return struct.pack(">" + fmt, *values)
