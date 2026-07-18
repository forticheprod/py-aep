"""Tests for RenderQueue model parsing."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from conftest import get_rqi, load_expected, parse_project

from py_aep.enums import (
    ConvertToLinearLight,
    GetSettingsFormat,
)
from py_aep.models.renderqueue import OutputModule

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "renderqueue"
OM_SAMPLES_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "output_module"
)
BUGS_DIR = Path(__file__).parent.parent.parent / "samples" / "bugs"
AE_PREFS_DIR = os.getenv("AE_PREFS_DIR")
OCS_SAMPLES_DIR = (
    Path(__file__).parent.parent.parent
    / "samples"
    / "models"
    / "output_module"
    / "output_color_space"
)


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
        assert om.output_color_space == expected_value

    def test_output_color_space_working(self) -> None:
        """Working Color Space should resolve to the project's working space."""
        project = parse_project(OCS_SAMPLES_DIR / "working_color_space.aep")
        om = project.render_queue.items[0].output_modules[0]
        assert om.output_color_space == project.working_space


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
