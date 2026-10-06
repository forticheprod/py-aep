"""Regression tests for the v9 fuzz findings on keyframe interpolation.

After Effects numbers below were measured on AE 2026 running the same
scripted operations (`setValueAtTime`, `setTemporalEaseAtKey`,
`setInterpolationTypeAtKey`, ...) on layers of the same size in a comp of the
same size, pixel aspect and frame rate, then reading `valueAtTime` and the key
attributes back. Comps are 1920x1080 at 24 fps unless stated.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest
from helpers import project_bytes

import py_aep
from py_aep import KeyframeEase, Shape, parse
from py_aep import KeyframeInterpolationType as KIT

TG = "ADBE Transform Group"
LIN, BEZ, HOLD = KIT.LINEAR, KIT.BEZIER, KIT.HOLD


SAMPLES = Path(__file__).parent.parent.parent / "samples"


def _leaves(group: Any) -> list[Any]:
    out = []
    for prop in group.properties:
        out.extend(_leaves(prop) if hasattr(prop, "properties") else [prop])
    return out


def _comp(
    width: int = 1920, height: int = 1080, par: float = 1.0, fps: float = 24.0
) -> tuple[py_aep.Application, Any]:
    app = py_aep.new()
    comp = app.project.root_folder.add_comp("C", width, height, par, 10.0, fps)
    return app, comp


def _solid(comp: Any, w: int = 200, h: int = 100, three_d: bool = False) -> Any:
    layer = comp.add_solid([1.0, 0.0, 0.0], "L", w, h, 1.0)
    if three_d:
        layer.three_d_layer = True
    return layer


def _effect(layer: Any, effect: str) -> Any:
    return layer.effects.add_property(effect).property(f"{effect}-0001")


def _keys(prop: Any, keys: list[tuple[float, Any]]) -> Any:
    for t, v in keys:
        prop.set_value_at_time(t, v)
    return prop


def _ease(kf: Any, in_ease: list[list[float]], out_ease: list[list[float]]) -> None:
    kf.in_temporal_ease = [KeyframeEase(s, i) for s, i in in_ease]
    kf.out_temporal_ease = [KeyframeEase(s, i) for s, i in out_ease]


def _types(kf: Any, in_type: KIT, out_type: KIT) -> None:
    kf.in_interpolation_type = in_type
    kf.out_interpolation_type = out_type


def _flat(value: Any) -> list[float]:
    if isinstance(value, (list, tuple)):
        return [x for item in value for x in _flat(item)]
    return [value]


def _speeds(eases: list[KeyframeEase]) -> list[float]:
    return _flat([[e.speed, e.influence] for e in eases])


def _verts(shape: Any) -> list[float]:
    return _flat([list(v) for v in shape.vertices])


def _reparse(app: py_aep.Application, tmp_path: Path) -> Any:
    path = tmp_path / "out.aep"
    app.project.save(path)
    comp = next(c for c in parse(path).project.compositions if c.name == "C")
    return next(lyr for lyr in comp.layers if lyr.name == "L")


def _reparse_comp(app: py_aep.Application, tmp_path: Path) -> Any:
    path = tmp_path / "out.aep"
    app.project.save(path)
    return next(c for c in parse(path).project.compositions if c.name == "C")


def _approx(value: Any, abs: float = 1e-6) -> Any:
    return pytest.approx(_flat(value) if isinstance(value, list) else value, abs=abs)


class TestFootageAnchorPointZ:
    """F1: a footage layer's Anchor Point Z is stored in layer heights."""

    def test_static_z_normalized_by_height(self, tmp_path: Path) -> None:
        # AE 2026 writes [100, 50, 80] on a 400x300 3-D solid as
        # [100 / 400, 50 / 300, 80 / 300].
        app, comp = _comp()
        layer = _solid(comp, 400, 300, three_d=True)
        anchor = layer[TG]["ADBE Anchor Point"]
        anchor.value = [100, 50, 80]
        assert anchor._cdat.values[:3] == _approx([0.25, 50 / 300, 80 / 300])
        assert anchor.value == _approx([100.0, 50.0, 80.0])
        again = _reparse(app, tmp_path)[TG]["ADBE Anchor Point"]
        assert again.value == _approx([100.0, 50.0, 80.0])


class TestTemporalAutoBezierParallelKinds:
    """F2 / F3: temporal auto-bezier on a path or an Orientation key."""

    def test_mask_path_auto_bezier(self) -> None:
        # AE 2026: keys report speed 1; the in-between shapes below.
        _app, comp = _comp()
        layer = _solid(comp, 3000, 200)
        path = layer.masks.add_property("ADBE Mask Atom")["ADBE Mask Shape"]
        _keys(
            path,
            [
                (0, Shape([[0, 0], [100, 0], [100, 100]], closed=True)),
                (1, Shape([[20, 10], [150, 0], [120, 140]], closed=True)),
                (2, Shape([[50, 50], [160, 30], [100, 180]], closed=True)),
            ],
        )
        kf = path.keyframes[1]
        kf.temporal_auto_bezier = True
        assert kf.temporal_continuous is True
        assert _speeds(kf.in_temporal_ease) == _approx([[1.0, 100 / 6]])
        assert _speeds(kf.out_temporal_ease) == _approx([[1.0, 100 / 6]])
        assert _verts(path.value_at_time(0.5)) == _approx(
            [[10, 5], [125, 0], [110, 120]], abs=1e-4
        )
        assert _verts(path.value_at_time(1.5)) == _approx(
            [[35, 30], [155, 15], [110, 160]], abs=1e-4
        )

    def test_orientation_auto_bezier(self) -> None:
        _app, comp = _comp()
        layer = _solid(comp, 400, 300, three_d=True)
        orient = _keys(
            layer[TG]["ADBE Orientation"],
            [(0, [0, 0, 0]), (1, [40, 30, 20]), (2, [90, 10, 300])],
        )
        kf = orient.keyframes[1]
        kf.temporal_auto_bezier = True
        assert _speeds(kf.in_temporal_ease) == _approx([[1.0, 100 / 6]])
        assert orient.value_at_time(1.208333333) == _approx(
            [52.6749651539118, 31.754058708850526, 1.4806168873979855], abs=1e-4
        )


