"""Tests for TextDocument and FontObject model parsing and roundtrip."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import get_comp

from py_aep import parse as parse_aep
from py_aep.enums import (
    AutoKernType,
    BaselineDirection,
    DigitSet,
    FontBaselineOption,
    FontCapsOption,
    LeadingType,
    LineJoinType,
    LineOrientation,
    ParagraphDirection,
    ParagraphJustification,
)

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"
TEXT_SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "text"


def _get_text_document(aep_path: Path, comp_name: str | None = None):
    """Parse and return the first text document from an .aep file."""
    app = parse_aep(aep_path)
    if comp_name:
        comp = get_comp(app.project, comp_name)
    else:
        comp = app.project.compositions[0]
    text_layer = comp.text_layers[0]
    return app.project, text_layer.text.source_text.value


class TestBoxOverflow:
    """box_overflow derived from the persisted layout cache."""

    def _doc(self, layer_name: str):
        app = parse_aep(TEXT_SAMPLES_DIR / "box_overflow.aep")
        comp = app.project.compositions[0]
        layer = next(ly for ly in comp.text_layers if ly.name == layer_name)
        return layer.text.source_text.value

    def test_overflowing_box(self) -> None:
        assert self._doc("BoxOverflows").box_overflow is True

    def test_fitting_box(self) -> None:
        assert self._doc("BoxFits").box_overflow is False

    def test_point_text_reads_none(self) -> None:
        # ExtendScript reads undefined for point text.
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.box_overflow is None


class TestTextDocumentParsing:
    """Tests for TextDocument lazy COS field access."""

    def test_text(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.text == "TextLayer"

    def test_font(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.font == "TimesNewRomanPSMT"

    def test_font_size(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.font_size == 36.0

    def test_fill_color(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.fill_color is not None
        assert len(doc.fill_color) == 3
        assert all(isinstance(c, float) for c in doc.fill_color)

    def test_stroke_color(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.stroke_color is not None
        assert doc.stroke_color == [0.0, 0.0, 0.0]

    def test_faux_bold(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.faux_bold is False

    def test_faux_italic(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.faux_italic is False

    def test_tracking(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.tracking is not None

    def test_justification(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.justification == ParagraphJustification.LEFT_JUSTIFY

    def test_font_caps_option(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.font_caps_option == FontCapsOption.FONT_NORMAL_CAPS

    def test_font_baseline_option(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.font_baseline_option == FontBaselineOption.FONT_NORMAL_BASELINE

    def test_derived_all_caps(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.all_caps is False

    def test_derived_small_caps(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.small_caps is False

    def test_derived_superscript(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.superscript is False

    def test_derived_subscript(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.subscript is False

    def test_paragraph_count(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.paragraph_count == 1

    def test_auto_leading(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.auto_leading is True

    def test_auto_hyphenate(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.auto_hyphenate is True

    def test_every_line_composer(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.every_line_composer is False

    def test_hanging_roman(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.hanging_roman is False

    def test_auto_kern_type(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.auto_kern_type == AutoKernType.METRIC_KERN

    def test_leading_type(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.leading_type == LeadingType.ROMAN_LEADING_TYPE

    def test_apply_fill(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.apply_fill is True

    def test_apply_stroke(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.apply_stroke is False


class TestFontObject:
    """Tests for FontObject COS field access."""

    def test_post_script_name(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.font_object is not None
        assert doc.font_object.post_script_name == "TimesNewRomanPSMT"

    def test_version(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.font_object is not None
        assert doc.font_object.version == "Version 7.00"


class TestTextDocumentWiredAttributes:
    """Read tests for attributes wired to COS keys in this change.

    Expected values for `type.aep` were validated against ExtendScript.
    """

    def test_baseline_direction(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.baseline_direction == BaselineDirection.BASELINE_WITH_STREAM

    def test_ligature(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.ligature is False

    def test_no_break(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.no_break is False

    def test_digit_set(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.digit_set == DigitSet.DEFAULT_DIGITS

    def test_line_join_type(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.line_join_type == LineJoinType.LINE_JOIN_MITER

    def test_direction(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.direction == ParagraphDirection.DIRECTION_LEFT_TO_RIGHT

    def test_line_orientation(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.line_orientation == LineOrientation.HORIZONTAL

    def test_tsume(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.tsume == 0.0

    def test_kerning(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.kerning == 0

    def test_leading_auto(self) -> None:
        # Auto-leading on: leading == font_size * 1.2 (43.2 for 36px).
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.auto_leading is True
        assert doc.leading == pytest.approx(43.2)
