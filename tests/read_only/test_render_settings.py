"""Tests for render queue settings parsing."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import parse_project

from py_aep.enums import PostRenderAction

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "renderqueue"
OM_SAMPLES_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "output_module"
)


class TestRenderSettings:
    """Tests for render settings parsing as dict."""

    def test_base_settings(self) -> None:
        """Test base render settings template."""
        project = parse_project(SAMPLES_DIR / "base.aep")
        rs = project.render_queue.items[0].settings

        assert rs is not None
        assert rs["Quality"] == 2  # Best
        assert rs["Resolution"] == [1, 1]  # Full
        assert rs["Frame Rate"] == 0
        assert rs["3:2 Pulldown"] == 0  # Off

    def test_quality_draft(self) -> None:
        """Test draft quality setting."""
        project = parse_project(SAMPLES_DIR / "custom_quality_draft.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Quality"] == 1  # Draft

    def test_quality_wireframe(self) -> None:
        """Test wireframe quality setting."""
        project = parse_project(SAMPLES_DIR / "custom_quality_wireframe.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Quality"] == 0  # Wireframe

    def test_resolution_half(self) -> None:
        """Test half resolution setting."""
        project = parse_project(SAMPLES_DIR / "custom_resolution_half.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Resolution"] == [2, 2]  # Half

    def test_resolution_third(self) -> None:
        """Test third resolution setting."""
        project = parse_project(SAMPLES_DIR / "custom_resolution_third.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Resolution"] == [3, 3]  # Third

    def test_resolution_quarter(self) -> None:
        """Test quarter resolution setting."""
        project = parse_project(SAMPLES_DIR / "custom_resolution_quarter.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Resolution"] == [4, 4]  # Quarter

    def test_resolution_custom(self) -> None:
        """Test custom resolution setting."""
        project = parse_project(
            SAMPLES_DIR / "custom_resolution_custom_7_horizontal_3_vertical.aep"
        )
        rs = project.render_queue.items[0].settings

        assert rs["Resolution"] == [7, 3]  # Custom 7x3

    def test_color_depth_8bit(self) -> None:
        """Test 8-bit color depth setting."""
        project = parse_project(SAMPLES_DIR / "color_depth_8.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Color Depth"] == 0  # 8-bit

    def test_color_depth_16bit(self) -> None:
        """Test 16-bit color depth setting."""
        project = parse_project(SAMPLES_DIR / "color_depth_16.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Color Depth"] == 1  # 16-bit

    def test_color_depth_32bit(self) -> None:
        """Test 32-bit color depth setting."""
        project = parse_project(SAMPLES_DIR / "color_depth_32.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Color Depth"] == 2  # 32-bit

    def test_field_render_lower_first(self) -> None:
        """Test lower field first setting."""
        project = parse_project(SAMPLES_DIR / "field_render_lower_field_first.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Field Render"] == 2  # Lower Field First

    def test_field_render_upper_first(self) -> None:
        """Test upper field first setting."""
        project = parse_project(SAMPLES_DIR / "field_render_upper_field_first.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Field Render"] == 1  # Upper Field First

    def test_pulldown_wssww(self) -> None:
        """Test 3:2 pulldown WSSWW setting."""
        project = parse_project(
            SAMPLES_DIR / "field_render_upper_field_first_pulldown_wssww.aep"
        )
        rs = project.render_queue.items[0].settings

        assert rs["3:2 Pulldown"] == 1  # WSSWW

    def test_pulldown_sswww(self) -> None:
        """Test 3:2 pulldown SSWWW setting."""
        project = parse_project(
            SAMPLES_DIR / "field_render_upper_field_first_pulldown_sswww.aep"
        )
        rs = project.render_queue.items[0].settings

        assert rs["3:2 Pulldown"] == 2  # SSWWW

    def test_pulldown_swwws(self) -> None:
        """Test 3:2 pulldown SWWWS setting."""
        project = parse_project(
            SAMPLES_DIR / "field_render_upper_field_first_pulldown_swwws.aep"
        )
        rs = project.render_queue.items[0].settings

        assert rs["3:2 Pulldown"] == 3  # SWWWS

    def test_pulldown_wwwss(self) -> None:
        """Test 3:2 pulldown WWWSS setting."""
        project = parse_project(
            SAMPLES_DIR / "field_render_upper_field_first_pulldown_wwwss.aep"
        )
        rs = project.render_queue.items[0].settings

        assert rs["3:2 Pulldown"] == 4  # WWWSS

    def test_pulldown_wwssw(self) -> None:
        """Test 3:2 pulldown WWSSW setting."""
        project = parse_project(
            SAMPLES_DIR / "field_render_upper_field_first_pulldown_wwssw.aep"
        )
        rs = project.render_queue.items[0].settings

        assert rs["3:2 Pulldown"] == 5  # WWSSW

    def test_frame_blending_current(self) -> None:
        """Test frame blending current settings."""
        project = parse_project(SAMPLES_DIR / "frame_blending_current.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Frame Blending"] == 2  # Current Settings

    def test_frame_blending_off(self) -> None:
        """Test frame blending off for all layers."""
        project = parse_project(SAMPLES_DIR / "frame_blending_off_for_all_layers.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Frame Blending"] == 0  # Off for All Layers

    def test_motion_blur_current(self) -> None:
        """Test motion blur current settings."""
        project = parse_project(SAMPLES_DIR / "motion_blur_current.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Motion Blur"] == 2  # Current Settings

    def test_motion_blur_off(self) -> None:
        """Test motion blur off for all layers."""
        project = parse_project(SAMPLES_DIR / "motion_blur_off_for_all_layers.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Motion Blur"] == 0  # Off for All Layers

    def test_use_this_frame_rate_24(self) -> None:
        """Test custom frame rate 24fps."""
        project = parse_project(SAMPLES_DIR / "use_this_frame_rate_24.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Frame Rate"]
        assert rs["Use this frame rate"] == 24.0

    def test_use_this_frame_rate_30(self) -> None:
        """Test custom frame rate 30fps."""
        project = parse_project(SAMPLES_DIR / "use_this_frame_rate_30.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Frame Rate"]
        assert rs["Use this frame rate"] == 30.0

    def test_proxy_use_all_proxies(self) -> None:
        """Test use all proxies setting."""
        project = parse_project(SAMPLES_DIR / "custom_proxy_use_use_all_proxies.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Proxy Use"] == 1  # Use All Proxies

    def test_proxy_use_comp_proxies_only(self) -> None:
        """Test use comp proxies only setting."""
        project = parse_project(
            SAMPLES_DIR / "custom_proxy_use_use_comp_proxies_only.aep"
        )
        rs = project.render_queue.items[0].settings

        assert rs["Proxy Use"] == 3  # Use Comp Proxies Only

    def test_effects_all_on(self) -> None:
        """Test effects all on setting."""
        project = parse_project(SAMPLES_DIR / "custom_effects_all_on.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Effects"] == 1  # All On

    def test_effects_all_off(self) -> None:
        """Test effects all off setting."""
        project = parse_project(SAMPLES_DIR / "custom_effects_all_off.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Effects"] == 0  # All Off

    def test_solo_switches_all_off(self) -> None:
        """Test solo switches all off setting."""
        project = parse_project(SAMPLES_DIR / "custom_solo_switches_all_off.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Solo Switches"] == 0  # All Off

    def test_guide_layers_current(self) -> None:
        """Test guide layers current settings."""
        project = parse_project(SAMPLES_DIR / "guide_layers_current.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Guide Layers"] == 2  # Current Settings

    def test_disk_cache_read_only(self) -> None:
        """Test disk cache read only (default)."""
        project = parse_project(SAMPLES_DIR / "custom.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Disk Cache"] == 0  # Read Only

    def test_disk_cache_current_settings(self) -> None:
        """Test disk cache current settings."""
        project = parse_project(SAMPLES_DIR / "custom_disk_cache_current.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Disk Cache"] == 2  # Current Settings

    def test_time_span_length_of_comp(self) -> None:
        """Test time span length of comp."""
        project = parse_project(SAMPLES_DIR / "time_span_length_of_comp.aep")
        rs = project.render_queue.items[0].settings

        assert rs["Time Span"] == 0  # Length of Comp

    def test_time_span_start_zero(self) -> None:
        """Test time span start of zero."""
        project = parse_project(
            SAMPLES_DIR / "time_span_custom_start_00_duration_24s13f.aep"
        )
        rs = project.render_queue.items[0].settings

        assert rs["Time Span Start"] == 0.0

    def test_time_span_start_custom(self) -> None:
        """Test custom time span start (1s 23f at 24fps)."""
        project = parse_project(
            SAMPLES_DIR / "time_span_custom_start_01s_23f_duration_24s13f.aep"
        )
        rs = project.render_queue.items[0].settings

        # 1s + 23 frames at 24fps = 1 + 23/24 = 1.9583... seconds
        assert abs(rs["Time Span Start"] - (1 + 23 / 24)) < 0.0001

    def test_time_span_duration(self) -> None:
        """Test time span duration (24s 13f at 24fps)."""
        project = parse_project(
            SAMPLES_DIR / "time_span_custom_start_00_duration_24s13f.aep"
        )
        rs = project.render_queue.items[0].settings

        # 24s + 13 frames at 24fps = 24 + 13/24 = 24.5416... seconds
        assert abs(rs["Time Span Duration"] - (24 + 13 / 24)) < 0.0001

    def test_time_span_duration_30s(self) -> None:
        """Test time span duration of 719 frames at 24fps."""
        project = parse_project(
            SAMPLES_DIR / "time_span_custom_start_01_duration_29.9583s.aep"
        )
        rs = project.render_queue.items[0].settings

        assert abs(rs["Time Span Duration"] - 29.9583333333333) < 0.0001


class TestOutputModuleSettings:
    """Tests for OutputModuleSettings parsing."""

    def test_base_output_module(self) -> None:
        """Test base output module settings."""
        project = parse_project(SAMPLES_DIR / "base.aep")
        om = project.render_queue.items[0].output_modules[0]

        assert om.settings is not None
        assert om.settings["Audio Channels"] == 2  # Stereo
        assert om.settings["Audio Bit Depth"] == 2  # 16-bit
        assert om.settings["Audio Sample Rate"] == 48000
        assert om.settings["Channels"] == 0  # RGB
        assert om.settings["Depth"] == 24  # Millions of Colors (8 bpc)
        assert om.settings["Format"] == 3  # H.264
        assert om.settings["Color"] == 1  # Premultiplied
        assert om.settings["Include Project Link"] is True
        assert om.settings["Lock Aspect Ratio"] is True
        assert om.settings["Resize"] is False
        assert om.settings["Resize Quality"] == 1  # High
        assert om.settings["Starting #"] == 0
        assert om.settings["Use Comp Frame Number"] is True

    @pytest.mark.parametrize(
        "filename, expected_output_audio",
        [
            ("audio_output_off.aep", 1),
            ("audio_output_on.aep", 2),
            ("audio_output_auto.aep", 3),
        ],
    )
    def test_audio_output(self, filename: str, expected_output_audio: int) -> None:
        """Test audio output settings."""
        project = parse_project(OM_SAMPLES_DIR / filename)
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Output Audio"] == expected_output_audio

    def test_audio_mono(self) -> None:
        """Test mono audio channel."""
        project = parse_project(OM_SAMPLES_DIR / "audio_mono.aep")
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Audio Channels"] == 1  # Mono

    def test_audio_8bit(self) -> None:
        """Test 8-bit audio depth."""
        project = parse_project(OM_SAMPLES_DIR / "audio_8bit.aep")
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Audio Bit Depth"] == 1  # 8-bit

    def test_audio_32bit(self) -> None:
        """Test 32-bit audio depth."""
        project = parse_project(OM_SAMPLES_DIR / "audio_32bit.aep")
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Audio Bit Depth"] == 4  # 32-bit

    @pytest.mark.parametrize(
        "filename, expected_rate",
        [
            ("audio_8000hz.aep", 8000),
            ("audio_16000hz.aep", 16000),
            ("audio_22050hz.aep", 22050),
            ("audio_32000hz.aep", 32000),
            ("audio_96000hz.aep", 96000),
        ],
    )
    def test_audio_sample_rate(self, filename: str, expected_rate: int) -> None:
        """Test audio sample rate parsing."""
        project = parse_project(OM_SAMPLES_DIR / filename)
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Audio Sample Rate"] == expected_rate

    @pytest.mark.parametrize(
        "filename, expected_channels",
        [
            ("channels_rgb.aep", 0),
            ("channels_rgba.aep", 1),
            ("channels_alpha.aep", 2),
        ],
    )
    def test_channels(self, filename: str, expected_channels: int) -> None:
        """Test output channels parsing."""
        project = parse_project(OM_SAMPLES_DIR / filename)
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Channels"] == expected_channels

    @pytest.mark.parametrize(
        "filename, expected_depth",
        [
            ("depth_millions.aep", 24),
            ("depth_millions+.aep", 32),
            ("depth_trillions.aep", 48),
            ("depth_trillions+.aep", 64),
            ("depth_floating.aep", 96),
            ("depth_floating+.aep", 128),
        ],
    )
    def test_depth(self, filename: str, expected_depth: int) -> None:
        """Test output color depth parsing."""
        project = parse_project(OM_SAMPLES_DIR / filename)
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Depth"] == expected_depth

    @pytest.mark.parametrize(
        "filename, expected_format",
        [
            ("format_aiff.aep", 0),
            ("format_avi.aep", 1),
            ("format_dpx_cineon_sequence.aep", 2),
            ("format_h264.aep", 3),
            ("format_iff_sequence.aep", 4),
            ("format_jpeg_sequence.aep", 5),
            ("format_mp3.aep", 6),
            ("format_openexr_sequence.aep", 7),
            ("format_png_sequence.aep", 8),
            ("format_photoshop_sequence.aep", 9),
            ("format_quicktime.aep", 10),
            ("format_radiance_sequence.aep", 11),
            ("format_sgi_sequence.aep", 12),
            ("format_tiff_sequence.aep", 13),
            ("format_targa_sequence.aep", 14),
            ("format_wav.aep", 15),
        ],
    )
    def test_format(self, filename: str, expected_format: int) -> None:
        """Test output format parsing."""
        project = parse_project(SAMPLES_DIR / filename)
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Format"] == expected_format

    def test_color_straight_unmatted(self) -> None:
        """Test straight (unmatted) color mode."""
        project = parse_project(OM_SAMPLES_DIR / "color_straight_unmatted.aep")
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Color"] == 0  # Straight (Unmatted)

    def test_include_project_link_off(self) -> None:
        """Test include project link is False when disabled."""
        project = parse_project(OM_SAMPLES_DIR / "include_project_link_off.aep")
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Include Project Link"] is False

    def test_include_project_link_on(self) -> None:
        """Test include project link is True when enabled."""
        project = parse_project(OM_SAMPLES_DIR / "include_project_link_on.aep")
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Include Project Link"] is True

    def test_use_region_of_interest_unchecked(self) -> None:
        """Test Use Region of Interest is False when unchecked."""
        project = parse_project(OM_SAMPLES_DIR / "crop_use_roi_unchecked.aep")
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Use Region of Interest"] is False

    def test_use_region_of_interest_checked(self) -> None:
        """Test Use Region of Interest is True when checked."""
        project = parse_project(OM_SAMPLES_DIR / "crop_use_roi_checked.aep")
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Use Region of Interest"] is True

    def test_lock_aspect_ratio_off(self) -> None:
        """Test Lock Aspect Ratio is False when disabled."""
        project = parse_project(SAMPLES_DIR / "lock_aspect_ratio_off.aep")
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Lock Aspect Ratio"] is False

    def test_lock_aspect_ratio_on(self) -> None:
        """Test Lock Aspect Ratio is True when enabled."""
        project = parse_project(SAMPLES_DIR / "lock_aspect_ratio_on.aep")
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Lock Aspect Ratio"] is True

    def test_resize_unchecked(self) -> None:
        """Test Resize is False when unchecked."""
        project = parse_project(OM_SAMPLES_DIR / "resize_unchecked.aep")
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Resize"] is False

    def test_resize_checked(self) -> None:
        """Test Resize is True when checked."""
        project = parse_project(OM_SAMPLES_DIR / "resize_checked.aep")
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Resize"] is True

    def test_resize_quality_low(self) -> None:
        """Test Resize Quality is 0 when set to low."""
        project = parse_project(OM_SAMPLES_DIR / "resize_quality_low.aep")
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Resize Quality"] == 0

    def test_resize_quality_high(self) -> None:
        """Test Resize Quality is 1 when set to high."""
        project = parse_project(OM_SAMPLES_DIR / "resize_quality_high.aep")
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Resize Quality"] == 1

    def test_resize_to_hd(self) -> None:
        """Test Resize to HD 1920x1080."""
        project = parse_project(OM_SAMPLES_DIR / "resize_hd_1920x1080_29.97_fps.aep")
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Resize to"] == [1920, 1080]

    def test_resize_to_dvcpro_hd(self) -> None:
        """Test Resize to DVCPRO HD 960x720."""
        project = parse_project(
            OM_SAMPLES_DIR / "resize_dvcpro_hd_960x720_1.33_23.976_fps.aep"
        )
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Resize to"] == [960, 720]

    def test_resize_to_custom(self) -> None:
        """Test Resize to custom 960x540."""
        project = parse_project(OM_SAMPLES_DIR / "resize_custom_960x540.aep")
        settings = project.render_queue.items[0].output_modules[0].settings

        assert settings["Resize to"] == [960, 540]

    def test_output_file_info_default(self) -> None:
        """Test Output File Info with default [compName].[fileExtension]."""
        project = parse_project(SAMPLES_DIR / "output_to_comp_and_frame_range.aep")
        info = (
            project.render_queue.items[0].output_modules[0].settings["Output File Info"]
        )

        assert info["File Template"] == "[compName].[fileExtension]"
        assert info["Subfolder Path"] == ""
        assert info["Base Path"] != ""
        assert info["Full Flat Path"] != ""
        assert info["File Name"] == "[compName].[fileExtension]"

    def test_output_file_info_comp_folder(self) -> None:
        """Test Output File Info with [compName] subfolder in base path."""
        project = parse_project(SAMPLES_DIR / "output_to_comp_folder_and_name.aep")
        info = (
            project.render_queue.items[0].output_modules[0].settings["Output File Info"]
        )

        assert "[compName]" in info["Base Path"]
        assert info["File Template"] == "[compName].[fileExtension]"
        assert info["File Name"] == "[compName].[fileExtension]"
        assert info["Subfolder Path"] == ""

    def test_output_file_info_custom_all_fields(self) -> None:
        """Test Output File Info with all available template tokens."""
        project = parse_project(SAMPLES_DIR / "output_to_custom_all_fields.aep")
        info = (
            project.render_queue.items[0].output_modules[0].settings["Output File Info"]
        )

        template = info["File Template"]
        assert "[projectFolder]" in template
        assert "[projectName]" in template
        assert "[compName]" in template
        assert "[width]" in template
        assert "[height]" in template
        assert "[fileExtension]" in template
        assert info["Base Path"] != ""
        assert info["Full Flat Path"].endswith(".[fileExtension]")

    def test_output_file_info_project_and_comp(self) -> None:
        """Test Output File Info with project and comp name template."""
        project = parse_project(SAMPLES_DIR / "output_to_project_and_comp_name.aep")
        info = (
            project.render_queue.items[0].output_modules[0].settings["Output File Info"]
        )

        assert info["File Template"] == ("[projectName]_[compName].[fileExtension]")

    def test_output_file_info_subfolder(self) -> None:
        """Test Output File Info with subfolder in file name template."""
        project = parse_project(SAMPLES_DIR / "save_in_subfolder_toto.aep")
        om = project.render_queue.items[0].output_modules[0]
        info = om.settings["Output File Info"]

        assert info["Subfolder Path"] == "toto"
        assert info["File Name"] == "Comp 1.[fileExtension]"
        assert info["File Template"] == "toto\\Comp 1.[fileExtension]"
        assert info["Base Path"] == "C:\\Users\\aurore.delaunay\\Downloads"
        assert info["Full Flat Path"] == (
            "C:\\Users\\aurore.delaunay\\Downloads\\toto\\Comp 1.[fileExtension]"
        )

    def test_video_output_on(self) -> None:
        """Test video output is enabled (default)."""
        project = parse_project(OM_SAMPLES_DIR / "custom_h264.aep")
        om = project.render_queue.items[0].output_modules[0]

        assert om.settings["Video Output"] is True

    def test_video_output_off(self) -> None:
        """Test video output is disabled."""
        project = parse_project(OM_SAMPLES_DIR / "custom_has_video_off.aep")
        om = project.render_queue.items[0].output_modules[0]

        assert om.settings["Video Output"] is False


class TestOutputModule:
    """Tests for OutputModule parsing."""

    def test_post_render_action_none(self) -> None:
        """Test post_render_action is NONE by default."""
        project = parse_project(SAMPLES_DIR / "base.aep")
        om = project.render_queue.items[0].output_modules[0]

        assert om.post_render_action == PostRenderAction.NONE

    def test_post_render_action_import(self) -> None:
        """Test post_render_action is IMPORT."""
        project = parse_project(SAMPLES_DIR / "post_render_import.aep")
        om = project.render_queue.items[0].output_modules[0]

        assert om.post_render_action == PostRenderAction.IMPORT

    def test_post_render_action_import_and_replace(self) -> None:
        """Test post_render_action is IMPORT_AND_REPLACE_USAGE."""
        project = parse_project(
            SAMPLES_DIR / "post_render_import_and_replace_this_comp.aep"
        )
        om = project.render_queue.items[0].output_modules[0]

        assert om.post_render_action == PostRenderAction.IMPORT_AND_REPLACE_USAGE

    def test_post_render_action_set_proxy(self) -> None:
        """Test post_render_action is SET_PROXY."""
        project = parse_project(SAMPLES_DIR / "post_render_set_proxy_this_comp.aep")
        om = project.render_queue.items[0].output_modules[0]

        assert om.post_render_action == PostRenderAction.SET_PROXY


class TestRenderQueueItem:
    """Tests for RenderQueueItem parsing."""

    def test_render_enabled(self) -> None:
        """Test render flag is True when item is queued."""
        project = parse_project(SAMPLES_DIR / "base.aep")
        item = project.render_queue.items[0]

        assert item.render is True

    def test_item_time_span_start(self) -> None:
        """Test RenderQueueItem.time_span_start property."""
        project = parse_project(
            SAMPLES_DIR / "time_span_custom_start_01s_23f_duration_24s13f.aep"
        )
        item = project.render_queue.items[0]

        assert abs(item.time_span_start - (1 + 23 / 24)) < 0.0001

    def test_item_time_span_duration(self) -> None:
        """Test RenderQueueItem.time_span_duration property."""
        project = parse_project(
            SAMPLES_DIR / "time_span_custom_start_01_duration_29.9583s.aep"
        )
        item = project.render_queue.items[0]

        assert abs(item.time_span_duration - 29.9583333333333) < 0.0001

    def test_default_comment(self) -> None:
        """Test RenderQueueItem.comment is None when no comment set."""
        project = parse_project(SAMPLES_DIR / "base.aep")
        item = project.render_queue.items[0]

        assert item.comment == ""