class TestInterpolationTypeWinsOverAutoBezier:
    """F4: a LINEAR / HOLD side wins over temporal auto-bezier."""

    def test_linear_sides_on_auto_bezier_key(self) -> None:
        _app, comp = _comp()
        slider = _keys(
            _effect(_solid(comp), "ADBE Slider Control"),
            [(0, 0), (1, 100), (2.5, 20)],
        )
        kf = slider.keyframes[1]
        kf.temporal_auto_bezier = True
        _types(kf, LIN, LIN)
        assert kf.temporal_auto_bezier is True
        assert kf.temporal_continuous is False
        assert slider.value_at_time(0.375) == _approx(37.5)
        assert slider.value_at_time(1.5) == _approx(73.33333333333334)
        assert kf.in_temporal_ease[0].speed == _approx(100.0)
        assert kf.out_temporal_ease[0].speed == _approx(-53.333333333333336)

    def test_bezier_side_of_last_key_facing_linear(self) -> None:
        # AE 2026: the BEZIER in side of an auto-bezier LAST key whose out
        # side is LINEAR reports speed 0.
        _app, comp = _comp()
        angle = _keys(
            _effect(_solid(comp), "ADBE Angle Control"),
            [(0, 0), (1, 50), (2, 200)],
        )
        kf = angle.keyframes[2]
        kf.temporal_auto_bezier = True
        _types(kf, BEZ, LIN)
        assert (kf.temporal_auto_bezier, kf.temporal_continuous) == (True, True)
        assert kf.in_temporal_ease[0].speed == _approx(0.0)
        assert angle.value_at_time(1.583333333) == _approx(147.93916302166082)


class TestInHoldSegments:
    """F5: an in-HOLD key holds the segment START value."""

    def test_colour(self) -> None:
        _app, comp = _comp()
        color = _keys(
            _effect(_solid(comp, 3000, 200), "ADBE Color Control"),
            [(0, [1, 0, 0, 1]), (1, [0, 0.5, 1, 1]), (2, [0.2, 1, 0.3, 1])],
        )
        _types(color.keyframes[1], HOLD, HOLD)
        assert color.value_at_time(0.5) == _approx([1.0, 0.0, 0.0, 1.0])

    def test_orientation(self) -> None:
        _app, comp = _comp()
        null = comp.add_null()
        null.three_d_layer = True
        orient = _keys(
            null[TG]["ADBE Orientation"],
            [(0, [0, 0, 0]), (1, [40, 30, 20]), (2, [90, 10, 300])],
        )
        _types(orient.keyframes[1], HOLD, HOLD)
        assert orient.value_at_time(0.5) == _approx([0.0, 0.0, 0.0])

    def test_mask_path(self) -> None:
        _app, comp = _comp()
        path = _solid(comp).masks.add_property("ADBE Mask Atom")["ADBE Mask Shape"]
        _keys(
            path,
            [
                (0, Shape([[0, 0], [100, 0], [100, 100]], closed=True)),
                (1, Shape([[20, 10], [150, 0], [120, 140]], closed=True)),
                (2, Shape([[50, 50], [160, 30], [100, 180]], closed=True)),
            ],
        )
        _types(path.keyframes[1], HOLD, HOLD)
        assert _verts(path.value_at_time(0.5)) == _approx(
            [[0, 0], [100, 0], [100, 100]]
        )


class TestColourModel:
    """F6: colour eases move along the RGBA line, scaled by its length."""

    KEYS = [(0, [1, 0, 0, 1]), (2, [0, 0.5, 1, 1])]

    def _color(self) -> Any:
        _app, comp = _comp()
        return _keys(_effect(_solid(comp), "ADBE Color Control"), self.KEYS)

    def test_linear_reports_distance_speed(self) -> None:
        color = self._color()
        # AE 2026: |RGBA delta| * 255 / 2 s
        assert _speeds(color.keyframes[0].out_temporal_ease) == _approx(
            [[191.25, 100 / 6]]
        )
        assert color.value_at_time(0.5) == _approx([0.75, 0.125, 0.25, 1.0])

    def test_bezier_into_linear(self) -> None:
        color = self._color()
        _ease(color.keyframes[0], [[0, 80]], [[0, 80]])
        _types(color.keyframes[1], LIN, LIN)
        assert color.value_at_time(1.708333333) == _approx(
            [0.3087938606486835, 0.34560306967565824, 0.6912061393513165, 1.0]
        )
        assert _speeds(color.keyframes[1].in_temporal_ease) == _approx(
            [[191.25, 100 / 6]]
        )

    def test_non_zero_speeds(self) -> None:
        color = self._color()
        for kf in color.keyframes:
            _types(kf, BEZ, BEZ)
        _ease(color.keyframes[0], [[0, 30]], [[60, 50]])
        _ease(color.keyframes[1], [[40, 40]], [[0, 30]])
        assert color.value_at_time(0.625) == _approx(
            [0.7876151810347797, 0.10619240948261015, 0.2123848189652203, 1.0]
        )


