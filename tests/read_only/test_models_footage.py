"""Tests for FootageItem model parsing."""

from __future__ import annotations

import math
from pathlib import Path

from conftest import (
    get_comp,
    get_first_footage,
    get_footage,
    get_footage_from_json_by_name,
    load_expected,
    parse_project,
)

from py_aep import (
    AlphaMode,
    FieldSeparationType,
)

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "footage"


class TestFootageSize:
    """Tests for footage size attributes."""

    def test_size_1920x1080(self) -> None:
        project = parse_project(SAMPLES_DIR / "solid_sizes.aep")
        comp = get_comp(project, "solid_size_1920x1080")
        footage = comp.layers[0].source
        assert footage.width == 1920
        assert footage.height == 1080

    def test_size_3840x2160(self) -> None:
        project = parse_project(SAMPLES_DIR / "solid_sizes.aep")
        comp = get_comp(project, "solid_size_3840x2160")
        footage = comp.layers[0].source
        assert footage.width == 3840
        assert footage.height == 2160


class TestPlaceholders:
    """Tests for placeholder footage."""

    def test_placeholder_still(self) -> None:
        expected = load_expected(SAMPLES_DIR, "placeholder")
        footage_json = get_footage_from_json_by_name(expected, "placeholder_still")
        footage = get_footage(
            parse_project(SAMPLES_DIR / "placeholder.aep"), "placeholder_still"
        )
        assert footage_json["mainSource"]["isStill"] is True
        assert footage.main_source.is_still == footage_json["mainSource"]["isStill"]

    def test_placeholder_movie(self) -> None:
        expected = load_expected(SAMPLES_DIR, "placeholder")
        footage_json = get_footage_from_json_by_name(expected, "placeholder_movie")
        footage = get_footage(
            parse_project(SAMPLES_DIR / "placeholder.aep"), "placeholder_movie"
        )
        assert footage_json["mainSource"]["isStill"] is False
        assert footage.main_source.is_still == footage_json["mainSource"]["isStill"]

    def test_placeholder_720p(self) -> None:
        expected = load_expected(SAMPLES_DIR, "placeholder")
        footage_json = get_footage_from_json_by_name(expected, "placeholder_720p")
        footage = get_footage(
            parse_project(SAMPLES_DIR / "placeholder.aep"), "placeholder_720p"
        )
        assert footage.width == footage_json["width"] == 1280
        assert footage.height == footage_json["height"] == 720

    def test_placeholder_4K(self) -> None:
        expected = load_expected(SAMPLES_DIR, "placeholder")
        footage_json = get_footage_from_json_by_name(expected, "placeholder_4K")
        footage = get_footage(
            parse_project(SAMPLES_DIR / "placeholder.aep"), "placeholder_4K"
        )
        assert footage.width == footage_json["width"] == 3840
        assert footage.height == footage_json["height"] == 2160

    def test_placeholder_30fps(self) -> None:
        expected = load_expected(SAMPLES_DIR, "placeholder")
        footage_json = get_footage_from_json_by_name(expected, "placeholder_30fps")
        footage = get_footage(
            parse_project(SAMPLES_DIR / "placeholder.aep"), "placeholder_30fps"
        )
        assert footage_json["frameRate"] == 30
        assert math.isclose(footage.frame_rate, footage_json["frameRate"])

    def test_placeholder_60fps(self) -> None:
        expected = load_expected(SAMPLES_DIR, "placeholder")
        footage_json = get_footage_from_json_by_name(expected, "placeholder_60fps")
        footage = get_footage(
            parse_project(SAMPLES_DIR / "placeholder.aep"), "placeholder_60fps"
        )
        assert footage_json["frameRate"] == 60
        assert math.isclose(footage.frame_rate, footage_json["frameRate"])

    def test_frameRate_23976(self) -> None:
        expected = load_expected(SAMPLES_DIR, "footage_misc")
        footage_json = get_footage_from_json_by_name(expected, "frameRate_23976")
        footage = get_footage(
            parse_project(SAMPLES_DIR / "footage_misc.aep"), "frameRate_23976"
        )
        assert math.isclose(
            footage.frame_rate, footage_json["frameRate"], rel_tol=0.001
        )


