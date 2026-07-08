"""Tests for Property model parsing with strengthened assertions."""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import (
    get_comp,
    get_first_layer,
    get_layer,
)

from py_aep import parse as parse_aep
from py_aep.enums import (
    KeyframeInterpolationType,
    Label,
    MaskFeatherFalloff,
    MaskMode,
    MaskMotionBlur,
    PropertyType,
)
from py_aep.models import Layer, MaskPropertyGroup, Property, PropertyGroup
from py_aep.models.layers import ShapeLayer, TextLayer

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "property"
BUGS_DIR = Path(__file__).parent.parent.parent / "samples" / "bugs"
LAYER_SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"
LAYER_SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"
VERSIONS_DIR = Path(__file__).parent.parent.parent / "samples" / "versions"
PROPERTY_SAMPLES_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "property"
)


def _find_property(layer: Layer, match_name: str) -> Property | None:
    """Find a property in the layer's transform by match_name."""
    for prop in layer.transform:
        if prop.match_name == match_name:
            return prop
    return None


def _deanimate(prop) -> None:
    """Remove all keyframes so the static `.value` setter is usable
    (setting a value on a keyframed property raises, as in ExtendScript)."""
    while prop.keyframes:
        prop.remove_key(0)


class TestRoundtripPropertyEnabled:
    """Roundtrip: toggle Layer.enabled and verify save/reload."""

    def test_disable_layer(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "is_modified_false.aep").project
        layer = project.compositions[0].layers[0]
        assert layer.enabled is True

        layer.enabled = False
        out = tmp_path / "disabled_layer.aep"
        project.save(out)

        project2 = parse_aep(out).project
        layer2 = project2.compositions[0].layers[0]
        assert layer2.enabled is False

    def test_reenable_layer(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "is_modified_false.aep").project
        layer = project.compositions[0].layers[0]

        layer.enabled = False
        out = tmp_path / "step1.aep"
        project.save(out)

        project2 = parse_aep(out).project
        layer2 = project2.compositions[0].layers[0]
        layer2.enabled = True
        out2 = tmp_path / "step2.aep"
        project2.save(out2)

        project3 = parse_aep(out2).project
        layer3 = project3.compositions[0].layers[0]
        assert layer3.enabled is True


class TestRoundtripMaskMode:
    """Roundtrip: change MaskPropertyGroup.mask_mode."""

    def test_change_mask_mode(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "mask_add.aep").project
        layer = project.compositions[0].layers[0]
        mask = layer.masks[0]
        assert isinstance(mask, MaskPropertyGroup)
        assert mask.mask_mode == MaskMode.ADD

        mask.mask_mode = MaskMode.SUBTRACT
        out = tmp_path / "mask_subtract.aep"
        project.save(out)

        project2 = parse_aep(out).project
        mask2 = project2.compositions[0].layers[0].masks[0]
        assert isinstance(mask2, MaskPropertyGroup)
        assert mask2.mask_mode == MaskMode.SUBTRACT


class TestRoundtripMaskInverted:
    """Roundtrip: toggle MaskPropertyGroup.inverted."""

    def test_invert_mask(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "mask_add.aep").project
        layer = project.compositions[0].layers[0]
        mask = layer.masks[0]
        assert isinstance(mask, MaskPropertyGroup)
        assert mask.inverted is False

        mask.inverted = True
        out = tmp_path / "mask_inverted.aep"
        project.save(out)

        project2 = parse_aep(out).project
        mask2 = project2.compositions[0].layers[0].masks[0]
        assert isinstance(mask2, MaskPropertyGroup)
        assert mask2.inverted is True


class TestRoundtripMaskLocked:
    """Roundtrip: toggle MaskPropertyGroup.locked."""

    def test_lock_mask(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "mask_add.aep").project
        layer = project.compositions[0].layers[0]
        mask = layer.masks[0]
        assert isinstance(mask, MaskPropertyGroup)
        assert mask.locked is False

        mask.locked = True
        out = tmp_path / "mask_locked.aep"
        project.save(out)

        project2 = parse_aep(out).project
        mask2 = project2.compositions[0].layers[0].masks[0]
        assert isinstance(mask2, MaskPropertyGroup)
        assert mask2.locked is True


class TestRoundtripMaskMotionBlur:
    """Roundtrip: change MaskPropertyGroup.mask_motion_blur."""

    def test_change_motion_blur(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "mask_motion_blur_same_as_layer.aep").project
        layer = project.compositions[0].layers[0]
        mask = layer.masks[0]
        assert isinstance(mask, MaskPropertyGroup)
        assert mask.mask_motion_blur == MaskMotionBlur.SAME_AS_LAYER

        mask.mask_motion_blur = MaskMotionBlur.ON
        out = tmp_path / "mask_motion_blur_on.aep"
        project.save(out)

        project2 = parse_aep(out).project
        mask2 = project2.compositions[0].layers[0].masks[0]
        assert isinstance(mask2, MaskPropertyGroup)
        assert mask2.mask_motion_blur == MaskMotionBlur.ON


class TestRoundtripMaskColor:
    """Roundtrip: change MaskPropertyGroup.color."""

    def test_change_color(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "mask_add.aep").project
        layer = project.compositions[0].layers[0]
        mask = layer.masks[0]
        assert isinstance(mask, MaskPropertyGroup)

        mask.color = [0.5, 0.25, 0.75]
        out = tmp_path / "mask_color.aep"
        project.save(out)

        project2 = parse_aep(out).project
        mask2 = project2.compositions[0].layers[0].masks[0]
        assert isinstance(mask2, MaskPropertyGroup)
        # Colors are stored as uint8, so precision is 1/255
        assert abs(mask2.color[0] - 0.5) < 0.005
        assert abs(mask2.color[1] - 0.25) < 0.005
        assert abs(mask2.color[2] - 0.75) < 0.005


class TestRoundtripMaskFeatherFalloff:
    """Roundtrip: change MaskPropertyGroup.mask_feather_falloff."""

    def test_change_feather_falloff(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "mask_feather_falloff_smooth.aep").project
        layer = project.compositions[0].layers[0]
        mask = layer.masks[0]
        assert isinstance(mask, MaskPropertyGroup)
        assert mask.mask_feather_falloff == MaskFeatherFalloff.FFO_SMOOTH

        mask.mask_feather_falloff = MaskFeatherFalloff.FFO_LINEAR
        out = tmp_path / "mask_feather_falloff_linear.aep"
        project.save(out)

        project2 = parse_aep(out).project
        mask2 = project2.compositions[0].layers[0].masks[0]
        assert isinstance(mask2, MaskPropertyGroup)
        assert mask2.mask_feather_falloff == MaskFeatherFalloff.FFO_LINEAR


class TestRoundtripFeatherPointRadius:
    """Roundtrip: modify FeatherPoint.radius and verify save/reload."""

    def test_modify_feather_radius(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "shape_feather.aep").project
        comp = get_comp(project, "shape_feather_points")
        layer = comp.layers[0]
        mask = layer.masks[0]
        shape = mask.properties[0].value
        assert len(shape.feather_points) == 2
        assert shape.feather_points[0].radius == 30.0

        shape.feather_points[0].radius = 55.0
        out = tmp_path / "modified_feather_radius.aep"
        project.save(out)

        project2 = parse_aep(out).project
        comp2 = get_comp(project2, "shape_feather_points")
        shape2 = comp2.layers[0].masks[0].properties[0].value
        assert shape2.feather_points[0].radius == 55.0
        # Second feather point unchanged
        assert shape2.feather_points[1].radius == 100.0

    def test_modify_feather_seg_loc(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "shape_feather.aep").project
        comp = get_comp(project, "shape_feather_points")
        layer = comp.layers[0]
        shape = layer.masks[0].properties[0].value
        assert shape.feather_points[0].seg_loc == 1

        shape.feather_points[0].seg_loc = 3
        out = tmp_path / "modified_feather_seg_loc.aep"
        project.save(out)

        project2 = parse_aep(out).project
        comp2 = get_comp(project2, "shape_feather_points")
        shape2 = comp2.layers[0].masks[0].properties[0].value
        assert shape2.feather_points[0].seg_loc == 3

    def test_modify_feather_tension(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "shape_feather.aep").project
        comp = get_comp(project, "shape_feather_inner_hold")
        layer = comp.layers[0]
        shape = layer.masks[0].properties[0].value
        assert shape.feather_points[1].tension == 0.5

        shape.feather_points[1].tension = 0.75
        out = tmp_path / "modified_feather_tension.aep"
        project.save(out)

        project2 = parse_aep(out).project
        comp2 = get_comp(project2, "shape_feather_inner_hold")
        shape2 = comp2.layers[0].masks[0].properties[0].value
        assert shape2.feather_points[1].tension == 0.75

    def test_feather_type_follows_radius_sign(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "shape_feather.aep").project
        comp = get_comp(project, "shape_feather_points")
        layer = comp.layers[0]
        shape = layer.masks[0].properties[0].value
        # Both are outer (positive radius)
        assert shape.feather_points[0].type == 0

        # Make it inner by setting negative radius
        shape.feather_points[0].radius = -30.0
        out = tmp_path / "modified_feather_type.aep"
        project.save(out)

        project2 = parse_aep(out).project
        comp2 = get_comp(project2, "shape_feather_points")
        shape2 = comp2.layers[0].masks[0].properties[0].value
        assert shape2.feather_points[0].type == 1
        assert shape2.feather_points[0].radius == -30.0


class TestValidateFeatherPoint:
    """Validation tests for FeatherPoint field constraints."""

    def test_seg_loc_rejects_negative(self) -> None:
        project = parse_aep(SAMPLES_DIR / "shape_feather.aep").project
        comp = get_comp(project, "shape_feather_points")
        fp = comp.layers[0].masks[0].properties[0].value
        with pytest.raises(ValueError, match="must be >= 0"):
            fp.feather_points[0].seg_loc = -1

    def test_seg_loc_rejects_float(self) -> None:
        project = parse_aep(SAMPLES_DIR / "shape_feather.aep").project
        comp = get_comp(project, "shape_feather_points")
        fp = comp.layers[0].masks[0].properties[0].value
        with pytest.raises(TypeError, match="expected an integer"):
            fp.feather_points[0].seg_loc = 1.5

    def test_rel_seg_loc_rejects_negative(self) -> None:
        project = parse_aep(SAMPLES_DIR / "shape_feather.aep").project
        comp = get_comp(project, "shape_feather_points")
        fp = comp.layers[0].masks[0].properties[0].value
        with pytest.raises(ValueError, match="must be >= 0"):
            fp.feather_points[0].rel_seg_loc = -0.1

    def test_rel_seg_loc_rejects_above_one(self) -> None:
        project = parse_aep(SAMPLES_DIR / "shape_feather.aep").project
        comp = get_comp(project, "shape_feather_points")
        fp = comp.layers[0].masks[0].properties[0].value
        with pytest.raises(ValueError, match="must be <= 1"):
            fp.feather_points[0].rel_seg_loc = 1.1

    def test_tension_rejects_negative(self) -> None:
        project = parse_aep(SAMPLES_DIR / "shape_feather.aep").project
        comp = get_comp(project, "shape_feather_inner_hold")
        fp = comp.layers[0].masks[0].properties[0].value
        with pytest.raises(ValueError, match="must be >= 0"):
            fp.feather_points[1].tension = -0.1

    def test_tension_rejects_above_one(self) -> None:
        project = parse_aep(SAMPLES_DIR / "shape_feather.aep").project
        comp = get_comp(project, "shape_feather_inner_hold")
        fp = comp.layers[0].masks[0].properties[0].value
        with pytest.raises(ValueError, match="must be <= 1"):
            fp.feather_points[1].tension = 1.1


class TestRoundtripKeyframeLabel:
    """Roundtrip: modify Keyframe.label and verify save/reload."""

    def test_modify_keyframe_label(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "keyframe_1D.aep").project
        comp = get_comp(project, "keyframe_bezier_ease_in_out_1D")
        layer = comp.layers[0]
        # Find the animated opacity property
        prop = _find_property(layer, "ADBE Opacity")
        assert len(prop.keyframes) >= 2
        original_label = prop.keyframes[0].label
        assert original_label != Label.RED

        prop.keyframes[0].label = Label.RED
        out = tmp_path / "modified_kf_label.aep"
        project.save(out)

        project2 = parse_aep(out).project
        comp2 = get_comp(project2, "keyframe_bezier_ease_in_out_1D")
        layer2 = comp2.layers[0]
        prop2 = _find_property(layer2, "ADBE Opacity")
        assert prop2.keyframes[0].label == Label.RED

    def test_modify_keyframe_roving(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "keyframe_1D.aep").project
        comp = get_comp(project, "keyframe_bezier_ease_in_out_1D")
        layer = comp.layers[0]
        prop = _find_property(layer, "ADBE Opacity")
        assert len(prop.keyframes) >= 2
        # Roving can only meaningfully be set on middle keyframes
        if len(prop.keyframes) >= 3:
            prop.keyframes[1].roving = True
            out = tmp_path / "modified_kf_roving.aep"
            project.save(out)

            project2 = parse_aep(out).project
            comp2 = get_comp(project2, "keyframe_bezier_ease_in_out_1D")
            prop2 = _find_property(comp2.layers[0], "ADBE Opacity")
            assert prop2.keyframes[1].roving is True


