"""Tests for the font/baseline/reset text APIs against AE 2026 ground truth.

Every expectation here is a value After Effects itself reported via
ExtendScript (2026-07-15 probe run); the `*_probe.json` files next to the
samples are those dumps, and the `*_after.aep` files are AE's own output for
the same operation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import parse_project
from helpers import parse_project_fresh

from py_aep.enums import AutoKernType
from py_aep.models.layers import TextLayer
from py_aep.models.text.text_document import TextDocument

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "text"
BASELINES_AEP = SAMPLES_DIR / "baseline_locs.aep"
REPLACE_FONT_AEP = SAMPLES_DIR / "replace_font.aep"
REPLACE_FONT_AFTER_AEP = SAMPLES_DIR / "replace_font_after.aep"
RESET_AEP = SAMPLES_DIR / "reset_style.aep"

# AE reports an empty line's start/end as the maximum 32-bit float.
FLT_MAX = 3.4028234663852886e38


def _fixture(name: str) -> dict:
    with open(SAMPLES_DIR / name, encoding="utf-8") as fp:
        return json.load(fp)


def _doc(project, comp_name: str, layer_name: str) -> TextDocument:
    comp = next(c for c in project.compositions if c.name == comp_name)
    layer = next(ly for ly in comp.layers if ly.name == layer_name)
    assert isinstance(layer, TextLayer)
    return layer.text["ADBE Text Document"].value


class TestBaselineLocs:
    """TextDocument.baseline_locs vs AE's own baselineLocs dump."""

    @pytest.mark.parametrize("layer_name", ["text_point", "text_box", "text_animated"])
    def test_matches_ae(self, layer_name: str) -> None:
        expected = _fixture("baseline_locs_probe.json")[layer_name]["baselineLocs"][
            "value"
        ]
        got = _doc(parse_project(BASELINES_AEP), "PROBE_MAIN", layer_name).baseline_locs
        assert len(got) == len(expected)
        for g, w in zip(got, expected):
            if w > 1e38:  # empty-line sentinel
                assert g == pytest.approx(FLT_MAX)
            else:
                assert g == pytest.approx(w, abs=5e-3)

    def test_empty_line_is_float_max(self) -> None:
        # "Hello\rWorld line two\r\rAfter empty": the third line is empty.
        locs = _doc(
            parse_project(BASELINES_AEP), "PROBE_MAIN", "text_point"
        ).baseline_locs
        assert locs[8:12] == [FLT_MAX] * 4

    def test_box_text_offset_by_box_pos(self) -> None:
        # A box's cached origins are box-relative; layer coordinates add
        # box_text_pos (AE: -110/-70 for a centered 220x140 box).
        doc = _doc(parse_project(BASELINES_AEP), "PROBE_MAIN", "text_box")
        assert doc.box_text_pos == [-110.0, -70.0]
        assert doc.baseline_locs[0] == pytest.approx(-110.0)

    def test_four_floats_per_composed_line(self) -> None:
        doc = _doc(parse_project(BASELINES_AEP), "PROBE_MAIN", "text_box")
        assert len(doc.baseline_locs) == 4 * (doc.composed_line_count or 0)

    def test_detached_document_is_empty(self) -> None:
        assert TextDocument("hi").baseline_locs == []


class TestUsedFonts:
    """Project.used_fonts vs AE's usedFonts dump."""

    def _snapshot(self, project) -> list:
        return [
            (
                entry["font"].post_script_name,
                [(u["layer_id"], u["layer_time"]) for u in entry["used_at"]],
            )
            for entry in project.used_fonts
        ]

    def _expected(self, records: list) -> list:
        return [
            (
                rec["font"]["postScriptName"],
                [(u["layerID"], float(u["layerTimeD"])) for u in rec["usedAt"]],
            )
            for rec in records
        ]

    def test_matches_ae(self) -> None:
        expected = _fixture("used_fonts_probe.json")["value"]
        project = parse_project(BASELINES_AEP)
        assert self._snapshot(project) == self._expected(expected)

    def test_mixed_and_keyframed_fonts_match_ae(self) -> None:
        # Four fonts, a mixed-font document, and a font-keyframed layer.
        expected = _fixture("replace_font_probe.json")["before"]["usedFonts"]["value"]
        project = parse_project(REPLACE_FONT_AEP)
        assert self._snapshot(project) == self._expected(expected)

    def test_sorted_by_post_script_name(self) -> None:
        names = [
            e["font"].post_script_name
            for e in parse_project(REPLACE_FONT_AEP).used_fonts
        ]
        assert names == sorted(names)