class TestIsMediaReplacementCompatible:
    """Ground truth: isMediaReplacementCompatible from ExtendScript exports."""

    LAYER_SAMPLES_DIR = SAMPLES_DIR.parent / "layer"

    def test_comp_is_compatible(self) -> None:
        project = parse_project(SAMPLES_DIR / "solid_sizes.aep")
        comp = get_comp(project, "solid_size_1920x1080")
        assert comp.is_media_replacement_compatible is True

    def test_solid_is_not_compatible(self) -> None:
        project = parse_project(SAMPLES_DIR / "solid_sizes.aep")
        solid = get_comp(project, "solid_size_1920x1080").layers[0].source
        assert solid.is_media_replacement_compatible is False

    def test_placeholder_is_compatible(self) -> None:
        project = parse_project(SAMPLES_DIR / "placeholder.aep")
        assert (
            get_footage(project, "placeholder_still").is_media_replacement_compatible
            is True
        )
        assert (
            get_footage(project, "placeholder_movie").is_media_replacement_compatible
            is True
        )

    def test_audio_only_footage_is_not_compatible(self) -> None:
        project = parse_project(self.LAYER_SAMPLES_DIR / "audioEnabled.aep")
        wav = get_footage(project, "wav.wav")
        assert wav.has_video is False
        assert wav.is_media_replacement_compatible is False

    def test_3d_model_is_not_compatible_but_movie_is(self) -> None:
        project = parse_project(self.LAYER_SAMPLES_DIR / "light_source_default.aep")
        fbx = get_footage(project, "crystal.fbx")
        assert fbx.has_video is True
        assert fbx.is_media_replacement_compatible is False
        mov = get_footage(project, "mov_23_976.mov")
        assert mov.is_media_replacement_compatible is True


class TestSolidColors:
    """Tests for solid footage colors."""

    def test_color_red(self) -> None:
        project = parse_project(SAMPLES_DIR / "solid_colors.aep")
        comp = get_comp(project, "solid_color_red")
        footage = comp.layers[0].source
        assert footage.main_source.color[:3] == [1, 0, 0]

    def test_color_green(self) -> None:
        project = parse_project(SAMPLES_DIR / "solid_colors.aep")
        comp = get_comp(project, "solid_color_green")
        footage = comp.layers[0].source
        assert footage.main_source.color[:3] == [0, 1, 0]

    def test_color_blue(self) -> None:
        project = parse_project(SAMPLES_DIR / "solid_colors.aep")
        comp = get_comp(project, "solid_color_blue")
        footage = comp.layers[0].source
        assert footage.main_source.color[:3] == [0, 0, 1]


class TestAlphaMode:
    """Tests for alpha mode attribute."""

    def test_alphaMode_IGNORE(self) -> None:
        expected = load_expected(SAMPLES_DIR, "alphaMode")
        footage_json = get_footage_from_json_by_name(expected, "alphaMode_IGNORE")
        footage = get_footage(
            parse_project(SAMPLES_DIR / "alphaMode.aep"), "alphaMode_IGNORE"
        )
        assert (
            footage.main_source.alpha_mode
            == footage_json["mainSource"]["alphaMode"]
            == AlphaMode.IGNORE
        )

    def test_alphaMode_STRAIGHT(self) -> None:
        expected = load_expected(SAMPLES_DIR, "alphaMode")
        footage_json = get_footage_from_json_by_name(expected, "alphaMode_STRAIGHT")
        footage = get_footage(
            parse_project(SAMPLES_DIR / "alphaMode.aep"), "alphaMode_STRAIGHT"
        )
        assert (
            footage.main_source.alpha_mode
            == footage_json["mainSource"]["alphaMode"]
            == AlphaMode.STRAIGHT
        )

    def test_alphaMode_PREMULTIPLIED(self) -> None:
        expected = load_expected(SAMPLES_DIR, "alphaMode")
        footage_json = get_footage_from_json_by_name(
            expected, "alphaMode_PREMULTIPLIED"
        )
        footage = get_footage(
            parse_project(SAMPLES_DIR / "alphaMode.aep"), "alphaMode_PREMULTIPLIED"
        )
        assert (
            footage.main_source.alpha_mode
            == footage_json["mainSource"]["alphaMode"]
            == AlphaMode.PREMULTIPLIED
        )


