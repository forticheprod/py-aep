"""Discover installed Adobe ICC profiles for writing Adobe-CMS color spaces.

Writing an Adobe-CMS working/display color space requires embedding the full
ICC profile bytes; writing a footage/output color space requires only the
16-byte ICC Profile ID (masked-MD5). This module resolves a color-space *name*
to either, discovering profiles at write time from the standard Adobe Color
directories (or caller-supplied dirs).

Profiles are NOT bundled - the camera/film/log profiles are vendor/Adobe
proprietary. They are discovered from the user's installation (present whenever
After Effects is). See the `color-management-write-rev-eng` notes.

The ID algorithm (`icc_profile_id`) and `desc` extraction
(`icc_profile_description`) are the ISO 15076-1 routines also used by
`scripts/dev/generate_color_space_mapping.py`, which imports them from here.
"""

from __future__ import annotations

import hashlib
import os
import platform
from pathlib import Path
from typing import TYPE_CHECKING

from ..enums.mappings import profile_id_for_name

if TYPE_CHECKING:
    from typing import Iterable


def icc_profile_id(data: bytes) -> bytes:
    """Compute the 16-byte ICC Profile ID per ISO 15076-1 7.2.18.

    The MD5 of the profile with the profile-flags (44-47), rendering-intent
    (64-67) and profile-ID (84-99) fields zeroed. This is the value After
    Effects stores in footage `apid` and output `output_profile_id`.

    Args:
        data: Raw ICC profile bytes.

    Returns:
        The 16-byte digest.
    """
    buf = bytearray(data)
    buf[44:48] = b"\x00" * 4
    buf[64:68] = b"\x00" * 4
    buf[84:100] = b"\x00" * 16
    return hashlib.md5(bytes(buf)).digest()


def icc_profile_description(data: bytes) -> str | None:
    """Extract the `desc` tag text from an ICC profile.

    Supports both the ICCv2 `textDescriptionType` and ICCv4
    `multiLocalizedUnicodeType` tag formats.

    Args:
        data: Raw ICC profile bytes.

    Returns:
        The profile description string, or `None` if not found.
    """
    if len(data) < 132:
        return None
    tag_count = int.from_bytes(data[128:132], "big")
    offset = 132
    for _ in range(tag_count):
        if offset + 12 > len(data):
            return None
        sig = data[offset : offset + 4]
        tag_offset = int.from_bytes(data[offset + 4 : offset + 8], "big")
        if sig == b"desc":
            if tag_offset + 12 > len(data):
                return None
            type_sig = data[tag_offset : tag_offset + 4]
            if type_sig == b"desc":
                # ICCv2 textDescriptionType
                str_len = int.from_bytes(data[tag_offset + 8 : tag_offset + 12], "big")
                end = min(tag_offset + 12 + str_len, len(data))
                raw = data[tag_offset + 12 : end]
                return raw.rstrip(b"\x00").decode("ascii", errors="replace")
            if type_sig == b"mluc":
                # ICCv4 multiLocalizedUnicodeType
                if tag_offset + 16 > len(data):
                    return None
                rec_count = int.from_bytes(
                    data[tag_offset + 8 : tag_offset + 12], "big"
                )
                if rec_count == 0:
                    return None
                rec_off = tag_offset + 16
                s_len = int.from_bytes(data[rec_off + 4 : rec_off + 8], "big")
                s_offset = int.from_bytes(data[rec_off + 8 : rec_off + 12], "big")
                abs_off = tag_offset + s_offset
                end = min(abs_off + s_len, len(data))
                return (
                    data[abs_off:end]
                    .decode("utf-16-be", errors="replace")
                    .rstrip("\x00")
                )
        offset += 12
    return None