class TestReplaceFont:
    """Project.replace_font vs AE's own replaceFont output."""

    def _layer_state(self, project) -> dict:
        from py_aep.models.text.ranges import _char_run_spans

        comp = next(c for c in project.compositions if c.name == "RFONT")
        state = {}
        for name in ("rfont_uniform", "rfont_mixed", "rfont_keyed"):
            layer = next(ly for ly in comp.layers if ly.name == name)
            prop = layer.text["ADBE Text Document"]
            docs = [kf.value for kf in prop.keyframes] or [prop.value]
            state[name] = (
                [f.post_script_name for f in docs[0]._fonts],
                [
                    [(s, e, style.get("0")) for s, e, style in _char_run_spans(d)]
                    for d in docs
                ],
            )
        return state

    def test_matches_ae_font_tables_and_runs(self) -> None:
        project = parse_project_fresh(REPLACE_FONT_AEP)
        assert project.replace_font("Verdana", "Georgia") is True
        # AE inserts the replacement directly after the replaced font and
        # keeps the old entry; unaffected runs are untouched.
        assert self._layer_state(project) == self._layer_state(
            parse_project(REPLACE_FONT_AFTER_AEP)
        )

    def test_used_fonts_after_replace_matches_ae(self) -> None:
        project = parse_project_fresh(REPLACE_FONT_AEP)
        project.replace_font("Verdana", "Georgia")
        expected = _fixture("replace_font_probe.json")["after"]["usedFonts"]["value"]
        got = [
            (
                e["font"].post_script_name,
                [(u["layer_id"], u["layer_time"]) for u in e["used_at"]],
            )
            for e in project.used_fonts
        ]
        want = [
            (
                r["font"]["postScriptName"],
                [(u["layerID"], float(u["layerTimeD"])) for u in r["usedAt"]],
            )
            for r in expected
        ]
        assert got == want

    def test_same_font_is_noop(self) -> None:
        project = parse_project_fresh(REPLACE_FONT_AEP)
        before = self._layer_state(project)
        assert project.replace_font("Verdana", "Verdana") is False
        assert self._layer_state(project) == before

    def test_unused_font_returns_false(self) -> None:
        project = parse_project_fresh(REPLACE_FONT_AEP)
        assert project.replace_font("NotInstalledFontXYZ", "Georgia") is False

    def test_accepts_font_objects(self) -> None:
        project = parse_project_fresh(REPLACE_FONT_AEP)
        verdana = next(
            e["font"]
            for e in project.used_fonts
            if e["font"].post_script_name == "Verdana"
        )
        assert project.replace_font(verdana, "Georgia") is True

    def test_survives_save_and_reparse(self, tmp_path: Path) -> None:
        project = parse_project_fresh(REPLACE_FONT_AEP)
        project.replace_font("Verdana", "Georgia")
        out = tmp_path / "replaced.aep"
        project.save(out)
        names = [
            e["font"].post_script_name for e in parse_project_fresh(out).used_fonts
        ]
        assert "Georgia" in names
        assert "Verdana" not in names


class TestResetStyles:
    """reset_char_style / reset_paragraph_style vs AE's own reset output.

    After Effects restores its Character/Paragraph panel defaults, which
    live in the AE preferences rather than the project file; py_aep reads
    the same `["Text Style Sheet"]` / `["Text Paragraph Sheet"]` sections.
    """

    CHAR_MAP = {
        "font": "font",
        "fontSize": "font_size",
        "fauxBold": "faux_bold",
        "fauxItalic": "faux_italic",
        "applyFill": "apply_fill",
        "applyStroke": "apply_stroke",
        "strokeWidth": "stroke_width",
        "strokeOverFill": "stroke_over_fill",
        "tracking": "tracking",
        "tsume": "tsume",
        "horizontalScale": "horizontal_scale",
        "verticalScale": "vertical_scale",
        "baselineShift": "baseline_shift",
        "autoLeading": "auto_leading",
    }
    PARA_MAP = {
        "justification": "justification",
        "firstLineIndent": "first_line_indent",
        "startIndent": "start_indent",
        "endIndent": "end_indent",
        "spaceBefore": "space_before",
        "spaceAfter": "space_after",
        "hangingRoman": "hanging_roman",
        "everyLineComposer": "every_line_composer",
    }

    def test_char_reset_matches_ae(self) -> None:
        expected = _fixture("reset_style_probe.json")["char_after"]
        doc = _doc(parse_project_fresh(RESET_AEP), "RESET2", "rc_char")
        doc.reset_char_style()
        for ae_key, py_key in self.CHAR_MAP.items():
            got, want = getattr(doc, py_key), expected[ae_key]
            if isinstance(want, bool) or isinstance(want, str):
                assert got == want, py_key
            else:
                assert float(got) == pytest.approx(float(want), abs=1e-3), py_key

    def test_char_reset_collapses_runs(self) -> None:
        from py_aep.models.text.ranges import _char_run_spans

        doc = _doc(parse_project_fresh(RESET_AEP), "RESET2", "rc_char")
        doc.reset_char_style()
        # AE leaves a single character run spanning the whole document.
        assert len(_char_run_spans(doc)) == 1

    def test_paragraph_reset_matches_ae(self) -> None:
        expected = _fixture("reset_style_probe.json")["para_after"]
        doc = _doc(parse_project_fresh(RESET_AEP), "RESET2", "rp_para")
        doc.reset_paragraph_style()
        for ae_key, py_key in self.PARA_MAP.items():
            got, want = getattr(doc, py_key), expected[ae_key]
            if isinstance(want, bool):
                assert got == want, py_key
            else:
                assert float(got) == pytest.approx(float(want), abs=1e-3), py_key

    def test_paragraph_reset_keeps_auto_hyphenate(self) -> None:
        # Hyphenation has no entry in the Paragraph panel sheet, so AE
        # leaves it alone (probed: True before and after).
        expected = _fixture("reset_style_probe.json")["para_after"]["autoHyphenate"]
        doc = _doc(parse_project_fresh(RESET_AEP), "RESET2", "rp_para")
        doc.reset_paragraph_style()
        assert doc.auto_hyphenate == expected

    def test_reset_without_prefs_uses_factory_defaults(self) -> None:
        # Parsed with no preferences directory: AE's factory panel values.
        doc = _doc(parse_project_fresh(RESET_AEP), "RESET2", "rc_char")
        doc.reset_char_style()
        assert doc.font == "MyriadPro-Regular"
        assert doc.font_size == pytest.approx(36.0)
        assert doc.fill_color == pytest.approx([0.92156994342804] * 3)

    def test_detached_document_raises(self) -> None:
        for method in ("reset_char_style", "reset_paragraph_style"):
            with pytest.raises(ValueError, match="not associated with a layer"):
                getattr(TextDocument("hi"), method)()

    def test_reset_survives_save_and_reparse(self, tmp_path: Path) -> None:
        project = parse_project_fresh(RESET_AEP)
        doc = _doc(project, "RESET2", "rc_char")
        doc.reset_char_style()
        out = tmp_path / "reset.aep"
        project.save(out)
        reparsed = _doc(parse_project_fresh(out), "RESET2", "rc_char")
        assert reparsed.font_size == pytest.approx(36.0)
        assert reparsed.faux_bold is False