class TestRangeClamp:
    """F7: an eased overshoot evaluates clamped to the property range."""

    def test_opacity(self) -> None:
        _app, comp = _comp()
        op = _keys(_solid(comp, 640, 360)[TG]["ADBE Opacity"], [(0, 10), (2, 90)])
        _ease(op.keyframes[0], [[0, 60]], [[300, 60]])
        _ease(op.keyframes[1], [[300, 60]], [[0, 60]])
        assert op.value_at_time(1.166666667) == 0.0

    def test_mask_feather_and_expansion(self) -> None:
        _app, comp = _comp()
        mask = _solid(comp, 3000, 200).masks.add_property("ADBE Mask Atom")
        feather = _keys(mask["ADBE Mask Feather"], [(0, [10, 10]), (2, [50, 60])])
        _ease(feather.keyframes[0], [[0, 30], [0, 30]], [[-300, 60], [200, 60]])
        assert feather.value_at_time(0.25) == _approx([0.0, 55.58876065072549])
        expansion = _keys(mask["ADBE Mask Offset"], [(0, 10), (2, 20)])
        _ease(expansion.keyframes[0], [[0, 30]], [[-90000, 60]])
        assert expansion.value_at_time(0.958333333) == -32000.0


class TestRejectedWritesDoNotMutate:
    """F8: a rejected keyframe value leaves the project untouched."""

    def test_nan_value(self) -> None:
        app, comp = _comp()
        rot = _solid(comp)[TG]["ADBE Rotate Z"]
        rot.value = 45.0
        before = project_bytes(app.project)
        with pytest.raises(ValueError):
            rot.set_value_at_time(1.0, float("nan"))
        assert project_bytes(app.project) == before
        assert rot.keyframes == [] and rot.value == 45.0

    def test_add_key_at_overshoot_stores_clamped(self, tmp_path: Path) -> None:
        # AE 2026 stores the clamped 100 and re-eases both neighbours.
        app, comp = _comp()
        op = _keys(_solid(comp)[TG]["ADBE Opacity"], [(0, 10), (2, 90)])
        for kf in op.keyframes:
            _types(kf, BEZ, BEZ)
        _ease(op.keyframes[0], [[0, 60]], [[300, 60]])
        op.add_key(0.5)
        new = op.keyframes[1]
        assert new.value == 100.0
        assert _speeds(new.in_temporal_ease) == _approx(
            [[179.0396178959919, 31.451892294166527]]
        )
        assert _speeds(new.out_temporal_ease) == _approx(
            [[179.03961789599282, 61.1377297149683]]
        )
        assert _speeds(op.keyframes[0].out_temporal_ease) == _approx(
            [[300.0, 35.131134850035764]]
        )
        again = _reparse(app, tmp_path)[TG]["ADBE Opacity"]
        assert [k.value for k in again.keyframes] == [10.0, 100.0, 90.0]


class TestEaseAndTangentWrites:
    """F9: what an ease or tangent write does to the key's other state."""

    def test_ease_on_linear_key_turns_it_bezier(self) -> None:
        _app, comp = _comp()
        op = _keys(_solid(comp)[TG]["ADBE Opacity"], [(0, 10), (2, 90)])
        _ease(op.keyframes[0], [[0, 75]], [[0, 75]])
        kf = op.keyframes[0]
        assert (kf.in_interpolation_type, kf.out_interpolation_type) == (BEZ, BEZ)
        assert _speeds(kf.out_temporal_ease) == _approx([[0.0, 75.0]])
        assert op.value_at_time(0.625) == _approx(14.649138906616496)
        assert _speeds(op.keyframes[1].in_temporal_ease) == _approx([[40.0, 100 / 6]])

    def test_ease_clears_temporal_auto_bezier(self) -> None:
        _app, comp = _comp()
        rot = _keys(_solid(comp)[TG]["ADBE Rotate Z"], [(0, 0), (1, 100), (2, 0)])
        kf = rot.keyframes[1]
        kf.temporal_auto_bezier = True
        _ease(kf, [[30, 50]], [[30, 50]])
        assert (kf.temporal_auto_bezier, kf.temporal_continuous) == (False, True)
        assert _speeds(kf.in_temporal_ease) == _approx([[30.0, 50.0]])
        assert rot.value_at_time(0.5) == _approx(65.31929354403154)

    def test_tangent_clears_spatial_auto_bezier(self) -> None:
        _app, comp = _comp()
        pos = _keys(
            _solid(comp)[TG]["ADBE Position"],
            [(0, [100, 100, 0]), (1, [300, 200, 0]), (2, [600, 100, 0])],
        )
        kf = pos.keyframes[1]
        kf.spatial_auto_bezier = True
        kf.in_spatial_tangent = [-50, 30, 0]
        kf.out_spatial_tangent = [50, -30, 0]
        assert kf.spatial_auto_bezier is False
        assert kf.in_spatial_tangent == _approx([-50, 30, 0])
        assert pos.value_at_time(0.5) == _approx(
            [192.98553351245596, 168.76659157486122, 0.0], abs=1e-4
        )
        assert pos.keyframes[0].out_temporal_ease[0].speed == _approx(
            231.49629625710023, abs=1e-4
        )
        assert kf.out_temporal_ease[0].speed == _approx(316.60351480214035, abs=1e-4)


