"""Composition chunk type: cdta (204 bytes).

Uses `fmt_field()` for all fixed-layout fields, `BitField` descriptors
for two flag bytes and sentinel-aware helpers for work-area end
interpretation.
"""

from __future__ import annotations

import math

from attrs import define

from .bin_utils import to_dividend_divisor
from .bitfield import BitField
from .chunk import Chunk
from .fmt_field import FmtItem, bytes_field, s4_field, u1_field, u2_field, u4_field
from .registry import register

# Standard NTSC multipliers: N*1000/1001 gives the NTSC frame rate.
_NTSC_MULTIPLIERS = frozenset({24, 30, 48, 60, 120})


def _is_ntsc(fps: float) -> bool:
    """Return True if fps is a standard NTSC drop-frame rate (N*1000/1001)."""
    n = round(fps * 1001 / 1000)
    if n not in _NTSC_MULTIPLIERS:
        return False
    true_rate = n * 1000 / 1001
    return abs(fps - true_rate) < 0.01


@register("cdta")
@define
class CdtaChunk(Chunk):
    """Composition data chunk (204 bytes).

    Holds timing, dimensions, motion blur, and composition flags.
    Binary fields stay raw except for sentinel-aware work-area end helpers.
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
    internal_timebase: int = u4_field(default=24576)
    """frame_rate * 256 * time_scale. E.g. 24576 for 24fps/ts=4."""

    _reserved_0c: bytes = bytes_field(4, repr=False)
    standard_timebase: int = u4_field(default=600)
    """Always 600."""

    # -- Time / work area / duration (bytes 20-51) -------------------------
    time_dividend: int = s4_field(default=1)
    time_divisor: int = u4_field(default=1)
    work_area_start_dividend: int = u4_field(default=1)
    work_area_start_divisor: int = u4_field(default=1)
    work_area_end_dividend: int = u4_field(default=0xFFFFFFFF)
    work_area_end_divisor: int = u4_field(default=1)
    duration_dividend: int = u4_field(default=1)
    duration_divisor: int = u4_field(default=1)

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
    pixel_aspect_dividend: int = u4_field(default=1)
    pixel_aspect_divisor: int = u4_field(default=1)
    _reserved_98: bytes = bytes_field(4, repr=False)

    # -- Frame rate (bytes 156-163) ----------------------------------------
    frame_rate_integer: int = u2_field()
    frame_rate_fractional: int = u2_field()
    """Fractional part (1/65536th units)."""

    _reserved_a0: bytes = bytes_field(4, repr=False)

    # -- Display start time (bytes 164-171) --------------------------------
    display_start_time_dividend: int = s4_field(default=1)
    """Signed. Negative = timeline starts before frame 0."""

    display_start_time_divisor: int = u4_field(default=1)

    # -- Shutter (bytes 172-187) -------------------------------------------
    _reserved_ac: bytes = bytes_field(2, repr=False)
    shutter_angle: int = u2_field(default=180)
    _reserved_b0: int = u4_field(default=360, repr=False)
    """Always 360 (0x0168) big-endian."""

    shutter_phase: int = s4_field()
    _reserved_b8: int = u4_field(default=360, repr=False)
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

    # -- Assembled properties ----------------------------------------------
    # Combine raw integer+fractional or dividend/divisor pairs into floats.
    # Used by model ChunkField descriptors for direct read/write.

    @property
    def frame_rate(self) -> float:
        """Frame rate assembled from integer + fractional/65536."""
        return self.frame_rate_integer + self.frame_rate_fractional / 65536.0

    @frame_rate.setter
    def frame_rate(self, value: float) -> None:
        self.frame_rate_integer = int(value)
        self.frame_rate_fractional = round((value - int(value)) * 65536)
        self._update_timebase(value)

    @property
    def time_scale(self) -> float:
        """Time scale assembled from integer + fractional/256."""
        return self.time_scale_integer + self.time_scale_fractional / 256.0

    @time_scale.setter
    def time_scale(self, value: float) -> None:
        self.time_scale_integer = int(value)
        self.time_scale_fractional = round((value - int(value)) * 256)

    def _update_timebase(self, fps: float) -> None:
        """Recalculate internal_timebase and time_scale for a new frame rate.

        NTSC rates (multiples of 24000/1001) use a fixed timebase of 23976.
        All other rates use the largest power-of-2 time_scale such that
        fps * time_scale * 256 <= 36864.
        """
        if _is_ntsc(fps):
            self.internal_timebase = 23976
            self.time_scale = 23976 / (fps * 256)
        else:
            time_scale = 2.0 ** math.floor(math.log2(144 / fps))
            self.internal_timebase = round(fps * time_scale * 256)
            self.time_scale = time_scale

    @property
    def pixel_aspect(self) -> float:
        """Pixel aspect ratio from dividend/divisor."""
        return self.pixel_aspect_dividend / self.pixel_aspect_divisor

    @pixel_aspect.setter
    def pixel_aspect(self, value: float) -> None:
        self.pixel_aspect_dividend, self.pixel_aspect_divisor = to_dividend_divisor(
            value
        )

    @property
    def duration(self) -> float:
        """Duration in seconds from dividend/divisor."""
        return self.duration_dividend / self.duration_divisor

    @duration.setter
    def duration(self, value: float) -> None:
        self.duration_dividend, self.duration_divisor = to_dividend_divisor(value)

    @property
    def display_start_time(self) -> float:
        """Display start time in seconds from dividend/divisor."""
        return self.display_start_time_dividend / self.display_start_time_divisor

    @display_start_time.setter
    def display_start_time(self, value: float) -> None:
        self.display_start_time_dividend, self.display_start_time_divisor = (
            to_dividend_divisor(value)
        )

    @property
    def work_area_start(self) -> float:
        """Work area start in seconds from dividend/divisor."""
        return self.work_area_start_dividend / self.work_area_start_divisor

    @work_area_start.setter
    def work_area_start(self, value: float) -> None:
        self.work_area_start_dividend, self.work_area_start_divisor = (
            to_dividend_divisor(value)
        )

    @property
    def time_seconds(self) -> float:
        """Current time in seconds from dividend/divisor."""
        return self.time_dividend / self.time_divisor

    @time_seconds.setter
    def time_seconds(self, value: float) -> None:
        self.time_dividend, self.time_divisor = to_dividend_divisor(value)

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
            return (self.display_start_time + self.duration) * self.frame_rate
        return self.work_area_end_absolute * self.frame_rate

    @property
    def bg_color(self) -> list[float]:
        """Background color as [R, G, B] in 0.0-1.0 range."""
        return [self.bg_color_r / 255, self.bg_color_g / 255, self.bg_color_b / 255]

    @bg_color.setter
    def bg_color(self, value: list[float]) -> None:
        self.bg_color_r = round(value[0] * 255)
        self.bg_color_g = round(value[1] * 255)
        self.bg_color_b = round(value[2] * 255)

    @property
    def resolution_factor(self) -> list[int]:
        """Resolution factor as [horizontal, vertical]."""
        return [self.resolution_factor_h, self.resolution_factor_v]

    @resolution_factor.setter
    def resolution_factor(self, value: list[int]) -> None:
        self.resolution_factor_h = value[0]
        self.resolution_factor_v = value[1]

    @property
    def frame_duration(self) -> int:
        """Duration in frames."""
        return int(self.duration * self.frame_rate)

    @frame_duration.setter
    def frame_duration(self, value: int) -> None:
        self.duration = value / self.frame_rate

    @property
    def display_start_frame(self) -> int:
        """Display start time in frames."""
        return int(self.display_start_time * self.frame_rate)

    @display_start_frame.setter
    def display_start_frame(self, value: int) -> None:
        self.display_start_time = value / self.frame_rate

    @property
    def work_area_start_frame(self) -> int:
        """Work area start in frames."""
        return int(self.work_area_start * self.frame_rate)

    @work_area_start_frame.setter
    def work_area_start_frame(self, value: int) -> None:
        self.work_area_start = value / self.frame_rate

    @property
    def work_area_duration(self) -> float:
        """Work area duration in seconds."""
        if self.work_area_end_dividend == 0xFFFFFFFF:
            return self.duration - self.work_area_start
        return (
            self.work_area_end_dividend / self.work_area_end_divisor
            - self.work_area_start
        )

    @work_area_duration.setter
    def work_area_duration(self, value: float) -> None:
        self.work_area_end_dividend, self.work_area_end_divisor = to_dividend_divisor(
            self.work_area_start + value
        )

    @property
    def work_area_duration_frame(self) -> int:
        """Work area duration in frames."""
        return int(self.work_area_duration * self.frame_rate)

    @work_area_duration_frame.setter
    def work_area_duration_frame(self, value: int) -> None:
        duration_seconds = value / self.frame_rate
        self.work_area_end_dividend, self.work_area_end_divisor = to_dividend_divisor(
            self.work_area_start + duration_seconds
        )

    @property
    def frame_time(self) -> int:
        """Current time in frames."""
        return int(self.time_seconds * self.frame_rate)

    @frame_time.setter
    def frame_time(self, value: int) -> None:
        self.time_seconds = value / self.frame_rate


# ---------------------------------------------------------------------------
# CsCt - CpS2 entry count
# ---------------------------------------------------------------------------


@register("CsCt")
@define
class CsctChunk(Chunk):
    """CpS2 entry count chunk."""

    chunk_type: str = "CsCt"
    value: int = u4_field(default=0x01000000)


# ---------------------------------------------------------------------------
# Composition preset entry (preferences only, not stored in .aep files)
# ---------------------------------------------------------------------------


@define
class CompPresetItem(FmtItem):
    """One "Composition Presets Section v11" preferences entry (16 bytes).

    Format/frame-rate/pixel-aspect of a New Composition preset; the
    display name lives in the adjacent preset-names section. Frame rate
    and pixel aspect use the same encodings as `CdtaChunk`.
    """

    width: int = u2_field()
    height: int = u2_field()
    frame_rate_integer: int = u2_field()
    frame_rate_fractional: int = u2_field()
    """Fractional part (1/65536th units)."""

    pixel_aspect_dividend: int = u4_field(default=1)
    pixel_aspect_divisor: int = u4_field(default=1)

    @property
    def frame_rate(self) -> float:
        """Frame rate assembled from integer + fractional/65536."""
        return self.frame_rate_integer + self.frame_rate_fractional / 65536.0

    @property
    def pixel_aspect(self) -> float:
        """Pixel aspect ratio assembled from dividend/divisor."""
        return self.pixel_aspect_dividend / self.pixel_aspect_divisor
