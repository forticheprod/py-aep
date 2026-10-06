"""Item and project-level chunk types: idta, head, nhed, nnhd.

All three use `fmt_field()` for fixed-layout I/O.
HeadChunk packs version info into a 32-bit bitfield word with @property
accessors. NnhdChunk uses `BitField` for scattered flag bits.
"""

from __future__ import annotations

import re

from attrs import define

from .bin_utils import MAC_EPOCH_OFFSET
from .bitfield import BitField
from .chunk import Chunk
from .fmt_field import FmtItem, bool_field, bytes_field, u1_field, u2_field, u4_field
from .registry import register

# ---------------------------------------------------------------------------
# idta - item descriptor (56 bytes + trailing)
# ---------------------------------------------------------------------------


@register("idta")
@define
class IdtaChunk(Chunk):
    """Item descriptor chunk.

    Contains item type, ID, and label. Most of the 84-byte body is
    reserved/unknown and preserved for round-trip fidelity.
    """

    chunk_type: str = "idta"

    item_type: int = u2_field()
    """Item type enum: 1=folder, 4=composition, 7=footage."""

    _reserved_02: bytes = bytes_field(14, repr=False)
    item_id: int = u4_field()
    """Unique item identifier within the project."""

    _flags_14: bytes = bytes_field(2, repr=False)
    _proxy_flags: int = u1_field(repr=False)

    _flags_17: int = u1_field(repr=False)
    _reserved_18: bytes = bytes_field(32, repr=False)
    _proxy_active: int = u1_field(repr=False)
    _reserved_39: bytes = bytes_field(1, repr=False)
    label: int = u1_field()
    """Label color index."""

    _reserved_3c: bytes = bytes_field(21, repr=False)
    _modified_stamp: int = u4_field(repr=False)
    """Bytes 0x50-0x53: big-endian Mac-epoch seconds (see `modified_time`)."""

    # -- BitField descriptors (not attrs fields) ---------------------------
    use_proxy = BitField("_proxy_flags", 0)
    is_solid = BitField("_flags_17", 4)
    is_footage = BitField("_flags_17", 5)

    @property
    def modified_time(self) -> int:
        """Item time stamp, as a Unix timestamp (`0` when unstamped).

        For file footage AE stores the last-modified time of the file in
        use (the proxy's while a file proxy is active); for other items it
        stores the time of the item's last edit.
        """
        stamp = self._modified_stamp
        return stamp - MAC_EPOCH_OFFSET if stamp else 0

    @modified_time.setter
    def modified_time(self, value: int) -> None:
        self._modified_stamp = value + MAC_EPOCH_OFFSET if value else 0


# ---------------------------------------------------------------------------
# idpc - item project context (8 bytes)
# ---------------------------------------------------------------------------


@register("idpc")
@define
class IdpcChunk(Chunk):
    """Item project context chunk (8 bytes)."""

    chunk_type: str = "idpc"
    data: bytes = b"\x00" * 8


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


#: The (file format version, minor) pair After Effects stamps when saving a
#: project for each release. 15 and 23-26 match projects those releases saved
#: (samples/versions); 16-18 and 22 are the pairs AE writes when it saves for
#: them (an early 22.x build saved samples/versions/ae2022 as 93.40). Its keys
#: are the majors py_aep can write a project for (there was no AE 19-21).
FORMAT_VERSIONS: dict[int, tuple[int, int]] = {
    15: (92, 14),
    16: (93, 5),
    17: (93, 22),
    18: (93, 29),
    22: (93, 43),
    23: (94, 9),
    24: (95, 6),
    25: (96, 9),
    26: (97, 2),
}

#: An After Effects version string, `"{major}.{minor}x{build}"`.
AE_VERSION_RE = re.compile(r"^(\d+)\.(\d+)x(\d+)$")