class TestLinearSpatialSpeed:
    """F10: a LINEAR spatial side reports arc length over time, not chord."""

    def test_curved_segment(self) -> None:
        _app, comp = _comp()
        pos = _keys(
            _solid(comp)[TG]["ADBE Position"], [(0, [100, 100, 0]), (2, [500, 100, 0])]
        )
        pos.keyframes[0].out_spatial_tangent = [100, 200, 0]
        pos.keyframes[1].in_spatial_tangent = [-100, 200, 0]
        assert pos.keyframes[0].out_temporal_ease[0].speed == _approx(
            263.4149868402037, abs=1e-4
        )
        assert pos.value_at_time(0.5) == _approx(
            [179.4680619443759, 203.85330816260333, 0.0], abs=1e-4
        )

    def test_zero_chord_segment(self) -> None:
        _app, comp = _comp()
        pos = _keys(
            comp.add_null()[TG]["ADBE Position"],
            [(0, [100, 100, 0]), (1, [100, 100, 0]), (2, [300, 100, 0])],
        )
        pos.keyframes[0].out_spatial_tangent = [80, 120, 0]
        pos.keyframes[1].in_spatial_tangent = [-60, 90, 0]
        assert pos.keyframes[0].out_temporal_ease[0].speed == _approx(
            188.63091379888618, abs=1e-4
        )
        assert pos.keyframes[1].out_temporal_ease[0].speed == _approx(200.0)
        assert pos.value_at_time(0.5) == _approx(
            [109.69902653105451, 179.08373632542654, 0.0], abs=1e-4
        )


class TestBezierSideFacingHold:
    """F11: a BEZIER side facing a HOLD side reports speed 0."""

    def test_speeds(self) -> None:
        _app, comp = _comp()
        rot = _keys(_solid(comp)[TG]["ADBE Rotate Z"], [(0, 0), (1, 100), (2, 300)])
        _types(rot.keyframes[1], HOLD, HOLD)
        _ease(rot.keyframes[0], [[0, 30]], [[200, 40]])
        _ease(rot.keyframes[2], [[150, 30]], [[0, 30]])
        assert _speeds(rot.keyframes[0].out_temporal_ease) == _approx([[0.0, 40.0]])
        assert _speeds(rot.keyframes[2].in_temporal_ease) == _approx([[0.0, 30.0]])
        assert rot.value_at_time(0.5) == _approx(100.0)


ROVING_KEYS = [
    (0, [100, 100, 0]),
    (1, [300, 150, 0]),
    (2, [350, 400, 0]),
    (3, [500, 420, 0]),
    (5, [800, 300, 0]),
]


def _roving_run(comp: Any) -> Any:
    pos = _keys(comp.add_null()[TG]["ADBE Position"], ROVING_KEYS)
    pos.keyframes[1].roving = True
    pos.keyframes[2].roving = True
    return pos


class TestRovingRunAfterHoldAnchor:
    """A roving run leaving an out-HOLD anchor: AE 2026 packs the run against
    the anchor, reports every in side of the run as 0 and keeps the run's
    speed on the out sides. Comp 640x480, square pixels, 25 fps."""

    def test_speeds_and_times(self) -> None:
        _app, comp = _comp(640, 480, 1.0, 25.0)
        pos = _roving_run(comp)
        _types(pos.keyframes[0], HOLD, HOLD)
        k = pos.keyframes
        assert [k[i].time for i in (1, 2)] == _approx([3.90625e-05, 7.8125e-05])
        assert [k[i].in_temporal_ease[0].speed for i in (1, 2, 3)] == [0.0] * 3
        for i in (1, 2):
            assert k[i].out_temporal_ease[0].speed == _approx(
                204.14457215491265, abs=1e-4
            )
        assert k[3].out_temporal_ease[0].speed == _approx(161.55494421403515)


class TestRovingRunRetimedByAnchorEase:
    """An anchor's ease decides where its roving run's keys fall, so writing
    it re-times the run. AE 2026 re-timed py's saved file to these times.
    Comp 1000x800, 10/11 pixel aspect, 29.97 fps."""

    def test_eased_anchor(self, tmp_path: Path) -> None:
        app, comp = _comp(1000, 800, 10 / 11, 29.97)
        pos = _roving_run(comp)
        pos.keyframes[3].spatial_auto_bezier = True
        _ease(pos.keyframes[0], [[0, 80]], [[0, 80]])
        want = [1.9925759092425759, 2.6412245578912246]
        assert [k.time for k in pos.keyframes[1:3]] == _approx(want)
        comp_again = _reparse_comp(app, tmp_path)
        again = comp_again.layers[0][TG]["ADBE Position"]
        assert [k.time for k in again.keyframes[1:3]] == _approx(want)

    def test_auto_bezier_anchors(self) -> None:
        _app, comp = _comp(1000, 800, 10 / 11, 29.97)
        pos = _roving_run(comp)
        pos.keyframes[0].temporal_auto_bezier = True
        pos.keyframes[3].temporal_auto_bezier = True
        assert [k.time for k in pos.keyframes[1:3]] == _approx(
            [0.9633383383383384, 2.267559225892559]
        )


