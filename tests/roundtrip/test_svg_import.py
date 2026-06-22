"""Tests for importing SVGs as cropped comps (`Project.import_file`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep import ImportAsType, ImportOptions, parse
from py_aep.models.items.composition import CompItem
from py_aep.models.layers.shape_layer import ShapeLayer
from py_aep.models.properties.property_group import PropertyGroup

SAMPLES = Path(__file__).parent.parent.parent / "samples"
BASE = SAMPLES / "models" / "folder" / "folder.aep"
ASSETS = SAMPLES / "assets"


def _import(name: str) -> tuple[object, CompItem]:
    app = parse(BASE)
    opts = ImportOptions(ASSETS / f"{name}.svg")
    opts.import_as = ImportAsType.COMP_CROPPED_LAYERS
    comp = app.project.import_file(opts)
    assert isinstance(comp, CompItem)
    return app, comp


class TestSvgImportBasics:
    def test_can_import_svg_as_cropped(self) -> None:
        opts = ImportOptions(ASSETS / "svg.svg")
        assert opts.can_import_as(ImportAsType.COMP_CROPPED_LAYERS) is True
        assert opts.can_import_as(ImportAsType.FOOTAGE) is False
        assert opts.can_import_as(ImportAsType.COMP) is False

    def test_footage_import_of_svg_rejected(self) -> None:
        app = parse(BASE)
        opts = ImportOptions(ASSETS / "svg.svg")  # default import_as = FOOTAGE
        with pytest.raises(ValueError, match="[Uu]nsupported footage format"):
            app.project.import_file(opts)

    def test_cropped_import_of_unsupported_format_rejected(self) -> None:
        # COMP_CROPPED_LAYERS is supported for SVG and layered .psd/.psb;
        # other formats (here audio) are still rejected.
        app = parse(BASE)
        opts = ImportOptions(ASSETS / "click.aiff")
        opts.import_as = ImportAsType.COMP_CROPPED_LAYERS
        with pytest.raises(ValueError, match="COMP_CROPPED_LAYERS"):
            app.project.import_file(opts)

    def test_creates_comp_and_single_shape_layer(self) -> None:
        _app, comp = _import("svg")
        assert comp.name == "svg.svg"
        assert (comp.width, comp.height) == (1070, 456)
        assert comp.frame_rate == 30.0
        assert len(comp.layers) == 1
        assert isinstance(comp.layers[0], ShapeLayer)
        assert comp.layers[0].name == "svg.svg"

    def test_group_count_matches_ae(self) -> None:
        # AE 2026 produces 29 vector groups for this SVG.
        _app, comp = _import("svg")
        contents = comp.layers[0].property("ADBE Root Vectors Group")
        assert isinstance(contents, PropertyGroup)
        groups = [g for g in contents.properties if g.match_name == "ADBE Vector Group"]
        assert len(groups) == 29

    def test_reverse_document_order(self) -> None:
        # AE Contents index 0 is the SVG's last-painted shape; the reader
        # lists document order, so the first group is the last drawable.
        # Vertices are stored centred on their bbox, with the offset in the
        # group's Vector Position (matching AE), so reconstruct the absolute
        # vertex before comparing.
        from py_aep.svg import read_svg

        doc = read_svg(ASSETS / "svg.svg")
        _app, comp = _import("svg")
        contents = comp.layers[0].property("ADBE Root Vectors Group")
        group = contents.properties[0]
        inner = group["ADBE Vectors Group"]
        path = inner["ADBE Vector Shape - Group"]["ADBE Vector Shape"].value
        pos = next(
            p
            for p in group["ADBE Vector Transform Group"].properties
            if p.match_name == "ADBE Vector Position"
        ).value
        abs_v0 = [path.vertices[0][0] + pos[0], path.vertices[0][1] + pos[1]]
        last_drawable_v0 = doc.drawables[-1].subpaths[0].vertices[0]
        assert abs_v0[0] == pytest.approx(last_drawable_v0[0], abs=1e-3)
        assert abs_v0[1] == pytest.approx(last_drawable_v0[1], abs=1e-3)

    def test_roundtrip_byte_identical(self, tmp_path: Path) -> None:
        app, _comp = _import("svg")
        out = tmp_path / "svg_cropped.aep"
        app.project.save(out)
        again = tmp_path / "svg_cropped_2.aep"
        parse(out).project.save(again)
        assert out.read_bytes() == again.read_bytes()


class TestSvgImportGradients:
    def test_butterfly_gradient_fills(self) -> None:
        _app, comp = _import("butterfly")
        assert (comp.width, comp.height) == (2434, 1699)
        contents = comp.layers[0].property("ADBE Root Vectors Group")
        gfills = 0
        for group in contents.properties:
            if group.match_name != "ADBE Vector Group":
                continue
            inner = group["ADBE Vectors Group"]
            for child in inner.properties:
                if child.match_name == "ADBE Vector Graphic - G-Fill":
                    gfills += 1
                    grad = child["ADBE Vector Grad Colors"].value
                    assert len(grad.color_stops) >= 2
                    assert child["ADBE Vector Grad Type"].value in (1.0, 2.0)
        # AE imported 15 gradient paints (10 linear + 5 radial).
        assert gfills == 15

    def test_butterfly_roundtrip(self, tmp_path: Path) -> None:
        app, _comp = _import("butterfly")
        out = tmp_path / "butterfly.aep"
        app.project.save(out)
        again = tmp_path / "butterfly_2.aep"
        parse(out).project.save(again)
        assert out.read_bytes() == again.read_bytes()


class TestSvgImportByteFidelity:
    """Byte-level fidelity fixes surfaced by aep-compare vs AE's import."""

    def test_shape_layer_anchor_written_raw(self) -> None:
        # AE stores a shape layer's anchor in raw pixels (not normalized by
        # comp size). Setting it must write the raw cdat, not value/comp.
        from typing import cast

        from py_aep.binary.utils import find_by_type
        from py_aep.models.properties.property import Property

        app = parse(BASE)
        comp = app.project.root_folder.add_comp("T", 1070, 456, 1.0, 1.0, 30.0)
        layer = comp.add_shape()
        anchor = cast(Property, layer.transform["ADBE Anchor Point"])
        anchor.value = [535.0, 228.0, 0.0]
        cdat = find_by_type(chunks=anchor._tdbs.chunks, chunk_type="cdat")
        assert list(cdat.values)[:3] == [535.0, 228.0, 0.0]

    def test_vector_materials_group_tdsb_collapsed(self) -> None:
        # AE writes the Vector Materials Group tdsb with _enable_flags=3
        # (enabled + collapsed); py defaulted to 1.
        app = parse(BASE)
        comp = app.project.root_folder.add_comp("T", 100, 100, 1.0, 1.0, 30.0)
        layer = comp.add_shape()
        contents = layer["ADBE Root Vectors Group"]
        group = contents.add_property("ADBE Vector Group")
        materials = group["ADBE Vector Materials Group"]
        tdsb = next(
            c
            for c in materials._tdgp.chunks
            if getattr(c, "chunk_type", None) == "tdsb"
        )
        assert tdsb._enable_flags == 3

    def test_menu_leaf_has_no_bound_chunks(self) -> None:
        # Bounded but non-animatable menu leaves (e.g. Stroke Line Cap) must
        # NOT get tdum/tduM bound chunks - AE omits them.
        app = parse(BASE)
        comp = app.project.root_folder.add_comp("T", 100, 100, 1.0, 1.0, 30.0)
        layer = comp.add_shape()
        contents = layer["ADBE Root Vectors Group"]
        stroke = contents.add_property("ADBE Vector Graphic - Stroke")
        cap = stroke["ADBE Vector Stroke Line Cap"]
        cap.value = 2.0  # round - non-default, forces materialization
        assert cap.can_vary_over_time is False
        kinds = [c.chunk_type for c in cap._tdbs.chunks]
        assert "tdum" not in kinds and "tduM" not in kinds

    def test_group_opacity_baked_into_paint_opacity(self) -> None:
        # AE bakes an SVG element/group opacity into the paint's Fill/Stroke
        # Opacity, 8-bit quantized (0.3 -> 77/255*100 = 30.196), and IGNORES
        # the fill-opacity/stroke-opacity attributes. Verified byte-for-byte
        # against AE 2026's own import of svg.svg (two <g opacity="0.3">
        # fills -> 30.196; its four stroke-opacity="0.5" strokes -> 100).
        _app, comp = _import("svg")
        contents = comp.layers[0].property("ADBE Root Vectors Group")
        fills, strokes = [], []
        for group in contents.properties:
            if group.match_name != "ADBE Vector Group":
                continue
            inner = group["ADBE Vectors Group"]
            for child in inner.properties:
                if child.match_name == "ADBE Vector Graphic - Fill":
                    fills.append(child["ADBE Vector Fill Opacity"].value)
                elif child.match_name == "ADBE Vector Graphic - Stroke":
                    strokes.append(child["ADBE Vector Stroke Opacity"].value)
        low = sorted(v for v in fills if v < 99.9)
        assert low == [pytest.approx(30.19607925, abs=1e-5)] * 2
        assert all(v == pytest.approx(100.0) for v in strokes)
