"""The layer-style documents of `samples/assets/psd_styles` against AE 2026's
import of them.

The documents come from `scripts/jsx/make_psd_styles_assets.jsx`: one case per
file (bevel styles and techniques, Stroke Emboss keyed on the stroke position
and size, glows, satin, the contour and gloss anti-alias flags, a styled text
layer, a Levels adjustment layer in a CMYK and a Lab document).
`samples/models/import/psd_styles_corpus.aep` holds every file imported as
COMP_CROPPED_LAYERS with merged layer styles, plus the Stroke Emboss files
imported as COMP with editable styles (comps named `<stem>|editable`).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import SAMPLES_DIR, get_comp, parse_project

import py_aep
from py_aep.enums.general import ImportAsType
from py_aep.models.import_options import ImportOptions
from py_aep.models.items.composition import CompItem
from py_aep.resolvers.psd_styles import merged_styles_bounds, read_global_light
from py_aep.resolvers.source_layers import psd_leaf_layers

CORPUS = SAMPLES_DIR / "assets" / "psd_styles"
FIXTURE = SAMPLES_DIR / "models" / "import" / "psd_styles_corpus.aep"
STYLED_PSDS = sorted(
    psd for psd in CORPUS.glob("*.psd") if not psd.stem.endswith("-levels")
)
STROKE_EMBOSS = [
    "bevel-stroke-smooth",
    "bevel-stroke-chisel-hard",
    "bevel-stroke-chisel-soft",
    "bevel-stroke-emboss-center-stroke-chisel-soft",
    "bevel-stroke-emboss-inside-stroke",
]


def _comp(name: str) -> CompItem:
    return get_comp(parse_project(FIXTURE), name)


def _layer_box(layer) -> tuple[float, float, float, float]:
    """Where a cropped PSD layer sits on the canvas, from its footage size
    and transform."""
    px, py = layer.transform.property("ADBE Position").value[:2]
    ax, ay = layer.transform.property("ADBE Anchor Point").value[:2]
    return (
        px - ax,
        py - ay,
        px - ax + layer.source.width,
        py - ay + layer.source.height,
    )


def _bevel_style(layer) -> float:
    for group in layer.property("ADBE Layer Styles"):
        if "bevelEmboss" in group.match_name:
            for leaf in group:
                if leaf.match_name == "bevelEmboss/bevelStyle":
                    return leaf.value
    raise AssertionError("no bevelStyle leaf")


@pytest.mark.parametrize("psd", STYLED_PSDS, ids=[p.stem for p in STYLED_PSDS])
def test_merged_styles_bounds_match_ae(psd: Path) -> None:
    comp = _comp(psd.stem)
    angle = read_global_light(psd)[0]
    for leaf in psd_leaf_layers(psd):
        if leaf.style_blocks is None or leaf.style_blocks.effects is None:
            continue
        ae = next(layer for layer in comp.layers if layer.name == leaf.name)
        assert merged_styles_bounds(leaf, angle) == _layer_box(ae), leaf.name


@pytest.mark.parametrize("psd", STYLED_PSDS, ids=[p.stem for p in STYLED_PSDS])
def test_cropped_merge_import_matches_ae(psd: Path) -> None:
    options = ImportOptions(psd)
    options.import_as = ImportAsType.COMP_CROPPED_LAYERS
    options.layer_styles = "merge"
    comp = py_aep.new().project.import_file(options)
    assert isinstance(comp, CompItem)
    ae_comp = _comp(psd.stem)
    assert [layer.name for layer in comp.layers] == [
        layer.name for layer in ae_comp.layers
    ]
    for layer, ae in zip(comp.layers, ae_comp.layers):
        assert (layer.source.width, layer.source.height) == (
            ae.source.width,
            ae.source.height,
        ), layer.name
        assert _layer_box(layer) == _layer_box(ae), layer.name


@pytest.mark.parametrize("stem", STROKE_EMBOSS)
def test_editable_stroke_emboss_style(stem: str) -> None:
    ae = next(
        layer for layer in _comp(f"{stem}|editable").layers if layer.name == "shape"
    )
    assert _bevel_style(ae) == 5.0
    options = ImportOptions(CORPUS / f"{stem}.psd")
    options.import_as = ImportAsType.COMP
    options.layer_styles = "editable"
    comp = py_aep.new().project.import_file(options)
    assert isinstance(comp, CompItem)
    shape = next(layer for layer in comp.layers if layer.name == "shape")
    assert _bevel_style(shape) == 5.0


@pytest.mark.xfail(
    strict=True,
    reason="AE imports a CMYK or Lab document as one flattened layer; py_aep still "
    "builds one layer per record (W4 follow-up)",
)
@pytest.mark.parametrize("mode", ["cmyk8", "lab8"])
def test_cmyk_and_lab_documents_import_flattened(mode: str) -> None:
    psd = CORPUS / f"{mode}-levels.psd"
    options = ImportOptions(psd)
    options.import_as = ImportAsType.COMP_CROPPED_LAYERS
    options.layer_styles = "merge"
    comp = py_aep.new().project.import_file(options)
    assert isinstance(comp, CompItem)
    assert [layer.name for layer in comp.layers] == [psd.name]
