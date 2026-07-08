"""Keyframe system chunks (lhd3, ldat) and their item types."""

from __future__ import annotations

import enum
import math
import struct
from typing import TYPE_CHECKING

from attrs import Factory, define

from .bin_utils import read_bytes, write_bytes
from .bitfield import BitField
from .chunk import Chunk
from .fmt_field import (
    FmtItem,
    bytes_field,
    f4_field,
    f8_field,
    u1_field,
    u2_field,
    u4_field,
    u8_field,
)
from .registry import register
from .render_chunks import OutputModuleSettingsItem, RenderSettingsItem

if TYPE_CHECKING:
    from typing import IO, Any


# ---------------------------------------------------------------------------
# LdatItemType enum
# ---------------------------------------------------------------------------


class LdatItemType(enum.IntEnum):
    """Keyframe / list data item type, derived from lhd3 raw type + size."""

    unknown = 0
    color = 1
    three_d_spatial = 2
    three_d = 3
    two_d_spatial = 4
    two_d = 5
    one_d = 6
    no_value = 7
    # 8 is unused
    orientation = 9
    shape = 10
    marker = 11
    lrdr = 12
    litm = 13
    gide = 14


# Dispatch table: (item_type_raw, item_size) -> LdatItemType
_ITEM_TYPE_MAP: dict[tuple[int, int], LdatItemType] = {
    (1, 2246): LdatItemType.lrdr,
    (1, 128): LdatItemType.litm,
    (2, 16): LdatItemType.gide,
    (4, 152): LdatItemType.color,
    (4, 128): LdatItemType.three_d,
    (4, 104): LdatItemType.two_d_spatial,
    (4, 88): LdatItemType.two_d,
    (4, 80): LdatItemType.orientation,
    (4, 64): LdatItemType.no_value,
    (4, 48): LdatItemType.one_d,
    (4, 16): LdatItemType.marker,
    (4, 8): LdatItemType.shape,
}

# num_value for multi-dimensional / spatial keyframe types
_NUM_VALUE: dict[int, int] = {
    LdatItemType.three_d: 3,
    LdatItemType.three_d_spatial: 3,
    LdatItemType.two_d: 2,
    LdatItemType.two_d_spatial: 2,
    LdatItemType.one_d: 1,
    LdatItemType.orientation: 1,
}


# ---------------------------------------------------------------------------
# Lhd3Chunk - keyframe list header
# ---------------------------------------------------------------------------


@register("lhd3")
@define
class Lhd3Chunk(Chunk):
    """Keyframe / list header. Stores item count, size, and raw type.

    The three `u4` counters after `item_type_raw` (`_count_b`,
    `_counter_a`, `_counter_b`) are opaque values AE maintains per list.
    Their meaning is list-type dependent: for `LIST:LRdr` they track the
    item count (with a floor of 1 when empty), but for `LIST:Gide` they
    do not - an empty guide list seeds them to `(1, 1, 2)` and three
    guides yields `(2, 1, 4)`, so they are neither a copy of `count` nor
    a simple version/id derived from it. They are kept private and set
    explicitly by mutation code rather than computed from `count`.
    """

    chunk_type: str = "lhd3"

    _prefix: bytes = bytes_field(
        10, default=b"\x00\xd0\x0b\xee\x00\x00\x00\x00\x00\x00", repr=False
    )
    count: int = u2_field()
    _count_b: int = u4_field(default=1, repr=False)
    _gap_b: bytes = bytes_field(2, default=b"\x00\x00", repr=False)
    item_size: int = u2_field()
    _gap2: bytes = bytes_field(3, default=b"\x00\x00\x00", repr=False)
    item_type_raw: int = u1_field()
    _counter_a: int = u4_field(default=1, repr=False)
    _counter_b: int = u4_field(default=2, repr=False)
    _trailing_pad: bytes | None = bytes_field(
        20, default=b"\x00" * 20, optional=True, repr=False
    )

    @property
    def item_type(self) -> LdatItemType:
        """Effective item type derived from raw type and item size."""
        return _ITEM_TYPE_MAP.get(
            (self.item_type_raw, self.item_size), LdatItemType.unknown
        )


