"""Byte-exact tests for the color-profile envelope format.

Verbatim envelope strings captured from AE 2026 samples (the build functions
must reproduce them byte-for-byte for round-trip fidelity):
- working space: samples/models/property/gradient_animated.aep
- display space: samples/models/project/display_color_space_ACES_sRGB.aep
"""

from __future__ import annotations

from py_aep.color.envelope import (
    PROFILE_TYPE_ICC,
    PROFILE_TYPE_OCIO,
    build_icc_envelope,
    build_ocio_colorspace_envelope,
    build_ocio_display_envelope,
    parse_envelope,
)

# Verbatim AE output.
WORKING_ACESCG = (
    '{"baseColorProfile":{"colorProfileData":'
    '"eyJjb2xvclNwYWNlMSI6IkFDRVNjZyIsIm9jaW9Db2xvclNwYWNlVHlwZSI6Mn0=",'
    '"colorProfileName":"ACEScg"},"baseProfileType":3}'
)
DISPLAY_ACES_SRGB = (
    '{"baseColorProfile":{"colorProfileData":'
    '"eyJjb2xvclNwYWNlMSI6IkFDRVMiLCJjb2xvclNwYWNlMiI6InNSR0IiLCJvY2lvQ29sb3JTcGFjZVR5cGUiOjF9",'
    '"colorProfileName":"ACES/sRGB"},"baseProfileType":3}'
)


class TestByteExact:
    """The builders must reproduce AE's bytes exactly."""

    def test_ocio_working_space(self) -> None:
        assert build_ocio_colorspace_envelope("ACEScg") == WORKING_ACESCG

    def test_ocio_display_space(self) -> None:
        assert build_ocio_display_envelope("ACES", "sRGB") == DISPLAY_ACES_SRGB

    def test_display_name_is_display_slash_view(self) -> None:
        prof = parse_envelope(build_ocio_display_envelope("sRGB - Display", "Raw"))
        assert prof.name == "sRGB - Display/Raw"


class TestRoundTrip:
    """build -> parse -> build is stable for every variant."""

    def test_ocio_colorspace_round_trip(self) -> None:
        env = build_ocio_colorspace_envelope("ACEScg")
        prof = parse_envelope(env)
        assert prof.name == "ACEScg"
        assert prof.profile_type == PROFILE_TYPE_OCIO
        assert prof.is_ocio
        assert prof.ocio_color_spaces == ("ACEScg",)
        assert build_ocio_colorspace_envelope(prof.name) == env

    def test_ocio_display_round_trip(self) -> None:
        env = build_ocio_display_envelope("ACES", "sRGB")
        prof = parse_envelope(env)
        assert prof.name == "ACES/sRGB"
        assert prof.ocio_color_spaces == ("ACES", "sRGB")
        display, view = prof.ocio_color_spaces
        assert build_ocio_display_envelope(display, view) == env

    def test_icc_round_trip(self) -> None:
        icc = b"\x00\x00\x02(fake-icc-payload" + bytes(range(40))
        env = build_icc_envelope("ProPhoto RGB", icc)
        prof = parse_envelope(env)
        assert prof.name == "ProPhoto RGB"
        assert prof.profile_type == PROFILE_TYPE_ICC
        assert prof.is_icc
        assert not prof.is_ocio
        assert prof.data == icc
        assert prof.ocio_color_spaces == ()


class TestKeyOrderAndSeparators:
    """Pin the exact key order and compact separators (no whitespace)."""

    def test_icc_envelope_structure(self) -> None:
        # base64("AA==") == b"\x00"; checks outer key order + compact separators.
        env = build_icc_envelope("X", b"\x00")
        assert env == (
            '{"baseColorProfile":{"colorProfileData":"AA==",'
            '"colorProfileName":"X"},"baseProfileType":2}'
        )

    def test_no_whitespace_in_inner_json(self) -> None:
        env = build_ocio_colorspace_envelope("ACEScg")
        assert ", " not in env and ": " not in env

    def test_special_characters_in_name(self) -> None:
        # Names with spaces/parens/slashes must survive both layers intact.
        name = "sRGB Encoded Rec.709 (sRGB)"
        prof = parse_envelope(build_ocio_colorspace_envelope(name))
        assert prof.name == name
        assert prof.ocio_color_spaces == (name,)
