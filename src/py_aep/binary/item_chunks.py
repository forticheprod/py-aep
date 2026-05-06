"""Item and project-level chunk types: idta, head, nhed, nnhd.

All three use `fmt_field()` for fixed-layout I/O.
HeadChunk packs version info into a 32-bit bitfield word with @property
accessors. NnhdChunk uses `BitField` for scattered flag bits.
"""
from __future__ import annotations

from attrs import define, field

from .bitfield import BitField
from .chunk import Chunk
from .fmt_field import bool_field, bytes_field, u1_field, u2_field, u4_field
from .registry import register

# ---------------------------------------------------------------------------
# idta - item descriptor (56 bytes + trailing)
# ---------------------------------------------------------------------------


@register("idta")
@define
class IdtaChunk(Chunk):
    """Item descriptor chunk.

    Contains item type, ID, and label. Most of the 56-byte body is
    reserved/unknown and preserved for round-trip fidelity.
    """

    chunk_type: str = "idta"

    item_type: int = u2_field()
    """Item type enum: 1=folder, 4=composition, 7=footage."""

    _reserved_02: bytes = bytes_field(14, repr=False)
    item_id: int = u4_field()
    """Unique item identifier within the project."""

    _flags_14: bytes = bytes_field(4, repr=False)
    _reserved_18: bytes = bytes_field(34, repr=False)
    label: int = u1_field()
    """Label color index."""

    _trailing: bytes = field(default=b"", repr=False)


# ---------------------------------------------------------------------------
# head - file header / version (28 bytes)
# ---------------------------------------------------------------------------
#
# Version bitfield layout (32 bits, MSB first):
#   bit  31      : reserved
#   bits 30-26   : ae_version_major_a  (5 bits)
#   bits 25-22   : ae_version_os       (4 bits)
#   bits 21-19   : ae_version_major_b  (3 bits)
#   bits 18-15   : ae_version_minor    (4 bits)
#   bits 14-11   : ae_version_patch    (4 bits)
#   bit  10      : reserved
#   bit   9      : ae_version_beta_flag (0=beta, 1=release)
#   bit   8      : reserved
#   bits  7-0    : ae_build_number     (8 bits)


@register("head")
@define
class HeadChunk(Chunk):
    """File header with AE version info.

    The version is packed into a single 32-bit word. Individual fields
    are exposed as @property accessors.
    """

    chunk_type: str = "head"

    _reserved_00: bytes = bytes_field(4, repr=False)
    _version_word: int = u4_field(repr=False)
    _reserved_08: bytes = bytes_field(10, repr=False)
    file_revision: int = u2_field()
    """File revision counter, incremented on each save."""

    @property
    def ae_version_major_a(self) -> int:
        return (self._version_word >> 26) & 0x1F

    @ae_version_major_a.setter
    def ae_version_major_a(self, value: int) -> None:
        self._version_word = (self._version_word & ~(0x1F << 26)) | ((value & 0x1F) << 26)

    @property
    def ae_version_major_b(self) -> int:
        return (self._version_word >> 19) & 0x07

    @ae_version_major_b.setter
    def ae_version_major_b(self, value: int) -> None:
        self._version_word = (self._version_word & ~(0x07 << 19)) | ((value & 0x07) << 19)

    @property
    def ae_version_minor(self) -> int:
        return (self._version_word >> 15) & 0x0F

    @ae_version_minor.setter
    def ae_version_minor(self, value: int) -> None:
        self._version_word = (self._version_word & ~(0x0F << 15)) | ((value & 0x0F) << 15)

    @property
    def ae_version_beta_flag(self) -> bool:
        """Raw flag: False=beta, True=release."""
        return bool((self._version_word >> 9) & 1)

    @ae_version_beta_flag.setter
    def ae_version_beta_flag(self, value: bool | int) -> None:
        if value:
            self._version_word |= 1 << 9
        else:
            self._version_word &= ~(1 << 9)

    @property
    def ae_build_number(self) -> int:
        return self._version_word & 0xFF

    @ae_build_number.setter
    def ae_build_number(self, value: int) -> None:
        self._version_word = (self._version_word & ~0xFF) | (value & 0xFF)

    @property
    def ae_version_major(self) -> int:
        """Full major version (e.g. 25)."""
        return self.ae_version_major_a * 8 + self.ae_version_major_b