class TestFieldSeparation:
    """Tests for field separation settings."""

    def test_fieldSeparationType_OFF(self) -> None:
        expected = load_expected(SAMPLES_DIR, "fieldSeparationType")
        footage_json = get_footage_from_json_by_name(
            expected, "fieldSeparationType_OFF"
        )
        footage = get_footage(
            parse_project(SAMPLES_DIR / "fieldSeparationType.aep"),
            "fieldSeparationType_OFF",
        )
        assert (
            footage.main_source.field_separation_type
            == footage_json["mainSource"]["fieldSeparationType"]
            == FieldSeparationType.OFF
        )

    def test_fieldSeparationType_UPPER(self) -> None:
        expected = load_expected(SAMPLES_DIR, "fieldSeparationType")
        footage_json = get_footage_from_json_by_name(
            expected, "fieldSeparationType_UPPER"
        )
        footage = get_footage(
            parse_project(SAMPLES_DIR / "fieldSeparationType.aep"),
            "fieldSeparationType_UPPER",
        )
        assert (
            footage.main_source.field_separation_type
            == footage_json["mainSource"]["fieldSeparationType"]
            == FieldSeparationType.UPPER_FIELD_FIRST
        )

    def test_fieldSeparationType_LOWER(self) -> None:
        expected = load_expected(SAMPLES_DIR, "fieldSeparationType")
        footage_json = get_footage_from_json_by_name(
            expected, "fieldSeparationType_LOWER"
        )
        footage = get_footage(
            parse_project(SAMPLES_DIR / "fieldSeparationType.aep"),
            "fieldSeparationType_LOWER",
        )
        assert (
            footage.main_source.field_separation_type
            == footage_json["mainSource"]["fieldSeparationType"]
            == FieldSeparationType.LOWER_FIELD_FIRST
        )

    def test_highQualityFieldSeparation_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "footage_misc")
        footage_json = get_footage_from_json_by_name(
            expected, "highQualityFieldSeparation_true"
        )
        footage = get_footage(
            parse_project(SAMPLES_DIR / "footage_misc.aep"),
            "highQualityFieldSeparation_true",
        )
        assert (
            footage.main_source.high_quality_field_separation
            == footage_json["mainSource"]["highQualityFieldSeparation"]
            is True
        )


class TestFootageSettings:
    """Tests for various footage settings."""

    def test_conformFrameRate_24(self) -> None:
        expected = load_expected(SAMPLES_DIR, "conformFrameRate")
        footage_json = get_footage_from_json_by_name(expected, "conformFrameRate_24")
        footage = get_footage(
            parse_project(SAMPLES_DIR / "conformFrameRate.aep"), "conformFrameRate_24"
        )
        assert (
            footage.main_source.conform_frame_rate
            == footage_json["mainSource"]["conformFrameRate"]
            == 24
        )

    def test_conformFrameRate_30(self) -> None:
        expected = load_expected(SAMPLES_DIR, "conformFrameRate")
        footage_json = get_footage_from_json_by_name(expected, "conformFrameRate_30")
        footage = get_footage(
            parse_project(SAMPLES_DIR / "conformFrameRate.aep"), "conformFrameRate_30"
        )
        assert (
            footage.main_source.conform_frame_rate
            == footage_json["mainSource"]["conformFrameRate"]
            == 30
        )

    def test_conform_frame_rate_2_5(self) -> None:
        footage = get_first_footage(
            parse_project(SAMPLES_DIR / "conform_frame_rate_2.5.aep")
        )
        assert footage is not None
        assert footage.main_source.conform_frame_rate == 2.5

    def test_loop_3(self) -> None:
        expected = load_expected(SAMPLES_DIR, "footage_misc")
        footage_json = get_footage_from_json_by_name(expected, "loop_3")
        footage = get_footage(parse_project(SAMPLES_DIR / "footage_misc.aep"), "loop_3")
        assert footage.main_source.loop == footage_json["mainSource"]["loop"] == 3

    def test_pixelAspect_2(self) -> None:
        project = parse_project(SAMPLES_DIR / "solid_sizes.aep")
        comp = get_comp(project, "solid_pixelAspect_2")
        footage = comp.layers[0].source
        assert math.isclose(footage.pixel_aspect, 2)

    def test_invertAlpha_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "footage_misc")
        footage_json = get_footage_from_json_by_name(expected, "invertAlpha_true")
        footage = get_footage(
            parse_project(SAMPLES_DIR / "footage_misc.aep"), "invertAlpha_true"
        )
        assert (
            footage.main_source.invert_alpha
            == footage_json["mainSource"]["invertAlpha"]
            is True
        )

    def test_premulColor_black(self) -> None:
        expected = load_expected(SAMPLES_DIR, "premulColor")
        footage_json = get_footage_from_json_by_name(expected, "premulColor_black")
        footage = get_footage(
            parse_project(SAMPLES_DIR / "premulColor.aep"), "premulColor_black"
        )
        assert (
            footage.main_source.premul_color
            == footage_json["mainSource"]["premulColor"]
            == [0, 0, 0]
        )

    def test_premulColor_red(self) -> None:
        expected = load_expected(SAMPLES_DIR, "premulColor")
        footage_json = get_footage_from_json_by_name(expected, "premulColor_red")
        footage = get_footage(
            parse_project(SAMPLES_DIR / "premulColor.aep"), "premulColor_red"
        )
        assert footage_json["mainSource"]["premulColor"] == [1, 0, 0]
        assert (
            footage.main_source.premul_color
            == footage_json["mainSource"]["premulColor"]
        )

    def test_name_renamed(self) -> None:
        expected = load_expected(SAMPLES_DIR, "footage_misc")
        footage_json = get_footage_from_json_by_name(expected, "RenamedFootage")
        footage = get_footage(
            parse_project(SAMPLES_DIR / "footage_misc.aep"), "RenamedFootage"
        )
        assert footage.name == footage_json["name"] == "RenamedFootage"