class TestRoundtripKeyframeInterpolationType:
    """Roundtrip: modify Keyframe interpolation type."""

    def test_change_interpolation_to_hold(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "keyframe_interpolation.aep").project
        comp = get_comp(project, "keyframe_LINEAR")
        layer = comp.layers[0]
        prop = _find_property(layer, "ADBE Position")
        assert len(prop.keyframes) >= 2
        assert (
            prop.keyframes[0].out_interpolation_type == KeyframeInterpolationType.LINEAR
        )

        prop.keyframes[0].out_interpolation_type = KeyframeInterpolationType.HOLD
        out = tmp_path / "modified_kf_interp.aep"
        project.save(out)

        project2 = parse_aep(out).project
        prop2 = _find_property(
            get_comp(project2, "keyframe_LINEAR").layers[0], "ADBE Position"
        )
        assert (
            prop2.keyframes[0].out_interpolation_type == KeyframeInterpolationType.HOLD
        )

    def test_change_in_interpolation(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "keyframe_interpolation.aep").project
        comp = get_comp(project, "keyframe_BEZIER")
        layer = comp.layers[0]
        prop = _find_property(layer, "ADBE Position")
        assert len(prop.keyframes) >= 2

        prop.keyframes[1].in_interpolation_type = KeyframeInterpolationType.LINEAR
        out = tmp_path / "modified_kf_in_interp.aep"
        project.save(out)

        project2 = parse_aep(out).project
        prop2 = _find_property(
            get_comp(project2, "keyframe_BEZIER").layers[0], "ADBE Position"
        )
        assert (
            prop2.keyframes[1].in_interpolation_type == KeyframeInterpolationType.LINEAR
        )


class TestRoundtripExpression:
    """Roundtrip: modify Property.expression and verify save/reload."""

    def test_change_expression(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "expression.aep").project
        comp = get_comp(project, "expression_enabled")
        layer = comp.layers[0]
        # Find any property with a non-empty expression
        prop = None
        for p in layer.transform:
            if p.expression:
                prop = p
                break
        assert prop is not None, "No property with expression found"
        match_name = prop.match_name

        prop.expression = "wiggle(5, 50)"
        out = tmp_path / "modified_expr.aep"
        project.save(out)

        project2 = parse_aep(out).project
        prop2 = _find_property(
            get_comp(project2, "expression_enabled").layers[0], match_name
        )
        assert prop2.expression == "wiggle(5, 50)"


class TestRoundtripShapeClosed:
    """Roundtrip: toggle Shape.closed and verify save/reload."""

    def test_open_closed_mask(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "mask.aep").project
        comp = get_comp(project, "is_mask_true")
        layer = comp.layers[0]
        mask = layer.masks[0]
        assert isinstance(mask, MaskPropertyGroup)
        mask_path = mask.property("ADBE Mask Shape")
        shape = mask_path.value
        assert shape.closed is True

        shape.closed = False
        out = tmp_path / "mask_opened.aep"
        project.save(out)

        project2 = parse_aep(out).project
        comp2 = get_comp(project2, "is_mask_true")
        mask2 = comp2.layers[0].masks[0]
        mask_path2 = mask2.property("ADBE Mask Shape")
        assert mask_path2.value.closed is False

    def test_close_open_mask(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "mask.aep").project
        comp = get_comp(project, "is_mask_true")
        layer = comp.layers[0]
        mask = layer.masks[0]
        mask_path = mask.property("ADBE Mask Shape")
        shape = mask_path.value

        # Open the mask
        shape.closed = False
        out = tmp_path / "step1.aep"
        project.save(out)

        # Re-close it
        project2 = parse_aep(out).project
        comp2 = get_comp(project2, "is_mask_true")
        mask2 = comp2.layers[0].masks[0]
        mask_path2 = mask2.property("ADBE Mask Shape")
        mask_path2.value.closed = True
        out2 = tmp_path / "step2.aep"
        project2.save(out2)

        project3 = parse_aep(out2).project
        comp3 = get_comp(project3, "is_mask_true")
        mask3 = comp3.layers[0].masks[0]
        mask_path3 = mask3.property("ADBE Mask Shape")
        assert mask_path3.value.closed is True


class TestRoundtripKeyframeEase:
    """Roundtrip: modify KeyframeEase speed/influence."""

    def test_change_bezier_ease(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "keyframe_interpolation.aep").project
        comp = get_comp(project, "keyframe_BEZIER")
        layer = comp.layers[0]
        prop = _find_property(layer, "ADBE Position")
        assert prop is not None
        assert len(prop.keyframes) >= 2

        kf = prop.keyframes[0]
        assert len(kf.out_temporal_ease) >= 1
        kf.out_temporal_ease[0].speed = 42.0
        kf.out_temporal_ease[0].influence = 75.0

        out = tmp_path / "modified_ease.aep"
        project.save(out)

        project2 = parse_aep(out).project
        prop2 = _find_property(
            get_comp(project2, "keyframe_BEZIER").layers[0], "ADBE Position"
        )
        assert prop2 is not None
        assert abs(prop2.keyframes[0].out_temporal_ease[0].speed - 42.0) < 0.01
        assert abs(prop2.keyframes[0].out_temporal_ease[0].influence - 75.0) < 0.01


class TestValidateKeyframeEaseInfluence:
    """Validation tests for KeyframeEase.influence bounds (0.1-100.0)."""

    def test_influence_rejects_below_min(self) -> None:
        project = parse_aep(SAMPLES_DIR / "keyframe_interpolation.aep").project
        comp = get_comp(project, "keyframe_BEZIER")
        layer = comp.layers[0]
        prop = _find_property(layer, "ADBE Position")
        assert prop is not None
        kf = prop.keyframes[0]
        with pytest.raises(ValueError, match="must be"):
            kf.out_temporal_ease[0].influence = 0.0

    def test_influence_rejects_above_max(self) -> None:
        project = parse_aep(SAMPLES_DIR / "keyframe_interpolation.aep").project
        comp = get_comp(project, "keyframe_BEZIER")
        layer = comp.layers[0]
        prop = _find_property(layer, "ADBE Position")
        assert prop is not None
        kf = prop.keyframes[0]
        with pytest.raises(ValueError, match="must be"):
            kf.out_temporal_ease[0].influence = 100.1


class TestRoundtripPropertyValue:
    """Roundtrip: modify Property.value and verify save/reload."""

    def test_change_scalar_value(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "is_modified_false.aep").project
        layer = project.compositions[0].layers[0]
        prop = _find_property(layer, "ADBE Rotate X")
        assert prop is not None
        assert prop._cdat is not None

        prop.value = 45.0
        out = tmp_path / "modified_rotate.aep"
        project.save(out)

        project2 = parse_aep(out).project
        prop2 = _find_property(project2.compositions[0].layers[0], "ADBE Rotate X")
        assert abs(prop2.value - 45.0) < 0.01

    def test_change_multidim_value(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "is_modified_false.aep").project
        layer = project.compositions[0].layers[0]
        prop = _find_property(layer, "ADBE Orientation")
        assert prop is not None
        assert prop._cdat is not None

        prop.value = [10.0, 20.0, 30.0]
        out = tmp_path / "modified_orientation.aep"
        project.save(out)

        project2 = parse_aep(out).project
        prop2 = _find_property(project2.compositions[0].layers[0], "ADBE Orientation")
        assert abs(prop2.value[0] - 10.0) < 0.01
        assert abs(prop2.value[1] - 20.0) < 0.01
        assert abs(prop2.value[2] - 30.0) < 0.01


class TestRoundtripExpressionCreate:
    """Roundtrip: add an expression to a property that had none."""

    def test_create_expression_on_empty(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "is_modified_false.aep").project
        layer = project.compositions[0].layers[0]
        prop = _find_property(layer, "ADBE Rotate Z")
        assert prop is not None
        assert prop.expression == ""
        assert prop._expression_utf8 is None

        prop.expression = "time * 90"
        assert prop._expression_utf8 is not None
        out = tmp_path / "new_expression.aep"
        project.save(out)

        project2 = parse_aep(out).project
        prop2 = _find_property(project2.compositions[0].layers[0], "ADBE Rotate Z")
        assert prop2.expression == "time * 90"

    def test_create_expression_sets_tdb4_marker(self) -> None:
        """Setting an expression must set AE's tdb4 expression-present
        marker. Without it AE silently DROPS the expression on open
        (verified against AE 2026); the py-only round-trip cannot catch
        that because py reads the Utf8 regardless of the marker.
        """
        project = parse_aep(SAMPLES_DIR / "is_modified_false.aep").project
        prop = _find_property(project.compositions[0].layers[0], "ADBE Rotate Z")
        assert prop is not None
        assert prop._tdb4.has_expression is False

        prop.expression = "time * 90"
        assert prop._tdb4.has_expression is True

        # Clearing removes the chunk and the marker again.
        prop.expression = ""
        assert prop._expression_utf8 is None
        assert prop._tdb4.has_expression is False


class TestRoundtripExpressionEnabled:
    """Roundtrip: toggle Property.expression_enabled."""

    def test_disable_expression(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "expression.aep").project
        comp = get_comp(project, "expression_enabled")
        layer = comp.layers[0]
        prop = None
        for p in layer.transform:
            if p.expression and p.expression_enabled:
                prop = p
                break
        assert prop is not None
        match_name = prop.match_name

        prop.expression_enabled = False
        out = tmp_path / "disabled_expr.aep"
        project.save(out)

        project2 = parse_aep(out).project
        prop2 = _find_property(
            get_comp(project2, "expression_enabled").layers[0], match_name
        )
        assert prop2.expression_enabled is False
        assert prop2.expression != ""

    def test_enable_expression(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "expression.aep").project
        comp = get_comp(project, "expression_disabled")
        layer = comp.layers[0]
        prop = None
        for p in layer.transform:
            if p.expression and not p.expression_enabled:
                prop = p
                break
        assert prop is not None
        match_name = prop.match_name

        prop.expression_enabled = True
        out = tmp_path / "enabled_expr.aep"
        project.save(out)

        project2 = parse_aep(out).project
        prop2 = _find_property(
            get_comp(project2, "expression_disabled").layers[0], match_name
        )
        assert prop2.expression_enabled is True

    def test_set_expression_enables_disabled(self, tmp_path: Path) -> None:
        # Assigning an expression to a property whose expression was DISABLED
        # must enable it (AE semantics) and clear the tdb4 disabled bit, so it
        # never persists the contradictory "has expression + disabled" state.
        project = parse_aep(SAMPLES_DIR / "expression.aep").project
        comp = get_comp(project, "expression_disabled")
        layer = comp.layers[0]
        prop = None
        for p in layer.transform:
            if p.expression and not p.expression_enabled:
                prop = p
                break
        assert prop is not None
        match_name = prop.match_name

        prop.expression = "100"
        assert prop.expression_enabled is True
        assert prop._tdb4._expr_flags == 0

        out = tmp_path / "reenabled_expr.aep"
        project.save(out)
        prop2 = _find_property(
            get_comp(parse_aep(out).project, "expression_disabled").layers[0],
            match_name,
        )
        assert prop2.expression == "100"
        assert prop2.expression_enabled is True


class TestRoundtripRotoBezier:
    """Roundtrip: toggle MaskPropertyGroup.roto_bezier."""

    def test_disable_roto_bezier(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "mask_rotobezier_on.aep").project
        layer = project.compositions[0].layers[0]
        mask = layer.masks[0]
        assert isinstance(mask, MaskPropertyGroup)
        assert mask.roto_bezier is True

        mask.roto_bezier = False
        out = tmp_path / "modified_roto.aep"
        project.save(out)

        project2 = parse_aep(out).project
        mask2 = project2.compositions[0].layers[0].masks[0]
        assert isinstance(mask2, MaskPropertyGroup)
        assert mask2.roto_bezier is False


class TestRoundtripDimensionsSeparated:
    """Roundtrip: toggle Property.dimensions_separated and verify save/reload."""

    def test_separate_dimensions(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "transform_separated.aep").project
        layer = project.compositions[0].layers[0]
        prop = _find_property(layer, "ADBE Position")
        assert prop is not None
        assert prop.dimensions_separated is True

        prop.dimensions_separated = False
        out = tmp_path / "unseparated.aep"
        project.save(out)

        project2 = parse_aep(out).project
        prop2 = _find_property(project2.compositions[0].layers[0], "ADBE Position")
        assert prop2.dimensions_separated is False

    def test_unseparate_dimensions(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "transform_separated.aep").project
        layer = project.compositions[0].layers[0]
        prop = _find_property(layer, "ADBE Position")
        assert prop is not None
        assert prop.dimensions_separated is True

        prop.dimensions_separated = False
        out = tmp_path / "unseparated.aep"
        project.save(out)

        project2 = parse_aep(out).project
        prop2 = _find_property(project2.compositions[0].layers[0], "ADBE Position")
        assert prop2.dimensions_separated is False


