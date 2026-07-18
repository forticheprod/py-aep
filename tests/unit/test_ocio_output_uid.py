"""The OCIO output-color-space UID = MurmurHash3-128 of a color-profile envelope.

Reverse-engineered from AE's `dvamediatypes.dll` / `dvacore.dll` (see the
`color-management-write-rev-eng` notes). Every expected id below is the value
After Effects itself stored in the matching sample under
`samples/unused/output_module/output_color_space_ocio/` (AE ground truth).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep.color.murmur3 import DVA_SEED, murmurhash3_x64_128
from py_aep.color.ocio import (
    ocio_color_space_for_profile_id,
    ocio_output_profile_id,
)

CONFIG = Path(__file__).parent.parent.parent / (
    "samples/models/output_module/output_color_space_ocio/sergb.ocio"
)


def test_murmurhash3_empty_is_zero() -> None:
    # Standard MurmurHash3_x64_128 of an empty input with seed 0 is all zeros.
    assert murmurhash3_x64_128(b"", 0) == b"\x00" * 16


def test_dva_seed() -> None:
    assert DVA_SEED == 0xC29DE5B8264CD69E


@pytest.mark.parametrize(
    ("color_space", "expected"),
    [
        # direct color space (family "ACES")
        ("ACEScg yo", "cd772629527fa64b21927794e61262e1"),
        # display color space (family "Display")
        ("sRGB yo", "0c6d240a9d763d2280efa009c82bc004"),
        # utility color space
        ("Linear Rec.709 yo", "97fa2ab73be1a7374957664d0f908212"),
        # role resolving to an alias (why 8 aliases -> 8 distinct ids)
        ("color_picking", "9be73db21a1cd0aa789806cda2cc211c"),
        # role resolving to a display color space
        ("cie_xyz_d65_interchange", "e20c1e9c43eb3902e8e0bb2df1208fbb"),
        # display + view pair
        ("sRGB yo/Un-tone-mapped yo", "57046209b3a07b687fa241e6f4bae3b4"),
    ],
)
def test_ocio_output_profile_id_matches_ae(color_space: str, expected: str) -> None:
    assert ocio_output_profile_id(CONFIG, color_space).hex() == expected


def test_ocio_output_profile_id_unknown_raises() -> None:
    with pytest.raises(ValueError, match="not a color space"):
        ocio_output_profile_id(CONFIG, "Not A Color Space In This Config")


def test_reverse_map_round_trips() -> None:
    for color_space in ("ACEScg yo", "sRGB yo", "sRGB yo/Un-tone-mapped yo"):
        profile_id = ocio_output_profile_id(CONFIG, color_space)
        assert ocio_color_space_for_profile_id(CONFIG, profile_id) == color_space


def test_reverse_map_unknown_id_is_none() -> None:
    assert ocio_color_space_for_profile_id(CONFIG, b"\x00" * 16) is None
