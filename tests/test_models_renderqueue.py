"""Tests for RenderQueue model parsing."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from conftest import get_rqi, load_expected, parse_project

from py_aep import parse as parse_aep
from py_aep.enums import (
    ConvertToLinearLight,
    FieldRender,
    FrameRateSetting,
    GetSettingsFormat,
    LogType,
    MotionBlurSetting,
    OutputChannels,
    OutputColorDepth,
    PostRenderAction,
    RenderQuality,
    ResizeQuality,
    RQItemStatus,
    TimeSpanSource,
)
from py_aep.models.renderqueue import OutputModule
from py_aep.resolvers.output import resolve_output_filename

SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "models" / "renderqueue"
OM_SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "models" / "output_module"
BUGS_DIR = Path(__file__).parent.parent / "samples" / "bugs"


class TestRenderQueueBasic:
    """Tests for basic render queue attributes."""

    @pytest.mark.parametrize(
        "sample_name, expected_count",
        [
            ("empty", 0),
            ("numItems_1", 1),
            ("numItems_2", 2),
        ],
    )
    def test_num_items(self, sample_name: str, expected_count: int) -> None:
        expected = load_expected(SAMPLES_DIR, sample_name)
        project = parse_project(SAMPLES_DIR / f"{sample_name}.aep")
        assert expected["renderQueue"]["numItems"] == expected_count
        assert len(project.render_queue.items) == expected_count


class TestOutputModule:
    """Tests for output module attributes."""

    def test_outputModule_file(self) -> None:
        _ = load_expected(OM_SAMPLES_DIR, "file")
        project = parse_project(OM_SAMPLES_DIR / "file.aep")
        rqi = project.render_queue.items[0]
        assert len(rqi.output_modules) >= 1
        om = rqi.output_modules[0]
        assert isinstance(om, OutputModule)
        assert om.file is not None

    def test_outputModule_template(self) -> None:
        _ = load_expected(OM_SAMPLES_DIR, "template")
        project = parse_project(OM_SAMPLES_DIR / "template.aep")
        rqi = project.render_queue.items[0]
        assert len(rqi.output_modules) >= 1
        om = rqi.output_modules[0]
        assert om.name is not None

    def test_outputModule_no_hdrm_chunk(self) -> None:
        """Files without hdrm chunk should still parse name/file_template/file
        correctly (Utf8 chunks identified by position relative to Als2)."""
        project = parse_project(BUGS_DIR / "outputmodule_path.aep")
        rqi = project.render_queue.items[0]
        om = rqi.output_modules[0]
        assert om.name == "H.264 - Match Render Settings - 15 Mbps"
        assert "[compName]" in om.file_template
        assert "[compName]" not in om.file

    def test_numOutputModules_2(self) -> None:
        expected = load_expected(OM_SAMPLES_DIR, "numOutputModules_2")
        project = parse_project(OM_SAMPLES_DIR / "numOutputModules_2.aep")
        rqi = project.render_queue.items[0]
        exp_oms = expected["renderQueue"]["items"][0]["outputModules"]
        assert len(rqi.output_modules) == len(exp_oms) == 2

    def test_include_source_xmp_on(self) -> None:
        project = parse_project(OM_SAMPLES_DIR / "om_misc.aep")
        rqi = get_rqi(project, "include_source_xmp_data_on")
        om = rqi.output_modules[0]
        assert om.include_source_xmp is True

    def test_include_source_xmp_off(self) -> None:
        project = parse_project(OM_SAMPLES_DIR / "include_source_xmp_data_off.aep")
        om = project.render_queue.items[0].output_modules[0]
        assert om.include_source_xmp is False

    def test_crop_checked(self) -> None:
        project = parse_project(OM_SAMPLES_DIR / "om_crop.aep")
        rqi = get_rqi(project, "crop_checked")
        om = rqi.output_modules[0]
        assert om.settings["Crop"] is True

    def test_crop_unchecked(self) -> None:
        project = parse_project(OM_SAMPLES_DIR / "crop_unchecked.aep")
        om = project.render_queue.items[0].output_modules[0]
        assert om.settings["Crop"] is False

    def test_crop_bottom_10(self) -> None:
        expected = load_expected(OM_SAMPLES_DIR, "crop_bottom_10")
        project = parse_project(OM_SAMPLES_DIR / "crop_bottom_10.aep")
        om = project.render_queue.items[0].output_modules[0]
        exp_om = expected["renderQueue"]["items"][0]["outputModules"][0]
        assert om.settings["Crop"] is True
        assert om.settings["Crop Bottom"] == exp_om["settings"]["Crop Bottom"] == 10
        assert om.settings["Crop Top"] == 0

    def test_crop_top_10(self) -> None:
        expected = load_expected(OM_SAMPLES_DIR, "crop_top_10")
        project = parse_project(OM_SAMPLES_DIR / "crop_top_10.aep")
        om = project.render_queue.items[0].output_modules[0]
        exp_om = expected["renderQueue"]["items"][0]["outputModules"][0]
        assert om.settings["Crop"] is True
        assert om.settings["Crop Top"] == exp_om["settings"]["Crop Top"] == 10
        assert om.settings["Crop Bottom"] == 0

    @pytest.mark.parametrize(
        "sample_name, expected_value",
        [
            ("convert_to_linear_light_off", ConvertToLinearLight.OFF),
            ("convert_to_linear_light_on", ConvertToLinearLight.ON),
            (
                "convert_to_linear_light_on_for_32_bpc",
                ConvertToLinearLight.ON_FOR_32_BPC,
            ),
        ],
    )
    def test_convert_to_linear_light(
        self, sample_name: str, expected_value: ConvertToLinearLight
    ) -> None:
        project = parse_project(OM_SAMPLES_DIR / f"{sample_name}.aep")
        om = project.render_queue.items[0].output_modules[0]
        assert om.settings["Convert to Linear Light"] == expected_value


class TestCompLinking:
    """Tests for render queue item composition linking."""

    def test_comp_name_matches(self) -> None:
        expected = load_expected(SAMPLES_DIR, "render_settings")
        project = parse_project(SAMPLES_DIR / "render_settings.aep")
        rqi = get_rqi(project, "base")
        exp_rqi = next(
            item
            for item in expected["renderQueue"]["items"]
            if item["compName"] == "base"
        )
        assert rqi.comp_name == exp_rqi["compName"]

    def test_2_rqitems_comp_linking(self) -> None:
        expected = load_expected(SAMPLES_DIR, "2_rqitems")
        project = parse_project(SAMPLES_DIR / "2_rqitems.aep")
        assert len(project.render_queue.items) == 2
        for i, rqi in enumerate(project.render_queue.items):
            exp_name = expected["renderQueue"]["items"][i]["compName"]
            assert rqi.comp_name == exp_name


class TestRenderQueueItemAttributes:
    """Tests for render queue item attributes."""

    def test_render_unchecked(self) -> None:
        expected = load_expected(SAMPLES_DIR, "render_unchecked")
        project = parse_project(SAMPLES_DIR / "render_unchecked.aep")
        rqi = project.render_queue.items[0]
        exp_rqi = expected["renderQueue"]["items"][0]
        assert rqi.render is False
        assert exp_rqi["render"] is False

    def test_comment(self) -> None:
        project = parse_project(SAMPLES_DIR / "comment_aaaaa.aep")
        rqi = project.render_queue.items[0]
        assert rqi.comment == "aaaaa"


class TestSkipFrames:
    """Tests for skip_frames calculation from frame rate ratio."""

    @pytest.mark.skip(
        reason="FIXME: Could not find parameter in UI and jsx"
        " script does not set this properly"
    )
    @pytest.mark.parametrize("n", [0, 1, 2, 3])
    def test_skip_frames(self, n: int) -> None:
        sample_name = f"skip_frames_{n}"
        expected = load_expected(SAMPLES_DIR, "skip_frames")
        project = parse_project(SAMPLES_DIR / "skip_frames.aep")
        rqi = get_rqi(project, sample_name)
        exp_rqi = next(
            item
            for item in expected["renderQueue"]["items"]
            if item["compName"] == sample_name
        )
        assert rqi.skip_frames == exp_rqi["skipFrames"] == n


class TestOutputModuleSettings:
    """Tests for output module settings values."""

    @pytest.mark.parametrize(
        "sample_name, expected_value",
        [
            ("starting_0", 0),
            ("starting_101", 101),
            ("starting_9999999", 9999999),
        ],
    )
    def test_starting_number(self, sample_name: str, expected_value: int) -> None:
        expected = load_expected(SAMPLES_DIR, sample_name)
        project = parse_project(SAMPLES_DIR / f"{sample_name}.aep")
        om = project.render_queue.items[0].output_modules[0]
        exp_om = expected["renderQueue"]["items"][0]["outputModules"][0]
        assert om.settings["Starting #"] == exp_om["settings"]["Starting #"]
        assert om.settings["Starting #"] == expected_value

    @pytest.mark.parametrize(
        "sample_name, expected_value",
        [
            ("use_comp_frame_number_off", False),
            ("use_comp_frame_number_on", True),
        ],
    )
    def test_use_comp_frame_number(
        self, sample_name: str, expected_value: bool
    ) -> None:
        expected = load_expected(SAMPLES_DIR, sample_name)
        project = parse_project(SAMPLES_DIR / f"{sample_name}.aep")
        om = project.render_queue.items[0].output_modules[0]
        exp_om = expected["renderQueue"]["items"][0]["outputModules"][0]
        assert om.settings["Use Comp Frame Number"] is expected_value
        assert exp_om["settings"]["Use Comp Frame Number"] is expected_value


class TestResolveOutputFilename:
    """Unit tests for resolve_output_filename()."""

    def test_empty_template(self) -> str:
        assert resolve_output_filename("") == ""

    @pytest.mark.parametrize(
        "template, kwargs, expected",
        [
            ("[projectName]", {"project_name": "MyProject"}, "MyProject"),
            ("[compName]", {"comp_name": "Comp 1"}, "Comp 1"),
            (
                "[renderSettingsName]",
                {"render_settings_name": "Best Settings"},
                "Best Settings",
            ),
            ("[outputModuleName]", {"output_module_name": "Lossless"}, "Lossless"),
            ("[width]", {"width": 1920}, "1920"),
            ("[height]", {"height": 1080}, "1080"),
            ("[frameRate]", {"frame_rate": 30.0}, "30"),
            ("[frameRate]", {"frame_rate": 29.97}, "29.97"),
            ("[compressor]", {"compressor": "H.264"}, "H.264"),
            ("[COMPNAME]", {"comp_name": "MyComp"}, "MyComp"),
        ],
    )
    def test_single_token(
        self, template: str, kwargs: dict[str, object], expected: str
    ) -> None:
        assert resolve_output_filename(template, **kwargs) == expected

    def test_aspect_ratio(self) -> None:
        result = resolve_output_filename("[aspectRatio]", width=1920, height=1080)
        assert result == "16x9"

    @pytest.mark.parametrize(
        "channels, expected",
        [
            (OutputChannels.RGB, "RGB"),
            (OutputChannels.RGBA, "RGBA"),
            (OutputChannels.ALPHA, "Alpha"),
        ],
    )
    def test_channels(self, channels: OutputChannels, expected: str) -> None:
        assert resolve_output_filename("[channels]", channels=channels) == expected

    @pytest.mark.parametrize(
        "depth, expected",
        [
            (8, "8bit"),
            (16, "16bit"),
            (32, "32bit"),
        ],
    )
    def test_project_color_depth(self, depth: int, expected: str) -> None:
        assert (
            resolve_output_filename("[projectColorDepth]", project_color_depth=depth)
            == expected
        )

    @pytest.mark.parametrize(
        "color_depth, expected",
        [
            (OutputColorDepth.MILLIONS_OF_COLORS, "Millions"),
            (OutputColorDepth.MILLIONS_OF_COLORS_PLUS, "Millions+"),
            (OutputColorDepth.TRILLIONS_OF_COLORS, "Trillions"),
            (OutputColorDepth.TRILLIONS_OF_COLORS_PLUS, "Trillions+"),
            (OutputColorDepth.FLOATING_POINT, "Floating Point"),
            (OutputColorDepth.FLOATING_POINT_PLUS, "Floating Point+"),
        ],
    )
    def test_output_color_depth(
        self, color_depth: OutputColorDepth, expected: str
    ) -> None:
        assert (
            resolve_output_filename(
                "[outputColorDepth]", output_color_depth=color_depth
            )
            == expected
        )

    def test_file_extension(self) -> None:
        result = resolve_output_filename(
            "[compName].[fileExtension]", comp_name="MyComp", file_extension="mp4"
        )
        assert result == "MyComp.mp4"

    def test_combined_template(self) -> None:
        result = resolve_output_filename(
            "[projectName]_[compName]_[width]x[height].[fileExtension]",
            project_name="Proj",
            comp_name="Comp1",
            width=1920,
            height=1080,
            file_extension="mov",
        )
        assert result == "Proj_Comp1_1920x1080.mov"

    @pytest.mark.parametrize(
        "template, kwargs, expected",
        [
            ("[startTimecode]", {"start_time": 0.0, "frame_rate": 24.0}, "0-00-00-00"),
            ("[endTimecode]", {"end_time": 10.0, "frame_rate": 24.0}, "0-00-10-00"),
            (
                "[durationTimecode]",
                {"duration_time": 5.0, "frame_rate": 24.0},
                "0-00-05-00",
            ),
        ],
    )
    def test_timecode(
        self, template: str, kwargs: dict[str, object], expected: str
    ) -> None:
        assert resolve_output_filename(template, **kwargs) == expected

    def test_project_folder_empty(self) -> None:
        result = resolve_output_filename(
            "[projectFolder][compName]", comp_name="MyComp"
        )
        assert result == "MyComp"


OCS_SAMPLES_DIR = (
    Path(__file__).parent.parent
    / "samples"
    / "models"
    / "output_module"
    / "output_color_space"
)


class TestOutputColorSpace:
    """Tests for OutputModule.output_color_space parsing."""

    @pytest.mark.parametrize(
        "sample_name, expected_value",
        [
            ("srgb", "sRGB IEC61966-2.1"),
            ("adobe_rgb", "Adobe RGB (1998)"),
            ("acescg", "ACEScg ACES Working Space AMPAS S-2014-004"),
            ("acescct", "ACEScct"),
            (
                "aces_2065-1",
                "ACES Academy Color Encoding Specification SMPTE ST 2065-1",
            ),
            ("prophoto_rgb", "ProPhoto RGB"),
            ("cie_rgb", "CIE RGB"),
            ("colormatch_rgb", "ColorMatch RGB"),
            ("apple_rgb", "Apple RGB"),
            ("image_p3", "image P3"),
            ("arri_logc3_800", "ARRI LogC3 Wide Color Gamut - EI 800"),
            ("canon_cinema_clog2", "Canon Cinema CLog2"),
            ("arriflex_daylight", "ARRIFLEX D-20 Daylight Log (by Adobe)"),
        ],
    )
    def test_output_color_space(self, sample_name: str, expected_value: str) -> None:
        project = parse_project(OCS_SAMPLES_DIR / f"{sample_name}.aep")
        om = project.render_queue.items[0].output_modules[0]
        assert om.settings["Output Color Space"] == expected_value

    def test_output_color_space_working(self) -> None:
        """Working Color Space should resolve to the project's working space."""
        project = parse_project(OCS_SAMPLES_DIR / "working_color_space.aep")
        om = project.render_queue.items[0].output_modules[0]
        assert om.settings["Output Color Space"] == project.working_space