class TestPropertyRemove:
    """Tests for PropertyBase.remove()."""

    AEP = SAMPLES_DIR / "2_gaussian.aep"

    def test_remove_effect(self) -> None:
        """Remove an effect and verify the model updates."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        assert len(layer.effects.properties) == 2
        first_name = layer.effects.properties[0].name
        layer.effects.properties[1].remove()
        assert len(layer.effects.properties) == 1
        assert layer.effects.properties[0].name == first_name

    def test_remove_roundtrip(self, tmp_path: Path) -> None:
        """Remove an effect, save, reload and verify."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        layer.effects.properties[0].remove()
        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        layer2 = app2.project.compositions[0].layers[0]
        assert layer2.effects is not None
        assert len(layer2.effects.properties) == 1
        assert layer2.effects.properties[0].name == "Gaussian Blur 2"

    def test_remove_non_indexed_raises(self) -> None:
        """Removing from a non-indexed group raises ValueError."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        transform = [
            p for p in layer.properties if p.match_name == "ADBE Transform Group"
        ][0]
        position = [p for p in transform.properties if p.match_name == "ADBE Position"][
            0
        ]
        with pytest.raises(ValueError, match="non-indexed"):
            position.remove()

    def test_remove_all_effects(self) -> None:
        """Remove all effects leaves an empty parade."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        effects = layer.effects
        assert effects is not None
        effects.properties[1].remove()
        effects.properties[0].remove()
        assert len(effects.properties) == 0
        # layer.effects returns None when parade is empty
        assert layer.effects is None

    def test_remove_all_roundtrip(self, tmp_path: Path) -> None:
        """Remove all effects, save, reload and verify."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        effects = layer.effects
        assert effects is not None
        effects.properties[1].remove()
        effects.properties[0].remove()
        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        layer2 = app2.project.compositions[0].layers[0]
        # After removing all, effects returns None (empty parade)
        assert layer2.effects is None


class TestPropertyMoveTo:
    """Tests for PropertyBase.move_to()."""

    AEP = SAMPLES_DIR / "2_gaussian.aep"

    def test_move_to_basic(self) -> None:
        """Swap the order of two effects."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        first_name = layer.effects.properties[0].name
        second_name = layer.effects.properties[1].name
        # Move second to position 0
        layer.effects.properties[1].move_to(0)
        assert layer.effects.properties[0].name == second_name
        assert layer.effects.properties[1].name == first_name

    def test_move_to_roundtrip(self, tmp_path: Path) -> None:
        """Move effects around, save and reload."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        second_name = layer.effects.properties[1].name
        layer.effects.properties[1].move_to(0)
        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        layer2 = app2.project.compositions[0].layers[0]
        assert layer2.effects is not None
        assert layer2.effects.properties[0].name == second_name

    def test_move_to_same_index(self) -> None:
        """Moving to current position is a no-op."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        first_name = layer.effects.properties[0].name
        layer.effects.properties[0].move_to(0)
        assert layer.effects.properties[0].name == first_name

    def test_move_to_invalid_raises(self) -> None:
        """Invalid index raises IndexError."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        with pytest.raises(IndexError):
            layer.effects.properties[0].move_to(5)


class TestPropertyDuplicate:
    """Tests for PropertyBase.duplicate()."""

    AEP = SAMPLES_DIR / "2_gaussian.aep"

    def test_duplicate_effect(self) -> None:
        """Duplicate creates a new effect after the original."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        original = layer.effects.properties[0]
        new_prop = original.duplicate()
        assert len(layer.effects.properties) == 3
        assert layer.effects.properties[1] is new_prop
        assert new_prop.match_name == original.match_name

    def test_duplicate_roundtrip(self, tmp_path: Path) -> None:
        """Duplicate, save and reload."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        layer.effects.properties[0].duplicate()
        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        layer2 = app2.project.compositions[0].layers[0]
        assert layer2.effects is not None
        assert len(layer2.effects.properties) == 3
        # First and second should have same match name
        assert (
            layer2.effects.properties[0].match_name
            == layer2.effects.properties[1].match_name
        )

    def test_duplicate_non_indexed_raises(self) -> None:
        """Duplicating a non-indexed property raises ValueError."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        transform = [
            p for p in layer.properties if p.match_name == "ADBE Transform Group"
        ][0]
        position = [p for p in transform.properties if p.match_name == "ADBE Position"][
            0
        ]
        with pytest.raises(ValueError, match="non-indexed"):
            position.duplicate()

    def test_duplicate_preserves_values(self) -> None:
        """Duplicated effect has the same param values."""
        app = parse_aep(SAMPLES_DIR / "2_gaussian_20_30.aep")
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        original = layer.effects.properties[0]
        new_prop = original.duplicate()
        # Both should be PropertyGroups (effects)
        assert isinstance(new_prop, PropertyGroup)
        assert isinstance(original, PropertyGroup)
        # Check blurriness value matches
        orig_blur = [
            p for p in original.properties if p.match_name == "ADBE Gaussian Blur-0001"
        ]
        new_blur = [
            p for p in new_prop.properties if p.match_name == "ADBE Gaussian Blur-0001"
        ]
        if orig_blur and new_blur:
            assert orig_blur[0].value == new_blur[0].value

    def test_remove_then_duplicate(self, tmp_path: Path) -> None:
        """Remove all, duplicate last remaining, verify clean state."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        # Remove second
        layer.effects.properties[1].remove()
        assert len(layer.effects.properties) == 1
        # Duplicate remaining
        layer.effects.properties[0].duplicate()
        assert len(layer.effects.properties) == 2
        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        layer2 = app2.project.compositions[0].layers[0]
        assert layer2.effects is not None
        assert len(layer2.effects.properties) == 2


class TestMaskMutations:
    """Mutations on mask atoms, which span three chunks in the parade
    (`tdmn` + `mkif` + `tdgp`) instead of the usual `(tdmn, body)` pair."""

    AEP = SAMPLES_DIR / "mask.aep"

    @staticmethod
    def _parade_chunk_types(parade: PropertyGroup) -> list[str]:
        assert parade._tdgp is not None
        return [
            getattr(c, "list_type", None) or c.chunk_type for c in parade._tdgp.chunks
        ]

    def test_remove_mask_deletes_full_span(self) -> None:
        """remove() deletes tdmn, mkif and tdgp - no orphaned chunks."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        masks = layer.masks
        assert masks is not None
        assert len(masks.properties) == 2
        masks.properties[0].remove()
        assert len(masks.properties) == 1
        assert self._parade_chunk_types(masks) == [
            "tdsb",
            "tdsn",
            "tdmn",
            "mkif",
            "tdgp",
            "tdmn",
        ]

    def test_remove_mask_roundtrip(self, tmp_path: Path) -> None:
        """Remove a mask, save, reload and verify."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.masks is not None
        layer.masks.properties[0].remove()
        out = tmp_path / "out.aep"
        app.project.save(out)
        layer2 = parse_aep(out).project.compositions[0].layers[0]
        assert layer2.masks is not None
        assert len(layer2.masks.properties) == 1
        assert layer2.masks.properties[0].name == "Mask 2"

    def test_duplicate_mask(self) -> None:
        """Duplicate clones the mkif and rebuilds a MaskPropertyGroup."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        masks = layer.masks
        assert masks is not None
        original = masks.properties[0]
        assert isinstance(original, MaskPropertyGroup)
        new_prop = masks.properties[0].duplicate()
        assert len(masks.properties) == 3
        assert masks.properties[1] is new_prop
        assert isinstance(new_prop, MaskPropertyGroup)
        assert new_prop.is_mask
        assert new_prop.mask_mode == original.mask_mode
        assert new_prop.inverted == original.inverted
        # AE assigns the duplicate a fresh per-layer mask id (max+1) and the
        # matching "<base> <new_id>" name, not the source's id/name (verified
        # in AE 2026: duplicating "Mask 1" of ["Mask 1","Mask 2"] -> "Mask 3").
        assert original._mkif.mask_id == 1
        assert new_prop._mkif.mask_id == 3
        assert new_prop.name == "Mask 3"
        # The clone's mkif is an independent chunk.
        new_prop.inverted = not original.inverted
        assert new_prop.inverted != original.inverted

    def test_duplicate_mask_synthesizes_children(self) -> None:
        """The duplicate re-fills synthesized children like a fresh parse."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.masks is not None
        new_prop = layer.masks.properties[0].duplicate()
        assert isinstance(new_prop, MaskPropertyGroup)
        assert [c.name for c in new_prop.properties] == [
            "Mask Path",
            "Mask Feather",
            "Mask Opacity",
            "Mask Expansion",
        ]

    def test_duplicate_mask_roundtrip(self, tmp_path: Path) -> None:
        """Duplicate a mask, save, reload and verify."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.masks is not None
        layer.masks.properties[0].duplicate()
        out = tmp_path / "out.aep"
        app.project.save(out)
        layer2 = parse_aep(out).project.compositions[0].layers[0]
        assert layer2.masks is not None
        assert len(layer2.masks.properties) == 3
        assert all(isinstance(m, MaskPropertyGroup) for m in layer2.masks.properties)
        # AE inserts the copy after the source and names it "Mask 3" (max id
        # + 1), with a matching unique mask id - not a duplicate "Mask 1"/id 1.
        assert [m.name for m in layer2.masks.properties] == [
            "Mask 1",
            "Mask 3",
            "Mask 2",
        ]
        ids = [m._mkif.mask_id for m in layer2.masks.properties]
        assert ids == [1, 3, 2]
        assert len(set(ids)) == len(ids)

    def test_duplicate_renamed_mask(self) -> None:
        """A renamed mask's duplicate keeps the base name + a fresh number.

        AE 2026: duplicating "Eyes" (when ids [1, 2] exist) yields "Eyes 3"
        with mask id 3 - the source's base name plus the new max+1 id.
        """
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.masks is not None
        layer.masks.properties[0].name = "Eyes"
        new_prop = layer.masks.properties[0].duplicate()
        assert isinstance(new_prop, MaskPropertyGroup)
        assert new_prop.name == "Eyes 3"
        assert new_prop._mkif.mask_id == 3

    def test_move_mask_roundtrip(self, tmp_path: Path) -> None:
        """Move a mask, save, reload and verify the order."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.masks is not None
        layer.masks.properties[1].move_to(0)
        assert [m.name for m in layer.masks.properties] == ["Mask 2", "Mask 1"]
        out = tmp_path / "out.aep"
        app.project.save(out)
        layer2 = parse_aep(out).project.compositions[0].layers[0]
        assert layer2.masks is not None
        assert [m.name for m in layer2.masks.properties] == ["Mask 2", "Mask 1"]


class TestAddProperty:
    """Tests for PropertyGroup.add_property() (mask atoms)."""

    AEP = SAMPLES_DIR / "mask.aep"
    NO_MASK_AEP = (
        Path(__file__).parent.parent.parent
        / "samples"
        / "models"
        / "layer"
        / "gray_solid_1_above.aep"
    )

    def test_add_mask_to_existing_parade(self) -> None:
        """Adding a mask appends a default atom to the parade."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        masks = layer.masks
        assert masks is not None
        new_mask = masks.add_property("ADBE Mask Atom")
        assert isinstance(new_mask, MaskPropertyGroup)
        assert len(masks.properties) == 3
        assert masks.properties[2] is new_mask
        assert new_mask.name == "Mask 3"
        assert new_mask.is_mask
        assert new_mask.mask_mode == MaskMode.ADD
        assert new_mask.inverted is False
        assert new_mask._mkif.mask_id == 3

    def test_add_mask_by_display_name(self) -> None:
        """The display name `Mask` resolves to the mask atom match name."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.masks is not None
        new_mask = layer.masks.add_property("Mask")
        assert new_mask.match_name == "ADBE Mask Atom"

    def test_add_mask_synthesizes_children(self) -> None:
        """A new mask exposes the four canonical children, like AE."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.masks is not None
        new_mask = layer.masks.add_property("ADBE Mask Atom")
        assert isinstance(new_mask, MaskPropertyGroup)
        assert [c.name for c in new_mask.properties] == [
            "Mask Path",
            "Mask Feather",
            "Mask Opacity",
            "Mask Expansion",
        ]

    def test_add_mask_writes_minimal_chunks(self) -> None:
        """AE writes no Mask Shape subtree for a fresh mask - just
        `tdmn + mkif + tdgp[tdsb, tdsn, group end]`."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.masks is not None
        new_mask = layer.masks.add_property("ADBE Mask Atom")
        assert isinstance(new_mask, MaskPropertyGroup)
        assert new_mask._tdgp is not None
        assert [
            getattr(c, "list_type", None) or c.chunk_type for c in new_mask._tdgp.chunks
        ] == ["tdsb", "tdsn", "tdmn"]
        assert not new_mask._tdgp.synthetic

    def test_add_mask_roundtrip(self, tmp_path: Path) -> None:
        """Add a mask, save, reload and verify."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.masks is not None
        layer.masks.add_property("ADBE Mask Atom")
        out = tmp_path / "out.aep"
        app.project.save(out)
        layer2 = parse_aep(out).project.compositions[0].layers[0]
        assert layer2.masks is not None
        assert [m.name for m in layer2.masks.properties] == [
            "Mask 1",
            "Mask 2",
            "Mask 3",
        ]
        mask3 = layer2.masks.properties[2]
        assert isinstance(mask3, MaskPropertyGroup)
        assert mask3.mask_mode == MaskMode.ADD
        assert mask3._mkif.mask_id == 3
        assert [c.name for c in mask3.properties] == [
            "Mask Path",
            "Mask Feather",
            "Mask Opacity",
            "Mask Expansion",
        ]

    def test_add_first_mask_materializes_parade(self, tmp_path: Path) -> None:
        """Adding to a layer with no masks materializes the synthetic
        parade at the canonical position (before Transform Group)."""
        app = parse_aep(self.NO_MASK_AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.masks is None
        parade = layer["ADBE Mask Parade"]
        assert isinstance(parade, PropertyGroup)
        assert not parade._is_live()
        new_mask = parade.add_property("ADBE Mask Atom")
        assert parade._is_live()
        assert new_mask.name == "Mask 1"
        assert layer.masks is parade
        out = tmp_path / "out.aep"
        app.project.save(out)
        layer2 = parse_aep(out).project.compositions[0].layers[0]
        assert layer2.masks is not None
        assert [m.name for m in layer2.masks.properties] == ["Mask 1"]
        # Parade must be written before the Transform Group, as AE does.
        chunks = layer2._tdgp.chunks
        parade_idx = next(
            i
            for i, c in enumerate(chunks)
            if c.chunk_type == "tdmn"
            and getattr(c, "value", None) == "ADBE Mask Parade"
            and not c.synthetic
        )
        transform_idx = next(
            i
            for i, c in enumerate(chunks)
            if c.chunk_type == "tdmn"
            and getattr(c, "value", None) == "ADBE Transform Group"
        )
        assert parade_idx < transform_idx

    def test_add_mask_then_mutate(self, tmp_path: Path) -> None:
        """A new mask accepts attribute writes that survive a reload."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.masks is not None
        new_mask = layer.masks.add_property("ADBE Mask Atom")
        assert isinstance(new_mask, MaskPropertyGroup)
        new_mask.inverted = True
        new_mask.mask_mode = MaskMode.SUBTRACT
        out = tmp_path / "out.aep"
        app.project.save(out)
        layer2 = parse_aep(out).project.compositions[0].layers[0]
        assert layer2.masks is not None
        mask3 = layer2.masks.properties[2]
        assert isinstance(mask3, MaskPropertyGroup)
        assert mask3.inverted is True
        assert mask3.mask_mode == MaskMode.SUBTRACT

    def test_add_mask_color_cycles(self) -> None:
        """Outline colors cycle deterministically by creation index."""
        app = parse_aep(self.NO_MASK_AEP)
        layer = app.project.compositions[0].layers[0]
        parade = layer["ADBE Mask Parade"]
        assert isinstance(parade, PropertyGroup)
        colors = set()
        for _ in range(3):
            mask = parade.add_property("ADBE Mask Atom")
            assert isinstance(mask, MaskPropertyGroup)
            colors.add(tuple(mask.color))
        assert len(colors) == 3

    def test_add_mask_id_no_collision_after_remove(self) -> None:
        """A mask added after a mid-parade removal gets a fresh id and name
        (highest existing + 1), never colliding with a surviving mask."""
        app = parse_aep(self.AEP)  # mask.aep: Mask 1 (id 1), Mask 2 (id 2)
        masks = app.project.compositions[0].layers[0].masks
        assert masks is not None
        m3 = masks.add_property("ADBE Mask Atom")
        assert isinstance(m3, MaskPropertyGroup)
        assert m3._mkif.mask_id == 3
        # Remove the middle mask, then add another: count+1 would reuse id 3.
        masks.properties[1].remove()
        m_new = masks.add_property("ADBE Mask Atom")
        assert isinstance(m_new, MaskPropertyGroup)
        ids = [
            m._mkif.mask_id
            for m in masks.properties
            if isinstance(m, MaskPropertyGroup)
        ]
        names = [m.name for m in masks.properties]
        assert len(set(ids)) == len(ids), f"duplicate mask ids: {ids}"
        assert len(set(names)) == len(names), f"duplicate mask names: {names}"
        assert m_new._mkif.mask_id == 4  # max(1, 3) + 1, not count(2) + 1
        assert m_new.name == "Mask 4"

    def test_add_mask_roto_bezier_materializes(self, tmp_path: Path) -> None:
        """Enabling rotoBezier on a freshly added mask materializes the
        default full-frame Mask Shape AE writes (mirroring AE, which has
        no Mask Shape subtree until rotoBezier/path is set) and round-trips."""
        from py_aep.models.properties.shape import Shape

        app = parse_aep(self.NO_MASK_AEP)
        parade = app.project.compositions[0].layers[0]["ADBE Mask Parade"]
        assert isinstance(parade, PropertyGroup)
        mask = parade.add_property("ADBE Mask Atom")
        assert isinstance(mask, MaskPropertyGroup)
        assert mask.roto_bezier is False
        mask.roto_bezier = True
        assert mask.roto_bezier is True
        # The Mask Path now exposes the default full-frame rectangle (4
        # bezier vertices), not None, and exactly one Mask Shape is written.
        mask_path = next(
            p for p in mask.properties if p.match_name == "ADBE Mask Shape"
        )
        assert isinstance(mask_path, Property)
        assert isinstance(mask_path.value, Shape)
        assert len(mask_path.value.vertices) == 4
        assert (
            sum(
                1
                for c in mask._tdgp.chunks
                if getattr(c, "value", None) == "ADBE Mask Shape"
            )
            == 1
        )
        out = tmp_path / "out.aep"
        app.project.save(out)
        m2 = parse_aep(out).project.compositions[0].layers[0].masks.properties[-1]
        assert isinstance(m2, MaskPropertyGroup)
        assert m2.roto_bezier is True
        mp2 = next(p for p in m2.properties if p.match_name == "ADBE Mask Shape")
        assert isinstance(mp2, Property)
        assert isinstance(mp2.value, Shape)
        assert len(mp2.value.vertices) == 4

    def test_materialize_mask_shape_preserves_handle(self) -> None:
        """Materializing the Mask Shape keeps the existing child object.

        A handle fetched before enabling rotoBezier must stay valid (and
        keep writing to the live chunks) rather than being orphaned by a
        fresh-object swap.
        """
        from py_aep.models.properties.shape import Shape

        app = parse_aep(self.NO_MASK_AEP)
        parade = app.project.compositions[0].layers[0]["ADBE Mask Parade"]
        assert isinstance(parade, PropertyGroup)
        mask = parade.add_property("ADBE Mask Atom")
        assert isinstance(mask, MaskPropertyGroup)
        handle = mask.property("ADBE Mask Shape")
        mask.roto_bezier = True
        # The pre-fetched handle is still the live child (identity preserved).
        assert handle is mask.property("ADBE Mask Shape")
        assert handle in mask.properties
        assert isinstance(handle, Property)
        assert isinstance(handle.value, Shape)
        assert len(handle.value.vertices) == 4

    def test_add_mask_roto_bezier_false_is_noop(self) -> None:
        """Setting rotoBezier=False on a mask with no Mask Shape writes
        nothing (AE leaves a default mask without a Mask Shape subtree)."""
        app = parse_aep(self.NO_MASK_AEP)
        parade = app.project.compositions[0].layers[0]["ADBE Mask Parade"]
        assert isinstance(parade, PropertyGroup)
        mask = parade.add_property("ADBE Mask Atom")
        assert isinstance(mask, MaskPropertyGroup)
        mask.roto_bezier = False
        assert mask.roto_bezier is False
        assert not any(
            getattr(c, "value", None) == "ADBE Mask Shape" for c in mask._tdgp.chunks
        )

    def test_add_property_invalid_name_raises(self) -> None:
        """An unknown name raises ValueError."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.masks is not None
        with pytest.raises(ValueError, match="Cannot add property"):
            layer.masks.add_property("Not A Property")

    def test_add_property_non_indexed_raises(self) -> None:
        """Adding to a non-indexed group raises ValueError."""
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        transform = layer["ADBE Transform Group"]
        assert isinstance(transform, PropertyGroup)
        with pytest.raises(ValueError, match="Cannot add property"):
            transform.add_property("ADBE Mask Atom")

    def test_add_dropdown_control(self) -> None:
        """The Dropdown Menu Control adds with a generated pseudo match
        name and a Menu enum param carrying the default items."""
        app = parse_aep(SAMPLES_DIR / "2_gaussian.aep")
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        fx = layer.effects.add_property("ADBE Dropdown Control")
        assert isinstance(fx, PropertyGroup)
        assert fx.is_effect
        assert fx.name == "Dropdown Menu Control"
        assert fx.match_name.startswith("Pseudo/@@")
        assert len(fx.match_name) == len("Pseudo/@@") + 22
        assert [c.name for c in fx.properties] == ["Menu", "Compositing Options"]
        menu = fx.properties[0]
        assert isinstance(menu, Property)
        assert menu.value == 1
        assert menu.property_parameters == ["Item 1", "Item 2", "Item 3"]

    def test_add_dropdown_by_display_name(self) -> None:
        app = parse_aep(SAMPLES_DIR / "2_gaussian.aep")
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        fx = layer.effects.add_property("Dropdown Menu Control")
        assert fx.match_name.startswith("Pseudo/@@")

    def test_add_dropdowns_distinct_names(self) -> None:
        """Each dropdown gets a fresh per-instance match name; AE-style
        numbering counts dropdowns by the Pseudo namespace."""
        app = parse_aep(self.NO_MASK_AEP)
        parade = app.project.compositions[0].layers[0]["ADBE Effect Parade"]
        assert isinstance(parade, PropertyGroup)
        d1 = parade.add_property("ADBE Dropdown Control")
        d2 = parade.add_property("ADBE Dropdown Control")
        assert d1.match_name != d2.match_name
        assert d1.name == "Dropdown Menu Control"
        assert d2.name == "Dropdown Menu Control 2"

    def test_add_dropdown_roundtrip(self, tmp_path: Path) -> None:
        """A dropdown survives save/reload with its menu intact."""
        app = parse_aep(self.NO_MASK_AEP)
        parade = app.project.compositions[0].layers[0]["ADBE Effect Parade"]
        assert isinstance(parade, PropertyGroup)
        fx = parade.add_property("ADBE Dropdown Control")
        mn = fx.match_name
        out = tmp_path / "out.aep"
        app.project.save(out)
        layer2 = parse_aep(out).project.compositions[0].layers[0]
        assert layer2.effects is not None
        fx2 = layer2.effects.properties[0]
        assert isinstance(fx2, PropertyGroup)
        assert fx2.match_name == mn
        assert fx2.name == "Dropdown Menu Control"
        menu2 = fx2.properties[0]
        assert isinstance(menu2, Property)
        assert menu2.property_parameters == ["Item 1", "Item 2", "Item 3"]


class TestSetPropertyParameters:
    """Tests for the writable Property.property_parameters."""

    AEP = (
        Path(__file__).parent.parent.parent
        / "samples"
        / "models"
        / "property"
        / "2_gaussian.aep"
    )
    ITEMS = ["First Item", "Second Item", "(-", "Another Item", "Last Item"]

    def _menu(self, app):
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        fx = layer.effects.add_property("ADBE Dropdown Control")
        menu = fx.properties[0]
        assert isinstance(menu, Property)
        return fx, menu

    def test_set_items_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(self.AEP)
        fx, menu = self._menu(app)
        menu.property_parameters = self.ITEMS
        assert menu.property_parameters == self.ITEMS
        assert menu.nb_options == 5
        assert menu.max_value == 5
        assert menu.value_text == "First Item"

        out = tmp_path / "dropdown_items.aep"
        app.project.save(out)
        layer2 = parse_aep(out).project.compositions[0].layers[0]
        assert layer2.effects is not None
        fx2 = next(
            e for e in layer2.effects.properties if e.match_name == fx.match_name
        )
        menu2 = fx2.properties[0]
        assert menu2.property_parameters == self.ITEMS
        assert menu2.nb_options == 5
        assert menu2.max_value == 5
        assert menu2.value_text == "First Item"

    def test_builtin_effect_dropdown_raises(self) -> None:
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        blur = layer.effects.properties[0]
        blur_dims = next(p for p in blur.properties if p.name == "Blur Dimensions")
        assert blur_dims.property_parameters is not None
        with pytest.raises(ValueError, match="Dropdown Menu Control"):
            blur_dims.property_parameters = ["A", "B"]

    def test_regular_property_raises(self) -> None:
        app = parse_aep(self.AEP)
        layer = app.project.compositions[0].layers[0]
        opacity = layer.transform.property("ADBE Opacity")
        with pytest.raises(ValueError, match="Dropdown Menu Control"):
            opacity.property_parameters = ["A", "B"]

    def test_invalid_items_raise(self) -> None:
        app = parse_aep(self.AEP)
        _, menu = self._menu(app)
        for bad in (
            [],
            ["ok", ""],
            ["dup", "dup"],
            ["back\\slash"],
            ["pi|pe"],
            "not a list",
        ):
            with pytest.raises(ValueError):
                menu.property_parameters = bad  # type: ignore[assignment]

    def test_separator_may_repeat(self) -> None:
        app = parse_aep(self.AEP)
        _, menu = self._menu(app)
        menu.property_parameters = ["A", "(-", "B", "(-", "C"]
        assert menu.nb_options == 5


class TestAddEffect:
    """Tests for PropertyGroup.add_property() (expression controls)."""

    NO_FX_AEP = (
        Path(__file__).parent.parent.parent
        / "samples"
        / "models"
        / "layer"
        / "gray_solid_1_above.aep"
    )

    def test_add_slider_to_existing_parade(self) -> None:
        """Adding a control appends a default effect to the parade."""
        app = parse_aep(SAMPLES_DIR / "2_gaussian.aep")
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        fx = layer.effects.add_property("ADBE Slider Control")
        assert isinstance(fx, PropertyGroup)
        assert fx.is_effect
        assert fx.name == "Slider Control"
        assert fx.match_name == "ADBE Slider Control"
        assert fx.property_type == PropertyType.INDEXED_GROUP
        assert len(layer.effects.properties) == 3
        assert layer.effects.properties[2] is fx

    def test_add_slider_param_defaults(self) -> None:
        """The control's parameter carries the baked parT definition."""
        app = parse_aep(SAMPLES_DIR / "2_gaussian.aep")
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        fx = layer.effects.add_property("Slider Control")
        assert isinstance(fx, PropertyGroup)
        assert [c.name for c in fx.properties] == ["Slider", "Compositing Options"]
        slider = fx.properties[0]
        assert isinstance(slider, Property)
        assert slider.value == 0.0
        assert slider.min_value == -1000000
        assert slider.max_value == 1000000

    def test_add_all_controls(self) -> None:
        """Every baked control adds with its AE default name and param."""
        app = parse_aep(self.NO_FX_AEP)
        layer = app.project.compositions[0].layers[0]
        parade = layer["ADBE Effect Parade"]
        assert isinstance(parade, PropertyGroup)
        expected = {
            "ADBE Slider Control": ("Slider Control", "Slider"),
            "ADBE Color Control": ("Color Control", "Color"),
            "ADBE Checkbox Control": ("Checkbox Control", "Checkbox"),
            "ADBE Point Control": ("Point Control", "Point"),
            "ADBE Point3D Control": ("3D Point Control", "3D Point"),
            "ADBE Angle Control": ("Angle Control", "Angle"),
            "ADBE Layer Control": ("Layer Control", "Layer"),
        }
        for match_name, (fx_name, param_name) in expected.items():
            fx = parade.add_property(match_name)
            assert isinstance(fx, PropertyGroup)
            assert fx.name == fx_name
            assert fx.properties[0].name == param_name

    def test_add_first_effect_materializes_parade(self, tmp_path: Path) -> None:
        """The synthetic parade materializes at the canonical position."""
        app = parse_aep(self.NO_FX_AEP)
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is None
        parade = layer["ADBE Effect Parade"]
        assert isinstance(parade, PropertyGroup)
        assert not parade._is_live()
        parade.add_property("ADBE Slider Control")
        assert parade._is_live()
        assert layer.effects is parade
        out = tmp_path / "out.aep"
        app.project.save(out)
        layer2 = parse_aep(out).project.compositions[0].layers[0]
        assert layer2.effects is not None
        assert [e.name for e in layer2.effects.properties] == ["Slider Control"]
        chunks = layer2._tdgp.chunks
        parade_idx = next(
            i
            for i, c in enumerate(chunks)
            if c.chunk_type == "tdmn"
            and getattr(c, "value", None) == "ADBE Effect Parade"
            and not c.synthetic
        )
        transform_idx = next(
            i
            for i, c in enumerate(chunks)
            if c.chunk_type == "tdmn"
            and getattr(c, "value", None) == "ADBE Transform Group"
        )
        assert parade_idx < transform_idx

    def test_add_second_instance_naming(self) -> None:
        """A second instance of the same control gets a numbered name."""
        app = parse_aep(self.NO_FX_AEP)
        layer = app.project.compositions[0].layers[0]
        parade = layer["ADBE Effect Parade"]
        assert isinstance(parade, PropertyGroup)
        first = parade.add_property("ADBE Slider Control")
        second = parade.add_property("ADBE Slider Control")
        assert first.name == "Slider Control"
        assert second.name == "Slider Control 2"
        assert second.is_name_set

    def test_add_effect_roundtrip(self, tmp_path: Path) -> None:
        """Add controls, save, reload and verify values survive."""
        app = parse_aep(self.NO_FX_AEP)
        layer = app.project.compositions[0].layers[0]
        parade = layer["ADBE Effect Parade"]
        assert isinstance(parade, PropertyGroup)
        parade.add_property("ADBE Slider Control")
        parade.add_property("ADBE Color Control")
        out = tmp_path / "out.aep"
        app.project.save(out)
        layer2 = parse_aep(out).project.compositions[0].layers[0]
        assert layer2.effects is not None
        assert [e.name for e in layer2.effects.properties] == [
            "Slider Control",
            "Color Control",
        ]
        slider = layer2.effects.properties[0].properties[0]
        assert isinstance(slider, Property)
        assert slider.value == 0.0
        color = layer2.effects.properties[1].properties[0]
        assert isinstance(color, Property)
        assert color.value == [1.0, 0.0, 0.0, 1.0]

    def test_non_adjacent_same_type_order(self, tmp_path: Path) -> None:
        """Same-type effects separated by another effect keep their
        file order on reparse (match-name runs, not dict grouping)."""
        app = parse_aep(self.NO_FX_AEP)
        layer = app.project.compositions[0].layers[0]
        parade = layer["ADBE Effect Parade"]
        assert isinstance(parade, PropertyGroup)
        parade.add_property("ADBE Slider Control")
        parade.add_property("ADBE Color Control")
        parade.add_property("ADBE Slider Control")
        out = tmp_path / "out.aep"
        app.project.save(out)
        layer2 = parse_aep(out).project.compositions[0].layers[0]
        assert layer2.effects is not None
        assert [e.name for e in layer2.effects.properties] == [
            "Slider Control",
            "Color Control",
            "Slider Control 2",
        ]

    def test_add_effect_then_set_value(self, tmp_path: Path) -> None:
        """A new control's parameter accepts writes that survive reload."""
        app = parse_aep(self.NO_FX_AEP)
        layer = app.project.compositions[0].layers[0]
        parade = layer["ADBE Effect Parade"]
        assert isinstance(parade, PropertyGroup)
        fx = parade.add_property("ADBE Slider Control")
        assert isinstance(fx, PropertyGroup)
        slider = fx.properties[0]
        assert isinstance(slider, Property)
        slider.value = 42.5
        out = tmp_path / "out.aep"
        app.project.save(out)
        layer2 = parse_aep(out).project.compositions[0].layers[0]
        assert layer2.effects is not None
        slider2 = layer2.effects.properties[0].properties[0]
        assert isinstance(slider2, Property)
        assert slider2.value == 42.5

    def test_add_effect_name_no_collision_after_remove(self) -> None:
        """An effect added after a mid-parade removal gets a non-colliding
        name; count+1 alone would reuse a surviving instance's number."""
        app = parse_aep(self.NO_FX_AEP)
        parade = app.project.compositions[0].layers[0]["ADBE Effect Parade"]
        assert isinstance(parade, PropertyGroup)
        parade.add_property("ADBE Slider Control")  # Slider Control
        parade.add_property("ADBE Slider Control")  # Slider Control 2
        s3 = parade.add_property("ADBE Slider Control")  # Slider Control 3
        assert s3.name == "Slider Control 3"
        parade.properties[1].remove()  # remove Slider Control 2
        s_new = parade.add_property("ADBE Slider Control")
        names = [p.name for p in parade.properties]
        assert len(set(names)) == len(names), f"duplicate effect names: {names}"
        assert s_new.name != "Slider Control 3"

    def test_expression_control_pgui_is_zero(self) -> None:
        """AE writes an all-zero pgui GUID for expression controls; the
        builder must match deterministically, not emit a random GUID."""
        from py_aep.binary.mutations import build_expression_control
        from py_aep.data.effect_controls import EXPRESSION_CONTROLS

        skeleton = EXPRESSION_CONTROLS["ADBE Slider Control"]
        guids = []
        for _ in range(2):
            _, sspc = build_expression_control(
                "ADBE Slider Control",
                skeleton["name"],
                bytes.fromhex(skeleton["part"]),
                tdsn_name="-_0_/-",
                time_base=24576,
                layer_id=1,
            )
            pgui = next(c for c in sspc.chunks if c.chunk_type == "pgui")
            guids.append(pgui.guid)
        assert guids[0] == b"\x00" * 16
        assert guids[0] == guids[1]  # deterministic, not a random GUID


class TestAddInstalledEffect:
    """Tests for add_property() of effects already defined in the
    project's EfdG (cloned from the stored definition)."""

    def test_can_add_installed_effect(self) -> None:
        """The Effect Parade accepts effects present in the project's
        EfdG by match name or display name, and rejects absent ones."""
        app = parse_aep(SAMPLES_DIR / "effects.aep")
        layer = get_layer(app.project, "effect_2dPoint")
        fx = layer.effects
        assert fx is not None
        # effects.aep defines ADBE Lens Flare / CC Sphere / ADBE FreePin3.
        assert fx.can_add_property("ADBE Lens Flare") is True
        assert fx.can_add_property("Lens Flare") is True  # display name
        assert fx.can_add_property("CC Sphere") is True
        # Absent from this project, and pure nonsense: both rejected.
        assert fx.can_add_property("ADBE Gaussian Blur 2") is False
        assert fx.can_add_property("Some Custom Effect") is False
        # Expression controls are unaffected.
        assert fx.can_add_property("ADBE Slider Control") is True

    def test_can_add_installed_effect_only_on_effect_parade(self) -> None:
        """A non-Effect-Parade group never reports installed effects."""
        app = parse_aep(SAMPLES_DIR / "effects.aep")
        layer = get_layer(app.project, "effect_2dPoint")
        assert layer.transform.can_add_property("ADBE Lens Flare") is False

    def test_add_installed_effect_appends_default_instance(self) -> None:
        """Adding clones the EfdG definition and appends it."""
        app = parse_aep(SAMPLES_DIR / "effects.aep")
        layer = get_layer(app.project, "effect_2dPoint")
        fx = layer.effects
        assert fx is not None
        before = len(fx.properties)
        added = fx.add_property("ADBE Lens Flare")
        assert isinstance(added, PropertyGroup)
        assert added.is_effect
        assert added.match_name == "ADBE Lens Flare"
        assert added.property_type == PropertyType.INDEXED_GROUP
        assert len(fx.properties) == before + 1
        assert fx.properties[-1] is added
        # Second instance of an existing effect is numbered.
        assert added.name == "Lens Flare 2"

    def test_add_installed_effect_roundtrip(self, tmp_path: Path) -> None:
        """A cloned effect survives save + reparse intact."""
        app = parse_aep(SAMPLES_DIR / "effects.aep")
        layer = get_layer(app.project, "effect_2dPoint")
        assert layer.effects is not None
        layer.effects.add_property("ADBE Lens Flare")
        out = tmp_path / "out.aep"
        app.project.save(out)
        layer2 = get_layer(parse_aep(out).project, "effect_2dPoint")
        assert layer2.effects is not None
        assert [e.match_name for e in layer2.effects] == [
            "ADBE Lens Flare",
            "ADBE Lens Flare",
        ]

    def test_add_installed_effect_uses_pard_defaults_not_def_values(self) -> None:
        """AE's EfdG entry mirrors the first applied instance, but a
        freshly added instance is default-valued (value params dropped
        and re-synthesized).

        `2_gaussian_20_30.aep` has two Gaussian Blur 2 instances
        (Blurriness 20 and 30); the shared EfdG def carries the first
        (20), yet the added instance must use the pard default 25.
        """
        app = parse_aep(SAMPLES_DIR / "2_gaussian_20_30.aep")
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        added = layer.effects.add_property("ADBE Gaussian Blur 2")
        blur = next(
            p for p in added.properties if p.match_name == "ADBE Gaussian Blur 2-0001"
        )
        assert blur.value == blur.default_value == 25.0

    def test_add_installed_effect_drops_source_animation(self) -> None:
        """A cloned effect must be STATIC even when the EfdG definition
        mirrors an animated first instance.

        In `2_gaussian_animated.aep` the Gaussian Blur 2 Blurriness is
        keyframed, so the EfdG def carries keyframes; the added instance
        must come out static at the pard default (no keyframes).
        """
        app = parse_aep(SAMPLES_DIR / "2_gaussian_animated.aep")
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        added = layer.effects.add_property("ADBE Gaussian Blur 2")
        blur = next(
            p for p in added.properties if p.match_name == "ADBE Gaussian Blur 2-0001"
        )
        assert len(blur.keyframes) == 0
        assert blur.value == blur.default_value == 25.0

    def test_add_installed_effect_drops_source_expression(self) -> None:
        """A cloned effect must carry no expression even when the EfdG
        definition mirrors an expression.

        In `2_gaussian_expr.aep` the first Gaussian Blur 2 Blurriness has
        the expression `42`, so the EfdG def carries it; the added
        instance must come out static at the default with no expression
        (and must leave the existing instance's expression intact).
        """
        app = parse_aep(SAMPLES_DIR / "2_gaussian_expr.aep")
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        existing = [e for e in layer.effects if e.match_name == "ADBE Gaussian Blur 2"]
        added = layer.effects.add_property("ADBE Gaussian Blur 2")
        blur = next(
            p for p in added.properties if p.match_name == "ADBE Gaussian Blur 2-0001"
        )
        assert blur.expression == ""
        assert blur.expression_enabled is False
        assert len(blur.keyframes) == 0
        assert blur.value == blur.default_value == 25.0
        # The pre-existing expression-bearing instance is untouched.
        first_blur = next(
            p
            for p in existing[0].properties
            if p.match_name == "ADBE Gaussian Blur 2-0001"
        )
        assert first_blur.expression == "42"

    def test_add_installed_effect_defaults_survive_roundtrip(
        self, tmp_path: Path
    ) -> None:
        """The default value persists through save + reparse."""
        app = parse_aep(SAMPLES_DIR / "2_gaussian_20_30.aep")
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        layer.effects.add_property("ADBE Gaussian Blur 2")
        out = tmp_path / "out.aep"
        app.project.save(out)
        layer2 = parse_aep(out).project.compositions[0].layers[0]
        assert layer2.effects is not None
        added = [e for e in layer2.effects if e.match_name == "ADBE Gaussian Blur 2"][
            -1
        ]
        blur = next(
            p for p in added.properties if p.match_name == "ADBE Gaussian Blur 2-0001"
        )
        assert blur.value == 25.0


class TestAddTextSelector:
    """Tests for PropertyGroup.add_property() (text animator selectors)."""

    AEP = SAMPLES_DIR / "text_animator.aep"

    def _selectors(self, app: object) -> PropertyGroup:
        comp = app.project.compositions[0]
        layer = next(lyr for lyr in comp.layers if lyr.name == "Animate Me")
        animator = layer["ADBE Text Properties"]["ADBE Text Animators"].properties[0]
        sel = animator["ADBE Text Selectors"]
        assert isinstance(sel, PropertyGroup)
        return sel

    def test_selectors_group_is_indexed(self) -> None:
        sel = self._selectors(parse_aep(self.AEP))
        assert sel.property_type == PropertyType.INDEXED_GROUP
        assert sel.can_add_property("ADBE Text Wiggly Selector")
        assert sel.can_add_property("Range Selector")  # display name

    def test_add_each_selector_type(self) -> None:
        sel = self._selectors(parse_aep(self.AEP))
        expected = {
            "ADBE Text Selector": "Range Selector 2",  # sample already has 1
            "ADBE Text Wiggly Selector": "Wiggly Selector 1",
            "ADBE Text Expressible Selector": "Expression Selector 1",
        }
        for match_name, name in expected.items():
            s = sel.add_property(match_name)
            assert isinstance(s, PropertyGroup)
            assert s.match_name == match_name
            assert s.name == name
            assert s.can_set_enabled is True

    def test_range_selector_children(self) -> None:
        sel = self._selectors(parse_aep(self.AEP))
        rng = sel.add_property("ADBE Text Selector")
        assert isinstance(rng, PropertyGroup)
        assert [c.name for c in rng.properties] == [
            "Start",
            "End",
            "Offset",
            "Start",
            "End",
            "Offset",
            "Advanced",
        ]
        advanced = rng["ADBE Text Range Advanced"]
        assert isinstance(advanced, PropertyGroup)
        assert [c.name for c in advanced.properties] == [
            "Units",
            "Based On",
            "Mode",
            "Amount",
            "Shape",
            "Smoothness",
            "Ease High",
            "Ease Low",
            "Randomize Order",
            "Random Seed",
        ]

    def test_wiggly_and_expression_children(self) -> None:
        sel = self._selectors(parse_aep(self.AEP))
        wiggly = sel.add_property("ADBE Text Wiggly Selector")
        assert isinstance(wiggly, PropertyGroup)
        assert [c.name for c in wiggly.properties] == [
            "Mode",
            "Max Amount",
            "Min Amount",
            "Based On",
            "Wiggles/Second",
            "Correlation",
            "Temporal Phase",
            "Spatial Phase",
            "Lock Dimensions",
            "Random Seed",
        ]
        expr = sel.add_property("ADBE Text Expressible Selector")
        assert isinstance(expr, PropertyGroup)
        assert [c.name for c in expr.properties] == ["Based On", "Amount"]
        amount = expr.properties[1]
        assert isinstance(amount, Property)
        assert amount.value == [100.0, 100.0, 100.0]

    def test_selector_child_bounds_and_units(self) -> None:
        sel = self._selectors(parse_aep(self.AEP))
        rng = sel.add_property("ADBE Text Selector")
        assert isinstance(rng, PropertyGroup)
        start = rng.properties[0]  # ADBE Text Percent Start
        assert isinstance(start, Property)
        assert start.match_name == "ADBE Text Percent Start"
        assert start.min_value == -100
        assert start.max_value == 100
        assert start.units_text == "percent"

    def test_add_selectors_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(self.AEP)
        sel = self._selectors(app)
        sel.add_property("ADBE Text Wiggly Selector")
        sel.add_property("ADBE Text Expressible Selector")
        sel.add_property("ADBE Text Selector")
        out = tmp_path / "out.aep"
        app.project.save(out)
        sel2 = self._selectors(parse_aep(out))
        assert [(s.name, s.match_name) for s in sel2.properties] == [
            ("Range Selector 1", "ADBE Text Selector"),
            ("Wiggly Selector 1", "ADBE Text Wiggly Selector"),
            ("Expression Selector 1", "ADBE Text Expressible Selector"),
            ("Range Selector 2", "ADBE Text Selector"),
        ]

    def test_selectors_removable(self) -> None:
        """Selectors are children of an indexed group, so removable."""
        sel = self._selectors(parse_aep(self.AEP))
        sel.add_property("ADBE Text Wiggly Selector")
        assert len(sel.properties) == 2
        sel.properties[1].remove()
        assert [s.match_name for s in sel.properties] == ["ADBE Text Selector"]


class TestAddTextAnimator:
    """Tests for PropertyGroup.add_property('ADBE Text Animator')."""

    AEP = (
        Path(__file__).parent.parent.parent
        / "samples"
        / "models"
        / "selection"
        / "selection_text_source_text.aep"
    )

    def _animators(self, app: object) -> PropertyGroup:
        comp = app.project.compositions[0]
        layer = next(lyr for lyr in comp.layers if isinstance(lyr, TextLayer))
        anims = layer["ADBE Text Properties"]["ADBE Text Animators"]
        assert isinstance(anims, PropertyGroup)
        return anims

    def test_animators_group_can_add(self) -> None:
        anims = self._animators(parse_aep(self.AEP))
        assert anims.property_type == PropertyType.INDEXED_GROUP
        assert anims.can_add_property("ADBE Text Animator")
        assert anims.can_add_property("Animator")  # display name

    def test_add_pristine_animator(self) -> None:
        """A fresh animator has an empty Selectors group + the 103-prop
        pool, matching AE; it is not yet modified."""
        anims = self._animators(parse_aep(self.AEP))
        a1 = anims.add_property("ADBE Text Animator")
        assert isinstance(a1, PropertyGroup)
        assert a1.name == "Animator 1"
        assert a1.can_set_enabled is True
        assert a1.is_modified is False
        assert [(c.name, c.match_name) for c in a1.properties] == [
            ("Selectors", "ADBE Text Selectors"),
            ("Properties", "ADBE Text Animator Properties"),
        ]
        sel = a1["ADBE Text Selectors"]
        assert isinstance(sel, PropertyGroup)
        assert sel.property_type == PropertyType.INDEXED_GROUP
        assert len(sel.properties) == 0
        assert len(a1["ADBE Text Animator Properties"].properties) == 103

    def test_animator_numbering(self) -> None:
        anims = self._animators(parse_aep(self.AEP))
        a1 = anims.add_property("ADBE Text Animator")
        a2 = anims.add_property("ADBE Text Animator")
        assert a1.name == "Animator 1"
        assert a2.name == "Animator 2"

    def test_animator_modified_after_adding_selector(self) -> None:
        anims = self._animators(parse_aep(self.AEP))
        a1 = anims.add_property("ADBE Text Animator")
        assert a1.is_modified is False
        a1["ADBE Text Selectors"].add_property("ADBE Text Selector")
        assert a1.is_modified is True

    def test_add_animator_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(self.AEP)
        anims = self._animators(app)
        a1 = anims.add_property("ADBE Text Animator")
        a1["ADBE Text Selectors"].add_property("ADBE Text Wiggly Selector")
        anims.add_property("ADBE Text Animator")
        out = tmp_path / "out.aep"
        app.project.save(out)
        anims2 = self._animators(parse_aep(out))
        summary = [
            (
                a.name,
                len(a["ADBE Text Selectors"].properties),
                len(a["ADBE Text Animator Properties"].properties),
            )
            for a in anims2.properties
        ]
        assert summary == [("Animator 1", 1, 103), ("Animator 2", 0, 103)]


class TestAddAnimatorProperty:
    """add_property on ADBE Text Animator Properties (named-group
    exception: materialize a fixed-pool member in place)."""

    AEP = (
        Path(__file__).parent.parent.parent
        / "samples"
        / "models"
        / "selection"
        / "selection_text_source_text.aep"
    )

    def _props(self, app: object) -> PropertyGroup:
        comp = app.project.compositions[0]
        layer = next(lyr for lyr in comp.layers if isinstance(lyr, TextLayer))
        anims = layer["ADBE Text Properties"]["ADBE Text Animators"]
        pg = anims.add_property("ADBE Text Animator")["ADBE Text Animator Properties"]
        assert isinstance(pg, PropertyGroup)
        return pg

    def test_named_group_can_add(self) -> None:
        pg = self._props(parse_aep(self.AEP))
        assert pg.property_type == PropertyType.NAMED_GROUP
        assert pg.can_add_property("ADBE Text Position 3D")
        assert pg.can_add_property("Position")  # display name
        # The 8 variable-font axes are not addable.
        assert not pg.can_add_property("ADBE Text VF Axis 1")
        assert not pg.can_add_property("Not A Property")

    def test_add_materializes_in_place(self) -> None:
        """Adding keeps the pool position and count (103); idempotent."""
        pg = self._props(parse_aep(self.AEP))
        pos = pg.add_property("ADBE Text Position 3D")
        assert isinstance(pos, Property)
        assert pos.name == "Position"
        assert pos.property_index == 1  # Anchor Point is 0
        assert len(pg.properties) == 103
        # Idempotent: re-adding returns the same member, no new child.
        again = pg.add_property("ADBE Text Position 3D")
        assert again is pos
        assert len(pg.properties) == 103

    def test_added_property_parity(self) -> None:
        """An applied animator property carries units / isSpatial /
        canSetExpression matching AE (unlike the unapplied pool)."""
        pg = self._props(parse_aep(self.AEP))
        opacity = pg.add_property("ADBE Text Opacity")
        assert isinstance(opacity, Property)
        assert opacity.units_text == "percent"
        assert opacity.can_set_expression is True
        fill = pg.add_property("ADBE Text Fill Color")
        assert isinstance(fill, Property)
        assert fill.is_spatial is True
        assert fill.can_set_expression is True

    def test_add_by_display_name(self) -> None:
        pg = self._props(parse_aep(self.AEP))
        scale = pg.add_property("Scale")
        assert scale.match_name == "ADBE Text Scale 3D"

    def test_add_property_value_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(self.AEP)
        pg = self._props(app)
        op = pg.add_property("ADBE Text Opacity")
        assert isinstance(op, Property)
        op.value = 40.0
        fill = pg.add_property("ADBE Text Fill Color")
        assert isinstance(fill, Property)
        fill.value = [0.0, 1.0, 0.0, 1.0]
        out = tmp_path / "out.aep"
        app.project.save(out)
        layer2 = next(
            lyr
            for lyr in parse_aep(out).project.compositions[0].layers
            if isinstance(lyr, TextLayer)
        )
        pg2 = layer2["ADBE Text Properties"]["ADBE Text Animators"].properties[0][
            "ADBE Text Animator Properties"
        ]
        assert len(pg2.properties) == 103
        op2 = next(p for p in pg2.properties if p.match_name == "ADBE Text Opacity")
        assert isinstance(op2, Property)
        assert op2.value == 40.0
        fill2 = next(
            p for p in pg2.properties if p.match_name == "ADBE Text Fill Color"
        )
        assert isinstance(fill2, Property)
        assert fill2.value == [0.0, 1.0, 0.0, 1.0]


class TestAddShapeElement:
    """Tests for PropertyGroup.add_property() (shape elements)."""

    BASE_AEP = (
        Path(__file__).parent.parent.parent
        / "samples"
        / "models"
        / "layer"
        / "gray_solid_1_above.aep"
    )

    # AE 2026 creation names per element type (ground truth).
    EXPECTED_NAMES = {
        "ADBE Vector Group": "Group 1",
        "ADBE Vector Shape - Rect": "Rectangle Path 1",
        "ADBE Vector Shape - Ellipse": "Ellipse Path 1",
        "ADBE Vector Shape - Star": "Polystar Path 1",
        "ADBE Vector Shape - Group": "Path 1",
        "ADBE Vector Graphic - Fill": "Fill 1",
        "ADBE Vector Graphic - Stroke": "Stroke 1",
        "ADBE Vector Graphic - G-Fill": "Gradient Fill 1",
        "ADBE Vector Graphic - G-Stroke": "Gradient Stroke 1",
        "ADBE Vector Filter - Merge": "Merge Paths 1",
        "ADBE Vector Filter - Offset": "Offset Paths 1",
        "ADBE Vector Filter - PB": "Pucker & Bloat 1",
        "ADBE Vector Filter - Repeater": "Repeater 1",
        "ADBE Vector Filter - RC": "Round Corners 1",
        "ADBE Vector Filter - Trim": "Trim Paths 1",
        "ADBE Vector Filter - Twist": "Twist 1",
        "ADBE Vector Filter - Roughen": "Wiggle Paths 1",
        "ADBE Vector Filter - Wiggler": "Wiggle Transform 1",
        "ADBE Vector Filter - Zigzag": "Zig Zag 1",
    }

    def _new_contents(self) -> tuple[object, PropertyGroup]:
        app = parse_aep(self.BASE_AEP)
        layer = app.project.compositions[0].add_shape()
        contents = layer["ADBE Root Vectors Group"]
        assert isinstance(contents, PropertyGroup)
        return app, contents

    def test_add_every_element_type(self) -> None:
        """Every addable element creates with AE's creation name."""
        _app, contents = self._new_contents()
        for match_name, expected_name in self.EXPECTED_NAMES.items():
            el = contents.add_property(match_name)
            assert isinstance(el, PropertyGroup)
            assert el.match_name == match_name
            assert el.name == expected_name
        assert len(contents.properties) == len(self.EXPECTED_NAMES)

    def test_add_rect_minimal_chunks(self) -> None:
        """A new element is a named empty group; children stay AE-side
        defaults (synthesized, not written to binary)."""
        _app, contents = self._new_contents()
        rect = contents.add_property("ADBE Vector Shape - Rect")
        assert isinstance(rect, PropertyGroup)
        assert rect._tdgp is not None
        assert [
            getattr(c, "list_type", None) or c.chunk_type for c in rect._tdgp.chunks
        ] == ["tdsb", "tdsn", "tdmn"]
        assert [c.name for c in rect.properties] == [
            "Shape Direction",
            "Size",
            "Position",
            "Roundness",
        ]

    def test_add_group_carries_mandatory_subgroups(self) -> None:
        """A Vector Group is created with contents, transform and
        material subgroups; its contents accepts nested adds."""
        _app, contents = self._new_contents()
        group = contents.add_property("ADBE Vector Group")
        assert isinstance(group, PropertyGroup)
        inner = group["ADBE Vectors Group"]
        assert isinstance(inner, PropertyGroup)
        assert inner.property_type == PropertyType.INDEXED_GROUP
        assert inner.can_add_property("ADBE Vector Shape - Ellipse")
        nested = inner.add_property("ADBE Vector Shape - Ellipse")
        # Numbering is per container: this is the first ellipse here.
        assert nested.name == "Ellipse Path 1"

    def test_numbering_per_type_and_container(self) -> None:
        _app, contents = self._new_contents()
        contents.add_property("ADBE Vector Shape - Rect")
        contents.add_property("ADBE Vector Graphic - Fill")
        second = contents.add_property("ADBE Vector Shape - Rect")
        assert second.name == "Rectangle Path 2"

    def test_add_elements_roundtrip(self, tmp_path: Path) -> None:
        """Elements (incl. nested and non-adjacent same-type) survive
        save/reload in order."""
        app, contents = self._new_contents()
        group = contents.add_property("ADBE Vector Group")
        assert isinstance(group, PropertyGroup)
        group["ADBE Vectors Group"].add_property("ADBE Vector Shape - Star")
        contents.add_property("ADBE Vector Shape - Rect")
        contents.add_property("ADBE Vector Graphic - Fill")
        contents.add_property("ADBE Vector Shape - Rect")
        out = tmp_path / "out.aep"
        app.project.save(out)
        comp2 = parse_aep(out).project.compositions[0]
        layer2 = next(lyr for lyr in comp2.layers if isinstance(lyr, ShapeLayer))
        contents2 = layer2["ADBE Root Vectors Group"]
        assert isinstance(contents2, PropertyGroup)
        assert [e.name for e in contents2.properties] == [
            "Group 1",
            "Rectangle Path 1",
            "Fill 1",
            "Rectangle Path 2",
        ]
        group2 = contents2.properties[0]
        assert isinstance(group2, PropertyGroup)
        inner2 = group2["ADBE Vectors Group"]
        assert isinstance(inner2, PropertyGroup)
        assert [e.name for e in inner2.properties] == ["Polystar Path 1"]

    def test_add_fill_then_set_color(self, tmp_path: Path) -> None:
        """A new element's synthesized child accepts writes that
        survive reload."""
        app, contents = self._new_contents()
        fill = contents.add_property("ADBE Vector Graphic - Fill")
        assert isinstance(fill, PropertyGroup)
        color = next(p for p in fill.properties if p.name == "Color")
        assert isinstance(color, Property)
        color.value = [0.0, 1.0, 0.0, 1.0]
        out = tmp_path / "out.aep"
        app.project.save(out)
        comp2 = parse_aep(out).project.compositions[0]
        layer2 = next(lyr for lyr in comp2.layers if isinstance(lyr, ShapeLayer))
        contents2 = layer2["ADBE Root Vectors Group"]
        assert isinstance(contents2, PropertyGroup)
        fill2 = contents2.properties[0]
        assert isinstance(fill2, PropertyGroup)
        color2 = next(p for p in fill2.properties if p.name == "Color")
        assert isinstance(color2, Property)
        assert color2.value == [0.0, 1.0, 0.0, 1.0]

    def test_add_to_contents_rejects_non_shape_names(self) -> None:
        _app, contents = self._new_contents()
        with pytest.raises(ValueError, match="Cannot add property"):
            contents.add_property("ADBE Mask Atom")
        with pytest.raises(ValueError, match="Cannot add property"):
            contents.add_property("ADBE Slider Control")

    def test_filter_children_synthesized(self) -> None:
        """Shape filters report their full child sets (from specs),
        matching ExtendScript - including the nested Wiggle Transform."""
        _app, contents = self._new_contents()
        expected = {
            "ADBE Vector Filter - Merge": ["Mode"],
            "ADBE Vector Filter - Trim": [
                "Start",
                "End",
                "Offset",
                "Trim Multiple Shapes",
            ],
            "ADBE Vector Filter - Twist": ["Angle", "Center"],
            "ADBE Vector Filter - Zigzag": ["Size", "Ridges per segment", "Points"],
        }
        for match_name, child_names in expected.items():
            el = contents.add_property(match_name)
            assert isinstance(el, PropertyGroup)
            assert [c.name for c in el.properties] == child_names

        wiggler = contents.add_property("ADBE Vector Filter - Wiggler")
        assert isinstance(wiggler, PropertyGroup)
        transform = wiggler["ADBE Vector Wiggler Transform"]
        assert isinstance(transform, PropertyGroup)
        assert [c.name for c in transform.properties] == [
            "Anchor Point",
            "Position",
            "Scale",
            "Rotation",
        ]
        assert transform.can_set_enabled is False

    def test_filter_child_bounds_and_units(self) -> None:
        """Synthesized filter children carry the min/max and units
        ExtendScript reports."""
        _app, contents = self._new_contents()
        trim = contents.add_property("ADBE Vector Filter - Trim")
        assert isinstance(trim, PropertyGroup)
        start = trim.properties[0]
        assert isinstance(start, Property)
        assert start.name == "Start"
        assert start.min_value == 0
        assert start.max_value == 100
        assert start.units_text == "percent"

    def test_path_element_has_shape_direction(self) -> None:
        """The Path element exposes Shape Direction + Path (the path
        property is spatial), matching ExtendScript."""
        _app, contents = self._new_contents()
        path = contents.add_property("ADBE Vector Shape - Group")
        assert isinstance(path, PropertyGroup)
        assert [c.name for c in path.properties] == ["Shape Direction", "Path"]
        path_prop = path.properties[1]
        assert isinstance(path_prop, Property)
        assert path_prop.is_spatial is True

    def test_add_path_value_is_empty_shape(self) -> None:
        """A fresh Path element's value is an empty Shape, not None
        (the empty bezier path carries no ldat chunk)."""
        from py_aep.models.properties.shape import Shape

        _app, contents = self._new_contents()
        path = contents.add_property("ADBE Vector Shape - Group")
        assert isinstance(path, PropertyGroup)
        path_prop = path["ADBE Vector Shape"]
        assert isinstance(path_prop, Property)
        assert path_prop.name == "Path"
        value = path_prop.value
        assert isinstance(value, Shape)
        assert value.vertices == []

    def test_set_path_geometry_marks_normalized_and_roundtrips(
        self, tmp_path: Path
    ) -> None:
        """Setting a from-scratch Shape writes a `normalized` shph (bit 0)
        and the absolute vertices survive reload. Without bit 0 AE reads
        the normalized points as literal coordinates (AE 2026 verified)."""
        from py_aep.binary.utils import find_by_type, recursive_find
        from py_aep.models.properties.shape import Shape

        app, contents = self._new_contents()
        path = contents.add_property("ADBE Vector Shape - Group")
        assert isinstance(path, PropertyGroup)
        path_prop = path["ADBE Vector Shape"]
        assert isinstance(path_prop, Property)
        tri = [[100.0, 100.0], [300.0, 100.0], [200.0, 280.0]]
        path_prop.value = Shape(tri, closed=True)

        out = tmp_path / "path.aep"
        app.project.save(out)
        reparsed = parse_aep(out).project
        rifx = reparsed._rifx
        shph = find_by_type(
            chunks=recursive_find(rifx.chunks, list_type="shap")[0].chunks,
            chunk_type="shph",
        )
        assert shph.normalized is True
        assert shph.open is False

        comp2 = reparsed.compositions[0]
        layer2 = next(lyr for lyr in comp2.layers if isinstance(lyr, ShapeLayer))
        contents2 = layer2["ADBE Root Vectors Group"]
        assert isinstance(contents2, PropertyGroup)
        path2 = contents2.properties[0]
        assert isinstance(path2, PropertyGroup)
        verts2 = path2["ADBE Vector Shape"].value.vertices
        for got, want in zip(verts2, tri):
            assert got == pytest.approx(want, abs=1e-3)

    def test_set_vector_position_survives_reload(self, tmp_path: Path) -> None:
        """Setting a shape group's Vector Position writes the canonical
        tdb4 flags AE honours (else AE silently shows 0,0; AE 2026
        verified) and the value survives reload."""
        app, contents = self._new_contents()
        group = contents.add_property("ADBE Vector Group")
        assert isinstance(group, PropertyGroup)
        transform = group["ADBE Vector Transform Group"]
        assert isinstance(transform, PropertyGroup)
        pos = next(p for p in transform.properties if p.name == "Position")
        assert isinstance(pos, Property)
        pos.value = [200.0, 160.0]
        assert pos._tdb4 is not None
        assert pos._tdb4._spatial_static_flags == 0x0F
        assert pos._tdb4._pad2a == 3
        assert pos._tdb4._value_hint_type == 0xFFFF
        assert pos._tdb4._property_category == 0x09

        out = tmp_path / "vpos.aep"
        app.project.save(out)
        comp2 = parse_aep(out).project.compositions[0]
        layer2 = next(lyr for lyr in comp2.layers if isinstance(lyr, ShapeLayer))
        group2 = layer2["ADBE Root Vectors Group"].properties[0]
        assert isinstance(group2, PropertyGroup)
        pos2 = next(
            p
            for p in group2["ADBE Vector Transform Group"].properties
            if p.name == "Position"
        )
        assert pos2.value == [200.0, 160.0]


class TestRoundtripName:
    """Roundtrip: modify PropertyBase.name and verify save/reload."""

    def test_modify_effect_group_name(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "2_gaussian.aep").project
        layer = get_first_layer(project)
        effect = layer.effects.properties[0]
        assert effect.name == "Gaussian Blur"

        effect.name = "My Blur"
        out = tmp_path / "renamed_effect.aep"
        project.save(out)

        project2 = parse_aep(out).project
        layer2 = get_first_layer(project2)
        assert layer2.effects.properties[0].name == "My Blur"

    def test_modify_mask_name(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "mask_add.aep").project
        layer = get_first_layer(project)
        mask = layer.masks.properties[0]
        assert isinstance(mask, MaskPropertyGroup)

        mask.name = "Custom Mask"
        out = tmp_path / "renamed_mask.aep"
        project.save(out)

        project2 = parse_aep(out).project
        layer2 = get_first_layer(project2)
        mask2 = layer2.masks.properties[0]
        assert mask2.name == "Custom Mask"


class TestRoundtripProxyBody:
    """Roundtrip: modify synthesized (ProxyBody-backed) property attributes."""

    @staticmethod
    def _find_synthesized_effect_prop(
        layer: Layer, effect_index: int, match_name: str
    ) -> Property:
        """Find a synthesized effect property by match name."""
        effect = layer.effects.properties[effect_index]
        assert isinstance(effect, PropertyGroup)
        for prop in effect.properties:
            if isinstance(prop, Property) and prop.match_name == match_name:
                return prop
        raise AssertionError(f"Property {match_name} not found in effect")

    def test_synthesized_effect_property_is_attached(self) -> None:
        """Synthesized effect properties are attached before user code sees them."""
        project = parse_aep(SAMPLES_DIR / "2_gaussian.aep").project
        layer = get_first_layer(project)
        effect = layer.effects.properties[0]
        blur = self._find_synthesized_effect_prop(layer, 0, "ADBE Gaussian Blur 2-0001")

        assert isinstance(effect, PropertyGroup)
        assert blur.parent_property is effect

    def test_modify_synthesized_value(self, tmp_path: Path) -> None:
        """Modify the value of a synthesized (default) effect property."""
        project = parse_aep(SAMPLES_DIR / "2_gaussian.aep").project
        layer = get_first_layer(project)
        blur = self._find_synthesized_effect_prop(layer, 0, "ADBE Gaussian Blur 2-0001")
        original = blur.value
        blur.value = 42.0
        out = tmp_path / "proxy_value.aep"
        project.save(out)

        project2 = parse_aep(out).project
        layer2 = get_first_layer(project2)
        blur2 = self._find_synthesized_effect_prop(
            layer2, 0, "ADBE Gaussian Blur 2-0001"
        )
        assert blur2.value == 42.0
        assert blur2.value != original

    def test_synthesized_enabled_read_only(self) -> None:
        """Effect-parameter `enabled` is read-only (AE `canSetEnabled` is False)."""
        project = parse_aep(SAMPLES_DIR / "2_gaussian.aep").project
        layer = get_first_layer(project)
        blur = self._find_synthesized_effect_prop(layer, 0, "ADBE Gaussian Blur 2-0001")
        assert blur.enabled is True
        assert blur.can_set_enabled is False
        with pytest.raises(AttributeError):
            blur.enabled = False

    def test_modify_synthesized_name(self, tmp_path: Path) -> None:
        """Modify the name of a synthesized effect property."""
        project = parse_aep(SAMPLES_DIR / "2_gaussian.aep").project
        layer = get_first_layer(project)
        blur = self._find_synthesized_effect_prop(layer, 0, "ADBE Gaussian Blur 2-0001")
        blur.name = "Custom Blur Name"
        out = tmp_path / "proxy_name.aep"
        project.save(out)

        project2 = parse_aep(out).project
        layer2 = get_first_layer(project2)
        blur2 = self._find_synthesized_effect_prop(
            layer2, 0, "ADBE Gaussian Blur 2-0001"
        )
        assert blur2.name == "Custom Blur Name"


class TestValueValidation:
    """Tests for Property.value setter min/max validation."""

    def test_scalar_below_min_raises(self) -> None:
        """Setting a scalar value below min_value raises ValueError."""
        # Fresh parse (not the cached parse_project_fresh): _deanimate mutates the
        # property, which would corrupt the session-shared cached Project.
        project = parse_aep(SAMPLES_DIR / "property_types.aep").project
        layer = get_layer(project, "property_1D_opacity")
        opacity = _find_property(layer, "ADBE Opacity")
        assert opacity is not None
        _deanimate(opacity)
        assert opacity.has_min
        assert opacity.min_value == 0
        with pytest.raises(ValueError, match="must be >= 0"):
            opacity.value = -10.0

    def test_scalar_above_max_raises(self) -> None:
        """Setting a scalar value above max_value raises ValueError."""
        project = parse_aep(SAMPLES_DIR / "property_types.aep").project
        layer = get_layer(project, "property_1D_opacity")
        opacity = _find_property(layer, "ADBE Opacity")
        assert opacity is not None
        _deanimate(opacity)
        assert opacity.has_max
        assert opacity.max_value == 100
        with pytest.raises(ValueError, match="must be <= 100"):
            opacity.value = 150.0

    def test_valid_value_accepted(self) -> None:
        """Setting a value within bounds does not raise."""
        project = parse_aep(SAMPLES_DIR / "property_types.aep").project
        layer = get_layer(project, "property_1D_opacity")
        opacity = _find_property(layer, "ADBE Opacity")
        assert opacity is not None
        _deanimate(opacity)
        opacity.value = 50.0
        assert opacity.value == 50.0

    def test_wrong_list_length_raises(self) -> None:
        """Setting a list with wrong number of dimensions raises ValueError."""
        project = parse_aep(SAMPLES_DIR / "property_types.aep").project
        layer = get_layer(project, "property_3D_position")
        position = _find_property(layer, "ADBE Position")
        assert position is not None
        _deanimate(position)
        assert position.dimensions == 3
        with pytest.raises(ValueError, match="expected 3 elements, got 2"):
            position.value = [100.0, 200.0]

    def test_list_on_scalar_raises(self) -> None:
        """Setting a list on a scalar (1D) property raises TypeError."""
        project = parse_aep(SAMPLES_DIR / "property_types.aep").project
        layer = get_layer(project, "property_1D_opacity")
        opacity = _find_property(layer, "ADBE Opacity")
        assert opacity is not None
        _deanimate(opacity)
        assert opacity.dimensions == 1
        with pytest.raises(TypeError, match="expected a number, got list"):
            opacity.value = [50.0, 60.0]

    def test_scalar_on_multidim_raises(self) -> None:
        """Setting a scalar on a multi-dimensional property raises TypeError."""
        project = parse_aep(SAMPLES_DIR / "property_types.aep").project
        layer = get_layer(project, "property_3D_position")
        position = _find_property(layer, "ADBE Position")
        assert position is not None
        _deanimate(position)
        assert position.dimensions == 3
        with pytest.raises(TypeError, match="expected a sequence of 3 elements"):
            position.value = 42.0


class TestValueInPlaceMutation:
    """Regression: re-assigning a mutated list value must write through.

    The value setter early-returns when re-assigning the identical object,
    which is correct only for complex write-through types. A plain list read,
    mutated in place, and re-assigned must still reach the cdat chunk.
    """

    def test_inplace_list_mutation_roundtrips(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "is_modified_false.aep").project
        layer = project.compositions[0].layers[0]
        pos = _find_property(layer, "ADBE Position")
        assert pos is not None
        original = list(pos.value)

        v = pos.value
        v[0] = original[0] + 123.0  # mutate in place
        pos.value = v  # re-assign the SAME object

        out = tmp_path / "out.aep"
        project.save(out)
        project2 = parse_aep(out).project
        pos2 = _find_property(project2.compositions[0].layers[0], "ADBE Position")
        assert pos2 is not None
        assert pos2.value[0] == pytest.approx(original[0] + 123.0)


def _find_descendant(node: Layer | PropertyGroup, match_name: str) -> Property | None:
    """Recursively find a leaf Property by match name under a layer/group."""
    for child in node:
        if isinstance(child, Property) and child.match_name == match_name:
            return child
        if isinstance(child, PropertyGroup):
            found = _find_descendant(child, match_name)
            if found is not None:
                return found
    return None


class TestPlaceholderBoundsValueSetter:
    """Setting a value on properties carrying AE's `[0.0]` placeholder bounds.

    AE writes a `[0.0]` tdum/tduM placeholder for Scale, the separated
    Position followers, and Time Remapping. py_aep used to read this as a
    real `max=0` and reject any non-zero value on the static `.value` setter.
    The placeholder is now suppressed for the value setter, and for Scale /
    separated Position on the read API too, matching ExtendScript. Time
    Remapping keeps its read bounds (ExtendScript reports `hasMax=True`/
    `maxValue=0`) while the setter no longer enforces them.
    """

    SAMPLE = PROPERTY_SAMPLES_DIR / "transform_separated.aep"

    def _layer(self) -> Layer:
        return parse_aep(self.SAMPLE).project.compositions[0].layers[0]

    def test_set_time_remapping_value(self) -> None:
        tr = _find_descendant(self._layer(), "ADBE Time Remapping")
        assert tr is not None and not tr.keyframes
        tr.value = 5.0  # used to raise "must be <= 0.0"
        assert tr.value == pytest.approx(5.0)
        # Read bounds still match ExtendScript (hasMax True, maxValue 0).
        assert tr.has_max is True
        assert tr.max_value == 0

    def test_set_separated_position_dimension(self) -> None:
        px = _find_descendant(self._layer(), "ADBE Position_0")
        assert px is not None and not px.keyframes
        px.value = -50.0  # used to raise; only 0.0 was accepted
        assert px.value == pytest.approx(-50.0)
        # ExtendScript reports no bounds for separated Position dimensions.
        assert px.has_min is False
        assert px.has_max is False

    def test_set_scale_value(self) -> None:
        scale = _find_descendant(self._layer(), "ADBE Scale")
        assert scale is not None and not scale.keyframes
        scale.value = [150.0, 150.0, 150.0]
        assert scale.value == pytest.approx([150.0, 150.0, 150.0])
        assert scale.has_max is False

    def test_real_bounds_still_enforced(self) -> None:
        op = _find_descendant(self._layer(), "ADBE Opacity")
        assert op is not None
        assert (op.min_value, op.max_value) == (0, 100)
        with pytest.raises(ValueError):
            op.value = 150.0

    def test_min_zero_bound_still_enforced(self) -> None:
        # Regression guard: a property with a real min=0 but a placeholder
        # (all-zero) max must still reject negatives. A prior fix wrongly
        # dropped the min whenever the max was absent, letting AE-invalid
        # negatives through for ~24 props (stroke width, light/camera, etc.).
        project = parse_aep(VERSIONS_DIR / "ae2026" / "complete.aep").project
        falloff = None
        for comp in project.compositions:
            for layer in comp.layers:
                p = _find_descendant(layer, "ADBE Light Falloff Distance")
                if p is not None and not p.keyframes:
                    falloff = p
                    break
            if falloff is not None:
                break
        assert falloff is not None
        assert falloff.min_value == 0
        with pytest.raises(ValueError):
            falloff.value = -5.0
        falloff.value = 50.0  # positive accepted (placeholder max not enforced)
        assert falloff.value == pytest.approx(50.0)

    def test_roundtrip_is_byte_identical(self, tmp_path: Path) -> None:
        # Parsing (which reads the suppressed bounds) must not mutate chunks.
        raw = self.SAMPLE.read_bytes()
        out = tmp_path / "rt.aep"
        parse_aep(self.SAMPLE).project.save(out)
        assert out.read_bytes() == raw

    def test_unbounded_props_match_extendscript(self) -> None:
        # Properties ExtendScript reports as unbounded must not over-report
        # bounds: fully-unbounded (channel blend, given a UI-range fallback)
        # and placeholder-max (light props with an all-zero [0.0] tduM).
        project = parse_aep(VERSIONS_DIR / "ae2026" / "complete.aep").project
        found: dict[str, Property] = {}

        def collect(node: Layer | PropertyGroup) -> None:
            for p in node:
                if isinstance(p, Property):
                    found.setdefault(p.match_name, p)
                elif isinstance(p, PropertyGroup):
                    collect(p)

        for comp in project.compositions:
            for layer in comp.layers:
                collect(layer)

        # Fully unbounded in ExtendScript (hasMin=False, hasMax=False):
        rb = found["ADBE R Channel Blend"]
        assert (rb.has_min, rb.has_max) == (False, False)
        # Light Falloff Distance: ES hasMin=True, hasMax=False (placeholder max).
        lf = found["ADBE Light Falloff Distance"]
        assert (lf.has_min, lf.has_max) == (True, False)
        # Light Intensity: ES hasMin=False, hasMax=False.
        li = found["ADBE Light Intensity"]
        assert (li.has_min, li.has_max) == (False, False)