# ---------------------------------------------------------------------------
# nhed - compact project settings mirror (32 bytes)
# ---------------------------------------------------------------------------


@register("nhed")
@define
class NhedChunk(Chunk):
    """Compact root-level mirror for selected project settings.

    Sample comparisons show that several `nnhd` display settings are
    mirrored here at more compact offsets. Some bytes still have
    unknown semantics and are preserved exactly.
    """

    chunk_type: str = "nhed"

    _reserved_00: bytes = bytes_field(8, repr=False)
    _display_byte: int = u1_field(repr=False)
    footage_timecode_display_start_type: int = u1_field()
    _reserved_0a: bytes = bytes_field(1, repr=False)
    _feet_byte: int = u1_field(repr=False)
    timecode_default_base: int = u1_field()
    _reserved_0d: bytes = bytes_field(1, repr=False)
    frames_count_type: int = u1_field()
    bits_per_channel: int = u1_field()
    transparency_grid_thumbnails: bool = bool_field()
    _reserved_11: bytes = bytes_field(15, repr=False)

    feet_frames_film_type = BitField("_display_byte", 7)
    frames_use_feet_frames = BitField("_feet_byte", 0)

    @property
    def time_display_type(self) -> int:
        """Time display type (0=TIMECODE, 1=FRAMES)."""
        return self._display_byte & 0x7F

    @time_display_type.setter
    def time_display_type(self, value: int) -> None:
        self._display_byte = (self._display_byte & 0x80) | (value & 0x7F)

    @property
    def display_start_frame(self) -> int:
        return self.frames_count_type % 2

    @display_start_frame.setter
    def display_start_frame(self, value: int) -> None:
        self.frames_count_type = value


# ---------------------------------------------------------------------------
# nnhd - project display settings (40 bytes)
# ---------------------------------------------------------------------------


@register("nnhd")
@define
class NnhdChunk(Chunk):
    """Project display settings.

    Contains time display format, frame count settings, color depth,
    and various toggle flags.
    """

    chunk_type: str = "nnhd"

    _reserved_00: bytes = bytes_field(8, repr=False)
    _display_byte: int = u1_field(repr=False)
    """Byte 8: bit 7 = feet_frames_film_type, bits 6-0 = time_display_type."""

    footage_timecode_display_start_type: int = u1_field(default=1)
    _reserved_0a: int = u1_field(repr=False)
    _feet_byte: int = u1_field(repr=False)
    """Byte 11: bit 0 = frames_use_feet_frames."""

    _reserved_0c: bytes = bytes_field(2, repr=False)
    timecode_default_base: int = u2_field()
    _unknown_10: bytes = bytes_field(4, default=b"\x00\x00\x00\x10", repr=False)
    frames_count_type: int = u1_field()
    _reserved_15: bytes = bytes_field(3, repr=False)
    bits_per_channel: int = u1_field()
    transparency_grid_thumbnails: bool = bool_field()
    _unknown_1a: bytes = bytes_field(14, repr=False)

    # -- Bit-level accessors (not attrs fields) ----------------------------
    feet_frames_film_type = BitField("_display_byte", 7)
    frames_use_feet_frames = BitField("_feet_byte", 0)

    @property
    def time_display_type(self) -> int:
        """Time display type (0=TIMECODE, 1=FRAMES)."""
        return self._display_byte & 0x7F

    @time_display_type.setter
    def time_display_type(self, value: int) -> None:
        self._display_byte = (self._display_byte & 0x80) | (value & 0x7F)

    @property
    def display_start_frame(self) -> int:
        return self.frames_count_type % 2
