"""Issue #225 review findings: keyframe evaluation in the layer's own time.

After Effects evaluates a temporal bezier in LAYER time - its ease speeds are
per layer second, and a negatively stretched layer's keyframes only ascend on
that axis. Evaluating in composition time instead put every stretched layer's
curve off by the stretch factor and stopped a reversed layer interpolating at
all.

Every expected number was measured in After Effects 2026 through `valueAtTime`
(or, for the roving times, AE's own placement of the same geometry). AE's
sampling is quoted in the docstrings so a future change can be judged against
it rather than against py's current output. The probes that produced them are
`scripts/jsx/stretch_ease_probe*.jsx`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import parse_app_fresh

import py_aep
from py_aep import KeyframeEase, KeyframeInterpolationType


def _new_comp(width: int = 200, height: int = 200, fps: float = 24.0):
    app = py_aep.new()
    comp = app.project.root_folder.add_comp("C", width, height, 1.0, 10.0, fps)
    return app, comp


def _bezier_both_sides(prop) -> None:
    for kf in prop.keyframes:
        kf.in_interpolation_type = KeyframeInterpolationType.BEZIER
        kf.out_interpolation_type = KeyframeInterpolationType.BEZIER


def _shape_fill_colour(comp):
    layer = comp.add_shape()
    contents = layer.property("Contents").add_property("ADBE Vector Group")
    inner = contents.property("Contents")
    inner.add_property("ADBE Vector Shape - Ellipse")
    return inner.add_property("ADBE Vector Graphic - Fill").property("Color")


class TestStretchedLayerEaseTimeBase:
    """The ease maths ran in composition time while the stored speeds are per
    layer second, so a stretched layer's curve was off by the stretch factor
    even though both endpoints landed exactly.

    AE 2026, Opacity 0 -> 100 authored at comp 0/2 with out ease 60/50 and in
    ease 20/75, then stretched: the same animation played slower or faster, so
    normalized to the key span the curve is identical at every stretch.
    """

    #: AE 2026 at 200 % - the keys move to comp 0 and 4.
    AE_200 = {0.0: 0.0, 1.0: 34.766915, 2.0: 72.382043, 3.0: 88.941757, 4.0: 100.0}
    #: AE 2026 at 50 % - the keys move to comp 0 and 1.
    AE_050 = {0.0: 0.0, 0.25: 34.766915, 0.5: 72.382043, 0.75: 88.941757, 1.0: 100.0}

    def _build(self, stretch: float):
        app, comp = _new_comp()
        layer = comp.add_solid([1, 0, 0], "L", 100, 100, 1.0)
        opacity = layer.property("Transform").property("Opacity")
        opacity.set_value_at_time(0.0, 0.0)
        opacity.set_value_at_time(2.0, 100.0)
        _bezier_both_sides(opacity)
        opacity.keyframes[0].out_temporal_ease = [
            KeyframeEase(speed=60.0, influence=50.0)
        ]
        opacity.keyframes[1].in_temporal_ease = [
            KeyframeEase(speed=20.0, influence=75.0)
        ]
        layer.stretch = stretch
        return app, opacity

    @pytest.mark.parametrize(
        "stretch, expected",
        [(200.0, AE_200), (50.0, AE_050)],
        ids=["stretch_200", "stretch_050"],
    )
    def test_matches_after_effects(
        self, stretch: float, expected: dict[float, float]
    ) -> None:
        _app, opacity = self._build(stretch)
        for time, value in expected.items():
            assert opacity.value_at_time(time) == pytest.approx(value, abs=1e-3)

    def test_unstretched_curve_is_unchanged(self) -> None:
        _app, opacity = self._build(100.0)
        # The 200 % readings, on the half-length span.
        for time, value in self.AE_050.items():
            assert opacity.value_at_time(time * 2.0) == pytest.approx(value, abs=1e-3)

    def test_survives_a_save_and_reparse(self, tmp_path: Path) -> None:
        app, _opacity = self._build(200.0)
        path = tmp_path / "stretched.aep"
        app.project.save(path)

        opacity = (
            parse_app_fresh(path)
            .project.compositions[0]
            .layers[0]
            .property("Transform")
            .property("Opacity")
        )
        for time, value in self.AE_200.items():
            assert opacity.value_at_time(time) == pytest.approx(value, abs=1e-3)


class TestNegativeStretchInterpolates:
    """A reversed layer's keyframes descend in composition time, so both
    boundary guards fired and the segment search was never reached: the layer
    held one value, jumped, and held the other.

    AE 2026, three LINEAR Opacity keys authored at comp 1/4/7 with values
    0/50/100 on a -150 % layer. AE indexes them in layer order, so
    `keyValue(1)` is the value-100 key sitting at comp 7.
    """

    AE = {0.0: 0.0, 1.0: 0.0, 2.5: 25.0, 4.0: 50.0, 5.5: 75.0, 7.0: 100.0, 8.0: 100.0}

    def _build(self):
        app, comp = _new_comp()
        layer = comp.add_solid([1, 0, 0], "L", 100, 100, 1.0)
        layer.stretch = -150.0
        opacity = layer.property("Transform").property("Opacity")
        opacity.set_value_at_time(1.0, 0.0)
        opacity.set_value_at_time(4.0, 50.0)
        opacity.set_value_at_time(7.0, 100.0)
        return app, opacity

    def test_keyframe_index_order_follows_the_layer(self) -> None:
        _app, opacity = self._build()
        assert [kf.time for kf in opacity.keyframes] == pytest.approx(
            [7.0, 4.0, 1.0], abs=1e-4
        )
        assert [kf.value for kf in opacity.keyframes] == [100.0, 50.0, 0.0]

    def test_interpolates_across_the_reversed_span(self) -> None:
        _app, opacity = self._build()
        for time, value in self.AE.items():
            assert opacity.value_at_time(time) == pytest.approx(value, abs=1e-3)


class TestLinearOutSideKeepsTheNextEase:
    """A LINEAR out side on a non-spatial property fell through to a straight
    lerp, discarding the NEXT key's in-side ease.

    AE stores a LINEAR side as a diagonal handle - speed equal to the chord
    slope, influence 100/6 - so the ordinary bezier path reproduces it.

    AE 2026, Opacity 0 -> 100 over comp 0..2 with key 1 LINEAR out and key 2
    BEZIER in at speed 0, influence 90.
    """

    AE = {0.0: 0.0, 0.5: 60.869573, 1.0: 87.520715, 1.5: 97.481984, 2.0: 100.0}

    def test_matches_after_effects(self) -> None:
        _app, comp = _new_comp()
        layer = comp.add_solid([1, 0, 0], "L", 100, 100, 1.0)
        opacity = layer.property("Transform").property("Opacity")
        opacity.set_value_at_time(0.0, 0.0)
        opacity.set_value_at_time(2.0, 100.0)
        opacity.keyframes[1].in_interpolation_type = KeyframeInterpolationType.BEZIER
        opacity.keyframes[1].in_temporal_ease = [
            KeyframeEase(speed=0.0, influence=90.0)
        ]
        opacity.keyframes[0].out_interpolation_type = KeyframeInterpolationType.LINEAR

        for time, value in self.AE.items():
            assert opacity.value_at_time(time) == pytest.approx(value, abs=1e-3)

    def test_linear_on_both_sides_is_still_a_straight_line(self) -> None:
        """The case where two defects used to cancel.

        A LINEAR/LINEAR segment on a stretched layer read correctly only
        because the lerp shortcut hid the comp-time ease maths. With the
        shortcut gone the stretch fix has to carry it: AE 2026 reads
        0/25/50/75/100 at comp 0..4 for keys authored at comp 0/2 on a
        layer then stretched to 200 %.
        """
        _app, comp = _new_comp()
        layer = comp.add_solid([1, 0, 0], "L", 100, 100, 1.0)
        opacity = layer.property("Transform").property("Opacity")
        opacity.set_value_at_time(0.0, 0.0)
        opacity.set_value_at_time(2.0, 100.0)
        layer.stretch = 200.0

        assert [kf.time for kf in opacity.keyframes] == pytest.approx([0.0, 4.0])
        for seconds in range(5):
            assert opacity.value_at_time(seconds) == pytest.approx(
                seconds * 25.0, abs=1e-3
            )


class TestLinearEaseSpeedIsLayerTime:
    """A LINEAR side's synthesized speed was the chord slope per COMPOSITION
    second, where AE stores it per layer second.

    AE 2026 reads 25 %/s back from three keys at comp 1/4/7 (values 0/50/100)
    on a 150 % layer - the span is 2 layer seconds, not 3 composition ones -
    and -25 %/s on a -150 % layer, where layer time runs backwards.
    """

    @pytest.mark.parametrize(
        "stretch, expected", [(100.0, 16.666667), (150.0, 25.0), (-150.0, -25.0)]
    )
    def test_speed_is_per_layer_second(self, stretch: float, expected: float) -> None:
        _app, comp = _new_comp()
        layer = comp.add_solid([1, 0, 0], "L", 100, 100, 1.0)
        layer.stretch = stretch
        opacity = layer.property("Transform").property("Opacity")
        opacity.set_value_at_time(1.0, 0.0)
        opacity.set_value_at_time(4.0, 50.0)
        opacity.set_value_at_time(7.0, 100.0)

        middle = opacity.keyframes[1]
        assert middle.out_temporal_ease[0].speed == pytest.approx(expected, abs=1e-3)
        assert middle.in_temporal_ease[0].speed == pytest.approx(expected, abs=1e-3)


class TestRovingRedistributionUnderStretch:
    """Roving times are derived in layer time but were written through a
    composition-time conversion, scaling the run by the stretch factor: on a
    200 % layer a roving key was written PAST its own end anchor, which
    re-sorted the property and stranded the roving flags.

    AE 2026 authoring the same geometry - four Position keys at comp 0/2/4/6
    on a 200 % layer, anchors eased 120/40 and 80/65, middle two roving -
    places the roving keys at 1.982869 and 2.956299.
    """

    AE_ROVING_TIMES = [1.982869, 2.956299]

    def _build(self, stretch: float):
        app, comp = _new_comp(400, 400)
        layer = comp.add_solid([1, 0, 0], "L", 100, 100, 1.0)
        layer.stretch = stretch
        position = layer.property("Transform").property("Position")
        for time, value in (
            (0.0, [50.0, 50.0, 0.0]),
            (2.0, [120.0, 250.0, 0.0]),
            (4.0, [260.0, 260.0, 0.0]),
            (6.0, [350.0, 60.0, 0.0]),
        ):
            position.set_value_at_time(time, value)
        _bezier_both_sides(position)
        position.keyframes[0].out_temporal_ease = [
            KeyframeEase(speed=120.0, influence=40.0)
        ]
        position.keyframes[3].in_temporal_ease = [
            KeyframeEase(speed=80.0, influence=65.0)
        ]
        return app, position

    def test_matches_after_effects_on_a_stretched_layer(self) -> None:
        _app, position = self._build(200.0)
        position.keyframes[1].roving = True
        position.keyframes[2].roving = True

        times = [kf.time for kf in position.keyframes]
        assert times[0] == pytest.approx(0.0)
        assert times[3] == pytest.approx(6.0)
        assert times[1:3] == pytest.approx(self.AE_ROVING_TIMES, abs=1e-4)

    @pytest.mark.parametrize("stretch", [100.0, 200.0, 50.0, -150.0])
    def test_roving_keys_stay_inside_their_run(self, stretch: float) -> None:
        _app, position = self._build(stretch)
        anchors = (position.keyframes[0].time, position.keyframes[3].time)
        position.keyframes[1].roving = True
        position.keyframes[2].roving = True

        assert [kf.roving for kf in position.keyframes] == [False, True, True, False]
        low, high = min(anchors), max(anchors)
        assert all(low <= kf.time <= high for kf in position.keyframes[1:3])
        layer_times = [kf._layer_time for kf in position.keyframes]
        assert layer_times == sorted(layer_times)

    def test_redistribution_persists_through_a_save(self, tmp_path: Path) -> None:
        app, position = self._build(200.0)
        position.keyframes[1].roving = True
        position.keyframes[2].roving = True
        path = tmp_path / "roving.aep"
        app.project.save(path)

        reparsed = (
            parse_app_fresh(path)
            .project.compositions[0]
            .layers[0]
            .property("Transform")
            .property("Position")
        )
        assert [kf.time for kf in reparsed.keyframes][1:3] == pytest.approx(
            self.AE_ROVING_TIMES, abs=1e-4
        )


class TestInertScaleDimension:
    """The absolute ease handles made a 2-D layer's Scale Z bow, where AE
    holds it flat. AE will not even STORE a Z other than 100 on a 2-D layer,
    so both keys always agree there; the third dimension only moves once the
    layer is 3-D.

    AE 2026, Scale X 100 -> 200 with Y and Z constant at 100, out ease 60/50
    and in ease 20/75.
    """

    #: AE 2026 on a 2-D layer: X and Y bow, Z is pinned.
    AE_2D = {
        0.5: [134.766915, 120.935113, 100.0],
        1.0: [172.382043, 101.423655, 100.0],
        1.5: [188.941757, 93.764502, 100.0],
    }

    def _build(self, three_d: bool):
        _app, comp = _new_comp(400, 400)
        layer = comp.add_solid([1, 0, 0], "L", 100, 100, 1.0)
        layer.three_d_layer = three_d
        scale = layer.property("Transform").property("Scale")
        scale.set_value_at_time(0.0, [100.0, 100.0, 100.0])
        scale.set_value_at_time(2.0, [200.0, 100.0, 100.0])
        _bezier_both_sides(scale)
        scale.keyframes[0].out_temporal_ease = [
            KeyframeEase(speed=60.0, influence=50.0)
        ] * 3
        scale.keyframes[1].in_temporal_ease = [
            KeyframeEase(speed=20.0, influence=75.0)
        ] * 3
        return scale

    def test_two_d_layer_holds_z(self) -> None:
        scale = self._build(three_d=False)
        for time, value in self.AE_2D.items():
            assert scale.value_at_time(time) == pytest.approx(value, abs=1e-3)

    def test_three_d_layer_bows_z_like_a_live_dimension(self) -> None:
        scale = self._build(three_d=True)
        value = scale.value_at_time(1.0)
        # AE 2026: with Z live it tracks Y exactly, both keys holding 100.
        assert value[2] == pytest.approx(value[1], abs=1e-6)
        assert value[2] == pytest.approx(101.423655, abs=1e-3)


class TestColourUsesOneSharedProgress:
    """A colour stores ONE ease and AE drives every channel with a single
    progress taken from the influences alone. Running a bezier per channel
    bowed the unchanged channels out of gamut - green read -0.0078 on a
    segment holding green at 0 in both keys.

    AE 2026, a shape Fill colour red -> blue with out ease 0.5/45 and in ease
    0.2/70: green and alpha stay exact, and red + blue always sum to 1.
    """

    AE = {
        0.5: [0.839653, 0.0, 0.160347, 1.0],
        1.0: [0.307084, 0.0, 0.692916, 1.0],
        1.5: [0.054479, 0.0, 0.945521, 1.0],
    }

    def _build(self):
        _app, comp = _new_comp(400, 400)
        colour = _shape_fill_colour(comp)
        colour.set_value_at_time(0.0, [1.0, 0.0, 0.0, 1.0])
        colour.set_value_at_time(2.0, [0.0, 0.0, 1.0, 1.0])
        colour.keyframes[0].out_temporal_ease = [
            KeyframeEase(speed=0.5, influence=45.0)
        ]
        colour.keyframes[1].in_temporal_ease = [KeyframeEase(speed=0.2, influence=70.0)]
        _bezier_both_sides(colour)
        return colour

    def test_matches_after_effects(self) -> None:
        colour = self._build()
        for time, value in self.AE.items():
            assert colour.value_at_time(time) == pytest.approx(value, abs=1e-3)

    def test_constant_channels_stay_in_gamut(self) -> None:
        colour = self._build()
        for frame in range(49):
            channels = colour.value_at_time(frame / 24.0)
            assert channels[1] == pytest.approx(0.0, abs=1e-6)
            assert channels[3] == pytest.approx(1.0, abs=1e-6)
            assert all(0.0 <= channel <= 1.0 for channel in channels)
