"""Unit tests for the transform matrix module.

Tests matrix composition, decomposition, and round-trip accuracy for
a variety of 2D and 3D transform configurations.
"""

from __future__ import annotations

import pytest

from py_aep.resolvers.transform import (
    Mat4,
    _translation,
    build_local_matrix,
    decompose_transform,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _approx(a, b, tol=1e-6):
    """Assert two values (scalar or nested list) are approximately equal."""
    if isinstance(a, list) and isinstance(b, list):
        assert len(a) == len(b), f"length mismatch: {len(a)} vs {len(b)}"
        for i, (ai, bi) in enumerate(zip(a, b)):
            assert ai == pytest.approx(bi, abs=tol), f"index {i}: {ai} != {bi}"
    else:
        assert a == pytest.approx(b, abs=tol)


def _mat_approx(a, b, tol=1e-6):
    """Assert two 4x4 matrices are approximately equal."""
    for r in range(4):
        for c in range(4):
            assert a[r][c] == pytest.approx(b[r][c], abs=tol), (
                f"M[{r}][{c}]: {a[r][c]} != {b[r][c]}"
            )


# ------------------------------------------------------------------
# Identity and basic operations
# ------------------------------------------------------------------


class TestMatrixPrimitives:
    def test_identity(self):
        m = Mat4.identity()
        for r in range(4):
            for c in range(4):
                expected = 1.0 if r == c else 0.0
                assert m[r][c] == expected

    def test_multiply_identity(self):
        a = build_local_matrix([10, 20, 0], [0, 0, 0], [100, 100, 100], 45)
        result = Mat4.identity() @ a
        _mat_approx(result, a)
        result2 = a @ Mat4.identity()
        _mat_approx(result2, a)

    def test_translation_roundtrip(self):
        t = _translation(5, 10, 15)
        t_inv = t.inverse()
        result = t @ t_inv
        _mat_approx(result, Mat4.identity())

    def test_inverse_of_identity(self):
        m = Mat4.identity()
        inv = m.inverse()
        _mat_approx(inv, Mat4.identity())

    def test_inverse_roundtrip(self):
        m = build_local_matrix(
            [30, 20, 10], [5, 5, 0], [150, 80, 100], 37, rotate_x=15, rotate_y=25
        )
        inv = m.inverse()
        result = m @ inv
        _mat_approx(result, Mat4.identity(), tol=1e-5)

    def test_singular_raises(self):
        m = Mat4([[0] * 4 for _ in range(4)])
        with pytest.raises(ValueError, match="Singular"):
            m.inverse()


# ------------------------------------------------------------------
# Build + decompose round-trip tests
# ------------------------------------------------------------------


class TestRoundTrip2D:
    """2D layers: only Position, Anchor, Scale, Rotation Z."""

    def test_identity_transform(self):
        pos = [0.0, 0.0, 0.0]
        anchor = [0.0, 0.0, 0.0]
        scale = [100.0, 100.0, 100.0]
        rz = 0.0
        m = build_local_matrix(pos, anchor, scale, rz)
        d_pos, d_scale, d_rz, d_rx, d_ry = decompose_transform(m, anchor)
        _approx(d_pos, pos)
        _approx(d_scale, scale)
        _approx(d_rz, rz)
        _approx(d_rx, 0.0)
        _approx(d_ry, 0.0)

    def test_position_only(self):
        pos = [73.0, 41.0, 0.0]
        anchor = [0.0, 0.0, 0.0]
        scale = [100.0, 100.0, 100.0]
        rz = 0.0
        m = build_local_matrix(pos, anchor, scale, rz)
        d_pos, d_scale, d_rz, d_rx, d_ry = decompose_transform(m, anchor)
        _approx(d_pos, pos)
        _approx(d_scale, scale)
        _approx(d_rz, rz)

    def test_position_with_anchor(self):
        pos = [50.0, 50.0, 0.0]
        anchor = [25.0, 25.0, 0.0]
        scale = [100.0, 100.0, 100.0]
        rz = 0.0
        m = build_local_matrix(pos, anchor, scale, rz)
        d_pos, d_scale, d_rz, _, _ = decompose_transform(m, anchor)
        _approx(d_pos, pos)
        _approx(d_scale, scale)
        _approx(d_rz, rz)

    def test_rotation_only(self):
        pos = [0.0, 0.0, 0.0]
        anchor = [0.0, 0.0, 0.0]
        scale = [100.0, 100.0, 100.0]
        rz = 45.0
        m = build_local_matrix(pos, anchor, scale, rz)
        d_pos, d_scale, d_rz, _, _ = decompose_transform(m, anchor)
        _approx(d_pos, pos)
        _approx(d_scale, scale)
        _approx(d_rz, rz)

    def test_scale_only(self):
        pos = [0.0, 0.0, 0.0]
        anchor = [0.0, 0.0, 0.0]
        scale = [200.0, 50.0, 100.0]
        rz = 0.0
        m = build_local_matrix(pos, anchor, scale, rz)
        d_pos, d_scale, d_rz, _, _ = decompose_transform(m, anchor)
        _approx(d_pos, pos)
        _approx(d_scale, scale)
        _approx(d_rz, rz)

    def test_combined_2d(self):
        pos = [30.0, 20.0, 0.0]
        anchor = [10.0, 10.0, 0.0]
        scale = [150.0, 80.0, 100.0]
        rz = 30.0
        m = build_local_matrix(pos, anchor, scale, rz)
        d_pos, d_scale, d_rz, _, _ = decompose_transform(m, anchor)
        _approx(d_pos, pos)
        _approx(d_scale, scale)
        _approx(d_rz, rz)

    def test_negative_rotation(self):
        pos = [100.0, 100.0, 0.0]
        anchor = [50.0, 50.0, 0.0]
        scale = [100.0, 100.0, 100.0]
        rz = -45.0
        m = build_local_matrix(pos, anchor, scale, rz)
        d_pos, d_scale, d_rz, _, _ = decompose_transform(m, anchor)
        _approx(d_pos, pos)
        _approx(d_scale, scale)
        _approx(d_rz, rz)

    def test_large_rotation(self):
        """Rotations > 180 degrees decompose into [-180, 180] range."""
        pos = [0.0, 0.0, 0.0]
        anchor = [0.0, 0.0, 0.0]
        scale = [100.0, 100.0, 100.0]
        rz = 270.0
        m = build_local_matrix(pos, anchor, scale, rz)
        d_pos, d_scale, d_rz, _, _ = decompose_transform(m, anchor)
        # 270 degrees decomposes to -90 (same visual rotation)
        _approx(d_rz, -90.0)


class TestRoundTrip3D:
    """3D layers: full rotation set."""

    def test_rotate_x_only(self):
        pos = [0.0, 0.0, 0.0]
        anchor = [0.0, 0.0, 0.0]
        scale = [100.0, 100.0, 100.0]
        m = build_local_matrix(pos, anchor, scale, 0.0, rotate_x=45.0)
        d_pos, d_scale, d_rz, d_rx, d_ry = decompose_transform(m, anchor)
        _approx(d_pos, pos)
        _approx(d_scale, scale)
        _approx(d_rx, 45.0)
        _approx(d_ry, 0.0)
        _approx(d_rz, 0.0)

    def test_rotate_y_only(self):
        pos = [0.0, 0.0, 0.0]
        anchor = [0.0, 0.0, 0.0]
        scale = [100.0, 100.0, 100.0]
        m = build_local_matrix(pos, anchor, scale, 0.0, rotate_y=30.0)
        d_pos, d_scale, d_rz, d_rx, d_ry = decompose_transform(m, anchor)
        _approx(d_ry, 30.0)
        _approx(d_rx, 0.0)

    def test_combined_3d_rotations(self):
        pos = [10.0, 20.0, 30.0]
        anchor = [5.0, 5.0, 5.0]
        scale = [120.0, 80.0, 100.0]
        rz = 15.0
        rx = 25.0
        ry = 35.0
        m = build_local_matrix(pos, anchor, scale, rz, rotate_x=rx, rotate_y=ry)
        d_pos, d_scale, d_rz, d_rx, d_ry = decompose_transform(m, anchor)
        _approx(d_pos, pos)
        _approx(d_scale, scale)
        _approx(d_rz, rz)
        _approx(d_rx, rx)
        _approx(d_ry, ry)

    def test_orientation_3d(self):
        """Orientation angles compose into the matrix correctly."""
        pos = [0.0, 0.0, 0.0]
        anchor = [0.0, 0.0, 0.0]
        scale = [100.0, 100.0, 100.0]
        orient = [10.0, 20.0, 30.0]
        m = build_local_matrix(pos, anchor, scale, 0.0, orientation=orient)
        # The decomposition extracts the combined rotation into
        # per-axis angles (since orientation is assumed zero for
        # decomposition). The key check is round-trip through
        # build -> decompose -> build produces the same matrix.
        d_pos, d_scale, d_rz, d_rx, d_ry = decompose_transform(m, anchor)
        m2 = build_local_matrix(
            d_pos, anchor, d_scale, d_rz, rotate_x=d_rx, rotate_y=d_ry
        )
        _mat_approx(m, m2, tol=1e-5)

    def test_combined_orientation_and_per_axis(self):
        """Orientation + per-axis rotations: decompose -> recompose
        produces the same matrix (rotation folded into per-axis)."""
        pos = [50.0, 50.0, 50.0]
        anchor = [10.0, 10.0, 0.0]
        scale = [100.0, 100.0, 100.0]
        orient = [5.0, 10.0, 15.0]
        rz, rx, ry = 20.0, 10.0, 5.0
        m = build_local_matrix(
            pos, anchor, scale, rz, orientation=orient, rotate_x=rx, rotate_y=ry
        )
        d_pos, d_scale, d_rz, d_rx, d_ry = decompose_transform(m, anchor)
        m2 = build_local_matrix(
            d_pos, anchor, d_scale, d_rz, rotate_x=d_rx, rotate_y=d_ry
        )
        _mat_approx(m, m2, tol=1e-5)


# ------------------------------------------------------------------
# Parent-child composition tests
# ------------------------------------------------------------------


class TestParentChild:
    """Simulate unparenting: compose parent+child, decompose child."""

    def test_position_only_parent(self):
        """Child at [0,0,0] with parent at [73,41,0] -> child becomes [73,41,0]."""
        parent_pos = [73.0, 41.0, 0.0]
        child_pos = [0.0, 0.0, 0.0]
        child_anchor = [50.0, 50.0, 0.0]
        scale = [100.0, 100.0, 100.0]

        parent_m = build_local_matrix(parent_pos, [0.0, 0.0, 0.0], scale, 0.0)
        child_m = build_local_matrix(child_pos, child_anchor, scale, 0.0)

        world = parent_m @ child_m
        d_pos, d_scale, d_rz, _, _ = decompose_transform(world, child_anchor)
        _approx(d_pos, [73.0, 41.0, 0.0])
        _approx(d_scale, scale)
        _approx(d_rz, 0.0)

    def test_rotated_parent(self):
        """Child at [100,0,0] with parent rotated 90deg -> child at [0,100,0]."""
        parent_m = build_local_matrix(
            [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [100.0, 100.0, 100.0], 90.0
        )
        child_m = build_local_matrix(
            [100.0, 0.0, 0.0], [0.0, 0.0, 0.0], [100.0, 100.0, 100.0], 0.0
        )
        world = parent_m @ child_m
        d_pos, d_scale, d_rz, _, _ = decompose_transform(world, [0.0, 0.0, 0.0])
        _approx(d_pos, [0.0, 100.0, 0.0])
        _approx(d_rz, 90.0)

    def test_scaled_parent(self):
        """Child at [50,50,0] with parent at 200% -> child at [100,100,0] with 200% scale."""
        parent_m = build_local_matrix(
            [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [200.0, 200.0, 100.0], 0.0
        )
        child_m = build_local_matrix(
            [50.0, 50.0, 0.0], [0.0, 0.0, 0.0], [100.0, 100.0, 100.0], 0.0
        )
        world = parent_m @ child_m
        d_pos, d_scale, d_rz, _, _ = decompose_transform(world, [0.0, 0.0, 0.0])
        _approx(d_pos, [100.0, 100.0, 0.0])
        _approx(d_scale, [200.0, 200.0, 100.0])

    def test_complex_parent(self):
        """Combined parent transform: pos + rotation + scale."""
        parent_m = build_local_matrix(
            [30.0, 20.0, 0.0], [0.0, 0.0, 0.0], [150.0, 150.0, 100.0], 30.0
        )
        child_m = build_local_matrix(
            [10.0, 5.0, 0.0], [0.0, 0.0, 0.0], [80.0, 80.0, 100.0], 15.0
        )
        world = parent_m @ child_m
        d_pos, d_scale, d_rz, _, _ = decompose_transform(world, [0.0, 0.0, 0.0])
        # Verify round-trip: rebuild from decomposed values matches world
        m2 = build_local_matrix(d_pos, [0.0, 0.0, 0.0], d_scale, d_rz)
        _mat_approx(world, m2, tol=1e-5)

    def test_parent_with_anchor_offset(self):
        """Parent with non-zero anchor: rotates around its anchor point."""
        parent_anchor = [25.0, 25.0, 0.0]
        parent_m = build_local_matrix(
            [50.0, 50.0, 0.0], parent_anchor, [100.0, 100.0, 100.0], 90.0
        )
        child_m = build_local_matrix(
            [20.0, 0.0, 0.0], [0.0, 0.0, 0.0], [100.0, 100.0, 100.0], 0.0
        )
        world = parent_m @ child_m
        d_pos, d_scale, d_rz, _, _ = decompose_transform(world, [0.0, 0.0, 0.0])
        # Rebuild from decomposed values
        m2 = build_local_matrix(d_pos, [0.0, 0.0, 0.0], d_scale, d_rz)
        _mat_approx(world, m2, tol=1e-5)

    def test_inverse_parent_gives_identity_child(self):
        """Assigning a new parent: child_new_local = inv(parent) @ child_world."""
        parent_m = build_local_matrix(
            [50.0, 30.0, 0.0], [0.0, 0.0, 0.0], [100.0, 100.0, 100.0], 0.0
        )
        child_world = build_local_matrix(
            [50.0, 30.0, 0.0], [0.0, 0.0, 0.0], [100.0, 100.0, 100.0], 0.0
        )
        child_local = parent_m.inverse() @ child_world
        d_pos, d_scale, d_rz, _, _ = decompose_transform(child_local, [0.0, 0.0, 0.0])
        _approx(d_pos, [0.0, 0.0, 0.0])
        _approx(d_scale, [100.0, 100.0, 100.0])
        _approx(d_rz, 0.0)


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------


class TestEdgeCases:
    def test_negative_scale(self):
        """Negative scale (mirror) round-trips correctly."""
        pos = [0.0, 0.0, 0.0]
        anchor = [0.0, 0.0, 0.0]
        scale = [-100.0, 100.0, 100.0]
        m = build_local_matrix(pos, anchor, scale, 0.0)
        d_pos, d_scale, d_rz, _, _ = decompose_transform(m, anchor)
        # Scale should come back negative on x
        assert d_scale[0] < 0
        # Rebuild should match
        m2 = build_local_matrix(d_pos, anchor, d_scale, d_rz)
        _mat_approx(m, m2, tol=1e-5)

    def test_zero_scale_clamped(self):
        """Zero scale doesn't crash - clamped to epsilon."""
        pos = [10.0, 20.0, 0.0]
        anchor = [0.0, 0.0, 0.0]
        scale = [0.0, 100.0, 100.0]
        m = build_local_matrix(pos, anchor, scale, 0.0)
        # Should not raise
        d_pos, d_scale, d_rz, _, _ = decompose_transform(m, anchor)
        _approx(d_pos, pos)

    def test_180_rotation(self):
        pos = [0.0, 0.0, 0.0]
        anchor = [0.0, 0.0, 0.0]
        scale = [100.0, 100.0, 100.0]
        m = build_local_matrix(pos, anchor, scale, 180.0)
        d_pos, d_scale, d_rz, _, _ = decompose_transform(m, anchor)
        _approx(abs(d_rz), 180.0, tol=0.01)

    def test_gimbal_lock_3d(self):
        """Near gimbal lock (ry=90) still decomposes to same matrix."""
        pos = [10.0, 20.0, 30.0]
        anchor = [0.0, 0.0, 0.0]
        scale = [100.0, 100.0, 100.0]
        m = build_local_matrix(pos, anchor, scale, 0.0, rotate_x=45.0, rotate_y=89.99)
        d_pos, d_scale, d_rz, d_rx, d_ry = decompose_transform(m, anchor)
        # The exact angle decomposition may differ but the matrix
        # must be equivalent.
        m2 = build_local_matrix(
            d_pos, anchor, d_scale, d_rz, rotate_x=d_rx, rotate_y=d_ry
        )
        _mat_approx(m, m2, tol=1e-4)
