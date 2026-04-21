"""Tests for CompItem model parsing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from conftest import (
    get_comp,
    get_comp_from_json_by_name,
    load_expected,
    parse_project,
)

from py_aep import parse as parse_aep
from py_aep.enums import GuideOrientationType
from py_aep.models.layers import (
    AVLayer,
    CameraLayer,
    LightLayer,
    ShapeLayer,
    TextLayer,
)
from py_aep.models.sources.file import FileSource
from py_aep.models.sources.solid import SolidSource

SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "models" / "composition"
LAYER_SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "models" / "layer"
FOOTAGE_SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "models" / "footage"


class TestCompItemBasic:
    """Tests for basic composition attributes."""

    def test_bgColor_red(self) -> None:
        expected = load_expected(SAMPLES_DIR, "bgColor")
        comp_json = get_comp_from_json_by_name(expected, "bgColor_red")
        comp = get_comp(parse_project(SAMPLES_DIR / "bgColor.aep"), "bgColor_red")
        assert math.isclose(comp.bg_color[0], comp_json["bgColor"][0])
        assert math.isclose(comp.bg_color[1], comp_json["bgColor"][1])
        assert math.isclose(comp.bg_color[2], comp_json["bgColor"][2])

    def test_bgColor_custom(self) -> None:
        expected = load_expected(SAMPLES_DIR, "bgColor")
        comp_json = get_comp_from_json_by_name(expected, "bgColor_custom")
        comp = get_comp(parse_project(SAMPLES_DIR / "bgColor.aep"), "bgColor_custom")
        assert math.isclose(comp.bg_color[0], comp_json["bgColor"][0])
        assert math.isclose(comp.bg_color[1], comp_json["bgColor"][1])
        assert math.isclose(comp.bg_color[2], comp_json["bgColor"][2])


class TestCompItemSize:
    """Tests for composition size attributes."""

    def test_size_1920x1080(self) -> None:
        expected = load_expected(SAMPLES_DIR, "size")
        comp_json = get_comp_from_json_by_name(expected, "size_1920x1080")
        comp = get_comp(parse_project(SAMPLES_DIR / "size.aep"), "size_1920x1080")
        assert comp.width == comp_json["width"] == 1920
        assert comp.height == comp_json["height"] == 1080

    def test_size_2048x872(self) -> None:
        expected = load_expected(SAMPLES_DIR, "size")
        comp_json = get_comp_from_json_by_name(expected, "size_2048x872")
        comp = get_comp(parse_project(SAMPLES_DIR / "size.aep"), "size_2048x872")
        assert comp.width == comp_json["width"] == 2048
        assert comp.height == comp_json["height"] == 872


class TestCompItemFrameRate:
    """Tests for composition frame rate."""

    def test_frameRate_23976(self) -> None:
        expected = load_expected(SAMPLES_DIR, "frameRate")
        comp_json = get_comp_from_json_by_name(expected, "frameRate_23976")
        comp = get_comp(parse_project(SAMPLES_DIR / "frameRate.aep"), "frameRate_23976")
        assert math.isclose(comp.frame_rate, comp_json["frameRate"], rel_tol=0.001)

    def test_frameRate_30(self) -> None:
        expected = load_expected(SAMPLES_DIR, "frameRate")
        comp_json = get_comp_from_json_by_name(expected, "frameRate_30")
        comp = get_comp(parse_project(SAMPLES_DIR / "frameRate.aep"), "frameRate_30")
        assert comp_json["frameRate"] == 30
        assert math.isclose(comp.frame_rate, comp_json["frameRate"], rel_tol=0.001)


class TestCompItemDuration:
    """Tests for composition duration."""

    def test_duration_60(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_misc")
        comp_json = get_comp_from_json_by_name(expected, "duration_60")
        comp = get_comp(parse_project(SAMPLES_DIR / "comp_misc.aep"), "duration_60")
        assert comp_json["duration"] == 60
        assert math.isclose(comp.duration, comp_json["duration"])


class TestCompItemMotionBlur:
    """Tests for motion blur attributes."""

    def test_motionBlur_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_flags")
        comp_json = get_comp_from_json_by_name(expected, "motionBlur_true")
        comp = get_comp(
            parse_project(SAMPLES_DIR / "comp_flags.aep"), "motionBlur_true"
        )
        assert comp_json["motionBlur"] is True
        assert comp.motion_blur == comp_json["motionBlur"]

    def test_shutterAngle_180(self) -> None:
        expected = load_expected(SAMPLES_DIR, "shutterAngle")
        comp_json = get_comp_from_json_by_name(expected, "shutterAngle_180")
        comp = get_comp(
            parse_project(SAMPLES_DIR / "shutterAngle.aep"), "shutterAngle_180"
        )
        assert comp.shutter_angle == comp_json["shutterAngle"] == 180

    def test_shutterAngle_360(self) -> None:
        expected = load_expected(SAMPLES_DIR, "shutterAngle")
        comp_json = get_comp_from_json_by_name(expected, "shutterAngle_360")
        comp = get_comp(
            parse_project(SAMPLES_DIR / "shutterAngle.aep"), "shutterAngle_360"
        )
        assert comp.shutter_angle == comp_json["shutterAngle"] == 360

    def test_shutterPhase_minus90(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_flags")
        comp_json = get_comp_from_json_by_name(expected, "shutterPhase_minus90")
        comp = get_comp(
            parse_project(SAMPLES_DIR / "comp_flags.aep"), "shutterPhase_minus90"
        )
        assert comp.shutter_phase == comp_json["shutterPhase"] == -90

    def test_motionBlurSamplesPerFrame_32(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_flags")
        comp_json = get_comp_from_json_by_name(expected, "motionBlurSamplesPerFrame_32")
        comp = get_comp(
            parse_project(SAMPLES_DIR / "comp_flags.aep"),
            "motionBlurSamplesPerFrame_32",
        )
        assert (
            comp.motion_blur_samples_per_frame
            == comp_json["motionBlurSamplesPerFrame"]
            == 32
        )

    def test_motionBlurAdaptiveSampleLimit_256(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_flags")
        comp_json = get_comp_from_json_by_name(
            expected, "motionBlurAdaptiveSampleLimit_256"
        )
        comp = get_comp(
            parse_project(SAMPLES_DIR / "comp_flags.aep"),
            "motionBlurAdaptiveSampleLimit_256",
        )
        assert (
            comp.motion_blur_adaptive_sample_limit
            == comp_json["motionBlurAdaptiveSampleLimit"]
            == 256
        )


class TestCompItemResolution:
    """Tests for resolution attributes."""

    def test_resolutionFactor_half(self) -> None:
        expected = load_expected(SAMPLES_DIR, "resolutionFactor")
        comp_json = get_comp_from_json_by_name(expected, "resolutionFactor_half")
        comp = get_comp(
            parse_project(SAMPLES_DIR / "resolutionFactor.aep"), "resolutionFactor_half"
        )
        assert comp.resolution_factor == comp_json["resolutionFactor"]

    def test_resolutionFactor_quarter(self) -> None:
        expected = load_expected(SAMPLES_DIR, "resolutionFactor")
        comp_json = get_comp_from_json_by_name(expected, "resolutionFactor_quarter")
        comp = get_comp(
            parse_project(SAMPLES_DIR / "resolutionFactor.aep"),
            "resolutionFactor_quarter",
        )
        assert comp.resolution_factor == comp_json["resolutionFactor"]


class TestCompItemNestedOptions:
    """Tests for nested composition options."""

    def test_preserveNestedFrameRate_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_flags")
        comp_json = get_comp_from_json_by_name(expected, "preserveNestedFrameRate_true")
        comp = get_comp(
            parse_project(SAMPLES_DIR / "comp_flags.aep"),
            "preserveNestedFrameRate_true",
        )
        assert comp_json["preserveNestedFrameRate"] is True
        assert comp.preserve_nested_frame_rate == comp_json["preserveNestedFrameRate"]

    def test_preserveNestedResolution_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_flags")
        comp_json = get_comp_from_json_by_name(
            expected, "preserveNestedResolution_true"
        )
        comp = get_comp(
            parse_project(SAMPLES_DIR / "comp_flags.aep"),
            "preserveNestedResolution_true",
        )
        assert comp_json["preserveNestedResolution"] is True
        assert comp.preserve_nested_resolution == comp_json["preserveNestedResolution"]


class TestCompItemFrameBlending:
    """Tests for frame blending attribute."""

    def test_frameBlending_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_flags")
        comp_json = get_comp_from_json_by_name(expected, "frameBlending_true")
        comp = get_comp(
            parse_project(SAMPLES_DIR / "comp_flags.aep"), "frameBlending_true"
        )
        assert comp_json["frameBlending"] is True
        assert comp.frame_blending == comp_json["frameBlending"]


class TestCompItemShyLayers:
    """Tests for hide shy layers attribute."""

    def test_hideShyLayers_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_flags")
        comp_json = get_comp_from_json_by_name(expected, "hideShyLayers_true")
        comp = get_comp(
            parse_project(SAMPLES_DIR / "comp_flags.aep"), "hideShyLayers_true"
        )
        assert comp_json["hideShyLayers"] is True
        assert comp.hide_shy_layers == comp_json["hideShyLayers"]


class TestCompItemTime:
    """Tests for time-related attributes (rel_tol=0.001 for precision)."""

    def test_time_0(self) -> None:
        expected = load_expected(SAMPLES_DIR, "time")
        comp_json = get_comp_from_json_by_name(expected, "time_0")
        comp = get_comp(parse_project(SAMPLES_DIR / "time.aep"), "time_0")
        assert comp_json["time"] == 0
        assert math.isclose(comp.time, comp_json["time"])

    def test_time_5(self) -> None:
        expected = load_expected(SAMPLES_DIR, "time")
        comp_json = get_comp_from_json_by_name(expected, "time_5")
        comp = get_comp(parse_project(SAMPLES_DIR / "time.aep"), "time_5")
        assert math.isclose(comp.time, comp_json["time"], rel_tol=0.001)

    def test_time_15(self) -> None:
        expected = load_expected(SAMPLES_DIR, "time")
        comp_json = get_comp_from_json_by_name(expected, "time_15")
        comp = get_comp(parse_project(SAMPLES_DIR / "time.aep"), "time_15")
        assert math.isclose(comp.time, comp_json["time"], rel_tol=0.001)


class TestCompItemWorkArea:
    """Tests for work area attributes (rel_tol=0.001 for precision)."""

    def test_workAreaStart_5(self) -> None:
        expected = load_expected(SAMPLES_DIR, "workArea")
        comp_json = get_comp_from_json_by_name(expected, "workAreaStart_5")
        comp = get_comp(parse_project(SAMPLES_DIR / "workArea.aep"), "workAreaStart_5")
        assert math.isclose(
            comp.work_area_start, comp_json["workAreaStart"], rel_tol=0.001
        )

    def test_workAreaDuration_10(self) -> None:
        expected = load_expected(SAMPLES_DIR, "workArea")
        comp_json = get_comp_from_json_by_name(expected, "workAreaDuration_10")
        comp = get_comp(
            parse_project(SAMPLES_DIR / "workArea.aep"), "workAreaDuration_10"
        )
        assert math.isclose(
            comp.work_area_duration, comp_json["workAreaDuration"], rel_tol=0.001
        )


class TestCompItemDisplayStart:
    """Tests for display start attributes."""

    def test_displayStartFrame_100(self) -> None:
        expected = load_expected(SAMPLES_DIR, "displayStart")
        comp_json = get_comp_from_json_by_name(expected, "displayStartFrame_100")
        comp = get_comp(
            parse_project(SAMPLES_DIR / "displayStart.aep"), "displayStartFrame_100"
        )
        assert comp.display_start_frame == comp_json["displayStartFrame"] == 100

    def test_displayStartTime_10(self) -> None:
        expected = load_expected(SAMPLES_DIR, "displayStart")
        comp_json = get_comp_from_json_by_name(expected, "displayStartTime_10")
        comp = get_comp(
            parse_project(SAMPLES_DIR / "displayStart.aep"), "displayStartTime_10"
        )
        assert comp_json["displayStartTime"] == 10
        assert math.isclose(comp.display_start_time, comp_json["displayStartTime"])


class TestCompItemPixelAspect:
    """Tests for pixel aspect ratio."""

    def test_pixelAspect_0_75(self) -> None:
        expected = load_expected(SAMPLES_DIR, "pixelAspect")
        comp_json = get_comp_from_json_by_name(expected, "pixelAspect_0.75")
        comp = get_comp(
            parse_project(SAMPLES_DIR / "pixelAspect.aep"), "pixelAspect_0.75"
        )
        assert math.isclose(comp.pixel_aspect, comp_json["pixelAspect"])

    def test_pixelAspect_2_0(self) -> None:
        expected = load_expected(SAMPLES_DIR, "pixelAspect")
        comp_json = get_comp_from_json_by_name(expected, "pixelAspect_2")
        comp = get_comp(parse_project(SAMPLES_DIR / "pixelAspect.aep"), "pixelAspect_2")
        assert math.isclose(comp.pixel_aspect, comp_json["pixelAspect"])


class TestCompItemName:
    """Tests for composition name."""

    def test_name_renamed(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_misc")
        comp_json = get_comp_from_json_by_name(expected, "RenamedComp")
        comp = get_comp(parse_project(SAMPLES_DIR / "comp_misc.aep"), "RenamedComp")
        assert comp.name == comp_json["name"] == "RenamedComp"


class TestCompItemComment:
    """Tests for composition comment."""

    def test_comment(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_misc")
        comp_json = get_comp_from_json_by_name(expected, "comment")
        comp = get_comp(parse_project(SAMPLES_DIR / "comp_misc.aep"), "comment")
        assert comp.comment == comp_json["comment"] == "Test comment"


class TestCompItemLabel:
    """Tests for composition label."""

    def test_label_5(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_misc")
        comp_json = get_comp_from_json_by_name(expected, "label_5")
        comp = get_comp(parse_project(SAMPLES_DIR / "comp_misc.aep"), "label_5")
        assert comp_json["label"] == 5
        assert comp.label.value == comp_json["label"]


class TestCompItemDropFrame:
    """Tests for composition drop frame."""

    def test_dropFrame_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "dropFrame")
        comp_json = get_comp_from_json_by_name(expected, "dropFrame_true")
        comp = get_comp(parse_project(SAMPLES_DIR / "dropFrame.aep"), "dropFrame_true")
        assert comp_json["dropFrame"] is True
        assert comp.drop_frame == comp_json["dropFrame"]

    def test_dropFrame_false(self) -> None:
        expected = load_expected(SAMPLES_DIR, "dropFrame")
        comp_json = get_comp_from_json_by_name(expected, "dropFrame_false")
        comp = get_comp(parse_project(SAMPLES_DIR / "dropFrame.aep"), "dropFrame_false")
        assert comp_json["dropFrame"] is False
        assert comp.drop_frame == comp_json["dropFrame"]


class TestCompItemRenderer:
    """Tests for composition renderer attribute."""

    def test_renderers(self) -> None:
        comp = parse_project(SAMPLES_DIR / "renderer_classic_3d.aep").compositions[0]
        assert comp.renderers == [
            "ADBE Advanced 3d",
            "ADBE Calder",
            "ADBE Ernst",
            "ADBE Picasso",
        ]

    def test_renderer_classic_3d(self) -> None:
        comp = parse_project(SAMPLES_DIR / "renderer_classic_3d.aep").compositions[0]
        assert comp.renderer == "ADBE Advanced 3d"

    def test_renderer_advanced_3d(self) -> None:
        comp = parse_project(SAMPLES_DIR / "renderer_advanced_3d.aep").compositions[0]
        assert comp.renderer == "ADBE Calder"

    def test_renderer_cinema_4d(self) -> None:
        comp = parse_project(SAMPLES_DIR / "renderer_cinema_4d.aep").compositions[0]
        assert comp.renderer == "ADBE Ernst"

    def test_renderer_ray_traced(self) -> None:
        comp = parse_project(SAMPLES_DIR / "renderer_ray_traced.aep").compositions[0]
        assert comp.renderer == "ADBE Picasso"


class TestRoundtripRenderer:
    """Roundtrip tests for CompItem.renderer."""

    def test_modify_renderer_to_advanced(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "renderer_classic_3d.aep").project
        comp = project.compositions[0]
        assert comp.renderer == "ADBE Advanced 3d"

        comp.renderer = "ADBE Calder"
        out = tmp_path / "modified_renderer.aep"
        project.save(out)
        comp2 = parse_aep(out).project.compositions[0]
        assert comp2.renderer == "ADBE Calder"

    def test_modify_renderer_to_cinema_4d(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "renderer_classic_3d.aep").project
        comp = project.compositions[0]

        comp.renderer = "ADBE Ernst"
        out = tmp_path / "modified_renderer_c4d.aep"
        project.save(out)
        comp2 = parse_aep(out).project.compositions[0]
        assert comp2.renderer == "ADBE Ernst"

    def test_modify_renderer_back_to_classic(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "renderer_advanced_3d.aep").project
        comp = project.compositions[0]
        assert comp.renderer == "ADBE Calder"

        comp.renderer = "ADBE Advanced 3d"
        out = tmp_path / "modified_renderer_classic.aep"
        project.save(out)
        comp2 = parse_aep(out).project.compositions[0]
        assert comp2.renderer == "ADBE Advanced 3d"

    def test_renderer_validation_rejects_invalid(self) -> None:
        comp = parse_project(SAMPLES_DIR / "renderer_classic_3d.aep").compositions[0]
        with pytest.raises(ValueError, match="Invalid renderer"):
            comp.renderer = "Not A Renderer"


class TestCompItemLayerFiltering:
    """Tests for CompItem layer-type filtering properties."""

    def test_text_layers(self) -> None:
        comp = get_comp(parse_project(LAYER_SAMPLES_DIR / "type.aep"), "type_text")
        assert len(comp.text_layers) == 1
        assert all(isinstance(layer, TextLayer) for layer in comp.text_layers)

    def test_shape_layers(self) -> None:
        comp = get_comp(parse_project(LAYER_SAMPLES_DIR / "type.aep"), "type_shape")
        assert len(comp.shape_layers) == 1
        assert all(isinstance(layer, ShapeLayer) for layer in comp.shape_layers)

    def test_camera_layers(self) -> None:
        comp = get_comp(parse_project(LAYER_SAMPLES_DIR / "type.aep"), "type_camera")
        assert len(comp.camera_layers) == 1
        assert all(isinstance(layer, CameraLayer) for layer in comp.camera_layers)

    def test_light_layers(self) -> None:
        comp = get_comp(
            parse_project(LAYER_SAMPLES_DIR / "lightType.aep"), "lightType_POINT"
        )
        assert len(comp.light_layers) == 1
        assert all(isinstance(layer, LightLayer) for layer in comp.light_layers)

    def test_null_layers(self) -> None:
        comp = get_comp(parse_project(LAYER_SAMPLES_DIR / "type.aep"), "type_null")
        assert len(comp.null_layers) == 1
        assert all(layer.null_layer for layer in comp.null_layers)

    def test_adjustment_layers(self) -> None:
        comp = get_comp(
            parse_project(LAYER_SAMPLES_DIR / "avlayer_flags.aep"),
            "adjustmentLayer_true",
        )
        assert len(comp.adjustment_layers) == 1
        assert all(
            isinstance(layer, AVLayer) and layer.adjustment_layer
            for layer in comp.adjustment_layers
        )

    def test_three_d_layers(self) -> None:
        comp = get_comp(
            parse_project(LAYER_SAMPLES_DIR / "avlayer_flags.aep"), "threeDLayer_true"
        )
        assert len(comp.three_d_layers) == 1
        assert all(
            isinstance(layer, AVLayer) and layer.three_d_layer
            for layer in comp.three_d_layers
        )

    def test_guide_layers(self) -> None:
        comp = get_comp(
            parse_project(LAYER_SAMPLES_DIR / "avlayer_flags.aep"), "guideLayer_true"
        )
        assert len(comp.guide_layers) == 1
        assert all(
            isinstance(layer, AVLayer) and layer.guide_layer
            for layer in comp.guide_layers
        )

    def test_solo_layers(self) -> None:
        comp = get_comp(
            parse_project(LAYER_SAMPLES_DIR / "layer_switches.aep"), "solo_true"
        )
        assert len(comp.solo_layers) == 1
        assert all(layer.solo for layer in comp.solo_layers)

    def test_empty_text_layers(self) -> None:
        """A comp with only a shape layer has no text layers."""
        comp = get_comp(parse_project(LAYER_SAMPLES_DIR / "type.aep"), "type_shape")
        assert comp.text_layers == []

    def test_empty_camera_layers(self) -> None:
        """A comp with only a text layer has no camera layers."""
        comp = get_comp(parse_project(LAYER_SAMPLES_DIR / "type.aep"), "type_text")
        assert comp.camera_layers == []

    def test_empty_light_layers(self) -> None:
        """A comp with only a text layer has no light layers."""
        comp = get_comp(parse_project(LAYER_SAMPLES_DIR / "type.aep"), "type_text")
        assert comp.light_layers == []

    def test_file_layers(self) -> None:
        comp = parse_project(
            FOOTAGE_SAMPLES_DIR / "footage_not_missing.aep"
        ).compositions[0]
        assert len(comp.file_layers) == 1
        for layer in comp.file_layers:
            assert isinstance(layer, AVLayer)
            assert isinstance(layer.source.main_source, FileSource)

    def test_solid_layers(self) -> None:
        comp = parse_project(LAYER_SAMPLES_DIR / "gray_solid_1_above.aep").compositions[
            0
        ]
        assert len(comp.solid_layers) == 2
        for layer in comp.solid_layers:
            assert isinstance(layer, AVLayer)
            assert isinstance(layer.source.main_source, SolidSource)

    def test_placeholder_layers_empty(self) -> None:
        """A comp with only solid layers has no placeholder layers."""
        comp = parse_project(LAYER_SAMPLES_DIR / "gray_solid_1_above.aep").compositions[
            0
        ]
        assert comp.placeholder_layers == []

    def test_empty_file_layers(self) -> None:
        """A comp with only solid layers has no file layers."""
        comp = parse_project(LAYER_SAMPLES_DIR / "gray_solid_1_above.aep").compositions[
            0
        ]
        assert comp.file_layers == []


class TestRoundtripBgColor:
    """Roundtrip tests for CompItem.bg_color."""

    def test_modify_bg_color(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "bgColor.aep").project
        comp = get_comp(project, "bgColor_red")

        # Modify
        comp.bg_color = [0.1, 0.2, 0.3]

        # Save and re-parse
        out = tmp_path / "modified_bg.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "bgColor_red")

        assert math.isclose(comp2.bg_color[0], 0.1, abs_tol=0.005)
        assert math.isclose(comp2.bg_color[1], 0.2, abs_tol=0.005)
        assert math.isclose(comp2.bg_color[2], 0.3, abs_tol=0.005)

    def test_bg_color_validation_rejects_bad_length(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "bgColor.aep"), "bgColor_red")
        with pytest.raises(ValueError, match="expected 3 elements"):
            comp.bg_color = [0.1, 0.2]

    def test_bg_color_validation_rejects_out_of_range(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "bgColor.aep"), "bgColor_red")
        with pytest.raises(ValueError, match="must be <= 1.0"):
            comp.bg_color = [1.5, 0.0, 0.0]


class TestRoundtripFrameRate:
    """Roundtrip tests for CompItem.frame_rate."""

    def test_modify_frame_rate_integer(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "frameRate.aep").project
        comp = get_comp(project, "frameRate_30")
        assert math.isclose(comp.frame_rate, 30.0, rel_tol=0.001)

        comp.frame_rate = 24.0
        out = tmp_path / "modified_fps.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "frameRate_30")
        assert math.isclose(comp2.frame_rate, 24.0, rel_tol=0.001)

    def test_modify_frame_rate_fractional(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "frameRate.aep").project
        comp = get_comp(project, "frameRate_30")

        comp.frame_rate = 60.0
        out = tmp_path / "modified_fps60.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "frameRate_30")
        assert math.isclose(comp2.frame_rate, 60.0, rel_tol=0.001)

    def test_frame_rate_validation_rejects_zero(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "frameRate.aep"), "frameRate_30")
        with pytest.raises(ValueError, match="must be >= 1.0"):
            comp.frame_rate = 0.0

    def test_frame_rate_validation_rejects_too_high(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "frameRate.aep"), "frameRate_30")
        with pytest.raises(ValueError, match="must be <= 999.0"):
            comp.frame_rate = 1000.0


class TestRoundtripPixelAspect:
    """Roundtrip tests for CompItem.pixel_aspect."""

    def test_modify_pixel_aspect(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "pixelAspect.aep").project
        comp = get_comp(project, "pixelAspect_2")
        assert math.isclose(comp.pixel_aspect, 2.0, rel_tol=0.01)

        comp.pixel_aspect = 1.0
        out = tmp_path / "modified_par.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "pixelAspect_2")
        assert math.isclose(comp2.pixel_aspect, 1.0, rel_tol=0.01)

    def test_pixel_aspect_validation_rejects_invalid(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "pixelAspect.aep"), "pixelAspect_2")
        with pytest.raises(ValueError, match="must be >= 0.01"):
            comp.pixel_aspect = -5


class TestRoundtripSize:
    """Roundtrip tests for CompItem.width and .height."""

    def test_modify_width_and_height(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "size.aep").project
        comp = get_comp(project, "size_1920x1080")
        assert comp.width == 1920
        assert comp.height == 1080

        comp.width = 3840
        comp.height = 2160
        out = tmp_path / "modified_size.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "size_1920x1080")
        assert comp2.width == 3840
        assert comp2.height == 2160

    def test_width_validation_rejects_too_small(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "size.aep"), "size_1920x1080")
        with pytest.raises(ValueError, match="must be >= 4"):
            comp.width = 3

    def test_width_validation_rejects_too_large(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "size.aep"), "size_1920x1080")
        with pytest.raises(ValueError, match="must be <= 30000"):
            comp.width = 30001

    def test_width_validation_rejects_non_int(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "size.aep"), "size_1920x1080")
        with pytest.raises(TypeError, match="expected an integer"):
            comp.width = 1920.5  # type: ignore[assignment]

    def test_height_validation_rejects_too_small(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "size.aep"), "size_1920x1080")
        with pytest.raises(ValueError, match="must be >= 4"):
            comp.height = 0

    def test_height_validation_rejects_too_large(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "size.aep"), "size_1920x1080")
        with pytest.raises(ValueError, match="must be <= 30000"):
            comp.height = 30001


class TestRoundtripFlags:
    """Roundtrip tests for boolean CompItem flags."""

    def test_toggle_motion_blur(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "comp_flags.aep").project
        comp = get_comp(project, "motionBlur_true")
        assert comp.motion_blur is True

        comp.motion_blur = False
        out = tmp_path / "modified_mb.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "motionBlur_true")
        assert comp2.motion_blur is False

    def test_toggle_frame_blending(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "comp_flags.aep").project
        comp = get_comp(project, "frameBlending_true")
        assert comp.frame_blending is True

        comp.frame_blending = False
        out = tmp_path / "modified_fb.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "frameBlending_true")
        assert comp2.frame_blending is False

    def test_toggle_hide_shy_layers(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "comp_flags.aep").project
        comp = get_comp(project, "hideShyLayers_true")
        assert comp.hide_shy_layers is True

        comp.hide_shy_layers = False
        out = tmp_path / "modified_shy.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "hideShyLayers_true")
        assert comp2.hide_shy_layers is False


class TestRoundtripShutter:
    """Roundtrip tests for shutter settings."""

    def test_modify_shutter_angle(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "shutterAngle.aep").project
        comp = get_comp(project, "shutterAngle_180")

        comp.shutter_angle = 360
        out = tmp_path / "modified_shutter.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "shutterAngle_180")
        assert comp2.shutter_angle == 360

    def test_shutter_angle_validation_rejects_negative(self) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "shutterAngle.aep"), "shutterAngle_180"
        )
        with pytest.raises(ValueError, match="must be >= 0"):
            comp.shutter_angle = -1

    def test_shutter_angle_validation_rejects_too_large(self) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "shutterAngle.aep"), "shutterAngle_180"
        )
        with pytest.raises(ValueError, match="must be <= 720"):
            comp.shutter_angle = 721

    def test_shutter_angle_validation_rejects_non_int(self) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "shutterAngle.aep"), "shutterAngle_180"
        )
        with pytest.raises(TypeError, match="expected an integer"):
            comp.shutter_angle = 180.5  # type: ignore[assignment]

    def test_modify_shutter_phase(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "comp_flags.aep").project
        comp = get_comp(project, "shutterPhase_minus90")

        comp.shutter_phase = -180
        out = tmp_path / "modified_phase.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "shutterPhase_minus90")
        assert comp2.shutter_phase == -180

    def test_shutter_phase_validation_rejects_too_small(self) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "comp_flags.aep"), "shutterPhase_minus90"
        )
        with pytest.raises(ValueError, match="must be >= -360"):
            comp.shutter_phase = -361

    def test_shutter_phase_validation_rejects_too_large(self) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "comp_flags.aep"), "shutterPhase_minus90"
        )
        with pytest.raises(ValueError, match="must be <= 360"):
            comp.shutter_phase = 361

    def test_shutter_phase_validation_rejects_non_int(self) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "comp_flags.aep"), "shutterPhase_minus90"
        )
        with pytest.raises(TypeError, match="expected an integer"):
            comp.shutter_phase = -90.5  # type: ignore[assignment]


class TestRoundtripResolution:
    """Roundtrip tests for CompItem.resolution_factor."""

    def test_modify_resolution_factor(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "resolutionFactor.aep").project
        comp = get_comp(project, "resolutionFactor_half")

        comp.resolution_factor = [1, 1]
        out = tmp_path / "modified_res.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "resolutionFactor_half")
        assert comp2.resolution_factor == [1, 1]


class TestTimeScaleReadOnly:
    """Test that time_scale is read-only."""

    def test_time_scale_is_read_only(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "frameRate.aep"), "frameRate_30")
        with pytest.raises(AttributeError, match="read-only"):
            comp.time_scale = 12345


class TestRoundtripDerivedTimes:
    """Roundtrip tests: changing frame_rate affects derived time fields."""

    def test_frame_rate_change_updates_frame_duration(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "frameRate.aep").project
        comp = get_comp(project, "frameRate_30")
        original_frame_duration = comp.frame_duration

        comp.frame_rate = 60.0
        out = tmp_path / "modified_fps60b.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "frameRate_30")

        # Duration in seconds should be the same
        assert math.isclose(comp2.duration, comp.duration, rel_tol=0.01)
        # Frame duration should be roughly double at 60fps
        assert comp2.frame_duration > original_frame_duration


class TestRoundtripCombined:
    """Test multiple modifications at once."""

    def test_multiple_fields_at_once(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "size.aep").project
        comp = get_comp(project, "size_1920x1080")

        comp.width = 1280
        comp.height = 720
        comp.bg_color = [0.0, 0.0, 0.0]
        comp.frame_rate = 25.0

        out = tmp_path / "modified_multi.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "size_1920x1080")

        assert comp2.width == 1280
        assert comp2.height == 720
        assert math.isclose(comp2.bg_color[0], 0.0, abs_tol=0.005)
        assert math.isclose(comp2.bg_color[1], 0.0, abs_tol=0.005)
        assert math.isclose(comp2.bg_color[2], 0.0, abs_tol=0.005)
        assert math.isclose(comp2.frame_rate, 25.0, rel_tol=0.001)


class TestRoundtripDisplayStartTime:
    """Roundtrip tests for CompItem.display_start_time."""

    def test_modify_display_start_time(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "displayStart.aep").project
        comp = get_comp(project, "displayStartTime_10")

        comp.display_start_time = 5.0
        out = tmp_path / "modified_dst.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "displayStartTime_10")
        assert math.isclose(comp2.display_start_time, 5.0, abs_tol=0.01)

    def test_display_start_time_validation_rejects_too_small(self) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "displayStart.aep"), "displayStartTime_10"
        )
        with pytest.raises(ValueError, match="must be >= -10800.0"):
            comp.display_start_time = -10801.0

    def test_display_start_time_validation_rejects_too_large(self) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "displayStart.aep"), "displayStartTime_10"
        )
        with pytest.raises(ValueError, match="must be <= 86340.0"):
            comp.display_start_time = 86341.0


class TestRoundtripDuration:
    """Roundtrip tests for CompItem.duration and .frame_duration."""

    def test_modify_duration(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "comp_misc.aep").project
        comp = get_comp(project, "duration_60")

        comp.duration = 120.0
        out = tmp_path / "modified_dur.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "duration_60")
        assert math.isclose(comp2.duration, 120.0, rel_tol=0.01)

    def test_modify_frame_duration(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "comp_misc.aep").project
        comp = get_comp(project, "duration_60")
        fps = comp.frame_rate

        comp.frame_duration = 300
        out = tmp_path / "modified_fdur.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "duration_60")
        assert comp2.frame_duration == 300
        assert math.isclose(comp2.duration, 300 / fps, rel_tol=0.01)

    def test_duration_validation_rejects_negative(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "comp_misc.aep"), "duration_60")
        with pytest.raises(ValueError, match="must be >= 0.0"):
            comp.duration = -1.0

    def test_duration_validation_rejects_too_large(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "comp_misc.aep"), "duration_60")
        with pytest.raises(ValueError, match="must be <= 10800.0"):
            comp.duration = 10801.0

    def test_frame_duration_validation_rejects_zero(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "comp_misc.aep"), "duration_60")
        with pytest.raises(ValueError, match="must be >= 1"):
            comp.frame_duration = 0

    def test_frame_duration_validation_rejects_non_int(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "comp_misc.aep"), "duration_60")
        with pytest.raises(TypeError, match="expected an integer"):
            comp.frame_duration = 300.5  # type: ignore[assignment]

    def test_frame_duration_validation_rejects_too_large(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "comp_misc.aep"), "duration_60")
        max_frames = int(comp.duration * comp.frame_rate)
        with pytest.raises(ValueError, match="must be <="):
            comp.frame_duration = max_frames + 1


class TestRoundtripMotionBlurSamples:
    """Roundtrip tests for motion blur sample settings."""

    def test_modify_samples_per_frame(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "comp_flags.aep").project
        comp = get_comp(project, "motionBlurSamplesPerFrame_32")

        comp.motion_blur_samples_per_frame = 16
        out = tmp_path / "modified_spf.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "motionBlurSamplesPerFrame_32")
        assert comp2.motion_blur_samples_per_frame == 16

    def test_samples_per_frame_validation_rejects_too_small(self) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "comp_flags.aep"),
            "motionBlurSamplesPerFrame_32",
        )
        with pytest.raises(ValueError, match="must be >= 2"):
            comp.motion_blur_samples_per_frame = 1

    def test_samples_per_frame_validation_rejects_too_large(self) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "comp_flags.aep"),
            "motionBlurSamplesPerFrame_32",
        )
        with pytest.raises(ValueError, match="must be <= 64"):
            comp.motion_blur_samples_per_frame = 65

    def test_samples_per_frame_validation_rejects_non_int(self) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "comp_flags.aep"),
            "motionBlurSamplesPerFrame_32",
        )
        with pytest.raises(TypeError, match="expected an integer"):
            comp.motion_blur_samples_per_frame = 16.5  # type: ignore[assignment]

    def test_modify_adaptive_sample_limit(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "comp_flags.aep").project
        comp = get_comp(project, "motionBlurAdaptiveSampleLimit_256")

        comp.motion_blur_adaptive_sample_limit = 128
        out = tmp_path / "modified_asl.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "motionBlurAdaptiveSampleLimit_256")
        assert comp2.motion_blur_adaptive_sample_limit == 128

    def test_adaptive_sample_limit_validation_rejects_too_small(self) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "comp_flags.aep"),
            "motionBlurAdaptiveSampleLimit_256",
        )
        with pytest.raises(ValueError, match=r"must be >= \d+"):
            comp.motion_blur_adaptive_sample_limit = 1

    def test_adaptive_sample_limit_validation_rejects_too_large(self) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "comp_flags.aep"),
            "motionBlurAdaptiveSampleLimit_256",
        )
        with pytest.raises(ValueError, match="must be <= 256"):
            comp.motion_blur_adaptive_sample_limit = 257

    def test_adaptive_sample_limit_validation_rejects_non_int(self) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "comp_flags.aep"),
            "motionBlurAdaptiveSampleLimit_256",
        )
        with pytest.raises(TypeError, match="expected an integer"):
            comp.motion_blur_adaptive_sample_limit = 128.5  # type: ignore[assignment]

    def test_adaptive_sample_limit_rejects_below_samples_per_frame(
        self,
    ) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "comp_flags.aep"),
            "motionBlurAdaptiveSampleLimit_256",
        )
        # samples_per_frame is 16, so 8 must be rejected
        assert comp.motion_blur_samples_per_frame == 16
        with pytest.raises(ValueError, match="must be >= 16"):
            comp.motion_blur_adaptive_sample_limit = 8


class TestRoundtripWorkAreaStart:
    """Roundtrip tests for CompItem.work_area_start."""

    def test_modify_work_area_start(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "workArea.aep").project
        comp = get_comp(project, "workAreaStart_5")

        comp.work_area_start = 2.0
        out = tmp_path / "modified_was.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "workAreaStart_5")
        assert math.isclose(comp2.work_area_start, 2.0, abs_tol=0.01)

    def test_modify_work_area_start_frame(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "workArea.aep").project
        comp = get_comp(project, "workAreaStart_5")

        comp.work_area_start_frame = 48
        out = tmp_path / "modified_wasf.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "workAreaStart_5")
        assert comp2.work_area_start_frame == 48

    def test_work_area_start_validation_rejects_negative(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "workArea.aep"), "workAreaStart_5")
        with pytest.raises(ValueError, match="must be >= 0"):
            comp.work_area_start = -1.0

    def test_work_area_start_validation_rejects_too_large(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "workArea.aep"), "workAreaStart_5")
        with pytest.raises(ValueError, match="must be <="):
            comp.work_area_start = comp.duration

    def test_work_area_start_frame_validation_rejects_negative(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "workArea.aep"), "workAreaStart_5")
        with pytest.raises(ValueError, match="must be >= 0"):
            comp.work_area_start_frame = -1

    def test_work_area_start_frame_validation_rejects_too_large(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "workArea.aep"), "workAreaStart_5")
        with pytest.raises(ValueError, match="must be <="):
            comp.work_area_start_frame = comp.frame_duration


class TestRoundtripWorkAreaDuration:
    """Roundtrip tests for CompItem.work_area_duration."""

    def test_modify_work_area_duration(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "workArea.aep").project
        comp = get_comp(project, "workAreaDuration_10")

        comp.work_area_duration = 5.0
        out = tmp_path / "modified_wad.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "workAreaDuration_10")
        assert math.isclose(comp2.work_area_duration, 5.0, abs_tol=0.01)

    def test_modify_work_area_duration_frame(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "workArea.aep").project
        comp = get_comp(project, "workAreaDuration_10")

        comp.work_area_duration_frame = 120
        out = tmp_path / "modified_wadf.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "workAreaDuration_10")
        assert comp2.work_area_duration_frame == 120

    def test_work_area_duration_validation_rejects_too_small(self) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "workArea.aep"), "workAreaDuration_10"
        )
        with pytest.raises(ValueError, match="must be >="):
            comp.work_area_duration = 0.0

    def test_work_area_duration_validation_rejects_too_large(self) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "workArea.aep"), "workAreaDuration_10"
        )
        with pytest.raises(ValueError, match="must be <="):
            comp.work_area_duration = comp.duration + 1.0

    def test_work_area_duration_frame_validation_rejects_zero(self) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "workArea.aep"), "workAreaDuration_10"
        )
        with pytest.raises(ValueError, match="must be >= 1"):
            comp.work_area_duration_frame = 0

    def test_work_area_duration_frame_validation_rejects_too_large(self) -> None:
        comp = get_comp(
            parse_project(SAMPLES_DIR / "workArea.aep"), "workAreaDuration_10"
        )
        with pytest.raises(ValueError, match="must be <="):
            comp.work_area_duration_frame = comp.frame_duration + 1


class TestCompItemGuides:
    """Tests for CompItem.guides."""

    def test_no_guides(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "guides.aep"), "guides_none")
        assert comp.guides == []

    def test_horizontal_guide(self) -> None:
        expected = load_expected(SAMPLES_DIR, "guides")
        comp_json = get_comp_from_json_by_name(expected, "guides_horizontal")
        comp = get_comp(parse_project(SAMPLES_DIR / "guides.aep"), "guides_horizontal")
        assert len(comp.guides) == 1
        guide = comp.guides[0]
        exp = comp_json["guides"][0]
        assert guide.orientation_type == exp["orientationType"]
        assert guide.position == exp["position"]
        assert guide.position_type == exp["positionType"]

    def test_both_guides(self) -> None:
        expected = load_expected(SAMPLES_DIR, "guides")
        comp_json = get_comp_from_json_by_name(expected, "guides_both")
        comp = get_comp(parse_project(SAMPLES_DIR / "guides.aep"), "guides_both")
        assert len(comp.guides) == len(comp_json["guides"])
        for guide, exp in zip(comp.guides, comp_json["guides"]):
            assert guide.orientation_type == exp["orientationType"]
            assert guide.position == exp["position"]
            assert guide.position_type == exp["positionType"]

    def test_guide_repr(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "guides.aep"), "guides_horizontal")
        assert "horizontal" in repr(comp.guides[0])

    def test_guide_orientation_horizontal(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "guides.aep"), "guides_horizontal")
        assert comp.guides[0].orientation_type == GuideOrientationType.HORIZONTAL

    def test_guide_orientation_vertical(self) -> None:
        comp = get_comp(parse_project(SAMPLES_DIR / "guides.aep"), "guides_both")
        vertical_guides = [
            g
            for g in comp.guides
            if g.orientation_type == GuideOrientationType.VERTICAL
        ]
        assert len(vertical_guides) == 1
        assert vertical_guides[0].position == 960.0


class TestRoundtripGuides:
    """Roundtrip tests for CompItem.guides."""

    def test_modify_guide_position(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "guides.aep").project
        comp = get_comp(project, "guides_horizontal")
        comp.guides[0].position = 100.0

        out = tmp_path / "modified_guide.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "guides_horizontal")
        assert comp2.guides[0].position == 100.0

    def test_modify_guide_orientation(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "guides.aep").project
        comp = get_comp(project, "guides_horizontal")
        assert comp.guides[0].orientation_type == 0
        comp.guides[0].orientation_type = 1

        out = tmp_path / "modified_orient.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "guides_horizontal")
        assert comp2.guides[0].orientation_type == 1


class TestValidateGuidePosition:
    """Validation tests for Guide.position bounds."""

    def test_position_rejects_negative(self) -> None:
        comp = get_comp(
            parse_aep(SAMPLES_DIR / "guides.aep").project, "guides_horizontal"
        )
        with pytest.raises(ValueError, match="must be >= 0"):
            comp.guides[0].position = -1.0


class TestRoundtripDraft3d:
    """Roundtrip tests for CompItem.draft3d."""

    def test_toggle_draft3d(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "renderer_classic_3d.aep").project
        comp = project.compositions[0]

        comp.draft3d = True
        out = tmp_path / "modified.aep"
        project.save(out)
        comp2 = parse_aep(out).project.compositions[0]
        assert comp2.draft3d is True

        comp2.draft3d = False
        out2 = tmp_path / "toggled.aep"
        parse_aep(out).project.save(out2)
        # Re-parse to check original state preserved
        project3 = parse_aep(out).project
        comp3 = project3.compositions[0]
        comp3.draft3d = False
        out3 = tmp_path / "toggled_back.aep"
        project3.save(out3)
        comp4 = parse_aep(out3).project.compositions[0]
        assert comp4.draft3d is False


class TestRoundtripPreserveNested:
    """Roundtrip tests for CompItem.preserve_nested_*."""

    def test_toggle_preserve_nested_frame_rate(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "comp_flags.aep").project
        comp = get_comp(project, "preserveNestedFrameRate_true")
        assert comp.preserve_nested_frame_rate is True

        comp.preserve_nested_frame_rate = False
        out = tmp_path / "modified.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "preserveNestedFrameRate_true")
        assert comp2.preserve_nested_frame_rate is False

    def test_toggle_preserve_nested_resolution(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "comp_flags.aep").project
        comp = get_comp(project, "preserveNestedResolution_true")
        assert comp.preserve_nested_resolution is True

        comp.preserve_nested_resolution = False
        out = tmp_path / "modified.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "preserveNestedResolution_true")
        assert comp2.preserve_nested_resolution is False


class TestRoundtripDropFrame:
    """Roundtrip tests for CompItem.drop_frame."""

    def test_toggle_drop_frame(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "dropFrame.aep").project
        comp = get_comp(project, "dropFrame_true")
        assert comp.drop_frame is True

        comp.drop_frame = False
        out = tmp_path / "modified.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "dropFrame_true")
        assert comp2.drop_frame is False


EG_SAMPLES_DIR = (
    Path(__file__).parent.parent / "samples" / "models" / "essential_graphics"
)


class TestEssentialGraphics:
    """Tests for Essential Graphics panel parsing."""

    def test_fill_color_added(self) -> None:
        project = parse_project(EG_SAMPLES_DIR / "fill_color_added.aep")
        comp = next(c for c in project.compositions if c.name == "primary")
        assert comp.motion_graphics_template_name == "Untitled"
        assert comp.motion_graphics_template_controller_count == 1
        assert comp.get_motion_graphics_template_controller_name(1) == "Fill Color"
        assert comp.motion_graphics_template_controller_names == ["Fill Color"]

    def test_custom_template_name(self) -> None:
        project = parse_project(EG_SAMPLES_DIR / "custom_template_name.aep")
        comp = next(c for c in project.compositions if c.name == "primary")
        assert comp.motion_graphics_template_name == "My Custom Template"

    def test_multiple_controllers(self) -> None:
        project = parse_project(EG_SAMPLES_DIR / "multiple_controllers.aep")
        comp = next(c for c in project.compositions if c.name == "primary")
        assert comp.motion_graphics_template_controller_count == 3
        assert comp.motion_graphics_template_controller_names == [
            "Brightness",
            "Layer Opacity",
            "Background Color",
        ]

    def test_controller_renamed(self) -> None:
        project = parse_project(EG_SAMPLES_DIR / "controller_renamed.aep")
        comp = next(c for c in project.compositions if c.name == "primary")
        assert comp.get_motion_graphics_template_controller_name(1) == "Renamed Color"

    def test_no_essential_properties(self) -> None:
        project = parse_project(EG_SAMPLES_DIR / "no_essential_properties.aep")
        for comp in project.compositions:
            assert comp.motion_graphics_template_controller_count == 0
            assert comp.motion_graphics_template_controller_names == []

    def test_main_comp_has_no_controllers(self) -> None:
        project = parse_project(EG_SAMPLES_DIR / "fill_color_added.aep")
        comp = next(c for c in project.compositions if c.name == "main")
        assert comp.motion_graphics_template_controller_count == 0

    def test_controller_types(self) -> None:
        """Verify controller_type for each controller type sample."""
        type_samples = {
            "checkbox_controller": 1,
            "slider_controller": 2,
            "color_controller": 4,
            "point_controller": 5,
            "text_source_text": 6,
            "dropdown_controller": 13,
        }
        for sample, expected_type in type_samples.items():
            project = parse_project(EG_SAMPLES_DIR / f"{sample}.aep")
            comp = next(c for c in project.compositions if c.name == "primary")
            assert comp._eg_controllers, f"{sample}: no controllers"
            ctrl = comp._eg_controllers[0]
            assert ctrl.controller_type == expected_type, (
                f"{sample}: expected type {expected_type}, got {ctrl.controller_type}"
            )


class TestRoundtripEssentialGraphics:
    """Roundtrip tests for Essential Graphics panel."""

    def test_rename_template(self, tmp_path: Path) -> None:
        project = parse_aep(EG_SAMPLES_DIR / "fill_color_added.aep").project
        comp = next(c for c in project.compositions if c.name == "primary")
        assert comp.motion_graphics_template_name == "Untitled"

        comp.motion_graphics_template_name = "My New Name"
        out = tmp_path / "modified.aep"
        project.save(out)
        comp2 = next(
            c for c in parse_aep(out).project.compositions if c.name == "primary"
        )
        assert comp2.motion_graphics_template_name == "My New Name"

    def test_rename_controller(self, tmp_path: Path) -> None:
        project = parse_aep(EG_SAMPLES_DIR / "fill_color_added.aep").project
        comp = next(c for c in project.compositions if c.name == "primary")
        assert comp.get_motion_graphics_template_controller_name(1) == "Fill Color"

        comp.set_motion_graphics_controller_name(1, "New Controller Name")
        out = tmp_path / "modified.aep"
        project.save(out)
        comp2 = next(
            c for c in parse_aep(out).project.compositions if c.name == "primary"
        )
        assert (
            comp2.get_motion_graphics_template_controller_name(1)
            == "New Controller Name"
        )

    def test_rename_multiple_controllers(self, tmp_path: Path) -> None:
        project = parse_aep(EG_SAMPLES_DIR / "multiple_controllers.aep").project
        comp = next(c for c in project.compositions if c.name == "primary")

        comp.set_motion_graphics_controller_name(2, "Renamed Opacity")
        out = tmp_path / "modified.aep"
        project.save(out)
        comp2 = next(
            c for c in parse_aep(out).project.compositions if c.name == "primary"
        )
        assert comp2.get_motion_graphics_template_controller_name(1) == "Brightness"
        assert (
            comp2.get_motion_graphics_template_controller_name(2) == "Renamed Opacity"
        )
        assert (
            comp2.get_motion_graphics_template_controller_name(3) == "Background Color"
        )

    def test_create_template_name(self, tmp_path: Path) -> None:
        """Setting motion_graphics_template_name on a comp without EG
        creates the CIF3 chunk structure and roundtrips correctly."""
        project = parse_aep(EG_SAMPLES_DIR / "base.aep").project
        comp = next(c for c in project.compositions if c.name == "main")
        assert comp.motion_graphics_template_name == "Untitled"

        # Overwrite existing template name
        comp.motion_graphics_template_name = "Brand New Template"
        out = tmp_path / "modified.aep"
        project.save(out)
        comp2 = next(c for c in parse_aep(out).project.compositions if c.name == "main")
        assert comp2.motion_graphics_template_name == "Brand New Template"

    def test_create_template_name_from_scratch(self) -> None:
        """Setting motion_graphics_template_name when _eg_template_name_utf8
        is None creates a new CIF3 chunk structure in memory."""
        project = parse_aep(EG_SAMPLES_DIR / "base.aep").project
        comp = next(c for c in project.compositions if c.name == "main")
        comp._eg_template_name_utf8 = None
        assert comp.motion_graphics_template_name is None

        comp.motion_graphics_template_name = "Created Template"
        assert comp.motion_graphics_template_name == "Created Template"
        assert comp.motion_graphics_template_controller_count == 0
