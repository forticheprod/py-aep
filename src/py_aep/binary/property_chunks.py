"""Property-level chunk types: tdsb, tdb4, cdat, tdum/tduM.

TdsbChunk and Tdb4Chunk use `fmt_field()` with `BitField` descriptors.
CdatChunk and TdumChunk override `read()` / `write()` because they
have variable-length or context-dependent layouts.
"""
from __future__ import annotations

import struct
from typing import TYPE_CHECKING

from attrs import Factory, define, field

from .bin_utils import read_bytes, write_bytes
from .bitfield import BitField
from .chunk import Chunk
from .fmt_field import fmt_field
from .registry import register

if TYPE_CHECKING:
    from typing import IO, Any


# ---------------------------------------------------------------------------
# tdsb - property flags (4 bytes, always inside LIST:tdbs at index 0)
# ---------------------------------------------------------------------------


@register("tdsb")
@define
class TdsbChunk(Chunk):
    """Property flags chunk (4 bytes).

    Bit-level flags are exposed via `BitField` descriptors that read/write
    through the raw byte fields.
    """

    roto_bezier: int = fmt_field("B")
    """RotoBezier flag for mask shapes (byte 0). 1 = enabled."""

    _pad1: int = fmt_field("B", repr=False)
    _lock_flags: int = fmt_field("B", repr=False)
    _enable_flags: int = fmt_field("B", repr=False)
    _trailing: bytes = field(default=b"", repr=False)

    # -- Bit-level accessors (not attrs fields) ----------------------------
    locked_ratio = BitField("_lock_flags", 4)
    dimensions_separated = BitField("_enable_flags", 1)
    enabled = BitField("_enable_flags", 0)


# ---------------------------------------------------------------------------
# tdb4 - property metadata (124 bytes, inside LIST:tdbs at index 2)
# ---------------------------------------------------------------------------
#
# Struct layout (big-endian):
#   H   magic (0xdb99)
#   H   dimensions
#   B   pad
#   B   spatial/static flags
#   5s  pad
#   B   can_vary_over_time flags
#   4s  pad
#   5d  unknown floats (threshold, aspect, 1.0, 1.0, 1.0)
#   B   pad
#   B   no_value flags
#   B   pad
#   B   type flags (vector, integer, color)
#   8s  pad
#   B   animated
#   15s pad
#   32s reserved (zeros)
#   3s  pad
#   B   expression_disabled flags
#   4s  pad
# Total: 124 bytes


@register("tdb4")
@define
class Tdb4Chunk(Chunk):
    """Property metadata chunk (124 bytes)."""

    _magic: int = fmt_field("H", default=0xDB99, repr=False)
    dimensions: int = fmt_field("H")
    _pad1: int = fmt_field("B", repr=False)
    _spatial_static_flags: int = fmt_field("B", repr=False)
    _pad2: bytes = fmt_field("5s", default=b"\x00" * 5, repr=False)
    _cvot_flags: int = fmt_field("B", repr=False)
    _pad3: bytes = fmt_field("4s", default=b"\x00" * 4, repr=False)
    _unknown_float_0: float = fmt_field("d", default=0.0001, repr=False)
    _unknown_float_1: float = fmt_field("d", default=1.0, repr=False)
    _unknown_float_2: float = fmt_field("d", default=1.0, repr=False)
    _unknown_float_3: float = fmt_field("d", default=1.0, repr=False)
    _unknown_float_4: float = fmt_field("d", default=1.0, repr=False)
    _pad4: int = fmt_field("B", repr=False)
    _no_value_flags: int = fmt_field("B", repr=False)
    _pad5: int = fmt_field("B", repr=False)
    _type_flags: int = fmt_field("B", repr=False)
    _pad6: bytes = fmt_field("8s", default=b"\x00" * 8, repr=False)
    animated: int = fmt_field("B")
    _pad7: bytes = fmt_field("15s", default=b"\x00" * 15, repr=False)
    _pad8: bytes = fmt_field("32s", default=b"\x00" * 32, repr=False)
    _pad9: bytes = fmt_field("3s", default=b"\x00" * 3, repr=False)
    _expr_flags: int = fmt_field("B", repr=False)
    _pad10: bytes = fmt_field("4s", default=b"\x00" * 4, repr=False)
    _trailing: bytes = field(default=b"", repr=False)

    # -- Bit-level accessors (not attrs fields) ----------------------------
    is_spatial = BitField("_spatial_static_flags", 3)
    static = BitField("_spatial_static_flags", 0)
    can_vary_over_time = BitField("_cvot_flags", 1)
    no_value = BitField("_no_value_flags", 0)
    vector = BitField("_type_flags", 3)
    integer = BitField("_type_flags", 2)
    color = BitField("_type_flags", 0)
    expression_disabled = BitField("_expr_flags", 0)


