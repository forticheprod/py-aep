"""Tests for Project model parsing."""

from __future__ import annotations

from pathlib import Path

from conftest import load_expected, parse_project

from py_aep import parse as parse_aep
from py_aep.enums import (
    BitsPerChannel,
    ColorManagementSystem,
    FeetFramesFilmType,
    FootageTimecodeDisplayStartType,
    FramesCountType,
    GpuAccelType,
    LutInterpolationMethod,
    TimeDisplayType,
)

SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "models" / "project"


class TestBitsPerChannel:
    """Tests for bitsPerChannel attribute."""

    def test_8bpc(self) -> None:
        expected = load_expected(SAMPLES_DIR, "bitsPerChannel_8")
        project = parse_project(SAMPLES_DIR / "bitsPerChannel_8.aep")
        assert expected["bitsPerChannel"] == 8
        assert project.bits_per_channel.value == expected["bitsPerChannel"]

    def test_16bpc(self) -> None:
        expected = load_expected(SAMPLES_DIR, "bitsPerChannel_16")
        project = parse_project(SAMPLES_DIR / "bitsPerChannel_16.aep")
        assert expected["bitsPerChannel"] == 16
        assert project.bits_per_channel.value == expected["bitsPerChannel"]

    def test_32bpc(self) -> None:
        expected = load_expected(SAMPLES_DIR, "bitsPerChannel_32")
        project = parse_project(SAMPLES_DIR / "bitsPerChannel_32.aep")
        assert expected["bitsPerChannel"] == 32
        assert project.bits_per_channel.value == expected["bitsPerChannel"]


class TestExpressionEngine:
    """Tests for expressionEngine attribute."""

    def test_javascript(self) -> None:
        expected = load_expected(SAMPLES_DIR, "expressionEngine_javascript")
        project = parse_project(SAMPLES_DIR / "expressionEngine_javascript.aep")
        assert expected["expressionEngine"] == "javascript-1.0"
        assert project.expression_engine == expected["expressionEngine"]


class TestDisplayStartFrame:
    """Tests for displayStartFrame attribute."""

    def test_displayStartFrame_1(self) -> None:
        expected = load_expected(SAMPLES_DIR, "displayStartFrame_1")
        project = parse_project(SAMPLES_DIR / "displayStartFrame_1.aep")
        assert expected["displayStartFrame"] == 1
        assert project.display_start_frame == expected["displayStartFrame"]


class TestFramesCountType:
    """Tests for framesCountType attribute."""

    def test_start0(self) -> None:
        load_expected(SAMPLES_DIR, "framesCountType_start0")
        project = parse_project(SAMPLES_DIR / "framesCountType_start0.aep")
        assert project.display_start_frame == 0


class TestWorkingGamma:
    """Tests for workingGamma attribute."""

    def test_workingGamma_2_4(self) -> None:
        project = parse_project(SAMPLES_DIR / "workingGamma_2.4.aep")
        assert project.working_gamma == 2.4

    def test_workingGamma_2_2(self) -> None:
        project = parse_project(SAMPLES_DIR / "workingGamma_2.2.aep")
        assert project.working_gamma == 2.2


class TestWorkingSpace:
    """Tests for workingSpace attribute."""

    def test_workingSpace_sRGB(self) -> None:
        expected = load_expected(SAMPLES_DIR, "workingSpace_sRGB")
        project = parse_project(SAMPLES_DIR / "workingSpace_sRGB.aep")
        assert expected["workingSpace"] == "sRGB IEC61966-2.1"
        assert project.working_space == expected["workingSpace"]


class TestDisplayColorSpace:
    """Tests for display_color_space attribute."""

    def test_none(self) -> None:
        project = parse_project(SAMPLES_DIR / "display_color_space_ACES_None.aep")
        assert project.display_color_space == "None"

    def test_srgb(self) -> None:
        project = parse_project(SAMPLES_DIR / "display_color_space_ACES_sRGB.aep")
        assert project.display_color_space == "ACES/sRGB"

    def test_dcdm(self) -> None:
        project = parse_project(SAMPLES_DIR / "display_color_space_ACES_DCDM.aep")
        assert project.display_color_space == "ACES/DCDM"


class TestAudioSampleRate:
    """Tests for audio_sample_rate attribute."""

    def test_96000(self) -> None:
        project = parse_project(SAMPLES_DIR / "Audio_sample_rate_96000.aep")
        assert project.audio_sample_rate == 96000.0

    def test_22050(self) -> None:
        project = parse_project(SAMPLES_DIR / "Audio_sample_rate_22050.aep")
        assert project.audio_sample_rate == 22050.0