# Block sizes for the lhd3 capacity counters, per list-container type. AE
# keeps a "block allocation" header alongside `count` that it validates on
# load; mutation code must keep it in sync or AE reports "Invalid read length".
# Verified against AE-authored samples (scan over 530 sample files):
#   keyframes (tdbs/list): block 4
#   guides (Gide/list): block 2
#   render-queue items (LRdr/list) and output modules (LItm/list): block 1
LHD3_BLOCK_KEYFRAMES = 4
LHD3_BLOCK_GUIDES = 2
LHD3_BLOCK_SINGLE = 1


def set_lhd3_count(lhd3: Lhd3Chunk, count: int, block: int) -> None:
    """Set `lhd3.count` and recompute the capacity counters from it.

    AE keeps `_count_b = ceil(count / block)` (minimum 1), `_counter_b =
    _count_b * block`, and `_counter_a = _count_b` for single-item blocks
    (render queue / output modules) else 1. Count and counters are set in
    one step because AE validates them together on load; a count written
    without the derived counters makes AE reject the file.
    """
    lhd3.count = count
    n = max(1, math.ceil(count / block))
    lhd3._count_b = n
    lhd3._counter_b = n * block
    lhd3._counter_a = n if block == 1 else 1


# ---------------------------------------------------------------------------
# Simple item types (not Chunk subclasses)
# ---------------------------------------------------------------------------


@define
class ShapePoint(FmtItem):
    """A single shape vertex (x, y) in big-endian float32."""

    x: float = f4_field()
    y: float = f4_field()


@define
class GuideItem(FmtItem):
    """A single composition guide (ruler line)."""

    orientation_type: int = u4_field()
    position_type: int = u4_field()
    position: float = f8_field()


@register("gdta")
@define
class GdtaChunk(Chunk):
    """Guide container data chunk (8 bytes, all zeros)."""

    chunk_type: str = "gdta"
    data: bytes = b"\x00\x00\x00\x00\x00\x00\x00\x00"


# ---------------------------------------------------------------------------
# Keyframe data types
# ---------------------------------------------------------------------------


@define
class KfNoValue(FmtItem):
    """Keyframe data for valueless properties (e.g. paint stroke)."""

    _unknown1: int = u8_field()
    _unknown2: float = f8_field()
    in_speed: float = f8_field()
    in_influence: float = f8_field()
    out_speed: float = f8_field()
    out_influence: float = f8_field()


@define
class KfColor(FmtItem):
    """Keyframe data for color properties (RGBA)."""

    _unknown1: int = u8_field()
    _unknown2: float = f8_field()
    in_speed: float = f8_field()
    in_influence: float = f8_field()
    out_speed: float = f8_field()
    out_influence: float = f8_field()
    r: float = f8_field()
    g: float = f8_field()
    b: float = f8_field()
    a: float = f8_field()
    _uf0: float = f8_field()
    _uf1: float = f8_field()
    _uf2: float = f8_field()
    _uf3: float = f8_field()
    _uf4: float = f8_field()
    _uf5: float = f8_field()
    _uf6: float = f8_field()
    _uf7: float = f8_field()

    @property
    def value(self) -> list[float]:
        return [self.r, self.g, self.b, self.a]

    @value.setter
    def value(self, v: list[float]) -> None:
        self.r, self.g, self.b, self.a = v


