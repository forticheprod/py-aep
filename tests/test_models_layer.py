"""Tests for Layer model parsing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from conftest import (
    get_comp,
    get_first_layer,
    get_layer,
    get_layer_from_json,
    get_layer_from_json_by_comp,
    load_expected,
    parse_project,
)

from py_aep import parse as parse_aep
from py_aep.enums import (
    AutoOrientType,
    BlendingMode,
    FrameBlendingType,
    Label,
    LayerQuality,
    LayerSamplingQuality,
    LightType,
    PropertyType,
    TrackMatteType,
)
from py_aep.models.layers import (
    AVLayer,
    CameraLayer,
    LightLayer,
    ShapeLayer,
    TextLayer,
)
from py_aep.models.layers.three_d_model_layer import ThreeDModelLayer
from py_aep.models.properties.property import Property
from py_aep.models.properties.property_base import PropertyBase
from py_aep.models.properties.property_group import PropertyGroup

SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "models" / "layer"
BUGS_DIR = Path(__file__).parent.parent / "samples" / "bugs"


class TestLayerBasic:
    """Tests for basic layer attributes."""

    def test_enabled_false(self) -> None:
        expected = load_expected(SAMPLES_DIR, "layer_switches")
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        layer_json = get_layer_from_json_by_comp(expected, "enabled_false")
        assert layer_json["enabled"] is False
        assert layer.enabled == layer_json["enabled"]

    def test_locked_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "layer_switches")
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "locked_true")
        layer_json = get_layer_from_json_by_comp(expected, "locked_true")
        assert layer_json["locked"] is True
        assert layer.locked == layer_json["locked"]

    def test_shy_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "layer_switches")
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "shy_true")
        layer_json = get_layer_from_json_by_comp(expected, "shy_true")
        assert layer_json["shy"] is True
        assert layer.shy == layer_json["shy"]

    def test_solo_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "layer_switches")
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "solo_true")
        layer_json = get_layer_from_json_by_comp(expected, "solo_true")
        assert layer_json["solo"] is True
        assert layer.solo == layer_json["solo"]

    def test_name_renamed(self) -> None:
        expected = load_expected(SAMPLES_DIR, "layer_misc")
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_misc.aep"), "name_renamed")
        layer_json = get_layer_from_json_by_comp(expected, "name_renamed")
        assert layer.name == layer_json["name"] == "RenamedLayer"

    def test_comment(self) -> None:
        expected = load_expected(SAMPLES_DIR, "layer_misc")
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_misc.aep"), "comment")
        layer_json = get_layer_from_json_by_comp(expected, "comment")
        assert layer.comment == layer_json["comment"] == "Test layer comment"

    def test_label_3(self) -> None:
        expected = load_expected(SAMPLES_DIR, "layer_misc")
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_misc.aep"), "label_3")
        layer_json = get_layer_from_json_by_comp(expected, "label_3")
        assert layer_json["label"] == 3
        assert layer.label.value == layer_json["label"]


class TestLayerTiming:
    """Tests for layer timing attributes."""

    def test_startTime_5(self) -> None:
        expected = load_expected(SAMPLES_DIR, "layer_timing")
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_timing.aep"), "startTime_5")
        layer_json = get_layer_from_json_by_comp(expected, "startTime_5")
        assert layer_json["startTime"] == 5
        assert math.isclose(layer.start_time, layer_json["startTime"])

    def test_inPoint_5(self) -> None:
        expected = load_expected(SAMPLES_DIR, "inPoint")
        layer = get_layer(parse_project(SAMPLES_DIR / "inPoint.aep"), "inPoint_5")
        layer_json = get_layer_from_json_by_comp(expected, "inPoint_5")
        assert layer_json["inPoint"] == 5
        assert math.isclose(layer.in_point, layer_json["inPoint"])

    def test_outPoint_10(self) -> None:
        expected = load_expected(SAMPLES_DIR, "outPoint")
        layer = get_layer(parse_project(SAMPLES_DIR / "outPoint.aep"), "outPoint_10")
        layer_json = get_layer_from_json_by_comp(expected, "outPoint_10")
        assert layer_json["outPoint"] == 10
        assert math.isclose(layer.out_point, layer_json["outPoint"])

    def test_stretch_200(self) -> None:
        expected = load_expected(SAMPLES_DIR, "layer_timing")
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_timing.aep"), "stretch_200")
        layer_json = get_layer_from_json_by_comp(expected, "stretch_200")
        assert layer_json["stretch"] == 200
        assert math.isclose(layer.stretch, layer_json["stretch"])

    def test_stretch_minus100(self) -> None:
        expected = load_expected(SAMPLES_DIR, "layer_timing")
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_timing.aep"), "stretch_minus100")
        layer_json = get_layer_from_json_by_comp(expected, "stretch_minus100")
        assert layer_json["stretch"] == -100
        assert math.isclose(layer.stretch, layer_json["stretch"])


class TestTimingEdgeCases:
    """Tests for outPoint/inPoint clamping with precomp sources."""

    def test_outPoint_clamp_precomp(self) -> None:
        """Precomp dur=5s, main comp=30s. OutPoint clamped to 5."""
        expected = load_expected(SAMPLES_DIR, "outPoint_clamp")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "outPoint_clamp.aep"), "outPoint_clamp_precomp"
        )
        layer_json = get_layer_from_json_by_comp(expected, "outPoint_clamp_precomp")
        assert math.isclose(layer.out_point, layer_json["outPoint"], abs_tol=0.001)
        assert math.isclose(layer.out_point, 5.0, abs_tol=0.001)

    def test_outPoint_clamp_stretch_200(self) -> None:
        """Precomp dur=5s, stretch=200%. OutPoint clamped to 10."""
        expected = load_expected(SAMPLES_DIR, "outPoint_clamp")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "outPoint_clamp.aep"), "outPoint_clamp_stretch_200"
        )
        layer_json = get_layer_from_json_by_comp(expected, "outPoint_clamp_stretch_200")
        assert math.isclose(layer.stretch, 200.0)
        assert math.isclose(layer.out_point, layer_json["outPoint"], abs_tol=0.001)
        assert math.isclose(layer.out_point, 10.0, abs_tol=0.001)

    def test_outPoint_clamp_stretch_400(self) -> None:
        """Precomp dur=5s, stretch=400%. OutPoint clamped to 20."""
        expected = load_expected(SAMPLES_DIR, "outPoint_clamp")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "outPoint_clamp.aep"), "outPoint_clamp_stretch_400"
        )
        layer_json = get_layer_from_json_by_comp(expected, "outPoint_clamp_stretch_400")
        assert math.isclose(layer.stretch, 400.0)
        assert math.isclose(layer.out_point, layer_json["outPoint"], abs_tol=0.001)
        assert math.isclose(layer.out_point, 20.0, abs_tol=0.001)

    def test_outPoint_clamp_collapse(self) -> None:
        """Precomp dur=5s, collapse=True. AE still clamps to 5."""
        expected = load_expected(SAMPLES_DIR, "outPoint_no_clamp")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "outPoint_no_clamp.aep"), "outPoint_no_clamp_collapse"
        )
        layer_json = get_layer_from_json_by_comp(expected, "outPoint_no_clamp_collapse")
        assert layer.collapse_transformation is True
        assert math.isclose(layer.out_point, layer_json["outPoint"], abs_tol=0.001)
        assert math.isclose(layer.out_point, 5.0, abs_tol=0.001)

    def test_outPoint_no_clamp_timeRemap(self) -> None:
        """Precomp dur=5s, timeRemap=True. OutPoint NOT clamped (stays 30)."""
        expected = load_expected(SAMPLES_DIR, "outPoint_no_clamp")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "outPoint_no_clamp.aep"), "outPoint_no_clamp_timeRemap"
        )
        layer_json = get_layer_from_json_by_comp(expected, "outPoint_no_clamp_timeRemap")
        assert layer.time_remap_enabled is True
        assert math.isclose(layer.out_point, layer_json["outPoint"], abs_tol=0.001)
        assert math.isclose(layer.out_point, 30.0, abs_tol=0.001)

    def test_outPoint_no_clamp_negative_stretch(self) -> None:
        """Precomp dur=5s, stretch=-100%. Clamping skipped."""
        expected = load_expected(SAMPLES_DIR, "outPoint_no_clamp")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "outPoint_no_clamp.aep"), "outPoint_no_clamp_negative_stretch"
        )
        layer_json = get_layer_from_json_by_comp(expected, "outPoint_no_clamp_negative_stretch")
        assert math.isclose(layer.stretch, -100.0)
        assert math.isclose(layer.out_point, layer_json["outPoint"], abs_tol=0.001)

    def test_outPoint_clamp_with_startTime(self) -> None:
        """Precomp dur=5s, startTime=3s. OutPoint clamped to 3+5=8."""
        expected = load_expected(SAMPLES_DIR, "outPoint_clamp")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "outPoint_clamp.aep"), "outPoint_clamp_with_startTime"
        )
        layer_json = get_layer_from_json_by_comp(expected, "outPoint_clamp_with_startTime")
        assert math.isclose(layer.start_time, 3.0, abs_tol=0.001)
        assert math.isclose(layer.out_point, layer_json["outPoint"], abs_tol=0.001)
        assert math.isclose(layer.out_point, 8.0, abs_tol=0.001)

    def test_inPoint_before_startTime(self) -> None:
        """Layer with inPoint (5) before startTime (10)."""
        expected = load_expected(SAMPLES_DIR, "inPoint")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "inPoint.aep"), "inPoint_before_startTime"
        )
        layer_json = get_layer_from_json_by_comp(expected, "inPoint_before_startTime")
        assert math.isclose(layer.in_point, layer_json["inPoint"])
        assert math.isclose(layer.in_point, 5.0)
        assert math.isclose(layer.start_time, layer_json["startTime"])
        assert math.isclose(layer.start_time, 10.0)

    def test_outPoint_with_negative_startTime(self) -> None:
        """Layer with negative startTime (-5) and outPoint (20)."""
        expected = load_expected(SAMPLES_DIR, "outPoint")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "outPoint.aep"), "outPoint_with_negative_startTime"
        )
        layer_json = get_layer_from_json_by_comp(expected, "outPoint_with_negative_startTime")
        assert math.isclose(layer.start_time, layer_json["startTime"])
        assert math.isclose(layer.start_time, -5.0)
        assert math.isclose(layer.in_point, layer_json["inPoint"])
        assert math.isclose(layer.in_point, -5.0)
        assert math.isclose(layer.out_point, layer_json["outPoint"])
        assert math.isclose(layer.out_point, 20.0)


class TestLayerTypes:
    """Tests for different layer types."""

    def test_type_camera(self) -> None:
        layer = get_layer(parse_project(SAMPLES_DIR / "type.aep"), "type_camera")
        assert layer.layer_type == "CameraLayer"
        assert isinstance(layer, CameraLayer)

    def test_type_null(self) -> None:
        expected = load_expected(SAMPLES_DIR, "type")
        layer = get_layer(parse_project(SAMPLES_DIR / "type.aep"), "type_null")
        layer_json = get_layer_from_json_by_comp(expected, "type_null")
        assert layer_json["nullLayer"] is True
        assert layer.null_layer == layer_json["nullLayer"]

    def test_type_shape(self) -> None:
        layer = get_layer(parse_project(SAMPLES_DIR / "type.aep"), "type_shape")
        assert layer.layer_type == "Layer"
        assert isinstance(layer, ShapeLayer)

    def test_type_text(self) -> None:
        layer = get_layer(parse_project(SAMPLES_DIR / "type.aep"), "type_text")
        assert layer.layer_type == "Layer"
        assert isinstance(layer, TextLayer)


class TestLightTypes:
    """Tests for light layer types."""

    def test_lightType_AMBIENT(self) -> None:
        expected = load_expected(SAMPLES_DIR, "lightType")
        layer = get_layer(parse_project(SAMPLES_DIR / "lightType.aep"), "lightType_AMBIENT")
        layer_json = get_layer_from_json_by_comp(expected, "lightType_AMBIENT")
        assert layer.light_type == layer_json["lightType"] == LightType.AMBIENT

    def test_lightType_POINT(self) -> None:
        expected = load_expected(SAMPLES_DIR, "lightType")
        layer = get_layer(parse_project(SAMPLES_DIR / "lightType.aep"), "lightType_POINT")
        layer_json = get_layer_from_json_by_comp(expected, "lightType_POINT")
        assert layer.light_type == layer_json["lightType"] == LightType.POINT

    def test_lightType_SPOT(self) -> None:
        expected = load_expected(SAMPLES_DIR, "lightType")
        layer = get_layer(parse_project(SAMPLES_DIR / "lightType.aep"), "lightType_SPOT")
        layer_json = get_layer_from_json_by_comp(expected, "lightType_SPOT")
        assert layer.light_type == layer_json["lightType"] == LightType.SPOT

    def test_lightType_PARALLEL(self) -> None:
        expected = load_expected(SAMPLES_DIR, "lightType")
        layer = get_layer(parse_project(SAMPLES_DIR / "lightType.aep"), "lightType_PARALLEL")
        layer_json = get_layer_from_json_by_comp(expected, "lightType_PARALLEL")
        assert layer.light_type == layer_json["lightType"] == LightType.PARALLEL

    def test_lightType_ENVIRONMENT(self) -> None:
        project = parse_project(SAMPLES_DIR / "light_source_default.aep")
        layer = get_first_layer(project)
        assert isinstance(layer, LightLayer)
        assert layer.light_type == LightType.ENVIRONMENT


class TestLightSource:
    """Tests for LightLayer.light_source."""

    def test_light_source_default_is_none(self) -> None:
        project = parse_project(SAMPLES_DIR / "light_source_default.aep")
        layer = get_first_layer(project)
        assert isinstance(layer, LightLayer)
        assert layer.light_source is None

    def test_light_source_mov(self) -> None:
        project = parse_project(SAMPLES_DIR / "light_source_mov_23_976.mov.aep")
        layer = get_first_layer(project)
        assert isinstance(layer, LightLayer)
        assert layer.light_source is not None
        assert isinstance(layer.light_source, AVLayer)
        assert layer.light_source.name == "mov_23_976.mov"

    def test_light_source_set_none(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "light_source_mov_23_976.mov.aep")
        layer = get_first_layer(project)
        assert isinstance(layer, LightLayer)
        assert layer.light_source is not None

        layer.light_source = None
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_first_layer(parse_aep(out).project)
        assert isinstance(layer2, LightLayer)
        assert layer2.light_source is None

    def test_light_source_rejects_3d_layer(self) -> None:
        project = parse_aep(SAMPLES_DIR / "light_source_mov_23_976.mov.aep").project
        light = project.compositions[0].light_layers[0]
        assert isinstance(light, LightLayer)
        source = light.light_source
        assert isinstance(source, AVLayer)

        source.three_d_layer = True
        with pytest.raises(ValueError, match="Invalid light source specified"):
            light.light_source = source


class TestAVLayerAttributes:
    """Tests for AVLayer-specific attributes."""

    def test_threeDLayer_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "avlayer_flags")
        layer = get_layer(parse_project(SAMPLES_DIR / "avlayer_flags.aep"), "threeDLayer_true")
        layer_json = get_layer_from_json_by_comp(expected, "threeDLayer_true")
        assert isinstance(layer, AVLayer)
        assert layer_json["threeDLayer"] is True
        assert layer.three_d_layer == layer_json["threeDLayer"]

    def test_adjustmentLayer_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "avlayer_flags")
        layer = get_layer(parse_project(SAMPLES_DIR / "avlayer_flags.aep"), "adjustmentLayer_true")
        layer_json = get_layer_from_json_by_comp(expected, "adjustmentLayer_true")
        assert layer.adjustment_layer == layer_json["adjustmentLayer"] is True

    def test_guideLayer_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "avlayer_flags")
        layer = get_layer(parse_project(SAMPLES_DIR / "avlayer_flags.aep"), "guideLayer_true")
        layer_json = get_layer_from_json_by_comp(expected, "guideLayer_true")
        assert layer.guide_layer == layer_json["guideLayer"] is True

    def test_collapseTransformation_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "avlayer_flags")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "avlayer_flags.aep"), "collapseTransformation_true"
        )
        layer_json = get_layer_from_json_by_comp(expected, "collapseTransformation_true")
        assert (
            layer.collapse_transformation
            == layer_json["collapseTransformation"]
            is True
        )

    def test_preserveTransparency_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "avlayer_flags")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "avlayer_flags.aep"), "preserveTransparency_true"
        )
        layer_json = get_layer_from_json_by_comp(expected, "preserveTransparency_true")
        assert layer.preserve_transparency == layer_json["preserveTransparency"] is True

    def test_motionBlur_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "avlayer_flags")
        layer = get_layer(parse_project(SAMPLES_DIR / "avlayer_flags.aep"), "motionBlur_true")
        layer_json = get_layer_from_json_by_comp(expected, "motionBlur_true")
        assert layer.motion_blur == layer_json["motionBlur"] is True

    def test_effectsActive_false(self) -> None:
        expected = load_expected(SAMPLES_DIR, "avlayer_flags")
        layer = get_layer(parse_project(SAMPLES_DIR / "avlayer_flags.aep"), "effectsActive_false")
        layer_json = get_layer_from_json_by_comp(expected, "effectsActive_false")
        assert layer_json["effectsActive"] is False
        assert layer.effects_active == layer_json["effectsActive"]


class TestBlendingModes:
    """Tests for blending mode attributes."""

    def test_blendingMode_ADD(self) -> None:
        expected = load_expected(SAMPLES_DIR, "blendingMode")
        layer = get_layer(parse_project(SAMPLES_DIR / "blendingMode.aep"), "blendingMode_ADD")
        layer_json = get_layer_from_json_by_comp(expected, "blendingMode_ADD")
        assert layer.blending_mode == layer_json["blendingMode"] == BlendingMode.ADD

    def test_blendingMode_MULTIPLY(self) -> None:
        expected = load_expected(SAMPLES_DIR, "blendingMode")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "blendingMode.aep"), "blendingMode_MULTIPLY"
        )
        layer_json = get_layer_from_json_by_comp(expected, "blendingMode_MULTIPLY")
        assert (
            layer.blending_mode == layer_json["blendingMode"] == BlendingMode.MULTIPLY
        )

    def test_blendingMode_SCREEN(self) -> None:
        expected = load_expected(SAMPLES_DIR, "blendingMode")
        layer = get_layer(parse_project(SAMPLES_DIR / "blendingMode.aep"), "blendingMode_SCREEN")
        layer_json = get_layer_from_json_by_comp(expected, "blendingMode_SCREEN")
        assert layer.blending_mode == layer_json["blendingMode"] == BlendingMode.SCREEN


class TestQualitySettings:
    """Tests for layer quality settings."""

    def test_quality_BEST(self) -> None:
        expected = load_expected(SAMPLES_DIR, "quality")
        layer = get_layer(parse_project(SAMPLES_DIR / "quality.aep"), "quality_BEST")
        layer_json = get_layer_from_json_by_comp(expected, "quality_BEST")
        assert layer.quality == layer_json["quality"] == LayerQuality.BEST

    def test_quality_DRAFT(self) -> None:
        expected = load_expected(SAMPLES_DIR, "quality")
        layer = get_layer(parse_project(SAMPLES_DIR / "quality.aep"), "quality_DRAFT")
        layer_json = get_layer_from_json_by_comp(expected, "quality_DRAFT")
        assert layer.quality == layer_json["quality"] == LayerQuality.DRAFT

    def test_quality_WIREFRAME(self) -> None:
        expected = load_expected(SAMPLES_DIR, "quality")
        layer = get_layer(parse_project(SAMPLES_DIR / "quality.aep"), "quality_WIREFRAME")
        layer_json = get_layer_from_json_by_comp(expected, "quality_WIREFRAME")
        assert layer.quality == layer_json["quality"] == LayerQuality.WIREFRAME

    def test_samplingQuality_BICUBIC(self) -> None:
        expected = load_expected(SAMPLES_DIR, "avlayer_flags")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "avlayer_flags.aep"), "samplingQuality_BICUBIC"
        )
        layer_json = get_layer_from_json_by_comp(expected, "samplingQuality_BICUBIC")
        assert (
            layer.sampling_quality
            == layer_json["samplingQuality"]
            == LayerSamplingQuality.BICUBIC
        )


class TestFrameBlending:
    """Tests for frame blending type."""

    def test_frameBlendingType_NO_FRAME_BLEND(self) -> None:
        expected = load_expected(SAMPLES_DIR, "frameBlendingType")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "frameBlendingType.aep"), "frameBlendingType_NO_FRAME_BLEND"
        )
        layer_json = get_layer_from_json_by_comp(expected, "frameBlendingType_NO_FRAME_BLEND")
        assert (
            layer.frame_blending_type
            == layer_json["frameBlendingType"]
            == FrameBlendingType.NO_FRAME_BLEND
        )
        assert layer.frame_blending is False

    def test_frameBlendingType_FRAME_MIX(self) -> None:
        expected = load_expected(SAMPLES_DIR, "frameBlendingType")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "frameBlendingType.aep"), "frameBlendingType_FRAME_MIX"
        )
        layer_json = get_layer_from_json_by_comp(expected, "frameBlendingType_FRAME_MIX")
        assert (
            layer.frame_blending_type
            == layer_json["frameBlendingType"]
            == FrameBlendingType.FRAME_MIX
        )

    def test_frameBlendingType_PIXEL_MOTION(self) -> None:
        expected = load_expected(SAMPLES_DIR, "frameBlendingType")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "frameBlendingType.aep"), "frameBlendingType_PIXEL_MOTION"
        )
        layer_json = get_layer_from_json_by_comp(expected, "frameBlendingType_PIXEL_MOTION")
        assert (
            layer.frame_blending_type
            == layer_json["frameBlendingType"]
            == FrameBlendingType.PIXEL_MOTION
        )


class TestAutoOrient:
    """Tests for auto-orient settings."""

    def test_autoOrient_ALONG_PATH(self) -> None:
        expected = load_expected(SAMPLES_DIR, "autoOrient")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "autoOrient.aep"), "autoOrient_ALONG_PATH"
        )
        layer_json = get_layer_from_json_by_comp(expected, "autoOrient_ALONG_PATH")
        assert (
            layer.auto_orient == layer_json["autoOrient"] == AutoOrientType.ALONG_PATH
        )

    def test_autoOrient_CAMERA(self) -> None:
        expected = load_expected(SAMPLES_DIR, "autoOrient")
        layer = get_layer(parse_project(SAMPLES_DIR / "autoOrient.aep"), "autoOrient_CAMERA")
        layer_json = get_layer_from_json_by_comp(expected, "autoOrient_CAMERA")
        assert (
            layer.auto_orient
            == layer_json["autoOrient"]
            == AutoOrientType.CAMERA_OR_POINT_OF_INTEREST
        )
        assert layer.three_d_layer is True

    def test_autoOrient_CHARACTERS(self) -> None:
        expected = load_expected(SAMPLES_DIR, "autoOrient")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "autoOrient.aep"), "autoOrient_CHARACTERS"
        )
        layer_json = get_layer_from_json_by_comp(expected, "autoOrient_CHARACTERS")
        assert (
            layer.auto_orient
            == layer_json["autoOrient"]
            == AutoOrientType.CHARACTERS_TOWARD_CAMERA
        )
        assert layer.three_d_layer is True


class TestTrackMatte:
    """Tests for track matte settings."""

    def test_trackMatteType_ALPHA(self) -> None:
        expected = load_expected(SAMPLES_DIR, "trackMatteType")
        project = parse_project(SAMPLES_DIR / "trackMatteType.aep")
        comp = get_comp(project, "trackMatteType_ALPHA")
        matted_layer = next(
            (
                layer
                for layer in comp.layers
                if layer.track_matte_type == TrackMatteType.ALPHA
            ),
            None,
        )
        expected_layer = None
        for item in expected["items"]:
            if item.get("name") == "trackMatteType_ALPHA" and "layers" in item:
                for lj in item["layers"]:
                    if lj.get("trackMatteType") == TrackMatteType.ALPHA:
                        expected_layer = lj
                        break
        assert matted_layer is not None
        assert expected_layer is not None
        assert matted_layer.track_matte_type == expected_layer["trackMatteType"]

    def test_trackMatteType_LUMA(self) -> None:
        expected = load_expected(SAMPLES_DIR, "trackMatteType")
        project = parse_project(SAMPLES_DIR / "trackMatteType.aep")
        comp = get_comp(project, "trackMatteType_LUMA")
        matted_layer = next(
            (
                layer
                for layer in comp.layers
                if layer.track_matte_type == TrackMatteType.LUMA
            ),
            None,
        )
        expected_layer = None
        for item in expected["items"]:
            if item.get("name") == "trackMatteType_LUMA" and "layers" in item:
                for lj in item["layers"]:
                    if lj.get("trackMatteType") == TrackMatteType.LUMA:
                        expected_layer = lj
                        break
        assert matted_layer is not None
        assert expected_layer is not None
        assert matted_layer.track_matte_type == expected_layer["trackMatteType"]

    def test_has_track_matte(self) -> None:
        expected = load_expected(SAMPLES_DIR, "track_matte_yes")
        project = parse_project(SAMPLES_DIR / "track_matte_yes.aep")
        comp = project.compositions[0]
        expected_layers = None
        for item in expected["items"]:
            if "layers" in item:
                expected_layers = item["layers"]
                break
        assert expected_layers is not None
        for layer, exp in zip(comp.layers, expected_layers):
            assert layer.has_track_matte == exp["hasTrackMatte"]

    def test_has_track_matte_false(self) -> None:
        expected = load_expected(SAMPLES_DIR, "track_matte_no")
        project = parse_project(SAMPLES_DIR / "track_matte_no.aep")
        comp = project.compositions[0]
        expected_layers = None
        for item in expected["items"]:
            if "layers" in item:
                expected_layers = item["layers"]
                break
        assert expected_layers is not None
        for layer in comp.layers:
            assert layer.has_track_matte is False

    def test_is_track_matte(self) -> None:
        expected = load_expected(SAMPLES_DIR, "track_matte_yes")
        project = parse_project(SAMPLES_DIR / "track_matte_yes.aep")
        comp = project.compositions[0]
        expected_layers = None
        for item in expected["items"]:
            if "layers" in item:
                expected_layers = item["layers"]
                break
        assert expected_layers is not None
        for layer, exp in zip(comp.layers, expected_layers):
            assert layer.is_track_matte == exp["isTrackMatte"]

    def test_is_track_matte_false(self) -> None:
        project = parse_project(SAMPLES_DIR / "track_matte_no.aep")
        comp = project.compositions[0]
        for layer in comp.layers:
            assert layer.is_track_matte is False

    def test_track_matte_layer(self) -> None:
        project = parse_project(SAMPLES_DIR / "track_matte_yes.aep")
        comp = project.compositions[0]
        matted_layer = next(
            (layer for layer in comp.layers if layer.has_track_matte), None
        )
        assert matted_layer is not None
        assert matted_layer.track_matte_layer is not None
        assert matted_layer.track_matte_layer.is_track_matte is True

    def test_track_matte_layer_none(self) -> None:
        project = parse_project(SAMPLES_DIR / "track_matte_no.aep")
        comp = project.compositions[0]
        for layer in comp.layers:
            assert layer.track_matte_layer is None


class TestParenting:
    """Tests for layer parenting."""

    def test_parent(self) -> None:
        expected = load_expected(SAMPLES_DIR, "layer_misc")
        project = parse_project(SAMPLES_DIR / "layer_misc.aep")
        comp = get_comp(project, "parent")
        child_layer = next(
            (layer for layer in comp.layers if layer._parent_id != 0), None
        )
        assert child_layer is not None
        for item in expected["items"]:
            if item.get("name") == "parent" and "layers" in item:
                for layer_json in item["layers"]:
                    if layer_json.get("parent") is not None:
                        assert child_layer._parent_id == layer_json["parent"]


class TestTimeRemap:
    """Tests for time remap."""

    def test_timeRemapEnabled_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "avlayer_flags")
        layer = get_layer(
            parse_project(SAMPLES_DIR / "avlayer_flags.aep"), "timeRemapEnabled_true"
        )
        layer_json = get_layer_from_json_by_comp(expected, "timeRemapEnabled_true")
        assert layer_json["timeRemapEnabled"] is True
        assert layer.time_remap_enabled == layer_json["timeRemapEnabled"]


class TestAudio:
    """Tests for audio attributes."""

    def test_audioEnabled_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "audioEnabled")
        layer = get_layer(parse_project(SAMPLES_DIR / "audioEnabled.aep"), "audioEnabled_true")
        layer_json = get_layer_from_json_by_comp(expected, "audioEnabled_true")
        assert layer.audio_enabled == layer_json["audioEnabled"] is True

    def test_audioEnabled_false(self) -> None:
        expected = load_expected(SAMPLES_DIR, "audioEnabled")
        layer = get_layer(parse_project(SAMPLES_DIR / "audioEnabled.aep"), "audioEnabled_false")
        layer_json = get_layer_from_json_by_comp(expected, "audioEnabled_false")
        assert layer_json["audioEnabled"] is False
        assert layer.audio_enabled == layer_json["audioEnabled"]


class TestLayerNameEncoding:
    """Regression tests for layer name encoding edge cases."""

    def test_non_ascii_layer_name(self) -> None:
        """Layer names with non-ASCII characters (e.g. ≈) should parse without error.

        Regression test for windows-1250 decoding error: byte 0x98 is undefined
        in windows-1250 but valid in windows-1252.
        """
        expected = load_expected(BUGS_DIR, "windows-1250_decoding_error")
        layer = get_first_layer(
            parse_project(BUGS_DIR / "windows-1250_decoding_error.aep")
        )
        layer_json = get_layer_from_json(expected)
        assert layer.name == layer_json["name"]
        assert layer.name == "\u2248"


class TestActiveAtTime:
    """Tests for Layer.active_at_time() method."""

    def test_enabled_layer_within_range(self) -> None:
        """An enabled, non-soloed layer returns True inside its in/out range."""
        project = parse_project(SAMPLES_DIR / "layer_timing.aep")
        layer = get_layer(project, "startTime_5")
        assert layer.enabled is True
        midpoint = (layer.in_point + layer.out_point) / 2
        assert layer.active_at_time(midpoint) is True

    def test_at_in_point(self) -> None:
        """Layer is active exactly at its in_point (inclusive)."""
        project = parse_project(SAMPLES_DIR / "inPoint.aep")
        layer = get_layer(project, "inPoint_5")
        assert layer.active_at_time(layer.in_point) is True

    def test_at_out_point(self) -> None:
        """Layer is not active at its out_point (exclusive)."""
        project = parse_project(SAMPLES_DIR / "inPoint.aep")
        layer = get_layer(project, "inPoint_5")
        assert layer.active_at_time(layer.out_point) is False

    def test_before_in_point(self) -> None:
        """Layer is not active before its in_point."""
        project = parse_project(SAMPLES_DIR / "inPoint.aep")
        layer = get_layer(project, "inPoint_5")
        assert layer.active_at_time(layer.in_point - 1) is False

    def test_disabled_layer(self) -> None:
        """A disabled layer is never active."""
        project = parse_project(SAMPLES_DIR / "layer_switches.aep")
        layer = get_layer(project, "enabled_false")
        assert layer.enabled is False
        midpoint = (layer.in_point + layer.out_point) / 2
        assert layer.active_at_time(midpoint) is False

    def test_solo_layer_active(self) -> None:
        """A soloed layer is active within its time range."""
        project = parse_project(SAMPLES_DIR / "layer_switches.aep")
        layer = get_layer(project, "solo_true")
        assert layer.solo is True
        midpoint = (layer.in_point + layer.out_point) / 2
        assert layer.active_at_time(midpoint) is True

    def test_non_solo_layer_inactive_when_other_is_soloed(self) -> None:
        """A non-soloed layer is inactive when another layer in the comp is soloed."""
        project = parse_project(SAMPLES_DIR / "layer_switches.aep")
        comp = get_comp(project, "solo_true")
        non_solo_layers = [lyr for lyr in comp.layers if not lyr.solo]
        if non_solo_layers:
            layer = non_solo_layers[0]
            midpoint = (layer.in_point + layer.out_point) / 2
            assert layer.active_at_time(midpoint) is False


class TestAudioActiveAtTime:
    """Tests for AVLayer.audio_active_at_time() method."""

    def test_audio_active_within_range(self) -> None:
        """Layer with audio enabled returns True inside its time range."""
        project = parse_project(SAMPLES_DIR / "audioEnabled.aep")
        layer = get_layer(project, "audioEnabled_true")
        assert isinstance(layer, AVLayer)
        midpoint = (layer.in_point + layer.out_point) / 2
        assert layer.audio_active_at_time(midpoint) is True

    def test_audio_disabled(self) -> None:
        """Layer with audio_enabled=False returns False."""
        project = parse_project(SAMPLES_DIR / "audioEnabled.aep")
        layer = get_layer(project, "audioEnabled_false")
        assert isinstance(layer, AVLayer)
        midpoint = (layer.in_point + layer.out_point) / 2
        assert layer.audio_active_at_time(midpoint) is False

    def test_before_in_point(self) -> None:
        """Layer is not audio-active before its in_point."""
        project = parse_project(SAMPLES_DIR / "audioEnabled.aep")
        layer = get_layer(project, "audioEnabled_true")
        assert isinstance(layer, AVLayer)
        assert layer.audio_active_at_time(layer.in_point - 1) is False

    def test_at_out_point(self) -> None:
        """Layer is not audio-active at its out_point (exclusive)."""
        project = parse_project(SAMPLES_DIR / "audioEnabled.aep")
        layer = get_layer(project, "audioEnabled_true")
        assert isinstance(layer, AVLayer)
        assert layer.audio_active_at_time(layer.out_point) is False

    def test_at_in_point(self) -> None:
        """Layer is audio-active at its in_point (inclusive)."""
        project = parse_project(SAMPLES_DIR / "audioEnabled.aep")
        layer = get_layer(project, "audioEnabled_true")
        assert isinstance(layer, AVLayer)
        assert layer.audio_active_at_time(layer.in_point) is True

    def test_audio_active_property(self) -> None:
        """audio_active property delegates to audio_active_at_time(time)."""
        project = parse_project(SAMPLES_DIR / "audioEnabled.aep")
        layer = get_layer(project, "audioEnabled_true")
        assert isinstance(layer, AVLayer)
        assert layer.audio_active == layer.audio_active_at_time(layer.time)


class TestLayerPropertyGroupInheritance:
    """Tests for Layer's PropertyGroup / PropertyBase inheritance."""

    def test_layer_is_property_group(self) -> None:
        """Layer is an instance of PropertyGroup."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        assert isinstance(layer, PropertyGroup)

    def test_layer_is_property_base(self) -> None:
        """Layer is an instance of PropertyBase."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        assert isinstance(layer, PropertyBase)

    def test_property_depth_is_zero(self) -> None:
        """Layers are at depth 0 (root of the property hierarchy)."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        assert layer.property_depth == 0

    def test_property_type_named_group(self) -> None:
        """Layer property_type is NAMED_GROUP."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        assert layer.property_type == PropertyType.NAMED_GROUP

    def test_av_layer_match_name(self) -> None:
        """AVLayer has the correct ExtendScript match name."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        assert isinstance(layer, AVLayer)
        assert layer.match_name == "ADBE AV Layer"

    def test_properties_contains_transform(self) -> None:
        """Layer.properties includes the Transform group."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        match_names = [p.match_name for p in layer.properties]
        assert "ADBE Transform Group" in match_names

    def test_transform_accessor(self) -> None:
        """Layer.transform returns the Transform PropertyGroup."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        assert isinstance(layer.transform, PropertyGroup)
        assert layer.transform.match_name == "ADBE Transform Group"

    def test_effects_none_when_no_effects(self) -> None:
        """Layer.effects is None when there are no effects."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        # Basic layer without effects
        assert layer.effects is None

    def test_num_properties_positive(self) -> None:
        """Layer.num_properties returns the count of top-level property groups."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        assert layer.num_properties == len(layer.properties)
        assert layer.num_properties > 0

    def test_active_property(self) -> None:
        """Layer.active reflects active_at_time(time)."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        assert layer.active == layer.active_at_time(layer.time)

    def test_identity_equality(self) -> None:
        """Two Layer objects are only equal when they are the same object."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        assert layer == layer
        # A copy (different object) should not be equal
        assert layer != object()

    def test_transform_is_same_object_in_properties(self) -> None:
        """Layer.transform returns the same PropertyGroup as in properties list."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        transform_from_list = next(
            p for p in layer.properties if p.match_name == "ADBE Transform Group"
        )
        assert layer.transform is transform_from_list

    def test_len_equals_num_properties(self) -> None:
        """len(layer) equals layer.num_properties."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        assert len(layer) == layer.num_properties
        assert len(layer) == len(layer.properties)

    def test_getitem_by_int_index(self) -> None:
        """layer[0] returns the first child property group."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        assert layer[0] is layer.properties[0]

    def test_getitem_by_match_name(self) -> None:
        """layer['ADBE Transform Group'] returns the Transform group."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        result = layer["ADBE Transform Group"]
        assert isinstance(result, PropertyGroup)
        assert result.match_name == "ADBE Transform Group"
        assert result is layer.transform

    def test_getitem_by_display_name(self) -> None:
        """layer['Transform'] returns the Transform group by display name."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        result = layer["Transform"]
        assert isinstance(result, PropertyGroup)
        assert result.match_name == "ADBE Transform Group"

    def test_getitem_chained(self) -> None:
        """layer['ADBE Transform Group']['ADBE Position'] chains correctly."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        transform = layer["ADBE Transform Group"]
        position = transform["ADBE Position"]
        assert position.match_name == "ADBE Position"

    def test_getitem_key_error(self) -> None:
        """layer['nonexistent'] raises KeyError."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        with pytest.raises(KeyError):
            layer["nonexistent_match_name"]

    def test_getitem_index_error(self) -> None:
        """layer[9999] raises IndexError."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        with pytest.raises(IndexError):
            layer[9999]

    def test_getitem_type_error(self) -> None:
        """layer[1.5] raises TypeError."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        with pytest.raises(TypeError):
            layer[1.5]  # type: ignore[index]

    def test_getattr_single_word(self) -> None:
        """layer.transform.position resolves via __getattr__."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        position = layer.transform.position  # type: ignore[attr-defined]
        assert position.match_name == "ADBE Position"

    def test_getattr_multi_word(self) -> None:
        """layer.transform.anchor_point resolves 'Anchor Point'."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        anchor = layer.transform.anchor_point  # type: ignore[attr-defined]
        assert anchor.match_name == "ADBE Anchor Point"

    def test_getattr_attribute_error(self) -> None:
        """Accessing a nonexistent child raises AttributeError."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        with pytest.raises(AttributeError):
            layer.transform.nonexistent  # type: ignore[attr-defined]  # noqa: B018

    def test_getattr_does_not_shadow_fields(self) -> None:
        """Dataclass fields take priority over __getattr__."""
        layer = get_layer(parse_project(SAMPLES_DIR / "layer_switches.aep"), "enabled_false")
        # 'name' is a dataclass field, should NOT look in children
        assert isinstance(layer.transform.name, str)


class TestThreeDModelLayer:
    """Tests for ThreeDModelLayer parsing."""

    def test_isinstance(self) -> None:
        """ThreeDModelLayer inherits from AVLayer."""
        project = parse_project(SAMPLES_DIR / "three_d_model_layer.aep")
        layer = get_first_layer(project)
        assert isinstance(layer, ThreeDModelLayer)
        assert isinstance(layer, AVLayer)

    def test_match_name(self) -> None:
        """ThreeDModelLayer match_name is 'ADBE 3D Model Layer'."""
        project = parse_project(SAMPLES_DIR / "three_d_model_layer.aep")
        layer = get_first_layer(project)
        assert layer.match_name == "ADBE 3D Model Layer"

    def test_layer_type(self) -> None:
        """ThreeDModelLayer layer_type is 'Layer'."""
        project = parse_project(SAMPLES_DIR / "three_d_model_layer.aep")
        layer = get_first_layer(project)
        assert layer.layer_type == "Layer"

    def test_three_d_layer(self) -> None:
        """ThreeDModelLayer always reports three_d_layer=True."""
        project = parse_project(SAMPLES_DIR / "three_d_model_layer.aep")
        layer = get_first_layer(project)
        assert isinstance(layer, ThreeDModelLayer)
        assert layer.three_d_layer is True

    def test_collapse_transformation(self) -> None:
        """ThreeDModelLayer has collapse_transformation=True."""
        project = parse_project(SAMPLES_DIR / "three_d_model_layer.aep")
        layer = get_first_layer(project)
        assert isinstance(layer, ThreeDModelLayer)
        assert layer.collapse_transformation is True

    def test_source_is_footage(self) -> None:
        """ThreeDModelLayer source is a FootageItem."""
        project = parse_project(SAMPLES_DIR / "three_d_model_layer.aep")
        layer = get_first_layer(project)
        assert isinstance(layer, ThreeDModelLayer)
        assert layer.source is not None
        assert layer.source.name == "crystal.fbx"

    def test_comp_three_d_model_layers(self) -> None:
        """CompItem.three_d_model_layers filters correctly."""
        project = parse_project(SAMPLES_DIR / "three_d_model_layer.aep")
        comp = project.compositions[0]
        assert len(comp.three_d_model_layers) == 1
        assert isinstance(comp.three_d_model_layers[0], ThreeDModelLayer)

    def test_can_set_collapse_transformation(self) -> None:
        """ThreeDModelLayer.can_set_collapse_transformation is always True."""
        project = parse_project(SAMPLES_DIR / "three_d_model_layer.aep")
        layer = get_first_layer(project)
        assert isinstance(layer, ThreeDModelLayer)
        assert layer.can_set_collapse_transformation is True

    def test_can_set_time_remap_enabled(self) -> None:
        """ThreeDModelLayer.can_set_time_remap_enabled is always False."""
        project = parse_project(SAMPLES_DIR / "three_d_model_layer.aep")
        layer = get_first_layer(project)
        assert isinstance(layer, ThreeDModelLayer)
        assert layer.can_set_time_remap_enabled is False


class TestThreeDPerChar:
    """Tests for AVLayer.three_d_per_char attribute."""

    def test_three_d_per_char_on(self) -> None:
        """three_d_per_char is True when per-character 3D is enabled."""
        project = parse_project(SAMPLES_DIR / "threeDPerChar_on.aep")
        layer = get_first_layer(project)
        assert isinstance(layer, AVLayer)
        assert layer.three_d_per_char is True

    def test_three_d_per_char_off(self) -> None:
        """three_d_per_char is False when per-character 3D is disabled."""
        project = parse_project(SAMPLES_DIR / "threeDPerChar_off.aep")
        layer = get_first_layer(project)
        assert isinstance(layer, AVLayer)
        assert layer.three_d_per_char is False


class TestRoundtripLightType:
    """Roundtrip tests for LightLayer.light_type."""

    def test_modify_light_type_to_spot(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "lightType.aep")
        layer = get_layer(project, "lightType_AMBIENT")
        assert isinstance(layer, LightLayer)
        assert layer.light_type == LightType.AMBIENT

        layer.light_type = LightType.SPOT
        out = tmp_path / "modified_light_type.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "lightType_AMBIENT")
        assert isinstance(layer2, LightLayer)
        assert layer2.light_type == LightType.SPOT

    def test_modify_light_type_to_point(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "lightType.aep")
        layer = get_layer(project, "lightType_SPOT")
        assert isinstance(layer, LightLayer)
        assert layer.light_type == LightType.SPOT

        layer.light_type = LightType.POINT
        out = tmp_path / "modified_light_type_point.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "lightType_SPOT")
        assert isinstance(layer2, LightLayer)
        assert layer2.light_type == LightType.POINT

    def test_modify_light_type_to_parallel(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "lightType.aep")
        layer = get_layer(project, "lightType_POINT")
        assert isinstance(layer, LightLayer)
        assert layer.light_type == LightType.POINT

        layer.light_type = LightType.PARALLEL
        out = tmp_path / "modified_light_type_parallel.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "lightType_POINT")
        assert isinstance(layer2, LightLayer)
        assert layer2.light_type == LightType.PARALLEL

    def test_light_type_validation_rejects_invalid(self) -> None:
        project = parse_project(SAMPLES_DIR / "lightType.aep")
        layer = get_layer(project, "lightType_AMBIENT")
        assert isinstance(layer, LightLayer)
        with pytest.raises(ValueError, match="Invalid value"):
            layer.light_type = 9999  # type: ignore[assignment]


class TestRoundtripLayerFlags:
    """Roundtrip tests for Layer chunk-backed boolean flags."""

    def test_modify_locked(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "layer_switches.aep")
        layer = get_layer(project, "locked_true")
        assert layer.locked is True

        layer.locked = False
        out = tmp_path / "modified_locked.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "locked_true")
        assert layer2.locked is False

    def test_modify_shy(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "layer_switches.aep")
        layer = get_layer(project, "shy_true")
        assert layer.shy is True

        layer.shy = False
        out = tmp_path / "modified_shy.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "shy_true")
        assert layer2.shy is False

    def test_modify_solo(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "layer_switches.aep")
        layer = get_layer(project, "solo_true")
        assert layer.solo is True

        layer.solo = False
        out = tmp_path / "modified_solo.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "solo_true")
        assert layer2.solo is False


class TestRoundtripAVLayerFlags:
    """Roundtrip tests for AVLayer chunk-backed flags."""

    def test_modify_blending_mode(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "blendingMode.aep")
        layer = get_layer(project, "blendingMode_ADD")
        assert isinstance(layer, AVLayer)
        assert layer.blending_mode == BlendingMode.ADD

        layer.blending_mode = BlendingMode.MULTIPLY
        out = tmp_path / "modified_blending.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "blendingMode_ADD")
        assert isinstance(layer2, AVLayer)
        assert layer2.blending_mode == BlendingMode.MULTIPLY

    def test_modify_three_d_layer(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "avlayer_flags.aep")
        layer = get_layer(project, "threeDLayer_true")
        assert isinstance(layer, AVLayer)
        assert layer.three_d_layer is True

        layer.three_d_layer = False
        out = tmp_path / "modified_3d.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "threeDLayer_true")
        assert isinstance(layer2, AVLayer)
        assert layer2.three_d_layer is False

    def test_environment_layer_sets_three_d_layer(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "avlayer_flags.aep")
        layer = get_layer(project, "threeDLayer_true")
        assert isinstance(layer, AVLayer)
        assert layer.environment_layer is False

        layer.environment_layer = True
        assert layer.three_d_layer is True

        out = tmp_path / "modified_env.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "threeDLayer_true")
        assert isinstance(layer2, AVLayer)
        assert layer2.environment_layer is True
        assert layer2.three_d_layer is True

    def test_three_d_layer_clears_environment_layer(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "avlayer_flags.aep")
        layer = get_layer(project, "threeDLayer_true")
        assert isinstance(layer, AVLayer)

        layer.environment_layer = True
        assert layer.environment_layer is True

        layer.three_d_layer = True
        assert layer.environment_layer is False

        out = tmp_path / "modified_3d_env.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "threeDLayer_true")
        assert isinstance(layer2, AVLayer)
        assert layer2.three_d_layer is True
        assert layer2.environment_layer is False


class TestRoundtripAutoOrient:
    """Roundtrip tests for Layer.auto_orient."""

    def test_modify_along_path_to_no_auto_orient(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "autoOrient.aep")
        layer = get_layer(project, "autoOrient_ALONG_PATH")
        assert layer.auto_orient == AutoOrientType.ALONG_PATH

        layer.auto_orient = AutoOrientType.NO_AUTO_ORIENT
        out = tmp_path / "modified_auto_orient.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "autoOrient_ALONG_PATH")
        assert layer2.auto_orient == AutoOrientType.NO_AUTO_ORIENT

    def test_modify_no_auto_orient_to_along_path(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "inPoint.aep")
        layer = get_layer(project, "inPoint_5")
        assert layer.auto_orient == AutoOrientType.NO_AUTO_ORIENT

        layer.auto_orient = AutoOrientType.ALONG_PATH
        out = tmp_path / "modified_auto_orient.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "inPoint_5")
        assert layer2.auto_orient == AutoOrientType.ALONG_PATH


class TestRoundtripComment:
    """Roundtrip tests for Layer.comment."""

    def test_modify_comment(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "layer_misc.aep")
        layer = get_layer(project, "comment")
        assert layer.comment != ""

        layer.comment = "modified comment"
        out = tmp_path / "modified_comment.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "comment")
        assert layer2.comment == "modified comment"


class TestRoundtripInOutPoint:
    """Roundtrip tests for Layer.in_point and Layer.out_point."""

    def test_modify_in_point(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "inPoint.aep")
        layer = get_layer(project, "inPoint_5")
        original_in = layer.in_point

        new_in = original_in + 1.0
        layer.in_point = new_in
        out = tmp_path / "modified_in_point.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "inPoint_5")
        assert abs(layer2.in_point - new_in) < 0.001

    def test_modify_out_point(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "inPoint.aep")
        layer = get_layer(project, "inPoint_5")
        original_out = layer.out_point

        new_out = original_out - 1.0
        layer.out_point = new_out
        out = tmp_path / "modified_out_point.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "inPoint_5")
        assert abs(layer2.out_point - new_out) < 0.001


class TestRoundtripCommentCreate:
    """Roundtrip tests for Layer.comment when cmta chunk is absent."""

    def test_create_comment_from_empty(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "inPoint.aep")
        layer = get_layer(project, "inPoint_5")
        assert layer.comment == ""

        layer.comment = "new comment"
        out = tmp_path / "created_comment.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "inPoint_5")
        assert layer2.comment == "new comment"


class TestRoundtripFramePoints:
    """Roundtrip tests for frame_in_point, frame_out_point, frame_start_time."""

    def test_modify_frame_in_point(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "inPoint.aep")
        layer = get_layer(project, "inPoint_5")

        layer.frame_in_point = 10
        out = tmp_path / "modified_frame_in_point.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "inPoint_5")
        assert layer2.frame_in_point == 10

    def test_modify_frame_out_point(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "inPoint.aep")
        layer = get_layer(project, "inPoint_5")

        layer.frame_out_point = 20
        out = tmp_path / "modified_frame_out_point.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "inPoint_5")
        assert layer2.frame_out_point == 20

    def test_modify_frame_start_time(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "inPoint.aep")
        layer = get_layer(project, "inPoint_5")

        layer.frame_start_time = 5
        out = tmp_path / "modified_frame_start_time.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "inPoint_5")
        assert layer2.frame_start_time == 5


class TestRoundtripFrameBlendingType:
    """Roundtrip tests for AVLayer.frame_blending_type."""

    def test_no_blend_to_frame_mix(self, tmp_path: Path) -> None:
        project = parse_project(
            SAMPLES_DIR / "frameBlendingType.aep"
        )
        layer = get_layer(project, "frameBlendingType_NO_FRAME_BLEND")
        assert layer.frame_blending_type == FrameBlendingType.NO_FRAME_BLEND
        assert layer.frame_blending is False

        layer.frame_blending_type = FrameBlendingType.FRAME_MIX
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "frameBlendingType_NO_FRAME_BLEND")
        assert layer2.frame_blending_type == FrameBlendingType.FRAME_MIX
        assert layer2.frame_blending is True

    def test_frame_mix_to_pixel_motion(self, tmp_path: Path) -> None:
        project = parse_project(
            SAMPLES_DIR / "frameBlendingType.aep"
        )
        layer = get_layer(project, "frameBlendingType_FRAME_MIX")
        assert layer.frame_blending_type == FrameBlendingType.FRAME_MIX

        layer.frame_blending_type = FrameBlendingType.PIXEL_MOTION
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "frameBlendingType_FRAME_MIX")
        assert layer2.frame_blending_type == FrameBlendingType.PIXEL_MOTION

    def test_pixel_motion_to_no_blend(self, tmp_path: Path) -> None:
        project = parse_project(
            SAMPLES_DIR / "frameBlendingType.aep"
        )
        layer = get_layer(project, "frameBlendingType_PIXEL_MOTION")
        assert layer.frame_blending_type == FrameBlendingType.PIXEL_MOTION

        layer.frame_blending_type = FrameBlendingType.NO_FRAME_BLEND
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "frameBlendingType_PIXEL_MOTION")
        assert layer2.frame_blending_type == FrameBlendingType.NO_FRAME_BLEND
        assert layer2.frame_blending is False


class TestRoundtripTimeRemapEnabled:
    """Roundtrip tests for AVLayer.time_remap_enabled."""

    def test_disable_time_remap(self, tmp_path: Path) -> None:
        project = parse_project(
            SAMPLES_DIR / "outPoint_no_clamp.aep"
        )
        layer = get_layer(project, "outPoint_no_clamp_timeRemap")
        assert isinstance(layer, AVLayer)
        assert layer.time_remap_enabled is True

        layer.time_remap_enabled = False
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "outPoint_no_clamp_timeRemap")
        assert isinstance(layer2, AVLayer)
        assert layer2.time_remap_enabled is False

    def test_enable_time_remap(self, tmp_path: Path) -> None:
        project = parse_project(
            SAMPLES_DIR / "outPoint_no_clamp.aep"
        )
        layer = get_layer(project, "outPoint_no_clamp_timeRemap")
        assert isinstance(layer, AVLayer)

        layer.time_remap_enabled = False
        out = tmp_path / "disabled.aep"
        project.save(out)

        project2 = parse_aep(out).project
        layer2 = get_layer(project2, "outPoint_no_clamp_timeRemap")
        assert isinstance(layer2, AVLayer)
        assert layer2.time_remap_enabled is False

        layer2.time_remap_enabled = True
        out2 = tmp_path / "re_enabled.aep"
        project2.save(out2)
        layer3 = get_layer(parse_aep(out2).project, "outPoint_no_clamp_timeRemap")
        assert isinstance(layer3, AVLayer)
        assert layer3.time_remap_enabled is True


class TestRoundtripLayerEnabled:
    """Roundtrip tests for Layer.enabled."""

    def test_modify_enabled(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "layer_switches.aep")
        layer = get_layer(project, "enabled_false")
        assert layer.enabled is False

        layer.enabled = True
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "enabled_false")
        assert layer2.enabled is True


class TestRoundtripLayerLabel:
    """Roundtrip tests for Layer.label."""

    def test_modify_label(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "layer_misc.aep")
        layer = get_layer(project, "label_3")
        assert layer.label == Label.AQUA

        layer.label = Label.RED
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "label_3")
        assert layer2.label == Label.RED


class TestRoundtripLayerStretch:
    """Roundtrip tests for Layer.stretch."""

    def test_modify_stretch(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "layer_timing.aep")
        layer = get_layer(project, "stretch_200")
        assert math.isclose(layer.stretch, 200.0)

        layer.stretch = 150.0
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "stretch_200")
        assert math.isclose(layer2.stretch, 150.0)


class TestRoundtripAVLayerBoolFlags:
    """Roundtrip tests for remaining AVLayer boolean flags."""

    def test_modify_adjustment_layer(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "avlayer_flags.aep")
        layer = get_layer(project, "adjustmentLayer_true")
        assert isinstance(layer, AVLayer)
        assert layer.adjustment_layer is True

        layer.adjustment_layer = False
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "adjustmentLayer_true")
        assert isinstance(layer2, AVLayer)
        assert layer2.adjustment_layer is False

    def test_modify_audio_enabled(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "audioEnabled.aep")
        layer = get_layer(project, "audioEnabled_false")
        assert isinstance(layer, AVLayer)
        assert layer.audio_enabled is False

        layer.audio_enabled = True
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "audioEnabled_false")
        assert isinstance(layer2, AVLayer)
        assert layer2.audio_enabled is True

    def test_modify_collapse_transformation(self, tmp_path: Path) -> None:
        project = parse_project(
            SAMPLES_DIR / "avlayer_flags.aep"
        )
        layer = get_layer(project, "collapseTransformation_true")
        assert isinstance(layer, AVLayer)
        assert layer.collapse_transformation is True

        layer.collapse_transformation = False
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "collapseTransformation_true")
        assert isinstance(layer2, AVLayer)
        assert layer2.collapse_transformation is False

    def test_modify_effects_active(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "avlayer_flags.aep")
        layer = get_layer(project, "effectsActive_false")
        assert isinstance(layer, AVLayer)
        assert layer.effects_active is False

        layer.effects_active = True
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "effectsActive_false")
        assert isinstance(layer2, AVLayer)
        assert layer2.effects_active is True

    def test_modify_guide_layer(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "avlayer_flags.aep")
        layer = get_layer(project, "guideLayer_true")
        assert isinstance(layer, AVLayer)
        assert layer.guide_layer is True

        layer.guide_layer = False
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "guideLayer_true")
        assert isinstance(layer2, AVLayer)
        assert layer2.guide_layer is False

    def test_modify_motion_blur(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "avlayer_flags.aep")
        layer = get_layer(project, "motionBlur_true")
        assert isinstance(layer, AVLayer)
        assert layer.motion_blur is True

        layer.motion_blur = False
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "motionBlur_true")
        assert isinstance(layer2, AVLayer)
        assert layer2.motion_blur is False

    def test_modify_preserve_transparency(self, tmp_path: Path) -> None:
        project = parse_project(
            SAMPLES_DIR / "avlayer_flags.aep"
        )
        layer = get_layer(project, "preserveTransparency_true")
        assert isinstance(layer, AVLayer)
        assert layer.preserve_transparency is True

        layer.preserve_transparency = False
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "preserveTransparency_true")
        assert isinstance(layer2, AVLayer)
        assert layer2.preserve_transparency is False


class TestRoundtripAVLayerQuality:
    """Roundtrip tests for AVLayer.quality and sampling_quality."""

    def test_modify_quality(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "quality.aep")
        layer = get_layer(project, "quality_BEST")
        assert isinstance(layer, AVLayer)
        assert layer.quality == LayerQuality.BEST

        layer.quality = LayerQuality.DRAFT
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "quality_BEST")
        assert isinstance(layer2, AVLayer)
        assert layer2.quality == LayerQuality.DRAFT

    def test_modify_sampling_quality(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "avlayer_flags.aep")
        layer = get_layer(project, "samplingQuality_BICUBIC")
        assert isinstance(layer, AVLayer)
        assert layer.sampling_quality == LayerSamplingQuality.BICUBIC

        layer.sampling_quality = LayerSamplingQuality.BILINEAR
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_layer(parse_aep(out).project, "samplingQuality_BICUBIC")
        assert isinstance(layer2, AVLayer)
        assert layer2.sampling_quality == LayerSamplingQuality.BILINEAR


class TestRoundtripThreeDPerChar:
    """Roundtrip tests for AVLayer.three_d_per_char."""

    def test_modify_three_d_per_char(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "threeDPerChar_on.aep")
        layer = get_first_layer(project)
        assert isinstance(layer, AVLayer)
        assert layer.three_d_per_char is True

        layer.three_d_per_char = False
        out = tmp_path / "modified.aep"
        project.save(out)
        layer2 = get_first_layer(parse_aep(out).project)
        assert isinstance(layer2, AVLayer)
        assert layer2.three_d_per_char is False


class TestRoundtripTrackMatteType:
    """Roundtrip tests for AVLayer.track_matte_type."""

    def test_modify_track_matte_type(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "trackMatteType.aep")
        comp = get_comp(project, "trackMatteType_ALPHA")
        # Track matte layer is the one with ALPHA matte
        matte_layer = None
        for layer in comp.layers:
            if (
                isinstance(layer, AVLayer)
                and layer.track_matte_type == TrackMatteType.ALPHA
            ):
                matte_layer = layer
                break
        assert matte_layer is not None

        matte_layer.track_matte_type = TrackMatteType.LUMA
        out = tmp_path / "modified.aep"
        project.save(out)

        comp2 = get_comp(parse_aep(out).project, "trackMatteType_ALPHA")
        matte_layer2 = None
        for layer in comp2.layers:
            if (
                isinstance(layer, AVLayer)
                and layer.track_matte_type == TrackMatteType.LUMA
            ):
                matte_layer2 = layer
                break
        assert matte_layer2 is not None


class TestRoundtripLayerName:
    """Roundtrip: modify Layer.name and verify save/reload."""

    def test_modify_layer_name(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "layer_misc.aep")
        layer = get_layer(project, "name_renamed")
        assert layer.name == "RenamedLayer"

        layer.name = "NewName"
        out = tmp_path / "modified_name.aep"
        project.save(out)

        layer2 = get_layer(parse_project(out), "name_renamed")
        assert layer2.name == "NewName"

    def test_set_name_on_source_layer(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "layer_misc.aep")
        layer = get_layer(project, "comment")
        assert not layer.is_name_set

        layer.name = "CustomName"
        out = tmp_path / "set_name.aep"
        project.save(out)

        layer2 = get_layer(parse_project(out), "comment")
        assert layer2.name == "CustomName"
        assert layer2.is_name_set


# ---------------------------------------------------------------------------
# Invariant tests for top-level property synthesis and ordering.
# These lock down the behavior of synthesize_layer_properties
# (in parsers/synthesis.py) so refactoring can be validated against them.
# ---------------------------------------------------------------------------


class TestTopLevelGroupOrder:
    """Canonical order of top-level property groups per layer type."""

    def test_camera_layer(self) -> None:
        layer = get_layer(parse_project(SAMPLES_DIR / "type.aep"), "type_camera")
        assert isinstance(layer, CameraLayer)
        match_names = [p.match_name for p in layer.properties]
        # Canonical groups first, then non-canonical tail (Camera Options)
        assert match_names == [
            "ADBE Marker",
            "ADBE Transform Group",
            "ADBE Camera Options Group",
        ]

    def test_light_layer(self) -> None:
        project = parse_project(SAMPLES_DIR / "lightType.aep")
        # Use any light comp
        layer = get_layer(project, "lightType_PARALLEL")
        assert isinstance(layer, LightLayer)
        match_names = [p.match_name for p in layer.properties]
        assert match_names == [
            "ADBE Marker",
            "ADBE Transform Group",
            "ADBE Light Options Group",
        ]

    def test_shape_layer(self) -> None:
        layer = get_layer(parse_project(SAMPLES_DIR / "type.aep"), "type_shape")
        assert isinstance(layer, ShapeLayer)
        match_names = [p.match_name for p in layer.properties]
        assert match_names == [
            "ADBE Marker",
            "ADBE Root Vectors Group",
            "ADBE Mask Parade",
            "ADBE Effect Parade",
            "ADBE Transform Group",
            "ADBE Layer Styles",
            "ADBE Extrsn Options Group",
            "ADBE Material Options Group",
            "ADBE Audio Group",
            "ADBE Layer Sets",
        ]

    def test_text_layer(self) -> None:
        layer = get_layer(parse_project(SAMPLES_DIR / "type.aep"), "type_text")
        assert isinstance(layer, TextLayer)
        match_names = [p.match_name for p in layer.properties]
        assert match_names == [
            "ADBE Marker",
            "ADBE Text Properties",
            "ADBE Mask Parade",
            "ADBE Effect Parade",
            "ADBE Transform Group",
            "ADBE Layer Styles",
            "ADBE Extrsn Options Group",
            "ADBE Material Options Group",
            "ADBE Audio Group",
            "ADBE Layer Sets",
        ]

    def test_regular_av_layer(self) -> None:
        layer = get_layer(
            parse_project(SAMPLES_DIR / "avlayer_flags.aep"),
            "adjustmentLayer_true",
        )
        assert isinstance(layer, AVLayer)
        assert not layer.three_d_layer
        match_names = [p.match_name for p in layer.properties]
        assert match_names == [
            "ADBE Marker",
            "ADBE Time Remapping",
            "ADBE MTrackers",
            "ADBE Mask Parade",
            "ADBE Effect Parade",
            "ADBE Transform Group",
            "ADBE Layer Styles",
            "ADBE Plane Options Group",
            "ADBE Extrsn Options Group",
            "ADBE Material Options Group",
            "ADBE Audio Group",
            "ADBE Data Group",
            "ADBE Layer Overrides",
            "ADBE Layer Sets",
            "ADBE Source Options Group",
        ]

    def test_three_d_av_layer(self) -> None:
        layer = get_layer(
            parse_project(SAMPLES_DIR / "avlayer_flags.aep"),
            "threeDLayer_true",
        )
        assert isinstance(layer, AVLayer)
        assert layer.three_d_layer
        match_names = [p.match_name for p in layer.properties]
        assert match_names == [
            "ADBE Marker",
            "ADBE Time Remapping",
            "ADBE MTrackers",
            "ADBE Mask Parade",
            "ADBE Effect Parade",
            "ADBE Transform Group",
            "ADBE Layer Styles",
            "ADBE Plane Options Group",
            "ADBE Extrsn Options Group",
            "ADBE Material Options Group",
            "ADBE Audio Group",
            "ADBE Data Group",
            "ADBE Layer Overrides",
            "ADBE Layer Sets",
            "ADBE Source Options Group",
        ]


class TestTopLevelSpecialCases:
    """Special metadata on specific top-level groups."""

    def test_marker_is_leaf_property(self) -> None:
        """Marker is a Property (leaf), not a PropertyGroup."""
        layer = get_layer(
            parse_project(SAMPLES_DIR / "avlayer_flags.aep"),
            "adjustmentLayer_true",
        )
        marker = next(p for p in layer.properties if p.match_name == "ADBE Marker")
        assert isinstance(marker, Property)
        assert not isinstance(marker, PropertyGroup)

    def test_marker_metadata(self) -> None:
        """Synthesized Marker has dimensions=0 and empty units_text."""
        layer = get_layer(
            parse_project(SAMPLES_DIR / "avlayer_flags.aep"),
            "adjustmentLayer_true",
        )
        marker = next(p for p in layer.properties if p.match_name == "ADBE Marker")
        assert isinstance(marker, Property)
        assert marker.dimensions == 0
        assert marker.units_text == ""

    def test_layer_sets_elided(self) -> None:
        """Layer Sets group has elided=True."""
        layer = get_layer(
            parse_project(SAMPLES_DIR / "avlayer_flags.aep"),
            "adjustmentLayer_true",
        )
        layer_sets = next(
            p for p in layer.properties if p.match_name == "ADBE Layer Sets"
        )
        assert isinstance(layer_sets, PropertyGroup)
        assert layer_sets.elided is True

    def test_all_canonical_groups_depth_one(self) -> None:
        """Every canonical top-level group has property_depth == 1."""
        layer = get_layer(
            parse_project(SAMPLES_DIR / "avlayer_flags.aep"),
            "adjustmentLayer_true",
        )
        for prop in layer.properties:
            assert prop.property_depth == 1, (
                f"{prop.match_name} has depth {prop.property_depth}"
            )

    def test_canonical_names(self) -> None:
        """Canonical groups have expected display names."""
        layer = get_layer(
            parse_project(SAMPLES_DIR / "avlayer_flags.aep"),
            "adjustmentLayer_true",
        )
        expected_names = {
            "ADBE Marker": "Marker",
            "ADBE Time Remapping": "Time Remap",
            "ADBE MTrackers": "Motion Trackers",
            "ADBE Mask Parade": "Masks",
            "ADBE Effect Parade": "Effects",
            "ADBE Transform Group": "Transform",
            "ADBE Layer Styles": "Layer Styles",
            "ADBE Plane Options Group": "Geometry Options",
            "ADBE Extrsn Options Group": "Geometry Options",
            "ADBE Material Options Group": "Material Options",
            "ADBE Audio Group": "Audio",
            "ADBE Data Group": "Data",
            "ADBE Layer Overrides": "Essential Properties",
            "ADBE Layer Sets": "Sets",
            "ADBE Source Options Group": "Replace Source",
        }
        for prop in layer.properties:
            if prop.match_name in expected_names:
                assert prop.name == expected_names[prop.match_name], (
                    f"{prop.match_name}: expected name {expected_names[prop.match_name]!r}, "
                    f"got {prop.name!r}"
                )


class TestLayerStylesEnabled:
    """Layer Styles collapsed enabled state and Blend Options mirroring."""

    def test_layer_styles_disabled_when_no_style_enabled(self) -> None:
        """Layer Styles group reports enabled=False when no style is on."""
        layer = get_layer(parse_project(SAMPLES_DIR / "type.aep"), "type_shape")
        layer_styles = next(
            p for p in layer.properties if p.match_name == "ADBE Layer Styles"
        )
        assert isinstance(layer_styles, PropertyGroup)
        assert layer_styles.enabled is False

        # Blend Options mirrors the parent
        blend_options = next(
            p for p in layer_styles.properties
            if p.match_name == "ADBE Blend Options Group"
        )
        assert isinstance(blend_options, PropertyGroup)
        assert blend_options.enabled is False

        # No individual style is enabled
        for child in layer_styles.properties:
            if (
                isinstance(child, PropertyGroup)
                and child.match_name != "ADBE Blend Options Group"
            ):
                assert child.enabled is False, (
                    f"{child.match_name} should be disabled"
                )


class TestTransformNaming:
    """Phase 3 context-dependent naming on transform properties."""

    def test_2d_rotate_z_named_rotation(self) -> None:
        """2D layers show Rotate Z as 'Rotation'."""
        layer = get_layer(
            parse_project(SAMPLES_DIR / "avlayer_flags.aep"),
            "adjustmentLayer_true",
        )
        rotate_z = next(
            p for p in layer.transform if p.match_name == "ADBE Rotate Z"
        )
        assert rotate_z.name == "Rotation"

    def test_3d_rotate_z_named_z_rotation(self) -> None:
        """3D layers show Rotate Z as 'Z Rotation'."""
        layer = get_layer(
            parse_project(SAMPLES_DIR / "avlayer_flags.aep"),
            "threeDLayer_true",
        )
        rotate_z = next(
            p for p in layer.transform if p.match_name == "ADBE Rotate Z"
        )
        assert rotate_z.name == "Z Rotation"

    def test_camera_rotate_z_named_z_rotation(self) -> None:
        """Camera layers show Rotate Z as 'Z Rotation'."""
        layer = get_layer(parse_project(SAMPLES_DIR / "type.aep"), "type_camera")
        rotate_z = next(
            p for p in layer.transform if p.match_name == "ADBE Rotate Z"
        )
        assert rotate_z.name == "Z Rotation"

    def test_camera_anchor_named_point_of_interest(self) -> None:
        """Camera layers show Anchor Point as 'Point of Interest'."""
        layer = get_layer(parse_project(SAMPLES_DIR / "type.aep"), "type_camera")
        anchor = next(
            p for p in layer.transform if p.match_name == "ADBE Anchor Point"
        )
        assert anchor.name == "Point of Interest"

    def test_light_anchor_named_point_of_interest(self) -> None:
        """Light layers show Anchor Point as 'Point of Interest'."""
        layer = get_layer(
            parse_project(SAMPLES_DIR / "lightType.aep"), "lightType_PARALLEL"
        )
        anchor = next(
            p for p in layer.transform if p.match_name == "ADBE Anchor Point"
        )
        assert anchor.name == "Point of Interest"

    def test_2d_anchor_named_anchor_point(self) -> None:
        """2D layers show Anchor Point as 'Anchor Point'."""
        layer = get_layer(
            parse_project(SAMPLES_DIR / "avlayer_flags.aep"),
            "adjustmentLayer_true",
        )
        anchor = next(
            p for p in layer.transform if p.match_name == "ADBE Anchor Point"
        )
        assert anchor.name == "Anchor Point"

    def test_non_canonical_tail_preserved(self) -> None:
        """Non-canonical groups appear after canonical ones."""
        layer = get_layer(parse_project(SAMPLES_DIR / "type.aep"), "type_camera")
        match_names = [p.match_name for p in layer.properties]
        # Camera Options is non-canonical, should be last
        assert match_names[-1] == "ADBE Camera Options Group"
        # Marker and Transform are canonical, should come before
        assert match_names.index("ADBE Marker") < match_names.index(
            "ADBE Camera Options Group"
        )
        assert match_names.index("ADBE Transform Group") < match_names.index(
            "ADBE Camera Options Group"
        )
