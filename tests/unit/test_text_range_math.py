"""Unit tests for text-range boundary math on synthetic COS documents.

These cover structural cases the AE-generated sample corpus cannot
(multi-segment composed lines, multiple frames, sparse style runs) plus
the UTF-16 helpers and the RangeField/CosField spec consistency guard.
"""

from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from py_aep.cos import CosField, CosName
from py_aep.cos.cos import CosString
from py_aep.models.text.ranges import (
    CHARACTER_RANGE_OOB,
    CharacterRange,
    ComposedLineRange,
    RangeField,
    _composed_line_spans,
    _merge_adjacent_runs,
    _snap_to_pairs,
    _split_run_array,
    u16_len,
    u16_slice,
)
from py_aep.models.text.text_document import TextDocument

EMOJI = "\U0001f600"


class TestWriteEnginePrimitives:
    def test_split_keeps_original_as_left_fragment(self) -> None:
        style = {"1": 36.0}
        runs = [{"0": {"0": {"6": style}}, "1": 10}]
        original = runs[0]
        _split_run_array(runs, {3, 7})
        assert [r["1"] for r in runs] == [3, 4, 3]
        # Run 0 keeps its object (and its style dict) as the left piece.
        assert runs[0] is original
        assert runs[0]["0"]["0"]["6"] is style
        # Fragments are independent copies.
        runs[1]["0"]["0"]["6"]["1"] = 72.0
        assert runs[0]["0"]["0"]["6"]["1"] == 36.0

    def test_merge_keeps_first_object(self) -> None:
        a = {"0": {"0": {"6": {"1": 72.0}}}, "1": 3}
        b = {"0": {"0": {"6": {"1": 72.0}}}, "1": 4}
        c = {"0": {"0": {"6": {"1": 36.0}}}, "1": 4}
        runs = [a, b, c]
        _merge_adjacent_runs(runs)
        assert runs == [a, c]
        assert runs[0] is a
        assert runs[0]["1"] == 7

    def test_snap_to_pairs(self) -> None:
        raw = f"ab{EMOJI}cd\r"
        assert _snap_to_pairs(raw, 3, 5) == (2, 5)
        assert _snap_to_pairs(raw, 2, 3) == (2, 4)
        assert _snap_to_pairs(raw, 0, 2) == (0, 2)
        # A mid-pair caret moves past the pair but stays zero-span, so
        # caret writes remain no-ops instead of covering the glyph.
        assert _snap_to_pairs(raw, 3, 3) == (4, 4)
        assert _snap_to_pairs(raw, 1, 1) == (1, 1)

    def test_deepcopy_preserves_cos_scalars(self) -> None:
        # The split engine deepcopies full style dicts; the serializer's
        # byte output depends on these flags surviving the copy.
        nested = {"99": CosName("X"), "0": [CosString("s", utf16=False)]}
        clone = copy.deepcopy(nested)
        assert clone["0"][0].cos_utf16 is False
        assert str(clone["99"]) == "X"

    def test_range_write_on_synthetic_doc(self) -> None:
        doc = make_doc("abcdefghij\r")
        CharacterRange(doc, 3, 7).font_size = 72
        lengths = [r["1"] for r in doc._doc["0"]["6"]["0"]]
        assert lengths == [3, 4, 4]
        assert CharacterRange(doc, 3, 7).font_size == 72.0
        assert CharacterRange(doc, 0, 3).font_size is None  # key absent -> default

    def test_range_write_validation(self) -> None:
        doc = make_doc("abcdefghij\r")
        with pytest.raises(ValueError):
            CharacterRange(doc, 0, 5).font_size = 0
        with pytest.raises((TypeError, ValueError)):
            CharacterRange(doc, 0, 5).auto_kern_type = 5

    def test_kerning_write_skips_terminator(self) -> None:
        # AE never kerns the raw \r terminator: a range ending at the
        # visible length must leave the final unit in an empty run.
        doc = make_doc("AVAW\r")
        CharacterRange(doc, 2, 4).kerning = 100
        runs = doc._doc["0"]["8"]["0"]
        assert runs[-1] == {"0": {}, "1": 1}
        assert sum(r["1"] for r in runs) == 5