@register("head")
@define
class HeadChunk(Chunk):
    """File header with AE version info.

    The version is packed into a single 32-bit word. Individual fields
    are exposed as @property accessors.
    """

    chunk_type: str = "head"

    # Defaults capture a fresh AE 2026 project (see project_chunks.py).
    _reserved_00a: bytes = bytes_field(1, repr=False)
    file_format_version: int = u1_field(default=0x61)
    """Project file-format version AE checks when opening: it refuses files
    whose value exceeds the running app's own. Equals the AE major version
    plus 71 for AE 2022+ (e.g. 0x61=97 for AE 26)."""
    _reserved_00c: bytes = bytes_field(1, repr=False)
    _format_subversion: int = u1_field(default=0x02, repr=False)
    # Fresh-project default: OS=12 (Windows, bits 25-22), the reserved bit 10
    # AE always sets on save, and bit 9=1 (release, not beta). The version
    # bits (major/minor/build) are stamped by the `version` setter, which
    # preserves these.
    _version_word: int = u4_field(default=(12 << 22) | (1 << 10) | (1 << 9), repr=False)
    _reserved_08: bytes = bytes_field(4, default=b"\x80\x00\x00\x00", repr=False)
    next_item_id: int = u4_field(default=1, repr=False)
    """Next item ID to allocate, always > max existing item ID."""
    file_revision: int = u4_field(default=1)
    """File revision counter (32-bit), incremented on each user action."""

    @property
    def ae_version_major_a(self) -> int:
        return (self._version_word >> 26) & 0x1F

    @ae_version_major_a.setter
    def ae_version_major_a(self, value: int) -> None:
        self._version_word = (self._version_word & ~(0x1F << 26)) | (
            (value & 0x1F) << 26
        )

    @property
    def ae_version_major_b(self) -> int:
        return (self._version_word >> 19) & 0x07

    @ae_version_major_b.setter
    def ae_version_major_b(self, value: int) -> None:
        self._version_word = (self._version_word & ~(0x07 << 19)) | (
            (value & 0x07) << 19
        )

    @property
    def ae_version_minor(self) -> int:
        return (self._version_word >> 15) & 0x0F

    @ae_version_minor.setter
    def ae_version_minor(self, value: int) -> None:
        self._version_word = (self._version_word & ~(0x0F << 15)) | (
            (value & 0x0F) << 15
        )

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
    def ae_version_os(self) -> int:
        """OS code (bits 25-22); 12 for Windows in saved files."""
        return (self._version_word >> 22) & 0x0F

    @ae_version_os.setter
    def ae_version_os(self, value: int) -> None:
        self._version_word = (self._version_word & ~(0x0F << 22)) | (
            (value & 0x0F) << 22
        )

    @property
    def ae_version_major(self) -> int:
        """Full major version (e.g. 25)."""
        return self.ae_version_major_a * 8 + self.ae_version_major_b

    @property
    def version(self) -> str:
        """AE version as `major.minorxbuild` (e.g. '25.6x101')."""
        return f"{self.ae_version_major}.{self.ae_version_minor}x{self.ae_build_number}"

    @version.setter
    def version(self, value: str) -> None:
        m = AE_VERSION_RE.match(value)
        if not m:
            raise ValueError(f"Invalid version format: {value!r}")
        major, minor, build = int(m.group(1)), int(m.group(2)), int(m.group(3))
        self.ae_version_major_a = major // 8
        self.ae_version_major_b = major % 8
        self.ae_version_minor = minor
        self.ae_build_number = build

    def sync_file_format_version(self) -> None:
        """Stamp `file_format_version` (the open-compatibility gate) and its
        minor for the current major version, as After Effects saves for that
        release (`FORMAT_VERSIONS`). AE opens a file whose format version is
        at most its own and reads it with the rules of the (format, minor)
        pair, so a major with no release to take a stamp from is refused: a
        derived pair (AE 2026 measured on `py_aep.new` 12-14 and 19-21) makes
        AE misread every property name or reject the file (`validate_ae_version`
        refuses such a major before it reaches the head chunk)."""
        self.file_format_version, self._format_subversion = FORMAT_VERSIONS[
            self.ae_version_major
        ]


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

    # Defaults capture a fresh AE 2026 project (see project_chunks.py).
    _reserved_00: bytes = bytes_field(8, default=b"\x00" * 7 + b"\x05", repr=False)
    _display_byte: int = u1_field(repr=False)
    footage_timecode_display_start_type: int = u1_field(default=1)
    _reserved_0a: bytes = bytes_field(1, default=b"\x01", repr=False)
    _feet_byte: int = u1_field(repr=False)
    timecode_default_base: int = u1_field(default=30)
    _reserved_0d: bytes = bytes_field(1, default=b"\x10", repr=False)
    frames_count_type: int = u1_field(default=2)
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

    # Defaults capture a fresh AE 2026 project (see project_chunks.py).
    _reserved_00: bytes = bytes_field(2, repr=False)
    _saving_platform: int = u1_field(repr=False)
    """Byte 2: 0x08 when After Effects on macOS saved the project, 0 on
    Windows (AE rewrites it on every save)."""

    _reserved_03: bytes = bytes_field(5, default=b"\x00" * 4 + b"\x05", repr=False)
    _display_byte: int = u1_field(repr=False)
    """Byte 8: bit 7 = feet_frames_film_type, bits 6-0 = time_display_type."""

    footage_timecode_display_start_type: int = u1_field(default=1)
    _reserved_0a: int = u1_field(default=1, repr=False)
    _feet_byte: int = u1_field(repr=False)
    """Byte 11: bit 0 = frames_use_feet_frames."""

    _reserved_0c: bytes = bytes_field(2, repr=False)
    timecode_default_base: int = u2_field(default=30)
    _unknown_10: bytes = bytes_field(4, default=b"\x00\x00\x00\x10", repr=False)
    frames_count_type: int = u1_field(default=2)
    _reserved_15: bytes = bytes_field(3, repr=False)
    bits_per_channel: int = u1_field()
    transparency_grid_thumbnails: bool = bool_field()
    _system_code_page: int = u2_field(repr=False)
    """Bytes 0x1A-0x1B: the saving system's text encoding - Windows code
    page 1252 up to AE 25 and 65001 (UTF-8) from AE 26, 0x0100 on macOS
    (AE rewrites it on every save)."""

    _unknown_1c: bytes = bytes_field(12, repr=False)

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

    @display_start_frame.setter
    def display_start_frame(self, value: int) -> None:
        self.frames_count_type = value


