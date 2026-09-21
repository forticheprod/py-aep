"""Issue #225 + v8 finding 1: keyframe evaluation and insertion.

Every expected number was measured in After Effects 2026 through
`valueAtTime`. AE's own sampling is quoted in the docstrings so a future change
can be judged against it rather than against py's current output.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import SAMPLES_DIR, parse_app_fresh

import py_aep
from py_aep import KeyframeEase, KeyframeInterpolationType

PROPERTY_DIR = SAMPLES_DIR / "models" / "property"


def _new_comp(width: int = 800, height: int = 400, fps: float = 24.0):
    app = py_aep.new()
    comp = app.project.root_folder.add_comp("C", width, height, 1.0, 10.0, fps)
    return app, comp


def _position_with(comp, name, keys, out_tan=None, in_tan=None, eases=None):
    layer = comp.add_solid([1, 0, 0], name, 100, 100, 1.0)
    pos = layer.property("Transform").property("Position")
    for t, value in keys:
        pos.set_value_at_time(t, value)
    if out_tan is not None:
        pos.keyframes[0].out_spatial_tangent = out_tan
    if in_tan is not None:
        pos.keyframes[-1].in_spatial_tangent = in_tan
    if eases is not None:
        out_ease, in_ease = eases
        pos.keyframes[0].out_temporal_ease = [out_ease]
        pos.keyframes[-1].in_temporal_ease = [in_ease]
    return layer, pos


class TestFlatBezierSegment:
    """Issue #225: a 1-D BEZIER segment whose keys hold the SAME value
    evaluated flat, because the ease handles were normalized by `v1 - v0`.
    AE places them absolutely, so the curve still bows."""

    #: AE 2026, opacity 50 -> 50 over 2 s, out ease 100/33, in ease -100/33.
    AE = {
        0.0: 50.0,
        0.25: 71.778350,
        0.5: 87.217522,
        0.75: 96.435069,
        1.0: 99.5,
        1.5: 87.217522,
        2.0: 50.0,
    }

    def _build(self):
        app, comp = _new_comp(200, 200)
        layer = comp.add_solid([1, 0, 0], "L", 100, 100, 1.0)
        op = layer.property("Transform").property("Opacity")
        op.set_value_at_time(0.0, 50.0)
        op.set_value_at_time(2.0, 50.0)
        for kf in op.keyframes:
            kf.in_interpolation_type = KeyframeInterpolationType.BEZIER
            kf.out_interpolation_type = KeyframeInterpolationType.BEZIER
        op.keyframes[0].out_temporal_ease = [KeyframeEase(speed=100.0, influence=33.0)]
        op.keyframes[1].in_temporal_ease = [KeyframeEase(speed=-100.0, influence=33.0)]
        return app, op

    def test_matches_after_effects(self) -> None:
        _app, op = self._build()
        for t, want in self.AE.items():
            assert op.value_at_time(t) == pytest.approx(want, abs=1e-4)

    def test_peaks_between_the_keys(self) -> None:
        """The headline symptom: every sample used to read exactly 50."""
        _app, op = self._build()
        assert op.value_at_time(1.0) > 99.0

    def test_still_linear_when_the_values_differ(self) -> None:
        """The absolute and normalized forms agree whenever `v1 != v0`."""
        app, comp = _new_comp(200, 200)
        layer = comp.add_solid([1, 0, 0], "L", 100, 100, 1.0)
        op = layer.property("Transform").property("Opacity")
        op.set_value_at_time(0.0, 0.0)
        op.set_value_at_time(2.0, 100.0)
        for kf in op.keyframes:
            kf.in_interpolation_type = KeyframeInterpolationType.LINEAR
            kf.out_interpolation_type = KeyframeInterpolationType.LINEAR
        assert op.value_at_time(1.0) == pytest.approx(50.0, abs=1e-6)


class TestLinearSideKeepsTheMotionPath:
    """Issue #225 item 2: a LINEAR side sets that side's EASE; the path still
    follows the spatial tangents. py lerped between the keys instead."""

    #: AE 2026: (50,50) -> (350,50), tangents (100,200) / (-100,200), LINEAR.
    AE = {
        0.0: [50.0, 50.0],
        0.5: [108.389427, 144.050019],
        1.0: [199.997539, 200.0],
        1.5: [291.611424, 144.048980],
        2.0: [350.0, 50.0],
    }

    def test_follows_the_cubic(self) -> None:
        _app, comp = _new_comp(400, 400)
        _layer, pos = _position_with(
            comp,
            "LinearOut",
            [(0.0, [50.0, 50.0, 0.0]), (2.0, [350.0, 50.0, 0.0])],
            out_tan=[100.0, 200.0, 0.0],
            in_tan=[-100.0, 200.0, 0.0],
        )
        for kf in pos.keyframes:
            kf.in_interpolation_type = KeyframeInterpolationType.LINEAR
            kf.out_interpolation_type = KeyframeInterpolationType.LINEAR

        for t, want in self.AE.items():
            got = pos.value_at_time(t)
            assert got[:2] == pytest.approx(want, abs=0.05)

    def test_a_tangentless_linear_segment_is_still_a_line(self) -> None:
        _app, comp = _new_comp(400, 400)
        _layer, pos = _position_with(
            comp, "Plain", [(0.0, [0.0, 0.0, 0.0]), (2.0, [100.0, 200.0, 0.0])]
        )
        for kf in pos.keyframes:
            kf.in_interpolation_type = KeyframeInterpolationType.LINEAR
            kf.out_interpolation_type = KeyframeInterpolationType.LINEAR
        assert pos.value_at_time(1.0)[:2] == pytest.approx([50.0, 100.0], abs=1e-6)


class TestSpatialEaseDivisorAndClamp:
    """Issue #225 item 1: the ease speed divides by the path's ARC LENGTH
    (one number for the segment), and a handle that reaches past the unit
    square is shortened along its own slope rather than clamped in y."""

    #: AE 2026: (50,100) -> (750,100), tangents +/-(400,0), ease 900/90.
    AE = {
        0.0: 50.0,
        0.25: 236.611771,
        0.5: 347.368151,
        1.0: 400.001294,
        1.5: 452.634536,
        2.0: 750.0,
    }

    def test_overshooting_handle_keeps_its_speed(self) -> None:
        _app, comp = _new_comp(800, 400)
        _layer, pos = _position_with(
            comp,
            "Overshoot",
            [(0.0, [50.0, 100.0, 0.0]), (2.0, [750.0, 100.0, 0.0])],
            out_tan=[400.0, 0.0, 0.0],
            in_tan=[-400.0, 0.0, 0.0],
            eases=(
                KeyframeEase(speed=900.0, influence=90.0),
                KeyframeEase(speed=900.0, influence=90.0),
            ),
        )
        for kf in pos.keyframes:
            kf.in_interpolation_type = KeyframeInterpolationType.BEZIER
            kf.out_interpolation_type = KeyframeInterpolationType.BEZIER

        for t, want_x in self.AE.items():
            assert pos.value_at_time(t)[0] == pytest.approx(want_x, abs=0.05)


class TestRovingRunIsOneEasedSpan:
    """Issue #225 item 3: the enclosing anchors' ease applies ONCE across the
    whole roving run, and the keys are spaced along that single eased span."""

    #: AE 2026 placed the two roving keys of a 4-point 8 s run at these times.
    AE_TIMES = [0.0, 3.544840, 4.308594, 8.0]
    #: AE's sampled positions on the same run.
    AE_CURVE = {
        1.0: [56.981111, 196.509445],
        3.0: [157.599662, 146.200169],
        5.0: [638.297201, 244.681120],
        7.0: [742.754934, 202.898026],
    }

    def _build(self):
        _app, comp = _new_comp(800, 400)
        layer = comp.add_solid([0, 0, 1], "Roving", 100, 100, 1.0)
        pos = layer.property("Transform").property("Position")
        for t, value in (
            (0.0, [50.0, 200.0, 0.0]),
            (2.0, [250.0, 100.0, 0.0]),
            (5.0, [500.0, 300.0, 0.0]),
            (8.0, [750.0, 200.0, 0.0]),
        ):
            pos.set_value_at_time(t, value)
        # AE's fixture has straight sub-segments; auto tangents would change
        # the arc lengths the roving keys are spaced along.
        for kf in pos.keyframes:
            kf.in_spatial_tangent = [0.0, 0.0, 0.0]
            kf.out_spatial_tangent = [0.0, 0.0, 0.0]
        # The anchors must be BEZIER for their ease to apply at all - a
        # LINEAR anchor carries no ease, and the run is then spaced evenly by
        # arc length (which is what AE does too).
        for kf in (pos.keyframes[0], pos.keyframes[-1]):
            kf.in_interpolation_type = KeyframeInterpolationType.BEZIER
            kf.out_interpolation_type = KeyframeInterpolationType.BEZIER
        ease = KeyframeEase(speed=0.0, influence=80.0)
        pos.keyframes[0].out_temporal_ease = [ease]
        pos.keyframes[-1].in_temporal_ease = [ease]
        pos.keyframes[1].roving = True
        pos.keyframes[2].roving = True
        return pos

    def test_key_times_match_after_effects(self) -> None:
        pos = self._build()
        times = [kf.time for kf in pos.keyframes]
        assert times == pytest.approx(self.AE_TIMES, abs=1e-4)

    def test_curve_matches_after_effects(self) -> None:
        pos = self._build()
        for t, want in self.AE_CURVE.items():
            assert pos.value_at_time(t)[:2] == pytest.approx(want, abs=0.05)


class TestAddKeyPreservesTheCurve:
    """v8 finding 1: `add_key` inserted a LINEAR key with a default ease,
    silently reshaping the animation. AE leaves `valueAtTime` untouched."""

    #: Samples whose animated transform property is 1-D. The spatial cases
    #: are covered by the AE-measured fixtures above: inserting a key there
    #: also splits the motion path, which AE itself only preserves closely.
    SAMPLES = [
        "keyframe_1D.aep",
        "keyframe_HOLD.aep",
        "keyframe_mixed_interpolation.aep",
        "keyframe_bezier_ease_in_out_1D.aep",
    ]

    @pytest.mark.parametrize("sample", SAMPLES)
    def test_curve_is_unchanged(self, sample: str) -> None:
        app = parse_app_fresh(PROPERTY_DIR / sample)
        times = [0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0]
        checked = 0
        for comp in app.project.compositions:
            for layer in comp.layers:
                for prop in layer.transform:
                    if not getattr(prop, "keyframes", None) or len(prop.keyframes) < 2:
                        continue
                    if prop.is_spatial:
                        continue  # covered by the AE-measured cases above
                    key_times = [kf.time for kf in prop.keyframes]
                    mid = (key_times[0] + key_times[1]) / 2.0
                    if any(abs(mid - t) < 1e-6 for t in key_times):
                        continue
                    before = [prop.value_at_time(t) for t in times]
                    prop.add_key(mid)
                    after = [prop.value_at_time(t) for t in times]
                    assert after == pytest.approx(before, abs=1e-6)
                    checked += 1
        assert checked, "no property exercised"

    def test_bezier_split_matches_after_effects(self) -> None:
        """AE splits a 5 s 0->100 segment eased 0/75 at 2.5 s into a BEZIER
        key of value 50 with 80.0 / 12.5 on both sides."""
        app = parse_app_fresh(PROPERTY_DIR / "keyframe_bezier_ease_in_out_1D.aep")
        prop = next(
            p
            for comp in app.project.compositions
            for layer in comp.layers
            for p in layer.transform
            if getattr(p, "keyframes", None) and len(p.keyframes) == 2
        )

        index = prop.add_key(2.5)

        kf = prop.keyframes[index]
        assert kf.time == pytest.approx(2.5)
        assert kf.value == pytest.approx(50.0)
        assert kf.in_interpolation_type == KeyframeInterpolationType.BEZIER
        assert kf.out_interpolation_type == KeyframeInterpolationType.BEZIER
        assert kf.in_temporal_ease[0].speed == pytest.approx(80.0, abs=1e-3)
        assert kf.in_temporal_ease[0].influence == pytest.approx(12.5, abs=1e-3)
        assert kf.out_temporal_ease[0].speed == pytest.approx(80.0, abs=1e-3)
        assert kf.out_temporal_ease[0].influence == pytest.approx(12.5, abs=1e-3)
        # AE leaves the neighbours' handles alone in this case.
        assert prop.keyframes[0].out_temporal_ease[0].influence == pytest.approx(75.0)
        assert prop.keyframes[2].in_temporal_ease[0].influence == pytest.approx(75.0)

    def test_hold_segment_stays_held(self) -> None:
        """AE gives the new key HOLD on both sides (speed 0, default
        influence), so the value never ramps."""
        app, comp = _new_comp(200, 200)
        layer = comp.add_solid([1, 0, 0], "L", 100, 100, 1.0)
        op = layer.property("Transform").property("Opacity")
        op.set_value_at_time(0.0, 100.0)
        op.set_value_at_time(4.0, 0.0)
        for kf in op.keyframes:
            kf.in_interpolation_type = KeyframeInterpolationType.HOLD
            kf.out_interpolation_type = KeyframeInterpolationType.HOLD

        before = [op.value_at_time(t) for t in (0.0, 1.0, 2.0, 3.0, 4.0)]
        op.add_key(2.0)
        after = [op.value_at_time(t) for t in (0.0, 1.0, 2.0, 3.0, 4.0)]

        assert after == pytest.approx(before)
        assert op.keyframes[1].out_interpolation_type == KeyframeInterpolationType.HOLD

    def test_add_then_remove_restores_the_keyframes(self, tmp_path: Path) -> None:
        app = parse_app_fresh(PROPERTY_DIR / "keyframe_bezier_ease_in_out_1D.aep")
        prop = next(
            p
            for comp in app.project.compositions
            for layer in comp.layers
            for p in layer.transform
            if getattr(p, "keyframes", None)
            and len(p.keyframes) >= 2
            and not p.is_spatial
        )
        times = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]
        before = [prop.value_at_time(t) for t in times]
        mid = (prop.keyframes[0].time + prop.keyframes[1].time) / 2.0

        index = prop.add_key(mid)
        prop.remove_key(index)

        assert [prop.value_at_time(t) for t in times] == pytest.approx(before, abs=1e-6)
