"""RotoBezier tangent rule (`resolvers.roto_bezier`), against values
measured on After Effects 2026."""

from __future__ import annotations

import pytest

from py_aep.resolvers.roto_bezier import (
    DEFAULT_TENSION,
    keyframe_tensions,
    roto_bezier_tangents,
)


def _flat(points: list[list[float]]) -> list[float]:
    return [c for point in points for c in point]


def _zeros(count: int) -> list[list[float]]:
    return [[0.0, 0.0] for _ in range(count)]


class TestRotoBezierTangents:
    def test_closed_path_in_pixel_space(self) -> None:
        # A 1920x1080 layer's current aspect stamp (width / height) makes
        # the measuring space pixel space: each tangent is k times the
        # distance to its neighbour, along next - prev.
        vertices = [[100, 100], [900, 120], [800, 700], [150, 600]]
        ins, outs = roto_bezier_tangents(
            vertices,
            _zeros(4),
            _zeros(4),
            True,
            [DEFAULT_TENSION] * 4,
            (1920 / 1080) / 1920,
            1 / 1080,
        )
        assert _flat(ins)[:2] == pytest.approx([-141.0787, 90.2904], abs=1e-3)
        assert _flat(outs)[:2] == pytest.approx([224.6758, -143.7926], abs=1e-3)

    def test_stale_aspect_measures_in_normalized_space(self) -> None:
        # An aspect of 1 (older files) measures the default full-layer
        # rectangle as a unit square: AE reports +-452.548 / 254.558 on a
        # 1920x1080 layer (the mask_rotobezier_on sample).
        vertices = [[0, 0], [0, 1080], [1920, 1080], [1920, 0]]
        ins, outs = roto_bezier_tangents(
            vertices,
            _zeros(4),
            _zeros(4),
            True,
            [DEFAULT_TENSION] * 4,
            1 / 1920,
            1 / 1080,
        )
        assert ins[0] == pytest.approx([452.5483, -254.5584], abs=1e-3)
        assert outs[0] == pytest.approx([-452.5483, 254.5584], abs=1e-3)

    def test_open_path_ends_aim_at_the_neighbouring_handle(self) -> None:
        ins, outs = roto_bezier_tangents(
            [[100, 100], [500, 500], [900, 100]],
            _zeros(3),
            _zeros(3),
            False,
            [0.0] * 3,
            1.0,
            1.0,
        )
        assert _flat(ins) == pytest.approx(
            [0, 0, -282.8427, 0, -58.5786, 200], abs=1e-3
        )
        assert _flat(outs) == pytest.approx([58.5786, 200, 282.8427, 0, 0, 0], abs=1e-3)

    def test_two_vertex_open_path_aims_at_the_stored_out_handle(self) -> None:
        # The last end is aimed first, at the first vertex's stored out
        # handle, then the first end at the new in handle. AE 2026 reads
        # (-102.963, -52.222) and (99.012, 49.259) (mask_rotobezier_handles).
        ins, outs = roto_bezier_tangents(
            [[100, 100], [500, 300]],
            [[0, 0], [-126.6667, -70]],
            [[91.1111, 43.3333], [0, 0]],
            False,
            [DEFAULT_TENSION] * 2,
            1.0,
            1.0,
        )
        assert _flat(ins) == pytest.approx([0, 0, -102.963, -52.222], abs=1e-3)
        assert _flat(outs) == pytest.approx([99.012, 49.259, 0, 0], abs=1e-3)

    @pytest.mark.parametrize(
        "vertices,stored_in,stored_out",
        [
            ([[100, 100], [500, 300]], [[-20, 10], [0, -30]], [[20, -10], [0, 30]]),
            ([[300, 300]], [[-5400, 0]], [[5400, 0]]),
        ],
    )
    def test_degenerate_closed_paths_keep_their_stored_handles(
        self,
        vertices: list[list[float]],
        stored_in: list[list[float]],
        stored_out: list[list[float]],
    ) -> None:
        ins, outs = roto_bezier_tangents(
            vertices, stored_in, stored_out, True, [0.0] * len(vertices), 1.0, 1.0
        )
        assert ins == stored_in
        assert outs == stored_out

    @pytest.mark.parametrize(
        "gap,in_tangent,out_tangent",
        [
            (0.0003, [0, -30], [0, 30]),
            (0.0015, [-240.3701, 0], [240.3697, 0]),
        ],
    )
    def test_near_coincident_neighbours_keep_the_stored_handles(
        self, gap: float, in_tangent: list[float], out_tangent: list[float]
    ) -> None:
        # Neighbours closer than 1e-6 layer heights leave the middle vertex
        # untouched (AE 2026, mask_rotobezier_handles).
        ins, outs = roto_bezier_tangents(
            [[100, 100], [700, 500], [100 + gap, 100]],
            [[0, 0], [0, -30], [200, 133.3333]],
            [[200, 133.3333], [0, 30], [0, 0]],
            True,
            [DEFAULT_TENSION] * 3,
            (1920 / 1080) / 1920,
            1 / 1080,
        )
        assert ins[1] == pytest.approx(in_tangent, abs=1e-3)
        assert outs[1] == pytest.approx(out_tangent, abs=1e-3)


class TestKeyframeTensions:
    def test_stored_tensions_are_kept(self) -> None:
        assert keyframe_tensions([0.5, 0.25], [[0, 0], [1, 2]], [[0, 0], [3, 4]]) == [
            0.5,
            0.25,
        ]

    def test_missing_tensions_follow_the_stored_handles(self) -> None:
        tensions = keyframe_tensions(
            [], [[-30, 10], [0, 0], [0, 0]], [[40, -20], [0, 0], [0, 5]]
        )
        assert tensions == [DEFAULT_TENSION, 1.0, DEFAULT_TENSION]