class TestGpuAccelType:
    """Tests for gpu_accel_type attribute."""

    def test_cuda(self) -> None:
        expected = load_expected(
            SAMPLES_DIR,
            "gpuAccelType_mercury_gpu_acceleration_CUDA",
        )
        project = parse_project(
            SAMPLES_DIR / "gpuAccelType_mercury_gpu_acceleration_CUDA.aep"
        )
        assert expected["gpuAccelType"] == 1813
        assert project.gpu_accel_type.value == expected["gpuAccelType"]

    def test_software(self) -> None:
        expected = load_expected(SAMPLES_DIR, "gpuAccelType_mercury_software_only")
        project = parse_project(SAMPLES_DIR / "gpuAccelType_mercury_software_only.aep")
        assert expected["gpuAccelType"] == 1816
        assert project.gpu_accel_type.value == expected["gpuAccelType"]


class TestLinearBlending:
    """Tests for linearBlending attribute."""

    def test_linearBlending_false(self) -> None:
        project = parse_project(SAMPLES_DIR / "linearBlending_false.aep")
        assert not project.linear_blending

    def test_linearBlending_true(self) -> None:
        project = parse_project(SAMPLES_DIR / "linearBlending_true.aep")
        assert project.linear_blending


class TestTransparencyGridThumbnails:
    """Tests for transparencyGridThumbnails attribute."""

    def test_true(self) -> None:
        project = parse_project(SAMPLES_DIR / "transparencyGridThumbnails_true.aep")
        assert project.transparency_grid_thumbnails is True

    def test_false(self) -> None:
        project = parse_project(SAMPLES_DIR / "transparencyGridThumbnails_false.aep")
        assert project.transparency_grid_thumbnails is False


class TestColorManagement:
    """Tests for CC 2024+ color management attributes."""

    def test_colorManagementSystem_adobe(self) -> None:
        project = parse_project(SAMPLES_DIR / "colorManagementSystem_adobe.aep")
        assert project.color_management_system.name == "ADOBE"

    def test_colorManagementSystem_ocio(self) -> None:
        project = parse_project(SAMPLES_DIR / "colorManagementSystem_ocio.aep")
        assert project.color_management_system.name == "OCIO"

    def test_lutInterpolationMethod_trilinear(self) -> None:
        project = parse_project(SAMPLES_DIR / "lutInterpolationMethod_trilinear.aep")
        assert (
            project.lut_interpolation_method
            == project.lut_interpolation_method.TRILINEAR
        )

    def test_lutInterpolationMethod_tetrahedral(self) -> None:
        project = parse_project(SAMPLES_DIR / "lutInterpolationMethod_tetrahedral.aep")
        assert (
            project.lut_interpolation_method
            == project.lut_interpolation_method.TETRAHEDRAL
        )


class TestRevision:
    """Tests for revision attribute."""

    def test_revision_save_01(self) -> None:
        """A new project saved once has revision 1."""
        project = parse_project(SAMPLES_DIR / "save_01.aep")
        assert project.revision == 1

    def test_revision_increases_with_changes(self) -> None:
        """Projects with more user actions have higher revision numbers."""
        project_simple = parse_project(SAMPLES_DIR / "save_01.aep")
        project_changed = parse_project(SAMPLES_DIR / "bitsPerChannel_16.aep")
        assert project_changed.revision > project_simple.revision


VIEW_SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "models" / "view"


class TestActiveItem:
    """Tests for active_item attribute."""

    def test_comp1_active(self) -> None:
        project = parse_project(VIEW_SAMPLES_DIR / "comp1_active.aep")
        assert project.active_item is not None
        assert project.active_item.name == "Comp 1"

    def test_comp2_active(self) -> None:
        project = parse_project(VIEW_SAMPLES_DIR / "comp2_active.aep")
        assert project.active_item is not None
        assert project.active_item.name == "Comp 2"


class TestRoundtripLinearBlending:
    """Roundtrip tests for Project.linear_blending."""

    def test_enable_linear_blending(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "linearBlending_false.aep").project
        assert project.linear_blending is False

        project.linear_blending = True

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.linear_blending is True

    def test_disable_linear_blending(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "linearBlending_true.aep").project
        assert project.linear_blending is True

        project.linear_blending = False

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.linear_blending is False

    def test_set_same_value_is_noop(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "linearBlending_true.aep").project
        assert project.linear_blending is True

        project.linear_blending = True  # no change

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.linear_blending is True


