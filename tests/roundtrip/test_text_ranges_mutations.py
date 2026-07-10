"""Mutation tests for the text-range prerequisites.

Covers the AE-parity behaviors around py-side edits: the `text` setter's
style-run rebuild (probed via the `RangesTextReset` fixture), trailing
line-break preservation, and the stale composed-line clamp semantics.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import parse_app_fresh

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "text"
SAMPLE = SAMPLES_DIR / "text_ranges.aep"


def _fresh_doc(name: str, app=None):
    app = app or parse_app_fresh(SAMPLE)
    comp = app.project.compositions[0]
    layer = next(ly for ly in comp.text_layers if ly.name == name)
    return app, layer.text.source_text.value


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


class TestStaleComposedLines:
    """AE-parity staleness: cached lines clamp; out-of-text lines raise."""

    def test_shrink_clamps_first_line_and_raises_beyond(self) -> None:
        _app, doc = _fresh_doc("RangesBox")
        assert doc.composed_line_count == 6

        held = doc.character_range(0, 10)
        held_line = doc.composed_line_range(1)
        doc.text = "tiny"

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
