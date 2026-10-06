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


class TestRotoBezierTangents:
    def test_closed_path_in_pixel_space(self) -> None:
        # A 1920x1080 layer's current aspect stamp (width / height) makes
        # the measuring space pixel space: each tangent is k times the
        # distance to its neighbour, along next - prev.
        vertices = [[100, 100], [900, 120], [800, 700], [150, 600]]
        ins, outs = roto_bezier_tangents(
            vertices, True, [DEFAULT_TENSION] * 4, (1920 / 1080) / 1920, 1 / 1080
        )
        assert _flat(ins)[:2] == pytest.approx([-141.0787, 90.2904], abs=1e-3)
        assert _flat(outs)[:2] == pytest.approx([224.6758, -143.7926], abs=1e-3)

    def test_stale_aspect_measures_in_normalized_space(self) -> None:
        # An aspect of 1 (older files) measures the default full-layer
        # rectangle as a unit square: AE reports +-452.548 / 254.558 on a
        # 1920x1080 layer (the mask_rotobezier_on sample).
        vertices = [[0, 0], [0, 1080], [1920, 1080], [1920, 0]]
        ins, outs = roto_bezier_tangents(
            vertices, True, [DEFAULT_TENSION] * 4, 1 / 1920, 1 / 1080
        )
        assert ins[0] == pytest.approx([452.5483, -254.5584], abs=1e-3)
        assert outs[0] == pytest.approx([-452.5483, 254.5584], abs=1e-3)

    def test_open_path_ends_aim_at_the_neighbouring_handle(self) -> None:
        ins, outs = roto_bezier_tangents(
            [[100, 100], [500, 500], [900, 100]], False, [0.0] * 3, 1.0, 1.0
        )
        assert _flat(ins) == pytest.approx(
            [0, 0, -282.8427, 0, -58.5786, 200], abs=1e-3
        )
        assert _flat(outs) == pytest.approx([58.5786, 200, 282.8427, 0, 0, 0], abs=1e-3)

    def test_two_vertex_open_path(self) -> None:
        # The last end is aimed first, while the first end's handle is 0.
        ins, outs = roto_bezier_tangents(
            [[100, 100], [500, 300]], False, [0.0, 0.0], 1.0, 1.0
        )
        assert _flat(ins) == pytest.approx([0, 0, -200, -100])
        assert _flat(outs) == pytest.approx([100, 50, 0, 0])

    @pytest.mark.parametrize(
        "vertices",
        [[[100, 100], [500, 300]], [[300, 300]]],
    )
    def test_degenerate_closed_paths_have_no_tangents(
        self, vertices: list[list[float]]
    ) -> None:
        ins, outs = roto_bezier_tangents(
            vertices, True, [0.0] * len(vertices), 1.0, 1.0
        )
        assert not any(_flat(ins) + _flat(outs))


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
