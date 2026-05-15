"""Layer chunk type: ldta (160-164 bytes).

The optional `matte_layer_id` (AE >= 23) uses `fmt_field(..., optional=True)`
so it reads as `None` from older files and is omitted on write when absent.
"""
from __future__ import annotations

from attrs import define

from .bitfield import BitField
from .chunk import Chunk
from .fmt_field import (
    bool_field,
    bytes_field,
    f8_field,
    s4_field,
    str_field,
    u1_field,
    u2_field,
    u4_field,
)
from .registry import register

# Offset of source_id (u4 big-endian) within a LIST:Layr raw body:
# chunk_type "ldta" (4) + body_size (4) + 40 bytes into ldta body = 48.
_LDTA_SOURCE_ID_OFFSET = 48
_LDTA_SOURCE_ID_END = 52

@register("ldta")
@define
class LdtaChunk(Chunk):
    """Layer descriptor chunk (160-164 bytes).

    Contains layer identity, timing, flags, and type info. The 32-byte
    `layer_name` is a windows-1252 null-terminated string. The optional
    `matte_layer_id` is present only in AE >= 23.
    """

    chunk_type: str = "ldta"

    # -- Identity / timing (bytes 0-35) ------------------------------------
    layer_id: int = u4_field()
    quality: int = u2_field()
    _reserved_06: bytes = bytes_field(2, repr=False)
    stretch_dividend: int = s4_field()
    start_time_dividend: int = s4_field()
    start_time_divisor: int = u4_field(default=1)
    in_point_dividend: int = s4_field()
    in_point_divisor: int = u4_field(default=1)
    out_point_dividend: int = s4_field()
    out_point_divisor: int = u4_field(default=1)

    # -- Flag bytes (bytes 36-39) ------------------------------------------
    _reserved_24: bytes = bytes_field(1, repr=False)
    _layer_flags_0: int = u1_field(repr=False)
    """Byte 37: bits for sampling, env, char-toward-cam, 3d-per-char, etc."""

    _layer_flags_1: int = u1_field(repr=False)
    """Byte 38: bits for null, cam-auto-orient, solo, 3d, adjustment, etc."""

    _layer_flags_2: int = u1_field(repr=False)
    """Byte 39: bits for collapse, shy, locked, frame-blend, motion-blur, etc."""

    # -- Source / label (bytes 40-63) --------------------------------------
    source_id: int = u4_field()
    _reserved_2c: bytes = bytes_field(17, repr=False)
    label: int = u1_field()
    _reserved_3e: bytes = bytes_field(2, repr=False)

    # -- Layer name (bytes 64-95, 32-byte windows-1252 strz) ---------------
    layer_name: str = str_field(32, default="", encoding="windows-1252")
    """32-byte windows-1252 null-terminated string."""

    # -- Post-name fields (bytes 96-159) -----------------------------------
    _reserved_60: bytes = bytes_field(3, repr=False)
    blending_mode: int = u1_field()
    _reserved_64: bytes = bytes_field(3, repr=False)
    preserve_transparency: bool = bool_field()
    _reserved_68: bytes = bytes_field(3, repr=False)
    track_matte_type: int = u1_field()
    stretch_divisor: int = u4_field(default=1)
    _reserved_70: bytes = bytes_field(7, repr=False)
    _ae26_flag: int = u1_field(default=0)
    """Byte 151: AE 26+ boolean flag (zero in earlier versions)."""
    _ae26_float: float = f8_field(default=0.0)
    """Bytes 152-159: AE 26+ float64 value (zero in earlier versions)."""
    _reserved_70b: bytes = bytes_field(3, repr=False)
    layer_type: int = u1_field()
    parent_id: int = u4_field()
    _reserved_88: bytes = bytes_field(3, repr=False)
    light_type: int = u1_field()
    _reserved_8c: bytes = bytes_field(20, repr=False)

    # -- Optional field (bytes 160-163, AE >= 23) --------------------------
    matte_layer_id: int | None = u4_field(default=None, optional=True)
    """Track matte layer ID. `None` = absent (AE < 23), `0` = no matte."""

    # -- BitField descriptors (not attrs fields) ---------------------------
    # byte 37: _layer_flags_0
    sampling_quality = BitField("_layer_flags_0", 6)
    environment_layer = BitField("_layer_flags_0", 5)
    characters_toward_camera = BitField("_layer_flags_0", 4)
    three_d_per_char = BitField("_layer_flags_0", 3)
    frame_blending_mode = BitField("_layer_flags_0", 2)
    guide_layer = BitField("_layer_flags_0", 1)

    # byte 38: _layer_flags_1
    null_layer = BitField("_layer_flags_1", 7)
    camera_or_poi_auto_orient = BitField("_layer_flags_1", 5)
    markers_locked = BitField("_layer_flags_1", 4)
    solo = BitField("_layer_flags_1", 3)
    three_d_layer = BitField("_layer_flags_1", 2)
    adjustment_layer = BitField("_layer_flags_1", 1)
    auto_orient_along_path = BitField("_layer_flags_1", 0)

    # byte 39: _layer_flags_2
    collapse_transformation = BitField("_layer_flags_2", 7)
    shy = BitField("_layer_flags_2", 6)
    locked = BitField("_layer_flags_2", 5)
    frame_blending = BitField("_layer_flags_2", 4)
    motion_blur_flag = BitField("_layer_flags_2", 3)
    effects_active = BitField("_layer_flags_2", 2)
    audio_enabled = BitField("_layer_flags_2", 1)
    enabled = BitField("_layer_flags_2", 0)

    # -- Computed properties -----------------------------------------------

    _TIME_DIVISOR = 10000

    @property
    def start_time(self) -> float:
        """Start time in seconds (dividend / divisor)."""
        return self.start_time_dividend / self.start_time_divisor

    @start_time.setter
    def start_time(self, value: float) -> None:
        self.start_time_dividend = round(value * self._TIME_DIVISOR)
        self.start_time_divisor = self._TIME_DIVISOR

    @property
    def in_point(self) -> float:
        """In point in seconds (dividend / divisor)."""
        return self.in_point_dividend / self.in_point_divisor

    @in_point.setter
    def in_point(self, value: float) -> None:
        self.in_point_dividend = round(value * self._TIME_DIVISOR)
        self.in_point_divisor = self._TIME_DIVISOR

    @property
    def out_point(self) -> float:
        """Out point in seconds (dividend / divisor)."""
        return self.out_point_dividend / self.out_point_divisor

    @out_point.setter
    def out_point(self, value: float) -> None:
        self.out_point_dividend = round(value * self._TIME_DIVISOR)
        self.out_point_divisor = self._TIME_DIVISOR

    @property
    def stretch(self) -> float:
        """Stretch percentage (dividend / divisor * 100). 100 = no stretch."""
        if self.stretch_divisor == 0:
            return 100.0
        return self.stretch_dividend / self.stretch_divisor * 100.0

    @stretch.setter
    def stretch(self, value: float) -> None:
        self.stretch_dividend = round(value * self._TIME_DIVISOR)
        self.stretch_divisor = self._TIME_DIVISOR * 100




