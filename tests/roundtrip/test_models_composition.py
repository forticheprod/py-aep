"""Tests for CompItem model parsing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from helpers import (
    get_comp,
    parse_project_fresh,
)

from py_aep import AdvancedRendererOptions
from py_aep import parse as parse_aep
from py_aep.enums import GuideOrientationType, ShadowMapResolution

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "composition"
LAYER_SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"
FOOTAGE_SAMPLES_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "footage"
)
EG_SAMPLES_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "essential_graphics"
)


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
        comp = parse_project_fresh(
            SAMPLES_DIR / "renderer_classic_3d.aep"
        ).compositions[0]
        with pytest.raises(ValueError, match="must be one of"):
            comp.renderer = "Not A Renderer"

    def test_renderer_change_swaps_display_name_and_options(
        self, tmp_path: Path
    ) -> None:
        """A renderer change must not leave the old renderer's prda behind.

        Rewriting only prin.match_name produced a file claiming one
        renderer but storing another's options blob, which AE silently
        misread field-by-field (a Classic Shadow Map Resolution index
        came back as Advanced 3D's Quality).
        """
        project = parse_aep(SAMPLES_DIR / "renderer_options_classic_3d.aep").project
        comp = project.compositions[0]
        assert comp.renderer_options.shadow_map_resolution is (
            ShadowMapResolution.RES_750
        )

        comp.renderer = "ADBE Calder"
        out = tmp_path / "switched_renderer.aep"
        project.save(out)

        comp2 = parse_aep(out).project.compositions[0]
        assert comp2._prin.display_name == "Advanced 3D"
        opts = comp2.renderer_options
        assert isinstance(opts, AdvancedRendererOptions)
        # Advanced 3D defaults, not Classic leftovers read as Quality.
        assert opts.quality == 8

    def test_renderer_reassign_same_value_keeps_options(self) -> None:
        project = parse_aep(SAMPLES_DIR / "renderer_options_classic_3d.aep").project
        comp = project.compositions[0]

        comp.renderer = "ADBE Advanced 3d"  # already Classic 3D

        assert comp.renderer_options.shadow_map_resolution is (
            ShadowMapResolution.RES_750
        )


class TestCompItemLazyLayerParsing:
    """Tests for deferred composition layer parsing."""

    def test_layers_parsed_on_first_access(self) -> None:
        comp = get_comp(parse_aep(LAYER_SAMPLES_DIR / "type.aep").project, "type_text")

        assert comp._layers_loaded is False
        assert comp._deferred_layers is not None
        assert len(comp._deferred_layers[0]) == 1

        # Non-layer attributes should not trigger layer parsing.
        _ = comp.width
        assert comp._layers_loaded is False

        layers = comp.layers
        assert comp._layers_loaded is True
        assert len(layers) == 1
        assert comp._deferred_layers is None

    def test_markers_are_eager_without_loading_layers(self) -> None:
        comp = get_comp(parse_aep(LAYER_SAMPLES_DIR / "type.aep").project, "type_text")

        assert comp._layers_loaded is False

        markers = comp.markers
        assert markers == []

        # Reading comp markers must not force regular layer parsing.
        assert comp._layers_loaded is False

    def test_source_used_in_linking_without_layer_parse(self) -> None:
        project = parse_aep(FOOTAGE_SAMPLES_DIR / "footage_not_missing.aep").project
        comp = project.compositions[0]

        assert comp._layers_loaded is False
        assert comp._deferred_layers is not None

        # Trigger lazy linking via used_in - source IDs are extracted
        # on-demand from DeferredListChunk raw bytes.
        footage_items = [it for it in project.items.values() if hasattr(it, "_used_in")]
        linked = [it for it in footage_items if comp in it.used_in]
        assert linked
        assert comp._layers_loaded is False


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
        comp = get_comp(parse_project_fresh(SAMPLES_DIR / "bgColor.aep"), "bgColor_red")
        with pytest.raises(ValueError, match="expected 3 elements"):
            comp.bg_color = [0.1, 0.2]

    def test_bg_color_validation_rejects_out_of_range(self) -> None:
        comp = get_comp(parse_project_fresh(SAMPLES_DIR / "bgColor.aep"), "bgColor_red")
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

        comp.frame_rate = 29.97
        out = tmp_path / "modified_fps29.97.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "frameRate_30")
        assert math.isclose(comp2.frame_rate, 29.97, rel_tol=0.001)

    def test_frame_rate_validation_rejects_zero(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "frameRate.aep"), "frameRate_30"
        )
        with pytest.raises(ValueError, match="must be >= 1.0"):
            comp.frame_rate = 0.0

    def test_frame_rate_validation_rejects_too_high(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "frameRate.aep"), "frameRate_30"
        )
        with pytest.raises(ValueError, match="must be <= 99.0"):
            comp.frame_rate = 100.0


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
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "pixelAspect.aep"), "pixelAspect_2"
        )
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
        comp = get_comp(parse_project_fresh(SAMPLES_DIR / "size.aep"), "size_1920x1080")
        with pytest.raises(ValueError, match="must be >= 4"):
            comp.width = 3

    def test_width_validation_rejects_too_large(self) -> None:
        comp = get_comp(parse_project_fresh(SAMPLES_DIR / "size.aep"), "size_1920x1080")
        with pytest.raises(ValueError, match="must be <= 30000"):
            comp.width = 30001

    def test_width_validation_rejects_non_int(self) -> None:
        comp = get_comp(parse_project_fresh(SAMPLES_DIR / "size.aep"), "size_1920x1080")
        with pytest.raises(TypeError, match="expected an integer"):
            comp.width = 1920.5  # type: ignore[assignment]

    def test_height_validation_rejects_too_small(self) -> None:
        comp = get_comp(parse_project_fresh(SAMPLES_DIR / "size.aep"), "size_1920x1080")
        with pytest.raises(ValueError, match="must be >= 4"):
            comp.height = 0

    def test_height_validation_rejects_too_large(self) -> None:
        comp = get_comp(parse_project_fresh(SAMPLES_DIR / "size.aep"), "size_1920x1080")
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
            parse_project_fresh(SAMPLES_DIR / "shutterAngle.aep"), "shutterAngle_180"
        )
        with pytest.raises(ValueError, match="must be >= 0"):
            comp.shutter_angle = -1

    def test_shutter_angle_validation_rejects_too_large(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "shutterAngle.aep"), "shutterAngle_180"
        )
        with pytest.raises(ValueError, match="must be <= 720"):
            comp.shutter_angle = 721

    def test_shutter_angle_validation_rejects_non_int(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "shutterAngle.aep"), "shutterAngle_180"
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
            parse_project_fresh(SAMPLES_DIR / "comp_flags.aep"), "shutterPhase_minus90"
        )
        with pytest.raises(ValueError, match="must be >= -360"):
            comp.shutter_phase = -361

    def test_shutter_phase_validation_rejects_too_large(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "comp_flags.aep"), "shutterPhase_minus90"
        )
        with pytest.raises(ValueError, match="must be <= 360"):
            comp.shutter_phase = 361

    def test_shutter_phase_validation_rejects_non_int(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "comp_flags.aep"), "shutterPhase_minus90"
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
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "frameRate.aep"), "frameRate_30"
        )
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
            parse_project_fresh(SAMPLES_DIR / "displayStart.aep"), "displayStartTime_10"
        )
        with pytest.raises(ValueError, match="must be >= -10800.0"):
            comp.display_start_time = -10801.0

    def test_display_start_time_validation_rejects_too_large(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "displayStart.aep"), "displayStartTime_10"
        )
        with pytest.raises(ValueError, match="must be <= 86339.0"):
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
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "comp_misc.aep"), "duration_60"
        )
        with pytest.raises(ValueError, match="must be >= 0.0"):
            comp.duration = -1.0

    def test_duration_validation_rejects_too_large(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "comp_misc.aep"), "duration_60"
        )
        with pytest.raises(ValueError, match="must be <= 10800.0"):
            comp.duration = 10801.0

    def test_frame_duration_validation_rejects_zero(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "comp_misc.aep"), "duration_60"
        )
        with pytest.raises(ValueError, match="must be >= 1"):
            comp.frame_duration = 0

    def test_frame_duration_validation_rejects_non_int(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "comp_misc.aep"), "duration_60"
        )
        with pytest.raises(TypeError, match="expected an integer"):
            comp.frame_duration = 300.5  # type: ignore[assignment]

    def test_frame_duration_validation_rejects_too_large(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "comp_misc.aep"), "duration_60"
        )
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
            parse_project_fresh(SAMPLES_DIR / "comp_flags.aep"),
            "motionBlurSamplesPerFrame_32",
        )
        with pytest.raises(ValueError, match="must be >= 2"):
            comp.motion_blur_samples_per_frame = 1

    def test_samples_per_frame_validation_rejects_too_large(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "comp_flags.aep"),
            "motionBlurSamplesPerFrame_32",
        )
        with pytest.raises(ValueError, match="must be <= 64"):
            comp.motion_blur_samples_per_frame = 65

    def test_samples_per_frame_validation_rejects_non_int(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "comp_flags.aep"),
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
            parse_project_fresh(SAMPLES_DIR / "comp_flags.aep"),
            "motionBlurAdaptiveSampleLimit_256",
        )
        with pytest.raises(ValueError, match=r"must be >= \d+"):
            comp.motion_blur_adaptive_sample_limit = 1

    def test_adaptive_sample_limit_validation_rejects_too_large(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "comp_flags.aep"),
            "motionBlurAdaptiveSampleLimit_256",
        )
        with pytest.raises(ValueError, match="must be <= 256"):
            comp.motion_blur_adaptive_sample_limit = 257

    def test_adaptive_sample_limit_validation_rejects_non_int(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "comp_flags.aep"),
            "motionBlurAdaptiveSampleLimit_256",
        )
        with pytest.raises(TypeError, match="expected an integer"):
            comp.motion_blur_adaptive_sample_limit = 128.5  # type: ignore[assignment]

    def test_adaptive_sample_limit_rejects_below_samples_per_frame(
        self,
    ) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "comp_flags.aep"),
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
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "workArea.aep"), "workAreaStart_5"
        )
        with pytest.raises(ValueError, match="must be >= 0"):
            comp.work_area_start = -1.0

    def test_work_area_start_validation_rejects_too_large(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "workArea.aep"), "workAreaStart_5"
        )
        with pytest.raises(ValueError, match="must be <="):
            comp.work_area_start = comp.duration

    def test_work_area_start_frame_validation_rejects_negative(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "workArea.aep"), "workAreaStart_5"
        )
        with pytest.raises(ValueError, match="must be >= 0"):
            comp.work_area_start_frame = -1

    def test_work_area_start_frame_validation_rejects_too_large(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "workArea.aep"), "workAreaStart_5"
        )
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
            parse_project_fresh(SAMPLES_DIR / "workArea.aep"), "workAreaDuration_10"
        )
        with pytest.raises(ValueError, match="must be >="):
            comp.work_area_duration = 0.0

    def test_work_area_duration_validation_rejects_too_large(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "workArea.aep"), "workAreaDuration_10"
        )
        with pytest.raises(ValueError, match="must be <="):
            comp.work_area_duration = comp.duration + 1.0

    def test_work_area_duration_frame_validation_rejects_zero(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "workArea.aep"), "workAreaDuration_10"
        )
        with pytest.raises(ValueError, match="must be >= 1"):
            comp.work_area_duration_frame = 0

    def test_work_area_duration_frame_validation_rejects_too_large(self) -> None:
        comp = get_comp(
            parse_project_fresh(SAMPLES_DIR / "workArea.aep"), "workAreaDuration_10"
        )
        with pytest.raises(ValueError, match="must be <="):
            comp.work_area_duration_frame = comp.frame_duration + 1


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


class TestAddGuide:
    """Tests for Item.add_guide()."""

    def test_add_guide_to_existing(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "guides.aep").project
        comp = get_comp(project, "guides_both")
        original_count = len(comp.guides)

        idx = comp.add_guide(0, 500)
        assert idx == original_count
        assert len(comp.guides) == original_count + 1
        assert comp.guides[idx].orientation_type == GuideOrientationType.HORIZONTAL
        assert comp.guides[idx].position == 500.0

        out = tmp_path / "add_guide.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "guides_both")
        assert len(comp2.guides) == original_count + 1
        assert comp2.guides[idx].orientation_type == GuideOrientationType.HORIZONTAL
        assert comp2.guides[idx].position == 500.0

    def test_add_guide_vertical(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "guides.aep").project
        comp = get_comp(project, "guides_horizontal")

        idx = comp.add_guide(1, 200)
        assert comp.guides[idx].orientation_type == GuideOrientationType.VERTICAL
        assert comp.guides[idx].position == 200.0

        out = tmp_path / "add_vert.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "guides_horizontal")
        assert comp2.guides[idx].orientation_type == GuideOrientationType.VERTICAL
        assert comp2.guides[idx].position == 200.0

    def test_add_guide_to_empty_comp(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "guides.aep").project
        comp = get_comp(project, "guides_none")
        assert comp.guides == []

        idx = comp.add_guide(0, 300)
        assert idx == 0
        assert len(comp.guides) == 1
        assert comp.guides[0].position == 300.0

        out = tmp_path / "bootstrap_guide.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "guides_none")
        assert len(comp2.guides) == 1
        assert comp2.guides[0].orientation_type == GuideOrientationType.HORIZONTAL
        assert comp2.guides[0].position == 300.0

    def test_add_guide_returns_index(self) -> None:
        project = parse_aep(SAMPLES_DIR / "guides.aep").project
        comp = get_comp(project, "guides_none")
        assert comp.add_guide(0, 100) == 0
        assert comp.add_guide(1, 200) == 1
        assert comp.add_guide(0, 300) == 2

    def test_add_guide_invalid_orientation_defaults_horizontal(self) -> None:
        project = parse_aep(SAMPLES_DIR / "guides.aep").project
        comp = get_comp(project, "guides_none")
        comp.add_guide(99, 100)
        assert comp.guides[0].orientation_type == GuideOrientationType.HORIZONTAL

    def test_add_guide_invariant(self) -> None:
        project = parse_aep(SAMPLES_DIR / "guides.aep").project
        comp = get_comp(project, "guides_both")
        comp.add_guide(0, 123)
        assert len(comp._ldat.items) == comp._lhd3.count


class TestRemoveGuide:
    """Tests for Item.remove_guide()."""

    def test_remove_guide_first(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "guides.aep").project
        comp = get_comp(project, "guides_both")
        original_count = len(comp.guides)
        second_guide_pos = comp.guides[1].position

        comp.remove_guide(0)
        assert len(comp.guides) == original_count - 1
        assert comp.guides[0].position == second_guide_pos

        out = tmp_path / "remove_first.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "guides_both")
        assert len(comp2.guides) == original_count - 1
        assert comp2.guides[0].position == second_guide_pos

    def test_remove_guide_last_remaining(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "guides.aep").project
        comp = get_comp(project, "guides_horizontal")
        assert len(comp.guides) == 1

        comp.remove_guide(0)
        assert comp.guides == []
        # After Effects always keeps an (empty) LIST:Gide for an item even with
        # zero guides; deleting the container entirely leaves a project AE opens
        # but cannot re-save. The container stays with count 0 and no ldat.
        assert comp._gide is not None
        assert comp._lhd3 is not None
        assert comp._lhd3.count == 0
        assert comp._ldat is None

        out = tmp_path / "remove_last.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "guides_horizontal")
        assert comp2.guides == []

    def test_remove_guide_invalid_index_raises(self) -> None:
        project = parse_aep(SAMPLES_DIR / "guides.aep").project
        comp = get_comp(project, "guides_horizontal")
        with pytest.raises(IndexError):
            comp.remove_guide(5)
        with pytest.raises(IndexError):
            comp.remove_guide(-1)

    def test_remove_guide_invariant(self) -> None:
        project = parse_aep(SAMPLES_DIR / "guides.aep").project
        comp = get_comp(project, "guides_both")
        comp.remove_guide(0)
        assert len(comp._ldat.items) == comp._lhd3.count

    def test_remove_all_then_add(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "guides.aep").project
        comp = get_comp(project, "guides_horizontal")
        comp.remove_guide(0)
        assert comp.guides == []

        idx = comp.add_guide(1, 400)
        assert idx == 0
        assert comp.guides[0].orientation_type == GuideOrientationType.VERTICAL

        out = tmp_path / "remove_add.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "guides_horizontal")
        assert len(comp2.guides) == 1
        assert comp2.guides[0].orientation_type == GuideOrientationType.VERTICAL
        assert comp2.guides[0].position == 400.0


class TestRemoveAllGuides:
    """Tests for Item.remove_all_guides()."""

    def test_remove_all_guides(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "guides.aep").project
        comp = get_comp(project, "guides_both")
        assert len(comp.guides) > 1

        comp.remove_all_guides()
        assert comp.guides == []
        # Same end state as removing the last guide by index: the empty
        # LIST:Gide stays, its ldat is dropped.
        assert comp._lhd3 is not None
        assert comp._lhd3.count == 0
        assert comp._ldat is None

        out = tmp_path / "remove_all_guides.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "guides_both")
        assert comp2.guides == []

    def test_remove_all_guides_noop(self) -> None:
        project = parse_aep(SAMPLES_DIR / "guides.aep").project
        comp = get_comp(project, "guides_none")
        assert comp.guides == []
        comp.remove_all_guides()
        assert comp.guides == []

    def test_remove_all_then_add(self) -> None:
        project = parse_aep(SAMPLES_DIR / "guides.aep").project
        comp = get_comp(project, "guides_both")
        comp.remove_all_guides()
        assert comp.add_guide(1, 250) == 0
        assert comp.guides[0].position == 250.0


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
        assert comp.motion_graphics_controllers[0].name == "Fill Color"

        comp.motion_graphics_controllers[0].name = "New Controller Name"
        out = tmp_path / "modified.aep"
        project.save(out)
        comp2 = next(
            c for c in parse_aep(out).project.compositions if c.name == "primary"
        )
        assert comp2.motion_graphics_controllers[0].name == "New Controller Name"

    def test_rename_multiple_controllers(self, tmp_path: Path) -> None:
        project = parse_aep(EG_SAMPLES_DIR / "multiple_controllers.aep").project
        comp = next(c for c in project.compositions if c.name == "primary")

        comp.motion_graphics_controllers[1].name = "Renamed Opacity"
        out = tmp_path / "modified.aep"
        project.save(out)
        comp2 = next(
            c for c in parse_aep(out).project.compositions if c.name == "primary"
        )
        assert comp2.motion_graphics_controllers[0].name == "Brightness"
        assert comp2.motion_graphics_controllers[1].name == "Renamed Opacity"
        assert comp2.motion_graphics_controllers[2].name == "Background Color"

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
        # Force deferred EG parsing, then clear to simulate from-scratch.
        comp._ensure_comp_parsed()
        comp._eg_template_name_utf8 = None
        assert comp.motion_graphics_template_name is None

        comp.motion_graphics_template_name = "Created Template"
        assert comp.motion_graphics_template_name == "Created Template"
        assert comp.motion_graphics_template_controller_count == 0
