"""Tests for Project model parsing."""

from __future__ import annotations

from pathlib import Path

from conftest import load_expected, parse_project

from py_aep.enums import GpuAccelType

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

    def test_pre_color_management_profile_id(self) -> None:
        """A CC 2018 project names its working space only by the `cpid`
        profile id, whose ICC sits in `LIST:CPPl`."""
        expected = load_expected(VERSIONS_DIR / "ae2018", "complete")
        project = parse_project(VERSIONS_DIR / "ae2018" / "complete.aep")
        assert expected["workingSpace"] == "sRGB IEC61966-2.1"
        assert project.working_space == expected["workingSpace"]

    def test_pre_color_management_no_working_space(self) -> None:
        # The all-0xFF `cpid` of an empty CC 2018 project: AE 2026 reports
        # workingSpace "None" for it.
        project = parse_project(SAMPLES_DIR / "emptier_2018.aep")
        assert project.working_space == "None"


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

    def test_opencl(self) -> None:
        # Saved by AE 25.3 (Windows); AE 2026 reports gpuAccelType 1812 for it.
        project = parse_project(
            SAMPLES_DIR.parent.parent / "bugs" / "outputmodule_path.aep"
        )
        assert project.gpu_accel_type == GpuAccelType.OPENCL

    def test_renderer_ids(self) -> None:
        # What AE 2026 reports as `gpuAccelType` for a project holding each id.
        ids = {
            "7ee0ab59-822d-44cc-ac10-16279d041016": GpuAccelType.CUDA,
            "be93941a-7488-4117-8a46-7e3596950307": GpuAccelType.OPENCL,
            "6ed1497e-17ad-4a5b-846f-52bb81e20104": GpuAccelType.METAL,
            "c4471277-d5d1-4ea7-a36c-b93ac76dfd41": GpuAccelType.VULKAN,
            "f33089e2-1ede-47c1-8a9e-b232bb1cc1a4": GpuAccelType.SOFTWARE,
            "cd99cfc1-bf65-4cb7-ab70-a8f5ea50e8f4": GpuAccelType.DIRECTX,
        }
        for guid, accel in ids.items():
            assert GpuAccelType.from_binary(guid) == accel
            assert GpuAccelType.to_binary(accel) == guid


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

    def test_revision_is_a_32_bit_counter(self) -> None:
        # The stored counter exceeds 16 bits. AE 2026 reports 23,113,386 for
        # this file: the stored value plus the 13 edits AE makes on open.
        project = parse_project(
            SAMPLES_DIR.parent.parent / "bugs" / "windows-1250_decoding_error.aep"
        )
        assert project.revision == 23_113_373


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


class TestDynamicLinkGUID:
    """Tests for Item.dynamic_link_guid.

    The id-derived formula was validated against AE 2026 (2026-07-14 probe:
    all 11 items of a generated project matched, stable across re-open, and
    reading the attribute left the chunk tree byte-identical).
    """

    def test_derived_from_item_id(self) -> None:
        project = parse_project(SAMPLES_DIR / "bitsPerChannel_8.aep")
        assert project.items
        for item_id, item in project.items.items():
            assert item.dynamic_link_guid == (
                f"{item_id:08x}-0000-0000-0000-000000000000"
            )

    def test_guid_shape(self) -> None:
        project = parse_project(SAMPLES_DIR / "bitsPerChannel_8.aep")
        guid = next(iter(project.items.values())).dynamic_link_guid
        groups = guid.split("-")
        assert [len(g) for g in groups] == [8, 4, 4, 4, 12]
        assert guid == guid.lower()
