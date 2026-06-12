"""Footage chunk types: sspc (source settings), opti (asset info).

SspcChunk uses `fmt_field()` for all fixed-layout fields with `BitField`
descriptors for alpha flags.
OptiChunk uses variant subclass dispatch: SoliOptiChunk (fmt_field),
PsdOptiChunk (custom read/write for LE fields), PlaceholderOptiChunk.
"""

from __future__ import annotations

import struct
from fractions import Fraction
from typing import TYPE_CHECKING

from attrs import define

from .bin_utils import read_bytes
from .bitfield import BitField
from .chunk import Chunk
from .fmt_field import (
    ascii_field,
    bool_field,
    bytes_field,
    f4_field,
    f8_field,
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
# sspc - source footage settings (184+ bytes)
# ---------------------------------------------------------------------------


@register("sspc")
@define
class SspcChunk(Chunk):
    """Source footage settings chunk.

    Contains dimensions, timing, alpha/field settings, pixel ratio,
    audio sample rate, and sequence info. A variable-length trailing
    section is preserved for round-trip fidelity.
    """

    chunk_type: str = "sspc"

    # -- Reserved (bytes 0-21) ---------------------------------------------
    _reserved_00: bytes = bytes_field(22, repr=False)

    # -- Source format (bytes 22-31) ---------------------------------------
    source_format_type: str = ascii_field(4)
    """4-char code: 'png!', '8BPS', 'MOoV', 'Soli', etc."""

    _reserved_1a: bytes = bytes_field(6, repr=False)

    # -- Dimensions / duration (bytes 32-45) -------------------------------
    width: int = u2_field()
    _reserved_22: bytes = bytes_field(2, repr=False)
    height: int = u2_field()
    duration_dividend: int = u4_field(default=1)
    duration_divisor: int = u4_field(default=1)

    # -- Frame rate (bytes 46-68) ------------------------------------------
    _reserved_2e: bytes = bytes_field(6, repr=False)
    _time_base: int = u2_field(default=600)
    _reserved_36: bytes = bytes_field(2, repr=False)
    native_frame_rate_integer: int = u4_field()
    native_frame_rate_fractional: int = u2_field()
    _reserved_3e: bytes = bytes_field(7, repr=False)

    # -- Alpha flags (byte 69) ---------------------------------------------
    _alpha_flags: int = u1_field(repr=False)
    """Byte 69: bit 1 = invert_alpha, bit 0 = premultiplied."""

    # -- Premul color / alpha mode (bytes 70-73) ---------------------------
    premul_color_r: int = u1_field()
    premul_color_g: int = u1_field()
    premul_color_b: int = u1_field()
    alpha_mode_raw: int = u1_field()
    """Alpha interpretation mode. 3 = no alpha channel."""

    # -- Field separation (bytes 74-87) ------------------------------------
    _reserved_4a: bytes = bytes_field(9, repr=False)
    field_separation_type_raw: int = u1_field()
    """0 = OFF, 1 = enabled (check field_order for upper/lower)."""

    _reserved_54: bytes = bytes_field(3, repr=False)
    field_order: int = u1_field()

    # -- Reserved / footage state (bytes 88-128) ---------------------------
    _reserved_58: bytes = bytes_field(17, repr=False)
    _is_synthetic_a: int = u1_field(default=1, repr=False)
    _reserved_6b: bytes = bytes_field(3, repr=False)
    _is_synthetic_b: int = u1_field(default=1, repr=False)
    _reserved_6f: bytes = bytes_field(5, repr=False)
    footage_missing_at_save: bool = bool_field()
    """0 = found, 1 = missing or placeholder."""

    _reserved_74: bytes = bytes_field(9, repr=False)
    _depth_flag: int = u1_field(default=0x0C, repr=False)
    _reserved_7e: bytes = bytes_field(3, repr=False)

    # -- Loop / pixel ratio (bytes 129-146) --------------------------------
    loop: int = u1_field(default=1)
    """Loop count (1 = no loop, 2+ = loop count)."""

    _reserved_82: bytes = bytes_field(4, repr=False)
    _is_synthetic_c: int = u1_field(default=1, repr=False)
    _reserved_87: bytes = bytes_field(1, repr=False)
    pixel_aspect_dividend: int = u4_field(default=1)
    pixel_aspect_divisor: int = u4_field(default=1)
    _reserved_90: bytes = bytes_field(3, repr=False)

    # -- Pulldown / conform (bytes 147-158) --------------------------------
    _remove_pulldown_value: int = u1_field(repr=False)

    conform_frame_rate_integer: int = u2_field()
    """0 = no conforming."""

    conform_frame_rate_fractional: int = u2_field()
    display_frame_rate_integer: int = u2_field()
    display_frame_rate_fractional: int = u2_field()
    _reserved_9c: bytes = bytes_field(3, repr=False)
    high_quality_field_separation: int = u1_field()

    # -- Audio / sequence (bytes 160-183) ----------------------------------
    audio_sample_rate: float = f8_field()
    """Sample rate in Hz (0.0 = no audio)."""

    _reserved_a8: bytes = bytes_field(4, repr=False)
    start_frame: int = u4_field()
    end_frame: int = u4_field()
    frame_padding: int = u4_field()
    """Zero-padded digit count for image sequences (0 for non-sequences)."""

    # -- Extended settings (bytes 184-221) ---------------------------------
    _reserved_b8: bytes = bytes_field(4, repr=False)
    work_area_start: int = u4_field(default=0xFFFFFFFF)
    work_area_end: int = u4_field(default=0xFFFFFFFF)
    _reserved_c4: bytes = bytes_field(6, repr=False)
    _reserved_ca: bytes = bytes_field(10, repr=False)
    _reserved_d4: bytes = bytes_field(10, default=b"\x01" + b"\x00" * 9, repr=False)

    # -- BitField descriptors (not attrs fields) ---------------------------
    invert_alpha = BitField("_alpha_flags", 1)
    premultiplied = BitField("_alpha_flags", 0)

    # -- Computed properties -----------------------------------------------

    @property
    def native_frame_rate(self) -> float:
        """Native frame rate (integer + fractional/65536)."""
        return (
            self.native_frame_rate_integer + self.native_frame_rate_fractional / 65536.0
        )

    @native_frame_rate.setter
    def native_frame_rate(self, value: float) -> None:
        self.native_frame_rate_integer = int(value)
        self.native_frame_rate_fractional = round((value - int(value)) * 65536)
        self._update_display_frame_rate()

    @property
    def conform_frame_rate(self) -> float:
        """Conform frame rate (integer + fractional/65536). 0 = no conform."""
        return (
            self.conform_frame_rate_integer
            + self.conform_frame_rate_fractional / 65536.0
        )

    @conform_frame_rate.setter
    def conform_frame_rate(self, value: float) -> None:
        self.conform_frame_rate_integer = int(value)
        self.conform_frame_rate_fractional = round((value - int(value)) * 65536)
        self._update_display_frame_rate()

    @property
    def duration(self) -> float:
        """Duration in seconds (dividend / divisor)."""
        if self.duration_divisor == 0:
            return 0.0
        return self.duration_dividend / self.duration_divisor

    @duration.setter
    def duration(self, value: float) -> None:
        frac = Fraction(value).limit_denominator()
        self.duration_dividend = frac.numerator
        self.duration_divisor = frac.denominator

    @property
    def pixel_aspect(self) -> float:
        """Pixel aspect ratio (dividend / divisor)."""
        if self.pixel_aspect_divisor == 0:
            return 1.0
        return self.pixel_aspect_dividend / self.pixel_aspect_divisor

    @pixel_aspect.setter
    def pixel_aspect(self, value: float) -> None:
        frac = Fraction(value).limit_denominator()
        self.pixel_aspect_dividend = frac.numerator
        self.pixel_aspect_divisor = frac.denominator

    @property
    def premul_color(self) -> list[float]:
        """Premultiply color as [R, G, B] in 0.0-1.0 range."""
        return [
            self.premul_color_r / 255,
            self.premul_color_g / 255,
            self.premul_color_b / 255,
        ]

    @premul_color.setter
    def premul_color(self, value: list[float]) -> None:
        self.premul_color_r = round(value[0] * 255)
        self.premul_color_g = round(value[1] * 255)
        self.premul_color_b = round(value[2] * 255)

    @property
    def field_separation_type(self) -> int:
        """Field separation type (0=off, 1=upper_first, 2=lower_first)."""
        if self.field_separation_type_raw == 0:
            return 0
        return self.field_order + 1

    @field_separation_type.setter
    def field_separation_type(self, value: int) -> None:
        if value == 0:
            self.field_separation_type_raw = 0
            self.field_order = 0
        else:
            self.field_separation_type_raw = 1
            self.field_order = value - 1

    @property
    def has_alpha(self) -> bool:
        """Whether the footage has an alpha component."""
        return self.alpha_mode_raw != 3

    @property
    def remove_pulldown(self) -> int:
        """0 = OFF, 1-10 = pulldown phase."""
        return self._remove_pulldown_value

    @remove_pulldown.setter
    def remove_pulldown(self, value: int) -> None:
        self._remove_pulldown_value = value
        self._update_display_frame_rate()

    @property
    def display_frame_rate(self) -> float:
        """Effective frame rate as displayed."""
        conform = self.conform_frame_rate
        base = conform if conform != 0 else self.native_frame_rate
        return base * (0.8 if self._remove_pulldown_value != 0 else 1.0)

    @display_frame_rate.setter
    def display_frame_rate(self, value: float) -> None:
        self.display_frame_rate_integer = int(value)
        self.display_frame_rate_fractional = round((value - int(value)) * 65536)

    def _update_display_frame_rate(self) -> None:
        """Recompute and store display_frame_rate from current settings."""
        conform = self.conform_frame_rate
        base = conform if conform != 0 else self.native_frame_rate
        self.display_frame_rate = base * (
            0.8 if self._remove_pulldown_value != 0 else 1.0
        )


# ---------------------------------------------------------------------------
# opti - footage asset info (variant dispatch by asset_type)
# ---------------------------------------------------------------------------


def build_generic_opti_data(source_format: str) -> bytes:
    """Build the 58-byte generic `opti` asset-info body for a file source.

    AE accepts an empty `opti` for single still images (it re-reads the
    located file), but requires this header to recognize non-TIFF/PSD
    image sequences and audio/video. The layout is the format 4-char code,
    a version word, the chunk length, the reversed code, and importer
    markers - matching what AE writes for WAV/MOV/etc.

    Note: TIFF sequences use `build_tiff_opti_data` instead (AE 2026
    measured); PSD sequences use an empty opti via `PsdOptiChunk`.
    """
    code = source_format.encode("ascii")[:4].ljust(4, b" ")
    return (
        code
        + b"\x00\x05"
        + b"\x00\x00\x00\x3a"  # 58 = total length
        + b"\x00" * 20
        + code[::-1]
        + b"\xff\xff\xff\xff"
        + b"\x00\x00\x00\x00"  # codec fourcc (unknown / not needed)
        + b"\x01\x00\x00\x00"
        + b"\x01"
        + b"\x00" * 11
    )


def _build_still_opti(
    code: bytes, width: int, height: int, bit_depth: int, tail: bytes
) -> bytes:
    """Build the 602-byte still-importer `opti` body shared by TIFF and PSD.

    Reverse-engineered from AE 2026. `code` is the 4-char format code (also
    embedded reversed mid-header); `tail` is the format-specific trailing
    field. The channel count is always 4 (AE composites the merge to RGBA).
    """
    return (
        code
        + b"\x01\x09"
        + struct.pack(">I", 602)  # total length (big-endian)
        + b"\x00\x00\x01\x01"
        + b"\xff\xff\xff\xff"
        + code[::-1]
        + b"\x01\x00\x00\x00"
        + b"\x00\x00\x00\x00"
        + b"\x04\x00"
        + struct.pack("<I", height)
        + struct.pack("<I", width)
        + struct.pack("<H", bit_depth)
        + b"\x03\x00"
        + b"\x00\x00\x00\x00"
        + tail
    ).ljust(602, b"\x00")


def build_tiff_opti_data(width: int, height: int, bit_depth: int = 8) -> bytes:
    """Build the 602-byte TIFF `opti` asset-info body.

    Unlike PNG/EXR, AE does not re-read a TIFF from the located file, so it
    needs this header for both stills and image sequences (an empty or generic
    header crashes AE in both cases - AE 2026 measured). The header is
    identical for 3- and 4-channel TIFFs.
    """
    return _build_still_opti(b"TIF ", width, height, bit_depth, b"\x02\x00")


def build_psd_opti_data(
    width: int, height: int, bit_depth: int = 8, layer_count: int = 1
) -> bytes:
    """Build the 602-byte merged-PSD/PSB `opti` asset-info body.

    AE 2026 measured: AE itself writes an empty opti for PSD imports (both
    stills and sequences), but it also accepts the 602-byte header produced
    here on re-open without error. This function is used by `PsdOptiChunk`
    via `write()` and for the `file_attributes` round-trip; it stores layer
    metadata (index, dimensions, bit depth, layer count) that AE exposes in
    its "Interpret Footage" dialog. Uses the same still-importer template as
    `build_tiff_opti_data` but with the `8BPS`/`SPB8` codes and the layer
    count in the trailing field.

    Args:
        width: Full PSD canvas width in pixels.
        height: Full PSD canvas height in pixels.
        bit_depth: Bits per channel (8, 16, or 32).
        layer_count: Number of layers in the PSD. A flattened document (0
            layers) is stored as 1, matching AE.
    """
    tail = struct.pack("<B", min(max(layer_count, 1), 255))
    return _build_still_opti(b"8BPS", width, height, bit_depth, tail)


@register("opti")
@define
class OptiChunk(Chunk):
    """Footage asset info chunk (polymorphic).

    Layout depends on `asset_type` (first 4 bytes). The base class
    dispatches to variant subclasses; unknown asset types fall back
    to raw bytes.
    """

    chunk_type: str = "opti"

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        *,
        chunk_type: str = "",
        **kwargs: Any,
    ) -> OptiChunk:
        if cls is not OptiChunk:
            # Variant subclass - use its own read
            return super().read(fp, size, chunk_type=chunk_type)  # type: ignore[return-value]  # returns Self
        if size < 6:
            return cls(chunk_type=chunk_type, data=read_bytes(fp, size))
        # Peek at discriminator (first 4 bytes = asset_type)
        disc_raw = read_bytes(fp, 6)
        nul = disc_raw.find(b"\x00", 0, 4)
        asset_type = disc_raw[: nul if nul >= 0 else 4].decode("ascii")
        asset_type_int = struct.unpack(">H", disc_raw[4:6])[0]
        fp.seek(-6, 1)
        # Placeholder: asset_type is empty but asset_type_int == 2
        if not asset_type and asset_type_int == 2:
            return PlaceholderOptiChunk.read(
                fp,
                size,
                chunk_type=chunk_type,
            )
        variant_cls = _OPTI_VARIANTS.get(asset_type, OptiChunk)
        if variant_cls is OptiChunk:
            return cls(chunk_type=chunk_type, data=read_bytes(fp, size))
        return variant_cls.read(fp, size, chunk_type=chunk_type)


