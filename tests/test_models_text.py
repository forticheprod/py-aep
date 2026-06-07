"""Tests for TextDocument and FontObject model parsing and roundtrip."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import get_comp

from py_aep import parse as parse_aep
from py_aep.enums import (
    AutoKernType,
    BaselineDirection,
    BoxAutoFitPolicy,
    BoxFirstBaselineAlignment,
    BoxVerticalAlignment,
    DigitSet,
    FontBaselineOption,
    FontCapsOption,
    LeadingType,
    LineJoinType,
    LineOrientation,
    ParagraphDirection,
    ParagraphJustification,
    PropertyValueType,
)
from py_aep.parsers import specialized_properties

SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "models" / "layer"


def _get_text_document(aep_path: Path, comp_name: str | None = None):
    """Parse and return the first text document from an .aep file."""
    app = parse_aep(aep_path)
    if comp_name:
        comp = get_comp(app.project, comp_name)
    else:
        comp = app.project.compositions[0]
    text_layer = comp.text_layers[0]
    return app.project, text_layer.text.source_text.value


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


class TestParseTextDocument:
    """Unit tests for Source Text property parsing fallbacks."""

    def test_ignores_malformed_cos_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Malformed COS data should keep the property but skip the value."""
        prop = SimpleNamespace(
            keyframes=[],
            value=None,
            _property_value_type=None,
        )
        tdbs_chunk = SimpleNamespace(chunks=[])
        btdk_chunk = SimpleNamespace(data=b"bad")
        root_chunk = SimpleNamespace(chunks=[])

        def fake_find_by_list_type(*, chunks: object, list_type: str):
            if list_type == "tdbs":
                return tdbs_chunk
            if list_type == "btdk":
                return btdk_chunk
            raise AssertionError(f"Unexpected list_type: {list_type}")

        class BrokenCosParser:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

            def parse(self) -> dict[str, object]:
                raise SyntaxError("bad COS")

        monkeypatch.setattr(
            specialized_properties,
            "find_by_list_type",
            fake_find_by_list_type,
        )
        monkeypatch.setattr(
            specialized_properties,
            "parse_property",
            lambda **_kwargs: prop,
        )
        monkeypatch.setattr(
            specialized_properties,
            "CosParser",
            BrokenCosParser,
        )

        result = specialized_properties.parse_text_document(
            btds_chunk=root_chunk,
            match_name="ADBE Text Document",
            property_depth=0,
            composition=SimpleNamespace(),
            tdmn=SimpleNamespace(),
        )

        assert result is prop
        assert prop._property_value_type == PropertyValueType.TEXT_DOCUMENT
        assert prop.value is None

    def test_raises_unexpected_cos_errors(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Unexpected bugs in COS conversion should still surface."""
        prop = SimpleNamespace(
            keyframes=[],
            value=None,
            _property_value_type=None,
        )
        tdbs_chunk = SimpleNamespace(chunks=[])
        btdk_chunk = SimpleNamespace(data=b"ok")
        root_chunk = SimpleNamespace(chunks=[])

        def fake_find_by_list_type(*, chunks: object, list_type: str):
            if list_type == "tdbs":
                return tdbs_chunk
            if list_type == "btdk":
                return btdk_chunk
            raise AssertionError(f"Unexpected list_type: {list_type}")

        class ValidCosParser:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

            def parse(self) -> dict[str, object]:
                return {}

        def raise_runtime_error(*_args: object, **_kwargs: object) -> object:
            raise RuntimeError("boom")

        monkeypatch.setattr(
            specialized_properties,
            "find_by_list_type",
            fake_find_by_list_type,
        )
        monkeypatch.setattr(
            specialized_properties,
            "parse_property",
            lambda **_kwargs: prop,
        )
        monkeypatch.setattr(
            specialized_properties,
            "CosParser",
            ValidCosParser,
        )
        monkeypatch.setattr(
            specialized_properties,
            "parse_btdk_cos",
            raise_runtime_error,
        )

        with pytest.raises(RuntimeError, match="boom"):
            specialized_properties.parse_text_document(
                btds_chunk=root_chunk,
                match_name="ADBE Text Document",
                property_depth=0,
                composition=SimpleNamespace(),
                tdmn=SimpleNamespace(),
            )


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
