"""Tests for Project.auto_fix_expressions.

AE 2026 semantics (2026-07-14 probe run): quoted references in both quote
styles are replaced across enabled expressions - including inside comments
of a rewritten expression - and disabled expressions are never touched.
py_aep's replacement gate diverges deliberately: AE only rewrites
expressions that currently ERROR (runtime state not stored in the file), so
py_aep rewrites every enabled expression containing the quoted text. All
five AE fixture cases were verified to produce identical results.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import parse_project_fresh

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "property"
SAMPLE = SAMPLES_DIR / "is_modified_false.aep"


def _opacity(project):
    return project.compositions[0].layers[0].transform["ADBE Opacity"]


class TestAutoFixExpressions:
    def test_double_quoted_reference_replaced(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLE)
        prop = _opacity(project)
        prop.expression = 'thisComp.layer("Ghost").transform.opacity'
        project.auto_fix_expressions("Ghost", "Real")
        assert prop.expression == 'thisComp.layer("Real").transform.opacity'

    def test_single_quoted_reference_replaced(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLE)
        prop = _opacity(project)
        prop.expression = "thisComp.layer('Ghost').transform.opacity / 2"
        project.auto_fix_expressions("Ghost", "Real")
        assert prop.expression == "thisComp.layer('Real').transform.opacity / 2"

    def test_disabled_expression_untouched(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLE)
        prop = _opacity(project)
        prop.expression = 'thisComp.layer("Ghost").transform.opacity'
        prop.expression_enabled = False
        project.auto_fix_expressions("Ghost", "Real")
        assert prop.expression == 'thisComp.layer("Ghost").transform.opacity'
        assert prop.expression_enabled is False

    def test_unquoted_text_untouched(self, tmp_path: Path) -> None:
        # AE parity for the probed comment case: an unquoted mention is
        # not a reference and is never rewritten.
        project = parse_project_fresh(SAMPLE)
        prop = _opacity(project)
        prop.expression = "// Ghost mentioned in comment only\n50"
        project.auto_fix_expressions("Ghost", "Real")
        assert prop.expression == "// Ghost mentioned in comment only\n50"

    def test_comment_occurrence_in_rewritten_expression(self, tmp_path: Path) -> None:
        # AE replaces plain-text across the whole broken expression,
        # including quoted occurrences inside comments (probed case_c).
        project = parse_project_fresh(SAMPLE)
        prop = _opacity(project)
        prop.expression = (
            '// see "Ghost" for details\nthisComp.layer("Ghost").transform.opacity'
        )
        project.auto_fix_expressions("Ghost", "Real")
        assert prop.expression == (
            '// see "Real" for details\nthisComp.layer("Real").transform.opacity'
        )

    def test_empty_old_text_is_noop(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLE)
        prop = _opacity(project)
        prop.expression = 'thisComp.layer("Ghost").transform.opacity'
        project.auto_fix_expressions("", "Real")
        assert prop.expression == 'thisComp.layer("Ghost").transform.opacity'

    def test_non_string_raises(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLE)
        with pytest.raises(TypeError):
            project.auto_fix_expressions(5, "Real")  # type: ignore[arg-type]

    def test_fix_survives_save_and_reparse(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLE)
        prop = _opacity(project)
        prop.expression = 'thisComp.layer("Ghost").transform.opacity'
        project.auto_fix_expressions("Ghost", "Real")
        out = tmp_path / "fixed.aep"
        project.save(out)
        reparsed = parse_project_fresh(out)
        assert _opacity(reparsed).expression == (
            'thisComp.layer("Real").transform.opacity'
        )
