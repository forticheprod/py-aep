"""Item and project-level chunk types: idta, head, nnhd.

All three use `fmt_field()` for fixed-layout I/O.
HeadChunk packs version info into a 32-bit bitfield word with @property
accessors. NnhdChunk uses `BitField` for scattered flag bits.
"""
from __future__ import annotations

from attrs import define, field

from .bitfield import BitField
from .chunk import Chunk
from .fmt_field import fmt_field
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

    item_type: int = fmt_field("H")
    """Item type enum: 1=folder, 4=composition, 7=footage."""

    _reserved_02: bytes = fmt_field("14s", default=b"\x00" * 14, repr=False)
    item_id: int = fmt_field("I")
    """Unique item identifier within the project."""

    _flags_14: bytes = fmt_field("4s", default=b"\x00" * 4, repr=False)
    _reserved_18: bytes = fmt_field("34s", default=b"\x00" * 34, repr=False)
    label: int = fmt_field("B")
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

    _reserved_00: bytes = fmt_field("4s", default=b"\x00" * 4, repr=False)
    _version_word: int = fmt_field("I", repr=False)
    _reserved_08: bytes = fmt_field("10s", default=b"\x00" * 10, repr=False)
    file_revision: int = fmt_field("H")
    """File revision counter, incremented on each save."""

    @property
    def ae_version_major_a(self) -> int:
        return (self._version_word >> 26) & 0x1F

    @property
    def ae_version_os(self) -> int:
        """OS code: 12=Windows, 13=Mac, 14=Mac ARM64."""
        return (self._version_word >> 22) & 0x0F

    @property
    def ae_version_major_b(self) -> int:
        return (self._version_word >> 19) & 0x07

    @property
    def ae_version_minor(self) -> int:
        return (self._version_word >> 15) & 0x0F

    @property
    def ae_version_patch(self) -> int:
        return (self._version_word >> 11) & 0x0F

    @property
    def ae_version_beta_flag(self) -> bool:
        """Raw flag: False=beta, True=release."""
        return bool((self._version_word >> 9) & 1)

    @property
    def ae_build_number(self) -> int:
        return self._version_word & 0xFF

    @property
    def ae_version_major(self) -> int:
        """Full major version (e.g. 25)."""
        return self.ae_version_major_a * 8 + self.ae_version_major_b

    @property
    def ae_version_beta(self) -> bool:
        """True if this is a beta version."""
        return not self.ae_version_beta_flag


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

    _reserved_00: bytes = fmt_field("8s", default=b"\x00" * 8, repr=False)
    _display_byte: int = fmt_field("B", repr=False)
    """Byte 8: bit 7 = feet_frames_film_type, bits 6-0 = time_display_type."""

    footage_timecode_display_start_type: int = fmt_field("B")
    _reserved_0a: int = fmt_field("B", repr=False)
    _feet_byte: int = fmt_field("B", repr=False)
    """Byte 11: bit 0 = frames_use_feet_frames."""

    _reserved_0c: bytes = fmt_field("2s", default=b"\x00" * 2, repr=False)
    timecode_default_base: int = fmt_field("H")
    _unknown_10: bytes = fmt_field("4s", default=b"\x00" * 4, repr=False)
    frames_count_type: int = fmt_field("B")
    _reserved_15: bytes = fmt_field("3s", default=b"\x00" * 3, repr=False)
    bits_per_channel: int = fmt_field("B")
    transparency_grid_thumbnails: int = fmt_field("B")
    _unknown_1a: bytes = fmt_field("5s", default=b"\x00" * 5, repr=False)
    _linearize_byte: int = fmt_field("B", repr=False)
    """Byte 31: bit 5 = linearize_working_space."""

    _unknown_20: bytes = fmt_field("8s", default=b"\x00" * 8, repr=False)

    # -- Bit-level accessors (not attrs fields) ----------------------------
    feet_frames_film_type = BitField("_display_byte", 7)
    frames_use_feet_frames = BitField("_feet_byte", 0)
    linearize_working_space = BitField("_linearize_byte", 5)

    @property
    def time_display_type(self) -> int:
        """Time display type (0=TIMECODE, 1=FRAMES)."""
        return self._display_byte & 0x7F

    @property
    def display_start_frame(self) -> int:
        return self.frames_count_type % 2
