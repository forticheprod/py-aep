"""Mutation tests for the text-range prerequisites.

Covers the AE-parity behaviors around py-side edits: the `text` setter's
style-run rebuild (probed via the `RangesTextReset` fixture), trailing
line-break preservation, and the stale composed-line clamp semantics.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import parse_app_fresh

from py_aep.cos import cos_get
from py_aep.enums import BoxVerticalAlignment
from py_aep.svg.fonts import resolve_postscript

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "text"
SAMPLE = SAMPLES_DIR / "text_ranges.aep"


def _fresh_doc(name: str, app=None):
    app = app or parse_app_fresh(SAMPLE)
    comp = app.project.compositions[0]
    layer = next(ly for ly in comp.text_layers if ly.name == name)
    return app, layer.text.source_text.value


def _require_composer(doc) -> None:
    """Skip when the calibrated composer cannot run on this machine
    (no uharfbuzz, or a font the doc's style runs use is missing).

    Only run-referenced fonts matter: `_fonts` also registers entries
    no run points at (e.g. AdobeInvisFont), which never get shaped.
    """
    pytest.importorskip("uharfbuzz")
    fonts = [font.post_script_name for font in doc._fonts]
    used = set()
    for run in cos_get(doc._doc, "0", "6", "0") or []:
        style = cos_get(run, "0", "0", "6") or {}
        index = style.get("0")
        if isinstance(index, int) and 0 <= index < len(fonts):
            used.add(fonts[index])
    missing = sorted(name for name in used if resolve_postscript(name) is None)
    if missing:
        pytest.skip(f"fixture fonts not installed: {', '.join(missing)}")


class TestTextSetterRunRebuild:
    """Setting `text` collapses styling like AE (RangesTextReset probe)."""

    def test_char_runs_collapse_to_first_style(self, tmp_path: Path) -> None:
        app, doc = _fresh_doc("RangesPoint")
        # Styled sample: chars 0-5 are 72pt red, the rest differs.
        assert doc.character_range(0, -1).font_size is None

        doc.text = "New text\rhere"
        assert doc.paragraph_count == 2
        full = doc.character_range(0, -1)
        assert full.font_size == 72.0
        assert full.fill_color == pytest.approx([1.0, 0.0, 0.0])

        out = tmp_path / "reset.aep"
        app.project.save(out)
        _app2, doc2 = _fresh_doc("RangesPoint", parse_app_fresh(out))
        assert doc2.text == "New text\nhere"
        assert doc2.paragraph_count == 2
        assert doc2.character_range(0, -1).font_size == 72.0
        assert (
            doc2.paragraph_range(1).character_start,
            doc2.paragraph_range(1).character_end,
        ) == (9, 13)

    def test_kerning_runs_dropped(self) -> None:
        _app, doc = _fresh_doc("RangesKernLead")
        assert doc.character_range(1, 4).kerning == 200
        doc.text = "AVAWAY"
        # Manual kerning values are dropped. Without stored values the
        # read is undefined even under NO_AUTO_KERN (probed X_TEXT_KERN).
        assert doc.character_range(0, -1).kerning is None

    def test_trailing_line_breaks_preserved(self, tmp_path: Path) -> None:
        app, doc = _fresh_doc("RangesPoint")
        doc.text = "A\nB\n"
        assert doc.text == "A\nB\n"
        assert doc.paragraph_count == 3
        pr = doc.paragraph_range(2)
        assert (pr.character_start, pr.character_end) == (4, 4)

        out = tmp_path / "trailing.aep"
        app.project.save(out)
        _app2, doc2 = _fresh_doc("RangesPoint", parse_app_fresh(out))
        assert doc2.text == "A\nB\n"
        assert doc2.paragraph_count == 3


class TestRecomposition:
    """Post-mutation composed-line freshness via the calibrated composer.

    The expected values are AE ground truth: opening the py-authored
    gate files, AE itself recomposed the shrunk box to 1 line and the
    grown text to 7 lines (gate_shrink / gate_grow, 2026-07-08), and
    reproduced the empty-paragraph / trailing-empty-paragraph /
    empty-text / zero-kept-lines spans byte-for-byte (gate_compose on
    mutated box_matrix layers, 2026-07-11).
    """

    def test_box_shrink_recomposes(self) -> None:
        _app, doc = _fresh_doc("RangesBox")
        _require_composer(doc)
        doc.text = "tiny"
        assert doc._composition_calibrated is True
        assert doc.composition_stale is False
        assert doc.composed_line_count == 1  # AE-verified
        rng = doc.composed_line_range(0)
        assert (rng.character_start, rng.character_end) == (0, 4)
        assert doc.box_overflow is False

    def test_box_growth_recomposes(self) -> None:
        _app, doc = _fresh_doc("RangesBox")
        _require_composer(doc)
        doc.text = "much longer text than before " * 4
        assert doc.composed_line_count == 7  # AE-verified
        assert doc.box_overflow is True
        assert doc.composition_stale is False

    def test_point_text_is_always_fresh(self) -> None:
        _app, doc = _fresh_doc("RangesPoint")
        doc.text = "one\ntwo\nthree"
        assert doc.composition_stale is False
        assert doc.composed_line_count == 3
        rng = doc.composed_line_range(2)
        assert (rng.character_start, rng.character_end) == (8, 13)

    def test_unresolvable_font_falls_back_to_stale(self) -> None:
        _app, doc = _fresh_doc("RangesBox")
        _require_composer(doc)
        doc.character_range(0, 4).font = "NotInstalled-Font"
        # Calibration (taken before the write) passed, but recomposition
        # now refuses; the stale cache stays, with clamp semantics.
        assert doc.composition_stale is True
        assert doc.composed_line_count == 6

    def test_empty_paragraph_recomposes(self) -> None:
        _app, doc = _fresh_doc("RangesBox")
        _require_composer(doc)
        doc.text = "a\n\nb"
        # The empty paragraph composes to its own (empty) line and the
        # spans stay contiguous over the raw text (gate_compose M_W300).
        assert doc.composition_stale is False
        assert doc.composed_line_count == 3
        assert doc.composed_line_ranges == [
            {"start": 0, "end": 2},
            {"start": 2, "end": 3},
            {"start": 3, "end": 4},
        ]
        assert doc.box_overflow is False

    def test_trailing_empty_paragraph_recomposes(self) -> None:
        _app, doc = _fresh_doc("RangesBox")
        _require_composer(doc)
        doc.text = "hello\n"
        # The trailing empty paragraph is its own zero-span line
        # (gate_compose M_H40: ranges [0, 6] and [6, 6]).
        assert doc.composition_stale is False
        assert doc.composed_line_count == 2
        assert doc.composed_line_ranges == [
            {"start": 0, "end": 6},
            {"start": 6, "end": 6},
        ]

    def test_empty_text_composes_one_line(self) -> None:
        _app, doc = _fresh_doc("RangesBox")
        _require_composer(doc)
        doc.text = ""
        # AE composes one empty line for empty box text (gate_compose
        # M_H55: count 1, range [0, 0], no overflow).
        assert doc.composed_line_count == 1
        assert doc.box_overflow is False

    def test_zero_kept_lines_reports_overflow(self) -> None:
        _app, doc = _fresh_doc("RangesBox")
        _require_composer(doc)
        # Box shorter than the first baseline: every line is clipped.
        # AE agrees (gate_compose M_H70: count 0, overflow true).
        doc.box_text_size = [200.0, 1.0]
        assert doc.composed_line_count == 0
        assert doc.box_overflow is True
        assert doc.composition_stale is False

    def test_frame_write_marks_sibling_keyframe_docs(self) -> None:
        app = parse_app_fresh(SAMPLE)
        comp = app.project.compositions[0]
        layer = next(ly for ly in comp.text_layers if ly.name == "RangesBox")
        prop = layer.text.source_text
        prop.add_key(0.0)
        prop.add_key(1.0)
        doc_a = prop.keyframes[0].value
        doc_b = prop.keyframes[1].value
        assert doc_a is not doc_b
        _require_composer(doc_a)

        # The box frame is layer-shared: resizing through one keyframe's
        # document must not leave the sibling serving its pre-resize
        # cache as fresh.
        doc_a.box_text_size = [220.0, 90.0]
        assert doc_b._layout_dirty is True
        assert doc_b.composition_stale is False
        assert doc_a.composed_line_count == doc_b.composed_line_count

    def test_unmodeled_layout_write_falls_back_to_stale(self) -> None:
        _app, doc = _fresh_doc("RangesBox")
        _require_composer(doc)
        doc.box_vertical_alignment = BoxVerticalAlignment.CENTER
        # Dirty-marked but outside the composer's verified envelope:
        # honest staleness, never a silent guess.
        assert doc.composition_stale is True
        assert doc.composed_line_count == 6


class TestStaleComposedLines:
    """Composer-less fallback: cached lines clamp; out-of-text lines raise."""

    def test_shrink_clamps_first_line_and_raises_beyond(self) -> None:
        _app, doc = _fresh_doc("RangesBox")
        assert doc.composed_line_count == 6

        held = doc.character_range(0, 10)
        held_line = doc.composed_line_range(1)
        doc.text = "tiny"
        # Force the composer-less path: an uncalibrated document keeps
        # the stale cache (AE-parity clamp semantics).
        doc._composition_calibrated = False

        # The cached count stays (ExtendScript behavior on an un-reapplied
        # value object); line 0 clamps, deeper lines raise at creation.
        assert doc.composed_line_count == 6
        first = doc.composed_line_range(0)
        assert (first.character_start, first.character_end) == (0, 4)
        assert first.character_range().text == "tiny"
        with pytest.raises(ValueError, match="ComposedLine index range"):
            doc.composed_line_range(1)

        assert held.is_range_valid is False
        with pytest.raises(ValueError, match="Character index range"):
            _ = held.text
        assert held_line.is_range_valid is False

    def test_growth_revalidates_fixed_end_range(self) -> None:
        _app, doc = _fresh_doc("RangesBox")
        held = doc.character_range(0, 50)
        doc.text = "tiny"
        assert held.is_range_valid is False
        doc.text = "x" * 60
        assert held.is_range_valid is True
        assert held.character_end == 50
