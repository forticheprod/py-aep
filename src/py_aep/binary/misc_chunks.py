"""Miscellaneous chunk types: prin, mkif, shph, NmHd, fips, pard, fth5.

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
from .fmt_field import FmtItem, fmt_field, items_field
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

    _reserved_00: bytes = fmt_field("4s", default=b"\x00" * 4, repr=False)
    match_name: str = fmt_field("48s", default="", encoding="ascii")
    """Internal match name (e.g. 'ADBE Advanced 3d')."""

    display_name: str = fmt_field("48s", default="", encoding="ascii")
    """Human-readable name (e.g. 'Classic 3D')."""

    _reserved_68: bytes = fmt_field("3s", default=b"\x00" * 3, repr=False)
    _end_marker: bytes = fmt_field("1s", default=b"\x01", repr=False)


# ---------------------------------------------------------------------------
# mkif - mask info (48 bytes)
# ---------------------------------------------------------------------------


@register("mkif")
@define
class MkifChunk(Chunk):
    """Mask info chunk (48 bytes).

    Contains mask flags, mode, and color.
    """

    inverted: int = fmt_field("B")
    """1 = inverted, 0 = normal."""

    locked: int = fmt_field("B")
    """1 = locked, 0 = unlocked."""

    mask_motion_blur: int = fmt_field("B")
    """0 = Same as Layer, 1 = Off, 2 = On."""

    mask_feather_falloff: int = fmt_field("B")
    """0 = Smooth, 1 = Linear."""

    _reserved_04: bytes = fmt_field("2s", default=b"\x00" * 2, repr=False)
    mode: int = fmt_field("H")
    """0=None, 1=Add, 2=Subtract, 3=Intersect, 4=Darken, 5=Lighten, 6=Difference."""

    _reserved_08: bytes = fmt_field("37s", default=b"\x00" * 37, repr=False)
    color_r: int = fmt_field("B")
    color_g: int = fmt_field("B")
    color_b: int = fmt_field("B")


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

    _reserved_00: bytes = fmt_field("3s", default=b"\x00" * 3, repr=False)
    _flags: int = fmt_field("B", repr=False)
    """Byte 3: bit 3 = open."""

    top_left_x: float = fmt_field("f")
    """Bounding-box left edge (x minimum)."""

    top_left_y: float = fmt_field("f")
    """Bounding-box top edge (y minimum)."""

    bottom_right_x: float = fmt_field("f")
    """Bounding-box right edge (x maximum)."""

    bottom_right_y: float = fmt_field("f")
    """Bounding-box bottom edge (y maximum)."""

    _reserved_14: bytes = fmt_field("4s", default=b"\x00" * 4, repr=False)

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

    _reserved_00: bytes = fmt_field("3s", default=b"\x00" * 3, repr=False)
    _marker_flags: int = fmt_field("B", repr=False)
    """Byte 3: bit 2=unknown, bit 1=protected_region, bit 0=navigation."""

    _reserved_04: bytes = fmt_field("4s", default=b"\x00" * 4, repr=False)
    frame_duration: int = fmt_field("I")
    """Duration in 600ths of a second."""

    _reserved_0c: bytes = fmt_field("4s", default=b"\x00" * 4, repr=False)
    label: int = fmt_field("B")
    """Label color index."""

    _trailing: bytes = field(default=b"", repr=False)

    # BitField descriptors
    protected_region = BitField("_marker_flags", 1)
    navigation = BitField("_marker_flags", 0)

    @property
    def duration(self) -> float:
        """Marker duration in seconds."""
        return self.frame_duration / 600.0


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

    _pad_00: bytes = fmt_field("7s", default=b"\x00" * 7, repr=False)
    channels: int = fmt_field("B")
    """Channel display mode (0=RGB, 1=Red, 2=Green, 3=Blue, 4=Alpha, 8=RGB Straight)."""

    _pad_08: bytes = fmt_field("3s", default=b"\x00" * 3, repr=False)
    _grid_safe_flags: int = fmt_field("B", repr=False)
    """Byte 11: bit 1=proportional_grid, bit 0=title_action_safe."""

    _draft_flags: int = fmt_field("B", repr=False)
    """Byte 12: bit 2=draft3d."""

    _preview_flags: int = fmt_field("B", repr=False)
    """Byte 13: bit 4=draft, bit 2=fast_draft, bit 0=adaptive."""

    _view_flags: int = fmt_field("B", repr=False)
    """Byte 14: bit 7=region_of_interest, bit 6=rulers, bit 4=wireframe."""

    _display_flags: int = fmt_field("B", repr=False)
    """Byte 15: bit 7=checkerboards, bit 4=mask_and_shape_path."""

    _pad_10: bytes = fmt_field("7s", default=b"\x00" * 7, repr=False)
    _guide_flags: int = fmt_field("B", repr=False)
    """Byte 23: bit 3=grid, bit 2=guides_snap, bit 1=guides_locked, bit 0=guides_visibility."""

    _pad_18: bytes = fmt_field("16s", default=b"\x00" * 16, repr=False)
    roi_top: int = fmt_field("H")
    roi_left: int = fmt_field("H")
    roi_bottom: int = fmt_field("H")
    roi_right: int = fmt_field("H")
    _pad_30: bytes = fmt_field("21s", default=b"\x00" * 21, repr=False)
    zoom_type: int = fmt_field("B")
    """Zoom mode (0=custom, 1=fit, 2=fit up to 100%)."""

    _pad_46: bytes = fmt_field("2s", default=b"\x00" * 2, repr=False)
    zoom: float = fmt_field("d")
    """Zoom factor (1.0 = 100%)."""

    exposure: float = fmt_field("f")
    """Exposure value in stops (-40.0 to 40.0)."""

    _pad_54: int = fmt_field("B", repr=False)
    _color_mgmt_flags: int = fmt_field("B", repr=False)
    """Byte 85: bit 0=use_display_color_management."""

    _resolution_flags: int = fmt_field("B", repr=False)
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
            return super().read(fp, size, chunk_type=chunk_type)  # type: ignore[return-value]
        if size < 56:
            return cls(chunk_type=chunk_type, data=read_bytes(fp, size))
        # Peek at discriminator (byte 15)
        header = read_bytes(fp, 16)
        control_type = header[15]
        fp.seek(-16, 1)
        variant_cls = _PARD_VARIANTS.get(control_type, PardChunk)
        if variant_cls is PardChunk:
            return cls(chunk_type=chunk_type, data=read_bytes(fp, size))
        return variant_cls.read(fp, size, chunk_type=chunk_type)  # type: ignore[attr-defined, no-any-return]

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
        self._raw_name = encoded + b"\x00" * (32 - len(encoded))


@define
class ColorPardChunk(PardChunk):
    """Color control (type 5): 4xB last/default/max color."""

    _pad_pre: bytes = fmt_field("15s", default=b"\x00" * 15, repr=False)
    property_control_type: int = fmt_field("B", default=5)
    _raw_name: bytes = fmt_field("32s", default=b"\x00" * 32, repr=False)
    _pad_post: bytes = fmt_field("8s", default=b"\x00" * 8, repr=False)
    _last_color: bytes = fmt_field("4s", default=b"\x00" * 4, repr=False)
    _default_color: bytes = fmt_field("4s", default=b"\x00" * 4, repr=False)
    _pad_body: bytes = fmt_field("64s", default=b"\x00" * 64, repr=False)
    _max_color: bytes = fmt_field("4s", default=b"\x00" * 4, repr=False)
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

    _pad_pre: bytes = fmt_field("15s", default=b"\x00" * 15, repr=False)
    property_control_type: int = fmt_field("B", default=2)
    _raw_name: bytes = fmt_field("32s", default=b"\x00" * 32, repr=False)
    _pad_post: bytes = fmt_field("8s", default=b"\x00" * 8, repr=False)
    last_value: int = fmt_field("i")
    _pad_body: bytes = fmt_field("72s", default=b"\x00" * 72, repr=False)
    min_value: int = fmt_field("h")
    _pad_mid: bytes = fmt_field("2s", default=b"\x00" * 2, repr=False)
    max_value: int = fmt_field("h")
    _trailing: bytes = field(default=b"", repr=False)


@define
class AnglePardChunk(PardChunk):
    """Angle control (type 3): s4 last_value."""

    _pad_pre: bytes = fmt_field("15s", default=b"\x00" * 15, repr=False)
    property_control_type: int = fmt_field("B", default=3)
    _raw_name: bytes = fmt_field("32s", default=b"\x00" * 32, repr=False)
    _pad_post: bytes = fmt_field("8s", default=b"\x00" * 8, repr=False)
    last_value: int = fmt_field("i")
    _trailing: bytes = field(default=b"", repr=False)


@define
class BooleanPardChunk(PardChunk):
    """Boolean control (type 4): u4 last_value, u1 default."""

    _pad_pre: bytes = fmt_field("15s", default=b"\x00" * 15, repr=False)
    property_control_type: int = fmt_field("B", default=4)
    _raw_name: bytes = fmt_field("32s", default=b"\x00" * 32, repr=False)
    _pad_post: bytes = fmt_field("8s", default=b"\x00" * 8, repr=False)
    last_value: int = fmt_field("I")
    default: int = fmt_field("B")
    _trailing: bytes = field(default=b"", repr=False)


@define
class TwoDPardChunk(PardChunk):
    """2D point control (type 6): s4 last_value_x_raw, s4 last_value_y_raw."""

    _pad_pre: bytes = fmt_field("15s", default=b"\x00" * 15, repr=False)
    property_control_type: int = fmt_field("B", default=6)
    _raw_name: bytes = fmt_field("32s", default=b"\x00" * 32, repr=False)
    _pad_post: bytes = fmt_field("8s", default=b"\x00" * 8, repr=False)
    last_value_x_raw: int = fmt_field("i")
    last_value_y_raw: int = fmt_field("i")
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

    _pad_pre: bytes = fmt_field("15s", default=b"\x00" * 15, repr=False)
    property_control_type: int = fmt_field("B", default=7)
    _raw_name: bytes = fmt_field("32s", default=b"\x00" * 32, repr=False)
    _pad_post: bytes = fmt_field("8s", default=b"\x00" * 8, repr=False)
    last_value: int = fmt_field("I")
    nb_options: int = fmt_field("i")
    default: int = fmt_field("i")
    _trailing: bytes = field(default=b"", repr=False)


@define
class SliderPardChunk(PardChunk):
    """Slider control (type 10): f8 last_value, 52s pad, f4 max_value."""

    _pad_pre: bytes = fmt_field("15s", default=b"\x00" * 15, repr=False)
    property_control_type: int = fmt_field("B", default=10)
    _raw_name: bytes = fmt_field("32s", default=b"\x00" * 32, repr=False)
    _pad_post: bytes = fmt_field("8s", default=b"\x00" * 8, repr=False)
    last_value: float = fmt_field("d")
    _pad_body: bytes = fmt_field("52s", default=b"\x00" * 52, repr=False)
    max_value: float = fmt_field("f")
    _trailing: bytes = field(default=b"", repr=False)


@define
class ThreeDPardChunk(PardChunk):
    """3D point control (type 18): 3x f8 for x/y/z raw values."""

    _pad_pre: bytes = fmt_field("15s", default=b"\x00" * 15, repr=False)
    property_control_type: int = fmt_field("B", default=18)
    _raw_name: bytes = fmt_field("32s", default=b"\x00" * 32, repr=False)
    _pad_post: bytes = fmt_field("8s", default=b"\x00" * 8, repr=False)
    last_value_x_raw: float = fmt_field("d")
    last_value_y_raw: float = fmt_field("d")
    last_value_z_raw: float = fmt_field("d")
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


_PARD_VARIANTS: dict[int, type] = {
    2: ScalarPardChunk,
    3: AnglePardChunk,
    4: BooleanPardChunk,
    5: ColorPardChunk,
    6: TwoDPardChunk,
    7: EnumPardChunk,
    10: SliderPardChunk,
    18: ThreeDPardChunk,
}


# ---------------------------------------------------------------------------
# fth5 - mask feather points (variable length, mixed endianness)
# ---------------------------------------------------------------------------


@define
class FeatherPoint(FmtItem):
    """A single variable-width mask feather point (32 bytes).

    Integer fields are little-endian; float fields are big-endian.
    """

    seg_loc: int = fmt_field("I", endian="<")
    """Segment index (0-based, LE u4)."""

    interp_raw: int = fmt_field("I", endian="<")
    """Interpolation type raw value (LE u4). 0=non-Hold, 2=Hold."""

    rel_seg_loc: float = fmt_field("d", default=0.0)
    """Relative position on the segment (0.0 to 1.0, BE f8)."""

    radius: float = fmt_field("d", default=0.0)
    """Feather radius. Negative=inner, positive=outer (BE f8)."""

    corner_angle: float = fmt_field("f", default=0.0)
    """Corner angle percentage 0-100 (BE f4)."""

    tension: float = fmt_field("f", default=0.0)
    """Feather tension 0.0-1.0 (BE f4)."""


_FTH5_ITEM_SIZE = 32


@register("fth5")
@define
class Fth5Chunk(Chunk):
    """Variable-width mask feather points (32 bytes per point)."""

    points: list[FeatherPoint] = items_field(FeatherPoint, 32)
    _trailing: bytes = field(default=b"", repr=False)
