"""Tests for keyframe mutation: add_key, remove_key, set_value(s)_at_time(s),
Shape creation from scratch, and numeric keyframe value persistence.

Mutation tests parse a fresh (uncached) copy so changes do not leak between
tests, and assert results survive a save / re-parse round-trip.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import get_comp

from py_aep import Application
from py_aep import parse as parse_aep
from py_aep.binary.chunk import write_aep
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
