"""state the model must refresh when a switch is written.

Measured in After Effects 2026
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import SAMPLES_DIR, parse_app_fresh

import py_aep

PROPERTY_DIR = SAMPLES_DIR / "models" / "property"
LAYER_DIR = SAMPLES_DIR / "models" / "layer"


def _walk(group, depth=0):
    if depth > 10:
        return
    for child in group:
        yield child
        if not hasattr(child, "keyframes"):
            yield from _walk(child, depth + 1)


class TestThreeDLayerRefreshesTransform:
    """AE 2026 renames `ADBE Rotate Z` the moment the 3-D switch is toggled -
    "Rotation" on a 2-D layer, "Z Rotation" on a 3-D one, in both directions.
    """

    def test_toggling_on_renames_rotation(self) -> None:
        app = parse_app_fresh(PROPERTY_DIR / "keyframe_1D.aep")
        layer = app.project.compositions[0].layers[0]
        rotate_z = layer.property("Transform").property("ADBE Rotate Z")
        assert not layer.three_d_layer
        assert str(rotate_z.name) == "Rotation"

        layer.three_d_layer = True

        assert str(rotate_z.name) == "Z Rotation"

    def test_toggling_off_restores_the_name(self) -> None:
        app = parse_app_fresh(PROPERTY_DIR / "keyframe_1D.aep")
        layer = app.project.compositions[0].layers[0]
        rotate_z = layer.property("Transform").property("ADBE Rotate Z")

        layer.three_d_layer = True
        layer.three_d_layer = False

        assert str(rotate_z.name) == "Rotation"

    def test_name_matches_a_reparse(self, tmp_path: Path) -> None:
        """The in-memory name must be the one a fresh parse reports."""
        app = parse_app_fresh(PROPERTY_DIR / "keyframe_1D.aep")
        layer = app.project.compositions[0].layers[0]
        layer.three_d_layer = True
        in_memory = str(layer.property("Transform").property("ADBE Rotate Z").name)

        out = tmp_path / "three_d.aep"
        app.project.save(out)

        app2 = parse_app_fresh(out)
        reparsed = (
            app2.project.compositions[0]
            .layers[0]
            .property("Transform")
            .property("ADBE Rotate Z")
        )
        assert in_memory == str(reparsed.name) == "Z Rotation"


class TestScaleZFollowsTheThreeDSwitch:
    """AE 2026: a Z of 40 set while 3-D reads 40; dropping the layer
    to 2-D reads 100; going back to 3-D still reads 100. The stored Z is
    DISCARDED on the way out of 3-D, not masked."""

    def _layer(self):
        app = py_aep.new()
        comp = app.project.root_folder.add_comp("Z", 320, 240, 1.0, 10.0, 24.0)
        layer = comp.add_solid([1, 0, 0], "ScaleZ", 320, 240, 1.0)
        return app, layer, layer.property("Transform").property("ADBE Scale")

    def test_three_d_shows_the_z(self) -> None:
        _app, layer, scale = self._layer()
        layer.three_d_layer = True
        scale.value = [60.0, 70.0, 40.0]
        assert scale.value == pytest.approx([60.0, 70.0, 40.0])

    def test_leaving_three_d_discards_the_z(self) -> None:
        _app, layer, scale = self._layer()
        layer.three_d_layer = True
        scale.value = [60.0, 70.0, 40.0]

        layer.three_d_layer = False
        assert scale.value == pytest.approx([60.0, 70.0, 100.0])

        layer.three_d_layer = True
        assert scale.value == pytest.approx([60.0, 70.0, 100.0])

    def test_the_discard_reaches_the_file(self, tmp_path: Path) -> None:
        app, layer, scale = self._layer()
        layer.three_d_layer = True
        scale.value = [60.0, 70.0, 40.0]
        layer.three_d_layer = False
        layer.three_d_layer = True

        out = tmp_path / "scale_z.aep"
        app.project.save(out)

        reparsed = (
            parse_app_fresh(out)
            .project.compositions[0]
            .layers[0]
            .property("Transform")
            .property("ADBE Scale")
        )
        assert reparsed.value == pytest.approx([60.0, 70.0, 100.0])

    def test_keyframed_scale_is_left_alone(self) -> None:
        """AE's behaviour on a keyframed Scale was not measured, so the switch
        must not flatten an animation on a guess."""
        _app, layer, scale = self._layer()
        layer.three_d_layer = True
        scale.set_value_at_time(0.0, [10.0, 20.0, 30.0])
        scale.set_value_at_time(1.0, [40.0, 50.0, 60.0])

        layer.three_d_layer = False

        assert len(scale.keyframes) == 2


class TestCameraAndLightSeparate:
    """AE 2026 accepts `dimensionsSeparated` on a camera AND a light position,
    reads it back true and keeps the position. py forced the
    getter to False, so the write never persisted - and the leader's Z was
    destroyed on the way (`_separate_static` parks the leader on its default).
    """

    @pytest.mark.parametrize(
        ("sample", "comp_name"),
        [("layer/type.aep", "type_camera"), ("layer/lightType.aep", "lightType_SPOT")],
    )
    def test_separation_persists(
        self, sample: str, comp_name: str | None, tmp_path: Path
    ) -> None:
        app = parse_app_fresh(SAMPLES_DIR / "models" / sample)
        comp = (
            next(c for c in app.project.compositions if c.name == comp_name)
            if comp_name
            else app.project.compositions[0]
        )
        layer = comp.layers[0]
        pos = layer.property("Transform").property("ADBE Position")
        before = list(pos.value)
        assert not pos.dimensions_separated

        pos.dimensions_separated = True

        assert pos.dimensions_separated
        out = tmp_path / "separated.aep"
        app.project.save(out)

        app2 = parse_app_fresh(out)
        comp2 = (
            next(c for c in app2.project.compositions if c.name == comp_name)
            if comp_name
            else app2.project.compositions[0]
        )
        pos2 = comp2.layers[0].property("Transform").property("ADBE Position")
        assert pos2.dimensions_separated
        # The Z the camera/light is positioned at must survive.
        assert pos2.value == pytest.approx(before)
        assert pos2.get_separation_follower(2).value == pytest.approx(before[2])

    def test_a_collapsed_group_is_not_a_separated_one(self) -> None:
        """`lightType.aep`'s ambient light has the enable byte's collapse bit
        set and AE reports `dimensionsSeparated` false - separation lives in
        the lock byte. Checked against every AE export in the corpus: the lock
        bit agrees 288/288, the enable bit 285/288."""
        app = parse_app_fresh(LAYER_DIR / "lightType.aep")
        comp = next(
            c for c in app.project.compositions if c.name == "lightType_AMBIENT"
        )
        pos = comp.layers[0].property("Transform").property("ADBE Position")

        assert pos._tdsb.collapsed is True
        assert pos.dimensions_separated is False


class TestRecombineResetsFollowers:
    """AE leaves a recombined follower unserialized, and its own export of a
    never-separated layer reports X / Y / Z = 0 even for a position of
    [960, 540, 0] (`before_separation.json`). The model must say the same as
    the file it just wrote."""

    def test_followers_read_zero_in_memory(self, tmp_path: Path) -> None:
        app = parse_app_fresh(PROPERTY_DIR / "transform_separated.aep")
        pos = next(
            p
            for comp in app.project.compositions
            for layer in comp.layers
            for p in _walk(layer)
            if getattr(p, "match_name", None) == "ADBE Position"
            and p.dimensions_separated
        )
        leader_before = list(pos.value)

        pos.dimensions_separated = False

        in_memory = [pos.get_separation_follower(d).value for d in range(3)]
        assert in_memory == pytest.approx([0.0, 0.0, 0.0])
        assert pos.value == pytest.approx(leader_before)

        out = tmp_path / "recombined.aep"
        app.project.save(out)
        app2 = parse_app_fresh(out)
        pos2 = next(
            p
            for comp in app2.project.compositions
            for layer in comp.layers
            for p in _walk(layer)
            if getattr(p, "match_name", None) == "ADBE Position"
        )
        on_disk = [pos2.get_separation_follower(d).value for d in range(3)]
        assert in_memory == pytest.approx(on_disk)


class TestPrecomposedEffectPoint:
    """AE keeps a Ramp start point at [40, 25] through a precompose.
    py re-resolved the moved layer's synthetic cdat, which for an effect
    param carries the `parT` default in 0-512 space, not the 0-1 an AE-written
    cdat holds."""

    def test_effect_point_survives_precompose(self) -> None:
        app = parse_app_fresh(PROPERTY_DIR / "effects.aep")
        comp = next(c for c in app.project.compositions if c.name == "effect_2dPoint")
        point = next(
            p
            for p in _walk(comp.layers[0])
            if getattr(p, "match_name", None) == "ADBE Lens Flare-0001"
        )
        before = list(point.value)

        new_comp = comp.precompose([0], "PreFX")

        moved = next(
            p
            for p in _walk(new_comp.layers[0])
            if getattr(p, "match_name", None) == "ADBE Lens Flare-0001"
        )
        assert moved.value == pytest.approx(before)

    def test_anchor_point_still_survives_precompose(self) -> None:
        """The sibling case: a synthesized LAYER cdat holds user units, so it
        must NOT be resolved again."""
        app = parse_app_fresh(PROPERTY_DIR / "keyframe_1D.aep")
        comp = app.project.compositions[0]
        before = list(
            comp.layers[0].property("Transform").property("ADBE Anchor Point").value
        )

        new_comp = comp.precompose([0], "Pre")

        after = (
            new_comp.layers[0].property("Transform").property("ADBE Anchor Point").value
        )
        assert after == pytest.approx(before)


class TestEaseSpeedsAreNotLayerTime:
    """Issue #225 item 4 also claims ease SPEEDS are in layer time. AE 2026
    reports the same speed for the same ease whatever the stretch (30/40 on
    a 100 % layer, on one stretched afterwards, and on one eased while
    already stretched), and py reads the stored value back unconverted. No
    conversion belongs here."""

    @pytest.mark.parametrize("stretch", [100.0, 200.0, 50.0])
    def test_speed_is_stretch_invariant(self, stretch: float) -> None:
        app = py_aep.new()
        comp = app.project.root_folder.add_comp("C", 320, 240, 1.0, 40.0, 24.0)
        layer = comp.add_solid([1, 1, 1], "L", 320, 240, 1.0)
        layer.stretch = stretch
        op = layer.property("Transform").property("Opacity")
        op.set_value_at_time(1.0, 0.0)
        op.set_value_at_time(5.0, 100.0)
        for kf in op.keyframes:
            kf.in_interpolation_type = py_aep.KeyframeInterpolationType.BEZIER
            kf.out_interpolation_type = py_aep.KeyframeInterpolationType.BEZIER
        op.keyframes[0].out_temporal_ease = [
            py_aep.KeyframeEase(speed=30.0, influence=40.0)
        ]

        assert op.keyframes[0].out_temporal_ease[0].speed == pytest.approx(30.0)
        assert op.keyframes[0].out_temporal_ease[0].influence == pytest.approx(40.0)
