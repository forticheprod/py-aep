"""Declarative field-format binding for chunk I/O.

Each field declares its struct format via `fmt_field("B")`.
`_struct_info()` introspects attrs metadata to derive the combined
format string and field list.  Generic `Chunk.read()` / `write()`
use this to handle all fixed-layout chunks with zero per-class I/O code.
"""
from __future__ import annotations

import struct
from functools import lru_cache
from typing import TYPE_CHECKING

from attrs import Attribute, Factory, field, fields

if TYPE_CHECKING:
    from typing import Any


def fmt_field(
    fmt: str,
    *,
    default: Any = 0,
    repr: bool = True,
    encoding: str | None = None,
    optional: bool = False,
    endian: str | None = None,
) -> Any:
    """Declare an attrs field with its struct format in metadata.

    Args:
        fmt: struct format character(s) (e.g. ``"B"``, ``"48s"``).
        default: Default value for the field.
        repr: Whether to include this field in ``repr()``.
        encoding: When set, the raw ``bytes`` from ``struct.unpack``
            are decoded to ``str`` (stripping trailing NUL bytes),
            and on write the ``str`` is encoded back and NUL-padded
            to fill the fixed size.
        optional: When ``True``, the field may be absent in older
            binary versions. Use ``default=None`` so that ``None``
            means "not present" (preserves round-trip fidelity).
            Optional fields must come after all required fields.
        endian: Per-field byte-order override (e.g. ``"<"`` for
            little-endian). When ``None`` (default), the chunk-level
            big-endian default is used. Triggers per-field I/O in
            `Chunk.read()` / `Chunk.write()`.
    """
    md: dict[str, Any] = {"fmt": fmt}
    if encoding is not None:
        md["encoding"] = encoding
    if optional:
        md["optional"] = True
    if endian == "<":
        md["endian"] = endian
    return field(default=default, repr=repr, metadata=md)


def items_field(
    item_cls: type,
    item_size: int,
) -> Any:
    """Declare a list-of-items field that fills the remaining body bytes.

    The item count is inferred at read time: ``count = remaining // item_size``.
    Item classes must use ``fmt_field()`` for their fields (with ``endian``
    and ``encoding`` as needed) so that ``_struct_info()`` can auto-serialize
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


@lru_cache(maxsize=None)
def _struct_info(
    cls: type,
) -> tuple[
    str,
    tuple[Attribute, ...],
    Attribute | None,
    dict[int, str],
    int,
    dict[int, str],
    tuple[str, type, int] | None,
] | None:
    """Derive struct layout metadata for a chunk class.

    Returns a 7-tuple ``(fmt, data_fields, trailing, encodings,
    optional_start, endians, items_info)`` or ``None`` for raw-bytes
    chunks that have neither ``fmt_field`` nor ``items_field`` fields.

    - ``encodings``: field-index -> encoding name.
    - ``optional_start``: index of first optional field.
    - ``endians``: field-index -> endian override (``"<"`` or ``">"``);
      non-empty triggers per-field I/O in `Chunk.read()` / `Chunk.write()`.
    - ``items_info``: ``(init_param_name, item_cls, item_size)`` or ``None``.
    """
    from .chunk import Chunk

    base_names: frozenset[str] = (
        frozenset(f.name for f in fields(Chunk))
        if issubclass(cls, Chunk)
        else frozenset()
    )
    fmt_parts: list[str] = []
    data_fields: list[Attribute] = []
    trailing: Attribute | None = None
    encodings: dict[int, str] = {}
    endians: dict[int, str] = {}
    optional_start: int | None = None
    items_info: tuple[str, type, int] | None = None

    for f in fields(cls):
        if f.name in base_names:
            continue
        if f.name == "_trailing":
            trailing = f
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
            fmt_parts.append(fmt_char)
            data_fields.append(f)

    if not fmt_parts and items_info is None:
        return None

    if optional_start is None:
        optional_start = len(data_fields)

    if fmt_parts:
        # Validate format/field count match at cache time
        combined = "".join(fmt_parts)
        n_values = len(struct.unpack(">" + combined, b"\x00" * struct.calcsize(">" + combined)))
        if n_values != len(data_fields):
            raise ValueError(
                f"{cls.__name__}: struct format yields {n_values} values "
                f"but has {len(data_fields)} fmt_field fields"
            )
    else:
        combined = ""

    return combined, tuple(data_fields), trailing, encodings, optional_start, endians, items_info


def _init_name(name: str) -> str:
    """Convert attrs field name to init parameter name.

    attrs strips the leading underscore from private field names for
    the `__init__` signature: `_trailing` -> `trailing=`.
    """
    return name.lstrip("_") if name.startswith("_") else name


class FmtItem:
    """Base for item types whose fields are declared with `fmt_field`."""

    @classmethod
    def frombytes(cls, data: bytes) -> FmtItem:
        """Construct an item from bytes using its `_struct_info` metadata."""
        info = _struct_info(cls)
        if info is None:
            raise TypeError(f"{cls.__name__} has no fmt_field metadata")
        fmt, data_fields, _, encodings, _, endians, _ = info
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
            values = list(struct.unpack(">" + fmt, data[: struct.calcsize(">" + fmt)]))
        kw: dict[str, Any] = {}
        for i, (fld, value) in enumerate(zip(data_fields, values)):
            enc = encodings.get(i)
            if enc is not None and value is not None:
                nul = value.find(b"\x00")
                value = value[:nul].decode(enc) if nul >= 0 else value.decode(enc)
            kw[_init_name(fld.name)] = value
        return cls(**kw)

    def tobytes(self) -> bytes:
        """Serialize an item to bytes using its `_struct_info` metadata."""
        info = _struct_info(type(self))
        if info is None:
            raise TypeError(f"{type(self).__name__} has no fmt_field metadata")
        fmt, data_fields, _, encodings, _, endians, _ = info
        if endians:
            parts: list[bytes] = []
            for i, f in enumerate(data_fields):
                fe = endians.get(i, ">")
                value = getattr(self, f.name)
                enc = encodings.get(i)
                if enc is not None:
                    field_size = struct.calcsize(fe + f.metadata["fmt"])
                    encoded = value.encode(enc)[:field_size]
                    value = encoded + b"\x00" * (field_size - len(encoded))
                parts.append(struct.pack(fe + f.metadata["fmt"], value))
            return b"".join(parts)
        values: list[Any] = []
        for i, f in enumerate(data_fields):
            value = getattr(self, f.name)
            enc = encodings.get(i)
            if enc is not None:
                field_size = struct.calcsize(">" + f.metadata["fmt"])
                encoded = value.encode(enc)[:field_size]
                value = encoded + b"\x00" * (field_size - len(encoded))
            values.append(value)
        return struct.pack(">" + fmt, *values)
