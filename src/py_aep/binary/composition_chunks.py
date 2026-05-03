"""Composition chunk type: cdta (204 bytes).

Uses `fmt_field()` for all fixed-layout fields, `BitField` descriptors
for two flag bytes, and `@property` accessors for computed values
(time scale, frame rate, duration, work area, etc.).
"""
from __future__ import annotations

from attrs import define

from .bitfield import BitField
from .chunk import Chunk
from .fmt_field import bytes_field, s4_field, u1_field, u2_field, u4_field
from .registry import register


@register("cdta")
@define
class CdtaChunk(Chunk):
    """Composition data chunk (204 bytes).

    Holds timing, dimensions, motion blur, and composition flags.
    Computed properties (time_scale, frame_rate, duration, etc.) derive
    from the raw dividend/divisor fields using true division.
    """

    chunk_type: str = "cdta"

    # -- Resolution (bytes 0-3) --------------------------------------------
    resolution_factor_h: int = u2_field(default=1)
    """Horizontal resolution factor."""

    resolution_factor_v: int = u2_field(default=1)
    """Vertical resolution factor."""

    # -- Time scale (bytes 4-7) --------------------------------------------
    _reserved_04: bytes = bytes_field(1, repr=False)
    time_scale_integer: int = u2_field(default=4)
    """Integer part of time scale."""

    time_scale_fractional: int = u1_field()
    """Fractional part (1/256th units). Non-zero for NTSC-style rates."""

    # -- Timebase (bytes 8-19) ---------------------------------------------
    internal_timebase: int = u4_field()
    """frame_rate * 256 * time_scale. E.g. 24576 for 24fps/ts=4."""

    _reserved_0c: bytes = bytes_field(4, repr=False)
    standard_timebase: int = u4_field(default=600)
    """Always 600."""

    # -- Time / work area / duration (bytes 20-51) -------------------------
    time_dividend: int = s4_field()
    time_divisor: int = u4_field()
    work_area_start_dividend: int = u4_field()
    work_area_start_divisor: int = u4_field()
    work_area_end_dividend: int = u4_field()
    work_area_end_divisor: int = u4_field()
    duration_dividend: int = u4_field()
    duration_divisor: int = u4_field()

    # -- Background color (bytes 52-54) ------------------------------------
    bg_color_r: int = u1_field()
    bg_color_g: int = u1_field()
    bg_color_b: int = u1_field()

    # -- Reserved (bytes 55-137, 83 bytes) ---------------------------------
    _reserved_37: bytes = bytes_field(83, repr=False)

    # -- Comp flags (bytes 138-139, 2 flag bytes) --------------------------
    _comp_flags_0: int = u1_field(repr=False)
    """Byte 138: bit 7 = draft3d."""

    _comp_flags_1: int = u1_field(repr=False)
    """Byte 139: composition toggle flags."""

    # -- Dimensions (bytes 140-143) ----------------------------------------
    width: int = u2_field()
    height: int = u2_field()

    # -- Pixel ratio (bytes 144-155) ---------------------------------------
    pixel_ratio_dividend: int = u4_field(default=1)
    pixel_ratio_divisor: int = u4_field(default=1)
    _reserved_98: bytes = bytes_field(4, repr=False)

    # -- Frame rate (bytes 156-163) ----------------------------------------
    frame_rate_integer: int = u2_field()
    frame_rate_fractional: int = u2_field()
    """Fractional part (1/65536th units)."""

    _reserved_a0: bytes = bytes_field(4, repr=False)

    # -- Display start time (bytes 164-171) --------------------------------
    display_start_time_dividend: int = s4_field()
    """Signed. Negative = timeline starts before frame 0."""

    display_start_time_divisor: int = u4_field()

    # -- Shutter (bytes 172-187) -------------------------------------------
    _reserved_ac: bytes = bytes_field(2, repr=False)
    shutter_angle: int = u2_field(default=180)
    _reserved_b0: bytes = bytes_field(4, default=b"\x00\x00\x01\x68", repr=False)
    """Always 360 (0x0168) big-endian."""

    shutter_phase: int = s4_field()
    _reserved_b8: bytes = bytes_field(4, default=b"\x00\x00\x01\x68", repr=False)
    """Always 360 (0x0168) big-endian."""

    # -- Trailing reserved (bytes 188-203) ---------------------------------
    _reserved_bc: bytes = bytes_field(8, repr=False)
    motion_blur_adaptive_sample_limit: int = s4_field(default=128)
    motion_blur_samples_per_frame: int = s4_field(default=16)

    # -- BitField descriptors (not attrs fields) ---------------------------
    draft3d = BitField("_comp_flags_0", 7)
    preserve_nested_resolution = BitField("_comp_flags_1", 7)
    preserve_nested_frame_rate = BitField("_comp_flags_1", 5)
    frame_blending = BitField("_comp_flags_1", 4)
    motion_blur = BitField("_comp_flags_1", 3)
    hide_shy_layers = BitField("_comp_flags_1", 0)

    # -- Computed properties -----------------------------------------------

    @property
    def bg_color(self) -> list[int]:
        """Background color as [R, G, B]."""
        return [self.bg_color_r, self.bg_color_g, self.bg_color_b]

    @bg_color.setter
    def bg_color(self, value: list[int]) -> None:
        self.bg_color_r, self.bg_color_g, self.bg_color_b = (
            value[0], value[1], value[2]
        )

    @property
    def resolution_factor(self) -> list[int]:
        """Resolution factor as [horizontal, vertical]."""
        return [self.resolution_factor_h, self.resolution_factor_v]

    @resolution_factor.setter
    def resolution_factor(self, value: list[int]) -> None:
        self.resolution_factor_h, self.resolution_factor_v = value[0], value[1]

    @property
    def time_scale(self) -> float:
        """Effective time scale (integer + fractional/256)."""
        return self.time_scale_integer + self.time_scale_fractional / 256.0

    @property
    def frame_rate(self) -> float:
        """Composition frame rate (integer + fractional/65536)."""
        return self.frame_rate_integer + self.frame_rate_fractional / 65536.0

    @property
    def display_start_time(self) -> float:
        """Display start time in seconds."""
        return self.display_start_time_dividend / self.display_start_time_divisor

    @property
    def display_start_frame(self) -> float:
        """Display start time in frames."""
        return self.display_start_time * self.frame_rate

    @property
    def duration(self) -> float:
        """Composition duration in seconds."""
        return self.duration_dividend / self.duration_divisor

    @property
    def frame_duration(self) -> float:
        """Composition duration in frames."""
        return self.duration * self.frame_rate

    @property
    def pixel_aspect(self) -> float:
        """Pixel aspect ratio."""
        return self.pixel_ratio_dividend / self.pixel_ratio_divisor

    @property
    def time(self) -> float:
        """Current time in seconds."""
        return self.time_dividend / self.time_divisor

    @property
    def frame_time(self) -> float:
        """Current time in frames."""
        return self.time * self.frame_rate

    @property
    def work_area_start_absolute(self) -> float:
        """Absolute work area start in seconds."""
        return (
            self.display_start_time
            + self.work_area_start_dividend / self.work_area_start_divisor
        )

    @property
    def frame_work_area_start_absolute(self) -> float:
        """Absolute work area start in frames."""
        return self.work_area_start_absolute * self.frame_rate

    @property
    def work_area_end_absolute(self) -> float:
        """Absolute work area end in seconds."""
        if self.work_area_end_dividend == 0xFFFFFFFF:
            return self.display_start_time + self.duration
        return (
            self.display_start_time
            + self.work_area_end_dividend / self.work_area_end_divisor
        )

    @property
    def frame_work_area_end_absolute(self) -> float:
        """Absolute work area end in frames."""
        if self.work_area_end_dividend == 0xFFFFFFFF:
            return self.display_start_frame + self.frame_duration
        return self.work_area_end_absolute * self.frame_rate

    @property
    def work_area_start_relative(self) -> float:
        """Work area start relative to composition start (seconds)."""
        return self.work_area_start_absolute - self.display_start_time

    @property
    def frame_work_area_start_relative(self) -> float:
        """Work area start relative to composition start (frames)."""
        return self.frame_work_area_start_absolute - self.display_start_frame

    @property
    def work_area_duration(self) -> float:
        """Work area duration in seconds."""
        return self.work_area_end_absolute - self.work_area_start_absolute

    @property
    def frame_work_area_duration(self) -> float:
        """Work area duration in frames."""
        return self.frame_work_area_end_absolute - self.frame_work_area_start_absolute
