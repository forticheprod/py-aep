"""Tests for CompItem model parsing."""

from __future__ import annotations

import math
from pathlib import Path

from conftest import (
    get_comp,
    get_comp_from_json_by_name,
    load_expected,
    parse_project,
)

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

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "composition"
LAYER_SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"
FOOTAGE_SAMPLES_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "footage"
)
EG_SAMPLES_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "essential_graphics"
)


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


class TestEssentialGraphics:
    """Tests for Essential Graphics panel parsing."""

    def test_fill_color_added(self) -> None:
        project = parse_project(EG_SAMPLES_DIR / "fill_color_added.aep")
        comp = next(c for c in project.compositions if c.name == "primary")
        assert comp.motion_graphics_template_name == "Untitled"
        assert comp.motion_graphics_template_controller_count == 1
        assert comp.motion_graphics_controllers[0].name == "Fill Color"
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
        assert comp.motion_graphics_controllers[0].name == "Renamed Color"

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
            ctrls = comp.motion_graphics_controllers
            assert ctrls, f"{sample}: no controllers"
            ctrl = ctrls[0]
            assert ctrl.controller_type == expected_type, (
                f"{sample}: expected type {expected_type}, got {ctrl.controller_type}"
            )
