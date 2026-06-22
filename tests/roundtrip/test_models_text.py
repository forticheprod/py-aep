"""Tests for TextDocument and FontObject model parsing and roundtrip."""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import get_comp

from py_aep import parse as parse_aep
from py_aep.enums import (
    AutoKernType,
    BaselineDirection,
    BoxAutoFitPolicy,
    BoxFirstBaselineAlignment,
    BoxVerticalAlignment,
    DigitSet,
    LineJoinType,
    LineOrientation,
    ParagraphDirection,
    ParagraphJustification,
)

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"


def _get_text_document(aep_path: Path, comp_name: str | None = None):
    """Parse and return the first text document from an .aep file."""
    app = parse_aep(aep_path)
    if comp_name:
        comp = get_comp(app.project, comp_name)
    else:
        comp = app.project.compositions[0]
    text_layer = comp.text_layers[0]
    return app.project, text_layer.text.source_text.value


class TestRoundtripFontSize:
    """Roundtrip tests for TextDocument.font_size."""

    def test_modify_font_size(self, tmp_path: Path) -> None:
        project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.font_size == 36.0

        doc.font_size = 72.0
        out = tmp_path / "modified.aep"
        project.save(out)

        _project2, doc2 = _get_text_document(out, "type_text")
        assert doc2.font_size == 72.0


class TestRoundtripFauxBold:
    """Roundtrip tests for TextDocument.faux_bold."""

    def test_enable_faux_bold(self, tmp_path: Path) -> None:
        project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.faux_bold is False

        doc.faux_bold = True
        out = tmp_path / "modified.aep"
        project.save(out)

        _project2, doc2 = _get_text_document(out, "type_text")
        assert doc2.faux_bold is True


class TestRoundtripFillColor:
    """Roundtrip tests for TextDocument.fill_color."""

    def test_modify_fill_color(self, tmp_path: Path) -> None:
        project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")

        doc.fill_color = [1.0, 0.0, 0.0]
        out = tmp_path / "modified.aep"
        project.save(out)

        _project2, doc2 = _get_text_document(out, "type_text")
        assert doc2.fill_color is not None
        assert doc2.fill_color[0] == 1.0
        assert doc2.fill_color[1] == 0.0
        assert doc2.fill_color[2] == 0.0


class TestRoundtripText:
    """Roundtrip tests for TextDocument.text."""

    def test_modify_text(self, tmp_path: Path) -> None:
        project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")

        doc.text = "Modified"
        out = tmp_path / "modified.aep"
        project.save(out)

        _project2, doc2 = _get_text_document(out, "type_text")
        assert doc2.text == "Modified"


class TestRoundtripJustification:
    """Roundtrip tests for TextDocument.justification."""

    def test_modify_justification(self, tmp_path: Path) -> None:
        project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.justification == ParagraphJustification.LEFT_JUSTIFY

        doc.justification = ParagraphJustification.CENTER_JUSTIFY
        out = tmp_path / "modified.aep"
        project.save(out)

        _project2, doc2 = _get_text_document(out, "type_text")
        assert doc2.justification == ParagraphJustification.CENTER_JUSTIFY


class TestRoundtripTracking:
    """Roundtrip tests for TextDocument.tracking."""

    def test_modify_tracking(self, tmp_path: Path) -> None:
        project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")

        doc.tracking = 50.0
        out = tmp_path / "modified.aep"
        project.save(out)

        _project2, doc2 = _get_text_document(out, "type_text")
        assert doc2.tracking == 50.0


class TestRoundtripWiredAttributes:
    """Set -> save -> reparse roundtrip for newly-wired attributes."""

    @pytest.mark.parametrize(
        ("attr", "value"),
        [
            ("tsume", 0.5),
            ("auto_leading", False),
            ("leading", 60.0),
            ("auto_kern_type", AutoKernType.OPTICAL_KERN),
            ("baseline_direction", BaselineDirection.BASELINE_VERTICAL_ROTATED),
            ("ligature", True),
            ("no_break", True),
            ("digit_set", DigitSet.ARABIC_DIGITS),
            ("line_join_type", LineJoinType.LINE_JOIN_ROUND),
            ("direction", ParagraphDirection.DIRECTION_RIGHT_TO_LEFT),
            ("every_line_composer", True),
            ("line_orientation", LineOrientation.VERTICAL_RIGHT_TO_LEFT),
        ],
    )
    def test_roundtrip(self, tmp_path: Path, attr: str, value: object) -> None:
        project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        setattr(doc, attr, value)
        out = tmp_path / "modified.aep"
        project.save(out)

        _project2, doc2 = _get_text_document(out, "type_text")
        assert getattr(doc2, attr) == value


