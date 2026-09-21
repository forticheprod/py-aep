"""Tests for keyframe mutation: add_key, remove_key, set_value(s)_at_time(s),
Shape creation from scratch, and numeric keyframe value persistence.

Mutation tests parse a fresh (uncached) copy so changes do not leak between
tests, and assert results survive a save / re-parse round-trip.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import get_comp, parse_project_fresh

from py_aep import Application
from py_aep import parse as parse_aep
from py_aep.binary.chunk import write_aep
from py_aep.enums import KeyframeInterpolationType
from py_aep.models.properties.keyframe_ease import KeyframeEase
from py_aep.models.properties.property import Property
from py_aep.models.properties.shape import Shape

SAMPLES = Path(__file__).parent.parent.parent / "samples" / "models" / "property"
SAMPLES_ROOT = Path(__file__).parent.parent.parent / "samples"


def _fresh(name: str) -> Application:
    return parse_aep(str(SAMPLES / name))


def _roundtrip(app: Application, tmp_path: Path) -> Application:
    out = tmp_path / "out.aep"
    with out.open("wb") as f:
        write_aep(f, app.project._rifx, app.project._xmp)
    return parse_aep(str(out))


def _prop(
    app: Application, match_name: str, *, comp: int = 0, layer: int = 0
) -> Property:
    lay = app.project.compositions[comp].layers[layer]
    return next(p for p in lay.transform if p.match_name == match_name)


def _approx_points(actual, expected, abs_tol=1e-2) -> bool:
    """Compare two lists of [x, y] pairs within tolerance."""
    if len(actual) != len(expected):
        return False
    return all(a == pytest.approx(e, abs=abs_tol) for a, e in zip(actual, expected))


def _find_static(app: Application, match_name: str):
    for ci, comp in enumerate(app.project.compositions):
        for li, lay in enumerate(comp.layers):
            for p in lay.transform:
                if p.match_name == match_name and not p.keyframes:
                    return p, ci, li
    return None, None, None


def _walk(group, match_name, out):
    for p in getattr(group, "properties", []):
        if p.match_name == match_name:
            out.append(p)
        if hasattr(p, "properties"):
            _walk(p, match_name, out)


def _grad_kf_prop(app: Application):
    for comp in app.project.compositions:
        for layer in comp.layers:
            out: list = []
            _walk(layer, "ADBE Vector Grad Colors", out)
            for p in out:
                if p.keyframes:
                    return p
    return None


def _orientation_kf_prop(app: Application):
    for comp in app.project.compositions:
        for layer in comp.layers:
            out: list = []
            _walk(layer, "ADBE Orientation", out)
            for p in out:
                if p.keyframes:
                    return p
    return None


def _text_static_prop(app: Application):
    for comp in app.project.compositions:
        for layer in comp.layers:
            out: list = []
            _walk(layer, "ADBE Text Document", out)
            for p in out:
                if not p.keyframes:
                    return p
    return None


def _grad_static_prop(app: Application):
    for comp in app.project.compositions:
        for layer in comp.layers:
            out: list = []
            _walk(layer, "ADBE Vector Grad Colors", out)
            for p in out:
                if not p.keyframes:
                    return p
    return None


class TestKeyframeValuePersistence:
    def test_1d_value_roundtrips(self, tmp_path: Path) -> None:
        app = _fresh("keyframe_HOLD.aep")
        _prop(app, "ADBE Opacity").keyframes[0].value = 42.0
        app2 = _roundtrip(app, tmp_path)
        assert _prop(app2, "ADBE Opacity").keyframes[0].value == pytest.approx(42.0)

    def test_multidim_value_roundtrips(self, tmp_path: Path) -> None:
        app = _fresh("keyframe_LINEAR.aep")
        pos = _prop(app, "ADBE Position")
        v = list(pos.keyframes[0].value)
        v[0] += 7.0
        pos.keyframes[0].value = v
        app2 = _roundtrip(app, tmp_path)
        assert _prop(app2, "ADBE Position").keyframes[0].value[0] == pytest.approx(v[0])


class TestAddKey:
    def test_add_key_to_animated(self, tmp_path: Path) -> None:
        app = _fresh("keyframe_HOLD.aep")
        op = _prop(app, "ADBE Opacity")
        n0 = len(op.keyframes)
        idx = op.add_key(0.5)
        assert len(op.keyframes) == n0 + 1
        assert 0 <= idx <= n0
        app2 = _roundtrip(app, tmp_path)
        assert len(_prop(app2, "ADBE Opacity").keyframes) == n0 + 1

    def test_add_key_returns_existing_index_at_same_time(self) -> None:
        app = _fresh("keyframe_HOLD.aep")
        op = _prop(app, "ADBE Opacity")
        n0 = len(op.keyframes)
        existing_time = op.keyframes[0].time
        idx = op.add_key(existing_time)
        assert idx == 0
        assert len(op.keyframes) == n0

    def test_first_key_animates_static_property(self, tmp_path: Path) -> None:
        app = _fresh("keyframe_HOLD.aep")
        prop, _, li = _find_static(app, "ADBE Rotate Z")
        assert prop is not None
        prop.add_key(0.0)
        prop.add_key(1.0)
        prop.keyframes[1].value = 25.0
        assert prop._animated
        assert len(prop.keyframes) == 2
        app2 = _roundtrip(app, tmp_path)
        prop2 = next(
            p
            for p in app2.project.compositions[0].layers[li].transform
            if p.match_name == "ADBE Rotate Z"
        )
        assert len(prop2.keyframes) == 2
        assert prop2.keyframes[1].value == pytest.approx(25.0)

    def test_synthetic_multidim_property_animates(self, tmp_path: Path) -> None:
        """A synthetic multi-dimensional property (Scale) animates + round-trips.

        Regression: materializing a synthetic non-spatial vector property
        must add the tdum/tduM bound chunks and reposition the property
        into canonical order, or AE rejects the file.
        """
        app = _fresh("keyframe_HOLD.aep")
        scale, _, li = _find_static(app, "ADBE Scale")
        assert scale is not None
        scale.set_value_at_time(0.0, [50.0, 50.0, 100.0])
        scale.set_value_at_time(1.0, [120.0, 120.0, 100.0])
        assert scale._animated
        # tdum/tduM bound chunks were added on materialization.
        kinds = [getattr(c, "chunk_type", None) for c in scale._tdbs.chunks]
        assert "tdum" in kinds and "tduM" in kinds
        app2 = _roundtrip(app, tmp_path)
        scale2 = next(
            p
            for p in app2.project.compositions[0].layers[li].transform
            if p.match_name == "ADBE Scale"
        )
        assert len(scale2.keyframes) == 2

    def test_keys_stay_time_sorted(self) -> None:
        app = _fresh("keyframe_HOLD.aep")
        op = _prop(app, "ADBE Opacity")
        op.add_key(0.5)
        op.add_key(0.1)
        times = [kf.frame_time for kf in op.keyframes]
        assert times == sorted(times)

    def test_add_key_no_value_property_raises(self) -> None:
        # A numeric property with no value slot cannot be keyframed; building
        # a numeric keyframe item for it would produce a wrong-size ldat item.
        app = _fresh("keyframe_HOLD.aep")
        op = _prop(app, "ADBE Opacity")
        op.__dict__["_no_value"] = True
        with pytest.raises(ValueError):
            op.add_key(0.5)


class TestRemoveKey:
    def test_remove_middle_key(self, tmp_path: Path) -> None:
        app = _fresh("keyframe_HOLD.aep")
        op = _prop(app, "ADBE Opacity")
        n0 = len(op.keyframes)
        op.remove_key(1)
        assert len(op.keyframes) == n0 - 1
        app2 = _roundtrip(app, tmp_path)
        assert len(_prop(app2, "ADBE Opacity").keyframes) == n0 - 1

    def test_remove_last_key_deanimates(self, tmp_path: Path) -> None:
        app = _fresh("keyframe_HOLD.aep")
        op = _prop(app, "ADBE Opacity")
        last_val = op.keyframes[0].value
        while op.keyframes:
            op.remove_key(0)
        assert not op._animated
        app2 = _roundtrip(app, tmp_path)
        op2 = _prop(app2, "ADBE Opacity")
        assert len(op2.keyframes) == 0
        assert op2.value == pytest.approx(last_val)

    def test_remove_key_out_of_range(self) -> None:
        app = _fresh("keyframe_HOLD.aep")
        op = _prop(app, "ADBE Opacity")
        with pytest.raises(ValueError):
            op.remove_key(99)


class TestMoveKeyframe:
    """Writing Keyframe.time / frame_time re-sorts keyframes and chunks."""

    def test_move_past_neighbour_resorts(self, tmp_path: Path) -> None:
        app = _fresh("keyframe_HOLD.aep")
        op = _prop(app, "ADBE Opacity")
        assert len(op.keyframes) >= 2
        for i, kf in enumerate(op.keyframes):
            kf.value = 10.0 * (i + 1)
        first = op.keyframes[0]
        first.time = op.keyframes[-1].time + 1.0
        assert op.keyframes[-1] is first
        times = [kf.frame_time for kf in op.keyframes]
        assert times == sorted(times)
        # prev/next chain follows the new order.
        assert first._next is None
        assert op.keyframes[-2]._next is first
        app2 = _roundtrip(app, tmp_path)
        op2 = _prop(app2, "ADBE Opacity")
        times2 = [kf.frame_time for kf in op2.keyframes]
        assert times2 == sorted(times2)
        # The moved keyframe's value traveled with it through the save.
        assert op2.keyframes[-1].value == pytest.approx(10.0)
        assert op2.keyframes[0].value == pytest.approx(20.0)

    def test_move_without_crossing_keeps_position(self) -> None:
        app = _fresh("keyframe_HOLD.aep")
        op = _prop(app, "ADBE Opacity")
        kf = op.keyframes[0]
        kf.frame_time = op.keyframes[1].frame_time - 1
        assert op.keyframes[0] is kf
        times = [k.frame_time for k in op.keyframes]
        assert times == sorted(times)

    def test_move_onto_existing_keyframe_raises(self) -> None:
        app = _fresh("keyframe_HOLD.aep")
        op = _prop(app, "ADBE Opacity")
        original = op.keyframes[0].frame_time
        with pytest.raises(ValueError, match="already exists"):
            op.keyframes[0].frame_time = op.keyframes[1].frame_time
        # The failed move left the keyframe untouched.
        assert op.keyframes[0].frame_time == original

    def test_move_marker_key_moves_container_value(self, tmp_path: Path) -> None:
        # Markers keep their values in the parallel Nmrd container, paired
        # by position: the container entry must travel with the keyframe.
        from py_aep.models.properties.marker import MarkerValue

        app = parse_aep(str(SAMPLES_ROOT / "models" / "marker" / "layer_marker.aep"))
        comp = get_comp(app.project, "layer_multiple_markers")
        mp = comp.layers[0]["ADBE Marker"]
        assert len(mp.keyframes) >= 2
        mp.keyframes[0].value = MarkerValue(comment="moved")
        mp.keyframes[0].time = mp.keyframes[-1].time + 1.0
        app2 = _roundtrip(app, tmp_path)
        mp2 = get_comp(app2.project, "layer_multiple_markers").layers[0]["ADBE Marker"]
        times2 = [kf.frame_time for kf in mp2.keyframes]
        assert times2 == sorted(times2)
        assert mp2.keyframes[-1].value.comment == "moved"
        assert all(kf.value.comment != "moved" for kf in mp2.keyframes[:-1])


def _keyframed_props(group) -> list:
    """Collect every descendant property that has keyframes."""
    out: list = []
    for p in getattr(group, "properties", []):
        if getattr(p, "keyframes", None):
            out.append(p)
        out.extend(_keyframed_props(p))
    return out


class TestRemoveAllKeys:
    def test_property_reverts_to_first_key_value(self, tmp_path: Path) -> None:
        app = _fresh("keyframe_HOLD.aep")
        op = _prop(app, "ADBE Opacity")
        first_val = op.keyframes[0].value
        op.remove_all_keys()
        assert op.keyframes == []
        app2 = _roundtrip(app, tmp_path)
        op2 = _prop(app2, "ADBE Opacity")
        assert op2.keyframes == []
        assert op2.value == pytest.approx(first_val)

    def test_noop_when_no_keyframes(self) -> None:
        app = _fresh("keyframe_HOLD.aep")
        op = _prop(app, "ADBE Opacity")
        op.remove_all_keys()
        op.remove_all_keys()
        assert op.keyframes == []

    def test_layer_remove_all_keys_recursive(self, tmp_path: Path) -> None:
        app = parse_aep(str(SAMPLES_ROOT / "models" / "property" / "all_animated.aep"))
        assert any(
            _keyframed_props(lay)
            for comp in app.project.compositions
            for lay in comp.layers
        )
        for comp in app.project.compositions:
            for lay in comp.layers:
                lay.remove_all_keys()
                assert _keyframed_props(lay) == []
        app2 = _roundtrip(app, tmp_path)
        for comp in app2.project.compositions:
            for lay in comp.layers:
                assert _keyframed_props(lay) == []


class TestSetValueAtTime:
    def test_replace_existing_key(self) -> None:
        app = _fresh("keyframe_LINEAR.aep")
        pos = _prop(app, "ADBE Position")
        n0 = len(pos.keyframes)
        t0 = pos.keyframes[0].time
        target = [11.0, 22.0, 0.0][: len(pos.keyframes[0].value)]
        pos.set_value_at_time(t0, target)
        assert len(pos.keyframes) == n0
        assert pos.keyframes[0].value == pytest.approx(target)

    def test_add_new_key(self, tmp_path: Path) -> None:
        app = _fresh("keyframe_LINEAR.aep")
        pos = _prop(app, "ADBE Position")
        n0 = len(pos.keyframes)
        t = pos.keyframes[0].time + 0.25
        target = [99.0, 88.0, 0.0][: len(pos.keyframes[0].value)]
        pos.set_value_at_time(t, target)
        assert len(pos.keyframes) == n0 + 1
        app2 = _roundtrip(app, tmp_path)
        assert len(_prop(app2, "ADBE Position").keyframes) == n0 + 1

    def test_set_values_at_times(self) -> None:
        app = _fresh("keyframe_HOLD.aep")
        op = _prop(app, "ADBE Opacity")
        op.set_values_at_times([0.0, 2.0], [10.0, 90.0])
        # The value set at each requested time is observable via value_at_time.
        assert op.value_at_time(0.0) == pytest.approx(10.0)
        assert op.value_at_time(2.0) == pytest.approx(90.0)

    def test_set_values_at_times_length_mismatch(self) -> None:
        app = _fresh("keyframe_HOLD.aep")
        op = _prop(app, "ADBE Opacity")
        with pytest.raises(ValueError):
            op.set_values_at_times([0.0, 1.0], [10.0])


class TestComplexTypeKeyframes:
    """add_key / remove_key / set_value_at_time for complex value types."""

    def test_orientation(self, tmp_path: Path) -> None:
        app = parse_aep(
            str(SAMPLES_ROOT / "models" / "layer" / "orientation_with_keyframes.aep")
        )
        o = _prop(app, "ADBE Orientation")
        n0 = len(o.keyframes)
        o.set_value_at_time(o.keyframes[-1].time + 0.3, [12.0, 34.0, 56.0])
        assert len(o.keyframes) == n0 + 1
        app2 = _roundtrip(app, tmp_path)
        o2 = _prop(app2, "ADBE Orientation")
        assert [12.0, 34.0, 56.0] in [k.value for k in o2.keyframes]
        o2.remove_key(0)
        assert len(o2.keyframes) == n0

    def test_marker(self, tmp_path: Path) -> None:
        from py_aep.models.properties.marker import MarkerValue

        app = parse_aep(str(SAMPLES_ROOT / "models" / "marker" / "layer_marker.aep"))
        comp = get_comp(app.project, "layer_multiple_markers")
        mp = comp.layers[0]["ADBE Marker"]
        n0 = len(mp.keyframes)
        mp.set_value_at_time(mp.keyframes[-1].time + 1.0, MarkerValue(comment="X"))
        mp.set_value_at_time(mp.keyframes[-1].time + 2.0, "str comment")
        app2 = _roundtrip(app, tmp_path)
        comp2 = get_comp(app2.project, "layer_multiple_markers")
        mp2 = comp2.layers[0]["ADBE Marker"]
        comments = [k.value.comment for k in mp2.keyframes]
        assert "X" in comments and "str comment" in comments
        assert len(mp2.keyframes) == n0 + 2

    def test_shape(self, tmp_path: Path) -> None:

        app = parse_aep(str(SAMPLES_ROOT / "models" / "property" / "all_animated.aep"))

        def get_ms(a):
            for comp in a.project.compositions:
                for layer in comp.layers:
                    try:
                        mp = layer["ADBE Mask Parade"]
                    except Exception:
                        continue
                    out: list = []
                    _walk(mp, "ADBE Mask Shape", out)
                    for p in out:
                        if p.keyframes:
                            return p
            return None

        ms = get_ms(app)
        n0 = len(ms.keyframes)
        ms.set_value_at_time(
            ms.keyframes[-1].time + 0.5,
            Shape([[10.0, 10.0], [80.0, 10.0], [80.0, 80.0], [10.0, 80.0]]),
        )
        assert len(ms.keyframes) == n0 + 1
        app2 = _roundtrip(app, tmp_path)
        ms2 = get_ms(app2)
        assert len(ms2.keyframes) == n0 + 1
        ms2.remove_key(0)
        assert len(ms2.keyframes) == n0

    def test_gradient(self, tmp_path: Path) -> None:
        app = parse_aep(
            str(SAMPLES_ROOT / "models" / "property" / "gradient_animated.aep")
        )

        def get_grad(a):
            for comp in a.project.compositions:
                for layer in comp.layers:
                    try:
                        root = layer["ADBE Root Vectors Group"]
                    except Exception:
                        continue
                    out: list = []
                    _walk(root, "ADBE Vector Grad Colors", out)
                    for p in out:
                        if p.keyframes:
                            return p
            return None

        g = get_grad(app)
        n0 = len(g.keyframes)
        g.add_key(g.keyframes[0].time + 0.1)
        assert len(g.keyframes) == n0 + 1
        app2 = _roundtrip(app, tmp_path)
        g2 = get_grad(app2)
        assert len(g2.keyframes) == n0 + 1

    def test_text(self, tmp_path: Path) -> None:
        app = parse_aep(str(SAMPLES_ROOT / "models" / "property" / "all_animated.aep"))

        def get_text(a):
            for comp in a.project.compositions:
                for layer in comp.layers:
                    try:
                        tp = layer["ADBE Text Properties"]
                    except Exception:
                        continue
                    out: list = []
                    _walk(tp, "ADBE Text Document", out)
                    for p in out:
                        if p.keyframes:
                            return p
            return None

        t = get_text(app)
        n0 = len(t.keyframes)
        t.set_value_at_time(t.keyframes[-1].time + 0.5, "NewLine")
        assert len(t.keyframes) == n0 + 1
        app2 = _roundtrip(app, tmp_path)
        t2 = get_text(app2)
        texts = [k.value.text for k in t2.keyframes]
        assert "NewLine" in texts
        assert len(t2.keyframes) == n0 + 1
        t2.remove_key(0)
        assert len(t2.keyframes) == n0

    def test_added_shape_keyframe_backed_by_own_chunk(self) -> None:
        # Regression: a newly added shape keyframe must wrap its own chunk,
        # not alias the donor keyframe's Shape; otherwise editing the new
        # keyframe's value would write through to the donor's chunk.
        app = parse_aep(str(SAMPLES_ROOT / "models" / "property" / "all_animated.aep"))
        ms = None
        for comp in app.project.compositions:
            for layer in comp.layers:
                try:
                    mp = layer["ADBE Mask Parade"]
                except Exception:
                    continue
                out: list = []
                _walk(mp, "ADBE Mask Shape", out)
                ms = next((p for p in out if len(p.keyframes) >= 1), None)
                if ms is not None:
                    break
            if ms is not None:
                break
        assert ms is not None
        t = ms.keyframes[-1].time + 0.5
        ms.add_key(t)
        idx = ms.nearest_key_index(t)
        new_shph = ms.keyframes[idx].value._shph
        others = [k.value._shph for j, k in enumerate(ms.keyframes) if j != idx]
        assert all(new_shph is not o for o in others)

    def test_remove_last_marker_key(self, tmp_path: Path) -> None:
        # Markers have no static value: removing the last one leaves the
        # valid zero-marker state, and a new marker can be added again.
        from py_aep.models.properties.marker import MarkerValue

        app = parse_aep(str(SAMPLES_ROOT / "models" / "marker" / "layer_marker.aep"))
        comp = get_comp(app.project, "layer_multiple_markers")
        mp = comp.layers[0]["ADBE Marker"]
        while mp.keyframes:
            mp.remove_key(0)
        app2 = _roundtrip(app, tmp_path)
        comp2 = get_comp(app2.project, "layer_multiple_markers")
        mp2 = comp2.layers[0]["ADBE Marker"]
        assert mp2.keyframes == []
        mp2.set_value_at_time(1.0, MarkerValue(comment="back"))
        app3 = _roundtrip(app2, tmp_path)
        comp3 = next(
            c for c in app3.project.compositions if c.name == "layer_multiple_markers"
        )
        mp3 = comp3.layers[0]["ADBE Marker"]
        assert [k.value.comment for k in mp3.keyframes] == ["back"]

    def test_remove_last_text_key_reverts_to_static(self, tmp_path: Path) -> None:
        app = parse_aep(str(SAMPLES_ROOT / "models" / "property" / "all_animated.aep"))

        def get_text(a):
            for comp in a.project.compositions:
                for layer in comp.layers:
                    try:
                        tp = layer["ADBE Text Properties"]
                    except Exception:
                        continue
                    out: list = []
                    _walk(tp, "ADBE Text Document", out)
                    for p in out:
                        if p.keyframes or p.value is not None:
                            return p
            return None

        t = get_text(app)
        # The last keyframe removed provides the static value.
        last_text = t.keyframes[-1].value.text
        while t.keyframes:
            t.remove_key(0)
        assert t.value.text == last_text
        app2 = _roundtrip(app, tmp_path)
        t2 = get_text(app2)
        assert t2.keyframes == []
        assert t2.value.text == last_text

    def test_remove_last_shape_key_reverts_to_static(self, tmp_path: Path) -> None:
        app = parse_aep(str(SAMPLES_ROOT / "models" / "property" / "all_animated.aep"))

        def get_ms(a):
            for comp in a.project.compositions:
                for layer in comp.layers:
                    try:
                        mp = layer["ADBE Mask Parade"]
                    except Exception:
                        continue
                    out: list = []
                    _walk(mp, "ADBE Mask Shape", out)
                    for p in out:
                        if p.keyframes or p.value is not None:
                            return p
            return None

        ms = get_ms(app)
        # The last keyframe removed provides the static value.
        last_vertices = ms.keyframes[-1].value.vertices
        while ms.keyframes:
            ms.remove_key(0)
        app2 = _roundtrip(app, tmp_path)
        ms2 = get_ms(app2)
        assert ms2.keyframes == []
        assert _approx_points(ms2.value.vertices, last_vertices)

    def test_remove_last_gradient_key_reverts_to_static(self, tmp_path: Path) -> None:
        app = parse_aep(
            str(SAMPLES_ROOT / "models" / "property" / "gradient_animated.aep")
        )

        def get_grad(a):
            for comp in a.project.compositions:
                for layer in comp.layers:
                    try:
                        root = layer["ADBE Root Vectors Group"]
                    except Exception:
                        continue
                    out: list = []
                    _walk(root, "ADBE Vector Grad Colors", out)
                    for p in out:
                        if p.keyframes or p.value is not None:
                            return p
            return None

        g = get_grad(app)
        while g.keyframes:
            g.remove_key(0)
        app2 = _roundtrip(app, tmp_path)
        g2 = get_grad(app2)
        assert g2.keyframes == []
        assert g2.value is not None

    def test_remove_last_orientation_key_reverts_to_static(
        self, tmp_path: Path
    ) -> None:
        app = parse_aep(
            str(SAMPLES_ROOT / "models" / "layer" / "orientation_with_keyframes.aep")
        )
        o = _prop(app, "ADBE Orientation")
        last_value = None
        while o.keyframes:
            last_value = o.keyframes[0].value
            o.remove_key(0)
        assert o.value == pytest.approx(last_value)
        app2 = _roundtrip(app, tmp_path)
        o2 = _prop(app2, "ADBE Orientation")
        assert o2.keyframes == []
        assert o2.value == pytest.approx(last_value)

    def test_animate_static_text(self, tmp_path: Path) -> None:
        app = parse_aep(str(SAMPLES_ROOT / "models" / "layer" / "type.aep"))

        def get_text(a):
            for comp in a.project.compositions:
                for layer in comp.layers:
                    try:
                        tp = layer["ADBE Text Properties"]
                    except Exception:
                        continue
                    out: list = []
                    _walk(tp, "ADBE Text Document", out)
                    if out:
                        return out[0]
            return None

        t = get_text(app)
        assert t.keyframes == []
        original = t.value.text
        idx = t.add_key(1.0)
        assert idx == 0
        assert len(t.keyframes) == 1
        assert t.keyframes[0].value.text == original
        app2 = _roundtrip(app, tmp_path)
        t2 = get_text(app2)
        assert len(t2.keyframes) == 1
        assert t2.keyframes[0].time == pytest.approx(1.0)
        assert t2.keyframes[0].value.text == original
        t2.set_value_at_time(2.0, "Second")
        app3 = _roundtrip(app2, tmp_path)
        t3 = get_text(app3)
        assert [k.value.text for k in t3.keyframes] == [original, "Second"]

    def test_animate_static_mask_shape(self, tmp_path: Path) -> None:
        app = parse_aep(str(SAMPLES_ROOT / "models" / "property" / "mask.aep"))

        def get_ms(a):
            for comp in a.project.compositions:
                for layer in comp.layers:
                    try:
                        mp = layer["ADBE Mask Parade"]
                    except Exception:
                        continue
                    out: list = []
                    _walk(mp, "ADBE Mask Shape", out)
                    if out:
                        return out[0]
            return None

        ms = get_ms(app)
        assert ms.keyframes == []
        vertices = ms.value.vertices
        ms.add_key(1.0)
        assert len(ms.keyframes) == 1
        app2 = _roundtrip(app, tmp_path)
        ms2 = get_ms(app2)
        assert len(ms2.keyframes) == 1
        assert ms2.keyframes[0].time == pytest.approx(1.0)
        assert _approx_points(ms2.keyframes[0].value.vertices, vertices)

    def test_animate_static_gradient(self, tmp_path: Path) -> None:
        app = parse_aep(str(SAMPLES_ROOT / "models" / "property" / "gradient.aep"))

        def get_grad(a):
            for comp in a.project.compositions:
                for layer in comp.layers:
                    try:
                        root = layer["ADBE Root Vectors Group"]
                    except Exception:
                        continue
                    out: list = []
                    _walk(root, "ADBE Vector Grad Colors", out)
                    if out:
                        return out[0]
            return None

        g = get_grad(app)
        assert g.keyframes == []
        assert g.value is not None
        g.add_key(0.5)
        assert len(g.keyframes) == 1
        app2 = _roundtrip(app, tmp_path)
        g2 = get_grad(app2)
        assert len(g2.keyframes) == 1
        assert g2.keyframes[0].value is not None

    def test_animate_static_orientation(self, tmp_path: Path) -> None:
        app = parse_aep(str(SAMPLES_ROOT / "models" / "property" / "mask.aep"))
        o = _prop(app, "ADBE Orientation")
        assert o.keyframes == []
        o.set_value_at_time(1.0, [10.0, 20.0, 30.0])
        assert len(o.keyframes) == 1
        app2 = _roundtrip(app, tmp_path)
        o2 = _prop(app2, "ADBE Orientation")
        assert len(o2.keyframes) == 1
        assert o2.keyframes[0].value == pytest.approx([10.0, 20.0, 30.0])

    def test_add_first_marker_to_unmarked_layer(self, tmp_path: Path) -> None:
        # A never-marked layer has no mrst subtree at all; adding the first
        # marker materializes it.
        from py_aep.models.properties.marker import MarkerValue

        app = parse_aep(str(SAMPLES_ROOT / "models" / "property" / "mask.aep"))
        mp = app.project.compositions[0].layers[0]["ADBE Marker"]
        assert mp.keyframes == []
        assert mp._kf_value_container is None
        mp.set_value_at_time(1.0, MarkerValue(comment="first"))
        app2 = _roundtrip(app, tmp_path)
        mp2 = app2.project.compositions[0].layers[0]["ADBE Marker"]
        assert [k.value.comment for k in mp2.keyframes] == ["first"]
        assert mp2.keyframes[0].time == pytest.approx(1.0)
        mp2.remove_key(0)
        app3 = _roundtrip(app2, tmp_path)
        mp3 = app3.project.compositions[0].layers[0]["ADBE Marker"]
        assert mp3.keyframes == []

    def test_animate_pristine_camera_orientation(self, tmp_path: Path) -> None:
        # A never-modified camera orientation is stored as a bare tdbs (no
        # otst / otky); keying it materializes the wrapper.
        app = parse_aep(str(SAMPLES_ROOT / "models" / "layer" / "type.aep"))

        def get_orient(a):
            for comp in a.project.compositions:
                for layer in comp.layers:
                    if layer.name != "CameraLayer":
                        continue
                    return next(
                        p for p in layer.transform if p.match_name == "ADBE Orientation"
                    )
            return None

        o = get_orient(app)
        assert o.keyframes == []
        assert o._kf_value_container is None
        o.set_value_at_time(1.0, [10.0, 20.0, 30.0])
        app2 = _roundtrip(app, tmp_path)
        o2 = get_orient(app2)
        assert len(o2.keyframes) == 1
        assert o2.keyframes[0].value == pytest.approx([10.0, 20.0, 30.0])
        o2.remove_key(0)
        app3 = _roundtrip(app2, tmp_path)
        o3 = get_orient(app3)
        assert o3.keyframes == []
        assert o3.value == pytest.approx([10.0, 20.0, 30.0])

    def test_animate_never_edited_gradient(self, tmp_path: Path) -> None:
        # A never-edited gradient fill has no GCst data; the first keyframe
        # materializes it with AE's default gradient.
        app = parse_aep(str(SAMPLES_ROOT / "models" / "property" / "all_animated.aep"))

        def get_grad(a):
            for comp in a.project.compositions:
                for layer in comp.layers:
                    try:
                        root = layer["ADBE Root Vectors Group"]
                    except Exception:
                        continue
                    out: list = []
                    _walk(root, "ADBE Vector Grad Colors", out)
                    if out:
                        return out[0]
            return None

        g = get_grad(app)
        assert g.keyframes == []
        assert g._kf_value_container is None
        g.add_key(0.5)
        assert len(g.keyframes) == 1
        app2 = _roundtrip(app, tmp_path)
        g2 = get_grad(app2)
        assert len(g2.keyframes) == 1
        assert g2.keyframes[0].value is not None


class TestParallelValueAliasing:
    """Regression tests for the 4 parallel-property value-write bugs."""

    GRAD_ANIM = SAMPLES_ROOT / "models" / "property" / "gradient_animated.aep"
    GRAD_STATIC = SAMPLES_ROOT / "models" / "property" / "gradient.aep"
    ORIENT_ANIM = SAMPLES_ROOT / "models" / "property" / "all_animated.aep"
    TEXT_STATIC = (
        SAMPLES_ROOT / "models" / "essential_graphics" / "text_source_text.aep"
    )

    def test_marker_set_at_two_times_is_independent(self, tmp_path: Path) -> None:
        # BUG 1: setting one MarkerValue at two times must not alias a single
        # set of chunks into both Nmrds; editing one keyframe afterwards must
        # leave the other untouched, with consistent nmhd.num_params.
        from py_aep.models.properties.marker import MarkerValue

        app = parse_aep(str(SAMPLES_ROOT / "models" / "marker" / "layer_marker.aep"))
        comp = get_comp(app.project, "layer_multiple_markers")
        mp = comp.layers[0]["ADBE Marker"]
        while mp.keyframes:
            mp.remove_key(0)

        shared = MarkerValue(comment="shared")
        mp.set_value_at_time(0.0, shared)
        mp.set_value_at_time(1.0, shared)
        k0, k1 = mp.keyframes[0], mp.keyframes[1]
        assert k0.value is not k1.value

        # Editing one keyframe must not bleed into the other.
        k0.value.comment = "first_only"
        assert k1.value.comment == "shared"
        # Param splice on k1 only; k0 stays empty with a consistent header.
        k1.value.params = {"a": "1", "b": "2"}
        assert k0.value.params == {}
        assert k0.value._nmhd.num_params == 0
        assert k1.value._nmhd.num_params == 2

        app2 = _roundtrip(app, tmp_path)
        comp2 = get_comp(app2.project, "layer_multiple_markers")
        mp2 = comp2.layers[0]["ADBE Marker"]
        by_comment = {k.value.comment: k.value for k in mp2.keyframes}
        assert by_comment["first_only"].params == {}
        assert by_comment["first_only"]._nmhd.num_params == 0
        assert by_comment["shared"].params == {"a": "1", "b": "2"}
        assert by_comment["shared"]._nmhd.num_params == 2

    def test_gradient_set_value_at_time_not_aliased(self, tmp_path: Path) -> None:
        # BUG 2: set_value_at_time(kf1.time, kf0.value) must rebind kf1 to its
        # own chunk; mutating kf1 afterwards must not change kf0.
        app = parse_aep(str(self.GRAD_ANIM))
        g = _grad_kf_prop(app)
        kf0, kf1 = g.keyframes[0], g.keyframes[1]
        kf0_xml_before = kf0.value._utf8.value

        g.set_value_at_time(kf1.time, kf0.value)
        assert kf1.value is not kf0.value
        kf1.value.add_color_stop(0.5, 0.5, (1.0, 0.0, 0.0))
        assert kf0.value._utf8.value == kf0_xml_before

        app2 = _roundtrip(app, tmp_path)
        g2 = _grad_kf_prop(app2)
        assert len(g2.keyframes[0].value.color_stops) == len(kf0.value.color_stops)
        assert len(g2.keyframes[1].value.color_stops) == len(kf1.value.color_stops)
        assert len(g2.keyframes[0].value.color_stops) != len(
            g2.keyframes[1].value.color_stops
        )

    def test_orientation_keyframe_value_persists(self, tmp_path: Path) -> None:
        # BUG 3: assigning kf.value on an animated orientation must write the
        # parallel otda container, not just the in-memory shadow.
        app = parse_aep(str(self.ORIENT_ANIM))
        o = _orientation_kf_prop(app)
        o.keyframes[0].value = [0.0, 0.0, 90.0]
        assert o.keyframes[0].value == [0.0, 0.0, 90.0]

        app2 = _roundtrip(app, tmp_path)
        o2 = _orientation_kf_prop(app2)
        assert o2.keyframes[0].value == [0.0, 0.0, 90.0]

    def test_static_gradient_value_reassign_persists(self, tmp_path: Path) -> None:
        # BUG 4 (implemented kind): assigning a new Gradient to a static
        # gradient property rebuilds its GCky container chunk.
        from py_aep.models.properties.gradient import Gradient

        app = parse_aep(str(self.GRAD_STATIC))
        g = _grad_static_prop(app)
        assert g is not None
        new_grad = Gradient()
        new_grad.add_color_stop(0.5, 0.5, (1.0, 0.0, 0.0))
        n_stops = len(new_grad.color_stops)
        g.value = new_grad

        app2 = _roundtrip(app, tmp_path)
        g2 = _grad_static_prop(app2)
        assert len(g2.value.color_stops) == n_stops

    def test_static_text_value_reassign_raises(self) -> None:
        # BUG 4 (rejected kind): a brand-new TextDocument cannot replace a
        # static text value (the btdk COS blob is byte-format-sensitive);
        # the documented in-place alternative is mutating prop.value.text.
        from py_aep.models.text.text_document import TextDocument

        app = parse_aep(str(self.TEXT_STATIC))
        t = _text_static_prop(app)
        assert t is not None
        with pytest.raises(ValueError, match="Mutate the existing prop.value"):
            t.value = TextDocument("CHANGED_TEXT")

    def test_static_text_inplace_mutation_persists(self, tmp_path: Path) -> None:
        # BUG 4 (rejected kind): the documented alternative - mutating the
        # existing value object in place - must still persist (no silent loss).
        app = parse_aep(str(self.TEXT_STATIC))
        t = _text_static_prop(app)
        assert t is not None
        t.value.text = "CHANGED_TEXT"
        app2 = _roundtrip(app, tmp_path)
        t2 = _text_static_prop(app2)
        assert t2.value.text == "CHANGED_TEXT"


class TestSpatialFlagGuards:
    """Non-spatial keyframes reject spatial-flag writes (ExtendScript's
    setSpatialAutoBezierAtKey errors regardless of the value written)."""

    def test_spatial_auto_bezier_on_non_spatial_raises(self) -> None:
        app = _fresh("keyframe_HOLD.aep")
        kf = _prop(app, "ADBE Opacity").keyframes[0]
        with pytest.raises(ValueError, match="spatial keyframes"):
            kf.spatial_auto_bezier = False

    def test_spatial_continuous_on_non_spatial_raises(self) -> None:
        app = _fresh("keyframe_HOLD.aep")
        kf = _prop(app, "ADBE Opacity").keyframes[0]
        with pytest.raises(ValueError, match="spatial keyframes"):
            kf.spatial_continuous = False


class TestRoundtripSubFrameKeyframeTime:
    """Keyframe.time is exact, not snapped to whole frames.

    AE places keyframes off the frame grid freely: `setValueAtTime(1.5)` in a
    25 fps comp is stored as 38400 units, i.e. frame 37.5, and every roving
    keyframe is positioned by arc length. Rounding to frames misreported such
    a keyframe by up to half a frame and moved it on the next write.
    """

    SAMPLE = SAMPLES / "effect_point_speed.aep"

    def test_off_grid_time_is_exact(self, tmp_path: Path) -> None:
        """1.5 s in a 25 fps comp is frame 37.5. Before the fix this read
        back as 1.52."""
        project = parse_project_fresh(self.SAMPLE)
        comp = project.compositions[0]
        assert comp.frame_rate == 25.0
        prop = comp.layers[0].transform["ADBE Opacity"]
        prop.add_key(1.5)

        keyframe = next(k for k in prop.keyframes if k.time_units == 38400)
        assert keyframe.time == pytest.approx(1.5)

        out = tmp_path / "modified.aep"
        project.save(out)
        comp2 = parse_aep(out).project.compositions[0]
        prop2 = comp2.layers[0].transform["ADBE Opacity"]
        keyframe2 = next(k for k in prop2.keyframes if k.time_units == 38400)
        assert keyframe2.time == pytest.approx(1.5)

    def test_rewriting_its_own_time_does_not_move_a_keyframe(self) -> None:
        """`kf.time = kf.time` used to snap an off-grid keyframe to the
        nearest frame."""
        project = parse_project_fresh(self.SAMPLE)
        prop = project.compositions[0].layers[0].transform["ADBE Opacity"]
        prop.add_key(1.5)
        keyframe = next(k for k in prop.keyframes if k.time_units == 38400)

        keyframe.time = keyframe.time

        assert keyframe.time_units == 38400

    def test_two_keyframes_can_share_a_frame(self) -> None:
        """Sub-frame keyframes inside one frame are distinct, so the
        duplicate-time guard must compare units and not frame indices."""
        project = parse_project_fresh(self.SAMPLE)
        prop = project.compositions[0].layers[0].transform["ADBE Opacity"]
        # Both round to frame 37 at 25 fps (37.025 and 37.375) while
        # occupying different timebase units.
        prop.add_key(1.481)
        prop.add_key(1.495)

        units = sorted(k.time_units for k in prop.keyframes)
        assert len(set(units)) == len(units)
        inside = [k for k in prop.keyframes if k.frame_time == 37]
        assert len(inside) == 2

    def test_frame_time_still_rounds(self) -> None:
        project = parse_project_fresh(self.SAMPLE)
        prop = project.compositions[0].layers[0].transform["ADBE Opacity"]
        prop.add_key(1.5)
        keyframe = next(k for k in prop.keyframes if k.time_units == 38400)
        assert keyframe.frame_time == 38
        assert keyframe.time == pytest.approx(1.5)

    def test_layer_start_offset_stays_in_seconds(self, tmp_path: Path) -> None:
        """Keyframe times are stored relative to the layer start; an
        off-grid start must not quantize the keyframe."""
        project = parse_project_fresh(self.SAMPLE)
        comp = project.compositions[0]
        layer = comp.layers[0]
        layer.start_time = 0.29166666666666663  # 7/24 s, off the 25 fps grid
        prop = layer.transform["ADBE Opacity"]
        prop.add_key(2.0)

        out = tmp_path / "modified.aep"
        project.save(out)
        comp2 = parse_aep(out).project.compositions[0]
        prop2 = comp2.layers[0].transform["ADBE Opacity"]
        # Times are an integer count of timebase units, so a request that
        # falls between units lands on the nearest one - AE requantizes
        # identically (it stored 0.99998697916667 for a 1.0 s request on a
        # layer with this start).
        half_unit = 0.5 / comp2._cdta.internal_timebase
        assert any(abs(k.time - 2.0) <= half_unit for k in prop2.keyframes)


class TestRoundtripRoving:
    """Roving keyframes are positioned by arc length, not stored freely.

    AE derives a roving keyframe's time so the speed along the spatial path
    is constant between the enclosing non-roving anchors, and applies it the
    moment the flag is set. Both expected times below are AE 2026
    measurements on a 25 fps comp with the first segment bowed by +/-400 px
    tangents - a case where chord length would predict 0.667 s.
    """

    SAMPLE = SAMPLES / "effect_point_speed.aep"

    def _bowed_path(self, bow: float) -> Property:
        project = parse_project_fresh(self.SAMPLE)
        comp = project.compositions[0]
        assert comp.frame_rate == 25.0
        prop = comp.layers[0].transform["ADBE Position"]
        while prop.keyframes:
            prop.remove_key(0)
        for time, value in ((0.0, 0.0), (1.0, 100.0), (4.0, 600.0)):
            prop.add_key(time)
            prop.keyframes[-1].value = [value, 200.0, 0.0]
        for keyframe in prop.keyframes:
            keyframe.in_interpolation_type = KeyframeInterpolationType.BEZIER
            keyframe.out_interpolation_type = KeyframeInterpolationType.BEZIER
        prop.keyframes[0].out_spatial_tangent = [0.0, bow, 0.0]
        prop.keyframes[1].in_spatial_tangent = [0.0, bow, 0.0]
        return prop

    def test_roving_uses_arc_length_not_chord(self) -> None:
        """AE put the roving key at 2.2205078125 s (56845 units). The chord
        between the same keyframes would put it at 0.667 s."""
        prop = self._bowed_path(400.0)
        assert prop.keyframes[1].time == 1.0

        prop.keyframes[1].roving = True

        assert prop.keyframes[1].time_units == 56845
        assert prop.keyframes[1].time == pytest.approx(2.2205078125)

    def test_flattening_the_path_moves_the_roving_key(self) -> None:
        """A shallower bow shortens the first segment, so AE pulls the key
        back to 0.819296875 s (20974 units)."""
        prop = self._bowed_path(40.0)
        prop.keyframes[1].roving = True
        assert prop.keyframes[1].time_units == 20974
        assert prop.keyframes[1].time == pytest.approx(0.819296875)

    def test_roving_survives_a_save(self, tmp_path: Path) -> None:
        project = parse_project_fresh(self.SAMPLE)
        comp = project.compositions[0]
        prop = comp.layers[0].transform["ADBE Position"]
        while prop.keyframes:
            prop.remove_key(0)
        for time, value in ((0.0, 0.0), (1.0, 100.0), (4.0, 600.0)):
            prop.add_key(time)
            prop.keyframes[-1].value = [value, 200.0, 0.0]
        prop.keyframes[1].roving = True
        moved = prop.keyframes[1].time_units

        out = tmp_path / "modified.aep"
        project.save(out)
        prop2 = (
            parse_aep(out).project.compositions[0].layers[0].transform["ADBE Position"]
        )
        assert prop2.keyframes[1].roving is True
        assert prop2.keyframes[1].time_units == moved

    def test_unroving_keeps_the_redistributed_time(self) -> None:
        """AE does not restore the original time: the redistribution already
        happened, and turning the flag off leaves the key where it moved to."""
        prop = self._bowed_path(400.0)
        prop.keyframes[1].roving = True
        moved = prop.keyframes[1].time_units

        prop.keyframes[1].roving = False

        assert prop.keyframes[1].roving is False
        assert prop.keyframes[1].time_units == moved

    def test_non_spatial_property_is_rejected(self) -> None:
        """AE raises here: "This property does not have a spatial
        PropertyValueType"."""
        project = parse_project_fresh(SAMPLES / "keyframe_misc.aep")
        prop = project.compositions[0].layers[0].transform["ADBE Scale"]
        assert not prop.is_spatial
        with pytest.raises(ValueError, match="spatial property"):
            prop.keyframes[1].roving = True

    @pytest.mark.parametrize("index", [0, -1])
    def test_first_and_last_keyframe_are_rejected(self, index: int) -> None:
        """AE silently no-ops these; py-aep raises so the caller sees it."""
        prop = self._bowed_path(400.0)
        with pytest.raises(ValueError, match="cannot rove"):
            prop.keyframes[index].roving = True


