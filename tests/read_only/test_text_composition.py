"""Composer parity against the box-matrix fixture.

`samples/models/text/box_matrix.aep` holds ~45 box-text layers generated
by `scripts/jsx/generate_box_matrix_sample.jsx`, sweeping the composition
parameter space. For every in-envelope layer the composer must reproduce
AE's persisted line spans and baselines exactly; every out-of-envelope
layer must be refused, never guessed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("uharfbuzz")

from helpers import parse_project

from py_aep.models.text.ranges import _cached_line_data
from py_aep.resolvers.text_composition import (
    CompositionUnsupported,
    _CharStyle,
    _shape_stretch,
    compose_lines,
)
from py_aep.svg.fonts import resolve_postscript

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "text"
FIXTURE = SAMPLES_DIR / "box_matrix.aep"

#: PostScript names the matrix layers' style runs compose with; CI
#: runners without them (e.g. ubuntu-latest) cannot exercise parity.
FIXTURE_FONTS = (
    "MyriadPro-Regular",
    "ArialMT",
    "Arial-BoldMT",
    "TimesNewRomanPSMT",
    "CourierNewPSMT",
)
if not all(resolve_postscript(name) for name in FIXTURE_FONTS):
    pytest.skip("box_matrix fixture fonts not installed", allow_module_level=True)

#: Layers the composer must refuse (unsupported features). Auto-hyphenate
#: is deliberately NOT here: it is AE's default and inert for the
#: single-line composer (M_HYPHENATE composes greedily like every other
#: layer).
REFUSED = {
    "M_ELC": "every-line composer",
    "M_OPTICAL": "optical",
    "M_TAB": "tab",
    "M_LIGA": "ligatures",
    "M_VERTICAL": "vertical",
    "M_RTL": "right-to-left",
    "M_NBSP": "no-break space",
}


@pytest.fixture(scope="module")
def docs() -> dict:
    project = parse_project(FIXTURE)
    comp = project.compositions[0]
    return {layer.name: layer.text.source_text.value for layer in comp.text_layers}


def test_every_matrix_layer_composes_or_refuses(docs) -> None:
    mismatches: list[str] = []
    composed_count = 0
    for name, doc in docs.items():
        if name in REFUSED:
            with pytest.raises(CompositionUnsupported):
                compose_lines(doc)
            continue
        cached = _cached_line_data(doc)
        assert cached is not None, name
        cached_spans, cached_baselines = cached
        try:
            composed = compose_lines(doc)
        except CompositionUnsupported as exc:
            mismatches.append(f"{name}: refused: {exc}")
            continue
        if composed.spans != cached_spans:
            mismatches.append(
                f"{name}: spans {composed.spans[:3]}... != {cached_spans[:3]}..."
            )
            continue
        for computed, expected in zip(composed.baselines, cached_baselines):
            if expected is not None and abs(computed - expected) > 0.05:
                mismatches.append(f"{name}: baseline {computed:.4f} != {expected:.4f}")
                break
        composed_count += 1
    assert not mismatches, "\n".join(mismatches)
    # The matrix must keep exercising the full in-envelope surface.
    assert composed_count >= 37


def test_refusal_reasons_are_specific(docs) -> None:
    for name, needle in REFUSED.items():
        with pytest.raises(CompositionUnsupported, match=needle):
            compose_lines(docs[name])


def test_overflow_matches_probe(docs) -> None:
    # The height-sweep layers overflow (600px of text in small boxes).
    for name in ("M_H40", "M_H55", "M_H70", "M_H90", "M_H120"):
        assert compose_lines(docs[name]).overflow is True
    assert compose_lines(docs["M_W300"]).overflow is False


def test_length_changing_case_map_is_refused() -> None:
    # 'straße'.upper() == 'STRASSE': clusters no longer map 1:1 onto the
    # source characters, so both caps modes must refuse, not crash.
    for caps in (1, 2):
        style = _CharStyle("ArialMT", {"1": 36.0, "12": caps})
        with pytest.raises(CompositionUnsupported, match="case mapping"):
            _shape_stretch("straße", style)
