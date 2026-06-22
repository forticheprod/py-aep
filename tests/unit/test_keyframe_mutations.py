"""Tests for keyframe mutation: add_key, remove_key, set_value(s)_at_time(s),
Shape creation from scratch, and numeric keyframe value persistence.

Mutation tests parse a fresh (uncached) copy so changes do not leak between
tests, and assert results survive a save / re-parse round-trip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep.models.properties.shape import Shape

SAMPLES = Path(__file__).parent.parent.parent / "samples" / "models" / "property"
SAMPLES_ROOT = Path(__file__).parent.parent.parent / "samples"


def _approx_points(actual, expected, abs_tol=1e-2) -> bool:
    """Compare two lists of [x, y] pairs within tolerance."""
    if len(actual) != len(expected):
        return False
    return all(a == pytest.approx(e, abs=abs_tol) for a, e in zip(actual, expected))


class TestShapeFromScratch:
    def test_closed_triangle_no_tangents(self) -> None:
        verts = [[0.0, 0.0], [100.0, 0.0], [50.0, 80.0]]
        s = Shape(verts)
        assert s.closed is True
        assert _approx_points(s.vertices, verts)
        assert _approx_points(s.in_tangents, [[0, 0]] * 3)
        assert _approx_points(s.out_tangents, [[0, 0]] * 3)

    def test_open_path_with_tangents(self) -> None:
        verts = [[0.0, 0.0], [200.0, 100.0]]
        ins = [[-10.0, 0.0], [-20.0, -5.0]]
        outs = [[10.0, 0.0], [20.0, 5.0]]
        s = Shape(verts, ins, outs, closed=False)
        assert s.closed is False
        assert _approx_points(s.vertices, verts)
        assert _approx_points(s.in_tangents, ins)
        assert _approx_points(s.out_tangents, outs)

    def test_empty_shape(self) -> None:
        s = Shape()
        assert s.vertices == []
        assert s.closed is True

    def test_mismatched_tangent_lengths_raise(self) -> None:
        with pytest.raises(ValueError):
            Shape([[0.0, 0.0], [1.0, 1.0]], in_tangents=[[0.0, 0.0]])

    def test_post_construction_vertices_edit(self) -> None:
        s = Shape([[0.0, 0.0], [100.0, 0.0], [50.0, 80.0]])
        new = [[0.0, 0.0], [300.0, 0.0], [150.0, 240.0]]
        s.vertices = new
        assert _approx_points(s.vertices, new)