class TestFuzzRegressions:
    """Bugs found by the v6 API fuzz campaign (scripts/dev/apifuzz/gen_v6.py).

    Neither was visible to the "AE opens the file" oracle: one crashed a
    read-only getter on a committed sample, the other silently skipped work.
    """

    BOX_MATRIX = SAMPLES_DIR / "box_matrix.aep"
    WRITES = SAMPLES_DIR / "text_writes.aep"

    def test_baseline_locs_on_ligated_text(self) -> None:
        # The stored advances carry one entry per GLYPH: "affinity " is 9
        # characters but 7 glyphs once "ffi" ligates, so indexing advances by
        # character position ran off the end (IndexError).
        project = parse_project(self.BOX_MATRIX)
        comp = project.compositions[0]
        doc = _doc(project, comp.name, "M_LIGA")
        locs = doc.baseline_locs
        assert len(locs) == 4 * (doc.composed_line_count or 0)
        # Line 0 is "affinity " - the extent excludes the trailing space.
        assert locs[2] == pytest.approx(locs[0] + 104.292, abs=5e-3)

    def test_baseline_locs_never_raises_across_the_matrix(self) -> None:
        # 45 text layers covering ligatures, tabs, optical kerning, vertical
        # text, giant words and hyphens.
        project = parse_project(self.BOX_MATRIX)
        for comp in project.compositions:
            for layer in comp.layers:
                if layer.text is None:
                    continue
                locs = layer.text["ADBE Text Document"].value.baseline_locs
                assert len(locs) % 4 == 0

    def test_reset_char_style_resets_kerning(self) -> None:
        # AE's reset takes autoKernType back to the panel default (Metric),
        # which also clears any MANUAL kerning - probed AE 2026. Without it
        # the character runs could not collapse.
        from py_aep.cos.cos import cos_get
        from py_aep.models.text.ranges import _char_run_spans

        project = parse_project_fresh(self.WRITES)
        comp = project.compositions[0]
        doc = _doc(project, comp.name, "W_KERN_START")
        assert doc.auto_kern_type == AutoKernType.NO_AUTO_KERN
        assert cos_get(doc._doc, "0", "8") is not None  # manual kern runs

        doc.reset_char_style()

        assert doc.auto_kern_type == AutoKernType.METRIC_KERN
        assert cos_get(doc._doc, "0", "8") is None  # manual kerning cleared
        assert len(_char_run_spans(doc)) == 1

    def test_replace_font_reaches_duplicate_table_entries(self) -> None:
        # A font table can hold several entries with one PostScript name (AE
        # writes a second MyriadPro-Regular when a style reset re-applies the
        # panel font). reset_para's runs point at the SECOND one, so matching
        # only the first silently skipped the layer.
        project = parse_project_fresh(REPLACE_FONT_AEP)
        doc = _doc(project, "RESET", "reset_para")
        names = [f.post_script_name for f in doc._fonts]
        assert names.count("MyriadPro-Regular") == 2, "sample lost its duplicate"
        assert [f.post_script_name for f in doc._used_font_objects()] == [
            "MyriadPro-Regular"
        ]

        assert project.replace_font("MyriadPro-Regular", "Georgia") is True

        assert [f.post_script_name for f in doc._used_font_objects()] == ["Georgia"]
        assert "MyriadPro-Regular" not in [
            e["font"].post_script_name for e in project.used_fonts
        ]