class TestTwoDimensionalLayerZ:
    """F12: a 2-D layer's Position evaluates with Z = 0, while the stored Z
    still counts in the path length."""

    def test_value_at_time(self) -> None:
        _app, comp = _comp()
        pos = _keys(
            comp.add_null()[TG]["ADBE Position"],
            [(0, [100, 100, 40]), (2, [500, 300, -30])],
        )
        assert pos.value_at_time(1.0) == _approx(
            [299.99689058473786, 199.99844529236896, 0.0], abs=1e-4
        )
        assert pos.keyframes[0].out_temporal_ease[0].speed == _approx(
            226.32940595512554, abs=1e-4
        )

    def test_key_and_static_values(self, tmp_path: Path) -> None:
        # AE 2026 reports Z = 0 in keyValue and value, keeps the stored Z in
        # the file, and addKey stores the interpolated stored Z (5.0005).
        app, comp = _comp()
        null = comp.add_null()
        null.name = "L"
        pos = _keys(
            null[TG]["ADBE Position"], [(0, [100, 100, 40]), (2, [500, 300, -30])]
        )
        pos.add_key(1.0)
        assert _flat([k.value for k in pos.keyframes]) == _approx(
            [
                [100, 100, 0],
                [299.996890584738, 199.998445292369, 0],
                [500, 300, 0],
            ],
            abs=1e-6,
        )
        assert pos.keyframes[1]._stored_value[2] == _approx(5.0005441476708805)
        anchor = null[TG]["ADBE Anchor Point"]
        anchor.value = [30, 20, 15]
        assert anchor.value == [30.0, 20.0, 0.0]
        again = _reparse(app, tmp_path)[TG]
        assert again["ADBE Anchor Point"]._stored_static_value() == [30, 20, 15]
        stored = [k._stored_value[2] for k in again["ADBE Position"].keyframes]
        assert stored == _approx([40.0, 5.0005441476708805, -30.0])

    def test_three_d_layer_keeps_z(self) -> None:
        _app, comp = _comp()
        pos = _solid(comp, three_d=True)[TG]["ADBE Position"]
        pos.value = [100, 120, 40]
        assert pos.value == [100.0, 120.0, 40.0]


class TestAddKeyOnMixedSegment:
    """F13 / F22: add_key on a LINEAR <-> BEZIER segment. AE turns the LINEAR
    side BEZIER with the segment's slope, then splits the curve. Comp
    1000x800, 10/11 pixel aspect, 29.97 fps."""

    def _slider(self) -> Any:
        _app, comp = _comp(1000, 800, 10 / 11, 29.97)
        return _keys(_effect(_solid(comp), "ADBE Slider Control"), [(0, 0), (2, 100)])

    def test_linear_into_bezier(self) -> None:
        slider = self._slider()
        _types(slider.keyframes[1], BEZ, BEZ)
        _ease(slider.keyframes[1], [[10, 40]], [[10, 40]])
        _types(slider.keyframes[0], LIN, LIN)
        before = slider.value_at_time(1.0)
        slider.add_key(0.7)
        k0, new, k2 = slider.keyframes
        assert (k0.in_interpolation_type, k0.out_interpolation_type) == (LIN, BEZ)
        assert _speeds(k0.out_temporal_ease) == _approx([[50.0, 20.98365339077507]])
        assert new.time == _approx(0.6999916583249917)
        assert new.value == _approx(45.426218155783275)
        assert _speeds(new.in_temporal_ease) == _approx(
            [[63.91994615492312, 43.23832887782448]]
        )
        assert _speeds(new.out_temporal_ease) == _approx(
            [[63.91994615492219, 29.553090510920317]]
        )
        assert _speeds(k2.in_temporal_ease) == _approx([[10.0, 34.42122712821061]])
        assert slider.value_at_time(1.0) == _approx(63.5560834013245)
        assert slider.value_at_time(1.0) == _approx(before)

    def test_bezier_into_linear(self) -> None:
        slider = self._slider()
        _types(slider.keyframes[0], BEZ, BEZ)
        _types(slider.keyframes[1], LIN, LIN)
        _ease(slider.keyframes[0], [[20, 60]], [[20, 60]])
        _types(slider.keyframes[1], BEZ, LIN)
        slider.add_key(0.7)
        k0, new, k2 = slider.keyframes
        assert _speeds(k0.out_temporal_ease) == _approx([[20.0, 36.03513774186484]])
        assert new.value == _approx(20.83860947763496)
        assert _speeds(new.in_temporal_ease) == _approx(
            [[39.64385120503754, 30.454616112180773]]
        )
        assert _speeds(new.out_temporal_ease) == _approx(
            [[39.643851205037365, 61.613775791779005]]
        )
        assert (k2.in_interpolation_type, k2.out_interpolation_type) == (BEZ, LIN)
        assert slider.value_at_time(1.0) == _approx(34.040679048187606)


