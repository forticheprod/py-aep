"""Parity tests for CharacterRange / ParagraphRange / ComposedLineRange.

Every assertion compares the parsed `samples/models/text/text_ranges.aep`
against `text_ranges_probe.json`, the exhaustive ExtendScript ground truth
dumped by `scripts/jsx/generate_text_range_samples.jsx` from the very AE
session that saved the sample.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from helpers import parse_project

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "text"
SAMPLE = SAMPLES_DIR / "text_ranges.aep"
PROBE = SAMPLES_DIR / "text_ranges_probe.json"

# ExtendScript attribute -> py_aep CharacterRange attribute. Attributes
# deliberately not exposed (host-font-resolved) are absent: fontFamily,
# fontStyle, fontLocation.
ATTR_MAP = {
    "characterStart": "character_start",
    "characterEnd": "character_end",
    "isRangeValid": "is_range_valid",
    "text": "text",
    "fillColor": "fill_color",
    "strokeColor": "stroke_color",
    "strokeOverFill": "stroke_over_fill",
    "strokeWidth": "stroke_width",
    "applyFill": "apply_fill",
    "applyStroke": "apply_stroke",
    "font": "font",
    "fontObject": "font_object",
    "fontSize": "font_size",
    "fauxBold": "faux_bold",
    "fauxItalic": "faux_italic",
    "autoLeading": "auto_leading",
    "leading": "leading",
    "kerning": "kerning",
    "autoKernType": "auto_kern_type",
    "tracking": "tracking",
    "baselineShift": "baseline_shift",
    "horizontalScale": "horizontal_scale",
    "verticalScale": "vertical_scale",
    "fontCapsOption": "font_caps_option",
    "fontBaselineOption": "font_baseline_option",
    "ligature": "ligature",
    "noBreak": "no_break",
    "baselineDirection": "baseline_direction",
    "tsume": "tsume",
    "digitSet": "digit_set",
    "lineJoinType": "line_join_type",
    "allCaps": "all_caps",
    "smallCaps": "small_caps",
    "superscript": "superscript",
    "subscript": "subscript",
    "composerEngine": "composer_engine",
    "justification": "justification",
    "firstLineIndent": "first_line_indent",
    "startIndent": "start_indent",
    "endIndent": "end_indent",
    "spaceBefore": "space_before",
    "spaceAfter": "space_after",
    "leadingType": "leading_type",
    "autoHyphenate": "auto_hyphenate",
    "hangingRoman": "hanging_roman",
    "everyLineComposer": "every_line_composer",
    "direction": "direction",
}

_AE_ERROR_PREFIX = "Error: After Effects error: "
_MARKER_RE = re.compile(r"<U\+([0-9A-F]{4})>")


def _load_probe() -> dict:
    with open(PROBE, encoding="utf-8") as fp:
        return json.load(fp)


def _expected_text(value: str) -> str:
    """ES text -> py text: CR becomes LF, marker escapes become chars.

    The probe writer replaces lone surrogates with `<U+XXXX>` markers
    (a raw lone surrogate kills ExtendScript's File.write); decode them
    back to compare against py_aep's surrogatepass slicing.
    """
    value = _MARKER_RE.sub(lambda m: chr(int(m.group(1), 16)), value)
    return value.replace("\r", "\n")


def _range_from_key(doc, key: str):
    """Build the CharacterRange a probe dict key describes (e.g. `0_-1`)."""
    start_s, end_s = key.rsplit("_", 1)
    start = int(start_s)
    if end_s == "def":
        return doc.character_range(start)
    return doc.character_range(start, int(end_s))


def _compare(py_val, expected, attr: str) -> str | None:
    """Return a mismatch description, or `None` when values agree."""
    if expected == "<<undefined>>":
        if py_val is None:
            return None
        return f"{attr}: expected None (ES undefined), got {py_val!r}"
    if attr == "fontObject":
        expected_name = expected.split(":", 1)[1] if isinstance(expected, str) else None
        actual_name = py_val.post_script_name if py_val is not None else None
        if actual_name == expected_name:
            return None
        return f"{attr}: expected {expected_name!r}, got {actual_name!r}"
    if attr == "text":
        expected = _expected_text(expected)
        if py_val == expected:
            return None
        return f"{attr}: expected {expected!r}, got {py_val!r}"
    if isinstance(expected, list):
        if py_val == pytest.approx(expected, abs=1e-5):
            return None
        return f"{attr}: expected {expected!r}, got {py_val!r}"
    if isinstance(expected, float) or isinstance(py_val, float):
        if py_val is not None and py_val == pytest.approx(expected, abs=1e-5):
            return None
        return f"{attr}: expected {expected!r}, got {py_val!r}"
    # bools, ints, IntEnums (IntEnum == int holds for ExtendScript values)
    if py_val == expected:
        return None
    return f"{attr}: expected {expected!r}, got {py_val!r}"


@pytest.fixture(scope="module")
def probe() -> dict:
    return _load_probe()


@pytest.fixture(scope="module")
def docs() -> dict:
    project = parse_project(SAMPLE)
    comp = project.compositions[0]
    return {layer.name: layer.text.source_text.value for layer in comp.text_layers}


LAYER_NAMES = [
    "RangesPoint",
    "RangesBox",
    "RangesKernLead",
    "RangesJust",
    "RangesEmpty",
    "RangesTrailing",
    "RangesEmoji",
    "RangesTextReset",
]


class TestDocumentLevel:
    """text / paragraph_count / composed_line_count parity per layer."""

    @pytest.mark.parametrize("name", LAYER_NAMES)
    def test_text(self, docs, probe, name: str) -> None:
        expected = probe["layers"][name]
        assert docs[name].text == _expected_text(expected["text"])

    @pytest.mark.parametrize("name", LAYER_NAMES)
    def test_paragraph_count(self, docs, probe, name: str) -> None:
        expected = probe["layers"][name]["paragraphCount"]
        if expected["ok"]:
            assert docs[name].paragraph_count == expected["value"]

    @pytest.mark.parametrize("name", LAYER_NAMES)
    def test_composed_line_count(self, docs, probe, name: str) -> None:
        expected = probe["layers"][name]["composedLineCount"]
        if expected["ok"]:
            assert docs[name].composed_line_count == expected["value"]

    def test_document_kerning_reads_zero(self, docs) -> None:
        # ExtendScript exports kerning=0 on every TextDocument value object,
        # even with manual per-character kerning present; the real values
        # are only reachable through character_range(...).kerning.
        assert docs["RangesKernLead"].kerning == 0
        assert docs["RangesKernLead"].character_range(1, 4).kerning == 200


class TestRangeBoundaries:
    """Paragraph / composed-line boundary and index-lookup parity."""

    @pytest.mark.parametrize("name", LAYER_NAMES)
    def test_paragraph_ranges(self, docs, probe, name: str) -> None:
        doc = docs[name]
        for entry in probe["layers"][name]["paragraphRanges"]:
            assert entry["ok"], f"{name}: ES probe failed: {entry}"
            exp = entry["value"]
            pr = doc.paragraph_range(exp["index"])
            assert str(pr) == exp["str"]
            assert pr.character_start == exp["characterStart"]
            assert pr.character_end == exp["characterEnd"]
            assert pr.is_range_valid == exp["isRangeValid"]
            assert pr.character_range().text == _expected_text(exp["charRangeText"])

    @pytest.mark.parametrize("name", LAYER_NAMES)
    def test_composed_line_ranges(self, docs, probe, name: str) -> None:
        doc = docs[name]
        for entry in probe["layers"][name]["composedLineRanges"]:
            assert entry["ok"], f"{name}: ES probe failed: {entry}"
            exp = entry["value"]
            clr = doc.composed_line_range(exp["index"])
            assert str(clr) == exp["str"]
            assert clr.character_start == exp["characterStart"]
            assert clr.character_end == exp["characterEnd"]
            assert clr.is_range_valid == exp["isRangeValid"]
            assert clr.character_range().text == _expected_text(exp["charRangeText"])

    @pytest.mark.parametrize("name", LAYER_NAMES)
    def test_character_indexes_at(self, docs, probe, name: str) -> None:
        doc = docs[name]
        layer_probe = probe["layers"][name]
        for idx_s, entry in layer_probe["paragraphCharacterIndexesAt"].items():
            if entry["ok"]:
                assert doc.paragraph_character_indexes_at(int(idx_s)) == entry["value"]
        for idx_s, entry in layer_probe["composedLineCharacterIndexesAt"].items():
            if entry["ok"]:
                assert (
                    doc.composed_line_character_indexes_at(int(idx_s)) == entry["value"]
                )


class TestCharacterRangeAttributes:
    """Every probed attribute of every probed range, against ES values."""

    @pytest.mark.parametrize("name", LAYER_NAMES)
    def test_attribute_parity(self, docs, probe, name: str) -> None:
        doc = docs[name]
        mismatches: list[str] = []
        for key, entry in probe["layers"][name]["charRanges"].items():
            if not entry["ok"]:
                # Creation must fail on the py side too.
                with pytest.raises(ValueError):
                    _range_from_key(doc, key)
                continue
            rng = _range_from_key(doc, key)
            for es_attr, expected in entry["value"].items():
                py_attr = ATTR_MAP.get(es_attr)
                if py_attr is None:
                    continue
                mismatch = _compare(getattr(rng, py_attr), expected, es_attr)
                if mismatch is not None:
                    mismatches.append(f"[{key}] {mismatch}")
        assert not mismatches, f"{name}:\n" + "\n".join(mismatches)


class TestEdgeCases:
    """Creation-time errors and zero-span semantics from the edge probes."""

    def _assert_edge(self, doc, edge: dict, build) -> None:
        if edge["ok"]:
            build()
            return
        expected_message = edge["error"]
        if expected_message.startswith(_AE_ERROR_PREFIX):
            expected_message = expected_message[len(_AE_ERROR_PREFIX) :]
        with pytest.raises(ValueError) as exc_info:
            build()
        assert str(exc_info.value) == expected_message

    def test_point_edges(self, docs, probe) -> None:
        doc = docs["RangesPoint"]
        edges = probe["layers"]["RangesPoint"]["edges"]
        length = len(doc.text)

        self._assert_edge(
            doc, edges["eof_default_end"], lambda: doc.character_range(length)
        )
        self._assert_edge(doc, edges["neg_two_end"], lambda: doc.character_range(0, -2))
        self._assert_edge(doc, edges["para_0_0"], lambda: doc.paragraph_range(0, 0))
        self._assert_edge(doc, edges["start_oob"], lambda: doc.character_range(9999))
        self._assert_edge(doc, edges["end_oob"], lambda: doc.character_range(0, 9999))
        self._assert_edge(
            doc, edges["end_before_start"], lambda: doc.character_range(5, 2)
        )
        self._assert_edge(doc, edges["para_oob"], lambda: doc.paragraph_range(99))

        eof = edges["eof_zero_span"]["value"]
        rng = doc.character_range(length, -1)
        assert rng.character_start == eof["s"]
        assert rng.character_end == eof["e"]
        assert rng.text == eof["text"]
        assert rng.font_size == eof["fontSize"]

        zero = edges["char_0_0"]["value"]
        rng = doc.character_range(0, 0)
        assert (rng.character_start, rng.character_end) == (zero["s"], zero["e"])
        assert rng.text == zero["text"]

        neg = edges["line_neg_end"]["value"]
        clr = doc.composed_line_range(0, -1)
        assert (clr.character_start, clr.character_end) == (neg["s"], neg["e"])

    def test_empty_edges(self, docs, probe) -> None:
        doc = docs["RangesEmpty"]
        edges = probe["layers"]["RangesEmpty"]["edges"]
        self._assert_edge(doc, edges["char_0_def"], lambda: doc.character_range(0))
        para = edges["para_0"]["value"]
        pr = doc.paragraph_range(0)
        assert (pr.character_start, pr.character_end) == (para["s"], para["e"])
        line = edges["line_0"]["value"]
        clr = doc.composed_line_range(0)
        assert (clr.character_start, clr.character_end) == (line["s"], line["e"])

    def test_split_surrogate(self, docs, probe) -> None:
        doc = docs["RangesEmoji"]
        edges = probe["layers"]["RangesEmoji"]["edges"]
        split = edges["split_surrogate_range"]["value"]
        rng = doc.character_range(2, 3)
        assert (rng.character_start, rng.character_end) == (split["s"], split["e"])
        assert rng.text == _expected_text(split["text"])
        assert rng.font_size == split["fontSize"]
        prefix = edges["split_surrogate_text"]["value"]
        assert doc.character_range(0, 3).text == _expected_text(prefix)
