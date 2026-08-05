"""Miscellaneous chunk types: prin, mkif, shph, NmHd, fips, pard, fth5, dwga.

Fixed-layout chunks use `fmt_field()` and `BitField`.
Fth5Chunk uses `items_field()` for repeating feather points.
PardChunk and PrdaChunk use variant subclass dispatch for polymorphic layouts.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from attrs import define

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


# ---------------------------------------------------------------------------
# pgui - 16-byte GUID
# ---------------------------------------------------------------------------


@register("pgui")
@define
class PguiChunk(Chunk):
    """16-byte GUID chunk."""

    chunk_type: str = "pgui"
    guid: bytes = bytes_field(16)

    @classmethod
    def new(cls) -> PguiChunk:
        """Build a pgui with a fresh random GUID."""
        return cls(guid=uuid.uuid4().bytes)


# ---------------------------------------------------------------------------
# prda - renderer additional data (variant dispatch)
# ---------------------------------------------------------------------------


@register("prda")
@define
class PrdaChunk(Chunk):
    """Renderer additional data (polymorphic).

    The layout is renderer-specific, so the base class dispatches on the
    sibling `prin` chunk's match name (resolved by the chunk reader), with
    the body size as a sanity check. Unknown renderers and unexpected
    sizes fall back to raw bytes and still round-trip byte-exact.

    These options are not exposed by ExtendScript.
    """

    chunk_type: str = "prda"

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        *,
        chunk_type: str = "",
        renderer_match_name: str = "",
        **kwargs: Any,
    ) -> PrdaChunk:
        if cls is not PrdaChunk:
            result = super().read(fp, size, chunk_type=chunk_type)
            assert isinstance(result, PrdaChunk)
            return result
        variant = _PRDA_VARIANTS.get(renderer_match_name)
        if variant is None or variant[1] != size:
            # preserve unknown raw bytes
            return cls(chunk_type=chunk_type, data=read_bytes(fp, size))
        return variant[0].read(fp, size, chunk_type=chunk_type)


@define
class ClassicPrdaChunk(PrdaChunk):
    """Classic 3D (`ADBE Escher`) options, 12 bytes."""

    _version: int = u4_field(default=1, repr=False)
    # Offset 4 seems likely to be unique per-renderer, but this is not fully proven.
    # Both Classic and RayTraced share the same values (version=1, tag=0), so this
    # works for now as RayTraced is deprecated. If a future renderer shares the same
    # tag value as another existing renderer, we should rename this to `_unknown_04`.
    _renderer_tag: int = u4_field(default=0, repr=False)

    shadow_map_resolution: int = u4_field(default=0)
    """Index into the Shadow Map Resolution dropdown, 0='Comp Size',
    1=250, 2=500, 3=750, 4=1000, 5=1500, 6=2000, 7=3000, 8=4000."""


@define
class AdvancedPrdaChunk(PrdaChunk):
    """Advanced 3D (`ADBE Calder`) options, 52 bytes.

    The body is genuinely mixed-endian: the header through `quality` is
    big-endian like the rest of the format, while everything from offset
    20 on is little-endian. That is AE's own layout, not a bug here.

    The three `casting_box_size_*` fields are written in lockstep by a
    single dialog control. All six float fields store fractions of the
    composition's **raw pixel** dimensions - pixel aspect ratio is not
    applied - rather than the pixel values the dialog displays.
    """

    _version: int = u4_field(default=1, repr=False)
    _renderer_tag: int = u4_field(default=3, repr=False)

    quality: int = u4_field(default=8)
    """Renderer quality, 1-125."""

    _reserved_12: int = u4_field(default=1, repr=False)
    _reserved_16: int = u4_field(default=0, repr=False)

    resolution: int = u4_field(default=1, endian="<")
    """Environment light shadow resolution:
    0='Half (2MB)', 1='Full (16MB)', 2='Double (128MB)'."""

    smoothness: int = u4_field(default=3, endian="<")
    """Environment light shadow smoothness, 1-20."""

    casting_box_size_x: float = f4_field(default=1.0, endian="<")
    """Casting box size on X, as a fraction of comp width."""

    casting_box_size_y: float = f4_field(default=1.0, endian="<")
    """Casting box size on Y, as a fraction of comp width."""

    casting_box_size_z: float = f4_field(default=1.0, endian="<")
    """Casting box size on Z, as a fraction of comp width."""

    casting_box_center_x: float = f4_field(default=0.0, endian="<")
    """Casting box centre on X, offset from comp centre, fraction of width."""

    casting_box_center_y: float = f4_field(default=0.0, endian="<")
    """Casting box centre on Y, offset from comp centre, fraction of height."""

    casting_box_center_z: float = f4_field(default=0.0, endian="<")
    """Casting box centre on Z, as a fraction of comp width."""


@define
class Cinema4DPrdaChunk(PrdaChunk):
    """Cinema 4D (`ADBE Ernst`) options, 20 bytes."""

    _version: int = u4_field(default=1, repr=False)
    _renderer_tag: int = u4_field(default=1, repr=False)

    quality: int = u4_field(default=25)
    """Renderer quality, 1-99."""

    _reserved_12: int = u4_field(default=1, repr=False)
    _reserved_16: int = u4_field(default=0, repr=False)


@define
class RayTracedPrdaChunk(PrdaChunk):
    """Ray-traced 3D (`ADBE Picasso`) options, 16 bytes.

    Legacy: this renderer has been removed since AE 17.0.
    Read-only in practice: files containing it can be parsed
    and rewritten, but no supported AE version can author one.
    """

    _version: int = u4_field(default=1, repr=False)
    _renderer_tag: int = u4_field(default=0, repr=False)
    _unknown_08: int = u4_field(default=3, repr=False)
    _unknown_12: int = u4_field(default=1, repr=False)


# Body size -> variant. Sizes are distinct per renderer, so size alone
# discriminates without needing the sibling `prin` chunk's match name.
_PRDA_VARIANTS: dict[str, tuple[type[PrdaChunk], int]] = {
    "ADBE Escher": (ClassicPrdaChunk, 12),
    "ADBE Picasso": (RayTracedPrdaChunk, 16),
    "ADBE Ernst": (Cinema4DPrdaChunk, 20),
    "ADBE Calder": (AdvancedPrdaChunk, 52),
}

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
    """SDK `PF_MaskMode`: 0=None, 1=Add, 2=Subtract, 3=Intersect,
    4=Lighten, 5=Darken, 6=Difference."""

    mask_id: int = u4_field()
    """1-based id assigned at mask creation (creation order within the
    layer)."""

    _reserved_0c: bytes = bytes_field(33, repr=False)
    color_r: int = u1_field()
    color_g: int = u1_field()
    color_b: int = u1_field()

    @property
    def color(self) -> list[float]:
        """Mask color as [R, G, B] in 0.0-1.0 range."""
        return [self.color_r / 255, self.color_g / 255, self.color_b / 255]

    @color.setter
    def color(self, value: list[float]) -> None:
        self.color_r = round(value[0] * 255)
        self.color_g = round(value[1] * 255)
        self.color_b = round(value[2] * 255)


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
    _flags: int = u1_field(default=1, repr=False)
    """Byte 3 bit flags: bit 0 = `normalized`, bit 3 = `open`. Defaults to
    `1` (normalized, closed)."""

    top_left_x: float = f4_field()
    """Bounding-box left edge (x minimum)."""

    top_left_y: float = f4_field()
    """Bounding-box top edge (y minimum)."""

    bottom_right_x: float = f4_field()
    """Bounding-box right edge (x maximum)."""

    bottom_right_y: float = f4_field()
    """Bounding-box bottom edge (y maximum)."""

    _reserved_14: bytes = bytes_field(4, default=b"\x01\x00\x00\x00", repr=False)

    normalized = BitField("_flags", 0)
    """True when the ldat points are stored as `[0, 1]` fractions of the
    bounding box (AE's universal encoding)."""

    open = BitField("_flags", 3)
    """True when the path is open (not closed)."""


# ---------------------------------------------------------------------------
# NmHd - marker data (17 bytes)
# ---------------------------------------------------------------------------


@register("NmHd")
@define
class NmhdChunk(Chunk):
    """Marker data chunk (20 bytes).

    Contains marker flags, duration, and label color.
    """

    chunk_type: str = "NmHd"

    _reserved_00: bytes = bytes_field(3, repr=False)
    _marker_flags: int = u1_field(repr=False)
    """Byte 3: bit 2=unknown, bit 1=protected_region, bit 0=navigation."""

    num_params: int = u4_field()
    """Number of cue-point parameter key/value pairs.

    Must match the number of trailing Utf8 pairs in the Nmrd list or
    AE ignores the parameters entirely.
    """

    frame_duration: int = u4_field()
    """Duration in 600ths of a second."""

    _reserved_0c: bytes = bytes_field(4, repr=False)
    label: int = u1_field()
    """Label color index."""

    _reserved_11: bytes = bytes_field(3, repr=False)
    """Bytes 17-19: trailing padding."""

    # BitField descriptors
    protected_region = BitField("_marker_flags", 1)
    navigation = BitField("_marker_flags", 0)

    @property
    def duration_seconds(self) -> float:
        """Duration in seconds (frame_duration / 600)."""
        return self.frame_duration / 600.0

    @duration_seconds.setter
    def duration_seconds(self, value: float) -> None:
        self.frame_duration = round(value * 600)


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

    @fast_preview_type.setter
    def fast_preview_type(self, value: int) -> None:
        self.fast_preview_adaptive = value == 1
        self.fast_preview_draft = value == 2
        self.fast_preview_fast_draft = value == 3
        self.fast_preview_wireframe = value == 4


# ---------------------------------------------------------------------------
# pard - effect property parameter definitions (variant dispatch)
# ---------------------------------------------------------------------------


@register("pard")
@define
class PardChunk(Chunk):
    """Effect property parameter definition (polymorphic).

    Serialized form of the AE SDK `PF_ParamDef`. Layout depends on
    `property_control_type` (the SDK `PF_ParamType`) at byte 15; the base
    class dispatches to variant subclasses and unknown control types fall
    back to raw bytes.

    Common header (56 bytes): 4s pad, u4 ui_flags (`PF_ParamUIFlags`),
    7s pad, B property_control_type, 32s name (UTF-8),
    u4 param_flags (`PF_ParamFlags`), 4s pad.
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
    def param_flags(self) -> int:
        """Low byte of the AE SDK `PF_ParamFlags` (u4 at offsets 48-51).

        Bit 1 (0x02) is `PF_ParamFlag_CANNOT_TIME_VARY`, bit 6 (0x40) is
        `PF_ParamFlag_SUPERVISE`. Validated against ExtendScript
        `canVaryOverTime` ground truth across the sample corpus.
        """
        pad: bytes = getattr(self, "_pad_post", b"")
        if len(pad) > 3:
            return pad[3]
        data = getattr(self, "data", b"")
        if len(data) > 51:
            return data[51]
        return 0

    @property
    def expressions_disabled(self) -> bool:
        """`PF_PUI_INVISIBLE` (bit 9 of the `PF_ParamUIFlags` u4 at
        offsets 4-7): the parameter is hidden from the Effect Controls
        and the Timeline, and expressions can never be set on it.

        Empirical: across the sample corpus, ExtendScript reports
        `canSetExpression = false` for every parameter with this bit set.
        """
        pre: bytes = getattr(self, "_pad_pre", b"")
        if len(pre) > 6:
            return bool(pre[6] & 0x02)
        data = getattr(self, "data", b"")
        if len(data) > 6:
            return bool(data[6] & 0x02)
        return False

    @property
    def name(self) -> str:
        """Decoded parameter name (from `_raw_name` up to first NUL)."""
        raw: bytes = getattr(self, "_raw_name", b"")
        if not raw:
            return ""
        nul = raw.find(b"\x00")
        if nul >= 0:
            return raw[:nul].decode("utf-8", "surrogateescape")
        return raw.decode("utf-8", "surrogateescape")

    @name.setter
    def name(self, value: str) -> None:
        encoded = value.encode("utf-8", "surrogateescape")[:31]
        self._raw_name = encoded + b"\x00" * (32 - len(encoded))  # type: ignore[misc]


@define
class GenericPardChunk(PardChunk):
    """Generic pard for control types without specialized body parsing.

    Covers SDK `PF_ParamType` values 0 (LAYER), 9 (NO_DATA),
    11 (ARBITRARY_DATA), 12 (PATH), 13 (GROUP_START), 14 (GROUP_END)
    and 15 (BUTTON).
    All are 148 bytes: 56-byte header + 92-byte body.
    """

    _pad_pre: bytes = bytes_field(15, repr=False)
    property_control_type: int = u1_field()
    _raw_name: bytes = bytes_field(32, repr=False)
    _pad_post: bytes = bytes_field(8, repr=False)
    _body: bytes = bytes_field(92, repr=False)


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
class IntegerPardChunk(PardChunk):
    """Integer slider (type 1, SDK `PF_Param_SLIDER` / `PF_SliderDef`).

    Body: s4 value, 32s value_str, 32s value_desc, s4 valid_min,
    s4 valid_max, s4 slider_min, s4 slider_max, s4 default. The valid
    range is what ExtendScript reports as `minValue`/`maxValue`;
    `default` is the parameter's factory default value.
    """

    _pad_pre: bytes = bytes_field(15, repr=False)
    property_control_type: int = u1_field(default=1)
    _raw_name: bytes = bytes_field(32, repr=False)
    _pad_post: bytes = bytes_field(8, repr=False)
    last_value: int = s4_field()
    _value_str: bytes = bytes_field(32, repr=False)
    _value_desc: bytes = bytes_field(32, repr=False)
    valid_min: int = s4_field()
    valid_max: int = s4_field()
    slider_min: int | None = s4_field(optional=True, default=None)
    slider_max: int | None = s4_field(optional=True, default=None)
    default: int | None = s4_field(optional=True, default=None)


@define
class ScalarPardChunk(PardChunk):
    """Fixed-point slider (type 2, SDK `PF_Param_FIX_SLIDER` /
    `PF_FixedSliderDef`).

    Body: `PF_Fixed` (16.16 fixed point, `raw / 65536`) value, 32s
    value_str, 32s value_desc, then PF_Fixed valid_min / valid_max
    (what ExtendScript reports as `minValue`/`maxValue`), PF_Fixed
    slider_min / slider_max (the UI slider range) and PF_Fixed
    default (the parameter's factory default value).
    """

    _pad_pre: bytes = bytes_field(15, repr=False)
    property_control_type: int = u1_field(default=2)
    _raw_name: bytes = bytes_field(32, repr=False)
    _pad_post: bytes = bytes_field(8, repr=False)
    last_value_raw: int = s4_field()
    _value_str: bytes = bytes_field(32, repr=False)
    _value_desc: bytes = bytes_field(32, repr=False)
    valid_min_raw: int = s4_field()
    valid_max_raw: int = s4_field()
    slider_min_raw: int = s4_field()
    slider_max_raw: int = s4_field()
    default_raw: int | None = s4_field(optional=True, default=None)

    @property
    def last_value(self) -> float:
        return self.last_value_raw / 65536

    @property
    def valid_min(self) -> float:
        return self.valid_min_raw / 65536

    @property
    def valid_max(self) -> float:
        return self.valid_max_raw / 65536

    @property
    def slider_min(self) -> float:
        return self.slider_min_raw / 65536

    @property
    def slider_max(self) -> float:
        return self.slider_max_raw / 65536

    @property
    def default(self) -> float | None:
        return None if self.default_raw is None else self.default_raw / 65536


@define
class AnglePardChunk(PardChunk):
    """Angle control (type 3, SDK `PF_AngleDef`).

    Body: `PF_Fixed` (16.16 fixed point, `raw / 65536`) value, then
    PF_Fixed default (the parameter's factory default value).
    """

    _pad_pre: bytes = bytes_field(15, repr=False)
    property_control_type: int = u1_field(default=3)
    _raw_name: bytes = bytes_field(32, repr=False)
    _pad_post: bytes = bytes_field(8, repr=False)
    last_value_raw: int = s4_field()
    default_raw: int | None = s4_field(optional=True, default=None)

    @property
    def last_value(self) -> float:
        return self.last_value_raw / 65536

    @property
    def default(self) -> float | None:
        return None if self.default_raw is None else self.default_raw / 65536


@define
class BooleanPardChunk(PardChunk):
    """Boolean control (type 4): u4 last_value, u1 default."""

    _pad_pre: bytes = bytes_field(15, repr=False)
    property_control_type: int = u1_field(default=4)
    _raw_name: bytes = bytes_field(32, repr=False)
    _pad_post: bytes = bytes_field(8, repr=False)
    last_value: int = u4_field()
    default: int = u1_field()


@define
class TwoDPardChunk(PardChunk):
    """2D point control (type 6): s4 last_value_x_raw, s4 last_value_y_raw."""

    _pad_pre: bytes = bytes_field(15, repr=False)
    property_control_type: int = u1_field(default=6)
    _raw_name: bytes = bytes_field(32, repr=False)
    _pad_post: bytes = bytes_field(8, repr=False)
    last_value_x_raw: int = s4_field()
    last_value_y_raw: int = s4_field()

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


@define
class SliderPardChunk(PardChunk):
    """Float slider (type 10, SDK `PF_Param_FLOAT_SLIDER` /
    `PF_FloatSliderDef`).

    Body: f8 value, f8 phase, 32s value_desc, then f4 valid_min /
    valid_max (what ExtendScript reports as `minValue`/`maxValue`;
    non-finite means that side is unbounded), f4 slider_min /
    slider_max (the UI slider range) and f4 default (the parameter's
    factory default value).
    """

    _pad_pre: bytes = bytes_field(15, repr=False)
    property_control_type: int = u1_field(default=10)
    _raw_name: bytes = bytes_field(32, repr=False)
    _pad_post: bytes = bytes_field(8, repr=False)
    last_value: float = f8_field()
    phase: float = f8_field()
    _value_desc: bytes = bytes_field(32, repr=False)
    valid_min: float = f4_field()
    valid_max: float = f4_field()
    slider_min: float = f4_field()
    slider_max: float = f4_field()
    default: float | None = f4_field(optional=True, default=None)
    _precision: int | None = u2_field(optional=True, default=None, repr=False)
    display_flags: int | None = u2_field(optional=True, default=None)
    """SDK `PF_ValueDisplayFlags`: bit 0 (PERCENT) is the only flag AE
    writes reliably for float sliders (fixed-point sliders leave it 0)."""

    @property
    def displays_percent(self) -> bool:
        """SDK `PF_ValueDisplayFlag_PERCENT` (bit 0)."""
        flags = self.display_flags
        return flags is not None and bool(flags & 0x01)


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
    """Working gamma selector chunk (4 bytes).

    The first byte selects the gamma (0 = 2.2, non-zero = 2.4)
    """

    chunk_type: str = "dwga"

    working_gamma_selector: int = u1_field()
    _reserved_01: bytes = bytes_field(3, repr=False)

    @property
    def working_gamma(self) -> float:
        """Working gamma (2.2 or 2.4)."""
        return 2.2 if self.working_gamma_selector == 0 else 2.4

    @working_gamma.setter
    def working_gamma(self, value: float) -> None:
        self.working_gamma_selector = 0 if value == 2.2 else 1


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


_PARD_VARIANTS: dict[int, type[PardChunk]] = {
    0: GenericPardChunk,
    1: IntegerPardChunk,
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


# ---------------------------------------------------------------------------
# Source / footage utility chunks
# ---------------------------------------------------------------------------


@register("apid")
@define
class ApidChunk(Chunk):
    """Application color profile ID (16 bytes, all 0xff = unmanaged)."""

    chunk_type: str = "apid"
    data: bytes = b"\xff" * 16


@register("epid")
@define
class EpidChunk(Chunk):
    """Embedded color profile ID (16 bytes, all 0xff = unmanaged)."""

    chunk_type: str = "epid"
    data: bytes = b"\xff" * 16


@register("empd")
@define
class EmpdChunk(Chunk):
    """Embedded-profile-present flag.

    AE writes this (value 1) when the source file carries an embedded color
    profile; the `Utf8` chunk that follows it in `LIST:CLRS` holds the
    profile's name (e.g. `Coated FOGRA39 (ISO 12647-2:2004)`). Absent when the
    source has no embedded profile.
    """

    chunk_type: str = "empd"
    value: bool = bool_field(default=True)


@register("linl")
@define
class LinlChunk(Chunk):
    """Linearization setting (4 bytes little-endian)."""

    chunk_type: str = "linl"
    value: int = u4_field(endian="<", default=2)


@register("embp")
@define
class EmbpChunk(Chunk):
    """Embed profile flag."""

    chunk_type: str = "embp"
    value: bool = bool_field(default=True)


@register("ipws")
@define
class IpwsChunk(Chunk):
    """Input profile working space."""

    chunk_type: str = "ipws"
    value: int = u1_field(default=1)


@register("dcui")
@define
class DcuiChunk(Chunk):
    """Display color UI flag (solid sources only)."""

    chunk_type: str = "dcui"
    value: bool = bool_field(default=True)


@register("prgb")
@define
class PrgbChunk(Chunk):
    """Preserve RGB flag (solid sources only)."""

    chunk_type: str = "prgb"
    value: int = u1_field(default=1)


@register("Mcsp")
@define
class McspChunk(Chunk):
    """Monitor color space flag."""

    chunk_type: str = "Mcsp"
    value: bool = bool_field(default=True)


@register("ocsp")
@define
class OcspChunk(Chunk):
    """Output color space flag."""

    chunk_type: str = "ocsp"
    value: bool = bool_field(default=True)


@register("hdrm")
@define
class HdrmChunk(Chunk):
    """HDR mode flag."""

    chunk_type: str = "hdrm"
    value: bool = bool_field(default=True)


@register("strt")
@define
class StrtChunk(Chunk):
    """Media start info (8 bytes)."""

    chunk_type: str = "strt"
    _reserved_00: bytes = bytes_field(4, repr=False)
    fps_byte: int = u1_field(default=1)
    _reserved_05: bytes = bytes_field(3, repr=False)


@register("drop")
@define
class DropChunk(Chunk):
    """Drop frame flag."""

    chunk_type: str = "drop"
    value: bool = bool_field(default=True)


@register("ftgi")
@define
class FtgiChunk(Chunk):
    """Footage interpretation global info (16 bytes)."""

    chunk_type: str = "ftgi"
    start_offset: int = u4_field()
    frame_rate_num: int = u4_field(default=1)
    end_frame: int = u4_field(default=0xFFFFFFFF)
    time_base: int = u4_field(default=600)