class TestRoundtripAutoBezierWrites:
    """The auto-bezier and continuity flags carry companion state.

    AE rewrites the derived values and forces companion flags when these are
    set, and - critically - it TRUSTS the stored bytes if the keyframe is
    later switched back to BEZIER: a stale 90% influence written under HOLD
    came back as 90 on the way out. So the bytes have to agree with the
    reader, not merely the reported values. All expectations are AE 2026
    measurements.
    """

    def _uneven_position(self) -> Property:
        """t = 0 / 1 / 4 with x = 0 / 100 / 600 - uneven in time, so a
        time-weighted tangent rule would disagree with AE's chord/6."""
        project = parse_project_fresh(SAMPLES / "effect_point_speed.aep")
        prop = project.compositions[0].layers[0].transform["ADBE Position"]
        while prop.keyframes:
            prop.remove_key(0)
        for time, x in ((0.0, 0.0), (1.0, 100.0), (4.0, 600.0)):
            prop.add_key(time)
            prop.keyframes[-1].value = [x, 0.0, 0.0]
        for keyframe in prop.keyframes:
            keyframe.in_interpolation_type = KeyframeInterpolationType.BEZIER
            keyframe.out_interpolation_type = KeyframeInterpolationType.BEZIER
        return prop

    def test_spatial_auto_bezier_writes_the_derived_tangents(self) -> None:
        prop = self._uneven_position()
        keyframe = prop.keyframes[1]
        keyframe.in_spatial_tangent = [-40.0, -10.0, 0.0]
        keyframe.out_spatial_tangent = [70.0, 25.0, 0.0]
        stored = keyframe._ldat_item.kf_data

        keyframe.spatial_auto_bezier = True

        assert list(stored.out_spatial_tangents) == pytest.approx([100.0, 0.0, 0.0])
        assert list(stored.in_spatial_tangents) == pytest.approx([-100.0, 0.0, 0.0])

    def test_spatial_auto_bezier_forces_continuity(self) -> None:
        prop = self._uneven_position()
        keyframe = prop.keyframes[1]
        keyframe.spatial_continuous = False

        keyframe.spatial_auto_bezier = True

        assert keyframe.spatial_continuous is True

    def test_clearing_spatial_auto_bezier_keeps_the_derived_tangents(self) -> None:
        """AE does not restore what was there before."""
        prop = self._uneven_position()
        keyframe = prop.keyframes[1]
        keyframe.spatial_auto_bezier = True
        keyframe.spatial_auto_bezier = False
        stored = keyframe._ldat_item.kf_data
        assert list(stored.out_spatial_tangents) == pytest.approx([100.0, 0.0, 0.0])

    def test_temporal_auto_bezier_is_per_dimension(self, tmp_path: Path) -> None:
        """2-D Scale 100->200->400 and 100->120->150 over 2 s gives per
        dimension speeds 150 and 25, not one shared scalar."""
        project = parse_project_fresh(SAMPLES / "keyframe_misc.aep")
        prop = project.compositions[0].layers[0].transform["ADBE Scale"]
        while prop.keyframes:
            prop.remove_key(0)
        for time, value in (
            (0.0, [100.0, 100.0, 100.0]),
            (1.0, [200.0, 120.0, 100.0]),
            (2.0, [400.0, 150.0, 100.0]),
        ):
            prop.add_key(time)
            prop.keyframes[-1].value = value
        for keyframe in prop.keyframes:
            keyframe.in_interpolation_type = KeyframeInterpolationType.BEZIER
            keyframe.out_interpolation_type = KeyframeInterpolationType.BEZIER

        prop.keyframes[1].temporal_auto_bezier = True

        out = tmp_path / "modified.aep"
        project.save(out)
        prop2 = parse_aep(out).project.compositions[0].layers[0].transform["ADBE Scale"]
        speeds = [ease.speed for ease in prop2.keyframes[1].in_temporal_ease]
        assert speeds == pytest.approx([150.0, 25.0, 0.0])
        influences = [ease.influence for ease in prop2.keyframes[1].in_temporal_ease]
        assert influences == pytest.approx([100.0 / 6.0] * 3)

    def test_temporal_auto_bezier_samples_each_dimension_at_its_own_speed(
        self,
    ) -> None:
        """Sampling a multi-dimensional auto-bezier property must give each
        dimension the curve it would have on its own.

        A single scalar ease applied across every dimension drove them all at
        dimension 0's speed, so y here read 131.875 at t=1.5 instead of
        134.6875 - visible on any Scale/Position whose axes move unequally.
        """
        curves = [(100.0, 200.0, 400.0), (100.0, 120.0, 150.0)]
        times = (0.0, 1.0, 2.0)

        project = parse_project_fresh(SAMPLES / "keyframe_misc.aep")
        transform = project.compositions[0].layers[0].transform
        scale = transform["ADBE Scale"]
        scale.remove_all_keys()
        for index, time in enumerate(times):
            scale.set_value_at_time(time, [curves[0][index], curves[1][index], 100.0])

        references = []
        for curve in curves:
            reference = parse_project_fresh(SAMPLES / "keyframe_misc.aep")
            rotation = reference.compositions[0].layers[0].transform["ADBE Rotate Z"]
            rotation.remove_all_keys()
            for index, time in enumerate(times):
                rotation.set_value_at_time(time, curve[index])
            references.append(rotation)

        for prop in [scale, *references]:
            for keyframe in prop.keyframes:
                keyframe.in_interpolation_type = KeyframeInterpolationType.BEZIER
                keyframe.out_interpolation_type = KeyframeInterpolationType.BEZIER
                keyframe.temporal_auto_bezier = True

        for sample in (1.25, 1.5, 1.75):
            composed = scale.value_at_time(sample)
            expected = [reference.value_at_time(sample) for reference in references]
            assert composed[:2] == pytest.approx(expected)

    def test_temporal_auto_bezier_forces_continuity_and_bezier(self) -> None:
        prop = self._uneven_position()
        keyframe = prop.keyframes[1]
        keyframe.in_interpolation_type = KeyframeInterpolationType.LINEAR
        keyframe.out_interpolation_type = KeyframeInterpolationType.LINEAR
        keyframe.temporal_continuous = False

        keyframe.temporal_auto_bezier = True

        assert keyframe.temporal_continuous is True
        assert keyframe.in_interpolation_type == KeyframeInterpolationType.BEZIER
        assert keyframe.out_interpolation_type == KeyframeInterpolationType.BEZIER

    def test_temporal_continuous_ties_the_out_speed_to_the_in_speed(self) -> None:
        """AE turns (10, 75) / (90, 25) into (10, 75) / (10, 25): the speeds
        are tied, both influences survive."""
        project = parse_project_fresh(SAMPLES / "keyframe_bezier_nonzero_speed.aep")
        prop = next(
            g
            for layer in project.compositions[0].layers
            for g in layer.transform.properties
            if g.keyframes and g.match_name == "ADBE Opacity"
        )
        keyframe = prop.keyframes[0]
        in_speed = keyframe.in_temporal_ease[0].speed
        out_influence = keyframe.out_temporal_ease[0].influence
        assert keyframe.out_temporal_ease[0].speed != in_speed

        keyframe.temporal_continuous = True

        assert keyframe.out_temporal_ease[0].speed == pytest.approx(in_speed)
        assert keyframe.out_temporal_ease[0].influence == pytest.approx(out_influence)

    def test_temporal_continuous_forces_bezier_and_uses_the_stored_speed(
        self,
    ) -> None:
        """AE 2026 (`scripts/jsx/temporal_continuous_probe.jsx`): setting
        temporal continuity rewrites BOTH interpolation types to BEZIER
        first, in all five in/out pairings tried. That is what makes the
        STORED in speed the one to copy - a LINEAR side reports the segment
        slope (100 on this ramp) but AE gives back the stored 10.
        """
        prop = self._uneven_position()
        keyframe = prop.keyframes[1]
        keyframe.in_temporal_ease = [KeyframeEase(speed=10.0, influence=75.0)]
        keyframe.out_temporal_ease = [KeyframeEase(speed=90.0, influence=25.0)]
        keyframe.in_interpolation_type = KeyframeInterpolationType.LINEAR
        # The LINEAR side reports the segment slope, not the stored 10.
        assert keyframe.in_temporal_ease[0].speed == pytest.approx(100.0)

        keyframe.temporal_continuous = True

        assert keyframe.in_interpolation_type == KeyframeInterpolationType.BEZIER
        assert keyframe.out_interpolation_type == KeyframeInterpolationType.BEZIER
        assert keyframe.in_temporal_ease[0].speed == pytest.approx(10.0)
        assert keyframe.in_temporal_ease[0].influence == pytest.approx(75.0)
        assert keyframe.out_temporal_ease[0].speed == pytest.approx(10.0)
        assert keyframe.out_temporal_ease[0].influence == pytest.approx(25.0)

    @pytest.mark.parametrize(
        "interpolation",
        [KeyframeInterpolationType.HOLD, KeyframeInterpolationType.LINEAR],
    )
    def test_interpolation_change_preserves_the_stored_ease(
        self, interpolation: KeyframeInterpolationType, tmp_path: Path
    ) -> None:
        """Changing the interpolation type must NOT rewrite the ease bytes.

        AE 2026 (`scripts/jsx/interpolation_ease_probe.jsx`): a keyframe
        eased (10, 75) / (90, 25) under BEZIER and then switched to LINEAR
        or HOLD keeps those bytes on disk - only the REPORTED ease changes,
        to the segment slope (LINEAR) or zero (HOLD). Switching back to
        BEZIER hands 10 / 75 and 90 / 25 straight back, and a keyframe that
        never carried an ease reports the stored `(0, 0)` under BEZIER
        rather than anything derived. Normalizing the bytes here wrote
        numbers AE never writes and destroyed the ease it gives back.
        """
        project = parse_project_fresh(
            SAMPLES / "keyframe_bezier_asymmetric_ease_1D.aep"
        )
        prop = next(
            g
            for layer in project.compositions[0].layers
            for g in layer.transform.properties
            if g.keyframes
        )
        keyframe = prop.keyframes[0]
        stored = keyframe._ldat_item.kf_data
        before = list(stored.in_influence), list(stored.out_influence)
        assert before[1] == pytest.approx([0.9])

        keyframe.in_interpolation_type = interpolation
        keyframe.out_interpolation_type = interpolation

        assert list(stored.in_influence) == pytest.approx(before[0])
        assert list(stored.out_influence) == pytest.approx(before[1])

        keyframe.in_interpolation_type = KeyframeInterpolationType.BEZIER
        keyframe.out_interpolation_type = KeyframeInterpolationType.BEZIER
        assert keyframe.out_temporal_ease[0].influence == pytest.approx(90.0)

        out = tmp_path / "modified.aep"
        project.save(out)
        prop2 = next(
            g
            for layer in parse_aep(out).project.compositions[0].layers
            for g in layer.transform.properties
            if g.keyframes
        )
        reloaded = prop2.keyframes[0]._ldat_item.kf_data
        assert list(reloaded.out_influence) == pytest.approx(before[1])
