"""Miscellaneous chunk types: prin, mkif, shph, NmHd, fips, pard, fth5, dwga.

Fixed-layout chunks use `fmt_field()` and `BitField`.
Fth5Chunk uses `items_field()` for repeating feather points.
PardChunk uses variant subclass dispatch for polymorphic layouts.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from attrs import define, field

from .bin_utils import read_bytes
from .bitfield import BitField
from .chunk import Chunk
from .fmt_field import (
    FmtItem,
    ascii_field,
    bool_field,
    bytes_field,
    f4_field,
    f8_field,
    items_field,
    s2_field,
    s4_field,
    u1_field,
    u2_field,
    u4_field,
)
from .registry import register

if TYPE_CHECKING:
    from typing import IO, Any

# ---------------------------------------------------------------------------
# prin - composition renderer info (104 bytes)
# ---------------------------------------------------------------------------


@register("prin")
@define
class PrinChunk(Chunk):
    """Composition renderer plug-in info (104 bytes).

    Contains the match name and display name of the active 3D renderer.
    """

    chunk_type: str = "prin"

    _reserved_00: bytes = bytes_field(4, repr=False)
    match_name: str = ascii_field(48, default="ADBE Escher")
    """Internal match name (e.g. 'ADBE Advanced 3d')."""

    display_name: str = ascii_field(48, default="Classic 3D")
    """Human-readable name (e.g. 'Classic 3D')."""

    _reserved_68: bytes = bytes_field(3, repr=False)
    _end_marker: bytes = bytes_field(1, default=b"\x01", repr=False)


# ---------------------------------------------------------------------------
# sfdt - subfolder data (4 bytes)
# ---------------------------------------------------------------------------


@register("sfdt")
@define
class SfdtChunk(Chunk):
    """Subfolder data chunk."""

    chunk_type: str = "sfdt"
    value: int = u4_field(default=1)
    _trailing: bytes = field(default=b"", repr=False)


# ---------------------------------------------------------------------------
# prda - renderer additional data (12 bytes)
# ---------------------------------------------------------------------------


@register("prda")
@define
class PrdaChunk(Chunk):
    """Renderer additional data."""

    chunk_type: str = "prda"
    _flag: int = u4_field(default=1)
    _reserved: bytes = bytes_field(8, repr=False)
    _trailing: bytes = field(default=b"", repr=False)


# ---------------------------------------------------------------------------
# mkif - mask info (48 bytes)
# ---------------------------------------------------------------------------


@register("mkif")
@define
class MkifChunk(Chunk):
    """Mask info chunk (48 bytes).

    Contains mask flags, mode, and color.
    """

    chunk_type: str = "mkif"

    inverted: bool = bool_field()
    """1 = inverted, 0 = normal."""

    locked: bool = bool_field()
    """1 = locked, 0 = unlocked."""

    mask_motion_blur: int = u1_field()
    """0 = Same as Layer, 1 = Off, 2 = On."""

    mask_feather_falloff: int = u1_field()
    """0 = Smooth, 1 = Linear."""

    _reserved_04: bytes = bytes_field(2, repr=False)
    mode: int = u2_field()
    """0=None, 1=Add, 2=Subtract, 3=Intersect, 4=Darken, 5=Lighten, 6=Difference."""

    _reserved_08: bytes = bytes_field(37, repr=False)
    color_r: int = u1_field()
    color_g: int = u1_field()
    color_b: int = u1_field()


# ---------------------------------------------------------------------------
# shph - shape path header (24 bytes)
# ---------------------------------------------------------------------------


@register("shph")
@define
class ShphChunk(Chunk):
    """Shape path header chunk (24 bytes).

    Contains closed/open flag and bounding box for shape vertices.
    Vertex coordinates in the associated ldat are normalized to
    [0, 1] relative to this bounding box.
    """

    chunk_type: str = "shph"

    _reserved_00: bytes = bytes_field(3, default=b"\xb3\xde\x02", repr=False)
    _flags: int = u1_field(repr=False)
    """Byte 3: bit 3 = open."""

    top_left_x: float = f4_field()
    """Bounding-box left edge (x minimum)."""

    top_left_y: float = f4_field()
    """Bounding-box top edge (y minimum)."""

    bottom_right_x: float = f4_field()
    """Bounding-box right edge (x maximum)."""

    bottom_right_y: float = f4_field()
    """Bounding-box bottom edge (y maximum)."""

    _reserved_14: bytes = bytes_field(4, default=b"\x01\x00\x00\x00", repr=False)

    open = BitField("_flags", 3)
    """True when the path is open (not closed)."""


# ---------------------------------------------------------------------------
# NmHd - marker data (17 bytes)
# ---------------------------------------------------------------------------


@register("NmHd")
@define
class NmhdChunk(Chunk):
    """Marker data chunk (17 bytes).

    Contains marker flags, duration, and label color.
    """

    chunk_type: str = "NmHd"

    _reserved_00: bytes = bytes_field(3, repr=False)
    _marker_flags: int = u1_field(repr=False)
    """Byte 3: bit 2=unknown, bit 1=protected_region, bit 0=navigation."""

    _reserved_04: bytes = bytes_field(4, repr=False)
    frame_duration: int = u4_field()
    """Duration in 600ths of a second."""

    _reserved_0c: bytes = bytes_field(4, repr=False)
    label: int = u1_field()
    """Label color index."""

    _trailing: bytes = field(default=b"", repr=False)

    # BitField descriptors
    protected_region = BitField("_marker_flags", 1)
    navigation = BitField("_marker_flags", 0)

# ---------------------------------------------------------------------------
# fips - viewer panel settings (96 bytes)
# ---------------------------------------------------------------------------


@register("fips")
@define
class FipsChunk(Chunk):
    """Viewer panel settings chunk (96 bytes).

    Contains zoom, exposure, ROI, channel display, and toggle flags
    for guides, rulers, grid, etc. Bitfield flags are exposed via
    `BitField` descriptors.
    """

    chunk_type: str = "fips"

    _pad_00: bytes = bytes_field(7, repr=False)
    channels: int = u1_field()
    """Channel display mode (0=RGB, 1=Red, 2=Green, 3=Blue, 4=Alpha, 8=RGB Straight)."""

    _pad_08: bytes = bytes_field(3, repr=False)
    _grid_safe_flags: int = u1_field(repr=False)
    """Byte 11: bit 1=proportional_grid, bit 0=title_action_safe."""

    _draft_flags: int = u1_field(repr=False)
    """Byte 12: bit 2=draft3d."""

    _preview_flags: int = u1_field(repr=False)
    """Byte 13: bit 4=draft, bit 2=fast_draft, bit 0=adaptive."""

    _view_flags: int = u1_field(repr=False)
    """Byte 14: bit 7=region_of_interest, bit 6=rulers, bit 4=wireframe."""

    _display_flags: int = u1_field(repr=False)
    """Byte 15: bit 7=checkerboards, bit 4=mask_and_shape_path."""

    _pad_10: bytes = bytes_field(7, repr=False)
    _guide_flags: int = u1_field(repr=False)
    """Byte 23: bit 3=grid, bit 2=guides_snap, bit 1=guides_locked, bit 0=guides_visibility."""

    _pad_18: bytes = bytes_field(16, repr=False)
    roi_top: int = u2_field()
    roi_left: int = u2_field()
    roi_bottom: int = u2_field()
    roi_right: int = u2_field()
    _pad_30: bytes = bytes_field(21, repr=False)
    zoom_type: int = u1_field()
    """Zoom mode (0=custom, 1=fit, 2=fit up to 100%)."""

    _pad_46: bytes = bytes_field(2, repr=False)
    zoom: float = f8_field()
    """Zoom factor (1.0 = 100%)."""

    exposure: float = f4_field()
    """Exposure value in stops (-40.0 to 40.0)."""

    _pad_54: int = u1_field(repr=False)
    _color_mgmt_flags: int = u1_field(default=1, repr=False)
    """Byte 85: bit 0=use_display_color_management."""

    _resolution_flags: int = u1_field(repr=False)
    """Byte 86: bit 0=auto_resolution."""

    _trailing: bytes = field(default=b"", repr=False)

    # -- BitField descriptors (not attrs fields) ---------------------------
    proportional_grid = BitField("_grid_safe_flags", 1)
    title_action_safe = BitField("_grid_safe_flags", 0)
    draft3d = BitField("_draft_flags", 2)
    fast_preview_draft = BitField("_preview_flags", 4)
    fast_preview_fast_draft = BitField("_preview_flags", 2)
    fast_preview_adaptive = BitField("_preview_flags", 0)
    region_of_interest = BitField("_view_flags", 7)
    rulers = BitField("_view_flags", 6)
    fast_preview_wireframe = BitField("_view_flags", 4)
    checkerboards = BitField("_display_flags", 7)
    mask_and_shape_path = BitField("_display_flags", 4)
    grid = BitField("_guide_flags", 3)
    guides_snap = BitField("_guide_flags", 2)
    guides_locked = BitField("_guide_flags", 1)
    guides_visibility = BitField("_guide_flags", 0)
    use_display_color_management = BitField("_color_mgmt_flags", 0)
    auto_resolution = BitField("_resolution_flags", 0)

    @property
    def fast_preview_type(self) -> int:
        """Computed fast preview type (0=off, 1=adaptive, 2=draft, 3=fast_draft, 4=wireframe)."""
        if self.fast_preview_wireframe:
            return 4
        if self.fast_preview_fast_draft:
            return 3
        if self.fast_preview_draft:
            return 2
        if self.fast_preview_adaptive:
            return 1
        return 0


# ---------------------------------------------------------------------------
# pard - effect property parameter definitions (variant dispatch)
# ---------------------------------------------------------------------------


@register("pard")
@define
class PardChunk(Chunk):
    """Effect property parameter definition (polymorphic).

    Layout depends on `property_control_type` at byte 15. The base class
    dispatches to variant subclasses; unknown control types fall back to
    raw bytes.

    Common header (56 bytes): 15s pad, B property_control_type,
    32s name (windows-1252), 8s pad.
    """

    chunk_type: str = "pard"

    @property
    def property_control_type(self) -> int:
        """Control type discriminator at byte 15 of the raw data."""
        data = getattr(self, "data", b"")
        if len(data) > 15:
            return data[15]
        return 0

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        *,
        chunk_type: str = "",
        **kwargs: Any,
    ) -> PardChunk:
        if cls is not PardChunk:
            result = super().read(fp, size, chunk_type=chunk_type)
            assert isinstance(result, PardChunk)
            return result
        if size < 56:
            return cls(chunk_type=chunk_type, data=read_bytes(fp, size))
        # Peek at discriminator (byte 15)
        header = read_bytes(fp, 16)
        control_type = header[15]
        fp.seek(-16, 1)
        variant_cls = _PARD_VARIANTS.get(control_type, PardChunk)
        if variant_cls is PardChunk:
            return cls(chunk_type=chunk_type, data=read_bytes(fp, size))
        return variant_cls.read(fp, size, chunk_type=chunk_type)

    @property
    def name(self) -> str:
        """Decoded parameter name (from `_raw_name` up to first NUL)."""
        raw: bytes = getattr(self, "_raw_name", b"")
        if not raw:
            return ""
        nul = raw.find(b"\x00")
        if nul >= 0:
            return raw[:nul].decode("windows-1252")
        return raw.decode("windows-1252")

    @name.setter
    def name(self, value: str) -> None:
        encoded = value.encode("windows-1252")[:31]
        self._raw_name = encoded + b"\x00" * (32 - len(encoded))  # type: ignore[misc]


@define
class GenericPardChunk(PardChunk):
    """Generic pard for control types without specialized body parsing.

    Covers types 0 (LAYER), 1 (CUSTOM), 9 (NONE), 11 (ARBITRARY_DATA),
    12 (PATH), 13 (BUTTON), 14 (NO_DATA), 15 (GROUP_START).
    All are 148 bytes: 56-byte header + 92-byte body.
    """

    _pad_pre: bytes = bytes_field(15, repr=False)
    property_control_type: int = u1_field()
    _raw_name: bytes = bytes_field(32, repr=False)
    _pad_post: bytes = bytes_field(8, repr=False)
    _body: bytes = bytes_field(92, repr=False)
    _trailing: bytes = field(default=b"", repr=False)


@define
class ColorPardChunk(PardChunk):
    """Color control (type 5): 4xB last/default/max color."""

    _pad_pre: bytes = bytes_field(15, repr=False)
    property_control_type: int = u1_field(default=5)
    _raw_name: bytes = bytes_field(32, repr=False)
    _pad_post: bytes = bytes_field(8, repr=False)
    _last_color: bytes = bytes_field(4, repr=False)
    _default_color: bytes = bytes_field(4, repr=False)
    _pad_body: bytes = bytes_field(64, repr=False)
    _max_color: bytes = bytes_field(4, repr=False)
    _trailing: bytes = field(default=b"", repr=False)

    @property
    def last_color(self) -> list[int]:
        return list(self._last_color)

    @last_color.setter
    def last_color(self, value: list[int]) -> None:
        self._last_color = bytes(value)

    @property
    def default_color(self) -> list[int]:
        return list(self._default_color)

    @default_color.setter
    def default_color(self, value: list[int]) -> None:
        self._default_color = bytes(value)

    @property
    def max_color(self) -> list[int]:
        return list(self._max_color)

    @max_color.setter
    def max_color(self, value: list[int]) -> None:
        self._max_color = bytes(value)


@define
class ScalarPardChunk(PardChunk):
    """Scalar control (type 2): s4 last_value, 72s pad, s2 min, 2s pad, s2 max."""

    _pad_pre: bytes = bytes_field(15, repr=False)
    property_control_type: int = u1_field(default=2)
    _raw_name: bytes = bytes_field(32, repr=False)
    _pad_post: bytes = bytes_field(8, repr=False)
    last_value: int = s4_field()
    _pad_body: bytes = bytes_field(72, repr=False)
    min_value: int = s2_field()
    _pad_mid: bytes = bytes_field(2, repr=False)
    max_value: int = s2_field()
    _trailing: bytes = field(default=b"", repr=False)


@define
class AnglePardChunk(PardChunk):
    """Angle control (type 3): s4 last_value."""

    _pad_pre: bytes = bytes_field(15, repr=False)
    property_control_type: int = u1_field(default=3)
    _raw_name: bytes = bytes_field(32, repr=False)
    _pad_post: bytes = bytes_field(8, repr=False)
    last_value: int = s4_field()
    _trailing: bytes = field(default=b"", repr=False)


@define
class BooleanPardChunk(PardChunk):
    """Boolean control (type 4): u4 last_value, u1 default."""

    _pad_pre: bytes = bytes_field(15, repr=False)
    property_control_type: int = u1_field(default=4)
    _raw_name: bytes = bytes_field(32, repr=False)
    _pad_post: bytes = bytes_field(8, repr=False)
    last_value: int = u4_field()
    default: int = u1_field()
    _trailing: bytes = field(default=b"", repr=False)


@define
class TwoDPardChunk(PardChunk):
    """2D point control (type 6): s4 last_value_x_raw, s4 last_value_y_raw."""

    _pad_pre: bytes = bytes_field(15, repr=False)
    property_control_type: int = u1_field(default=6)
    _raw_name: bytes = bytes_field(32, repr=False)
    _pad_post: bytes = bytes_field(8, repr=False)
    last_value_x_raw: int = s4_field()
    last_value_y_raw: int = s4_field()
    _trailing: bytes = field(default=b"", repr=False)

    @property
    def last_value_x(self) -> float:
        return self.last_value_x_raw * (1.0 / 128)

    @property
    def last_value_y(self) -> float:
        return self.last_value_y_raw * (1.0 / 128)


@define
class EnumPardChunk(PardChunk):
    """Enum/popup control (type 7): u4 last_value, s4 nb_options, s4 default."""

    _pad_pre: bytes = bytes_field(15, repr=False)
    property_control_type: int = u1_field(default=7)
    _raw_name: bytes = bytes_field(32, repr=False)
    _pad_post: bytes = bytes_field(8, repr=False)
    last_value: int = u4_field()
    nb_options: int = s4_field()
    default: int = s4_field()
    _trailing: bytes = field(default=b"", repr=False)


@define
class SliderPardChunk(PardChunk):
    """Slider control (type 10): f8 last_value, 52s pad, f4 max_value."""

    _pad_pre: bytes = bytes_field(15, repr=False)
    property_control_type: int = u1_field(default=10)
    _raw_name: bytes = bytes_field(32, repr=False)
    _pad_post: bytes = bytes_field(8, repr=False)
    last_value: float = f8_field()
    _pad_body: bytes = bytes_field(52, repr=False)
    max_value: float = f4_field()
    _trailing: bytes = field(default=b"", repr=False)


@define
class ThreeDPardChunk(PardChunk):
    """3D point control (type 18): 3x f8 for x/y/z raw values."""

    _pad_pre: bytes = bytes_field(15, repr=False)
    property_control_type: int = u1_field(default=18)
    _raw_name: bytes = bytes_field(32, repr=False)
    _pad_post: bytes = bytes_field(8, repr=False)
    last_value_x_raw: float = f8_field()
    last_value_y_raw: float = f8_field()
    last_value_z_raw: float = f8_field()
    _trailing: bytes = field(default=b"", repr=False)

    @property
    def last_value_x(self) -> float:
        return self.last_value_x_raw * 512

    @property
    def last_value_y(self) -> float:
        return self.last_value_y_raw * 512

    @property
    def last_value_z(self) -> float:
        return self.last_value_z_raw * 512


# ---------------------------------------------------------------------------
# dwga - working gamma selector (1 byte)
# ---------------------------------------------------------------------------


@register("dwga")
@define
class DwgaChunk(Chunk):
    """Working gamma selector chunk (1 byte).

    Stores a single byte: 0 = gamma 2.2, non-zero = gamma 2.4.
    """

    chunk_type: str = "dwga"

    working_gamma_selector: int = u1_field()
    _trailing: bytes = field(default=b"", repr=False)


# ---------------------------------------------------------------------------
# ewot - effect workspace outline entries
# ---------------------------------------------------------------------------


@define
class EwotItem(FmtItem):
    """Single effect workspace outline entry (4 bytes).

    Bit 7 of byte 0 marks child-property entries; bit 6 marks selected.
    """

    _flags: int = u1_field()
    _data: bytes = bytes_field(3)

    is_child_property = BitField("_flags", 7)
    selected = BitField("_flags", 6)


@register("ewot")
@define
class EwotChunk(Chunk):
    """Effect workspace outline entries.

    4-byte count header followed by `count` × 4-byte entries.
    """

    chunk_type: str = "ewot"
    num_entries: int = u4_field()
    items: list[EwotItem] = items_field(EwotItem, 4)
    _trailing: bytes = field(default=b"", repr=False)


# ---------------------------------------------------------------------------
# otln - composition panel outline entries
# ---------------------------------------------------------------------------


@define
class OtlnItem(FmtItem):
    """Single comp panel outline entry (4 bytes).

    Bit 7 = collapsed, bit 6 = selected, bit 5 = is_property,
    bit 3 = is_sub_entry.  `entry_type == 68` marks layer boundaries.
    """

    _flags: int = u1_field()
    _unnamed6: bytes = bytes_field(2)
    entry_type: int = u1_field()

    collapsed = BitField("_flags", 7)
    selected = BitField("_flags", 6)
    is_property = BitField("_flags", 5)
    is_sub_entry = BitField("_flags", 3)

    @property
    def is_layer_marker(self) -> bool:
        """True when this entry is a per-layer boundary marker."""
        return self.entry_type == 68


@register("otln")
@define
class OtlnChunk(Chunk):
    """Comp panel outline entries.

    4-byte count header followed by `count` × 4-byte entries.
    """

    chunk_type: str = "otln"
    num_entries: int = u4_field()
    items: list[OtlnItem] = items_field(OtlnItem, 4)
    _trailing: bytes = field(default=b"", repr=False)


_PARD_VARIANTS: dict[int, type[PardChunk]] = {
    0: GenericPardChunk,
    1: GenericPardChunk,
    2: ScalarPardChunk,
    3: AnglePardChunk,
    4: BooleanPardChunk,
    5: ColorPardChunk,
    6: TwoDPardChunk,
    7: EnumPardChunk,
    9: GenericPardChunk,
    10: SliderPardChunk,
    11: GenericPardChunk,
    12: GenericPardChunk,
    13: GenericPardChunk,
    14: GenericPardChunk,
    15: GenericPardChunk,
    18: ThreeDPardChunk,
}


# ---------------------------------------------------------------------------
# fth5 - mask feather points (variable length, mixed endianness)
# ---------------------------------------------------------------------------


@define
class FeatherPointItem(FmtItem):
    """A single variable-width mask feather point (32 bytes).

    Integer fields are little-endian; float fields are big-endian.
    """

    seg_loc: int = u4_field(endian="<")
    """Segment index (0-based, LE u4)."""

    interp_raw: int = u4_field(endian="<")
    """Interpolation type raw value (LE u4). 0=non-Hold, 2=Hold."""

    rel_seg_loc: float = f8_field(default=0.0)
    """Relative position on the segment (0.0 to 1.0, BE f8)."""

    radius: float = f8_field(default=0.0)
    """Feather radius. Negative=inner, positive=outer (BE f8)."""

    corner_angle: float = f4_field(default=0.0)
    """Corner angle percentage 0-100 (BE f4)."""

    tension: float = f4_field(default=0.0)
    """Feather tension 0.0-1.0 (BE f4)."""


_FTH5_ITEM_SIZE = 32


@register("fth5")
@define
class Fth5Chunk(Chunk):
    """Variable-width mask feather points (32 bytes per point)."""
    chunk_type: str = "fth5"

    points: list[FeatherPointItem] = items_field(FeatherPointItem, 32)
    _trailing: bytes = field(default=b"", repr=False)
