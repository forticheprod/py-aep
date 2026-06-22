"""Tests for Project model parsing."""

from __future__ import annotations

from pathlib import Path

from conftest import load_expected, parse_project

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "project"
VIEW_SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "view"
VERSIONS_DIR = Path(__file__).parent.parent.parent / "samples" / "versions"
LAYER_SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"
COMP_SAMPLES_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "composition"
)


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


class TestListColorProfiles:
    """Tests for Project.list_color_profiles()."""

    def test_adobe_mode_matches_catalogue(self) -> None:
        # Validated set-equal to AE listColorProfiles() (102 names, AE 2026).
        project = parse_project(SAMPLES_DIR / "workingSpace_sRGB.aep")
        profiles = project.list_color_profiles()
        assert len(profiles) == 102
        for expected in ("sRGB IEC61966-2.1", "ProPhoto RGB", "Apple RGB"):
            assert expected in profiles

    def test_ocio_mode_missing_config_returns_empty(self) -> None:
        # This sample's stored ocioConfigurationFile path no longer exists; the
        # method degrades gracefully to an empty list.
        project = parse_project(SAMPLES_DIR / "colorManagementSystem_ocio.aep")
        assert project.color_management_system.name == "OCIO"
        assert project.list_color_profiles() == []
