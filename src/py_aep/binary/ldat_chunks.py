"""Keyframe system chunks (lhd3, ldat) and their item types."""
from __future__ import annotations

import enum
import struct
from typing import TYPE_CHECKING

from attrs import Factory, define, field

from .bin_utils import read_bytes, write_bytes
from .bitfield import BitField
from .chunk import Chunk
from .fmt_field import FmtItem, fmt_field
from .registry import register

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
    """Keyframe list header. Stores item count, size, and raw type."""

    _prefix: bytes = fmt_field("10s")
    count: int = fmt_field("H")
    _gap: bytes = fmt_field("6s")
    item_size: int = fmt_field("H")
    _gap2: bytes = fmt_field("3s")
    item_type_raw: int = fmt_field("B")
    _trailing: bytes = field(default=b"", repr=False)

    @property
    def item_type(self) -> LdatItemType:
        """Effective item type derived from raw type and item size."""
        return _ITEM_TYPE_MAP.get(
            (self.item_type_raw, self.item_size), LdatItemType.unknown
        )


# ---------------------------------------------------------------------------
# Simple item types (not Chunk subclasses)
# ---------------------------------------------------------------------------


@define
class ShapePoint(FmtItem):
    """A single shape vertex (x, y) in big-endian float32."""

    x: float = fmt_field("f")
    y: float = fmt_field("f")


@define
class GuideItem(FmtItem):
    """A single composition guide (ruler line)."""

    orientation_type: int = fmt_field("I")
    position_type: int = fmt_field("I")
    position: float = fmt_field("d")





# ---------------------------------------------------------------------------
# Keyframe data types
# ---------------------------------------------------------------------------


@define
class KfNoValue(FmtItem):
    """Keyframe data for valueless properties (e.g. paint stroke)."""

    _unknown1: int = fmt_field("Q")
    _unknown2: float = fmt_field("d")
    in_speed: float = fmt_field("d")
    in_influence: float = fmt_field("d")
    out_speed: float = fmt_field("d")
    out_influence: float = fmt_field("d")


@define
class KfColor(FmtItem):
    """Keyframe data for color properties (RGBA)."""

    _unknown1: int = fmt_field("Q")
    _unknown2: float = fmt_field("d")
    in_speed: float = fmt_field("d")
    in_influence: float = fmt_field("d")
    out_speed: float = fmt_field("d")
    out_influence: float = fmt_field("d")
    r: float = fmt_field("d")
    g: float = fmt_field("d")
    b: float = fmt_field("d")
    a: float = fmt_field("d")
    _uf0: float = fmt_field("d")
    _uf1: float = fmt_field("d")
    _uf2: float = fmt_field("d")
    _uf3: float = fmt_field("d")
    _uf4: float = fmt_field("d")
    _uf5: float = fmt_field("d")
    _uf6: float = fmt_field("d")
    _uf7: float = fmt_field("d")

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
    def frombytes(
        cls, data: bytes, *, num_value: int
    ) -> KfMultiDimensional:
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
        vals = struct.unpack(
            ">" + "d" * total_doubles, data[8 : 8 + total_doubles * 8]
        )
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
            in_spatial_tangents=list(
                vals[5 + num_value : 5 + 2 * num_value]
            ),
            out_spatial_tangents=list(
                vals[5 + 2 * num_value : 5 + 3 * num_value]
            ),
        )

    def tobytes(self) -> bytes:
        all_vals = [
            self._unknown_header,
            self.in_speed,
            self.in_influence,
            self.out_speed,
            self.out_influence,
        ] + self.value + self.in_spatial_tangents + self.out_spatial_tangents
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
    """A single keyframe item with 8-byte header and typed payload."""

    _pad1: bytes = b"\x00"
    time_raw: int = 0
    _pad2: bytes = b"\x00"
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
    def frombytes(
        cls, data: bytes, *, item_type: LdatItemType
    ) -> LdatItem:
        # 8-byte header
        pad1 = data[0:1]
        time_raw = struct.unpack(">h", data[1:3])[0]
        pad2 = data[3:4]
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
            kf_data = KfMultiDimensional.frombytes(
                payload, num_value=num_value
            )
            expected = 5 * num_value * 8
            trailing = payload[expected:]
        else:
            # marker, unknown - raw bytes
            kf_data = payload
            trailing = b""

        return cls(
            pad1=pad1,
            time_raw=time_raw,
            pad2=pad2,
            in_interpolation_type=in_interp,
            out_interpolation_type=out_interp,
            label=label_val,
            temporal_flags=flags,
            kf_data=kf_data,
            trailing=trailing,
        )

    def tobytes(self) -> bytes:
        header = (
            self._pad1
            + struct.pack(">h", self.time_raw)
            + self._pad2
            + struct.pack(
                ">BBBB",
                self.in_interpolation_type,
                self.out_interpolation_type,
                self.label,
                self._temporal_flags,
            )
        )
        if isinstance(self.kf_data, bytes):
            payload = self.kf_data
        else:
            payload = self.kf_data.tobytes()
        return header + payload + self._trailing


# ---------------------------------------------------------------------------
# LdatChunk - registered chunk
# ---------------------------------------------------------------------------


def _read_item(data: bytes, item_type: LdatItemType) -> Any:
    """Dispatch item reading by type."""
    if item_type == LdatItemType.lrdr:
        return data
    if item_type == LdatItemType.litm:
        return data
    if item_type == LdatItemType.shape:
        return ShapePoint.frombytes(data)
    if item_type == LdatItemType.gide:
        return GuideItem.frombytes(data)
    return LdatItem.frombytes(data, item_type=item_type)


@register("ldat")
@define
class LdatChunk(Chunk):
    """Keyframe / shape / settings data items."""

    items: list[Any] = Factory(list)
    item_type: LdatItemType = LdatItemType.unknown
    item_size: int = 0
    _trailing: bytes = field(default=b"", repr=False)

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
        return cls(
            chunk_type=chunk_type,
            items=items,
            item_type=item_type,
            item_size=item_size,
            trailing=trailing,
        )

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
