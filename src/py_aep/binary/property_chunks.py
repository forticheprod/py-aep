"""Property-level chunk types: tdsb, tdb4, cdat, tdum/tduM.

TdsbChunk and Tdb4Chunk use `fmt_field()` with `BitField` descriptors.
CdatChunk and TdumChunk override `read()` / `write()` because they
have variable-length or context-dependent layouts.
"""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

from attrs import Factory, define

from .bin_utils import read_bytes, write_bytes
from .bitfield import BitField
from .chunk import Chunk
from .fmt_field import bool_field, f8_field, u1_field, u2_field, u4_field, u8_field
from .registry import register
from .scalar_chunks import _StringChunkBase

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

    chunk_type: str = "tdsb"

    roto_bezier: bool = bool_field()
    """RotoBezier flag for mask shapes (byte 0). 1 = enabled."""

    _pad1: int = u1_field(repr=False)
    _lock_flags: int = u1_field(repr=False)
    _enable_flags: int = u1_field(default=1, repr=False)

    # -- Bit-level accessors (not attrs fields) ----------------------------
    locked_ratio = BitField("_lock_flags", 4)
    dimensions_separated = BitField("_enable_flags", 1)
    enabled = BitField("_enable_flags", 0)


# ---------------------------------------------------------------------------
# tdb4 - property metadata (124 bytes, inside LIST:tdbs at index 2)
# ---------------------------------------------------------------------------
#
# Struct layout (big-endian, 124 bytes):
#   H   magic (0xdb99)
#   H   dimensions
#   B   pad1
#   B   spatial/static flags
#   H   pad2a
#   H   value_hint_type
#   B   value_hint_flag
#   B   can_vary_over_time flags
#   H   pad3a
#   H   time_base (0x7800 when has_time_base, else 0)
#   5d  unknown floats (threshold, aspect, 1.0, 1.0, 1.0)
#   B   pad4
#   B   no_value flags
#   B   pad5
#   B   type flags (vector, integer, color)
#   B   property_category
#   I   pad6a
#   H   pad6b
#   B   pad6c
#   B   animated
#   I   pad7a
#   I   pad7b
#   H   pad7c
#   B   spatial_marker
#   I   pad7d
#   Q   pad8a
#   Q   pad8b
#   Q   pad8c
#   Q   pad8d
#   H   pad9a
#   B   pad9b
#   B   expression_disabled flags
#   I   pad10


