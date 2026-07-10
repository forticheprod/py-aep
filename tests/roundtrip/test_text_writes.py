"""Byte-parity harness for the text-range write engine (phase W1).

Each test replays one write operation from
`scripts/jsx/generate_text_write_samples.jsx` on a pristine base document
and compares py_aep's resulting btdk COS tree byte-for-byte against the
layer AE produced for the same operation in
`samples/models/text/text_writes.aep`. The `/PC` layout cache
(`doc["1"]["2"]`) is masked on both sides: AE recomposes it on apply,
py_aep must leave it untouched.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from helpers import parse_app_fresh

from py_aep.cos import serialize
from py_aep.cos.cos import CosParser  # noqa: F401  (documents the data source)
from py_aep.enums import AutoKernType, ParagraphJustification
from py_aep.svg.fonts import font_version_string

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "text"
FIXTURE = SAMPLES_DIR / "text_writes.aep"
PROBE = SAMPLES_DIR / "text_writes_probe.json"
FIXTURE2 = SAMPLES_DIR / "text_writes2.aep"
PROBE2 = SAMPLES_DIR / "text_writes2_probe.json"


def _doc_for(app, layer_name: str):
    comp = app.project.compositions[0]
    layer = next(ly for ly in comp.text_layers if ly.name == layer_name)
    return layer.text.source_text.value


def _base_doc(base_text: str | None = None):
    """A pristine single-run document (the fixture's untouched W_NOOP...

    ...layer is byte-equal to a freshly added text layer). Setting a
    different base text goes through the py text setter, which collapses
    runs exactly like AE's `addText` produces them.
    """
    app = parse_app_fresh(FIXTURE)
    doc = _doc_for(app, "W_NOOP")
    if base_text is not None:
        doc.text = base_text
    return app, doc


def _masked_bytes(cos_data: dict) -> bytes:
    clone = copy.deepcopy(cos_data)
    for doc in clone.get("1", {}).get("1", []) or []:
        if isinstance(doc.get("1"), dict):
            doc["1"].pop("2", None)
    return serialize(clone)


@pytest.fixture(scope="module")
def probe() -> dict:
    with open(PROBE, encoding="utf-8") as fp:
        return json.load(fp)


@pytest.fixture(scope="module")
def fixture_app():
    """Read-only view of the AE fixture for expected-side data."""
    return parse_app_fresh(FIXTURE)


@pytest.fixture(scope="module")
def probe2() -> dict:
    with open(PROBE2, encoding="utf-8") as fp:
        return json.load(fp)


@pytest.fixture(scope="module")
def fixture2_app():
    """Read-only view of the phase-2 AE fixture."""
    return parse_app_fresh(FIXTURE2)


def _assert_alias_integrity(doc) -> None:
    """The F1 invariant: `_char_style` must be the live first-run style."""
    first = doc._doc["0"]["6"]["0"][0]["0"]["0"]["6"]
    assert doc._char_style is first


def _assert_byte_parity(py_doc, fixture_app, op_name: str) -> None:
    expected = _doc_for(fixture_app, op_name)
    assert _masked_bytes(py_doc._cos_data) == _masked_bytes(expected._cos_data), (
        f"{op_name}: py-written btdk diverges from the AE fixture "
        f"(outside the masked /PC cache)"
    )


PER_CHAR_MAP = {
    "fontSize": "font_size",
    "applyFill": "apply_fill",
    "applyStroke": "apply_stroke",
    "justification": "justification",
    "autoLeading": "auto_leading",
    "fillColor": "fill_color",
    "strokeColor": "stroke_color",
    "leading": "leading",
    "font": "font",
    "kerning": "kerning",
    "autoKernType": "auto_kern_type",
}


def _assert_per_char(py_doc, probe: dict, op_name: str, attrs: list[str]) -> None:
    expected_chars = probe["ops"][op_name]["perChar"]
    n = len(py_doc.text)
    assert n == len(expected_chars)
    for i in range(n):
        rng = py_doc.character_range(i, i + 1)
        for es_attr in attrs:
            expected = expected_chars[i][es_attr]
            actual = getattr(rng, PER_CHAR_MAP[es_attr])
            if expected == "<<undefined>>":
                assert actual is None, f"{op_name}[{i}].{es_attr}: {actual!r}"
            elif isinstance(expected, list):
                assert actual == pytest.approx(expected, abs=1e-5), (
                    f"{op_name}[{i}].{es_attr}: expected {expected!r}, got {actual!r}"
                )
            else:
                assert actual == expected, (
                    f"{op_name}[{i}].{es_attr}: expected {expected!r}, got {actual!r}"
                )


class TestScalarWrites:
    def test_split(self, fixture_app, probe) -> None:
        _app, doc = _base_doc()
        doc.character_range(3, 7).font_size = 72
        _assert_alias_integrity(doc)
        _assert_byte_parity(doc, fixture_app, "W_SPLIT")
        _assert_per_char(doc, probe, "W_SPLIT", ["fontSize"])

    def test_adjacent_equal_writes_merge(self, fixture_app, probe) -> None:
        _app, doc = _base_doc()
        doc.character_range(0, 5).font_size = 72
        doc.character_range(5, 10).font_size = 72
        _assert_alias_integrity(doc)
        # AE coalesced this into a single run covering the terminator.
        assert len(doc._doc["0"]["6"]["0"]) == 1
        _assert_byte_parity(doc, fixture_app, "W_MERGE_SAME")
        _assert_per_char(doc, probe, "W_MERGE_SAME", ["fontSize"])

    def test_noop_write_keeps_structure(self, fixture_app, probe) -> None:
        _app, doc = _base_doc()
        doc.character_range(2, 8).font_size = 36
        _assert_alias_integrity(doc)
        assert len(doc._doc["0"]["6"]["0"]) == 1
        _assert_byte_parity(doc, fixture_app, "W_NOOP")

    def test_overlapping_equal_writes(self, fixture_app, probe) -> None:
        _app, doc = _base_doc()
        doc.character_range(0, 5).font_size = 72
        doc.character_range(3, 8).font_size = 72
        _assert_alias_integrity(doc)
        _assert_byte_parity(doc, fixture_app, "W_PARTIAL_EQ")
        _assert_per_char(doc, probe, "W_PARTIAL_EQ", ["fontSize"])

    def test_bool_write(self, fixture_app, probe) -> None:
        _app, doc = _base_doc()
        doc.character_range(2, 6).apply_fill = False
        _assert_alias_integrity(doc)
        _assert_byte_parity(doc, fixture_app, "W_FILL_UNAPPLY")
        _assert_per_char(doc, probe, "W_FILL_UNAPPLY", ["applyFill"])

    def test_zero_span_write_is_noop(self, fixture_app, probe) -> None:
        _app, doc = _base_doc()
        doc.character_range(3, 3).font_size = 90
        _assert_byte_parity(doc, fixture_app, "W_ZERO_STYLE")

    def test_validation(self) -> None:
        _app, doc = _base_doc()
        with pytest.raises(ValueError):
            doc.character_range(0, 5).font_size = 0
        with pytest.raises(AttributeError):
            doc.character_range(0, 5).font_object = None


class TestColorFontLeadingWrites:
    def test_stroke_color_does_not_flip_gate(self, fixture_app, probe) -> None:
        _app, doc = _base_doc()
        doc.character_range(2, 6).stroke_color = [0, 1, 0]
        _assert_byte_parity(doc, fixture_app, "W_STROKE_GATE")
        # AE leaves applyStroke off, so the gated read stays undefined.
        _assert_per_char(doc, probe, "W_STROKE_GATE", ["strokeColor", "applyStroke"])

    def test_leading_disables_auto_leading(self, fixture_app, probe) -> None:
        _app, doc = _base_doc()
        doc.character_range(1, 4).leading = 50
        _assert_byte_parity(doc, fixture_app, "W_LEAD")
        _assert_per_char(doc, probe, "W_LEAD", ["leading", "autoLeading"])

    def test_font_prepends_and_reindexes(self, fixture_app, probe) -> None:
        # The fixture embeds the version string AE resolved from the
        # host font; byte parity only holds where that font matches.
        expected = _doc_for(fixture_app, "W_FONT")
        fixture_version = expected._cos_data["0"]["1"]["0"][0]["0"]["0"].get("5")
        if font_version_string("Arial-BoldMT") != fixture_version:
            pytest.skip("Arial-BoldMT not installed at the fixture's version")
        _app, doc = _base_doc()
        doc.character_range(3, 7).font = "Arial-BoldMT"
        assert [f.post_script_name for f in doc._fonts][0] == "Arial-BoldMT"
        _assert_byte_parity(doc, fixture_app, "W_FONT")
        _assert_per_char(doc, probe, "W_FONT", ["font"])

    def test_existing_font_reuses_index(self) -> None:
        _app, doc = _base_doc()
        before = [f.post_script_name for f in doc._fonts]
        doc.character_range(3, 7).font = before[0]
        assert [f.post_script_name for f in doc._fonts] == before

    def test_fill_color_write_and_clear(self) -> None:
        _app, doc = _base_doc()
        doc.character_range(2, 6).fill_color = [1, 0, 0]
        assert doc.character_range(2, 6).fill_color == pytest.approx([1.0, 0.0, 0.0])
        assert doc.character_range(0, 2).fill_color != pytest.approx([1.0, 0.0, 0.0])
        doc.character_range(2, 6).fill_color = None
        # Cleared paint: the gated read has applyFill runs but no color.
        assert doc.character_range(2, 6).fill_color is None


class TestKerningWrites:
    def test_kern_mid_pair_shift(self, fixture_app, probe) -> None:
        _app, doc = _base_doc("AVAWAYAVAW")
        doc.character_range(2, 5).kerning = 150
        _assert_byte_parity(doc, fixture_app, "W_KERN_MID")
        _assert_per_char(doc, probe, "W_KERN_MID", ["kerning", "autoKernType"])

    def test_kern_at_start_writes_leading_edge(self, fixture_app, probe) -> None:
        _app, doc = _base_doc("AVAWAYAVAW")
        doc.character_range(0, 2).kerning = 150
        assert doc._doc["0"]["7"] == 150
        assert doc.kerning == 150
        _assert_byte_parity(doc, fixture_app, "W_KERN_START")
        _assert_per_char(doc, probe, "W_KERN_START", ["kerning", "autoKernType"])

    def test_document_kerning_reads_leading_edge(self, fixture_app) -> None:
        assert _doc_for(fixture_app, "W_KERN_START").kerning == 150
        assert _doc_for(fixture_app, "W_KERN_MID").kerning == 0

    def test_auto_kern_type_clears_values(self, fixture2_app, probe2) -> None:

        _app, doc = _base_doc("AVAWAYAV")
        doc.character_range(1, 4).kerning = 200
        doc.character_range(0, -1).auto_kern_type = AutoKernType.METRIC_KERN
        assert "8" not in doc._doc["0"]
        _assert_byte_parity(doc, fixture2_app, "X_AKT_SET")
        _assert_per_char(doc, probe2, "X_AKT_SET", ["kerning", "autoKernType"])

    def test_auto_leading_resets_explicit_leading(self, fixture2_app, probe2) -> None:
        _app, doc = _base_doc("abcdefgh")
        doc.character_range(1, 4).leading = 50
        doc.character_range(0, -1).auto_leading = True
        # AE merges back to a single run with the leading sentinel.
        assert len(doc._doc["0"]["6"]["0"]) == 1
        _assert_byte_parity(doc, fixture2_app, "X_AL_SET")
        _assert_per_char(doc, probe2, "X_AL_SET", ["leading", "autoLeading"])


class TestParagraphWrites:
    def test_partial_range_styles_whole_paragraph(self, fixture_app, probe) -> None:
        _app, doc = _base_doc("Left one\nRight two")
        doc.character_range(2, 5).justification = ParagraphJustification.RIGHT_JUSTIFY
        _assert_byte_parity(doc, fixture_app, "W_PARA_PARTIAL")
        _assert_per_char(doc, probe, "W_PARA_PARTIAL", ["justification"])


class TestTextReplacement:
    def _styled_base(self):
        app, doc = _base_doc()
        doc.character_range(0, 5).fill_color = [1, 0, 0]
        doc.character_range(0, 5).font_size = 72
        return app, doc

    def test_replace_shorter(self, fixture_app, probe) -> None:
        _app, doc = self._styled_base()
        rng = doc.character_range(3, 7)
        rng.text = "XY"
        # The range keeps its creation indices against the new text.
        assert rng.text == "XYhi"
        _assert_byte_parity(doc, fixture_app, "W_TEXT_SHORTER")
        _assert_per_char(doc, probe, "W_TEXT_SHORTER", ["fontSize", "fillColor"])

    def test_replace_longer(self, fixture_app, probe) -> None:
        _app, doc = self._styled_base()
        rng = doc.character_range(3, 5)
        rng.text = "LONGERBIT"
        assert rng.text == "LO"
        _assert_byte_parity(doc, fixture_app, "W_TEXT_LONGER")
        _assert_per_char(doc, probe, "W_TEXT_LONGER", ["fontSize", "fillColor"])

    def test_replace_adds_paragraph(self, fixture_app, probe) -> None:
        _app, doc = self._styled_base()
        doc.character_range(3, 5).text = "A\nB"
        assert doc.paragraph_count == 2
        _assert_byte_parity(doc, fixture_app, "W_TEXT_ADDPARA")

    def test_zero_span_insert(self, fixture_app, probe) -> None:
        _app, doc = self._styled_base()
        rng = doc.character_range(4, 4)
        rng.text = "ins"
        assert rng.text == ""
        assert doc.text == "abcdinsefghij"
        _assert_byte_parity(doc, fixture_app, "W_TEXT_INSERT")
        _assert_per_char(doc, probe, "W_TEXT_INSERT", ["fontSize", "fillColor"])

    def test_replace_at_visible_end(self, fixture2_app, probe2) -> None:
        _app, doc = _base_doc()
        doc.character_range(0, 4).font_size = 72
        doc.character_range(6, 10).text = "ZZ"
        assert doc.text == "abcdefZZ"
        _assert_byte_parity(doc, fixture2_app, "X_TEXT_END")
        _assert_per_char(doc, probe2, "X_TEXT_END", ["fontSize"])

    def test_replace_splices_kern_values(self, fixture2_app, probe2) -> None:
        _app, doc = _base_doc("AVAWAYAV")
        doc.character_range(1, 4).kerning = 200
        doc.character_range(2, 5).text = "xy"
        assert doc.text == "AVxyYAV"
        _assert_byte_parity(doc, fixture2_app, "X_TEXT_KERN")
        _assert_per_char(doc, probe2, "X_TEXT_KERN", ["kerning", "autoKernType"])


class TestPasteFrom:
    def test_paste_same_document(self, fixture_app, probe) -> None:
        _app, doc = _base_doc()
        src = doc.character_range(0, 3)
        src.fill_color = [1, 0, 0]
        src.font_size = 72
        doc.character_range(6, 9).paste_from(doc.character_range(0, 3))
        _assert_byte_parity(doc, fixture_app, "W_PASTE_SAME")
        _assert_per_char(doc, probe, "W_PASTE_SAME", ["fontSize", "fillColor"])

    def test_paste_cross_document_remaps_fonts(self, fixture_app, probe) -> None:
        app, doc = _base_doc()
        src_doc = _doc_for(app, "W_SPLIT")
        src_doc.text = "QQQQ"
        src_all = src_doc.character_range(0, -1)
        src_all.font = "Arial-BoldMT"
        src_all.font_size = 90
        doc.character_range(2, 6).paste_from(src_doc.character_range(0, 4))
        assert doc.text == "abQQQQghij"
        _assert_per_char(doc, probe, "W_PASTE_XDOC", ["fontSize", "font"])

    def test_paste_shorter_invalidates_target(self, fixture_app, probe) -> None:
        app, doc = _base_doc()
        src_doc = _doc_for(app, "W_SPLIT")
        src_doc.text = "QQQQ"
        src_all = src_doc.character_range(0, -1)
        src_all.font = "Arial-BoldMT"
        src_all.font_size = 90
        target = doc.character_range(2, 9)
        target.paste_from(src_doc.character_range(0, 2))
        assert doc.text == "abQQj"
        assert target.is_range_valid is False
        with pytest.raises(ValueError):
            _ = target.text

    def test_paste_transplants_kern_values(self, fixture2_app, probe2) -> None:
        app, doc = _base_doc("abcdefgh")
        src_doc = _doc_for(app, "W_SPLIT")
        src_doc.text = "AVAV"
        src_doc.character_range(1, 3).kerning = 150
        doc.character_range(2, 6).paste_from(src_doc.character_range(0, 4))
        assert doc.text == "abAVAVgh"
        _assert_byte_parity(doc, fixture2_app, "X_PASTE_KERN")
        _assert_per_char(doc, probe2, "X_PASTE_KERN", ["kerning", "autoKernType"])

    def test_transplanted_styles_differ_only_in_font_index(self, fixture_app) -> None:
        # W5 entry gate: the only doc-level index a transplanted style
        # carries is the font reference (key "0").
        pasted = _doc_for(fixture_app, "W_PASTE_XDOC")
        source = _doc_for(fixture_app, "PasteSrc")
        pasted_style = pasted._doc["0"]["6"]["0"][1]["0"]["0"]["6"]
        source_style = source._doc["0"]["6"]["0"][0]["0"]["0"]["6"]
        diff_keys = {
            k
            for k in set(pasted_style) | set(source_style)
            if pasted_style.get(k) != source_style.get(k)
        }
        assert diff_keys <= {"0"}


class TestSurrogateWrites:
    def test_mid_pair_write_expands(self, probe) -> None:
        # Value parity only: AE materialized an emoji fallback font into
        # the font array at composition, which py cannot reproduce.
        _app, doc = _base_doc("ab\U0001f600cd")
        doc.character_range(2, 3).font_size = 72
        # Per UTF-16 unit, like the ExtendScript probe (the emoji is 2 units).
        expected = [c["fontSize"] for c in probe["ops"]["W_SURROGATE_STYLE"]["perChar"]]
        actual = [doc.character_range(i, i + 1).font_size for i in range(len(expected))]
        assert actual == expected


class TestDocumentWideWrites:
    def test_cosfield_setter_collapses_runs(self, fixture_app, probe) -> None:
        _app, doc = _base_doc()
        doc.character_range(0, 5).font_size = 72
        doc.font_size = 50
        assert len(doc._doc["0"]["6"]["0"]) == 1
        _assert_byte_parity(doc, fixture_app, "W_DOCLEVEL")
        _assert_per_char(doc, probe, "W_DOCLEVEL", ["fontSize"])

    def test_custom_setter_styles_all_runs(self, fixture2_app, probe2) -> None:
        _app, doc = _base_doc("abcdefgh")
        doc.character_range(0, 4).font_size = 72
        doc.fill_color = [0, 0, 1]
        _assert_byte_parity(doc, fixture2_app, "X_DOC_FILL")
        _assert_per_char(doc, probe2, "X_DOC_FILL", ["fillColor", "fontSize"])

    def test_paragraph_setter_styles_all_paragraphs(self, fixture2_app, probe2) -> None:
        _app, doc = _base_doc("One two\nThree four")
        doc.justification = ParagraphJustification.CENTER_JUSTIFY
        _assert_byte_parity(doc, fixture2_app, "X_DOC_JUST")
        _assert_per_char(doc, probe2, "X_DOC_JUST", ["justification"])

    def test_auto_leading_resets_sentinel_document_wide(self) -> None:
        _app, doc = _base_doc()
        doc.character_range(1, 4).leading = 50
        doc.auto_leading = True
        assert len(doc._doc["0"]["6"]["0"]) == 1
        assert doc._char_style["5"] == 0.01


class TestRoundTripAfterWrite:
    def test_mutated_save_is_idempotent(self, tmp_path: Path) -> None:
        app, doc = _base_doc()
        doc.character_range(3, 7).font_size = 72
        first = tmp_path / "first.aep"
        app.project.save(first)
        app2 = parse_app_fresh(first)
        second = tmp_path / "second.aep"
        app2.project.save(second)
        assert first.read_bytes() == second.read_bytes()

    def test_document_getter_tracks_first_run_after_writes(self) -> None:
        # After splits and merges, document-level getters (which alias the
        # first run's style dict) must keep reading char 0's actual style.
        _app, doc = _base_doc()
        doc.character_range(3, 7).font_size = 72
        assert doc.font_size == 36.0
        doc.character_range(0, 3).font_size = 72
        assert doc.font_size == 72.0
