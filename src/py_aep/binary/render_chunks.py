"""Render queue chunk types: Roou, Ropt, Rout.

RouuChunk exposes output module settings fields as `fmt_field()`.
RoptChunk uses variant subclass dispatch by format_code.
RoutChunk uses `items_field()` for repeating render-flag entries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from attrs import define, fields

from .bin_utils import read_bytes, to_dividend_divisor
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
    str_field,
    u1_field,
    u2_field,
    u4_field,
)
from .registry import register

if TYPE_CHECKING:
    from typing import IO, Any

# ---------------------------------------------------------------------------
# Roou - output module settings (154+ bytes)
# ---------------------------------------------------------------------------


@register("Roou")
@define
class RouuChunk(Chunk):
    """Output module settings chunk.

    Contains video/audio codec, format, dimensions, frame rate, depth,
    and channel settings.

    Field defaults reproduce the full 154-byte `Rouu` body AE writes for a
    fresh "TIFF Sequence with Alpha" output module (a simple image sequence
    with an empty `Ropt` and no audio), so a freshly created `RouuChunk()` is
    a valid output format with no preferences needed. The placeholder
    `width`/`height` are overwritten once output dimensions are resolved.
    """

    chunk_type: str = "Roou"

    _magic: bytes = bytes_field(4, default=b"FXTC", repr=False)
    video_codec: str = ascii_field(4, default="FXTC")
    """Video codec 4-char code."""

    _reserved_08: bytes = bytes_field(
        8, default=b"\x0f\x10\x06\x43\x80\x00\x00\x00", repr=False
    )
    starting_number: int = u4_field()
    """Starting frame number for image sequence output."""

    _reserved_14: bytes = bytes_field(
        6, default=b"\xff\xff\xff\xff\x01\x00", repr=False
    )
    format_id: str = ascii_field(4, default="TIF ")
    """Output format 4-char identifier (e.g. '.AVI', 'H264', 'png!')."""

    _reserved_1e: bytes = bytes_field(2, repr=False)
    _reserved_20: bytes = bytes_field(4, repr=False)
    width: int = u2_field(default=100)
    """Output width (0 when video disabled)."""

    _reserved_26: bytes = bytes_field(2, repr=False)
    height: int = u2_field(default=100)
    """Output height (0 when video disabled)."""

    _reserved_2a: bytes = bytes_field(15, repr=False)
    applied_marker: int = u1_field(default=1)
    """Set to 1 once AE applies the format header to a render queue item;
    0 in prefs-stored output module templates."""

    _reserved_3a: bytes = bytes_field(9, repr=False)
    frame_rate: int = u1_field(default=30)
    depth: int = s4_field(default=32)
    """Color depth in total bits-per-pixel as a signed 4-byte big-endian value:
    24=Millions/8bpc, 48=Trillions/16bpc, 96=Floating/32bpc, and -32 for the
    32bpc single-channel `Floating Point Gray` depth."""

    _reserved_48: bytes = bytes_field(5, default=b"\x01\x01\x00\x00\x00", repr=False)
    color_premultiplied: int = u1_field(default=1)
    _reserved_4e: bytes = bytes_field(3, repr=False)
    color_matted: int = u1_field(default=1)
    _reserved_52: bytes = bytes_field(
        18, default=b"FIEL\x00\x01" + b"\x00" * 12, repr=False
    )
    audio_sample_rate: float = f8_field(default=-1.0)
    """Audio sample rate in Hz (e.g. 44100.0, 48000.0)."""

    audio_disabled_hi: int = u1_field(default=255)
    """0xFF when audio is disabled."""

    audio_format: int = u1_field(default=255)
    """Audio format: 2=16-bit, 3=24-bit, 4=32-bit."""

    _reserved_6e: int = u1_field(default=255, repr=False)
    audio_bit_depth: int = u1_field(default=255)
    """Audio bit depth: 1=8-bit, 2=16-bit, 4=32-bit."""

    _reserved_70: int = u1_field(repr=False)
    audio_channels: int = u1_field()
    """1=mono, 2=stereo."""

    # The 40 bytes AE writes after the audio fields (offset 0x72..0x99); carries
    # a few audio-config sub-bytes that vary by codec. The default is the
    # block AE writes for a fresh image-sequence output module. Older
    # writers emit only the first 114 bytes; `optional=True` keeps short
    # bodies parseable (the field reads as None and is skipped on write,
    # so they round-trip), while newly built chunks still write 154 bytes.
    _reserved_72: bytes | None = bytes_field(
        40,
        default=b"\x00" * 13 + b"\x01" + b"\x00" * 3 + b"\x01" + b"\x00" * 22,
        optional=True,
        repr=False,
    )


# ---------------------------------------------------------------------------
# Ropt - format-specific render options (variant dispatch by format_code)
# ---------------------------------------------------------------------------


@register("Ropt")
@define
class RoptChunk(Chunk):
    """Format-specific render options (polymorphic).

    Layout depends on `format_code` (first 4 bytes). The base class
    dispatches to variant subclasses; unknown format codes fall back
    to raw bytes.
    """

    chunk_type: str = "Ropt"

    @property
    def format_code(self) -> str:
        """Format code from the first 4 bytes of raw data (for fallback chunks)."""
        data = getattr(self, "data", b"")
        if len(data) >= 4:
            return data[:4].decode("ascii")
        return ""

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        *,
        chunk_type: str = "",
        **kwargs: Any,
    ) -> RoptChunk:
        if cls is not RoptChunk:
            # Variant subclass - use standard fmt_field parsing
            return super().read(fp, size, chunk_type=chunk_type)  # type: ignore[return-value]  # returns Self
        if size < 4:
            return cls(chunk_type=chunk_type, data=read_bytes(fp, size))
        # Peek at discriminator (first 4 bytes = format_code)
        disc_raw = read_bytes(fp, 4)
        format_code = disc_raw.decode("ascii")
        fp.seek(-4, 1)
        variant_cls = _ROPT_VARIANTS.get(format_code, RoptChunk)
        if variant_cls is RoptChunk:
            return cls(chunk_type=chunk_type, data=read_bytes(fp, size))
        return variant_cls.read(fp, size, chunk_type=chunk_type)


# Pad defaults reproducing AE's real `Ropt` bytes per format (oEXR/png! from
# AE preferences, others from sample projects). Long blocks are module-level
# constants so the field declarations stay readable.
_JPEG_PAD = bytes.fromhex(
    "002e0000003a01000000000000000000001c00000000000000004a503634"
    "000000000000000000000000000000000000"
)
_TARGA_PAD = (
    bytes.fromhex("002e000000540400") + b"\x00" * 9 + b"\x36" + b"\x00" * 54 + b"\x01"
)
_PNG_TRAILING = (
    bytes.fromhex("00000006") + b"\x00" * 8 + bytes.fromhex("00000004") + b"\x00" * 272
)


@define
class CineonRoptChunk(RoptChunk):
    """Cineon/DPX render options (format_code='sDPX').

    Field defaults reproduce AE's exact 48-byte DPX `Ropt`, so a default
    `CineonRoptChunk()` is a valid format-options chunk.
    """

    format_code: str = ascii_field(4, default="sDPX")
    _pad: bytes = bytes_field(
        10, default=bytes.fromhex("00030000003000000000"), repr=False
    )
    ten_bit_black_point: int = u2_field(default=1)
    ten_bit_white_point: int = u2_field(default=1023)
    converted_black_point: float = f8_field(default=0.0)
    converted_white_point: float = f8_field(default=1.0)
    current_gamma: float = f8_field(default=1.0)
    highlight_expansion: int = u2_field()
    logarithmic_conversion: bool = bool_field()
    file_format: int = u1_field(default=1)
    bit_depth: int = u1_field(default=10)
    _pad_end: bytes = bytes_field(1, repr=False)


@define
class JpegRoptChunk(RoptChunk):
    """JPEG render options (format_code='JPEG').

    Field defaults reproduce AE's exact 58-byte JPEG `Ropt`, so a default
    `JpegRoptChunk()` is a valid format-options chunk.
    """

    format_code: str = ascii_field(4, default="JPEG")
    _pad: bytes = bytes_field(48, default=_JPEG_PAD, repr=False)
    quality: int = u2_field(default=5)
    format_type: int = u2_field()
    scans: int = u2_field(default=1)


@define
class OpenExrRoptChunk(RoptChunk):
    """OpenEXR render options (format_code='oEXR').

    Field defaults reproduce AE's exact 78-byte OpenEXR `Ropt`, so a default
    `OpenExrRoptChunk()` is a valid format-options chunk.
    """

    format_code: str = ascii_field(4, default="oEXR")
    _pad_04: bytes = bytes_field(
        10, default=bytes.fromhex("00010000004e01000000"), repr=False
    )
    compression: int = u1_field(default=2)
    thirty_two_bit_float: bool = bool_field()
    luminance_chroma: bool = bool_field()
    _pad_11: bytes = bytes_field(1, repr=False)
    dwa_compression_level: float = f4_field(default=0.0, endian="<")
    _pad_end: bytes = bytes_field(56, repr=False)


@define
class TargaRoptChunk(RoptChunk):
    """Targa render options (format_code='TPIC').

    Field defaults reproduce AE's exact 84-byte Targa `Ropt`, so a default
    `TargaRoptChunk()` is a valid format-options chunk.
    """

    format_code: str = ascii_field(4, default="TPIC")
    _pad: bytes = bytes_field(73, default=_TARGA_PAD, repr=False)
    bits_per_pixel: int = u1_field(default=24)
    _pad2: bytes = bytes_field(4, default=b"TimS", repr=False)
    rle_compression: bool = bool_field()
    _pad_end: bytes = bytes_field(1, repr=False)


@define
class TiffRoptChunk(RoptChunk):
    """TIFF render options (format_code='TIF ').

    The pad defaults carry the fixed markers AE writes for a TIFF sequence,
    so a default `TiffRoptChunk()` is the exact `Ropt` AE writes for "TIFF
    Sequence with Alpha" - used as the format options for a freshly created
    output module.
    """

    format_code: str = ascii_field(4, default="TIF ")
    _pad_04: bytes = bytes_field(4, default=bytes([1, 9, 0, 0]), repr=False)
    chunk_size: int = u2_field(default=602)
    """Full `Ropt` body size in bytes (AE writes a redundant copy here)."""

    _pad_0a: bytes = bytes_field(
        590, default=bytes([0, 0, 1, 1]) + b"\x00" * 586, repr=False
    )
    ibm_pc_byte_order: bool = bool_field()
    lzw_compression: bool = bool_field()


@define
class PngRoptChunk(RoptChunk):
    """PNG render options (format_code='png!').

    Field defaults reproduce AE's exact 322-byte PNG `Ropt`, so a default
    `PngRoptChunk()` is a valid format-options chunk. The placeholder
    `width`/`height` come from the reference template.
    """

    format_code: str = ascii_field(4, default="png!")
    _pad: bytes = bytes_field(
        14, default=bytes.fromhex("0001000001420100000000000001"), repr=False
    )
    width: int = u4_field(default=320)
    height: int = u4_field(default=240)
    _pad2: bytes = bytes_field(2, repr=False)
    bit_depth: int = u2_field(default=16)
    compression: int = u4_field()
    _pad_end: bytes = bytes_field(288, default=_PNG_TRAILING, repr=False)


_ROPT_VARIANTS: dict[str, type[RoptChunk]] = {
    "sDPX": CineonRoptChunk,
    "JPEG": JpegRoptChunk,
    "oEXR": OpenExrRoptChunk,
    "TPIC": TargaRoptChunk,
    "TIF ": TiffRoptChunk,
    "png!": PngRoptChunk,
}


# ---------------------------------------------------------------------------
# Rout - render queue item flags (variable length, repeating items)
# ---------------------------------------------------------------------------


@define
class RoutItem(FmtItem):
    """A single render queue item entry (4 bytes).

    Contains a render flag at bit 6 of the first byte.
    The last byte holds a position-dependent slot type code:
    0x11 for slots 0/1/3, 0x7B for slot 2, 0x88 for slot 4.
    """

    _flags: int = u1_field(repr=False)
    _pad: bytes = bytes_field(2, default=b"\x00\x00", repr=False)
    _state: int = u1_field(repr=False)

    render = BitField("_flags", 6)


# ---------------------------------------------------------------------------
# Render settings ldat item (2246 bytes per item)
# ---------------------------------------------------------------------------


@define
class RenderSettingsItem(FmtItem):
    """Per-render-queue-item settings (2246 bytes).

    Stored as ldat items in the LIST:list under LIST:LRdr.
    """

    # Reserved-region defaults reproduce the constant bytes AE writes for a
    # render-queue item (verified identical across real items). Without them
    # AE reports "missing data in file" when opening a py_aep-created item.
    _reserved_00: bytes = bytes_field(
        7, default=b"\x00\x01\x00\x00\x00\x00\x00", repr=False
    )
    _flag_byte: int = u1_field(repr=False)
    comp_id: int = u4_field()
    status: int = s4_field(default=2)  # RQItemStatus.QUEUED (-1 = WILL_CONTINUE)
    _reserved_06: bytes = bytes_field(4, default=b"\x00\x03\x00\x00", repr=False)
    time_span_start_dividend: int = s4_field()
    time_span_start_divisor: int = u4_field(default=1)
    time_span_duration_dividend: int = s4_field()
    time_span_duration_divisor: int = u4_field(default=1)
    _reserved_11: bytes = bytes_field(8, repr=False)
    frame_rate_integer: int = u2_field()
    frame_rate_fractional: int = u2_field()
    _reserved_14: bytes = bytes_field(2, repr=False)
    field_render: int = u2_field()
    _reserved_16: bytes = bytes_field(2, repr=False)
    pulldown: int = u2_field()
    quality: int = u2_field(default=2)  # RenderQuality.BEST
    resolution_x: int = u2_field(default=1)
    resolution_y: int = u2_field(default=1)
    _reserved_21: bytes = bytes_field(2, repr=False)
    effects: int = u2_field(default=2)  # EffectsSetting.CURRENT_SETTINGS
    _reserved_23: bytes = bytes_field(2, repr=False)
    proxy_use: int = u2_field()
    _reserved_25: bytes = bytes_field(2, repr=False)
    motion_blur: int = u2_field(default=1)  # MotionBlurSetting.ON_FOR_CHECKED_LAYERS
    _reserved_27: bytes = bytes_field(2, repr=False)
    frame_blending: int = u2_field(
        default=1
    )  # FrameBlendingSetting.ON_FOR_CHECKED_LAYERS
    _reserved_29: bytes = bytes_field(2, repr=False)
    log_type: int = u2_field()
    _reserved_31: bytes = bytes_field(2, repr=False)
    skip_existing_files: bool = u2_field(coerce=bool)
    _reserved_33: bytes = bytes_field(4, repr=False)
    # Defaults mirror AE's factory "Best Settings" render template, so a fresh
    # item is valid even when parse() had no ae_preferences_dir to read from.
    template_name: str = str_field(64, default="Best Settings", encoding="windows-1252")
    _reserved_35: bytes = bytes_field(1990, repr=False)
    use_this_frame_rate: int = u2_field()
    _reserved_37: bytes = bytes_field(2, repr=False)
    time_span_source: int = u2_field()
    _reserved_39: bytes = bytes_field(
        14, default=b"\xff\xff\xff\xff\x00\xb4" + b"\x00" * 8, repr=False
    )
    solo_switches: int = u2_field(default=2)  # SoloSwitchesSetting.CURRENT_SETTINGS
    _reserved_41: bytes = bytes_field(2, repr=False)
    disk_cache: int = u2_field()
    _reserved_43: bytes = bytes_field(2, repr=False)
    guide_layers: int = u2_field()
    _reserved_45: bytes = bytes_field(
        6, default=b"\x00\x00\x00\x02\xff\xff", repr=False
    )
    color_depth: int = u2_field(default=0xFFFF)  # current/project depth
    _reserved_47: bytes = bytes_field(16, repr=False)
    start_time: int = u4_field()
    elapsed_seconds: int = u4_field()
    _remaining: bytes = bytes_field(
        40, default=b"\x00" * 19 + b"\x02\x00\x00\x00\x0f" + b"\x00" * 16, repr=False
    )

    queue_item_notify = BitField("_flag_byte", 2)

    _TEMPLATE_FIELDS: ClassVar[tuple[str, ...]] = (
        "quality",
        "resolution_x",
        "resolution_y",
        "effects",
        "motion_blur",
        "frame_blending",
        "field_render",
        "pulldown",
        "proxy_use",
        "solo_switches",
        "disk_cache",
        "guide_layers",
        "color_depth",
        "log_type",
        "skip_existing_files",
        "template_name",
    )

    def copy_settings_from(self, source: RenderSettingsItem) -> None:
        """Copy template-relevant settings from another item.

        Only the fields that AE's "Apply Template" dialog sets are
        copied; identity fields like comp_id, status, and time spans
        are preserved.
        """
        for field in self._TEMPLATE_FIELDS:
            setattr(self, field, getattr(source, field))

    @property
    def clean_template_name(self) -> str:
        """Template name with trailing null bytes stripped."""
        return self.template_name.strip("\x00")

    # -- Computed properties -----------------------------------------------

    @property
    def frame_rate(self) -> float:
        """Assembled frame rate (integer + fractional/65536)."""
        return self.frame_rate_integer + self.frame_rate_fractional / 65536.0

    @frame_rate.setter
    def frame_rate(self, value: float) -> None:
        self.frame_rate_integer = int(value)
        self.frame_rate_fractional = round((value - int(value)) * 65536)

    @property
    def time_span_start(self) -> float:
        """Time span start in seconds (dividend / divisor)."""
        if self.time_span_start_divisor == 0:
            return 0.0
        return self.time_span_start_dividend / self.time_span_start_divisor

    @time_span_start.setter
    def time_span_start(self, value: float) -> None:
        self.time_span_start_dividend, self.time_span_start_divisor = (
            to_dividend_divisor(value)
        )

    @property
    def time_span_duration(self) -> float:
        """Time span duration in seconds (dividend / divisor)."""
        if self.time_span_duration_divisor == 0:
            return 0.0
        return self.time_span_duration_dividend / self.time_span_duration_divisor

    @time_span_duration.setter
    def time_span_duration(self, value: float) -> None:
        self.time_span_duration_dividend, self.time_span_duration_divisor = (
            to_dividend_divisor(value)
        )


# ---------------------------------------------------------------------------
# Output module settings ldat item (128 bytes per item)
# ---------------------------------------------------------------------------


@define
class OutputModuleSettingsItem(FmtItem):
    """Per-output-module settings (128 bytes).

    Stored as ldat items in the LIST:list within each render queue item.

    Field defaults reproduce the settings AE writes for a fresh
    "TIFF Sequence with Alpha" output module, so a freshly created
    `OutputModuleSettingsItem()` is valid with no preferences needed.
    """

    _reserved_00: bytes = bytes_field(
        7, default=b"\x00\x05\x00\x00\x00\x00\x00", repr=False
    )
    _flag_byte_07: int = u1_field(default=8, repr=False)
    """Byte 7: bit 7=preserve_rgb, bit 6=include_source_xmp,
    bit 4=use_region_of_interest, bit 3=use_comp_frame_number."""

    post_render_target_comp_id: int = u4_field()
    _reserved_08: bytes = bytes_field(4, default=b"\x00\x00\x00\x01", repr=False)
    _reserved_09: bytes = bytes_field(3, repr=False)
    channels: int = u1_field(default=1)
    _reserved_11: bytes = bytes_field(3, repr=False)
    resize_quality: int = u1_field(default=1)
    _reserved_13: bytes = bytes_field(3, default=b"\x00\x01\x00", repr=False)
    resize: bool = bool_field()
    _reserved_15: bytes = bytes_field(1, repr=False)
    lock_aspect_ratio: bool = bool_field(default=True)
    _reserved_17: bytes = bytes_field(1, repr=False)
    _flag_byte_22: int = u1_field(repr=False)
    """Byte 22: bit 0=crop."""

    crop_top: int = s2_field()
    crop_left: int = s2_field()
    crop_bottom: int = s2_field()
    crop_right: int = s2_field()
    _reserved_24: bytes = bytes_field(2, repr=False)
    output_audio: int = u1_field(default=1)
    _reserved_26: bytes = bytes_field(4, repr=False)
    include_project_link: bool = bool_field()
    post_render_action: int = u4_field()
    post_render_use_comp: int = u4_field()
    _reserved_30: bytes = bytes_field(16, default=b"\xff" * 16, repr=False)
    output_profile_id: bytes = bytes_field(16, default=b"\xff" * 16)
    _reserved_32: bytes = bytes_field(3, repr=False)
    convert_to_linear_light: int = u1_field(default=2)
    _prev_byte_34: bytes = bytes_field(1, default=b"\x01", repr=False)
    output_color_space_working: int = u1_field(default=1)
    _reserved_36: bytes = bytes_field(34, repr=False)

    preserve_rgb = BitField("_flag_byte_07", 7)
    include_source_xmp = BitField("_flag_byte_07", 6)
    use_region_of_interest = BitField("_flag_byte_07", 4)
    use_comp_frame_number = BitField("_flag_byte_07", 3)
    crop = BitField("_flag_byte_22", 0)

    _TEMPLATE_FIELDS: ClassVar[tuple[str, ...]] = (
        "_flag_byte_07",
        "_reserved_09",
        "channels",
        "_reserved_11",
        "resize_quality",
        "_reserved_13",
        "resize",
        "_reserved_15",
        "lock_aspect_ratio",
        "_reserved_17",
        "_flag_byte_22",
        "crop_top",
        "crop_left",
        "crop_bottom",
        "crop_right",
        "_reserved_24",
        "output_audio",
        "_reserved_26",
        "include_project_link",
        "post_render_action",
        "_reserved_30",
        "output_profile_id",
        "_reserved_32",
        "convert_to_linear_light",
        "_prev_byte_34",
        "output_color_space_working",
        "_reserved_36",
    )

    def copy_settings_from(self, source: OutputModuleSettingsItem) -> None:
        """Copy template-relevant settings from another item.

        Only the fields that AE's "Apply Template" dialog sets are
        copied; identity fields like `post_render_target_comp_id` and
        `post_render_use_comp` are preserved.
        """
        for field in self._TEMPLATE_FIELDS:
            setattr(self, field, getattr(source, field))

    def restore_from(self, source: OutputModuleSettingsItem) -> None:
        """Copy EVERY field from `source`, keeping this item's identity.

        Used by `OutputModule.batch_edit` rollback: this item is
        referenced from the ldat items list, so restoring in place
        avoids re-wiring references.
        """
        for field in fields(OutputModuleSettingsItem):
            setattr(self, field.name, getattr(source, field.name))


_ROUT_ITEM_SIZE = 4

# AE writes a fixed block of 5 Rout items per render queue item (1 render-flag
# entry followed by 4 position-dependent slot entries), independent of the
# number of output modules.
ROUT_ITEMS_PER_RQ_ITEM = 5


@register("Rout")
@define
class RoutChunk(Chunk):
    """Render queue item flags chunk.

    4-byte header followed by 4 bytes per item, each with a render
    flag at bit 6 of the first byte.
    """

    chunk_type: str = "Rout"

    count: int = u4_field()
    items: list[RoutItem] = items_field(RoutItem, 4)


# ---------------------------------------------------------------------------
# ARsi - render queue state (fixed 1872 bytes, mostly opaque)
# ---------------------------------------------------------------------------


@register("ARsi")
@define
class ArsiChunk(Chunk):
    """Render queue state chunk (`LRdr/LSIf`), a fixed 1872 bytes.

    The body is a 7-byte header followed by 88-byte slot records; most of
    it is opaque to py_aep. Only the two bytes AE rewrites when the render
    queue goes from empty to non-empty are named, so callers can set them
    by name instead of poking raw offsets. The remaining bytes are kept as
    reserved blocks that round-trip verbatim.
    """

    chunk_type: str = "ARsi"

    _reserved_00: bytes = bytes_field(3, repr=False)
    queue_nonempty: int = u1_field()
    """Offset 3: 1 once the render queue holds at least one item, else 0."""

    _reserved_04: bytes = bytes_field(375, repr=False)
    active_slot_state: int = u1_field()
    """Offset 379: a slot state byte AE rewrites on the empty -> first-item
    transition (set to 0x73). Exact semantics are not fully understood."""

    _reserved_180: bytes = bytes_field(1492, repr=False)
