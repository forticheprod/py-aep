"""Render queue chunk types: Roou, Ropt, Rout.

RouuChunk exposes output module settings fields as `fmt_field()`.
RoptChunk uses variant subclass dispatch by format_code.
RoutChunk uses `items_field()` for repeating render-flag entries.
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
    """

    chunk_type: str = "Roou"

    _magic: bytes = bytes_field(4, default=b"FXTC", repr=False)
    video_codec: str = ascii_field(4, default="\x00" * 4)
    """Video codec 4-char code."""

    _reserved_08: bytes = bytes_field(8, repr=False)
    starting_number: int = u4_field()
    """Starting frame number for image sequence output."""

    _reserved_14: bytes = bytes_field(
        6, default=b"\xff\xff\xff\xff\x01\x00", repr=False
    )
    format_id: str = ascii_field(4, default="\x00" * 4)
    """Output format 4-char identifier (e.g. '.AVI', 'H264', 'png!')."""

    _reserved_1e: bytes = bytes_field(2, repr=False)
    _reserved_20: bytes = bytes_field(4, repr=False)
    width: int = u2_field()
    """Output width (0 when video disabled)."""

    _reserved_26: bytes = bytes_field(2, repr=False)
    height: int = u2_field()
    """Output height (0 when video disabled)."""

    _reserved_2a: bytes = bytes_field(
        25,
        default=b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00",
        repr=False,
    )
    frame_rate: int = u1_field()
    _reserved_44: bytes = bytes_field(3, repr=False)
    depth: int = u1_field()
    """Color depth: 24=Millions/8bpc, 48=Trillions/16bpc, 96=Floating/32bpc."""

    _reserved_48: bytes = bytes_field(5, default=b"\x01\x01\x00\x00\x00", repr=False)
    color_premultiplied: int = u1_field(default=1)
    _reserved_4e: bytes = bytes_field(3, repr=False)
    color_matted: int = u1_field(default=1)
    _reserved_52: bytes = bytes_field(
        18, default=b"FIEL\x00\x01" + b"\x00" * 12, repr=False
    )
    audio_sample_rate: float = f8_field()
    """Audio sample rate in Hz (e.g. 44100.0, 48000.0)."""

    audio_disabled_hi: int = u1_field()
    """0xFF when audio is disabled."""

    audio_format: int = u1_field()
    """Audio format: 2=16-bit, 3=24-bit, 4=32-bit."""

    _reserved_6e: int = u1_field(repr=False)
    audio_bit_depth: int = u1_field()
    """Audio bit depth: 1=8-bit, 2=16-bit, 4=32-bit."""

    _reserved_70: int = u1_field(repr=False)
    audio_channels: int = u1_field()
    """1=mono, 2=stereo."""

    _trailing: bytes = field(default=b"", repr=False)


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


@define
class CineonRoptChunk(RoptChunk):
    """Cineon/DPX render options (format_code='sDPX')."""

    format_code: str = ascii_field(4, default="sDPX")
    _pad: bytes = bytes_field(10, repr=False)
    ten_bit_black_point: int = u2_field()
    ten_bit_white_point: int = u2_field()
    converted_black_point: float = f8_field()
    converted_white_point: float = f8_field()
    current_gamma: float = f8_field()
    highlight_expansion: int = u2_field()
    logarithmic_conversion: bool = bool_field()
    file_format: int = u1_field()
    bit_depth: int = u1_field()
    _trailing: bytes = field(default=b"", repr=False)


@define
class JpegRoptChunk(RoptChunk):
    """JPEG render options (format_code='JPEG')."""

    format_code: str = ascii_field(4, default="JPEG")
    _pad: bytes = bytes_field(48, repr=False)
    quality: int = u2_field()
    format_type: int = u2_field()
    scans: int = u2_field()
    _trailing: bytes = field(default=b"", repr=False)


@define
class OpenExrRoptChunk(RoptChunk):
    """OpenEXR render options (format_code='oEXR')."""

    format_code: str = ascii_field(4, default="oEXR")
    _pad_04: bytes = bytes_field(10, repr=False)
    compression: int = u1_field()
    thirty_two_bit_float: bool = bool_field()
    luminance_chroma: bool = bool_field()
    _pad_11: bytes = bytes_field(1, repr=False)
    dwa_compression_level: float = f4_field(default=0.0, endian="<")
    _trailing: bytes = field(default=b"", repr=False)


