"""Tests for Project model parsing."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from helpers import project_bytes

import py_aep
from py_aep import Project
from py_aep import parse as parse_aep
from py_aep.binary.utils import find_by_list_type
from py_aep.color.envelope import parse_envelope
from py_aep.color.icc import ColorProfileNotFoundError, icc_profile_id
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

if TYPE_CHECKING:
    from py_aep.binary.chunk import Chunk

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "project"
VIEW_SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "view"
VERSIONS_DIR = Path(__file__).parent.parent.parent / "samples" / "versions"
LAYER_SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"
COMP_SAMPLES_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "composition"
)


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
        assert project2._nhed.bits_per_channel == BitsPerChannel.THIRTY_TWO.to_binary()
        assert project2._nnhd.bits_per_channel == BitsPerChannel.THIRTY_TWO.to_binary()

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
        assert (
            project2._nhed.feet_frames_film_type == project2._nnhd.feet_frames_film_type
        )

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
        assert project2._nhed.frames_count_type == project2._nnhd.frames_count_type

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
        assert project2._nhed.frames_count_type == project2._nnhd.frames_count_type

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
        assert project.frames_use_feet_frames is False

        project.frames_use_feet_frames = True

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.frames_use_feet_frames is True
        assert (
            project2._nhed.frames_use_feet_frames
            == project2._nnhd.frames_use_feet_frames
        )

    def test_disable(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "framesUseFeetFrames_true.aep").project
        assert project.frames_use_feet_frames is True

        project.frames_use_feet_frames = False

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.frames_use_feet_frames is False
        assert (
            project2._nhed.frames_use_feet_frames
            == project2._nnhd.frames_use_feet_frames
        )


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
        assert project2._nhed.time_display_type == project2._nnhd.time_display_type

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
        assert (
            project2._nhed.transparency_grid_thumbnails
            == project2._nnhd.transparency_grid_thumbnails
        )

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

    def test_unrecognized_uuid_roundtrips(self, tmp_path: Path) -> None:
        """A renderer id py_aep does not map reads back as its UUID string,
        and that string can be written back."""
        uuid = "01234567-89ab-cdef-0123-456789abcdef"
        project = parse_aep(
            SAMPLES_DIR / "gpuAccelType_mercury_software_only.aep"
        ).project
        project.gpu_accel_type = uuid  # type: ignore[assignment]
        assert project.gpu_accel_type == uuid
        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project
        assert project2.gpu_accel_type == uuid
        project2.gpu_accel_type = project2.gpu_accel_type

    def test_rejects_malformed_uuid(self) -> None:
        project = parse_aep(
            SAMPLES_DIR / "gpuAccelType_mercury_software_only.aep"
        ).project
        with pytest.raises(ValueError, match="UUID"):
            project.gpu_accel_type = "not-a-uuid"  # type: ignore[assignment]
        assert project.gpu_accel_type == GpuAccelType.SOFTWARE


class TestRoundtripWorkingSpaceProfileId:
    """`cpid` holds the ICC profile id of the working space.

    AE 2026 rewrites it when a script sets `workingSpace` (the id of the
    new profile; all 0xFF for "None"), and every AE-saved project whose
    working space is an ICC profile has `cpid` equal to that profile's id.
    OCIO projects store all 0xFF.
    """

    ACESCCT_DONOR = (
        Path(__file__).parent.parent.parent
        / "samples"
        / "models"
        / "footage"
        / "override_media_colorspace_working_colorspace_-aces_cg_or_cct.aep"
    )

    @staticmethod
    def _cpid(project: Project) -> bytes:
        return next(c.tobytes() for c in project._rifx.chunks if c.chunk_type == "cpid")

    def test_adobe_working_space_writes_profile_id(self, tmp_path: Path) -> None:
        # The ACEScct ICC exactly as AE embedded it, next to the cpid AE
        # wrote for it.
        donor = parse_aep(self.ACESCCT_DONOR).project
        assert donor._ws_utf8 is not None
        icc = parse_envelope(donor._ws_utf8.value).data
        assert self._cpid(donor).hex() == "ae27d1e66d65c5a0a50fe0ec149a24fa"
        icc_dir = tmp_path / "icc"
        icc_dir.mkdir()
        (icc_dir / "ACEScct.icc").write_bytes(icc)

        project = parse_aep(SAMPLES_DIR / "workingSpace_sRGB.aep").project
        project.icc_profile_dirs = [icc_dir]
        project.working_space = "ACEScct"
        out = tmp_path / "ws.aep"
        project.save(out)
        project2 = parse_aep(out).project
        assert project2.working_space == "ACEScct"
        assert self._cpid(project2) == self._cpid(donor)

    def test_ocio_working_space_writes_no_profile_id(self, tmp_path: Path) -> None:
        config = (
            Path(__file__).parent.parent.parent / "samples" / "assets" / "config.ocio"
        )
        project = parse_aep(SAMPLES_DIR / "workingSpace_sRGB.aep").project
        assert self._cpid(project) != b"\xff" * 16
        project.color_management_system = ColorManagementSystem.OCIO
        project.ocio_configuration_file = str(config)
        project.working_space = "ACEScg"
        assert self._cpid(project) == b"\xff" * 16


def _profile_pool(project: Project) -> list[Chunk]:
    return find_by_list_type(chunks=project._rifx.chunks, list_type="CPPl").chunks


class TestRoundtripPre22WorkingSpace:
    """Before AE 22 the working space is a `pprf` ICC in `LIST:CPPl`, named
    by its profile id in `cpid`.

    Measured on AE 15.1: it re-saves this pool as py_aep writes it, keeps a
    profile nothing refers to anymore, sorts the pool by profile id, and
    renders a new 15.1 project with an sRGB working space like its own
    template.
    """

    # An AE 15 pool: sRGB IEC61966-2.1 (the working space), then SDTV NTSC.
    DONOR = VERSIONS_DIR / "ae2018" / "complete.aep"
    SRGB = "sRGB IEC61966-2.1"
    SRGB_ID = bytes.fromhex("1d3fda2edb4a89ab60a23c5f7c7d81dd")
    NTSC_ID = bytes.fromhex("2734184f30e0dfca20be1a95a0a65519")

    @classmethod
    def _icc_dir(cls, tmp_path: Path) -> Path:
        # The ICCs exactly as AE stored them, so no installed profile is needed.
        icc_dir = tmp_path / "icc"
        icc_dir.mkdir()
        for i, pprf in enumerate(_profile_pool(parse_aep(cls.DONOR).project)):
            (icc_dir / f"{i}.icc").write_bytes(pprf.data)
        return icc_dir

    def test_new_15_project_settings_round_trip(self, tmp_path: Path) -> None:
        project = py_aep.new("15.1x69").project
        project.icc_profile_dirs = [self._icc_dir(tmp_path)]
        project.bits_per_channel = BitsPerChannel.THIRTY_TWO
        project.time_display_type = TimeDisplayType.FRAMES
        project.gpu_accel_type = GpuAccelType.SOFTWARE
        project.linearize_working_space = True
        project.working_space = self.SRGB

        out = tmp_path / "new15.aep"
        project.save(out)
        app2 = parse_aep(out)
        project2 = app2.project

        assert app2.version == "15.1x69"
        assert project2.working_space == self.SRGB
        assert project2.linearize_working_space is True
        assert project2.bits_per_channel == BitsPerChannel.THIRTY_TWO
        assert project2.time_display_type == TimeDisplayType.FRAMES
        assert project2.gpu_accel_type == GpuAccelType.SOFTWARE
        # AE 15.1's own template: the pool holds just the working space's
        # ICC, and `lnrp` sits between `cpid` and `dwga`.
        donor_icc = _profile_pool(parse_aep(self.DONOR).project)[0].data
        assert [c.data for c in _profile_pool(project2)] == [donor_icc]
        assert project2._cpid.data == self.SRGB_ID
        types = [c.chunk_type for c in project2._rifx.chunks]
        i = types.index("cpid")
        assert types[i : i + 3] == ["cpid", "lnrp", "dwga"]

    def test_new_profile_is_inserted_in_id_order(self, tmp_path: Path) -> None:
        project = py_aep.new("15.1x69").project
        project.icc_profile_dirs = [self._icc_dir(tmp_path)]
        project.working_space = "SDTV NTSC"
        project.working_space = self.SRGB

        out = tmp_path / "ws.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.working_space == self.SRGB
        assert project2._cpid.data == self.SRGB_ID
        # The replaced SDTV NTSC stays, after the lower sRGB id.
        pool_ids = [icc_profile_id(c.data) for c in _profile_pool(project2)]
        assert pool_ids == [self.SRGB_ID, self.NTSC_ID]

    def test_pooled_profile_is_reused(self, tmp_path: Path) -> None:
        project = parse_aep(self.DONOR).project
        project.icc_profile_dirs = [self._icc_dir(tmp_path)]
        before = project_bytes(project)
        project.working_space = project.working_space
        assert project_bytes(project) == before

        project.working_space = "SDTV NTSC"
        out = tmp_path / "ws.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.working_space == "SDTV NTSC"
        assert project2._cpid.data == self.NTSC_ID
        assert len(_profile_pool(project2)) == 2

    def test_none_keeps_the_pool(self, tmp_path: Path) -> None:
        project = parse_aep(self.DONOR).project
        pool = [c.data for c in _profile_pool(project)]
        project.working_space = "None"

        out = tmp_path / "ws.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.working_space == "None"
        assert project2._cpid.data == b"\xff" * 16
        assert [c.data for c in _profile_pool(project2)] == pool

    def test_unknown_profile_leaves_project_unchanged(self, tmp_path: Path) -> None:
        project = py_aep.new("15.1x69").project
        project.icc_profile_dirs = [self._icc_dir(tmp_path)]
        before = project_bytes(project)
        with pytest.raises(ColorProfileNotFoundError):
            project.working_space = "Not A Profile"
        assert project_bytes(project) == before


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

    def test_set_revision_above_16_bits(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "save_01.aep").project
        project.revision = 70_000
        out = tmp_path / "modified.aep"
        project.save(out)
        assert parse_aep(out).project.revision == 70_000
        with pytest.raises(ValueError):
            project.revision = 1 << 32

    """Roundtrip tests for Project.xmp_packet."""

    def test_set_xmp_packet(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "linearBlending_false.aep").project

        xmp_packet = project.xmp_packet
        xmp_packet.set("py_aep_test_marker", "1")
        project.xmp_packet = xmp_packet

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.xmp_packet.get("py_aep_test_marker") == "1"


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


class TestListColorProfilesOcio:
    """Project.list_color_profiles() in OCIO mode with a resolvable config."""

    CONFIG = Path(__file__).parent.parent.parent / "samples" / "assets" / "config.ocio"

    def test_resolvable_config_lists_colorspaces(self) -> None:
        project = parse_aep(SAMPLES_DIR / "colorManagementSystem_ocio.aep").project
        project.ocio_configuration_file = str(self.CONFIG)
        profiles = project.list_color_profiles()
        assert len(profiles) == 22  # == PyOpenColorIO
        assert "ACEScg" in profiles

    def test_listed_names_are_assignable_as_working_space(self) -> None:
        # Every listed OCIO name is a valid working_space, and what it reads
        # back as can be assigned again (read -> write -> read is stable).
        #
        # It does NOT read back as the name assigned: AE stores a direct
        # colorspace pick's `colorProfileName` as "<family>/<name>", and the
        # getter is AE-faithful (ExtendScript's workingSpace echoes the same
        # qualified string). That asymmetry is AE's, not py_aep's.
        project = parse_aep(SAMPLES_DIR / "colorManagementSystem_ocio.aep").project
        project.ocio_configuration_file = str(self.CONFIG)
        for name in project.list_color_profiles():
            project.working_space = name
            stored = project.working_space
            assert stored.rsplit("/", 1)[-1] == name
            project.working_space = stored
            assert project.working_space == stored


class TestColorProfileSlotBinding:
    """The `PwCs` (working) and `pdvc` (display) color-profile slots must not
    be confused for one another.

    Both slots hold a `Utf8` whose unset value is the literal `{}`, so binding
    them by the ORDER the envelopes appear in reads a display space as the
    working space whenever the working space is unset. They are bound by their
    marker chunk instead, on both the read and the write side.

    AE 2026 authenticates the shape: it opens a py_aep file written this way
    and re-saves it keeping the envelope under `pdvc` with `PwCs` still `{}`.
    """

    # An AE-authored OCIO project whose working space is unset (`PwCs` == {}).
    UNSET_WS = LAYER_SAMPLES_DIR / "geometry_probe.aep"

    def test_display_space_roundtrips_with_working_space_unset(
        self, tmp_path: Path
    ) -> None:
        project = parse_aep(self.UNSET_WS).project
        assert project.working_space == "None"
        assert project.display_color_space == "None"

        project.display_color_space = ("ACES", "sRGB")

        out = tmp_path / "display.aep"
        project.save(out)
        project2 = parse_aep(out).project

        assert project2.display_color_space == "ACES/sRGB"

    def test_display_space_write_does_not_leak_into_working_space(
        self, tmp_path: Path
    ) -> None:
        project = parse_aep(self.UNSET_WS).project
        project.display_color_space = ("ACES", "sRGB")

        out = tmp_path / "display.aep"
        project.save(out)
        project2 = parse_aep(out).project

        # Writing only the DISPLAY space must not give the project a working
        # space it never had.
        assert project2.working_space == "None"

    def test_both_slots_roundtrip_together(self, tmp_path: Path) -> None:
        config = (
            Path(__file__).parent.parent.parent / "samples" / "assets" / "config.ocio"
        )
        project = parse_aep(self.UNSET_WS).project
        project.ocio_configuration_file = str(config)
        project.working_space = "ACEScg"
        project.display_color_space = ("ACES", "sRGB")

        out = tmp_path / "both.aep"
        project.save(out)
        project2 = parse_aep(out).project

        # A direct colorspace pick reads back qualified as "<family>/<name>"
        # (AE's stored colorProfileName) - see
        # TestListColorProfilesOcio::test_listed_names_are_assignable_as_working_space.
        assert project2.working_space == "ACES/ACEScg"
        assert project2.display_color_space == "ACES/sRGB"
