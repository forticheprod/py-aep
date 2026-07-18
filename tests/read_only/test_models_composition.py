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

    def test_essential_property_uuids_resolve_to_controllers(self) -> None:
        # Regression: a precomp layer's OvG2 overrides live under the layer's
        # root tdgp, not the Layr's direct children. _parse_ovg2_uuids used to
        # search the wrong level, so essential_property_uuids returned [] for
        # every populated sample. The override UUIDs are the source comp's
        # controller UUIDs verbatim.
        project = parse_project(EG_SAMPLES_DIR / "multiple_controllers.aep")
        source = next(c for c in project.compositions if c.name == "primary")
        controller_uuids = {c.uuid for c in source.motion_graphics_controllers}
        assert len(controller_uuids) == 3

        main = next(c for c in project.compositions if c.name == "main")
        with_overrides = [
            layer for layer in main.layers if layer.essential_property_uuids
        ]
        assert len(with_overrides) == 1
        overrides = with_overrides[0].essential_property_uuids
        assert len(overrides) == 3
        assert set(overrides) <= controller_uuids

    def test_essential_property_uuids_empty_without_overrides(self) -> None:
        project = parse_project(EG_SAMPLES_DIR / "no_essential_properties.aep")
        for comp in project.compositions:
            for layer in comp.layers:
                assert layer.essential_property_uuids == []

    def test_essential_property_controllers_resolve(self) -> None:
        # The precomp layer's overrides resolve to the source comp's
        # controllers by shared UUID, in override order.
        project = parse_project(EG_SAMPLES_DIR / "multiple_controllers.aep")
        main = next(c for c in project.compositions if c.name == "main")
        layer = next(layer for layer in main.layers if layer.essential_property_uuids)
        controllers = layer.essential_property_controllers
        assert [c.name for c in controllers] == [
            "Brightness",
            "Layer Opacity",
            "Background Color",
        ]
        # Each resolved controller's uuid is the override uuid at that position.
        assert [c.uuid for c in controllers] == layer.essential_property_uuids

    def test_essential_property_controllers_single_override(self) -> None:
        project = parse_project(EG_SAMPLES_DIR / "text_source_text.aep")
        layer = next(
            layer
            for comp in project.compositions
            for layer in comp.layers
            if layer.essential_property_uuids
        )
        controllers = layer.essential_property_controllers
        assert len(controllers) == 1
        assert controllers[0].name == "Title Text"

    def test_essential_property_controllers_empty_for_non_precomp(self) -> None:
        # A layer with no overrides (a solid, non-CompItem source) resolves [].
        project = parse_project(EG_SAMPLES_DIR / "multiple_controllers.aep")
        primary = next(c for c in project.compositions if c.name == "primary")
        solid = next(layer for layer in primary.layers if layer.name == "Gray Solid 1")
        assert solid.essential_property_controllers == []

    def test_controller_source_property_path(self) -> None:
        # Each controller records the root-to-leaf path of the source-comp
        # property it exposes (match name + index; None index = match by name).
        project = parse_project(EG_SAMPLES_DIR / "multiple_controllers.aep")
        comp = next(c for c in project.compositions if c.name == "primary")
        by_name = {c.name: c for c in comp.motion_graphics_controllers}

        bg = by_name["Background Color"].source_property_path
        assert [n.match_name for n in bg] == [
            "ADBE Effect Parade",
            "ADBE Fill",
            "ADBE Fill-0002",
        ]
        assert [n.prop_index for n in bg] == [None, 0, 3]

        # A transform property (not an effect): every node matches by name.
        opacity = by_name["Layer Opacity"].source_property_path
        assert [n.match_name for n in opacity] == [
            "ADBE Transform Group",
            "ADBE Opacity",
        ]
        assert all(n.prop_index is None for n in opacity)

    def test_group_controller(self) -> None:
        # A type-10 Group controller and its members parse as a flat controller
        # list - group members are SIBLING CCtl, not nested, so the stored ones
        # are not lost. The group itself controls no single source property.
        # (ExtendScript reports a 4th "GropDropZone" drop-zone controller that
        # AE synthesizes at runtime and does not store, so it is absent here.)
        project = parse_project(EG_SAMPLES_DIR / "group_controller.aep")
        comp = next(c for c in project.compositions if c.name == "Comp 1")
        assert [
            (c.name, c.controller_type) for c in comp.motion_graphics_controllers
        ] == [
            ("Group", 10),
            ("Gaussian Blur Blurriness", 2),
            ("Fill Color", 4),
        ]
        assert comp.motion_graphics_controllers[0].source_property_path == []
        # Pin the deliberate one-lower-than-ExtendScript count (ES reports 4
        # including the unstored runtime "GropDropZone"); guards against drift.
        assert comp.motion_graphics_template_controller_count == 3
        assert "GropDropZone" not in comp.motion_graphics_template_controller_names

        # The precomp layer's overrides resolve to all three (incl. the group).
        main = next(c for c in project.compositions if c.name == "main")
        layer = next(la for la in main.layers if la.essential_property_uuids)
        assert [c.name for c in layer.essential_property_controllers] == [
            "Group",
            "Gaussian Blur Blurriness",
            "Fill Color",
        ]

    def test_media_replacement_controller(self) -> None:
        # A type-14 Media Replacement controller parses, and (unlike a Group)
        # AE synthesizes no extra drop-zone controller, so the count matches
        # ExtendScript exactly.
        project = parse_project(EG_SAMPLES_DIR / "media_replacement.aep")
        comp = next(c for c in project.compositions if c.name == "image_with_alpha")
        ctrls = comp.motion_graphics_controllers
        assert comp.motion_graphics_template_controller_count == 1
        assert len(ctrls) == 1
        assert ctrls[0].controller_type == 14
        assert ctrls[0].name == "image_with_alpha.png"
        # The controller records the source comp + layer it controls.
        assert ctrls[0].source_comp_id == 2
        assert ctrls[0].source_layer_id == 14

    def test_media_replacement_override_attributes(self) -> None:
        # The precomp layer's Essential Properties override now exposes its
        # ADBE Layer Source Alternate child, and the media-replacement
        # attributes decode from the blsi slot (AE wraps the replacement
        # footage in a composition, so alternate_source is that comp).
        project = parse_project(EG_SAMPLES_DIR / "media_replacement.aep")
        host = next(c for c in project.compositions if c.name == "image_with_alpha 2")
        layer = next(la for la in host.layers if la.essential_property_uuids)

        overrides = next(
            p for p in layer.properties if p.match_name == "ADBE Layer Overrides"
        )
        assert overrides.num_properties == 1
        alt = overrides.properties[0]
        assert alt.match_name == "ADBE Layer Source Alternate"
        assert alt.name == "image_with_alpha.png"
        assert alt.can_set_alternate_source is True
        assert alt.is_modified is True
        assert alt.alternate_source is not None
        assert alt.alternate_source.name == "image_with_alpha.png_sequence"
        # essential_property_source resolves the override to its source layer
        # in the master comp (matched via the controller's CCId/CLId).
        src = alt.essential_property_source
        assert src is not None
        assert src.name == "image_with_alpha.png"
        assert src.containing_comp.name == "image_with_alpha"

        # The Source Options copy is an unset slot (blsi == 0).
        src_group = next(
            p for p in layer.properties if p.match_name == "ADBE Source Options Group"
        )
        src_alt = next(
            c
            for c in src_group.properties
            if c.match_name == "ADBE Layer Source Alternate"
        )
        assert src_alt.can_set_alternate_source is False
        assert src_alt.alternate_source is None

    def test_property_source_essential_property_walk(self) -> None:
        # A Property-source controller (created from a Property, not Media
        # Replacement Footage) resolves to its source Property by walking the
        # controller's source-property path BY MATCH NAME - prop_index is
        # AE-internal and ignored, so the hidden `-0001`/`-0002` effect leaves
        # resolve correctly. This drives the resolver helpers directly via the
        # controllers (the public `essential_property_source` path is exercised
        # by test_essential_property_override_metadata).
        from py_aep.resolvers.essential_properties import (
            _resolve_controller_source_layer,
            _walk_source_property,
            resolve_essential_property_controllers,
        )

        project = parse_project(EG_SAMPLES_DIR / "group_controller.aep")
        layer = next(
            la
            for comp in project.compositions
            for la in comp.layers
            if resolve_essential_property_controllers(la)
        )
        ctrls = resolve_essential_property_controllers(layer)
        by_name = {c.name: c for c in ctrls}

        blur = by_name["Gaussian Blur Blurriness"]
        src_layer = _resolve_controller_source_layer(project, blur)
        assert src_layer is not None
        leaf = _walk_source_property(src_layer, blur.source_property_path)
        assert leaf is not None
        assert leaf.match_name == "ADBE Gaussian Blur 2-0001"
        assert leaf.enabled is True
        assert leaf.min_value == 0
        assert leaf.max_value == 30000
        assert leaf.value == 25.0

        # The override leaf carries its OWN value; the source Property here is
        # the effect's source value ([1,0,0,1]), distinct from any override.
        fill = by_name["Fill Color"]
        fill_leaf = _walk_source_property(
            _resolve_controller_source_layer(project, fill),
            fill.source_property_path,
        )
        assert fill_leaf is not None
        assert fill_leaf.match_name == "ADBE Fill-0002"
        assert list(fill_leaf.value) == [1.0, 0.0, 0.0, 1.0]

        # A Group controller (type 10) stores no source-property path -> no leaf.
        group = by_name["Group"]
        assert group.source_property_path == []

    def test_essential_property_override_metadata(self) -> None:
        # Non-media-replacement override groups are exposed; each leaf's derived
        # metadata (enabled, bounds, is_modified, name) reflects its Essential
        # Graphics SOURCE property, while its value is its own override cdat.
        project = parse_project(EG_SAMPLES_DIR / "group_controller.aep")
        layer = next(
            la
            for comp in project.compositions
            for la in comp.layers
            if any(p.match_name == "ADBE Layer Overrides" for p in la.properties)
            and next(
                p for p in la.properties if p.match_name == "ADBE Layer Overrides"
            ).num_properties
            > 0
        )
        overrides = next(
            p for p in layer.properties if p.match_name == "ADBE Layer Overrides"
        )
        assert overrides.num_properties == 1
        assert overrides.is_modified is True  # non-empty override group

        grp = overrides.properties[0]
        assert grp.match_name == "ADBE Layer Overrides Group"
        assert grp.num_properties == 2
        assert grp.is_modified is True

        blur, fill = grp.properties
        # Source-derived bounds/enabled (leaf's own tduM is 50, source is 30000).
        assert blur.name == "Gaussian Blur Blurriness"
        assert blur.enabled is True
        assert blur.has_min and blur.has_max
        assert (blur.min_value, blur.max_value) == (0, 30000)
        assert blur.value == 25.0  # own override value
        assert blur.is_modified is False  # equals source value

        # Fill leaf has no tdum/tduM; bounds come from the source Fill Color.
        assert fill.name == "Fill Color"
        assert fill.has_min and fill.has_max
        assert round(fill.max_value, 2) == 3921568.63
        assert fill.is_modified is True  # override differs from source [1,0,0,1]
        assert [round(c, 4) for c in fill.value] == [0.2475, 0.7255, 0.6299, 1.0]

        # Public essential_property_source resolves the override to its source
        # Property (a different object than the override leaf).
        src = blur.essential_property_source
        assert src is not None and src is not blur
        assert src.match_name == "ADBE Gaussian Blur 2-0001"

    def test_point_override_value_in_source_pixels(self) -> None:
        # A point-control override leaf borrows its source parameter's pixel
        # denormalization scale, so its value is in source-comp pixels (matching
        # ExtendScript), not the raw 0-1 the leaf stores. is_modified then
        # compares like for like. Source comp is 1000x1000, so 0.5 -> 500.
        project = parse_project(EG_SAMPLES_DIR / "point_controller.aep")
        layer = next(
            la
            for comp in project.compositions
            for la in comp.layers
            if any(
                p.match_name == "ADBE Layer Overrides" and p.num_properties > 0
                for p in la.properties
            )
        )
        overrides = next(
            p for p in layer.properties if p.match_name == "ADBE Layer Overrides"
        )
        leaf = overrides.properties[0]
        assert leaf.match_name == "ADBE Point Control-0001"
        assert leaf.value == [500.0, 500.0]  # pixels, not the stored [0.5, 0.5]
        assert leaf.is_modified is False  # equals source, once in the same units
        assert leaf.units_text == "pixels"
        src = leaf.essential_property_source
        assert src is not None and src.value == [500.0, 500.0]

    def test_essential_property_override_name_from_controller(self) -> None:
        # When an override leaf's own tdsn is empty, its display name comes from
        # the Essential Graphics controller, not the match-name fallback.
        project = parse_project(EG_SAMPLES_DIR / "multiple_controllers.aep")
        layer = next(
            la
            for comp in project.compositions
            for la in comp.layers
            if any(
                p.match_name == "ADBE Layer Overrides" and p.num_properties > 0
                for p in la.properties
            )
        )
        overrides = next(
            p for p in layer.properties if p.match_name == "ADBE Layer Overrides"
        )
        names = [leaf.name for leaf in overrides.properties]
        assert names == ["Brightness", "Layer Opacity", "Background Color"]

    def test_pre_cif3_falls_back_to_legacy_container(self) -> None:
        # Pre-CIF3 files (AE < 2022) store Essential Graphics in CIF2/CIFO.
        # The parser falls back to them, so the template name still resolves
        # to ExtendScript's "Untitled" instead of None.
        versions = Path(__file__).parent.parent.parent / "samples" / "versions"
        project = parse_project(versions / "ae2018" / "complete.aep")
        assert project.compositions
        for comp in project.compositions:
            assert comp.motion_graphics_template_name == "Untitled"
            assert comp.motion_graphics_template_controller_count == 0
