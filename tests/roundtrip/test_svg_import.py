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

    def test_radial_gradient_transform_becomes_grad_scale(self) -> None:
        # The butterfly's four wings use radial gradients with a vertical
        # gradientTransform stretch (matrix(1 0 0 N ...), N in {2,3,4}). AE
        # 2026 stores that aspect ratio in Grad Scale; without it the wing
        # gradients render as circles instead of tall ellipses. Import into a
        # fresh (2026) project so the Grad Scale / Grad Rotation leaves exist.
        from py_aep import new

        app = new()
        opts = ImportOptions(ASSETS / "butterfly.svg")
        opts.import_as = ImportAsType.COMP_CROPPED_LAYERS
        comp = app.project.import_file(opts)
        assert isinstance(comp, CompItem)
        contents = comp.layers[0].property("ADBE Root Vectors Group")
        assert isinstance(contents, PropertyGroup)

        scales_y = []
        for group in contents.properties:
            if group.match_name != "ADBE Vector Group":
                continue
            inner = group["ADBE Vectors Group"]
            for child in inner.properties:
                if child.match_name != "ADBE Vector Graphic - G-Fill":
                    continue
                if child["ADBE Vector Grad Type"].value != 2.0:  # radial only
                    continue
                # Every radial gradient carries AE's 360-degree baseline.
                assert child["ADBE Vector Grad Rotation"].value == pytest.approx(360.0)
                scales_y.append(child["ADBE Vector Grad Scale"].value[1])
        # Five radial gradients: four stretched wings (200/200/300/400) plus
        # the unstretched body (100).
        assert sorted(round(s) for s in scales_y) == [100, 200, 200, 300, 400]


class TestSvgImportByteFidelity:
    """Byte-level fidelity fixes surfaced by aep-compare vs AE's import."""

    def test_gradient_paint_opacity_from_group(self, tmp_path: Path) -> None:
        # A group/element opacity over a GRADIENT fill/stroke goes into the
        # Fill/Stroke Opacity leaf (AE 2026 ground truth), NOT the alpha stops.
        # Unlike solid paints it is the RAW percentage, not 8-bit quantized:
        # AE reads the SVG opacity as float32, so 0.3 -> 30.000001907 (not the
        # solid-path 30.196). A fully-opaque gradient leaves Opacity defaulted.
        from py_aep import new

        svg = tmp_path / "go.svg"
        svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
            '<defs><linearGradient id="g" gradientUnits="objectBoundingBox"'
            ' x1="0" y1="0" x2="1" y2="0">'
            '<stop offset="0" stop-color="#f00"/>'
            '<stop offset="1" stop-color="#00f"/></linearGradient></defs>'
            '<g opacity="0.3"><rect width="40" height="40" fill="url(#g)"/></g>'
            '<g opacity="0.5"><rect x="50" y="50" width="40" height="40"'
            ' fill="none" stroke="url(#g)" stroke-width="6"/></g>'
            '<rect x="50" width="40" height="40" fill="url(#g)"/>'
            "</svg>"
        )
        app = new()
        opts = ImportOptions(svg)
        opts.import_as = ImportAsType.COMP_CROPPED_LAYERS
        comp = app.project.import_file(opts)
        assert isinstance(comp, CompItem)
        contents = comp.layers[0].property("ADBE Root Vectors Group")
        assert isinstance(contents, PropertyGroup)

        fill_ops: list[float] = []
        stroke_ops: list[float] = []
        for group in contents.properties:
            if group.match_name != "ADBE Vector Group":
                continue
            inner = group["ADBE Vectors Group"]
            for child in inner.properties:
                if child.match_name == "ADBE Vector Graphic - G-Fill":
                    fill_ops.append(child["ADBE Vector Fill Opacity"].value)
                    # opacity lives in the leaf, not the gradient alpha stops
                    grad = child["ADBE Vector Grad Colors"].value
                    assert all(s.alpha == 1.0 for s in grad.alpha_stops)
                elif child.match_name == "ADBE Vector Graphic - G-Stroke":
                    stroke_ops.append(child["ADBE Vector Stroke Opacity"].value)

        # 0.3 fill (float32-exact, not 8-bit), opaque control fill (default 100)
        assert sorted(fill_ops) == [
            pytest.approx(30.000001907, abs=1e-5),
            pytest.approx(100.0),
        ]
        assert stroke_ops == [pytest.approx(50.0)]

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

    def test_compound_path_gets_merge_paths(self) -> None:
        # A compound path (one SVG <path> with several subpaths) needs a Merge
        # Paths op so overlapping subpaths cut holes via the nonzero winding
        # rule; without it AE fills each subpath solid and the holes vanish. AE
        # adds exactly one (Merge Type 1) to every multi-subpath group and none
        # to single-subpath groups - mirror that.
        _app, comp = _import("butterfly")
        contents = comp.layers[0].property("ADBE Root Vectors Group")
        assert isinstance(contents, PropertyGroup)
        multi = single = 0
        for group in contents.properties:
            if group.match_name != "ADBE Vector Group":
                continue
            inner = group["ADBE Vectors Group"]
            nshapes = sum(
                1
                for c in inner.properties
                if c.match_name == "ADBE Vector Shape - Group"
            )
            merges = [
                c
                for c in inner.properties
                if c.match_name == "ADBE Vector Filter - Merge"
            ]
            if nshapes > 1:
                multi += 1
                assert len(merges) == 1, f"{group.name}: nshapes={nshapes}"
                assert merges[0]["ADBE Vector Merge Type"].value == 1.0
            else:
                single += 1
                assert not merges, f"{group.name} (single subpath) has a Merge"
        assert multi == 3 and single == 18  # butterfly: 3 compound, 18 simple

    def test_layer_styles_synthesized_disabled(self, tmp_path: Path) -> None:
        # Every layer style must stay OFF on a freshly synthesized layer. The
        # tdsb enable bit (bit 0) is written to disk, so a stray "enabled"
        # toggle makes AE apply that style on open - notably a default-red
        # Color Overlay, which painted the whole shape red. The in-memory
        # state is masked by _derive_layer_styles_enabled, so the bug only
        # surfaces after a save + reparse: check there.
        app = parse(BASE)
        comp = app.project.root_folder.add_comp("T", 100, 100, 1.0, 1.0, 30.0)
        comp.add_shape()
        out = tmp_path / "ls.aep"
        app.project.save(out)

        reparsed = parse(out)
        layer = next(
            item.layers[0]
            for item in reparsed.project.items.values()
            if getattr(item, "layers", None)
        )
        styles = layer["ADBE Layer Styles"]
        assert isinstance(styles, PropertyGroup)
        assert styles.enabled is False
        assert styles._tdsb is not None and styles._tdsb.synthetic is False
        assert styles._tdsb._enable_flags == 3  # enabled+collapsed parent
        for child in styles.properties:
            assert child.enabled is False, child.match_name
            assert child._tdsb is not None
            # Blending Options mirrors the parent (3); the 10 style toggles
            # are disabled (2 = bit 0 clear).
            expected = 3 if child.match_name == "ADBE Blend Options Group" else 2
            assert child._tdsb._enable_flags == expected, child.match_name

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