class TestMaskPathAddKey:
    """F14: add_key between two path keys inserts the in-between shape.
    Comp 640x480, 1.5 pixel aspect, 25 fps."""

    def test_in_between_shape(self, tmp_path: Path) -> None:
        app, comp = _comp(640, 480, 1.5, 25.0)
        path = _solid(comp).masks.add_property("ADBE Mask Atom")["ADBE Mask Shape"]
        _keys(
            path,
            [
                (0, Shape([[0, 0], [100, 0], [100, 100]], closed=True)),
                (2, Shape([[20, 10], [150, 0], [120, 140]], closed=True)),
            ],
        )
        path.add_key(0.7)
        want = [[7.0, 3.5], [117.5, 0.0], [107.0, 114.0]]
        assert _verts(path.keyframes[1].value) == _approx(want, abs=1e-3)
        again = _reparse(app, tmp_path).masks.properties[0]["ADBE Mask Shape"]
        assert _verts(again.keyframes[1].value) == _approx(want, abs=1e-3)


TRI0 = Shape([[0, 0], [100, 0], [100, 100]], closed=True)
TRI1 = Shape([[20, 10], [150, 0], [120, 140]], closed=True)
_T = {"L": LIN, "B": BEZ, "H": HOLD}


class TestParallelAddKeyTypes:
    """add_key on a path or an Orientation: AE 2026 gives the new key types
    from the key sides facing it (left key's out, right key's in) and does
    not touch the neighbours. Any BEZIER makes a continuous BEZIER key with
    speed 1 / influence 16.667 (speed 0 outside the keyed range)."""

    @staticmethod
    def _path(keys: list[tuple[float, Any]]) -> Any:
        _app, comp = _comp()
        path = _solid(comp).masks.add_property("ADBE Mask Atom")["ADBE Mask Shape"]
        return _keys(path, keys)

    @pytest.mark.parametrize(
        ("left_out", "right_in", "new_types", "continuous"),
        [
            ("L", "L", "LL", False),
            ("L", "B", "BB", True),
            ("L", "H", "LH", False),
            ("B", "L", "BB", True),
            ("B", "B", "BB", True),
            ("B", "H", "BB", True),
            ("H", "L", "HH", False),
            ("H", "B", "BB", True),
            ("H", "H", "HH", False),
        ],
    )
    def test_inside_the_keyed_range(
        self, left_out: str, right_in: str, new_types: str, continuous: bool
    ) -> None:
        path = self._path([(0, TRI0), (2, TRI1)])
        _types(path.keyframes[0], LIN, _T[left_out])
        _types(path.keyframes[1], _T[right_in], LIN)
        path.add_key(0.6)
        k0, new, k2 = path.keyframes
        assert (new.in_interpolation_type, new.out_interpolation_type) == (
            _T[new_types[0]],
            _T[new_types[1]],
        )
        assert new.temporal_continuous is continuous
        assert k0.out_interpolation_type == _T[left_out]
        assert k2.in_interpolation_type == _T[right_in]
        if continuous:
            data = new._ldat_item.kf_data
            assert (data.in_speed, data.out_speed) == (1.0, 1.0)
            assert data.in_influence == _approx(1 / 6)

    def test_outside_the_keyed_range(self) -> None:
        path = self._path([(1, TRI0), (2, TRI1)])
        for kf in path.keyframes:
            _types(kf, BEZ, BEZ)
        path.add_key(0.4)
        new = path.keyframes[0]
        assert (new.in_interpolation_type, new.out_interpolation_type) == (BEZ, BEZ)
        assert new.temporal_continuous is True
        assert _speeds(new.out_temporal_ease) == _approx([0.0, 100 / 6])
        held = self._path([(0, TRI0), (1, TRI1)])
        _types(held.keyframes[1], HOLD, HOLD)
        held.add_key(2.0)
        last = held.keyframes[2]
        assert (last.in_interpolation_type, last.out_interpolation_type) == (
            HOLD,
            HOLD,
        )

    def test_orientation(self, tmp_path: Path) -> None:
        app, comp = _comp()
        orient = _keys(
            _solid(comp, 400, 300, three_d=True)[TG]["ADBE Orientation"],
            [(0, [0, 0, 0]), (2, [40, 30, 20])],
        )
        for kf in orient.keyframes:
            _types(kf, BEZ, BEZ)
        _ease(orient.keyframes[0], [[0, 30]], [[0, 70]])
        orient.add_key(0.6)
        new = orient.keyframes[1]
        assert (new.in_interpolation_type, new.temporal_continuous) == (BEZ, True)
        assert _speeds(new.in_temporal_ease) == _approx([1.0, 100 / 6])
        assert _speeds(orient.keyframes[0].out_temporal_ease) == _approx([0.0, 70.0])
        again = _reparse(app, tmp_path)[TG]["ADBE Orientation"].keyframes[1]
        assert (again.out_interpolation_type, again.temporal_continuous) == (BEZ, True)


