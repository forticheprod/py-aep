"""Tests for TextDocument and FontObject model parsing and roundtrip."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import get_comp

from py_aep import parse as parse_aep
from py_aep.enums import (
    AutoKernType,
    FontBaselineOption,
    FontCapsOption,
    LeadingType,
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
        assert doc.auto_kern_type == AutoKernType.NO_AUTO_KERN

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
        tdbs_chunk = SimpleNamespace(body=SimpleNamespace(chunks=[]))
        btdk_chunk = SimpleNamespace(body=SimpleNamespace(binary_data=b"bad"))
        root_chunk = SimpleNamespace(body=SimpleNamespace(chunks=[]))

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
        tdbs_chunk = SimpleNamespace(body=SimpleNamespace(chunks=[]))
        btdk_chunk = SimpleNamespace(body=SimpleNamespace(binary_data=b"ok"))
        root_chunk = SimpleNamespace(body=SimpleNamespace(chunks=[]))

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
            )
