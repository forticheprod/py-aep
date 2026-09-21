"""Issue #225 item 4: keyframe ticks are in LAYER time, and the `tdb4`
timebase that counts them is a full 32-bit field.

Measured on After Effects 2026: keys authored at layer-seconds 1 / 4 / 7
on a 24 fps comp, then stretched, come back at these composition times -

    stretch   50 %   ->  0.5  / 2     / 3.5      tdb4 24576
    stretch  101 %   ->  1.01 / 4.04  / 7.07     tdb4 24821
    stretch  150 %   ->  1.5  / 6     / 10.5     tdb4 36864
    stretch  300 %   ->  3    / 12    / 21       tdb4 73728   (0x00012000)
    stretch -150 %   -> -1.5  / -6    / -10.5    tdb4 36864

73728 needs 17 bits, so the field cannot be the `u2` py_aep used to read -
the overflow landed in the two bytes it labelled padding.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from helpers import SAMPLES_DIR, parse_app_fresh

import py_aep

LAYER_DIR = SAMPLES_DIR / "models" / "layer"


def _opacity_with_keys(comp, stretch: float):
    layer = comp.add_solid([1, 0, 0], "L", 320, 240, 1.0)
    layer.stretch = stretch
    op = layer.property("Transform").property("Opacity")
    for t, v in ((1.0, 10.0), (4.0, 50.0), (7.0, 90.0)):
        op.set_value_at_time(t, v)
    return layer, op


class TestStretchedLayerTimebase:
    @pytest.mark.parametrize("stretch", [50.0, 101.0, 150.0, 300.0])
    def test_timebase_scales_with_stretch(self, stretch: float) -> None:
        app = py_aep.new()
        comp = app.project.root_folder.add_comp("C", 320, 240, 1.0, 40.0, 24.0)
        _layer, op = _opacity_with_keys(comp, stretch)

        want = math.floor(comp._cdta.internal_timebase * max(1.0, stretch / 100.0))
        assert op._tdb4._time_base == want

    def test_three_hundred_percent_needs_more_than_sixteen_bits(self) -> None:
        app = py_aep.new()
        comp = app.project.root_folder.add_comp("C", 320, 240, 1.0, 40.0, 24.0)
        _layer, op = _opacity_with_keys(comp, 300.0)

        assert op._tdb4._time_base == 73728
        assert op._tdb4._time_base > 0xFFFF

    @pytest.mark.parametrize("stretch", [50.0, 150.0, 300.0])
    def test_key_times_survive_a_roundtrip(
        self, stretch: float, tmp_path: Path
    ) -> None:
        """Keys written at composition time must read back at the same time."""
        app = py_aep.new()
        comp = app.project.root_folder.add_comp("C", 320, 240, 1.0, 40.0, 24.0)
        _layer, op = _opacity_with_keys(comp, stretch)
        assert [kf.time for kf in op.keyframes] == pytest.approx([1.0, 4.0, 7.0])

        out = tmp_path / "stretched.aep"
        app.project.save(out)

        app2 = parse_app_fresh(out)
        op2 = (
            app2.project.compositions[0]
            .layers[0]
            .property("Transform")
            .property("Opacity")
        )
        assert [kf.time for kf in op2.keyframes] == pytest.approx([1.0, 4.0, 7.0])

    def test_ticks_are_layer_time(self) -> None:
        """A 150 % layer stores half as many ticks per composition second."""
        app = py_aep.new()
        comp = app.project.root_folder.add_comp("C", 320, 240, 1.0, 40.0, 24.0)
        _layer, op = _opacity_with_keys(comp, 150.0)

        # comp second 1 -> layer second 1/1.5, at 36864 units per layer second
        assert op.keyframes[0]._ldat_item.time_units == 24576

    def test_ae_authored_stretched_layer_reads_back(self) -> None:
        """`layer_timing.aep` is AE-authored and carries a 200 % layer."""
        app = parse_app_fresh(LAYER_DIR / "layer_timing.aep")
        comp = next(c for c in app.project.compositions if c.name == "stretch_200")
        layer = comp.layers[0]
        assert layer.stretch == 200.0

        want = comp._cdta.internal_timebase * 2
        bases = {
            prop._tdb4._time_base
            for prop in layer
            if getattr(prop, "_tdb4", None) is not None
            and not prop._tdbs.synthetic
            and prop._tdb4._time_base
        }
        assert bases == {want}


class TestStretchRetimesKeyframes:
    """AE holds a keyframe at the same LAYER time across a stretch change and
    rescales the stored counts: keys at layer-seconds 1 and 5 on a 24 fps comp
    hold 24576 / 122880 ticks, and 49152 / 245760 against a tdb4 of 49152 once
    the layer is stretched to 200 % - composition seconds 2 and 10."""

    def _animated(self, fps: float = 24.0):
        app = py_aep.new()
        comp = app.project.root_folder.add_comp("C", 320, 240, 1.0, 40.0, fps)
        layer = comp.add_solid([1, 1, 1], "L", 320, 240, 1.0)
        op = layer.property("Transform").property("Opacity")
        op.set_value_at_time(1.0, 0.0)
        op.set_value_at_time(5.0, 100.0)
        return app, layer, op

    def test_ticks_and_timebase_match_after_effects(self) -> None:
        _app, layer, op = self._animated()
        assert [kf._ldat_item.time_units for kf in op.keyframes] == [24576, 122880]

        layer.stretch = 200.0

        assert op._tdb4._time_base == 49152
        assert [kf._ldat_item.time_units for kf in op.keyframes] == [49152, 245760]
        assert [kf.time for kf in op.keyframes] == pytest.approx([2.0, 10.0])

    def test_stretching_back_restores_the_times(self) -> None:
        _app, layer, op = self._animated()
        layer.stretch = 200.0
        layer.stretch = 100.0

        assert [kf.time for kf in op.keyframes] == pytest.approx([1.0, 5.0])

    def test_survives_a_roundtrip(self, tmp_path: Path) -> None:
        app, layer, op = self._animated()
        layer.stretch = 200.0

        out = tmp_path / "stretched.aep"
        app.project.save(out)

        op2 = (
            parse_app_fresh(out)
            .project.compositions[0]
            .layers[0]
            .property("Transform")
            .property("Opacity")
        )
        assert [kf.time for kf in op2.keyframes] == pytest.approx([2.0, 10.0])
        assert [kf._ldat_item.time_units for kf in op2.keyframes] == [49152, 245760]


class TestNegativeStretchOffset:
    """A reversed layer starts a hair before its nominal start. AE 2026 offsets
    it by `|stretch| / 100 / 3000` seconds - measured at -50 / -100 / -150 /
    -200 % and 24 / 25 / 30 fps, twelve readings, all matching and frame-rate
    independent. Keys authored at layer-seconds 1 and 4, startTime 0:

        -50 %  -> -0.5001667 / -2.0001667
        -100 % -> -1.0003333 / -4.0003333
        -150 % -> -1.5005000 / -6.0005000
        -200 % -> -2.0006667 / -8.0006667
    """

    AE = {
        -50.0: [-0.5001667, -2.0001667],
        -100.0: [-1.0003333, -4.0003333],
        -150.0: [-1.5005000, -6.0005000],
        -200.0: [-2.0006667, -8.0006667],
    }

    @pytest.mark.parametrize("fps", [24.0, 25.0, 30.0])
    @pytest.mark.parametrize("stretch", [-50.0, -100.0, -150.0, -200.0])
    def test_key_times_match_after_effects(self, stretch: float, fps: float) -> None:
        app = py_aep.new()
        comp = app.project.root_folder.add_comp("C", 320, 240, 1.0, 60.0, fps)
        layer = comp.add_solid([1, 1, 1], "L", 320, 240, 1.0)
        op = layer.property("Transform").property("Opacity")
        # Author while unstretched so the ticks land on layer-seconds 1 and 4,
        # then reverse - the order AE's probe used.
        op.set_value_at_time(1.0, 10.0)
        op.set_value_at_time(4.0, 90.0)
        layer.stretch = stretch

        got = [kf.time for kf in op.keyframes]
        assert got == pytest.approx(self.AE[stretch], abs=1e-6)

    def test_positive_stretch_has_no_offset(self) -> None:
        app = py_aep.new()
        comp = app.project.root_folder.add_comp("C", 320, 240, 1.0, 60.0, 24.0)
        layer = comp.add_solid([1, 1, 1], "L", 320, 240, 1.0)
        op = layer.property("Transform").property("Opacity")
        op.set_value_at_time(1.0, 10.0)
        op.set_value_at_time(4.0, 90.0)
        layer.stretch = 150.0

        assert [kf.time for kf in op.keyframes] == pytest.approx([1.5, 6.0])


class TestValueAtTimeRejectsNaN:
    """AE 2026: `valueAtTime(NaN)` throws "NaN is not a number"; infinity is
    accepted and evaluates to the last keyframe."""

    def _animated(self):
        app = py_aep.new()
        comp = app.project.root_folder.add_comp("C", 200, 200, 1.0, 10.0, 24.0)
        layer = comp.add_solid([1, 0, 0], "L", 100, 100, 1.0)
        op = layer.property("Transform").property("Opacity")
        op.set_value_at_time(0.0, 0.0)
        op.set_value_at_time(2.0, 100.0)
        return op

    def test_nan_raises(self) -> None:
        op = self._animated()
        with pytest.raises(ValueError, match="NaN"):
            op.value_at_time(float("nan"))

    def test_infinity_still_evaluates(self) -> None:
        op = self._animated()
        assert op.value_at_time(float("inf")) == pytest.approx(100.0)