class TestQueryTimeQuantization:
    """F15: AE snaps the query time to the layer's tick grid (comp time, then
    the layer time it maps to). LINEAR opacity 0 -> 100 over 4 s."""

    #: (stretch, {comp time: AE value})
    CASES = [
        (
            150,
            {
                0.001: 0.025431315104166668,
                0.021480183919598: 0.537109375,
                0.044093249246231155: 1.1016845703125,
            },
        ),
        (
            50,
            {
                0.001: 0.025431315104166668,
                0.021480183919598: 0.537109375,
                0.044093249246231155: 1.1027018229166665,
            },
        ),
    ]

    @pytest.mark.parametrize(("stretch", "samples"), CASES)
    def test_samples(self, stretch: int, samples: dict[float, float]) -> None:
        _app, comp = _comp()
        layer = _solid(comp)
        layer.stretch = stretch
        op = _keys(layer[TG]["ADBE Opacity"], [(0, 0), (4, 100)])
        for t, want in samples.items():
            assert op.value_at_time(t) == _approx(want, abs=1e-9)


class TestRemoveKeyNextToRovingRun:
    """F16: remove_key re-times the roving run it bounded. Comp 640x480,
    square pixels, 25 fps."""

    def test_times(self) -> None:
        _app, comp = _comp(640, 480, 1.0, 25.0)
        pos = _keys(
            _solid(comp)[TG]["ADBE Position"],
            [
                (0, [100, 100, 0]),
                (1, [300, 150, 0]),
                (2, [350, 400, 0]),
                (3, [500, 420, 0]),
                (5, [800, 300, 0]),
            ],
        )
        pos.keyframes[1].roving = True
        pos.keyframes[2].roving = True
        pos.remove_key(3)
        assert [k.time for k in pos.keyframes] == _approx(
            [0.0, 1.1178515625, 2.5003125, 5.0], abs=1e-9
        )

    def test_remove_first_anchor(self) -> None:
        # The roving key that becomes first keeps its flag and its time, and
        # bounds the rest of the run (AE 2026).
        _app, comp = _comp(640, 480, 1.0, 25.0)
        pos = _roving_run(comp)
        pos.remove_key(0)
        assert [k.time for k in pos.keyframes] == _approx(
            [1.00984375, 2.2587109375, 3.0, 5.0], abs=1e-9
        )
        assert pos.keyframes[0].roving is True


class TestSetValueAtTimeIntoLinearSegment:
    """F17: set_value_at_time inside a LINEAR segment stores a virgin 0 / 0
    ease, which a later switch to BEZIER reports. Comp 1000x800, 10/11 pixel
    aspect, 29.97 fps."""

    def test_virgin_ease(self, tmp_path: Path) -> None:
        app, comp = _comp(1000, 800, 10 / 11, 29.97)
        rot = _keys(_solid(comp)[TG]["ADBE Rotate Z"], [(0, 0), (2, 100)])
        rot.set_value_at_time(0.8, 70.0)
        kf = rot.keyframes[1]
        _types(kf, BEZ, BEZ)
        assert _speeds(kf.in_temporal_ease) == [0.0, 0.0]
        assert _speeds(kf.out_temporal_ease) == [0.0, 0.0]
        assert rot.keyframes[0].out_temporal_ease[0].speed == _approx(
            87.49908763880924, abs=1e-6
        )
        again = _reparse(app, tmp_path)[TG]["ADBE Rotate Z"]
        assert _speeds(again.keyframes[1].in_temporal_ease) == [0.0, 0.0]


class TestOrientationOvershoot:
    """F18: an eased Orientation segment with a LINEAR side overshoots
    unclamped."""

    def test_value(self) -> None:
        _app, comp = _comp()
        orient = _keys(
            _solid(comp, 400, 300, three_d=True)[TG]["ADBE Orientation"],
            [(0, [0, 0, 0]), (2, [40, 30, 20])],
        )
        _ease(orient.keyframes[0], [[0, 30]], [[50, 50]])
        assert orient.value_at_time(0.125) == _approx(
            [203.9391721948668, 60.25097116014023, 293.2536769415112], abs=1e-4
        )


class TestDecimalFrameRateKeyTicks:
    """A keyframe at a decimal frame rate counts AE's frame-grid units:
    12.3456 fps is 2000 units a frame, 24692 a second (AE 2026)."""

    def test_key_at_one_second(self, tmp_path: Path) -> None:
        app, comp = _comp(400, 300, 1.0, 12.3456)
        op = _keys(_solid(comp)[TG]["ADBE Opacity"], [(1.0, 50)])
        assert op.keyframes[0].time_units == 24692
        again = _reparse(app, tmp_path)[TG]["ADBE Opacity"]
        assert again.keyframes[0].time_units == 24692
        assert again.keyframes[0].time == _approx(1.0)


class TestShapeBoundHints:
    """The tdum/tduM AE writes for an edited shape property hold a 0 / 100 UI
    slider hint, not a bound: ExtendScript reports Stroke Width with no
    maximum and Miter Limit as min 1, no maximum (AE 2026 bounds probe over
    131 shape properties, and the sample's own export)."""

    def test_gradient_sample(self) -> None:
        app = parse(SAMPLES / "models" / "property" / "gradient.aep")
        seen = set()
        for comp in app.project.compositions:
            for layer in comp.layers:
                for prop in _leaves(layer):
                    if prop.match_name == "ADBE Vector Stroke Width":
                        assert (prop.has_min, prop.min_value) == (True, 0)
                        assert (prop.has_max, prop.max_value) == (False, None)
                        seen.add(prop.match_name)
                    elif prop.match_name == "ADBE Vector Stroke Miter Limit":
                        assert (prop.has_min, prop.min_value) == (True, 1)
                        assert (prop.has_max, prop.max_value) == (False, None)
                        seen.add(prop.match_name)
        assert seen == {"ADBE Vector Stroke Width", "ADBE Vector Stroke Miter Limit"}