def make_doc(
    raw: str,
    char_runs: list[tuple[int, dict]] | None = None,
    para_runs: list[tuple[int, dict]] | None = None,
    line_cache: list | None = None,
) -> SimpleNamespace:
    """Build a duck-typed document from `(length, style)` run pairs."""

    def run_array(runs: list[tuple[int, dict]], style_key: str) -> dict:
        return {
            "0": [
                {"0": {"0": {style_key: style}}, "1": length} for length, style in runs
            ]
        }

    total = u16_len(raw)
    doc: dict = {"0": {"0": raw}}
    doc["0"]["6"] = run_array(char_runs or [(total, {})], "6")
    doc["0"]["5"] = run_array(para_runs or [(total, {})], "5")
    if line_cache is not None:
        doc["1"] = {"2": line_cache}
    # Docs carrying a line cache act as box text (point text derives its
    # composed lines from the paragraphs and never reads the cache).
    return SimpleNamespace(_doc=doc, _fonts=[], box_text=line_cache is not None)


def line(*segment_counts: int) -> dict:
    """A synthetic `/L` record with one `/S` per count."""
    return {
        "99": CosName("L"),
        "6": [{"99": CosName("S"), "15": {"0": count}} for count in segment_counts],
    }


class TestU16Helpers:
    def test_len_bmp(self) -> None:
        assert u16_len("hello") == 5
        assert u16_len("") == 0

    def test_len_astral(self) -> None:
        assert u16_len(EMOJI) == 2
        assert u16_len(f"ab{EMOJI}cd") == 6

    def test_slice_bmp(self) -> None:
        assert u16_slice("hello", 1, 3) == "el"

    def test_slice_astral(self) -> None:
        assert u16_slice(f"ab{EMOJI}cd", 2, 4) == EMOJI
        assert u16_slice(f"ab{EMOJI}cd", 0, 6) == f"ab{EMOJI}cd"

    def test_slice_splits_surrogate_pair(self) -> None:
        # AE allows the split and yields a lone surrogate; so do we.
        assert u16_slice(f"ab{EMOJI}cd", 2, 3) == "\ud83d"
        assert u16_slice(f"ab{EMOJI}cd", 0, 3) == "ab\ud83d"


class TestComposedLineSpans:
    def test_multi_segment_lines(self) -> None:
        # A line split into several /S segments (e.g. bidi) must sum them.
        cache = [
            {
                "99": CosName("PC"),
                "6": [{"99": CosName("F"), "6": [line(3, 2), line(4)]}],
            }
        ]
        doc = make_doc("abcdefgh\r", line_cache=cache)
        assert _composed_line_spans(doc) == [(0, 5), (5, 9)]

    def test_multiple_frames(self) -> None:
        cache = [
            {
                "99": CosName("PC"),
                "6": [
                    {"99": CosName("F"), "6": [line(4)]},
                    {"99": CosName("F"), "6": [line(5)]},
                ],
            }
        ]
        doc = make_doc("abcdefgh\r", line_cache=cache)
        assert _composed_line_spans(doc) == [(0, 4), (4, 9)]

    def test_box_without_cache(self) -> None:
        doc = make_doc("abcd\r")
        doc.box_text = True
        assert _composed_line_spans(doc) is None

    def test_point_text_lines_are_the_paragraphs(self) -> None:
        # Point text never wraps; its composed lines derive from the
        # paragraph runs and stay fresh without any cache.
        doc = make_doc("ab\rcd\r", para_runs=[(3, {}), (3, {})])
        assert _composed_line_spans(doc) == [(0, 3), (3, 6)]

    def test_stale_cache_clamps_and_raises(self) -> None:
        # Cache describes 9 chars, text shrank to "ab\r" (visible 2).
        cache = [
            {"99": CosName("PC"), "6": [{"99": CosName("F"), "6": [line(5), line(4)]}]}
        ]
        doc = make_doc("ab\r", line_cache=cache)
        first = ComposedLineRange(doc, 0, 1)
        assert (first.character_start, first.character_end) == (0, 2)
        with pytest.raises(ValueError, match="ComposedLine index range"):
            ComposedLineRange(doc, 1, 2)


