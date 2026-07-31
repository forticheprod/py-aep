"""Tests for the prda renderer-option chunk variants."""

from __future__ import annotations

from io import BytesIO

import pytest

from py_aep.binary.misc_chunks import (
    AdvancedPrdaChunk,
    Cinema4DPrdaChunk,
    ClassicPrdaChunk,
    PrdaChunk,
    RayTracedPrdaChunk,
)

PRDA_CLASSIC_DEFAULT = bytes.fromhex("000000010000000000000000")
PRDA_ADVANCED_DEFAULT = bytes.fromhex(
    # big-endian head: version, renderer tag, quality 8, two reserved words
    "0000000100000003000000080000000100000000"
    # little-endian tail: resolution 1, smoothness 3, size 1.0 x3, centre 0.0 x3
    "01000000030000000000803f0000803f0000803f000000000000000000000000")
PRDA_CINEMA_DEFAULT = bytes.fromhex("0000000100000001000000190000000100000000")
PRDA_RAYTRACED = bytes.fromhex("00000001000000000000000300000001") # obsolete renderer, removed in AE 2020 (17.0)

PRDA_CLASSIC_SET = bytes.fromhex("000000010000000000000003")
PRDA_ADVANCED_SET = bytes.fromhex(
    "00000001000000030000003d0000000100000000"
    "02000000060000000000a03e0000a03e0000a03e565595be408e633d555555bd")
PRDA_CINEMA_SET = bytes.fromhex("00000001000000010000002c0000000100000000")

class TestPrdaVariants:
    @pytest.mark.parametrize(
        ("body", "expected_cls"),
        [
            (PRDA_CLASSIC_DEFAULT, ClassicPrdaChunk),
            (PRDA_RAYTRACED, RayTracedPrdaChunk),
            (PRDA_CINEMA_DEFAULT, Cinema4DPrdaChunk),
            (PRDA_ADVANCED_DEFAULT, AdvancedPrdaChunk),
        ],
    )
    def test_dispatch_by_size(self, body: bytes, expected_cls: type) -> None:
        assert type(PrdaChunk.frombytes(body, chunk_type="prda")) is expected_cls

    @pytest.mark.parametrize(
        "body",
        [
            PRDA_CLASSIC_DEFAULT,
            PRDA_CLASSIC_SET,
            PRDA_RAYTRACED,
            PRDA_CINEMA_DEFAULT,
            PRDA_CINEMA_SET,
            PRDA_ADVANCED_DEFAULT,
            PRDA_ADVANCED_SET,
        ],
    )
    def test_roundtrip_byte_exact(self, body: bytes) -> None:
        chunk = PrdaChunk.frombytes(body, chunk_type="prda")
        buf = BytesIO()
        chunk.write(buf)
        assert buf.getvalue() == body

    def test_classic_shadow_map_resolution(self) -> None:
        chunk = PrdaChunk.frombytes(PRDA_CLASSIC_SET, chunk_type="prda")
        assert chunk.shadow_map_resolution == 3

    def test_cinema_quality(self) -> None:
        chunk = PrdaChunk.frombytes(PRDA_CINEMA_SET, chunk_type="prda")
        assert chunk.quality == 44

    def test_advanced_fields_mixed_endian(self) -> None:
        """Head is big-endian, the tail from offset 20 little-endian."""
        chunk = PrdaChunk.frombytes(PRDA_ADVANCED_SET, chunk_type="prda")
        assert chunk.quality == 61
        assert chunk.resolution == 2
        assert chunk.smoothness == 6
        assert chunk.casting_box_size_x == pytest.approx(0.3125)
        assert chunk.casting_box_size_y == pytest.approx(0.3125)
        assert chunk.casting_box_size_z == pytest.approx(0.3125)
        assert chunk.casting_box_center_x == pytest.approx(-0.2916667)
        assert chunk.casting_box_center_y == pytest.approx(0.0555556)
        assert chunk.casting_box_center_z == pytest.approx(-0.0520833)

    @pytest.mark.parametrize(
        ("cls", "expected"),
        [
            (ClassicPrdaChunk, PRDA_CLASSIC_DEFAULT),
            (RayTracedPrdaChunk, PRDA_RAYTRACED),
            (Cinema4DPrdaChunk, PRDA_CINEMA_DEFAULT),
            (AdvancedPrdaChunk, PRDA_ADVANCED_DEFAULT),
        ],
    )
    def test_defaults_match_after_effects(self, cls: type, expected: bytes) -> None:
        """A default-constructed variant equals AE's own default blob."""
        buf = BytesIO()
        cls().write(buf)
        assert buf.getvalue() == expected

    def test_unknown_size_falls_back_to_raw(self) -> None:
        """A future renderer must not corrupt the file."""
        body = bytes.fromhex("00112233445566")
        chunk = PrdaChunk.frombytes(body, chunk_type="prda")
        assert type(chunk) is PrdaChunk
        buf = BytesIO()
        chunk.write(buf)
        assert buf.getvalue() == body