class TestRoundtripLinearizeWorkingSpace:
    """Roundtrip tests for Project.linearize_working_space."""

    def test_enable_linearize_working_space(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "linearizeWorkingSpace_false.aep").project
        assert project.linearize_working_space is False

        project.linearize_working_space = True

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.linearize_working_space is True

    def test_disable_linearize_working_space(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "linearizeWorkingSpace_true.aep").project
        assert project.linearize_working_space is True

        project.linearize_working_space = False

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.linearize_working_space is False

    def test_set_same_value_is_noop(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "linearizeWorkingSpace_false.aep").project
        assert project.linearize_working_space is False

        project.linearize_working_space = False  # no change

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.linearize_working_space is False


class TestRoundtripExpressionEngine:
    """Roundtrip tests for Project.expression_engine."""

    def test_set_extendscript(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "expressionEngine_javascript.aep").project
        assert project.expression_engine == "javascript-1.0"

        project.expression_engine = "extendscript"

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.expression_engine == "extendscript"

    def test_set_javascript(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "linearBlending_false.aep").project
        assert project.expression_engine == "extendscript"

        project.expression_engine = "javascript-1.0"

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.expression_engine == "javascript-1.0"

    def test_set_same_value_is_noop(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "expressionEngine_javascript.aep").project
        assert project.expression_engine == "javascript-1.0"

        project.expression_engine = "javascript-1.0"

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.expression_engine == "javascript-1.0"


class TestRoundtripColorManagementSystem:
    """Roundtrip tests for Project.color_management_system."""

    def test_set_ocio(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "colorManagementSystem_adobe.aep").project
        assert project.color_management_system == ColorManagementSystem.ADOBE

        project.color_management_system = ColorManagementSystem.OCIO

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.color_management_system == ColorManagementSystem.OCIO

    def test_set_adobe(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "colorManagementSystem_ocio.aep").project
        assert project.color_management_system == ColorManagementSystem.OCIO

        project.color_management_system = ColorManagementSystem.ADOBE

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.color_management_system == ColorManagementSystem.ADOBE


class TestRoundtripLutInterpolationMethod:
    """Roundtrip tests for Project.lut_interpolation_method."""

    def test_set_tetrahedral(self, tmp_path: Path) -> None:
        project = parse_aep(
            SAMPLES_DIR / "lutInterpolationMethod_trilinear.aep"
        ).project
        assert project.lut_interpolation_method == LutInterpolationMethod.TRILINEAR

        project.lut_interpolation_method = LutInterpolationMethod.TETRAHEDRAL

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.lut_interpolation_method == LutInterpolationMethod.TETRAHEDRAL

    def test_set_trilinear(self, tmp_path: Path) -> None:
        project = parse_aep(
            SAMPLES_DIR / "lutInterpolationMethod_tetrahedral.aep"
        ).project
        assert project.lut_interpolation_method == LutInterpolationMethod.TETRAHEDRAL

        project.lut_interpolation_method = LutInterpolationMethod.TRILINEAR

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.lut_interpolation_method == LutInterpolationMethod.TRILINEAR


class TestRoundtripOcioConfigurationFile:
    """Roundtrip tests for Project.ocio_configuration_file."""

    def test_set_ocio_config(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "colorManagementSystem_ocio.aep").project

        project.ocio_configuration_file = "new_config.ocio"

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.ocio_configuration_file == "new_config.ocio"


class TestRoundtripBitsPerChannel:
    """Roundtrip tests for Project.bits_per_channel."""

    def test_set_sixteen(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "bitsPerChannel_8.aep").project
        assert project.bits_per_channel == BitsPerChannel.EIGHT

        project.bits_per_channel = BitsPerChannel.SIXTEEN

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.bits_per_channel == BitsPerChannel.SIXTEEN

    def test_set_thirty_two(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "bitsPerChannel_8.aep").project
        assert project.bits_per_channel == BitsPerChannel.EIGHT

        project.bits_per_channel = BitsPerChannel.THIRTY_TWO

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.bits_per_channel == BitsPerChannel.THIRTY_TWO

    def test_set_eight(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "bitsPerChannel_32.aep").project
        assert project.bits_per_channel == BitsPerChannel.THIRTY_TWO

        project.bits_per_channel = BitsPerChannel.EIGHT

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.bits_per_channel == BitsPerChannel.EIGHT