# ---------------------------------------------------------------------------
# cdat - property value doubles (variable length, optional LE for OTST)
# ---------------------------------------------------------------------------


@register("cdat")
@define
class CdatChunk(Chunk):
    """Property value chunk storing one or more doubles.

    Normally big-endian.  When `is_le` is true (inside an OTST
    orientation list), values are stored little-endian.
    """

    values: list[float] = Factory(list)
    is_le: bool = False
    _trailing: bytes = field(default=b"", repr=False)

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        *,
        chunk_type: str = "",
        is_le: bool = False,
        **kwargs: Any,
    ) -> CdatChunk:
        count = size // 8
        if count == 0:
            trailing = read_bytes(fp, size) if size > 0 else b""
            return cls(
                chunk_type=chunk_type, is_le=is_le, trailing=trailing,
            )
        fmt = "<" if is_le else ">"
        fmt += f"{count}d"
        raw = read_bytes(fp, count * 8)
        vals = list(struct.unpack(fmt, raw))
        rest = size - count * 8
        trailing = read_bytes(fp, rest) if rest > 0 else b""
        return cls(
            chunk_type=chunk_type, values=vals, is_le=is_le,
            trailing=trailing,
        )

    def write(self, fp: IO[bytes]) -> int:
        written = 0
        if self.values:
            count = len(self.values)
            fmt = "<" if self.is_le else ">"
            fmt += f"{count}d"
            raw = struct.pack(fmt, *self.values)
            written += write_bytes(fp, raw)
        if self._trailing:
            written += write_bytes(fp, self._trailing)
        return written


# ---------------------------------------------------------------------------
# tdum / tduM - property min/max value (variable, context-dependent)
# ---------------------------------------------------------------------------


@register("tdum", "tduM")
@define
class TdumChunk(Chunk):
    """Property min/max value chunk.

    Layout depends on sibling tdb4 flags:
    - color: 4 x f4 (big-endian floats)
    - integer: 1 x u4 (big-endian uint32)
    - otherwise: N x f8 (big-endian doubles, N = size / 8)
    """

    values: list[float] = Factory(list)
    """Stored values (floats for color/scalar, int cast to float for integer)."""

    is_color: bool = False
    is_integer: bool = False
    _trailing: bytes = field(default=b"", repr=False)

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        *,
        chunk_type: str = "",
        is_color: bool = False,
        is_integer: bool = False,
        **kwargs: Any,
    ) -> TdumChunk:
        raw = read_bytes(fp, size)
        if is_color:
            vals = list(struct.unpack(">4f", raw[:16]))
            trailing = raw[16:]
        elif is_integer:
            (v,) = struct.unpack(">I", raw[:4])
            vals = [float(v)]
            trailing = raw[4:]
        else:
            count = size // 8
            vals = list(struct.unpack(f">{count}d", raw[: count * 8]))
            trailing = raw[count * 8 :]
        return cls(
            chunk_type=chunk_type,
            values=vals,
            is_color=is_color,
            is_integer=is_integer,
            trailing=trailing,
        )

    def write(self, fp: IO[bytes]) -> int:
        if self.is_color:
            raw = struct.pack(">4f", *self.values)
        elif self.is_integer:
            raw = struct.pack(">I", int(self.values[0]))
        else:
            raw = struct.pack(f">{len(self.values)}d", *self.values)
        written = write_bytes(fp, raw)
        if self._trailing:
            written += write_bytes(fp, self._trailing)
        return written
