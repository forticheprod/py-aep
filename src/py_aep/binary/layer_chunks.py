"""Layer chunk type: ldta (160-164 bytes).

The optional `matte_layer_id` (AE >= 23) uses ``fmt_field(..., optional=True)``
so it reads as ``None`` from older files and is omitted on write when absent.
"""
from __future__ import annotations

from attrs import define

from .bitfield import BitField
from .chunk import Chunk
from .fmt_field import fmt_field
from .registry import register


@register("ldta")
@define
class LdtaChunk(Chunk):
    """Layer descriptor chunk (160-164 bytes).

    Contains layer identity, timing, flags, and type info. The 32-byte
    `layer_name` is a windows-1252 null-terminated string. The optional
    `matte_layer_id` is present only in AE >= 23.
    """

    # -- Identity / timing (bytes 0-35) ------------------------------------
    layer_id: int = fmt_field("I")
    quality: int = fmt_field("H")
    _reserved_06: bytes = fmt_field("2s", default=b"\x00" * 2, repr=False)
    stretch_dividend: int = fmt_field("i")
    start_time_dividend: int = fmt_field("i")
    start_time_divisor: int = fmt_field("I", default=1)
    in_point_dividend: int = fmt_field("i")
    in_point_divisor: int = fmt_field("I", default=1)
    out_point_dividend: int = fmt_field("i")
    out_point_divisor: int = fmt_field("I", default=1)

    # -- Flag bytes (bytes 36-39) ------------------------------------------
    _reserved_24: bytes = fmt_field("1s", default=b"\x00", repr=False)
    _layer_flags_0: int = fmt_field("B", repr=False)
    """Byte 37: bits for sampling, env, char-toward-cam, 3d-per-char, etc."""

    _layer_flags_1: int = fmt_field("B", repr=False)
    """Byte 38: bits for null, cam-auto-orient, solo, 3d, adjustment, etc."""

    _layer_flags_2: int = fmt_field("B", repr=False)
    """Byte 39: bits for collapse, shy, locked, frame-blend, motion-blur, etc."""

    # -- Source / label (bytes 40-63) --------------------------------------
    source_id: int = fmt_field("I")
    _reserved_2c: bytes = fmt_field("17s", default=b"\x00" * 17, repr=False)
    label: int = fmt_field("B")
    _reserved_3e: bytes = fmt_field("2s", default=b"\x00" * 2, repr=False)

    # -- Layer name (bytes 64-95, 32-byte windows-1252 strz) ---------------
    layer_name: str = fmt_field("32s", default="", encoding="windows-1252")
    """32-byte windows-1252 null-terminated string."""

    # -- Post-name fields (bytes 96-159) -----------------------------------
    _reserved_60: bytes = fmt_field("3s", default=b"\x00" * 3, repr=False)
    blending_mode: int = fmt_field("B")
    _reserved_64: bytes = fmt_field("3s", default=b"\x00" * 3, repr=False)
    preserve_transparency: int = fmt_field("B")
    _reserved_68: bytes = fmt_field("3s", default=b"\x00" * 3, repr=False)
    track_matte_type: int = fmt_field("B")
    stretch_divisor: int = fmt_field("I")
    _reserved_70: bytes = fmt_field("19s", default=b"\x00" * 19, repr=False)
    layer_type: int = fmt_field("B")
    parent_id: int = fmt_field("I")
    _reserved_88: bytes = fmt_field("3s", default=b"\x00" * 3, repr=False)
    light_type: int = fmt_field("B")
    _reserved_8c: bytes = fmt_field("20s", default=b"\x00" * 20, repr=False)

    # -- Optional field (bytes 160-163, AE >= 23) --------------------------
    matte_layer_id: int | None = fmt_field("I", default=None, optional=True)
    """Track matte layer ID. ``None`` = absent (AE < 23), ``0`` = no matte."""

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

    @property
    def start_time(self) -> float:
        return self.start_time_dividend / self.start_time_divisor

    @property
    def in_point(self) -> float:
        """In point relative to start_time (seconds, before stretch)."""
        return self.in_point_dividend / self.in_point_divisor

    @property
    def out_point(self) -> float:
        """Out point relative to start_time (seconds, before stretch)."""
        return self.out_point_dividend / self.out_point_divisor

    @property
    def stretch(self) -> float:
        """Time stretch as percentage (100 = normal speed)."""
        if self.stretch_divisor == 0:
            return 0.0
        return self.stretch_dividend * 100.0 / self.stretch_divisor

    @property
    def auto_orient_type(self) -> int:
        """0=none, 1=along_path, 2=camera_or_poi, 3=characters_toward_camera."""
        if self.auto_orient_along_path:
            return 1
        if self.camera_or_poi_auto_orient and self.three_d_layer:
            return 2
        if self.characters_toward_camera and self.three_d_per_char:
            return 3
        return 0

    @property
    def frame_blending_type(self) -> int:
        """0=none, 1=frame_mix, 2=pixel_motion."""
        if not self.frame_blending:
            return 0
        return 2 if self.frame_blending_mode else 1
