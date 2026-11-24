"""Keyframe values, bit for bit against After Effects.

After Effects evaluates a keyed number at a whole tick of the layer's
timebase and in the units the file stores. A segment LINEAR on both sides
is `(v1 - v0) * (ticks / span) + v0`, so every expected number below is the
double AE 2026 returned from `valueAtTime` for the same keys, compared with
`==`. The eased segment goes through a cubic solver whose last bit follows
the maths library, so it is held to a few ulps instead.
"""

from __future__ import annotations

import pytest

import py_aep
from py_aep import KeyframeEase, KeyframeInterpolationType


def _layer(fps: float = 24.0, width: int = 1920, height: int = 1080):
    app = py_aep.new()
    comp = app.project.root_folder.add_comp("C", width, height, 1.0, 10.0, fps)
    return comp.add_solid([1, 0, 0], "L", 100, 100, 1.0)


class TestLinearSegments:
    """LINEAR keys on a 24 fps layer, read at whole frames."""

    def test_opacity(self) -> None:
        # Opacity is stored as a fraction, AE scales the result by 100.
        opacity = _layer().property("Transform").property("Opacity")
        opacity.set_value_at_time(1.0, 20.0)
        opacity.set_value_at_time(1.5, 80.0)
        expected = [
            (1.0833333333333333, 30.000000000000004),
            (1.125, 35.0),
            (1.1666666666666667, 40.0),
            (1.2083333333333333, 45.00000000000001),
            (1.3333333333333333, 60.00000000000001),
            (1.4583333333333333, 75.0),
        ]
        for time, value in expected:
            assert opacity.value_at_time(time) == value

    def test_rotation(self) -> None:
        rotation = _layer().property("Transform").property("Rotation")
        rotation.set_value_at_time(1.0, 0.0)
        rotation.set_value_at_time(1.5, 90.0)
        rotation.set_value_at_time(2.0, 45.0)
        expected = [
            (1.0416666666666667, 7.5),
            (1.0833333333333333, 15.0),
            (1.125, 22.5),
            (1.1666666666666667, 30.0),
            (1.2083333333333333, 37.5),
            (1.3333333333333333, 60.0),
        ]
        for time, value in expected:
            assert rotation.value_at_time(time) == value

    def test_scale(self) -> None:
        scale = _layer().property("Transform").property("Scale")
        scale.set_value_at_time(0.5, [100.0, 100.0, 100.0])
        scale.set_value_at_time(1.0, [50.0, 150.0, 100.0])
        expected = [
            (0.5416666666666666, [95.83333333333334, 104.16666666666667, 100.0]),
            (0.5833333333333334, [91.66666666666666, 108.33333333333333, 100.0]),
            (0.625, [87.5, 112.5, 100.0]),
            (0.75, [75.0, 125.0, 100.0]),
            (0.8333333333333334, [66.66666666666667, 133.33333333333331, 100.0]),
        ]
        for time, value in expected:
            assert scale.value_at_time(time) == value

    def test_stretched_layers(self) -> None:
        # 25 fps comp. Rotation keys 0 / 90 / 30, 0.4 s apart in layer time.
        cases = [
            # start 0.13 s, 100 %
            (0.13, 100.0, (0.53, 0.93, 1.33), (0.5416666666666666, 2.6279296875)),
            (0.13, 100.0, (0.53, 0.93, 1.33), (0.75, 49.50000000000001)),
            (0.13, 100.0, (0.53, 0.93, 1.33), (1.0416666666666667, 73.248046875)),
            # start 0 s, 50 %
            (0.0, 50.0, (0.2, 0.4, 0.6), (0.20833333333333334, 3.744140625)),
            (0.0, 50.0, (0.2, 0.4, 0.6), (0.4583333333333333, 72.50390625)),
        ]
        for start, stretch, key_times, (time, value) in cases:
            layer = _layer(25.0, 1000, 500)
            layer.start_time = start
            layer.stretch = stretch
            rotation = layer.property("Transform").property("Rotation")
            for key_time, key_value in zip(key_times, (0.0, 90.0, 30.0)):
                rotation.set_value_at_time(key_time, key_value)
            assert [kf.time_units for kf in rotation.keyframes] == [
                10240,
                20480,
                30720,
            ]
            assert rotation.value_at_time(time) == value


class TestEasedSegment:
    """A Slider Control keyed 0 / 100 / 50 at 0.25 / 1 / 1.75 s, BEZIER on
    every side, at 24 fps."""

    def test_matches_after_effects(self) -> None:
        layer = _layer()
        slider = layer.effects.add_property("ADBE Slider Control").property(
            "ADBE Slider Control-0001"
        )
        slider.set_value_at_time(0.25, 0.0)
        slider.set_value_at_time(1.0, 100.0)
        slider.set_value_at_time(1.75, 50.0)
        eases = [
            ((0.0, 33.0), (0.0, 75.0)),
            ((20.0, 50.0), (-30.0, 40.0)),
            ((0.0, 60.0), (0.0, 60.0)),
        ]
        for keyframe, (ease_in, ease_out) in zip(slider.keyframes, eases):
            keyframe.in_interpolation_type = KeyframeInterpolationType.BEZIER
            keyframe.out_interpolation_type = KeyframeInterpolationType.BEZIER
            keyframe.in_temporal_ease = [
                KeyframeEase(speed=ease_in[0], influence=ease_in[1])
            ]
            keyframe.out_temporal_ease = [
                KeyframeEase(speed=ease_out[0], influence=ease_out[1])
            ]
        expected = [
            (0.2916666666666667, 0.17817420241000148),
            (0.4166666666666667, 3.4169342769762596),
            (0.5833333333333334, 19.200427810057544),
            (0.75, 66.32464719609334),
            (0.9166666666666666, 96.41858742550305),
            (1.0833333333333333, 96.31863175784378),
            (1.25, 80.2861029609866),
            (1.4166666666666667, 61.42691477860235),
            (1.5833333333333333, 52.27237649343462),
        ]
        for time, value in expected:
            assert slider.value_at_time(time) == pytest.approx(value, rel=1e-14)