# ---------------------------------------------------------------------------
# Project time-display preference blob (preferences only, not in .aep files)
# ---------------------------------------------------------------------------


@define
class TimeDisplayPrefItem(FmtItem):
    """The "Project Settings Time Display Format" preferences value (16 bytes).

    Mirrors the `nnhd` time-display settings cluster (AE stamps the
    last-used Project Settings into this machine-specific preference and
    new projects inherit it). Field defaults reproduce a factory AE 2026
    preferences file.
    """

    display_byte: int = u1_field()
    """Bit 7 = feet_frames_film_type, bits 6-0 = time_display_type."""

    footage_timecode_display_start_type: int = u1_field(default=1)
    _reserved_02: int = u1_field(default=1, repr=False)
    feet_byte: int = u1_field()
    """Bit 0 = frames_use_feet_frames."""

    timecode_default_base: int = u4_field(default=30, endian="<")
    _reserved_08: int = u4_field(default=16, endian="<", repr=False)
    frames_count_type: int = u4_field(default=2, endian="<")


# ---------------------------------------------------------------------------
# cmta - item comment (variable-length, null-terminated UTF-8)
# ---------------------------------------------------------------------------


@register("cmta")
@define
class CmtaChunk(Chunk):
    """Comment chunk: null-terminated UTF-8, CRLF line endings.

    `data` holds the raw bytes (roundtrip-safe). The `value` property
    decodes to normalised text (LF, no null). Setting `value` encodes
    back with CRLF and a double-null terminator, matching AE's convention.
    """

    chunk_type: str = "cmta"

    @property
    def value(self) -> str:
        """Decoded comment text, LF line endings, no trailing null."""
        return self.data.decode("UTF-8").split("\x00")[0].replace("\r\n", "\n")

    @value.setter
    def value(self, text: str) -> None:
        # AE always writes a double-null terminator inside the chunk data.
        encoded = (text.replace("\n", "\r\n") + "\x00\x00").encode("UTF-8")
        object.__setattr__(self, "data", encoded)