class TestSynthesizedBoundChunks:
    """A materialized effect param's tdum/tduM: 8-byte doubles holding the UI
    slider range, as AE 2026 writes for a Slider Control (0 / 100)."""

    def test_slider_control(self, tmp_path: Path) -> None:
        app, comp = _comp()
        slider = _effect(_solid(comp), "ADBE Slider Control")
        slider.value = 7
        bounds = {
            c.chunk_type: (c.values, c.is_integer)
            for c in slider._tdbs.chunks
            if c.chunk_type in ("tdum", "tduM")
        }
        assert bounds == {"tdum": ([0.0], False), "tduM": ([100.0], False)}
        again = _reparse(app, tmp_path).effects.properties[0].properties[0]
        assert (again.min_value, again.max_value) == (-1000000, 1000000)
        assert again.value == 7.0


class TestValidation:
    """F19: inputs AE rejects, and huge coordinates."""

    def test_none_keyframe_value(self) -> None:
        app, comp = _comp()
        slider = _effect(_solid(comp), "ADBE Slider Control")
        before = project_bytes(app.project)
        with pytest.raises(TypeError):
            slider.set_value_at_time(1.0, None)
        assert slider.keyframes == [] and project_bytes(app.project) == before

    def test_non_numeric_time(self) -> None:
        _app, comp = _comp()
        rot = _solid(comp)[TG]["ADBE Rotate Z"]
        with pytest.raises(TypeError):
            rot.value_at_time("abc")  # type: ignore[arg-type]

    def test_huge_coordinate_evaluates(self) -> None:
        _app, comp = _comp()
        pos = _keys(
            _solid(comp)[TG]["ADBE Position"], [(0, [0, 0, 0]), (1, [1e200, 0, 0])]
        )
        value = pos.value_at_time(0.5)
        assert all(math.isfinite(v) for v in value)
        assert value[0] == pytest.approx(5e199, rel=1e-6)

    def test_ease_speed_none(self) -> None:
        ease = KeyframeEase(1, 50)
        with pytest.raises((TypeError, ValueError)):
            ease.speed = None  # type: ignore[assignment]
        assert ease.speed == 1


class TestTemporalContinuityFlags:
    """Temporal continuity versus interpolation types and auto-bezier, as AE
    2026 saves the flags (read back from its file)."""

    def _rot(self) -> Any:
        _app, comp = _comp()
        rot = _keys(_solid(comp)[TG]["ADBE Rotate Z"], [(0, 0), (1, 100), (2, 0)])
        return rot.keyframes[1]

    @pytest.mark.parametrize(
        ("in_type", "out_type", "continuous"),
        [
            (LIN, LIN, False),
            (LIN, BEZ, True),
            (LIN, HOLD, False),
            (BEZ, LIN, True),
            (BEZ, HOLD, True),
            (HOLD, LIN, False),
            (HOLD, BEZ, True),
            (HOLD, HOLD, False),
        ],
    )
    def test_types_after_continuous(
        self, in_type: KIT, out_type: KIT, continuous: bool
    ) -> None:
        for first in ("temporal_continuous", "temporal_auto_bezier"):
            kf = self._rot()
            setattr(kf, first, True)
            _types(kf, in_type, out_type)
            assert kf.temporal_continuous is continuous
            assert kf.temporal_auto_bezier is (first == "temporal_auto_bezier")

    def test_continuous_clears_auto_bezier(self) -> None:
        kf = self._rot()
        kf.temporal_auto_bezier = True
        kf.temporal_continuous = True
        assert (kf.temporal_auto_bezier, kf.temporal_continuous) == (False, True)

    def test_auto_bezier_key_stays_continuous(self) -> None:
        kf = self._rot()
        kf.temporal_auto_bezier = True
        kf.temporal_continuous = False
        assert (kf.temporal_auto_bezier, kf.temporal_continuous) == (True, True)

    def test_auto_bezier_back_on_bezier_sides(self) -> None:
        kf = self._rot()
        kf.temporal_auto_bezier = True
        _types(kf, LIN, LIN)
        _types(kf, BEZ, BEZ)
        assert (kf.temporal_auto_bezier, kf.temporal_continuous) == (True, True)

    def test_flags_survive_save(self, tmp_path: Path) -> None:
        app, comp = _comp()
        rot = _keys(_solid(comp)[TG]["ADBE Rotate Z"], [(0, 0), (1, 100), (2, 0)])
        kf = rot.keyframes[1]
        kf.temporal_auto_bezier = True
        _types(kf, LIN, BEZ)
        again = _reparse(app, tmp_path)[TG]["ADBE Rotate Z"].keyframes[1]
        assert (again.temporal_auto_bezier, again.temporal_continuous) == (True, True)