@register("tdb4")
@define
class Tdb4Chunk(Chunk):
    """Property metadata chunk (124 bytes)."""

    chunk_type: str = "tdb4"

    _magic: int = u2_field(default=0xDB99, repr=False)
    dimensions: int = u2_field(default=1)
    _pad1: int = u1_field(repr=False)
    _spatial_static_flags: int = u1_field(default=1, repr=False)
    _pad2a: int = u2_field(repr=False)
    _value_hint_type: int = u2_field(repr=False)
    _value_hint_flag: int = u1_field(repr=False)
    _cvot_flags: int = u1_field(repr=False)
    _pad3a: int = u2_field(repr=False)
    _time_base: int = u2_field(repr=False)
    _unknown_float_0: float = f8_field(default=0.0001, repr=False)
    _unknown_float_1: float = f8_field(default=1.0, repr=False)
    _unknown_float_2: float = f8_field(default=1.0, repr=False)
    _unknown_float_3: float = f8_field(default=1.0, repr=False)
    _unknown_float_4: float = f8_field(default=1.0, repr=False)
    _pad4: int = u1_field(repr=False)
    _no_value_flags: int = u1_field(repr=False)
    _pad5: int = u1_field(repr=False)
    _type_flags: int = u1_field(repr=False)
    _property_category: int = u1_field(repr=False)
    _pad6a: int = u4_field(repr=False)
    _pad6b: int = u2_field(repr=False)
    _pad6c: int = u1_field(repr=False)
    animated: bool = bool_field()
    _pad7a: int = u4_field(repr=False)
    _pad7b: int = u4_field(repr=False)
    _pad7c: int = u2_field(repr=False)
    _spatial_marker: bool = bool_field(repr=False)
    _pad7d: int = u4_field(repr=False)
    _pad8a: int = u8_field(repr=False)
    _pad8b: int = u8_field(repr=False)
    _pad8c: int = u8_field(repr=False)
    _pad8d: int = u8_field(repr=False)
    _pad9a: int = u2_field(repr=False)
    _pad9b: int = u1_field(repr=False)
    _expr_flags: int = u1_field(repr=False)
    _pad10: int = u4_field(repr=False)

    # -- Bit-level accessors (not attrs fields) ----------------------------
    is_spatial = BitField("_spatial_static_flags", 3)
    static = BitField("_spatial_static_flags", 0)
    can_vary_over_time = BitField("_cvot_flags", 1)
    no_value = BitField("_no_value_flags", 0)
    vector = BitField("_type_flags", 3)
    integer = BitField("_type_flags", 2)
    color = BitField("_type_flags", 0)
    expression_disabled = BitField("_expr_flags", 0)

    @property
    def has_time_base(self) -> bool:
        return self._time_base != 0


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

    chunk_type: str = "cdat"

    values: list[float] = Factory(list)
    is_le: bool = False

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
            instance = cls(chunk_type=chunk_type, is_le=is_le)
            if trailing:
                object.__setattr__(instance, "_trailing", trailing)
            return instance
        fmt = "<" if is_le else ">"
        fmt += f"{count}d"
        raw = read_bytes(fp, count * 8)
        vals = list(struct.unpack(fmt, raw))
        rest = size - count * 8
        trailing = read_bytes(fp, rest) if rest > 0 else b""
        instance = cls(chunk_type=chunk_type, values=vals, is_le=is_le)
        if trailing:
            object.__setattr__(instance, "_trailing", trailing)
        return instance

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
        instance = cls(
            chunk_type=chunk_type,
            values=vals,
            is_color=is_color,
            is_integer=is_integer,
        )
        if trailing:
            object.__setattr__(instance, "_trailing", trailing)
        return instance

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


# ---------------------------------------------------------------------------
# otda - orientation keyframe data (N big-endian doubles)
# ---------------------------------------------------------------------------


@register("otda")
@define
class OtdaChunk(Chunk):
    """Orientation keyframe data: N big-endian doubles (typically 3 for XYZ)."""

    chunk_type: str = "otda"
    values: list[float] = Factory(list)

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        *,
        chunk_type: str = "",
        **kwargs: Any,
    ) -> OtdaChunk:
        raw = read_bytes(fp, size)
        n = size // 8
        vals = list(struct.unpack(f">{n}d", raw[: n * 8]))
        trailing = raw[n * 8 :]
        instance = cls(chunk_type=chunk_type, values=vals)
        if trailing:
            object.__setattr__(instance, "_trailing", trailing)
        return instance

    def write(self, fp: IO[bytes]) -> int:
        raw = struct.pack(f">{len(self.values)}d", *self.values)
        written = write_bytes(fp, raw)
        if self._trailing:
            written += write_bytes(fp, self._trailing)
        return written


# ---------------------------------------------------------------------------
# tdmn - match name (40 bytes, null-padded)
# ---------------------------------------------------------------------------


@register("tdmn")
@define
class TdmnChunk(_StringChunkBase):
    """Fixed-width 40-byte null-padded match name chunk."""

    chunk_type: str = "tdmn"
    _ENCODING = "UTF-8"

    @classmethod
    def read(
        cls, fp: IO[bytes], size: int, *, chunk_type: str = "", **kw: Any
    ) -> TdmnChunk:
        raw = read_bytes(fp, size)
        return cls(chunk_type=chunk_type, value=raw.rstrip(b"\x00").decode("UTF-8"))

    def write(self, fp: IO[bytes]) -> int:
        encoded = self.value.encode("UTF-8")[:40]
        padded = encoded.ljust(40, b"\x00")
        return write_bytes(fp, padded)
