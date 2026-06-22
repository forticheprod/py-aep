"""Tests for the ICC profile discovery provider."""

from __future__ import annotations

import hashlib

import pytest

from py_aep.data.icc_profiles import (
    ColorProfileNotFoundError,
    IccProfileLibrary,
    default_icc_directories,
    icc_profile_id,
)
from py_aep.enums.mappings import _ICC_PROFILE_MAPPING, profile_id_for_name


class TestProfileIdForName:
    """Name -> 16-byte ID inversion of the catalogue."""

    def test_known_name(self) -> None:
        assert profile_id_for_name("sRGB IEC61966-2.1") == bytes.fromhex(
            "1d3fda2edb4a89ab60a23c5f7c7d81dd"
        )

    def test_unknown_name_returns_none(self) -> None:
        assert profile_id_for_name("Not A Real Profile") is None
        assert profile_id_for_name("ACEScg") is None  # OCIO name, not ICC

    def test_inversion_is_total_and_consistent(self) -> None:
        for uid_hex, name in _ICC_PROFILE_MAPPING.items():
            assert profile_id_for_name(name) == bytes.fromhex(uid_hex)


class TestIccProfileId:
    """The masked-MD5 ID algorithm."""

    def test_masks_flag_intent_and_id_fields(self) -> None:
        data = bytes(range(256))
        expected = bytearray(data)
        expected[44:48] = b"\x00" * 4
        expected[64:68] = b"\x00" * 4
        expected[84:100] = b"\x00" * 16
        assert icc_profile_id(data) == hashlib.md5(bytes(expected)).digest()
        assert len(icc_profile_id(data)) == 16

    def test_rendering_intent_byte_does_not_change_id(self) -> None:
        # Two profiles differing only in the masked rendering-intent region
        # must hash identically (the reason the masking exists).
        a = bytearray(range(256))
        b = bytearray(range(256))
        b[64:68] = b"\xde\xad\xbe\xef"
        assert icc_profile_id(bytes(a)) == icc_profile_id(bytes(b))


class TestLibraryErrors:
    def test_missing_profile_raises_with_context(self) -> None:
        lib = IccProfileLibrary(dirs=[])  # nothing to scan
        with pytest.raises(ColorProfileNotFoundError) as exc:
            lib.bytes_for("ProPhoto RGB")
        assert "ProPhoto RGB" in str(exc.value)
        assert exc.value.profile_name == "ProPhoto RGB"

    def test_hash_for_uses_catalogue_without_disk(self) -> None:
        # Even with no directories, a catalogued name resolves via the mapping.
        lib = IccProfileLibrary(dirs=[])
        assert lib.hash_for("Apple RGB") == bytes.fromhex(
            "47ae2b5f4c143df9d07b5dc78036b5a8"
        )

    def test_hash_for_unknown_raises(self) -> None:
        lib = IccProfileLibrary(dirs=[])
        with pytest.raises(ColorProfileNotFoundError):
            lib.hash_for("Definitely Not Catalogued XYZ")


# Disk discovery depends on an Adobe installation; skip cleanly when absent.
_DISCOVERABLE = any(d.is_dir() for d in default_icc_directories())


@pytest.mark.skipif(not _DISCOVERABLE, reason="Adobe Color dirs not installed")
class TestDiscovery:
    def test_discovered_bytes_hash_to_catalogued_id(self) -> None:
        lib = IccProfileLibrary()
        data = lib.bytes_for("sRGB IEC61966-2.1")
        assert data[36:40] == b"acsp"
        assert icc_profile_id(data) == profile_id_for_name("sRGB IEC61966-2.1")


# The WCS profiles are cached only in the per-user Adobe Color directory, and
# only after After Effects has generated them at runtime.
_WCS_CACHE_DIRS = [
    d for d in default_icc_directories() if d.name == "Profiles" and "Adobe" in d.parts
]
_WCS_PRESENT = any((d / "wsRGB.icc").is_file() for d in _WCS_CACHE_DIRS)


@pytest.mark.skipif(not _WCS_PRESENT, reason="WCS cache not populated by AE")
class TestWcsCacheDiscovery:
    """The per-user Adobe Color cache fills the `* wsRGB`/`* wscRGB` gap."""

    @pytest.mark.parametrize("name", ["* wsRGB", "* wscRGB"])
    def test_wcs_profile_bytes_hash_to_catalogued_id(self, name: str) -> None:
        lib = IccProfileLibrary()
        data = lib.bytes_for(name)
        assert data[36:40] == b"acsp"
        assert icc_profile_id(data) == profile_id_for_name(name)
