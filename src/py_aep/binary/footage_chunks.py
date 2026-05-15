"""Footage chunk types: sspc (source settings), opti (asset info).

SspcChunk uses `fmt_field()` for all fixed-layout fields with `BitField`
descriptors for alpha flags.
OptiChunk uses variant subclass dispatch: SoliOptiChunk (fmt_field),
PsdOptiChunk (custom read/write for LE fields), PlaceholderOptiChunk.
"""
from __future__ import annotations

import struct
from typing import TYPE_CHECKING

from attrs import define, field

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
    duration_dividend: int = u4_field()
    duration_divisor: int = u4_field(default=1)

    # -- Frame rate (bytes 46-68) ------------------------------------------
    _reserved_2e: bytes = bytes_field(10, repr=False)
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
    _reserved_58: bytes = bytes_field(27, repr=False)
    footage_missing_at_save: bool = bool_field()
    """0 = found, 1 = missing or placeholder."""

    _reserved_74: bytes = bytes_field(13, repr=False)

    # -- Loop / pixel ratio (bytes 129-146) --------------------------------
    loop: int = u1_field(default=1)
    """Loop count (1 = no loop, 2+ = loop count)."""

    _reserved_82: bytes = bytes_field(6, repr=False)
    pixel_ratio_dividend: int = u4_field(default=1)
    pixel_ratio_divisor: int = u4_field(default=1)
    _reserved_90: bytes = bytes_field(3, repr=False)

    # -- Pulldown / conform (bytes 147-158) --------------------------------
    remove_pulldown: int = u1_field()
    """0 = OFF, 1-10 = pulldown phase."""

    conform_frame_rate_integer: int = u2_field()
    """0 = no conforming."""

    conform_frame_rate_fractional: int = u2_field()
    _reserved_98: bytes = bytes_field(7, repr=False)
    high_quality_field_separation: int = u1_field()

    # -- Audio / sequence (bytes 160-183) ----------------------------------
    audio_sample_rate: float = f8_field()
    """Sample rate in Hz (0.0 = no audio)."""

    _reserved_a8: bytes = bytes_field(4, repr=False)
    start_frame: int = u4_field()
    end_frame: int = u4_field()
    frame_padding: int = u4_field()
    """Zero-padded digit count for image sequences (0 for non-sequences)."""

    # -- Trailing (bytes 184+) ---------------------------------------------
    _trailing: bytes = field(default=b"", repr=False)

    # -- BitField descriptors (not attrs fields) ---------------------------
    invert_alpha = BitField("_alpha_flags", 1)
    premultiplied = BitField("_alpha_flags", 0)

    # -- Computed properties -----------------------------------------------

    _TIME_DIVISOR = 10000
    _PIXEL_DIVISOR = 100000

    @property
    def native_frame_rate(self) -> float:
        """Native frame rate (integer + fractional/65536)."""
        return (
            self.native_frame_rate_integer
            + self.native_frame_rate_fractional / 65536.0
        )

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

    @property
    def duration(self) -> float:
        """Duration in seconds (dividend / divisor)."""
        if self.duration_divisor == 0:
            return 0.0
        return self.duration_dividend / self.duration_divisor

    @property
    def pixel_aspect(self) -> float:
        """Pixel aspect ratio (dividend / divisor)."""
        if self.pixel_ratio_divisor == 0:
            return 1.0
        return self.pixel_ratio_dividend / self.pixel_ratio_divisor

# ---------------------------------------------------------------------------
# opti - footage asset info (variant dispatch by asset_type)
# ---------------------------------------------------------------------------


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
        asset_type = disc_raw[:nul if nul >= 0 else 4].decode("ascii")
        asset_type_int = struct.unpack(">H", disc_raw[4:6])[0]
        fp.seek(-6, 1)
        # Placeholder: asset_type is empty but asset_type_int == 2
        if not asset_type and asset_type_int == 2:
            return PlaceholderOptiChunk.read(
                fp, size, chunk_type=chunk_type,
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
    _pad: bytes = bytes_field(8, default=b"\x00\x00\x01\x1a\x3f\x80\x00\x00", repr=False)
    color_r: float = f4_field()
    """Solid color red component (0.0-1.0)."""

    color_g: float = f4_field()
    """Solid color green component (0.0-1.0)."""

    color_b: float = f4_field()
    """Solid color blue component (0.0-1.0)."""

    solid_name: str = str_field(256, default="", encoding="windows-1252")
    """Solid item name."""

    _trailing: bytes = field(default=b"", repr=False)

@define
class PsdOptiChunk(OptiChunk):
    """PSD footage asset (asset_type='8BPS')."""

    asset_type: str = ascii_field(4, default="8BPS")
    asset_type_int: int = u2_field(default=264)
    _pad_06: bytes = bytes_field(10, repr=False)
    psd_layer_index: int = u2_field()
    """0-based layer index. 0xFFFF = merged/flattened."""

    _pad_12: bytes = bytes_field(12, default=b"\x53\x50\x42\x38\x01\x00\x00\x00\x00\x00\x00\x00", repr=False)
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
    _trailing: bytes = field(default=b"", repr=False)

    @property
    def psd_group_name(self) -> str:
        """PSD group/folder name (variable-length UTF-8 at end of chunk)."""
        return self._trailing.decode("utf-8") if self._trailing else ""

    @psd_group_name.setter
    def psd_group_name(self, value: str) -> None:
        self._trailing = value.encode("utf-8") if value else b""


@define
class PlaceholderOptiChunk(OptiChunk):
    """Placeholder footage asset (asset_type_int=2)."""

    asset_type: str = ascii_field(4, default="")
    asset_type_int: int = u2_field(default=2)
    _pad: bytes = bytes_field(4, default=b"\x00\x00\x01\x0a", repr=False)
    _trailing: bytes = field(default=b"", repr=False)

    @property
    def placeholder_name(self) -> str:
        """Placeholder name (variable-length windows-1252 in trailing bytes)."""
        if not self._trailing:
            return ""
        nul = self._trailing.find(b"\x00")
        if nul >= 0:
            return self._trailing[:nul].decode("windows-1252")
        return self._trailing.decode("windows-1252")

    @placeholder_name.setter
    def placeholder_name(self, value: str) -> None:
        # Preserve any bytes after the NUL-terminated name
        old_nul = self._trailing.find(b"\x00")
        suffix = self._trailing[old_nul:] if old_nul >= 0 else b"\x00"
        self._trailing = value.encode("windows-1252") + suffix


_OPTI_VARIANTS: dict[str, type[OptiChunk]] = {
    "Soli": SoliOptiChunk,
    "8BPS": PsdOptiChunk,
}