class TestCharacterRangeMath:
    def test_dynamic_minus_one_end(self) -> None:
        doc = make_doc("hello\r")
        rng = CharacterRange(doc, 0, -1)
        assert rng.character_end == 5
        doc._doc["0"]["0"] = "hi\r"
        assert rng.character_end == 2

    def test_shrink_invalidates_fixed_end(self) -> None:
        doc = make_doc("hello\r")
        rng = CharacterRange(doc, 0, 5)
        assert rng.is_range_valid
        doc._doc["0"]["0"] = "hi\r"
        assert not rng.is_range_valid
        with pytest.raises(ValueError, match=CHARACTER_RANGE_OOB[:20]):
            _ = rng.character_start

    def test_creation_bounds(self) -> None:
        doc = make_doc("hello\r")
        for start, end in ((6, 7), (0, 6), (3, 1), (0, -2), (-1, 2)):
            with pytest.raises(ValueError, match="Character index range"):
                CharacterRange(doc, start, end)

    def test_sparse_runs_mix_with_default(self) -> None:
        # Defensive path: a run lacking the key contributes the default.
        doc = make_doc(
            "abcdef\r",
            char_runs=[(3, {"2": True}), (4, {})],
        )
        rng = CharacterRange(doc, 0, 6)
        # Stored True vs absent (default None) -> mixed -> None
        assert rng.faux_bold is None

    def test_gated_color_resolution(self) -> None:
        red = {"99": CosName("SimplePaint"), "0": {"0": 1, "1": [1.0, 1.0, 0.0, 0.0]}}
        black = {"99": CosName("SimplePaint"), "0": {"0": 1, "1": [1.0, 0.0, 0.0, 0.0]}}
        doc = make_doc(
            "abcdef\r",
            char_runs=[(3, {"57": False, "54": black}), (4, {"57": True, "54": red})],
        )
        # Only the applyStroke run participates: uniform red, not mixed.
        assert CharacterRange(doc, 0, 6).stroke_color == [1.0, 0.0, 0.0]
        # A range over non-stroked runs only reads None.
        assert CharacterRange(doc, 0, 3).stroke_color is None

    def test_zero_span_uses_containing_run(self) -> None:
        doc = make_doc(
            "abcdef\r",
            char_runs=[(3, {"1": 72.0}), (4, {"1": 36.0})],
        )
        assert CharacterRange(doc, 2, 2).font_size == 72.0
        # A caret on a run boundary belongs to the following run.
        assert CharacterRange(doc, 3, 3).font_size == 36.0
        # EOF caret lands in the final run (which covers the terminator).
        assert CharacterRange(doc, 6, 6).font_size == 36.0


class TestUnassociatedDocuments:
    def test_template_document_refuses_ranges(self) -> None:
        doc = TextDocument("hello")
        assert doc.composed_line_count is None
        with pytest.raises(ValueError, match="not associated with a layer"):
            doc.character_range(0)
        with pytest.raises(ValueError, match="not associated with a layer"):
            doc.paragraph_range(0)
        with pytest.raises(ValueError, match="not associated with a layer"):
            doc.composed_line_range(0)
        with pytest.raises(ValueError, match="not associated with a layer"):
            doc.paragraph_character_indexes_at(0)


class TestSpecConsistency:
    """RangeField declarations must agree with TextDocument's CosFields."""

    KIND_TO_DICT_ATTR = {"char": "_char_style", "para": "_para_style"}

    def test_rangefields_match_cosfields(self) -> None:
        mismatches = []
        for name, field in vars(CharacterRange).items():
            if not isinstance(field, RangeField):
                continue
            cos_field = TextDocument.__dict__.get(name)
            if not isinstance(cos_field, CosField):
                continue
            if field.key != cos_field.key:
                mismatches.append(
                    f"{name}: RangeField key {field.key!r} != CosField key {cos_field.key!r}"
                )
            expected_dict_attr = self.KIND_TO_DICT_ATTR.get(field.kind)
            if cos_field.dict_attr != expected_dict_attr:
                mismatches.append(
                    f"{name}: RangeField kind {field.kind!r} vs CosField dict "
                    f"{cos_field.dict_attr!r}"
                )
            if not field.read_only and field.validate is not cos_field.validate:
                mismatches.append(
                    f"{name}: RangeField validate {field.validate!r} != "
                    f"CosField validate {cos_field.validate!r}"
                )
        assert not mismatches, "\n".join(mismatches)
