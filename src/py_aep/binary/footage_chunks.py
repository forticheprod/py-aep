"""Footage chunk types: sspc (source settings), opti (asset info).

SspcChunk uses `fmt_field()` for all fixed-layout fields with `BitField`
descriptors for alpha flags and `@property` for computed values.
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
from .fmt_field import fmt_field
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

    # -- Reserved (bytes 0-21) ---------------------------------------------
    _reserved_00: bytes = fmt_field("22s", default=b"\x00" * 22, repr=False)

    # -- Source format (bytes 22-31) ---------------------------------------
    source_format_type: bytes = fmt_field("4s", default=b"\x00" * 4)
    """4-char code: 'png!', '8BPS', 'MOoV', 'Soli', etc."""

    _reserved_1a: bytes = fmt_field("6s", default=b"\x00" * 6, repr=False)

    # -- Dimensions / duration (bytes 32-45) -------------------------------
    width: int = fmt_field("H")
    _reserved_22: bytes = fmt_field("2s", default=b"\x00" * 2, repr=False)
    height: int = fmt_field("H")
    duration_dividend: int = fmt_field("I")
    duration_divisor: int = fmt_field("I")

    # -- Frame rate (bytes 46-68) ------------------------------------------
    _reserved_2e: bytes = fmt_field("10s", default=b"\x00" * 10, repr=False)
    native_frame_rate_integer: int = fmt_field("I")
    native_frame_rate_fractional: int = fmt_field("H")
    _reserved_3e: bytes = fmt_field("7s", default=b"\x00" * 7, repr=False)

    # -- Alpha flags (byte 69) ---------------------------------------------
    _alpha_flags: int = fmt_field("B", repr=False)
    """Byte 69: bit 1 = invert_alpha, bit 0 = premultiplied."""

    # -- Premul color / alpha mode (bytes 70-73) ---------------------------
    premul_color_r: int = fmt_field("B")
    premul_color_g: int = fmt_field("B")
    premul_color_b: int = fmt_field("B")
    alpha_mode_raw: int = fmt_field("B")
    """Alpha interpretation mode. 3 = no alpha channel."""

    # -- Field separation (bytes 74-87) ------------------------------------
    _reserved_4a: bytes = fmt_field("9s", default=b"\x00" * 9, repr=False)
    field_separation_type_raw: int = fmt_field("B")
    """0 = OFF, 1 = enabled (check field_order for upper/lower)."""

    _reserved_54: bytes = fmt_field("3s", default=b"\x00" * 3, repr=False)
    field_order: int = fmt_field("B")

    # -- Reserved / footage state (bytes 88-128) ---------------------------
    _reserved_58: bytes = fmt_field("27s", default=b"\x00" * 27, repr=False)
    footage_missing_at_save: int = fmt_field("B")
    """0 = found, 1 = missing or placeholder."""

    _reserved_74: bytes = fmt_field("13s", default=b"\x00" * 13, repr=False)

    # -- Loop / pixel ratio (bytes 129-146) --------------------------------
    loop: int = fmt_field("B")
    """Loop count (1 = no loop, 2+ = loop count)."""

    _reserved_82: bytes = fmt_field("6s", default=b"\x00" * 6, repr=False)
    pixel_ratio_dividend: int = fmt_field("I")
    pixel_ratio_divisor: int = fmt_field("I")
    _reserved_90: bytes = fmt_field("3s", default=b"\x00" * 3, repr=False)

    # -- Pulldown / conform (bytes 147-158) --------------------------------
    remove_pulldown: int = fmt_field("B")
    """0 = OFF, 1-10 = pulldown phase."""

    conform_frame_rate_integer: int = fmt_field("H")
    """0 = no conforming."""

    conform_frame_rate_fractional: int = fmt_field("H")
    _reserved_98: bytes = fmt_field("7s", default=b"\x00" * 7, repr=False)
    high_quality_field_separation: int = fmt_field("B")

    # -- Audio / sequence (bytes 160-183) ----------------------------------
    audio_sample_rate: float = fmt_field("d")
    """Sample rate in Hz (0.0 = no audio)."""

    _reserved_a8: bytes = fmt_field("4s", default=b"\x00" * 4, repr=False)
    start_frame: int = fmt_field("I")
    end_frame: int = fmt_field("I")
    frame_padding: int = fmt_field("I")
    """Zero-padded digit count for image sequences (0 for non-sequences)."""

    # -- Trailing (bytes 184+) ---------------------------------------------
    _trailing: bytes = field(default=b"", repr=False)

    # -- BitField descriptors (not attrs fields) ---------------------------
    invert_alpha = BitField("_alpha_flags", 1)
    premultiplied = BitField("_alpha_flags", 0)

    # -- Computed properties -----------------------------------------------

    @property
    def native_frame_rate(self) -> float:
        return (
            self.native_frame_rate_integer
            + self.native_frame_rate_fractional / 65536.0
        )

    @property
    def pixel_aspect(self) -> float:
        return self.pixel_ratio_dividend / self.pixel_ratio_divisor

    @property
    def has_alpha(self) -> bool:
        return self.alpha_mode_raw != 3

    @property
    def has_audio(self) -> bool:
        return self.audio_sample_rate > 0

    @property
    def field_separation_type(self) -> int:
        """0 = OFF, 1 = UPPER_FIELD_FIRST, 2 = LOWER_FIELD_FIRST."""
        if self.field_separation_type_raw == 0:
            return 0
        return self.field_order + 1

    @property
    def conform_frame_rate(self) -> float:
        """0 = no conforming."""
        return (
            self.conform_frame_rate_integer
            + self.conform_frame_rate_fractional / 65536.0
        )

    @property
    def display_frame_rate(self) -> float:
        """Effective frame rate (accounts for conform and pulldown)."""
        base = (
            self.conform_frame_rate
            if self.conform_frame_rate != 0
            else self.native_frame_rate
        )
        return base * (0.8 if self.remove_pulldown != 0 else 1.0)

    @property
    def source_duration(self) -> float:
        """Raw duration in seconds (before conform/loop)."""
        return self.duration_dividend / self.duration_divisor

    @property
    def duration(self) -> float:
        """Total duration in seconds (with conform and loop)."""
        conform_factor = (
            self.native_frame_rate / self.conform_frame_rate
            if self.conform_frame_rate != 0
            else 1.0
        )
        return self.source_duration * conform_factor * self.loop

    @property
    def frame_duration(self) -> float:
        """Total number of frames."""
        return self.duration * self.display_frame_rate


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
            return super().read(fp, size, chunk_type=chunk_type)  # type: ignore[return-value]
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
        return variant_cls.read(fp, size, chunk_type=chunk_type)  # type: ignore[attr-defined, no-any-return]


@define
class SoliOptiChunk(OptiChunk):
    """Solid footage asset (asset_type='Soli').

    All fields are big-endian and fixed-layout -> fmt_field.
    """

    asset_type: bytes = fmt_field("4s", default=b"Soli")
    asset_type_int: int = fmt_field("H", default=9)
    _pad: bytes = fmt_field("8s", default=b"\x00" * 8, repr=False)
    color_r: float = fmt_field("f")
    """Solid color red component (0.0-1.0)."""

    color_g: float = fmt_field("f")
    """Solid color green component (0.0-1.0)."""

    color_b: float = fmt_field("f")
    """Solid color blue component (0.0-1.0)."""

    solid_name: str = fmt_field("256s", default="", encoding="windows-1252")
    """Solid item name."""

    _trailing: bytes = field(default=b"", repr=False)

    @property
    def color(self) -> list[float]:
        """RGB color as a 3-element list."""
        return [self.color_r, self.color_g, self.color_b]


@define
class PsdOptiChunk(OptiChunk):
    """PSD footage asset (asset_type='8BPS')."""

    asset_type: str = fmt_field("4s", default="", encoding="ascii")
    asset_type_int: int = fmt_field("H")
    _pad_06: bytes = fmt_field("10s", default=b"\x00" * 10, repr=False)
    psd_layer_index: int = fmt_field("H")
    """0-based layer index. 0xFFFF = merged/flattened."""

    _pad_12: bytes = fmt_field("12s", default=b"\x00" * 12, repr=False)
    psd_channels: int = fmt_field("B")
    """Number of color channels (3=RGB, 4=RGBA/CMYK)."""

    _pad_1f: bytes = fmt_field("1s", default=b"\x00", repr=False)
    psd_canvas_height: int = fmt_field("H", endian="<")
    """Full PSD canvas height in pixels (LE u2)."""

    _pad_22: bytes = fmt_field("2s", default=b"\x00" * 2, repr=False)
    psd_canvas_width: int = fmt_field("H", endian="<")
    """Full PSD canvas width in pixels (LE u2)."""

    _pad_26: bytes = fmt_field("2s", default=b"\x00" * 2, repr=False)
    psd_bit_depth: int = fmt_field("B")
    """Bit depth per channel (8 or 16)."""

    _pad_29: bytes = fmt_field("7s", default=b"\x00" * 7, repr=False)
    psd_layer_count: int = fmt_field("B")
    """Total number of layers in the PSD."""

    _pad_31: bytes = fmt_field("29s", default=b"\x00" * 29, repr=False)
    psd_layer_top: int = fmt_field("i", endian="<")
    """Layer bounding box top (LE s4, can be negative)."""

    psd_layer_left: int = fmt_field("i", endian="<")
    """Layer bounding box left (LE s4, can be negative)."""

    psd_layer_bottom: int = fmt_field("i", endian="<")
    """Layer bounding box bottom (LE s4)."""

    psd_layer_right: int = fmt_field("i", endian="<")
    """Layer bounding box right (LE s4)."""

    _pad_5e: bytes = fmt_field("250s", default=b"\x00" * 250, repr=False)
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

    asset_type: str = fmt_field("4s", default="", encoding="ascii")
    asset_type_int: int = fmt_field("H", default=2)
    _pad: bytes = fmt_field("4s", default=b"\x00" * 4, repr=False)
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


_OPTI_VARIANTS: dict[str, type] = {
    "Soli": SoliOptiChunk,
    "8BPS": PsdOptiChunk,
}