def default_icc_directories() -> list[Path]:
    """Return the platform's standard ICC profile directories.

    The canonical Adobe "Media Production" set comes first (`MPProfiles`, then
    `Profiles` and `Profiles/Recommended`); it supplies the working/display
    catalog and wins on name collisions because the index keeps the first
    match. The per-user Adobe Color cache and the OS color-profile store follow
    as fallbacks: the cache holds the Windows Color System profiles
    (`* wsRGB`, `* wscRGB`) that After Effects generates at runtime and caches
    nowhere else on disk.
    """
    if platform.system() == "Windows":
        base = Path(r"C:\Program Files (x86)\Common Files\Adobe\Color")
        dirs = [
            base / "MPProfiles",
            base / "Profiles",
            base / "Profiles" / "Recommended",
        ]
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            dirs.append(Path(local_appdata) / "Adobe" / "Color" / "Profiles")
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        dirs.append(Path(system_root) / "System32" / "spool" / "drivers" / "color")
        return dirs
    # macOS
    base = Path("/Library/Application Support/Adobe/Color")
    home = Path.home()
    return [
        base / "MPProfiles",
        base / "Profiles",
        base / "Profiles" / "Recommended",
        home / "Library" / "Application Support" / "Adobe" / "Color" / "Profiles",
        home / "Library" / "ColorSync" / "Profiles",
        Path("/Library/ColorSync/Profiles"),
        Path("/System/Library/ColorSync/Profiles"),
    ]


class ColorProfileNotFoundError(LookupError):
    """Raised when a named ICC profile cannot be found on disk."""

    def __init__(self, name: str, searched: Iterable[Path]) -> None:
        dirs = "\n  ".join(str(d) for d in searched)
        super().__init__(
            f"ICC profile {name!r} was not found. Writing an Adobe-CMS "
            "working/display color space needs the profile's ICC file, which is "
            "discovered from the installed Adobe Color directories (present "
            "wherever After Effects is installed). Searched:\n  "
            f"{dirs}\n"
            "Pass icc_profile_dirs to point at a folder of .icc files, or use "
            "OCIO color management (which needs no ICC files). Note: 'e-sRGB' "
            "is generated by the Adobe Color Engine at runtime and has no ICC "
            "file."
        )
        self.profile_name = name


class IccProfileLibrary:
    """A lazily-scanned index of installed ICC profiles, keyed by description.

    Resolves a color-space *name* to its raw ICC bytes (`bytes_for`, for
    embedding a working/display space) or its 16-byte profile ID (`hash_for`,
    for a footage/output color space).
    """

    def __init__(self, dirs: list[Path] | None = None) -> None:
        """
        Args:
            dirs: Directories to scan for `.icc`/`.icm` files. When `None`, the
                platform's standard Adobe Color directories are used.
        """
        self._dirs = dirs if dirs is not None else default_icc_directories()
        self._by_name: dict[str, Path] | None = None

    def _index(self) -> dict[str, Path]:
        # Indexing reads each file once to extract its description, but keeps
        # only the path: the OS color store commonly holds hundreds of
        # profiles, and the library singleton lives for the whole process.
        if self._by_name is None:
            by_name: dict[str, Path] = {}
            for directory in self._dirs:
                if not directory.is_dir():
                    continue
                for f in sorted(directory.iterdir()):
                    if f.suffix.lower() not in (".icc", ".icm"):
                        continue
                    try:
                        data = f.read_bytes()
                    except OSError:
                        continue
                    if len(data) < 132 or data[36:40] != b"acsp":
                        continue
                    desc = icc_profile_description(data)
                    # First directory wins (MPProfiles is the canonical set).
                    if desc and desc not in by_name:
                        by_name[desc] = f
            self._by_name = by_name
        return self._by_name

    def bytes_for(self, name: str) -> bytes:
        """Return the raw ICC bytes for a profile name.

        Raises:
            ColorProfileNotFoundError: If no profile with that description is
                found in the searched directories.
        """
        path = self._index().get(name)
        if path is None:
            raise ColorProfileNotFoundError(name, self._dirs)
        return path.read_bytes()

    def hash_for(self, name: str) -> bytes:
        """Return the 16-byte ICC Profile ID for a profile name.

        Prefers the catalogued ID (no disk access needed); falls back to hashing
        a discovered ICC file.

        Raises:
            ColorProfileNotFoundError: If the name is neither catalogued nor
                found on disk.
        """
        known = profile_id_for_name(name)
        if known is not None:
            return known
        path = self._index().get(name)
        if path is None:
            raise ColorProfileNotFoundError(name, self._dirs)
        return icc_profile_id(path.read_bytes())


_default_library: IccProfileLibrary | None = None


def default_icc_library() -> IccProfileLibrary:
    """Return a shared `IccProfileLibrary` over the standard Adobe Color dirs.

    Used where no per-project `icc_profile_dirs` override is available (e.g.
    footage sources). Scanned once and cached for the process.
    """
    global _default_library
    if _default_library is None:
        _default_library = IccProfileLibrary()
    return _default_library
