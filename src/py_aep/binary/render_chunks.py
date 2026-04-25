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
from .fmt_field import FmtItem, fmt_field, items_field
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

    _magic: bytes = fmt_field("4s", default=b"FXTC", repr=False)
    video_codec: bytes = fmt_field("4s", default=b"\x00" * 4)
    """Video codec 4-char code."""

    _reserved_08: bytes = fmt_field("8s", default=b"\x00" * 8, repr=False)
    starting_number: int = fmt_field("I")
    """Starting frame number for image sequence output."""

    _reserved_14: bytes = fmt_field("6s", default=b"\x00" * 6, repr=False)
    format_id: bytes = fmt_field("4s", default=b"\x00" * 4)
    """Output format 4-char identifier (e.g. '.AVI', 'H264', 'png!')."""

    _reserved_1e: bytes = fmt_field("2s", default=b"\x00" * 2, repr=False)
    _reserved_20: bytes = fmt_field("4s", default=b"\x00" * 4, repr=False)
    width: int = fmt_field("H")
    """Output width (0 when video disabled)."""

    _reserved_26: bytes = fmt_field("2s", default=b"\x00" * 2, repr=False)
    height: int = fmt_field("H")
    """Output height (0 when video disabled)."""

    _reserved_2a: bytes = fmt_field("25s", default=b"\x00" * 25, repr=False)
    frame_rate: int = fmt_field("B")
    _reserved_44: bytes = fmt_field("3s", default=b"\x00" * 3, repr=False)
    depth: int = fmt_field("B")
    """Color depth: 24=Millions/8bpc, 48=Trillions/16bpc, 96=Floating/32bpc."""

    _reserved_48: bytes = fmt_field("5s", default=b"\x00" * 5, repr=False)
    color_premultiplied: int = fmt_field("B")
    _reserved_4e: bytes = fmt_field("3s", default=b"\x00" * 3, repr=False)
    color_matted: int = fmt_field("B")
    _reserved_52: bytes = fmt_field("18s", default=b"\x00" * 18, repr=False)
    audio_sample_rate: float = fmt_field("d")
    """Audio sample rate in Hz (e.g. 44100.0, 48000.0)."""

    audio_disabled_hi: int = fmt_field("B")
    """0xFF when audio is disabled."""

    audio_format: int = fmt_field("B")
    """Audio format: 2=16-bit, 3=24-bit, 4=32-bit."""

    _reserved_6e: int = fmt_field("B", repr=False)
    audio_bit_depth: int = fmt_field("B")
    """Audio bit depth: 1=8-bit, 2=16-bit, 4=32-bit."""

    _reserved_70: int = fmt_field("B", repr=False)
    audio_channels: int = fmt_field("B")
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
            return super().read(fp, size, chunk_type=chunk_type)  # type: ignore[return-value]
        if size < 4:
            return cls(chunk_type=chunk_type, data=read_bytes(fp, size))
        # Peek at discriminator (first 4 bytes = format_code)
        disc_raw = read_bytes(fp, 4)
        format_code = disc_raw.decode("ascii")
        fp.seek(-4, 1)
        variant_cls = _ROPT_VARIANTS.get(format_code, RoptChunk)
        if variant_cls is RoptChunk:
            return cls(chunk_type=chunk_type, data=read_bytes(fp, size))
        return variant_cls.read(fp, size, chunk_type=chunk_type)  # type: ignore[attr-defined, no-any-return]


@define
class CineonRoptChunk(RoptChunk):
    """Cineon/DPX render options (format_code='sDPX')."""

    format_code: bytes = fmt_field("4s", default=b"sDPX")
    _pad: bytes = fmt_field("10s", default=b"\x00" * 10, repr=False)
    ten_bit_black_point: int = fmt_field("H")
    ten_bit_white_point: int = fmt_field("H")
    converted_black_point: float = fmt_field("d")
    converted_white_point: float = fmt_field("d")
    current_gamma: float = fmt_field("d")
    highlight_expansion: int = fmt_field("H")
    logarithmic_conversion: int = fmt_field("B")
    file_format: int = fmt_field("B")
    bit_depth: int = fmt_field("B")
    _trailing: bytes = field(default=b"", repr=False)


@define
class JpegRoptChunk(RoptChunk):
    """JPEG render options (format_code='JPEG')."""

    format_code: bytes = fmt_field("4s", default=b"JPEG")
    _pad: bytes = fmt_field("48s", default=b"\x00" * 48, repr=False)
    quality: int = fmt_field("H")
    format_type: int = fmt_field("H")
    scans: int = fmt_field("H")
    _trailing: bytes = field(default=b"", repr=False)


@define
class OpenExrRoptChunk(RoptChunk):
    """OpenEXR render options (format_code='oEXR')."""

    format_code: str = fmt_field("4s", default="oEXR", encoding="ascii")
    _pad_04: bytes = fmt_field("10s", default=b"\x00" * 10, repr=False)
    compression: int = fmt_field("B")
    thirty_two_bit_float: int = fmt_field("B")
    luminance_chroma: int = fmt_field("B")
    _pad_11: bytes = fmt_field("1s", default=b"\x00", repr=False)
    dwa_compression_level: float = fmt_field("f", default=0.0, endian="<")
    _trailing: bytes = field(default=b"", repr=False)


@define
class TargaRoptChunk(RoptChunk):
    """Targa render options (format_code='TPIC')."""

    format_code: bytes = fmt_field("4s", default=b"TPIC")
    _pad: bytes = fmt_field("73s", default=b"\x00" * 73, repr=False)
    bits_per_pixel: int = fmt_field("B")
    _pad2: bytes = fmt_field("4s", default=b"\x00" * 4, repr=False)
    rle_compression: int = fmt_field("B")
    _trailing: bytes = field(default=b"", repr=False)


@define
class TiffRoptChunk(RoptChunk):
    """TIFF render options (format_code='TIF ')."""

    format_code: bytes = fmt_field("4s", default=b"TIF ")
    _pad: bytes = fmt_field("596s", default=b"\x00" * 596, repr=False)
    ibm_pc_byte_order: int = fmt_field("B")
    lzw_compression: int = fmt_field("B")
    _trailing: bytes = field(default=b"", repr=False)


@define
class PngRoptChunk(RoptChunk):
    """PNG render options (format_code='png!')."""

    format_code: bytes = fmt_field("4s", default=b"png!")
    _pad: bytes = fmt_field("14s", default=b"\x00" * 14, repr=False)
    width: int = fmt_field("I")
    height: int = fmt_field("I")
    _pad2: bytes = fmt_field("2s", default=b"\x00" * 2, repr=False)
    bit_depth: int = fmt_field("H")
    compression: int = fmt_field("I")
    _trailing: bytes = field(default=b"", repr=False)


_ROPT_VARIANTS: dict[str, type] = {
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

    _flags: int = fmt_field("B", default=0)
    _pad: bytes = fmt_field("3s", default=b"\x00" * 3, repr=False)

    render = BitField("_flags", 6)


_ROUT_ITEM_SIZE = 4


@register("Rout")
@define
class RoutChunk(Chunk):
    """Render queue item flags chunk.

    4-byte header followed by 4 bytes per item, each with a render
    flag at bit 6 of the first byte.
    """

    header: bytes = fmt_field("4s", default=b"\x00" * 4)
    items: list[RoutItem] = items_field(RoutItem, 4)
    _trailing: bytes = field(default=b"", repr=False)