@define
class SoliOptiChunk(OptiChunk):
    """Solid footage asset (asset_type='Soli').

    All fields are big-endian and fixed-layout -> fmt_field.
    """

    asset_type: str = ascii_field(4, default="Soli")
    asset_type_int: int = u2_field(default=9)
    _pad: bytes = bytes_field(
        8, default=b"\x00\x00\x01\x1a\x3f\x80\x00\x00", repr=False
    )
    color_r: float = f4_field()
    """Solid color red component (0.0-1.0)."""

    color_g: float = f4_field()
    """Solid color green component (0.0-1.0)."""

    color_b: float = f4_field()
    """Solid color blue component (0.0-1.0)."""

    solid_name: str = str_field(256, default="", encoding="utf-8")
    """Solid item name."""

    @property
    def color(self) -> list[float]:
        """Solid color as [R, G, B] in 0.0-1.0 range."""
        return [self.color_r, self.color_g, self.color_b]

    @color.setter
    def color(self, value: list[float]) -> None:
        self.color_r = value[0]
        self.color_g = value[1]
        self.color_b = value[2]


@define
class PsdOptiChunk(OptiChunk):
    """PSD footage asset (asset_type='8BPS')."""

    asset_type: str = ascii_field(4, default="8BPS")
    asset_type_int: int = u2_field(default=264)
    _pad_06: bytes = bytes_field(10, repr=False)
    psd_layer_index: int = u2_field()
    """0-based layer index. 0xFFFF = merged/flattened."""

    _pad_12: bytes = bytes_field(
        12, default=b"\x53\x50\x42\x38\x01\x00\x00\x00\x00\x00\x00\x00", repr=False
    )
    psd_channels: int = u1_field()
    """Number of color channels (3=RGB, 4=RGBA/CMYK)."""

    _pad_1f: bytes = bytes_field(1, repr=False)
    psd_canvas_height: int = u2_field(endian="<")
    """Full PSD canvas height in pixels (LE u2)."""

    _pad_22: bytes = bytes_field(2, repr=False)
    psd_canvas_width: int = u2_field(endian="<")
    """Full PSD canvas width in pixels (LE u2)."""

    _pad_26: bytes = bytes_field(2, repr=False)
    psd_bit_depth: int = u1_field()
    """Bit depth per channel (8 or 16)."""

    _pad_29: bytes = bytes_field(7, default=b"\x00\x03\x00\x00\x00\x00\x00", repr=False)
    psd_layer_count: int = u1_field()
    """Total number of layers in the PSD."""

    _pad_31: bytes = bytes_field(29, repr=False)
    psd_layer_top: int = s4_field(endian="<")
    """Layer bounding box top (LE s4, can be negative)."""

    psd_layer_left: int = s4_field(endian="<")
    """Layer bounding box left (LE s4, can be negative)."""

    psd_layer_bottom: int = s4_field(endian="<")
    """Layer bounding box bottom (LE s4)."""

    psd_layer_right: int = s4_field(endian="<")
    """Layer bounding box right (LE s4)."""

    _pad_5e: bytes = bytes_field(250, repr=False)

    @property
    def psd_group_name(self) -> str:
        """PSD group/folder name (NUL-terminated UTF-8 at end of chunk).

        Empty for a merged import, where the trailing region is all-NUL.
        """
        return self._trailing.split(b"\x00", 1)[0].decode("utf-8")

    @psd_group_name.setter
    def psd_group_name(self, value: str) -> None:
        self._trailing = value.encode("utf-8") if value else b""


@define
class PlaceholderOptiChunk(OptiChunk):
    """Placeholder footage asset (asset_type_int=2)."""

    asset_type: str = ascii_field(4, default="")
    asset_type_int: int = u2_field(default=2)
    _pad: bytes = bytes_field(4, default=b"\x00\x00\x01\x0a", repr=False)
    placeholder_name: str = str_field(256, default="", encoding="utf-8")
    """Placeholder name (256-byte NUL-padded UTF-8)."""


_OPTI_VARIANTS: dict[str, type[OptiChunk]] = {
    "Soli": SoliOptiChunk,
    "8BPS": PsdOptiChunk,
}