class TestRoundtripLogType:
    """Roundtrip tests for RenderQueueItem.log_type."""

    def test_modify_log_type(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.log_type = LogType.ERRORS_AND_PER_FRAME_INFO

        out = tmp_path / "modified_log_type.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.log_type == LogType.ERRORS_AND_PER_FRAME_INFO

    def test_log_type_validation_rejects_invalid(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(ValueError, match="Invalid value"):
            rqi.log_type = 9999


class TestRoundtripQueueItemNotify:
    """Roundtrip tests for RenderQueueItem.queue_item_notify."""

    def test_modify_queue_item_notify(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        original = rqi.queue_item_notify
        rqi.queue_item_notify = not original

        out = tmp_path / "modified_notify.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.queue_item_notify is (not original)


class TestRoundtripStatus:
    """Roundtrip tests for RenderQueueItem.status."""

    def test_set_status_directly(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.status = RQItemStatus.UNQUEUED

        out = tmp_path / "modified_status.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.status == RQItemStatus.UNQUEUED

    def test_modify_status_via_render(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.render = False

        out = tmp_path / "modified_status.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.status == RQItemStatus.UNQUEUED
        assert rqi2.render is False

    def test_status_resets_start_time_and_elapsed(self, tmp_path: Path) -> None:
        """Setting render resets start_time and elapsed_seconds
        for QUEUED/UNQUEUED statuses."""
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        # Prime with non-zero values via underlying chunk body
        rqi._ldat.start_time = 1000000
        rqi._ldat.elapsed_seconds = 42

        rqi.status = RQItemStatus.QUEUED
        assert rqi.start_time is None
        assert rqi.elapsed_seconds == 0

        out = tmp_path / "status_reset.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.start_time is None
        assert rqi2.elapsed_seconds == 0
        assert rqi2.status == RQItemStatus.QUEUED


class TestRoundtripRender:
    """Roundtrip tests for RenderQueueItem.render setter."""

    def test_set_render_false(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.render = False

        out = tmp_path / "render_false.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.render is False
        assert rqi2.status == RQItemStatus.UNQUEUED

    def test_set_render_true(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.render = False
        rqi.render = True

        out = tmp_path / "render_true.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.render is True
        assert rqi2.status == RQItemStatus.QUEUED


class TestRoundtripName:
    """Roundtrip tests for RenderQueueItem.name (template name)."""

    def test_modify_name(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.name = "Custom Template"

        out = tmp_path / "modified_name.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.name == "Custom Template"


class TestRoundtripTimeSpan:
    """Roundtrip tests for time span frame fields."""

    def test_modify_time_span_start_frame(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.time_span_start_frame = 10

        out = tmp_path / "modified_ts_start.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.time_span_start_frame == 10

    def test_modify_time_span_duration_frames(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.time_span_duration_frames = 48

        out = tmp_path / "modified_ts_dur.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.time_span_duration_frames == 48


class TestRoundtripStartTime:
    """Tests for RenderQueueItem.start_time (read-only)."""

    def test_start_time_is_read_only(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(AttributeError, match="read-only"):
            rqi.start_time = datetime(2025, 6, 15, 12, 0, 0)

    def test_start_time_default_is_none(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        assert rqi.start_time is None


class TestReadOnlyFields:
    """Tests that read-only fields raise on write."""

    def test_elapsed_seconds_is_read_only(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(AttributeError, match="read-only"):
            rqi.elapsed_seconds = 999


class TestSetSetting:
    """Tests for RenderQueueItem.set_setting."""

    def test_set_enum_value(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.set_setting("Quality", RenderQuality.DRAFT)

        out = tmp_path / "quality_enum.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Quality"] == RenderQuality.DRAFT

    def test_set_int_value(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.set_setting("Quality", 1)  # DRAFT

        out = tmp_path / "quality_int.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Quality"] == RenderQuality.DRAFT

    def test_set_string_value(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.set_setting("Motion Blur", "On for Checked Layers")

        out = tmp_path / "mblur_str.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Motion Blur"] == MotionBlurSetting.ON_FOR_CHECKED_LAYERS

    def test_set_resolution(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.set_setting("Resolution", [2, 2])

        out = tmp_path / "resolution.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Resolution"] == [2, 2]

    def test_set_skip_existing_files(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.set_setting("Skip Existing Files", True)

        out = tmp_path / "skip_existing.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Skip Existing Files"] is True

    def test_set_frame_rate(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.set_setting("Use this frame rate", 30.0)

        out = tmp_path / "frame_rate.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Use this frame rate"] == pytest.approx(30.0)

    def test_unknown_key_raises(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(KeyError, match="Unknown setting"):
            rqi.set_setting("Nonexistent", 42)

    def test_read_only_key_raises(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(AttributeError, match="read-only"):
            rqi.set_setting("Use comp's frame rate", 30.0)

    def test_invalid_enum_int_raises(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(ValueError, match="Invalid int value"):
            rqi.set_setting("Quality", 9999)

    def test_invalid_enum_str_raises(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(ValueError, match="Invalid string"):
            rqi.set_setting("Quality", "SuperHD")

    def test_invalid_type_raises(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(TypeError, match="Expected"):
            rqi.set_setting("Quality", [1, 2, 3])


class TestSetSettings:
    """Tests for RenderQueueItem.set_settings."""

    def test_set_multiple(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.set_settings(
            {
                "Quality": RenderQuality.DRAFT,
                "Resolution": [2, 2],
            }
        )

        out = tmp_path / "multi_settings.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Quality"] == RenderQuality.DRAFT
        assert rqi2.settings["Resolution"] == [2, 2]


class TestRoundtripComment:
    """Roundtrip tests for the comment property."""

    def test_modify_existing_comment(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "comment_aaaaa.aep").project
        rqi = project.render_queue.items[0]
        assert rqi.comment == "aaaaa"
        rqi.comment = "new comment"

        out = tmp_path / "comment_modified.aep"
        project.save(out)
        rqi2 = parse_aep(out).project.render_queue.items[0]
        assert rqi2.comment == "new comment"

    def test_create_comment_from_none(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "2_rqitems.aep").project
        items = project.render_queue.items
        assert len(items) == 2
        for rqi in items:
            assert rqi._rcom_utf8 is None
            assert rqi.comment == ""

        items[0].comment = "first comment"
        items[1].comment = "second comment"

        out = tmp_path / "comment_created.aep"
        project.save(out)
        items2 = parse_aep(out).project.render_queue.items
        assert items2[0].comment == "first comment"
        assert items2[1].comment == "second comment"


class TestRoundtripOutputModuleIncludeSourceXmp:
    """Roundtrip tests for OutputModule.include_source_xmp."""

    def test_modify_include_source_xmp(self, tmp_path: Path) -> None:
        project = parse_aep(OM_SAMPLES_DIR / "om_misc.aep").project
        rqi = get_rqi(project, "include_source_xmp_data_on")
        om = rqi.output_modules[0]
        assert om.include_source_xmp is True
        om.include_source_xmp = False

        out = tmp_path / "xmp_off.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "include_source_xmp_data_on")
        om2 = rqi2.output_modules[0]
        assert om2.include_source_xmp is False

    def test_enable_include_source_xmp(self, tmp_path: Path) -> None:
        project = parse_aep(OM_SAMPLES_DIR / "include_source_xmp_data_off.aep").project
        om = project.render_queue.items[0].output_modules[0]
        assert om.include_source_xmp is False
        om.include_source_xmp = True

        out = tmp_path / "xmp_on.aep"
        project.save(out)
        om2 = parse_aep(out).project.render_queue.items[0].output_modules[0]
        assert om2.include_source_xmp is True


class TestRoundtripOutputModulePostRenderAction:
    """Roundtrip tests for OutputModule.post_render_action."""

    def test_modify_post_render_action(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        om = rqi.output_modules[0]
        om.post_render_action = PostRenderAction.IMPORT

        out = tmp_path / "pra_import.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        om2 = rqi2.output_modules[0]
        assert om2.post_render_action == PostRenderAction.IMPORT

    def test_post_render_action_validation_rejects_invalid(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        om = rqi.output_modules[0]
        with pytest.raises(ValueError, match="Invalid value"):
            om.post_render_action = 9999


class TestRoundtripFileTemplate:
    """Roundtrip tests for OutputModule.file_template property."""

    def test_file_template_read(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        om = rqi.output_modules[0]
        assert om.file_template  # should be non-empty

    def test_file_template_roundtrip(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        om = rqi.output_modules[0]
        original = om.file_template
        assert original  # non-empty

        # Replace the filename portion with a custom template
        sep = "\\" if "\\" in original else "/"
        last_sep = original.rfind(sep)
        new_template = original[: last_sep + 1] + "custom_output.[fileExtension]"
        om.file_template = new_template

        out = tmp_path / "ft_roundtrip.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        om2 = rqi2.output_modules[0]
        assert om2.file_template == new_template


class TestRoundtripSkipFrames:
    """Roundtrip tests for RenderQueueItem.skip_frames setter."""

    def test_set_skip_frames(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "skip_frames.aep").project
        rqi = get_rqi(project, "skip_frames_0")
        assert rqi.skip_frames == 0
        rqi.skip_frames = 1

        out = tmp_path / "skip1.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "skip_frames_0")
        assert rqi2.skip_frames == 1

    def test_set_skip_frames_back_to_0(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "skip_frames.aep").project
        rqi = get_rqi(project, "skip_frames_1")
        assert rqi.skip_frames == 1
        rqi.skip_frames = 0

        out = tmp_path / "skip0.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "skip_frames_1")
        assert rqi2.skip_frames == 0


class TestRoundtripTimeSpanStart:
    """Roundtrip tests for RenderQueueItem.time_span_start setter."""

    def test_set_time_span_start(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "time_span.aep").project
        rqi = get_rqi(project, "time_span_custom_start_1s23f")
        rqi.time_span_start = 2.0

        out = tmp_path / "ts_start.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "time_span_custom_start_1s23f")
        assert rqi2.time_span_start == pytest.approx(2.0, abs=0.04)

    def test_set_time_span_start_switches_to_custom(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "time_span.aep").project
        rqi = get_rqi(project, "time_span_length_of_comp")
        rqi.time_span_start = 1.0

        out = tmp_path / "ts_custom.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "time_span_length_of_comp")
        assert rqi2.time_span_start == pytest.approx(1.0, abs=0.04)


class TestRoundtripTimeSpanDuration:
    """Roundtrip tests for RenderQueueItem.time_span_duration setter."""

    def test_set_time_span_duration(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "time_span.aep").project
        rqi = get_rqi(project, "time_span_custom_24s13f")
        rqi.time_span_duration = 5.0

        out = tmp_path / "ts_dur.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "time_span_custom_24s13f")
        assert rqi2.time_span_duration == pytest.approx(5.0, abs=0.04)


class TestRoundtripTimeSpanEnd:
    """Roundtrip tests for time_span_end and time_span_end_frame setters."""

    def test_set_time_span_end(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "time_span.aep").project
        rqi = get_rqi(project, "time_span_custom_start_1s23f")
        start = rqi.time_span_start
        rqi.time_span_end = start + 3.0

        out = tmp_path / "ts_end.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "time_span_custom_start_1s23f")
        assert rqi2.time_span_duration == pytest.approx(3.0, abs=0.04)
        assert rqi2.time_span_end == pytest.approx(start + 3.0, abs=0.04)

    def test_set_time_span_end_frame(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.time_span_start_frame = 5
        rqi.time_span_end_frame = 30

        out = tmp_path / "ts_end_frame.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.time_span_start_frame == 5
        assert rqi2.time_span_duration_frames == 25
        assert rqi2.time_span_end_frame == 30


class TestRoundtripSettingsResolution:
    """Roundtrip tests for Resolution via SettingsView dict access."""

    def test_asymmetric_resolution(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.settings["Resolution"] = [7, 3]

        out = tmp_path / "res_asymmetric.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Resolution"] == [7, 3]

    def test_resolution_full_to_custom_roundtrip(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "resolution.aep").project
        rqi = get_rqi(project, "resolution_custom_7x3")
        assert rqi.settings["Resolution"] == [7, 3]

        rqi.settings["Resolution"] = [1, 1]
        out = tmp_path / "res_full.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "resolution_custom_7x3")
        assert rqi2.settings["Resolution"] == [1, 1]

        # And back to a different custom value
        rqi2.settings["Resolution"] = [8, 3]
        out2 = tmp_path / "res_custom_again.aep"
        rqi2._project.save(out2)
        rqi3 = get_rqi(parse_aep(out2).project, "resolution_custom_7x3")
        assert rqi3.settings["Resolution"] == [8, 3]


class TestRoundtripSettingsFrameRate:
    """Roundtrip tests for Use this frame rate (integer+fractional split)."""

    def test_fractional_frame_rate_29_97(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.settings["Frame Rate"] = FrameRateSetting.USE_THIS_FRAME_RATE
        rqi.settings["Use this frame rate"] = 29.97

        out = tmp_path / "fr_29_97.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Frame Rate"] == FrameRateSetting.USE_THIS_FRAME_RATE
        assert rqi2.settings["Use this frame rate"] == pytest.approx(29.97, abs=0.01)

    def test_integer_frame_rate_24(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "frame_rate.aep").project
        rqi = get_rqi(project, "frame_rate_24")
        assert rqi.settings["Use this frame rate"] == pytest.approx(24.0)

        rqi.settings["Use this frame rate"] = 60.0
        out = tmp_path / "fr_60.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "frame_rate_24")
        assert rqi2.settings["Use this frame rate"] == pytest.approx(60.0)

    def test_existing_fractional_roundtrip(self, tmp_path: Path) -> None:
        """Parse and save 29.97 without modification preserves the value."""
        project = parse_aep(SAMPLES_DIR / "frame_rate.aep").project
        rqi = get_rqi(project, "frame_rate_29_97")
        original = rqi.settings["Use this frame rate"]
        assert original == pytest.approx(29.97, abs=0.01)

        out = tmp_path / "fr_29_97_unchanged.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "frame_rate_29_97")
        assert rqi2.settings["Use this frame rate"] == pytest.approx(
            original, abs=0.001
        )


class TestRoundtripSettingsMultiWrite:
    """Roundtrip tests for multiple settings writes with save/reparse."""

    def test_multiple_settings(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")

        rqi.settings["Quality"] = RenderQuality.DRAFT
        rqi.settings["Resolution"] = [3, 3]
        rqi.settings["Motion Blur"] = MotionBlurSetting.ON_FOR_CHECKED_LAYERS
        rqi.settings["Field Render"] = FieldRender.UPPER_FIELD_FIRST

        out = tmp_path / "batch_multi.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Quality"] == RenderQuality.DRAFT
        assert rqi2.settings["Resolution"] == [3, 3]
        assert rqi2.settings["Motion Blur"] == MotionBlurSetting.ON_FOR_CHECKED_LAYERS
        assert rqi2.settings["Field Render"] == FieldRender.UPPER_FIELD_FIRST

    def test_frame_rate_pair(self, tmp_path: Path) -> None:
        """Set the frame rate toggle and value together."""
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")

        rqi.settings["Frame Rate"] = FrameRateSetting.USE_THIS_FRAME_RATE
        rqi.settings["Use this frame rate"] = 23.976

        out = tmp_path / "batch_fr.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Frame Rate"] == FrameRateSetting.USE_THIS_FRAME_RATE
        assert rqi2.settings["Use this frame rate"] == pytest.approx(23.976, abs=0.01)


class TestRoundtripSettingsBulkAssign:
    """Roundtrip tests for bulk settings assignment via .settings setter."""

    def test_assign_settings_dict(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.settings = {
            "Quality": RenderQuality.WIREFRAME,
            "Resolution": [4, 4],
            "Skip Existing Files": True,
        }

        out = tmp_path / "bulk_assign.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Quality"] == RenderQuality.WIREFRAME
        assert rqi2.settings["Resolution"] == [4, 4]
        assert rqi2.settings["Skip Existing Files"] is True

    def test_assign_from_another_rqi(self, tmp_path: Path) -> None:
        """Copy settings from one RQI to another via .settings setter."""
        project = parse_aep(SAMPLES_DIR / "2_rqitems.aep").project
        items = project.render_queue.items
        assert len(items) == 2

        items[0].settings["Quality"] = RenderQuality.DRAFT
        items[0].settings["Resolution"] = [2, 2]
        items[1].settings = dict(items[0].settings)

        out = tmp_path / "copy_settings.aep"
        project.save(out)
        items2 = parse_aep(out).project.render_queue.items
        assert items2[1].settings["Quality"] == RenderQuality.DRAFT
        assert items2[1].settings["Resolution"] == [2, 2]


class TestRoundtripSettingsReadOnly:
    """Tests that read-only settings raise on dict-style write."""

    def test_time_span_start_writable(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        # Time Span Start is now writable - verify no error
        rqi.settings["Time Span Start"] = 1.0

    def test_time_span_duration_writable(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        # Time Span Duration is now writable - verify no error
        rqi.settings["Time Span Duration"] = 5.0

    def test_comps_frame_rate_read_only(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(AttributeError, match="read-only"):
            rqi.settings["Use comp's frame rate"] = 30.0

    def test_unknown_key_via_dict_raises(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(KeyError):
            rqi.settings["Nonexistent"]
        with pytest.raises(KeyError, match="Unknown setting"):
            rqi.settings["Nonexistent"] = 42


class TestRoundtripOutputModuleResize:
    """Roundtrip tests for OutputModule Resize to (2-field getter/setter)."""

    def test_set_resize_to(self, tmp_path: Path) -> None:
        project = parse_aep(OM_SAMPLES_DIR / "resize_custom_960x540.aep").project
        om = project.render_queue.items[0].output_modules[0]
        assert om.settings["Resize to"] == [960, 540]

        om.settings["Resize to"] = [1280, 720]
        out = tmp_path / "resize_720p.aep"
        project.save(out)
        om2 = parse_aep(out).project.render_queue.items[0].output_modules[0]
        assert om2.settings["Resize to"] == [1280, 720]

    def test_resize_roundtrip_back(self, tmp_path: Path) -> None:
        project = parse_aep(OM_SAMPLES_DIR / "resize_custom_960x540.aep").project
        om = project.render_queue.items[0].output_modules[0]
        om.settings["Resize to"] = [3840, 2160]

        out = tmp_path / "resize_4k.aep"
        project.save(out)
        om2 = parse_aep(out).project.render_queue.items[0].output_modules[0]
        assert om2.settings["Resize to"] == [3840, 2160]

        om2.settings["Resize to"] = [640, 480]
        out2 = tmp_path / "resize_vga.aep"
        om2._project.save(out2)
        om3 = parse_aep(out2).project.render_queue.items[0].output_modules[0]
        assert om3.settings["Resize to"] == [640, 480]


class TestRoundtripOutputModuleCrop:
    """Roundtrip tests for OutputModule crop settings."""

    def test_set_all_crop_values(self, tmp_path: Path) -> None:
        project = parse_aep(OM_SAMPLES_DIR / "om_crop.aep").project
        rqi = get_rqi(project, "crop_checked")
        om = rqi.output_modules[0]

        om.settings["Crop Top"] = 20
        om.settings["Crop Left"] = 30
        om.settings["Crop Bottom"] = 40
        om.settings["Crop Right"] = 50

        out = tmp_path / "crop_all.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "crop_checked")
        om2 = rqi2.output_modules[0]
        assert om2.settings["Crop Top"] == 20
        assert om2.settings["Crop Left"] == 30
        assert om2.settings["Crop Bottom"] == 40
        assert om2.settings["Crop Right"] == 50

    def test_toggle_crop_and_set_values(self, tmp_path: Path) -> None:
        project = parse_aep(OM_SAMPLES_DIR / "crop_unchecked.aep").project
        om = project.render_queue.items[0].output_modules[0]
        assert om.settings["Crop"] is False

        om.settings["Crop"] = True
        om.settings["Crop Top"] = 10
        om.settings["Crop Bottom"] = 10

        out = tmp_path / "crop_enabled.aep"
        project.save(out)
        om2 = parse_aep(out).project.render_queue.items[0].output_modules[0]
        assert om2.settings["Crop"] is True
        assert om2.settings["Crop Top"] == 10
        assert om2.settings["Crop Bottom"] == 10


class TestRoundtripOutputModuleSettings:
    """Roundtrip tests for various OutputModule settings via dict access."""

    def test_set_resize_quality(self, tmp_path: Path) -> None:
        project = parse_aep(OM_SAMPLES_DIR / "om_resize.aep").project
        rqi = get_rqi(project, "resize_quality_low")
        om = rqi.output_modules[0]
        assert om.settings["Resize Quality"] == ResizeQuality.LOW

        om.settings["Resize Quality"] = ResizeQuality.HIGH
        out = tmp_path / "rq_high.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "resize_quality_low")
        om2 = rqi2.output_modules[0]
        assert om2.settings["Resize Quality"] == ResizeQuality.HIGH

    def test_read_only_om_settings(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        om = rqi.output_modules[0]
        with pytest.raises(AttributeError, match="read-only"):
            om.settings["Output File Info"] = {}
        with pytest.raises(AttributeError, match="read-only"):
            om.settings["Output Color Space"] = "sRGB"

    def test_om_settings_contain_required_keys(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        om = rqi.output_modules[0]
        settings = om.settings
        assert "Channels" in settings
        assert "Depth" in settings
        assert "Crop" in settings
        assert "Resize" in settings
        assert "Format" in settings
        assert "Output File Info" in settings

    def test_time_span_via_settings(self, tmp_path: Path) -> None:
        """Time Span key in RQI settings roundtrips correctly."""
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.settings["Time Span"] = TimeSpanSource.WORK_AREA_ONLY

        out = tmp_path / "ts_work_area.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Time Span"] == TimeSpanSource.WORK_AREA_ONLY


class TestGetSettings:
    """Tests for RenderQueueItem.get_settings/get_setting and OutputModule.get_settings/get_setting."""

    def test_rqi_get_settings_string(self) -> None:
        """get_settings(STRING) returns all string values."""
        project = parse_project(SAMPLES_DIR / "render_settings.aep")
        rqi = get_rqi(project, "base")
        result = rqi.get_settings(GetSettingsFormat.STRING)
        assert isinstance(result, dict)
        assert all(isinstance(v, str) for v in result.values())

    def test_rqi_get_settings_number(self) -> None:
        """get_settings(NUMBER) returns numeric values."""
        project = parse_project(SAMPLES_DIR / "render_settings.aep")
        rqi = get_rqi(project, "base")
        result = rqi.get_settings(GetSettingsFormat.NUMBER)
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_rqi_get_settings_default_is_string(self) -> None:
        """get_settings() defaults to STRING format."""
        project = parse_project(SAMPLES_DIR / "render_settings.aep")
        rqi = get_rqi(project, "base")
        default_result = rqi.get_settings()
        string_result = rqi.get_settings(GetSettingsFormat.STRING)
        assert default_result == string_result

    def test_rqi_get_setting_string(self) -> None:
        """get_setting returns a single string value."""
        project = parse_project(SAMPLES_DIR / "render_settings.aep")
        rqi = get_rqi(project, "base")
        result = rqi.get_setting("Quality")
        assert isinstance(result, str)

    def test_rqi_get_setting_number(self) -> None:
        """get_setting with NUMBER format returns the numeric value."""
        project = parse_project(SAMPLES_DIR / "render_settings.aep")
        rqi = get_rqi(project, "base")
        result = rqi.get_setting("Quality", GetSettingsFormat.NUMBER)
        assert isinstance(result, (int, float))

    def test_rqi_get_setting_invalid_key(self) -> None:
        """get_setting with unknown key raises KeyError."""
        project = parse_project(SAMPLES_DIR / "render_settings.aep")
        rqi = get_rqi(project, "base")
        with pytest.raises(KeyError):
            rqi.get_setting("NonExistentKey12345")

    def test_rqi_get_settings_invalid_format(self) -> None:
        """get_settings with invalid format raises ValueError."""
        project = parse_project(SAMPLES_DIR / "render_settings.aep")
        rqi = get_rqi(project, "base")
        with pytest.raises(ValueError):
            rqi.get_settings(9999)  # type: ignore[arg-type]

    def test_om_get_settings_string(self) -> None:
        """get_settings(STRING) returns string values (except nested dicts)."""
        project = parse_project(SAMPLES_DIR / "render_settings.aep")
        rqi = get_rqi(project, "base")
        om = rqi.output_modules[0]
        result = om.get_settings(GetSettingsFormat.STRING)
        assert isinstance(result, dict)
        # All values are strings except 'Output File Info' which is a dict
        for key, val in result.items():
            if key != "Output File Info":
                assert isinstance(val, str), f"{key} is {type(val)}, expected str"

    def test_om_get_settings_number(self) -> None:
        """OutputModule.get_settings(NUMBER) returns numeric values."""
        project = parse_project(SAMPLES_DIR / "render_settings.aep")
        rqi = get_rqi(project, "base")
        om = rqi.output_modules[0]
        result = om.get_settings(GetSettingsFormat.NUMBER)
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_om_get_setting_string(self) -> None:
        """OutputModule.get_setting returns a single string value."""
        project = parse_project(SAMPLES_DIR / "render_settings.aep")
        rqi = get_rqi(project, "base")
        om = rqi.output_modules[0]
        result = om.get_setting("Channels")
        assert isinstance(result, str)

    def test_om_get_setting_number(self) -> None:
        """OutputModule.get_setting with NUMBER format."""
        project = parse_project(SAMPLES_DIR / "render_settings.aep")
        rqi = get_rqi(project, "base")
        om = rqi.output_modules[0]
        result = om.get_setting("Channels", GetSettingsFormat.NUMBER)
        assert isinstance(result, (int, float))

    def test_om_get_setting_invalid_key(self) -> None:
        """OutputModule.get_setting with unknown key raises KeyError."""
        project = parse_project(SAMPLES_DIR / "render_settings.aep")
        rqi = get_rqi(project, "base")
        om = rqi.output_modules[0]
        with pytest.raises(KeyError):
            om.get_setting("NonExistentKey12345")

    def test_om_get_settings_invalid_format(self) -> None:
        """OutputModule.get_settings with invalid format raises ValueError."""
        project = parse_project(SAMPLES_DIR / "render_settings.aep")
        rqi = get_rqi(project, "base")
        om = rqi.output_modules[0]
        with pytest.raises(ValueError):
            om.get_settings(9999)  # type: ignore[arg-type]