class TestBoxText:
    """Box (paragraph) text attributes via point->box conversion + roundtrip."""

    def test_convert_point_to_box(self, tmp_path: Path) -> None:
        project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.point_text is True
        assert doc.box_text_size is None

        doc.box_text_size = [320.0, 180.0]
        assert doc.box_text is True
        out = tmp_path / "box.aep"
        project.save(out)

        _p2, doc2 = _get_text_document(out, "type_text")
        assert doc2.box_text is True
        assert doc2.box_text_size == [320.0, 180.0]

    def test_box_text_pos_requires_box(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        with pytest.raises(ValueError, match="box text"):
            doc.box_text_pos = [10.0, 20.0]

    @pytest.mark.parametrize(
        ("attr", "value"),
        [
            ("box_text_size", [240.0, 120.0]),
            ("box_text_pos", [15.0, 25.0]),
            ("box_inset_spacing", 4.0),
            ("box_vertical_alignment", BoxVerticalAlignment.CENTER),
            ("box_vertical_alignment", BoxVerticalAlignment.JUSTIFY),
            ("box_auto_fit_policy", BoxAutoFitPolicy.HEIGHT_BASELINE),
            ("box_first_baseline_alignment", BoxFirstBaselineAlignment.CAP_HEIGHT),
            (
                "box_first_baseline_alignment",
                BoxFirstBaselineAlignment.MINIMUM_VALUE_ROMAN,
            ),
            ("box_first_baseline_alignment_minimum", 7.0),
        ],
    )
    def test_box_attr_roundtrip(self, tmp_path: Path, attr: str, value: object) -> None:
        project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        doc.box_text_size = [300.0, 150.0]  # convert to box first
        setattr(doc, attr, value)
        out = tmp_path / "box.aep"
        project.save(out)

        _p2, doc2 = _get_text_document(out, "type_text")
        assert getattr(doc2, attr) == value


class TestRegisterFont:
    """Regression: setting a font absent from the document registers it.

    The new font entry's `99` type tag must be a COS name (`/CoolTypeFont`),
    matching how AE and the parser represent it, not a plain string.
    """

    def test_new_font_tag_is_cos_name(self) -> None:
        from py_aep.cos import CosName

        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        doc.font = "Arial-BoldMT"  # not in the template -> _register_font
        new_entry = doc._cos_data["0"]["1"]["0"][-1]
        assert isinstance(new_entry["0"]["99"], CosName)

    def test_new_font_roundtrips(self, tmp_path: Path) -> None:
        project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        doc.font = "Arial-BoldMT"
        out = tmp_path / "out.aep"
        project.save(out)

        _project2, doc2 = _get_text_document(out, "type_text")
        assert doc2.font == "Arial-BoldMT"


class TestColorAndLeadingNone:
    """Setting fill/stroke color or leading to `None` clears, not raises.

    Regression: the setters validated unconditionally, so the documented
    `None` branch (popping the COS char-style key) raised TypeError.
    """

    def test_fill_color_none_pops_cos_key(self, tmp_path: Path) -> None:
        project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.fill_color is not None

        doc.fill_color = None
        assert doc._char_style is not None
        assert "53" not in doc._char_style
        assert doc.fill_color is None

        out = tmp_path / "modified.aep"
        project.save(out)
        _project2, doc2 = _get_text_document(out, "type_text")
        assert doc2.fill_color is None

    def test_stroke_color_none_pops_cos_key(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")
        assert doc.stroke_color is not None

        doc.stroke_color = None
        assert doc._char_style is not None
        assert "54" not in doc._char_style
        assert doc.stroke_color is None

    def test_leading_none_does_not_raise(self) -> None:
        _project, doc = _get_text_document(SAMPLES_DIR / "type.aep", "type_text")

        doc.leading = None
        # The explicit-leading branch is skipped; auto-leading still
        # resolves the displayed value (font_size * 1.2).
        assert doc.leading == pytest.approx(43.2)
