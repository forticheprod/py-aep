"""Tests for FootageItem model parsing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from helpers import (
    get_comp,
    get_first_footage,
    get_footage,
    parse_project_fresh,
)

from py_aep import (
    AlphaMode,
    FieldSeparationType,
    LinearLightMode,
    PulldownPhase,
)
from py_aep import parse as parse_aep
from py_aep.color.envelope import build_ocio_colorspace_envelope
from py_aep.color.icc import default_icc_directories
from py_aep.enums.mappings import profile_id_for_name

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "footage"
# Adobe-CMS ICC embedding needs the installed Adobe Color profiles on disk.
_ICC_AVAILABLE = any(d.is_dir() for d in default_icc_directories())


class TestRoundtripLoop:
    """Roundtrip tests for FootageSource.loop."""

    def test_modify_loop(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "footage_misc.aep").project
        footage = get_footage(project, "loop_3")
        source = footage.main_source
        assert source.loop == 3

        source.loop = 5
        out = tmp_path / "modified.aep"
        project.save(out)
        source2 = get_footage(parse_aep(out).project, "loop_3").main_source
        assert source2.loop == 5

    def test_loop_validation_rejects_zero(self) -> None:
        source = get_footage(
            parse_project_fresh(SAMPLES_DIR / "footage_misc.aep"), "loop_3"
        ).main_source
        with pytest.raises(ValueError, match="must be >= 1"):
            source.loop = 0

    def test_loop_validation_rejects_too_high(self) -> None:
        source = get_footage(
            parse_project_fresh(SAMPLES_DIR / "footage_misc.aep"), "loop_3"
        ).main_source
        with pytest.raises(ValueError, match="must be <= 9999"):
            source.loop = 10000


class TestRoundtripInvertAlpha:
    """Roundtrip tests for FootageSource.invert_alpha."""

    def test_modify_invert_alpha(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "footage_misc.aep").project
        footage = get_footage(project, "invertAlpha_true")
        source = footage.main_source
        assert source.invert_alpha is True

        source.invert_alpha = False
        out = tmp_path / "modified.aep"
        project.save(out)
        source2 = get_footage(parse_aep(out).project, "invertAlpha_true").main_source
        assert source2.invert_alpha is False


class TestRoundtripHighQualityFieldSeparation:
    """Roundtrip tests for FootageSource.high_quality_field_separation."""

    def test_modify_high_quality_field_separation(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "footage_misc.aep").project
        footage = get_footage(project, "highQualityFieldSeparation_true")
        source = footage.main_source
        assert source.high_quality_field_separation is True

        source.high_quality_field_separation = False
        out = tmp_path / "modified.aep"
        project.save(out)
        source2 = get_footage(
            parse_aep(out).project, "highQualityFieldSeparation_true"
        ).main_source
        assert source2.high_quality_field_separation is False


class TestRoundtripAlphaMode:
    """Roundtrip tests for FootageSource.alpha_mode."""

    def test_modify_alpha_mode_straight_to_premultiplied(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "alphaMode.aep").project
        footage = get_footage(project, "alphaMode_STRAIGHT")
        source = footage.main_source
        assert source.alpha_mode == AlphaMode.STRAIGHT

        source.alpha_mode = AlphaMode.PREMULTIPLIED
        out = tmp_path / "modified.aep"
        project.save(out)
        source2 = get_footage(parse_aep(out).project, "alphaMode_STRAIGHT").main_source
        assert source2.alpha_mode == AlphaMode.PREMULTIPLIED

    def test_modify_alpha_mode_to_ignore(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "alphaMode.aep").project
        footage = get_footage(project, "alphaMode_STRAIGHT")
        source = footage.main_source

        source.alpha_mode = AlphaMode.IGNORE
        out = tmp_path / "modified.aep"
        project.save(out)
        source2 = get_footage(parse_aep(out).project, "alphaMode_STRAIGHT").main_source
        assert source2.alpha_mode == AlphaMode.IGNORE

    def test_alpha_mode_validation_rejects_invalid(self) -> None:
        source = get_footage(
            parse_project_fresh(SAMPLES_DIR / "alphaMode.aep"), "alphaMode_STRAIGHT"
        ).main_source
        with pytest.raises(ValueError, match="Invalid value.*alpha_mode"):
            source.alpha_mode = 999  # type: ignore[assignment]


class TestRoundtripFieldSeparationType:
    """Roundtrip tests for FootageSource.field_separation_type."""

    def test_modify_field_separation_upper_to_lower(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "fieldSeparationType.aep").project
        footage = get_footage(project, "fieldSeparationType_UPPER")
        source = footage.main_source
        assert source.field_separation_type == FieldSeparationType.UPPER_FIELD_FIRST

        source.field_separation_type = FieldSeparationType.LOWER_FIELD_FIRST
        out = tmp_path / "modified.aep"
        project.save(out)
        source2 = get_footage(
            parse_aep(out).project, "fieldSeparationType_UPPER"
        ).main_source
        assert source2.field_separation_type == FieldSeparationType.LOWER_FIELD_FIRST

    def test_modify_field_separation_to_off(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "fieldSeparationType.aep").project
        footage = get_footage(project, "fieldSeparationType_UPPER")
        source = footage.main_source

        source.field_separation_type = FieldSeparationType.OFF
        out = tmp_path / "modified.aep"
        project.save(out)
        source2 = get_footage(
            parse_aep(out).project, "fieldSeparationType_UPPER"
        ).main_source
        assert source2.field_separation_type == FieldSeparationType.OFF

    def test_field_separation_type_validation_rejects_invalid(self) -> None:
        source = get_footage(
            parse_project_fresh(SAMPLES_DIR / "fieldSeparationType.aep"),
            "fieldSeparationType_UPPER",
        ).main_source
        with pytest.raises(ValueError, match="is not a valid FieldSeparationType"):
            source.field_separation_type = "invalid"  # type: ignore[assignment]


class TestRoundtripPremulColor:
    """Roundtrip tests for FootageSource.premul_color."""

    def test_modify_premul_color(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "premulColor.aep").project
        footage = get_footage(project, "premulColor_red")
        source = footage.main_source

        source.premul_color = [0.0, 1.0, 0.5]
        out = tmp_path / "modified.aep"
        project.save(out)
        source2 = get_footage(parse_aep(out).project, "premulColor_red").main_source
        assert math.isclose(source2.premul_color[0], 0.0, abs_tol=0.005)
        assert math.isclose(source2.premul_color[1], 1.0, abs_tol=0.005)
        assert math.isclose(source2.premul_color[2], 0.5, abs_tol=0.02)

    def test_premul_color_validation_rejects_bad_length(self) -> None:
        source = get_footage(
            parse_project_fresh(SAMPLES_DIR / "premulColor.aep"), "premulColor_red"
        ).main_source
        with pytest.raises(ValueError, match="expected 3 elements"):
            source.premul_color = [0.1, 0.2]

    def test_premul_color_validation_rejects_out_of_range(self) -> None:
        source = get_footage(
            parse_project_fresh(SAMPLES_DIR / "premulColor.aep"), "premulColor_red"
        ).main_source
        with pytest.raises(ValueError, match="must be <= 1.0"):
            source.premul_color = [1.5, 0.0, 0.0]


class TestRoundtripConformFrameRate:
    """Roundtrip tests for FootageSource.conform_frame_rate."""

    def test_modify_conform_frame_rate(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "conformFrameRate.aep").project
        footage = get_footage(project, "conformFrameRate_30")
        source = footage.main_source
        assert source.conform_frame_rate == 30.0

        source.conform_frame_rate = 24.0
        out = tmp_path / "modified.aep"
        project.save(out)
        source2 = get_footage(parse_aep(out).project, "conformFrameRate_30").main_source
        assert source2.conform_frame_rate == 24.0

    def test_modify_conform_frame_rate_to_zero(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "conformFrameRate.aep").project
        footage = get_footage(project, "conformFrameRate_30")
        source = footage.main_source

        source.conform_frame_rate = 0.0
        out = tmp_path / "modified.aep"
        project.save(out)
        source2 = get_footage(parse_aep(out).project, "conformFrameRate_30").main_source
        assert source2.conform_frame_rate == 0.0

    def test_modify_conform_frame_rate_fractional(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "conform_frame_rate_2.5.aep").project
        footage = project.footages[0]
        source = footage.main_source
        assert source.conform_frame_rate == 2.5

        source.conform_frame_rate = 29.97
        out = tmp_path / "modified.aep"
        project.save(out)
        source2 = parse_aep(out).project.footages[0].main_source
        assert math.isclose(source2.conform_frame_rate, 29.97, rel_tol=1e-4)

    def test_conform_frame_rate_validation_rejects_negative(self) -> None:
        source = get_footage(
            parse_project_fresh(SAMPLES_DIR / "conformFrameRate.aep"),
            "conformFrameRate_30",
        ).main_source
        with pytest.raises(ValueError, match="must be >= 0"):
            source.conform_frame_rate = -1.0

    def test_conform_frame_rate_validation_rejects_too_high(self) -> None:
        source = get_footage(
            parse_project_fresh(SAMPLES_DIR / "conformFrameRate.aep"),
            "conformFrameRate_30",
        ).main_source
        with pytest.raises(ValueError, match="must be <= 999"):
            source.conform_frame_rate = 1000.0


class TestRemovePulldown:
    """Roundtrip tests for FootageSource.remove_pulldown."""

    def test_read_off(self) -> None:
        source = get_first_footage(
            parse_project_fresh(SAMPLES_DIR / "conform_frame_rate_2.5_uff_off.aep")
        ).main_source
        assert source.remove_pulldown == PulldownPhase.OFF

    def test_read_wssww(self) -> None:
        source = get_first_footage(
            parse_project_fresh(SAMPLES_DIR / "conform_frame_rate_2.5_uff_wssww.aep")
        ).main_source
        assert source.remove_pulldown == PulldownPhase.WSSWW

    def test_read_sswww(self) -> None:
        source = get_first_footage(
            parse_project_fresh(SAMPLES_DIR / "conform_frame_rate_2.5_uff_sswww.aep")
        ).main_source
        assert source.remove_pulldown == PulldownPhase.SSWWW

    def test_read_wwwsw_24p(self) -> None:
        source = get_first_footage(
            parse_project_fresh(SAMPLES_DIR / "conform_frame_rate_2.5_uff_wwwsw.aep")
        ).main_source
        assert source.remove_pulldown == PulldownPhase.WWWSW_24P_ADVANCE

    def test_modify_pulldown(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "conform_frame_rate_2.5_uff_off.aep").project
        source = project.footages[0].main_source
        assert source.remove_pulldown == PulldownPhase.OFF

        source.remove_pulldown = PulldownPhase.WSSWW
        out = tmp_path / "out.aep"
        project.save(out)
        source2 = parse_aep(out).project.footages[0].main_source
        assert source2.remove_pulldown == PulldownPhase.WSSWW

    def test_modify_pulldown_updates_display_frame_rate(self) -> None:
        source = get_first_footage(
            parse_project_fresh(SAMPLES_DIR / "conform_frame_rate_2.5_uff_off.aep")
        ).main_source
        assert source.display_frame_rate == 2.5
        source.remove_pulldown = PulldownPhase.WSSWW
        assert source.display_frame_rate == 2.0


class TestInterpretAsLinearLight:
    """Tests for FootageSource.interpret_as_linear_light."""

    def test_off(self) -> None:
        source = get_first_footage(
            parse_project_fresh(SAMPLES_DIR / "interpret_as_linear_light_off.aep")
        ).main_source
        assert source.interpret_as_linear_light == LinearLightMode.OFF

    def test_on(self) -> None:
        source = get_first_footage(
            parse_project_fresh(SAMPLES_DIR / "interpret_as_linear_light_on.aep")
        ).main_source
        assert source.interpret_as_linear_light == LinearLightMode.ON

    def test_on_for_32_bpc(self) -> None:
        source = get_first_footage(
            parse_project_fresh(
                SAMPLES_DIR / "interpret_as_linear_light_on_for_32_bpc.aep"
            )
        ).main_source
        assert source.interpret_as_linear_light == LinearLightMode.ON_FOR_32BPC

    def test_is_writable(self) -> None:
        source = get_first_footage(
            parse_project_fresh(SAMPLES_DIR / "interpret_as_linear_light_off.aep")
        ).main_source
        source.interpret_as_linear_light = LinearLightMode.ON
        assert source.interpret_as_linear_light == LinearLightMode.ON

    def test_modify_roundtrip(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "interpret_as_linear_light_off.aep").project
        source = get_first_footage(project).main_source
        assert source.interpret_as_linear_light == LinearLightMode.OFF

        source.interpret_as_linear_light = LinearLightMode.ON
        out = tmp_path / "modified.aep"
        project.save(out)
        source2 = get_first_footage(parse_aep(out).project).main_source
        assert source2.interpret_as_linear_light == LinearLightMode.ON


class TestPreserveRgb:
    """Tests for FootageSource.preserve_rgb."""

    def test_on(self) -> None:
        source = get_first_footage(
            parse_project_fresh(SAMPLES_DIR / "preserve_rgb_on.aep")
        ).main_source
        assert source.preserve_rgb is True

    def test_off(self) -> None:
        source = get_first_footage(
            parse_project_fresh(SAMPLES_DIR / "preserve_rgb_off.aep")
        ).main_source
        assert source.preserve_rgb is False

    def test_is_writable(self) -> None:
        source = get_first_footage(
            parse_project_fresh(SAMPLES_DIR / "preserve_rgb_on.aep")
        ).main_source
        source.preserve_rgb = False
        assert source.preserve_rgb is False


class TestRoundtripSolidColor:
    """Roundtrip tests for SolidSource.color."""

    def test_modify_color(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "solid_colors.aep").project
        comp = get_comp(project, "solid_color_red")
        source = comp.layers[0].source.main_source

        # Modify
        source.color = [0.1, 0.2, 0.3]

        # Save and re-parse
        out = tmp_path / "modified_solid.aep"
        project.save(out)
        re_project = parse_aep(out).project
        source2 = get_comp(re_project, "solid_color_red").layers[0].source.main_source

        assert math.isclose(source2.color[0], 0.1, abs_tol=0.005)
        assert math.isclose(source2.color[1], 0.2, abs_tol=0.005)
        assert math.isclose(source2.color[2], 0.3, abs_tol=0.005)

    def test_validation_rejects_bad_length(self) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "solid_colors.aep")
        source = get_comp(project, "solid_color_red").layers[0].source.main_source
        with pytest.raises(ValueError, match="expected 3 elements"):
            source.color = [0.1, 0.2]

    def test_validation_rejects_out_of_range(self) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "solid_colors.aep")
        source = get_comp(project, "solid_color_red").layers[0].source.main_source
        with pytest.raises(ValueError, match="must be <= 1.0"):
            source.color = [1.5, 0.0, 0.0]


class TestRoundtripMediaColorSpace:
    """Roundtrip tests for FootageSource.media_color_space."""

    def _first_source(self, project):  # type: ignore[no-untyped-def]
        item = get_first_footage(project)
        assert item is not None
        return item.main_source

    def test_set_ocio_colorspace(self, tmp_path: Path) -> None:
        project = parse_aep(
            SAMPLES_DIR / "override_media_colorspace_embedded.aep"
        ).project
        self._first_source(project).media_color_space = "ACEScg"

        out = tmp_path / "modified.aep"
        project.save(out)
        source2 = self._first_source(parse_aep(out).project)
        assert source2.media_color_space == "ACEScg"
        # ocsp envelope is byte-exact AE output.
        ocsp = source2._ocsp_utf8()
        assert ocsp is not None
        assert ocsp.value == build_ocio_colorspace_envelope("ACEScg")

    def test_set_working_color_space(self, tmp_path: Path) -> None:
        project = parse_aep(
            SAMPLES_DIR / "override_media_colorspace_embedded.aep"
        ).project
        self._first_source(project).media_color_space = "Working Color Space"

        out = tmp_path / "modified.aep"
        project.save(out)
        source2 = self._first_source(parse_aep(out).project)
        assert source2.media_color_space == "Working Color Space"
        # AE-fidelity (verified via aep-compare): the ocsp envelope is emptied.
        ocsp = source2._ocsp_utf8()
        assert ocsp is not None and ocsp.value == ""

    def test_set_embedded_reverts_override(self, tmp_path: Path) -> None:
        # Start from an Apple RGB override, set back to Embedded.
        project = parse_aep(
            SAMPLES_DIR / "override_media_colorspace_apple_rgb.aep"
        ).project
        source = self._first_source(project)
        assert source.media_color_space == "Apple RGB"
        source.media_color_space = "Embedded"

        out = tmp_path / "modified.aep"
        project.save(out)
        source2 = self._first_source(parse_aep(out).project)
        assert source2.media_color_space == "Embedded"

    def test_set_ocio_then_back_to_embedded(self, tmp_path: Path) -> None:
        project = parse_aep(
            SAMPLES_DIR / "override_media_colorspace_embedded.aep"
        ).project
        source = self._first_source(project)
        source.media_color_space = "ACEScg"
        assert source.media_color_space == "ACEScg"
        source.media_color_space = "Embedded"

        out = tmp_path / "modified.aep"
        project.save(out)
        assert (
            self._first_source(parse_aep(out).project).media_color_space == "Embedded"
        )

    @pytest.mark.skipif(not _ICC_AVAILABLE, reason="Adobe ICC profiles not installed")
    def test_set_adobe_profile(self, tmp_path: Path) -> None:
        project = parse_aep(
            SAMPLES_DIR / "override_media_colorspace_embedded.aep"
        ).project
        self._first_source(project).media_color_space = "Apple RGB"

        out = tmp_path / "modified.aep"
        project.save(out)
        source2 = self._first_source(parse_aep(out).project)
        assert source2.media_color_space == "Apple RGB"
        # apid is the catalogued ICC profile ID (matches AE ground truth).
        apid = next(c for c in source2._clrs.chunks if c.chunk_type == "apid")
        assert apid.data == profile_id_for_name("Apple RGB")