class TestRoundtripFeetFramesFilmType:
    """Roundtrip tests for Project.feet_frames_film_type."""

    def test_set_mm16(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "feetFramesFilmType_MM35.aep").project
        assert project.feet_frames_film_type == FeetFramesFilmType.MM35

        project.feet_frames_film_type = FeetFramesFilmType.MM16

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.feet_frames_film_type == FeetFramesFilmType.MM16

    def test_set_mm35(self, tmp_path: Path) -> None:
        """Set to MM16 then back to MM35 via chained roundtrip."""
        project = parse_aep(SAMPLES_DIR / "feetFramesFilmType_MM35.aep").project
        project.feet_frames_film_type = FeetFramesFilmType.MM16
        mid = tmp_path / "mid.aep"
        project.save(mid)

        project2 = parse_aep(mid).project
        project2.feet_frames_film_type = FeetFramesFilmType.MM35
        out = tmp_path / "modified.aep"
        project2.save(out)
        project3 = parse_aep(out).project

        assert project3.feet_frames_film_type == FeetFramesFilmType.MM35


class TestRoundtripFootageTimecodeDisplayStartType:
    """Roundtrip tests for Project.footage_timecode_display_start_type."""

    def test_set_start_0(self, tmp_path: Path) -> None:
        project = parse_aep(
            SAMPLES_DIR / "footageTimecodeDisplayStartType_source.aep"
        ).project
        assert (
            project.footage_timecode_display_start_type
            == FootageTimecodeDisplayStartType.FTCS_USE_SOURCE_MEDIA
        )

        project.footage_timecode_display_start_type = (
            FootageTimecodeDisplayStartType.FTCS_START_0
        )

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert (
            project2.footage_timecode_display_start_type
            == FootageTimecodeDisplayStartType.FTCS_START_0
        )

    def test_set_use_source_media(self, tmp_path: Path) -> None:
        """Set to START_0 then back to USE_SOURCE_MEDIA via chained roundtrip."""
        project = parse_aep(
            SAMPLES_DIR / "footageTimecodeDisplayStartType_source.aep"
        ).project
        project.footage_timecode_display_start_type = (
            FootageTimecodeDisplayStartType.FTCS_START_0
        )
        mid = tmp_path / "mid.aep"
        project.save(mid)

        project2 = parse_aep(mid).project
        project2.footage_timecode_display_start_type = (
            FootageTimecodeDisplayStartType.FTCS_USE_SOURCE_MEDIA
        )
        out = tmp_path / "modified.aep"
        project2.save(out)
        project3 = parse_aep(out).project

        assert (
            project3.footage_timecode_display_start_type
            == FootageTimecodeDisplayStartType.FTCS_USE_SOURCE_MEDIA
        )


class TestRoundtripFramesCountType:
    """Roundtrip tests for Project.frames_count_type."""

    def test_set_start_1(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "framesCountType_start0.aep").project
        assert project.frames_count_type == FramesCountType.FC_START_0

        project.frames_count_type = FramesCountType.FC_START_1

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.frames_count_type == FramesCountType.FC_START_1

    def test_set_start_0(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "displayStartFrame_1.aep").project
        assert project.frames_count_type == FramesCountType.FC_START_1

        project.frames_count_type = FramesCountType.FC_START_0

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.frames_count_type == FramesCountType.FC_START_0


class TestRoundtripDisplayStartFrame:
    """Roundtrip tests for Project.display_start_frame."""

    def test_set_1(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "framesCountType_start0.aep").project
        assert project.display_start_frame == 0

        project.display_start_frame = 1

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.display_start_frame == 1

    def test_set_0(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "displayStartFrame_1.aep").project
        assert project.display_start_frame == 1

        project.display_start_frame = 0

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.display_start_frame == 0


class TestRoundtripFramesUseFeetFrames:
    """Roundtrip tests for Project.frames_use_feet_frames."""

    def test_enable(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "framesUseFeetFrames_false.aep").project
        assert project.frames_use_feet_frames == 0

        project.frames_use_feet_frames = 1

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.frames_use_feet_frames == 1

    def test_disable(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "framesUseFeetFrames_true.aep").project
        assert project.frames_use_feet_frames == 1

        project.frames_use_feet_frames = 0

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.frames_use_feet_frames == 0