class TestNativeFrameRate:
    """Read-only tests for FootageSource.native_frame_rate."""

    def test_native_frame_rate(self) -> None:
        source = get_footage(
            parse_project(SAMPLES_DIR / "conformFrameRate.aep"), "conformFrameRate_24"
        ).main_source
        assert source.native_frame_rate == 30.0


class TestDisplayFrameRate:
    """Read-only tests for FootageSource.display_frame_rate."""

    def test_display_frame_rate_with_conform(self) -> None:
        source = get_footage(
            parse_project(SAMPLES_DIR / "conformFrameRate.aep"), "conformFrameRate_24"
        ).main_source
        assert source.display_frame_rate == 24.0

    def test_display_frame_rate_without_conform(self) -> None:
        source = get_footage(
            parse_project(SAMPLES_DIR / "footage_misc.aep"), "loop_3"
        ).main_source
        assert source.conform_frame_rate == 0.0
        assert source.display_frame_rate == 30.0

    def test_display_frame_rate_with_pulldown(self) -> None:
        source = get_first_footage(
            parse_project(SAMPLES_DIR / "conform_frame_rate_2.5_uff_wssww.aep")
        ).main_source
        assert source.conform_frame_rate == 2.5
        assert source.display_frame_rate == 2.0

    def test_display_frame_rate_without_pulldown(self) -> None:
        source = get_first_footage(
            parse_project(SAMPLES_DIR / "conform_frame_rate_2.5_uff_off.aep")
        ).main_source
        assert source.conform_frame_rate == 2.5
        assert source.display_frame_rate == 2.5


class TestOverrideMediaColorSpace:
    """Tests for FootageSource.media_color_space."""

    def test_embedded(self) -> None:
        source = get_first_footage(
            parse_project(SAMPLES_DIR / "override_media_colorspace_embedded.aep")
        ).main_source
        assert source.media_color_space == "Embedded"

    def test_custom_profile(self) -> None:
        source = get_first_footage(
            parse_project(SAMPLES_DIR / "override_media_colorspace_apple_rgb.aep")
        ).main_source
        assert source.media_color_space == "Apple RGB"

    def test_working_colorspace(self) -> None:
        source = get_first_footage(
            parse_project(
                SAMPLES_DIR / "override_media_colorspace_working_colorspace_-.aep"
            )
        ).main_source
        assert source.media_color_space == "Working Color Space"

    def test_working_colorspace_aces(self) -> None:
        source = get_first_footage(
            parse_project(
                SAMPLES_DIR
                / "override_media_colorspace_working_colorspace_-aces_cg_or_cct.aep"
            )
        ).main_source
        assert source.media_color_space == "Working Color Space"


class TestHasAudio:
    """Tests for FootageItem.has_audio."""

    def test_footage_with_audio(self) -> None:
        project = parse_project(SAMPLES_DIR / "no_audio.aep")
        footage = next(f for f in project.footages if f.name == "mov_23_976.mov")
        assert footage.has_audio is True

    def test_footage_without_audio(self) -> None:
        project = parse_project(SAMPLES_DIR / "no_audio.aep")
        footage = next(
            f for f in project.footages if f.name == "mov_23_976_no_audio.mov"
        )
        assert footage.has_audio is False


class TestImageSequenceSource:
    """An image-sequence source's `file` joins the folder and first frame
    with the folder's own separator, matching AE's fsName.

    Regression: the join used PurePosixPath unconditionally, so a Windows
    folder produced a mixed-separator path (`...\\assets/sequence_001.gif`).
    That mis-splits under `PurePosixPath.name` on a POSIX host, which broke
    the media-replacement validation on Linux CI while passing on Windows.
    """

    EG_DIR = SAMPLES_DIR.parent / "essential_graphics"

    def test_sequence_file_matches_ground_truth(self) -> None:
        project = parse_project(self.EG_DIR / "media_replacement.aep")
        footage = get_footage(project, "sequence_[001-003].gif")
        expected = load_expected(self.EG_DIR, "media_replacement")
        exp_source = get_footage_from_json_by_name(expected, "sequence_[001-003].gif")[
            "mainSource"
        ]
        # Exact string match against AE's fsName, separators included.
        assert footage.main_source.file == exp_source["filePath"]
        # This sample is Windows-authored: no stray forward slash on any host.
        assert "/" not in footage.main_source.file