@define
class TargaRoptChunk(RoptChunk):
    """Targa render options (format_code='TPIC')."""

    format_code: str = ascii_field(4, default="TPIC")
    _pad: bytes = bytes_field(73, repr=False)
    bits_per_pixel: int = u1_field()
    _pad2: bytes = bytes_field(4, repr=False)
    rle_compression: bool = bool_field()
    _trailing: bytes = field(default=b"", repr=False)


@define
class TiffRoptChunk(RoptChunk):
    """TIFF render options (format_code='TIF ')."""

    format_code: str = ascii_field(4, default="TIF ")
    _pad: bytes = bytes_field(596, repr=False)
    ibm_pc_byte_order: bool = bool_field()
    lzw_compression: bool = bool_field()
    _trailing: bytes = field(default=b"", repr=False)


@define
class PngRoptChunk(RoptChunk):
    """PNG render options (format_code='png!')."""

    format_code: str = ascii_field(4, default="png!")
    _pad: bytes = bytes_field(14, repr=False)
    width: int = u4_field()
    height: int = u4_field()
    _pad2: bytes = bytes_field(2, repr=False)
    bit_depth: int = u2_field()
    compression: int = u4_field()
    _trailing: bytes = field(default=b"", repr=False)


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
    """

    _flags: int = u1_field(default=0)
    _pad: bytes = bytes_field(3, repr=False)

    render = BitField("_flags", 6)


# ---------------------------------------------------------------------------
# Render settings ldat item (2246 bytes per item)
# ---------------------------------------------------------------------------


@define
class RenderSettingsItem(FmtItem):
    """Per-render-queue-item settings (2246 bytes).

    Stored as ldat items in the LIST:list under LIST:LRdr.
    """

    _reserved_00: bytes = bytes_field(7, repr=False)
    _flag_byte: int = u1_field(repr=False)
    comp_id: int = u4_field()
    status: int = u4_field()
    _reserved_06: bytes = bytes_field(4, repr=False)
    time_span_start_dividend: int = u4_field()
    time_span_start_divisor: int = u4_field()
    time_span_duration_dividend: int = u4_field()
    time_span_duration_divisor: int = u4_field()
    _reserved_11: bytes = bytes_field(8, repr=False)
    frame_rate_integer: int = u2_field()
    frame_rate_fractional: int = u2_field()
    _reserved_14: bytes = bytes_field(2, repr=False)
    field_render: int = u2_field()
    _reserved_16: bytes = bytes_field(2, repr=False)
    pulldown: int = u2_field()
    quality: int = u2_field()
    resolution_x: int = u2_field()
    resolution_y: int = u2_field()
    _reserved_21: bytes = bytes_field(2, repr=False)
    effects: int = u2_field()
    _reserved_23: bytes = bytes_field(2, repr=False)
    proxy_use: int = u2_field()
    _reserved_25: bytes = bytes_field(2, repr=False)
    motion_blur: int = u2_field()
    _reserved_27: bytes = bytes_field(2, repr=False)
    frame_blending: int = u2_field()
    _reserved_29: bytes = bytes_field(2, repr=False)
    log_type: int = u2_field()
    _reserved_31: bytes = bytes_field(2, repr=False)
    skip_existing_files: bool = u2_field(coerce=bool)
    _reserved_33: bytes = bytes_field(4, repr=False)
    template_name: str = str_field(64, default="", encoding="windows-1252")
    _reserved_35: bytes = bytes_field(1990, repr=False)
    use_this_frame_rate: int = u2_field()
    _reserved_37: bytes = bytes_field(2, repr=False)
    time_span_source: int = u2_field()
    _reserved_39: bytes = bytes_field(14, repr=False)
    solo_switches: int = u2_field()
    _reserved_41: bytes = bytes_field(2, repr=False)
    disk_cache: int = u2_field()
    _reserved_43: bytes = bytes_field(2, repr=False)
    guide_layers: int = u2_field()
    _reserved_45: bytes = bytes_field(6, repr=False)
    color_depth: int = u2_field()
    _reserved_47: bytes = bytes_field(16, repr=False)
    start_time: int = u4_field()
    elapsed_seconds: int = u4_field()
    _remaining: bytes = bytes_field(40, repr=False)

    queue_item_notify = BitField("_flag_byte", 2)

    # -- Computed properties -----------------------------------------------

    _TIME_DIVISOR = 10000

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
        divisor = self.time_span_start_divisor or self._TIME_DIVISOR
        self.time_span_start_dividend = round(value * divisor)
        self.time_span_start_divisor = divisor

    @property
    def time_span_duration(self) -> float:
        """Time span duration in seconds (dividend / divisor)."""
        if self.time_span_duration_divisor == 0:
            return 0.0
        return self.time_span_duration_dividend / self.time_span_duration_divisor

    @time_span_duration.setter
    def time_span_duration(self, value: float) -> None:
        divisor = self.time_span_duration_divisor or self._TIME_DIVISOR
        self.time_span_duration_dividend = round(value * divisor)
        self.time_span_duration_divisor = divisor

# ---------------------------------------------------------------------------
# Output module settings ldat item (128 bytes per item)
# ---------------------------------------------------------------------------


@define
class OutputModuleSettingsItem(FmtItem):
    """Per-output-module settings (128 bytes).

    Stored as ldat items in the LIST:list within each render queue item.
    """

    _reserved_00: bytes = bytes_field(7, repr=False)
    _flag_byte_07: int = u1_field(repr=False)
    """Byte 7: bit 7=preserve_rgb, bit 6=include_source_xmp,
    bit 4=use_region_of_interest, bit 3=use_comp_frame_number."""

    post_render_target_comp_id: int = u4_field()
    _reserved_08: bytes = bytes_field(4, repr=False)
    _reserved_09: bytes = bytes_field(3, repr=False)
    channels: int = u1_field()
    _reserved_11: bytes = bytes_field(3, repr=False)
    resize_quality: int = u1_field()
    _reserved_13: bytes = bytes_field(3, repr=False)
    resize: bool = bool_field()
    _reserved_15: bytes = bytes_field(1, repr=False)
    lock_aspect_ratio: bool = bool_field()
    _reserved_17: bytes = bytes_field(1, repr=False)
    _flag_byte_22: int = u1_field(repr=False)
    """Byte 22: bit 0=crop."""

    crop_top: int = u2_field()
    crop_left: int = u2_field()
    crop_bottom: int = u2_field()
    crop_right: int = u2_field()
    _reserved_24: bytes = bytes_field(2, repr=False)
    output_audio: int = u1_field()
    _reserved_26: bytes = bytes_field(4, repr=False)
    include_project_link: bool = bool_field()
    post_render_action: int = u4_field()
    post_render_use_comp: int = u4_field()
    _reserved_30: bytes = bytes_field(16, repr=False)
    output_profile_id: bytes = bytes_field(16)
    _reserved_32: bytes = bytes_field(3, repr=False)
    convert_to_linear_light: int = u1_field()
    _reserved_34: bytes = bytes_field(1, repr=False)
    output_color_space_working: int = u1_field()
    _reserved_36: bytes = bytes_field(34, repr=False)

    preserve_rgb = BitField("_flag_byte_07", 7)
    include_source_xmp = BitField("_flag_byte_07", 6)
    use_region_of_interest = BitField("_flag_byte_07", 4)
    use_comp_frame_number = BitField("_flag_byte_07", 3)
    crop = BitField("_flag_byte_22", 0)


_ROUT_ITEM_SIZE = 4


@register("Rout")
@define
class RoutChunk(Chunk):
    """Render queue item flags chunk.

    4-byte header followed by 4 bytes per item, each with a render
    flag at bit 6 of the first byte.
    """

    chunk_type: str = "Rout"

    header: bytes = bytes_field(4)
    items: list[RoutItem] = items_field(RoutItem, 4)
    _trailing: bytes = field(default=b"", repr=False)
