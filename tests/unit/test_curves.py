"""Tests for the Curves effect's value (ADBE CurvesCustom-0001)."""

from __future__ import annotations

import math
import struct

import pytest

from py_aep.models.properties.curves import CURVES_CHANNELS, Curves


def _blob(points: dict[str, list[tuple[int, int]]], mode: int = 1, stale: bool = False) -> bytes:
    """A Curves value as After Effects writes it, the maps left for the test to fill."""
    out = bytearray(4 + 5 * 256 + 5 * 72)
    struct.pack_into(">HH", out, 0, 1, mode)
    for c, name in enumerate(CURVES_CHANNELS):
        pts = points.get(name, [(0, 0), (255, 255)])
        out[4 + 256 * c : 4 + 256 * (c + 1)] = bytes(range(256))
        offset = 4 + 5 * 256 + 72 * c
        for i, (x, y) in enumerate(pts):
            struct.pack_into(">hh", out, offset + 4 * i, x, y)
        if stale:
            # After Effects leaves old points past the count.
            struct.pack_into(">hh", out, offset + 4 * len(pts), 5440, 8193)
        struct.pack_into(">Ii", out, offset + 64, len(pts), -1)
    return bytes(out)


def test_decodes_points_in_channel_order() -> None:
    curves = Curves(_blob({"rgb": [(0, 0), (168, 93), (255, 246)]}, stale=True))
    assert curves.uses_points
    assert curves.channels["rgb"].points == [(0, 0), (168, 93), (255, 246)]
    assert curves.channels["red"].points == [(0, 0), (255, 255)]
    assert curves.channels["red"].is_identity
    assert not curves.channels["rgb"].is_identity


def test_natural_spline_goes_through_the_points() -> None:
    curves = Curves(_blob({"rgb": [(0, 0), (41, 30), (129, 149), (191, 211), (255, 255)]}))
    for x, y in curves.channels["rgb"].points:
        assert math.isclose(curves.evaluate("rgb", x / 255.0), y / 255.0, abs_tol=1e-9)


def test_two_points_are_a_straight_line() -> None:
    curves = Curves(_blob({"green": [(0, 51), (255, 204)]}))
    assert math.isclose(curves.evaluate("green", 0.5), 0.5, abs_tol=1e-9)


def test_overshoot_is_clamped_unless_asked() -> None:
    # Grayscale 4: the spline dips below 0 near black.
    curves = Curves(_blob({"rgb": [(0, 0), (62, 18), (193, 238), (255, 255)]}))
    assert curves.evaluate("rgb", 0.05) == 0.0
    assert curves.evaluate("rgb", 0.05, clamp=False) < 0.0


def test_pencil_mode_reads_the_maps() -> None:
    blob = bytearray(_blob({}, mode=0))
    blob[4 : 4 + 256] = bytes(255 - i for i in range(256))
    curves = Curves(bytes(blob))
    assert not curves.uses_points
    assert math.isclose(curves.evaluate("rgb", 0.0), 1.0)
    assert math.isclose(curves.evaluate("rgb", 1.0), 0.0)


def test_rejects_other_sizes() -> None:
    with pytest.raises(ValueError):
        Curves(b"\x00" * 16)
