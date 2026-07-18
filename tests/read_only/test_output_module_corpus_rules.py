"""Corpus self-validation: AE-written files must satisfy our own tables.

This is the independent oracle for the rules data: every value AE itself
stored must be inside the allowed set our tables claim for it. A failure
here means a wrong or too-narrow table row, not a bad file (this is how
the MP3 mono/stereo column swap and the Targa RGB+32bpp case were
caught).
"""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_app

_CORPUS_ROOTS = [
    SAMPLES_DIR / "models" / "format_options",
    SAMPLES_DIR / "models" / "renderqueue",
    SAMPLES_DIR / "unused" / "output_module",
    SAMPLES_DIR / "unused" / "output_module_settings",
    SAMPLES_DIR / "unused" / "renderqueue",
    SAMPLES_DIR / "unused" / "models" / "renderqueue",
]

_CORPUS = sorted(
    path for root in _CORPUS_ROOTS if root.is_dir() for path in root.rglob("*.aep")
)


@pytest.mark.parametrize(
    "aep_path",
    _CORPUS,
    ids=[str(p.relative_to(SAMPLES_DIR)) for p in _CORPUS],
)
def test_ae_written_state_passes_our_tables(aep_path) -> None:
    app = parse_app(aep_path)
    for rqi in app.project.render_queue.items:
        for om in rqi.output_modules:
            assert om.validate_state() == []