@define
class KfMultiDimensional:
    """Keyframe data for non-spatial multi-dimensional properties."""

    value: list[float] = Factory(list)
    in_speed: list[float] = Factory(list)
    in_influence: list[float] = Factory(list)
    out_speed: list[float] = Factory(list)
    out_influence: list[float] = Factory(list)

    @classmethod
    def frombytes(cls, data: bytes, *, num_value: int) -> KfMultiDimensional:
        count = 5 * num_value
        vals = struct.unpack(">" + "d" * count, data[: count * 8])
        n = num_value
        return cls(
            value=list(vals[:n]),
            in_speed=list(vals[n : 2 * n]),
            in_influence=list(vals[2 * n : 3 * n]),
            out_speed=list(vals[3 * n : 4 * n]),
            out_influence=list(vals[4 * n : 5 * n]),
        )

    def tobytes(self) -> bytes:
        all_vals = (
            self.value
            + self.in_speed
            + self.in_influence
            + self.out_speed
            + self.out_influence
        )
        return struct.pack(">" + "d" * len(all_vals), *all_vals)


@define
class KfPosition:
    """Keyframe data for spatial properties (position, anchor point)."""

    _pad1: bytes = b"\x00\x00\x00"
    _spatial_flags: int = 0
    _pad2: bytes = b"\x00\x00\x00\x00"
    _unknown_header: float = 0.0
    in_speed: float = 0.0
    in_influence: float = 0.0
    out_speed: float = 0.0
    out_influence: float = 0.0
    value: list[float] = Factory(list)
    in_spatial_tangents: list[float] = Factory(list)
    out_spatial_tangents: list[float] = Factory(list)

    spatial_auto_bezier = BitField("_spatial_flags", 1)
    spatial_continuous = BitField("_spatial_flags", 0)

    @classmethod
    def frombytes(cls, data: bytes, *, num_value: int) -> KfPosition:
        pad1 = data[:3]
        flags = data[3]
        pad2 = data[4:8]
        # 5 fixed doubles + 3*num_value array doubles
        total_doubles = 5 + 3 * num_value
        vals = struct.unpack(">" + "d" * total_doubles, data[8 : 8 + total_doubles * 8])
        return cls(
            pad1=pad1,
            spatial_flags=flags,
            pad2=pad2,
            unknown_header=vals[0],
            in_speed=vals[1],
            in_influence=vals[2],
            out_speed=vals[3],
            out_influence=vals[4],
            value=list(vals[5 : 5 + num_value]),
            in_spatial_tangents=list(vals[5 + num_value : 5 + 2 * num_value]),
            out_spatial_tangents=list(vals[5 + 2 * num_value : 5 + 3 * num_value]),
        )

    def tobytes(self) -> bytes:
        all_vals = (
            [
                self._unknown_header,
                self.in_speed,
                self.in_influence,
                self.out_speed,
                self.out_influence,
            ]
            + self.value
            + self.in_spatial_tangents
            + self.out_spatial_tangents
        )
        return (
            self._pad1
            + struct.pack(">B", self._spatial_flags)
            + self._pad2
            + struct.pack(">" + "d" * len(all_vals), *all_vals)
        )


# ---------------------------------------------------------------------------
# LdatItem - generic keyframe with header + typed payload
# ---------------------------------------------------------------------------