class TestRoundtripTimeDisplayType:
    """Roundtrip tests for Project.time_display_type."""

    def test_set_frames(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "timeDisplayType_timecode.aep").project
        assert project.time_display_type == TimeDisplayType.TIMECODE

        project.time_display_type = TimeDisplayType.FRAMES

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.time_display_type == TimeDisplayType.FRAMES

    def test_set_timecode(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "timeDisplayType_frames.aep").project
        assert project.time_display_type == TimeDisplayType.FRAMES

        project.time_display_type = TimeDisplayType.TIMECODE

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.time_display_type == TimeDisplayType.TIMECODE


class TestRoundtripTransparencyGridThumbnails:
    """Roundtrip tests for Project.transparency_grid_thumbnails."""

    def test_enable(self, tmp_path: Path) -> None:
        project = parse_aep(
            SAMPLES_DIR / "transparencyGridThumbnails_false.aep"
        ).project
        assert project.transparency_grid_thumbnails is False

        project.transparency_grid_thumbnails = True

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.transparency_grid_thumbnails is True

    def test_disable(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "transparencyGridThumbnails_true.aep").project
        assert project.transparency_grid_thumbnails is True

        project.transparency_grid_thumbnails = False

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.transparency_grid_thumbnails is False


class TestRoundtripCompensateForSceneReferredProfiles:
    """Roundtrip tests for Project.compensate_for_scene_referred_profiles."""

    def test_enable(self, tmp_path: Path) -> None:
        project = parse_aep(
            SAMPLES_DIR / "compensateForSceneReferredProfiles_false.aep"
        ).project
        assert project.compensate_for_scene_referred_profiles is False

        project.compensate_for_scene_referred_profiles = True

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.compensate_for_scene_referred_profiles is True

    def test_disable(self, tmp_path: Path) -> None:
        project = parse_aep(
            SAMPLES_DIR / "compensateForSceneReferredProfiles_true.aep"
        ).project
        assert project.compensate_for_scene_referred_profiles is True

        project.compensate_for_scene_referred_profiles = False

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.compensate_for_scene_referred_profiles is False


class TestRoundtripAudioSampleRate:
    """Roundtrip tests for Project.audio_sample_rate."""

    def test_set_96000(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "Audio_sample_rate_22050.aep").project
        assert project.audio_sample_rate == 22050.0

        project.audio_sample_rate = 96000.0

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.audio_sample_rate == 96000.0

    def test_set_22050(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "Audio_sample_rate_96000.aep").project
        assert project.audio_sample_rate == 96000.0

        project.audio_sample_rate = 22050.0

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.audio_sample_rate == 22050.0


class TestRoundtripWorkingGamma:
    """Roundtrip tests for Project.working_gamma."""

    def test_set_2_2(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "workingGamma_2.4.aep").project
        assert project.working_gamma == 2.4

        project.working_gamma = 2.2

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.working_gamma == 2.2

    def test_set_2_4(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "workingGamma_2.2.aep").project
        assert project.working_gamma == 2.2

        project.working_gamma = 2.4

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.working_gamma == 2.4


class TestRoundtripGpuAccelType:
    """Roundtrip tests for Project.gpu_accel_type."""

    def test_set_software(self, tmp_path: Path) -> None:
        project = parse_aep(
            SAMPLES_DIR / "gpuAccelType_mercury_gpu_acceleration_CUDA.aep"
        ).project
        assert project.gpu_accel_type == GpuAccelType.CUDA

        project.gpu_accel_type = GpuAccelType.SOFTWARE

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.gpu_accel_type == GpuAccelType.SOFTWARE

    def test_set_cuda(self, tmp_path: Path) -> None:
        project = parse_aep(
            SAMPLES_DIR / "gpuAccelType_mercury_software_only.aep"
        ).project
        assert project.gpu_accel_type == GpuAccelType.SOFTWARE

        project.gpu_accel_type = GpuAccelType.CUDA

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.gpu_accel_type == GpuAccelType.CUDA


class TestRoundtripRevision:
    """Roundtrip tests for Project.revision."""

    def test_set_revision(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "save_01.aep").project
        original = project.revision

        project.revision = original + 10

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.revision == original + 10


VERSIONS_DIR = Path(__file__).parent.parent / "samples" / "versions"


class TestIdempotency:
    """Parse then save must produce identical bytes."""

    def test_roundtrip_complete(self, tmp_path: Path) -> None:
        aep_path = VERSIONS_DIR / "ae2025" / "complete.aep"
        original_bytes = aep_path.read_bytes()

        app = parse_aep(aep_path)
        out = tmp_path / "roundtrip.aep"
        app.project.save(out)
        roundtrip_bytes = out.read_bytes()

        assert original_bytes == roundtrip_bytes