@define
class LdatItem:
    """A single keyframe item with 8-byte header and typed payload.

    `time_units` is the keyframe time as a signed 32-bit count of the
    comp's `internal_timebase` units per second (e.g. 24576 for 24 fps;
    measured on AE 2026 keyframes up to 10000 s).
    """

    time_units: int = 0
    in_interpolation_type: int = 0
    out_interpolation_type: int = 0
    label: int = 0
    _temporal_flags: int = 0
    kf_data: Any = b""
    _trailing: bytes = b""

    roving = BitField("_temporal_flags", 5)
    temporal_auto_bezier = BitField("_temporal_flags", 4)
    temporal_continuous = BitField("_temporal_flags", 3)

    @classmethod
    def frombytes(cls, data: bytes, *, item_type: LdatItemType) -> LdatItem:
        # 8-byte header
        time_units = struct.unpack(">i", data[0:4])[0]
        in_interp = data[4]
        out_interp = data[5]
        label_val = data[6]
        flags = data[7]

        payload = data[8:]
        num_value = _NUM_VALUE.get(item_type)
        kf_data: Any
        trailing: bytes

        if item_type == LdatItemType.color:
            kf_data = KfColor.frombytes(payload)
            trailing = payload[144:]
        elif item_type == LdatItemType.no_value:
            kf_data = KfNoValue.frombytes(payload)
            trailing = payload[48:]
        elif item_type in (
            LdatItemType.three_d_spatial,
            LdatItemType.two_d_spatial,
        ):
            assert num_value is not None
            kf_data = KfPosition.frombytes(payload, num_value=num_value)
            # prefix(8) + fixed_doubles(5*8) + arrays(3*num_value*8)
            expected = 8 + 5 * 8 + 3 * num_value * 8
            trailing = payload[expected:]
        elif num_value is not None:
            # three_d, two_d, one_d, orientation
            kf_data = KfMultiDimensional.frombytes(payload, num_value=num_value)
            expected = 5 * num_value * 8
            trailing = payload[expected:]
        else:
            # marker, unknown - raw bytes
            kf_data = payload
            trailing = b""

        return cls(
            time_units=time_units,
            in_interpolation_type=in_interp,
            out_interpolation_type=out_interp,
            label=label_val,
            temporal_flags=flags,
            kf_data=kf_data,
            trailing=trailing,
        )

    def tobytes(self) -> bytes:
        header = struct.pack(
            ">iBBBB",
            self.time_units,
            self.in_interpolation_type,
            self.out_interpolation_type,
            self.label,
            self._temporal_flags,
        )
        if isinstance(self.kf_data, bytes):
            payload = self.kf_data
        else:
            payload = self.kf_data.tobytes()
        return header + payload + self._trailing


# ---------------------------------------------------------------------------
# LdatChunk - registered chunk
# ---------------------------------------------------------------------------


def _read_item(data: bytes, item_type: LdatItemType) -> FmtItem | LdatItem:
    """Dispatch item reading by type."""
    if item_type == LdatItemType.lrdr:
        return RenderSettingsItem.frombytes(data)
    if item_type == LdatItemType.litm:
        return OutputModuleSettingsItem.frombytes(data)
    if item_type == LdatItemType.shape:
        return ShapePoint.frombytes(data)
    if item_type == LdatItemType.gide:
        return GuideItem.frombytes(data)
    return LdatItem.frombytes(data, item_type=item_type)


@register("ldat")
@define
class LdatChunk(Chunk):
    """Keyframe / shape / settings data items."""

    chunk_type: str = "ldat"

    items: list[Any] = Factory(list)
    item_type: LdatItemType = LdatItemType.unknown
    item_size: int = 0

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        *,
        chunk_type: str = "",
        item_type: LdatItemType = LdatItemType.unknown,
        item_size: int = 0,
        count: int = 0,
        is_spatial: bool = False,
        **kwargs: Any,
    ) -> LdatChunk:
        # Spatial promotion: three_d -> three_d_spatial
        if item_type == LdatItemType.three_d and is_spatial:
            item_type = LdatItemType.three_d_spatial

        if item_size == 0 or count == 0:
            data = read_bytes(fp, size)
            return cls(
                chunk_type=chunk_type,
                data=data,
                item_type=item_type,
                item_size=item_size,
            )
        items: list[Any] = []
        for _ in range(count):
            item_data = read_bytes(fp, item_size)
            items.append(_read_item(item_data, item_type))
        remaining = size - count * item_size
        trailing = read_bytes(fp, remaining) if remaining > 0 else b""
        instance = cls(
            chunk_type=chunk_type,
            items=items,
            item_type=item_type,
            item_size=item_size,
        )
        if trailing:
            object.__setattr__(instance, "_trailing", trailing)
        return instance

    def write(self, fp: IO[bytes]) -> int:
        if not self.items:
            return write_bytes(fp, self.data)
        written = 0
        for item in self.items:
            if isinstance(item, bytes):
                written += write_bytes(fp, item)
            else:
                written += write_bytes(fp, item.tobytes())
        if self._trailing:
            written += write_bytes(fp, self._trailing)
        return written
