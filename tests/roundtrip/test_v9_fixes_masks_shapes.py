"""Regression tests for the v9 fuzz findings on masks, paths and effects.

After Effects numbers below were measured on AE 2026 (26.0x67) running the
same scripted operation on a `py_aep.new()` project holding a 400x300 comp
("C") with a 200x100 solid, then reading the values back and saving.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import project_bytes

import py_aep
from py_aep import parse
from py_aep.binary.utils import filter_by_list_type, find_by_type
from py_aep.models.properties.shape import Shape

SAMPLES = Path(__file__).parent.parent.parent / "samples"
FEATHER = SAMPLES / "models" / "property" / "shape_feather.aep"

ZERO3 = [[0.0, 0.0]] * 3
TRIANGLE = [[10.0, 10.0], [150.0, 20.0], [100.0, 90.0]]
QUAD = [[10.0, 10.0], [150.0, 20.0], [100.0, 90.0], [20.0, 80.0]]


def _solid_mask(width: int = 200, height: int = 100):  # type: ignore[no-untyped-def]
    app = py_aep.new()
    comp = app.project.root_folder.add_comp("C", 400, 300, 1.0, 5.0, 24.0)
    solid = comp.add_solid([1.0, 0.0, 0.0], "S", width, height, 1.0)
    mask = solid.masks.add_property("ADBE Mask Atom")
    return app, comp, solid, mask


def _reparse_mask(app: py_aep.Application, tmp_path: Path):  # type: ignore[no-untyped-def]
    path = tmp_path / "out.aep"
    app.project.save(path)
    comp = next(c for c in parse(path).project.compositions if c.name == "C")
    return next(lyr for lyr in comp.layers if lyr.name == "S").masks.properties[0]


def _tensions(path_prop) -> list[list[float]]:  # type: ignore[no-untyped-def]
    shaps = filter_by_list_type(
        chunks=path_prop._kf_value_container.chunks, list_type="shap"
    )
    return [
        [
            round(t.value, 6)
            for t in find_by_type(chunks=s.chunks, chunk_type="omtn").tensions
        ]
        for s in shaps
    ]


def _round(points: list[list[float]], digits: int = 3) -> list[list[float]]:
    return [[round(x, digits) for x in p] for p in points]


class TestRotoBezierTensions:
    def test_enabling_keeps_a_polygon_a_polygon(self, tmp_path: Path) -> None:
        # AE 2026: setValue(triangle) then rotoBezier = true -> every tangent
        # [0, 0], omtn [1, 1, 1].
        app, _, _, mask = _solid_mask()
        mask.property("ADBE Mask Shape").value = Shape(TRIANGLE)
        mask.roto_bezier = True
        reread = _reparse_mask(app, tmp_path)
        path = reread.property("ADBE Mask Shape")
        assert reread.roto_bezier
        assert _tensions(path) == [[1.0, 1.0, 1.0]]
        assert _round(path.value.in_tangents) == ZERO3
        assert _round(path.value.out_tangents) == ZERO3

    def test_enabling_curves_only_vertices_with_handles(self, tmp_path: Path) -> None:
        # AE 2026: handles on vertex 1 only -> tensions [1, 1/3, 1, 1], and
        # the stored handles become the drawn tangents.
        app, _, _, mask = _solid_mask()
        handles_in = [[0.0, 0.0], [-20.0, 5.0], [0.0, 0.0], [0.0, 0.0]]
        handles_out = [[0.0, 0.0], [20.0, -5.0], [0.0, 0.0], [0.0, 0.0]]
        mask.property("ADBE Mask Shape").value = Shape(QUAD, handles_in, handles_out)
        mask.roto_bezier = True
        path = _reparse_mask(app, tmp_path).property("ADBE Mask Shape")
        assert _tensions(path) == [[1.0, 0.333333, 1.0, 1.0]]
        drawn_in = [[0.0, 0.0], [-34.968, -31.083], [0.0, 0.0], [0.0, 0.0]]
        drawn_out = [[0.0, 0.0], [21.432, 19.05], [0.0, 0.0], [0.0, 0.0]]
        assert _round(path.value.in_tangents) == drawn_in
        assert _round(path.value.out_tangents) == drawn_out
        assert _round(path.value._stored_tangents(-1)) == drawn_in

    def test_value_set_on_a_roto_mask_has_tension_one(self, tmp_path: Path) -> None:
        # AE 2026: rotoBezier = true then setValue(quad with handles) -> all
        # tangents [0, 0] (tension 1 everywhere), the handles stay stored.
        app, _, _, mask = _solid_mask()
        mask.roto_bezier = True
        handles = [[-5.0, 0.0], [-20.0, 5.0], [5.0, 5.0], [0.0, -5.0]]
        mask.property("ADBE Mask Shape").value = Shape(QUAD, handles, handles)
        path = _reparse_mask(app, tmp_path).property("ADBE Mask Shape")
        assert _tensions(path) == [[1.0, 1.0, 1.0, 1.0]]
        assert _round(path.value.in_tangents) == [[0.0, 0.0]] * 4

    def test_keys_set_on_a_roto_mask_have_tension_one(self, tmp_path: Path) -> None:
        app, _, _, mask = _solid_mask()
        mask.roto_bezier = True
        path = mask.property("ADBE Mask Shape")
        path.set_value_at_time(0.0, Shape(QUAD))
        handles = [[-5.0, 0.0], [0.0, 5.0], [5.0, 0.0], [0.0, 0.0]]
        path.set_value_at_time(2.0, Shape(QUAD, handles, handles))
        reread = _reparse_mask(app, tmp_path).property("ADBE Mask Shape")
        assert _tensions(reread) == [[1.0] * 4, [1.0] * 4]

    def test_enabling_on_a_keyed_path_treats_each_key(self, tmp_path: Path) -> None:
        # AE 2026: key 1 without handles -> tension 1; key 2 with handles on
        # every vertex -> 1/3.
        app, _, _, mask = _solid_mask()
        path = mask.property("ADBE Mask Shape")
        path.set_value_at_time(0.0, Shape(TRIANGLE))
        ins = [[-5.0, 0.0], [0.0, 5.0], [5.0, 0.0]]
        outs = [[5.0, 0.0], [0.0, -5.0], [-5.0, 0.0]]
        path.set_value_at_time(2.0, Shape([[20, 10], [180, 30], [90, 95]], ins, outs))
        mask.roto_bezier = True
        reread = _reparse_mask(app, tmp_path).property("ADBE Mask Shape")
        assert _tensions(reread) == [[1.0] * 3, [0.333333] * 3]
        k2 = reread.keyframes[1].value
        assert _round(k2.in_tangents) == [
            [-29.756, 21.49],
            [-34.168, -41.49],
            [36.72, 4.59],
        ]

    def test_disabling_keeps_the_drawn_tangents(self, tmp_path: Path) -> None:
        # AE 2026: rotoBezier on then off -> omtn emptied, the handles are the
        # tangents RotoBezier drew.
        app, _, _, mask = _solid_mask()
        ins = [[-5.0, 0.0], [0.0, 5.0], [5.0, 0.0]]
        outs = [[5.0, 0.0], [0.0, -5.0], [-5.0, 0.0]]
        mask.property("ADBE Mask Shape").value = Shape(TRIANGLE, ins, outs)
        mask.roto_bezier = True
        mask.roto_bezier = False
        reread = _reparse_mask(app, tmp_path)
        path = reread.property("ADBE Mask Shape")
        assert not reread.roto_bezier
        assert _tensions(path) == [[]]
        assert _round(path.value.in_tangents) == [
            [-23.33, 32.662],
            [-34.968, -31.083],
            [28.602, 2.043],
        ]


class TestMaskNaming:
    @pytest.mark.parametrize(
        ("existing", "expected"),
        [
            # AE 2026 addProperty("ADBE Mask Atom") beside masks so named.
            (["Mask 01"], "Mask 02"),
            (["Mask 001"], "Mask 002"),
            (["Mask 0099"], "Mask 0100"),
            (["Mask 09"], "Mask 10"),
            (["Mask 999"], "Mask 1000"),
            (["Mask 03", "Mask 3"], "Mask 04"),
            (["Mask 3", "Mask 03"], "Mask 4"),
            (["Mask 9", "Mask 08"], "Mask 10"),
            (["Mask"], "Mask 2"),
            (["Mask", "Mask 2"], "Mask 3"),
            (["Mask 0"], "Mask 1"),
            (["Mask 00"], "Mask 1"),
            (["Mask 999999"], "Mask 1000000"),
            (["Mask 000001"], "Mask 000002"),
            (["Mask 1234567"], "Mask 1"),
            (["Mask 0000099"], "Mask 1"),
            (["Mask 12345678"], "Mask 1"),
            (["Mask 2147483647"], "Mask 1"),
            (["Mask ٣"], "Mask 1"),
            (["Mask 5 "], "Mask 1"),
            (["stored"], "Mask 1"),
            (["Mask 10", "Mask 9"], "Mask 11"),
        ],
    )
    def test_new_mask_name(self, existing: list[str], expected: str) -> None:
        _, _, solid, mask = _solid_mask()
        mask.name = existing[0]
        for name in existing[1:]:
            solid.masks.add_property("ADBE Mask Atom").name = name
        assert solid.masks.add_property("ADBE Mask Atom").name == expected


class TestPathValueValidation:
    @pytest.mark.parametrize("value", [[[1, 2], [3, 4]], None, 5, (1, 2)])
    def test_non_shape_rejected_without_mutation(self, value: object) -> None:
        # AE 2026 refuses `setValue([[0,0],[1,1]])` on a mask path ("Array is
        # not of the correct type").
        app, _, _, mask = _solid_mask()
        path = mask.property("ADBE Mask Shape")
        before = project_bytes(app.project)
        with pytest.raises(TypeError):
            path.value = value  # type: ignore[assignment]
        assert project_bytes(app.project) == before
        path.value = Shape(TRIANGLE)
        before = project_bytes(app.project)
        with pytest.raises(TypeError):
            path.value = value  # type: ignore[assignment]
        assert project_bytes(app.project) == before
        assert isinstance(path.value, Shape)

    def test_shape_layer_path_rejects_non_shape(self) -> None:
        app = py_aep.new()
        comp = app.project.root_folder.add_comp("C", 400, 300, 1.0, 5.0, 24.0)
        group = comp.add_shape()["ADBE Root Vectors Group"]
        path = group.add_property("ADBE Vector Shape - Group").property(
            "ADBE Vector Shape"
        )
        with pytest.raises(TypeError):
            path.value = [[1, 2], [3, 4]]  # type: ignore[assignment]

    @pytest.mark.parametrize(
        "call",
        [
            lambda p: p.add_key(1e9),
            lambda p: p.add_key("1"),
            lambda p: p.set_value_at_time(1e9, Shape(TRIANGLE)),
            lambda p: p.set_value_at_time(1.0, [[0, 0], [1, 1]]),
        ],
    )
    def test_rejected_key_leaves_a_fresh_mask_untouched(self, call) -> None:  # type: ignore[no-untyped-def]
        app, _, _, mask = _solid_mask()
        before = project_bytes(app.project)
        with pytest.raises((TypeError, ValueError)):
            call(mask.property("ADBE Mask Shape"))
        assert project_bytes(app.project) == before


class TestFreshMaskNoOps:
    def test_default_value_writes_no_path(self) -> None:
        # AE 2026: maskPath.setValue(maskPath.value) on a fresh mask saves the
        # bare atom; so does setValue of an equal, newly built rectangle.
        app, _, _, mask = _solid_mask()
        path = mask.property("ADBE Mask Shape")
        before = project_bytes(app.project)
        path.value = path.value
        path.value = Shape([[0, 0], [0, 100], [200, 100], [200, 0]])
        path.expression_enabled = False
        assert project_bytes(app.project) == before

    def test_a_different_value_writes_the_path(self) -> None:
        app, _, _, mask = _solid_mask()
        before = project_bytes(app.project)
        mask.property("ADBE Mask Shape").value = Shape(
            [[0, 0], [0, 100], [200, 100], [201, 0]]
        )
        assert project_bytes(app.project) != before


class TestShapeGeometry:
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"vertices": [[1e39, 0.0], [1.0, 1.0]]},
            {
                "vertices": [[3e38, 0.0], [1.0, 1.0]],
                "in_tangents": [[3e38, 0.0], [0, 0]],
            },
            {"vertices": [[0.0, 0.0]], "out_tangents": [[float("inf"), 0.0]]},
        ],
    )
    def test_beyond_float32_is_rejected(self, kwargs: dict) -> None:  # type: ignore[type-arg]
        with pytest.raises(ValueError):
            Shape(**kwargs)

    def test_closed_must_be_a_bool(self) -> None:
        with pytest.raises(TypeError):
            Shape([[0, 0]], closed=1)  # type: ignore[arg-type]

    def test_vertex_move_keeps_relative_tangents(self) -> None:
        shape = Shape([[0, 0], [10, 0], [5, 5]], [[1, 1], [0, 0], [0, 0]])
        shape.vertices = [[100, 100], [110, 100], [105, 105]]
        assert shape.vertices == [[100, 100], [110, 100], [105, 105]]
        assert _round(shape.in_tangents) == [[1, 1], [0, 0], [0, 0]]

    def test_flat_path_takes_new_coordinates(self) -> None:
        shape = Shape([[0, 5], [10, 5], [20, 5]])
        shape.vertices = [[0, 0], [10, 10], [20, 0]]
        shape.in_tangents = [[1, 1], [1, 1], [1, 1]]
        assert shape.vertices == [[0, 0], [10, 10], [20, 0]]
        assert _round(shape.in_tangents) == [[1, 1]] * 3

    def test_new_shape_then_vertices(self) -> None:
        # The ExtendScript idiom: `new Shape()`, then assign the vertices.
        shape = Shape()
        shape.vertices = [[0, 0], [10, 0], [5, 5]]
        shape.out_tangents = [[1, 0], [0, 1], [0, 0]]
        assert shape.vertices == [[0, 0], [10, 0], [5, 5]]
        assert _round(shape.out_tangents) == [[1, 0], [0, 1], [0, 0]]

    def test_empty_vertices_rejected(self) -> None:
        # AE 2026: "Value array does not have at least 1 element(s)".
        with pytest.raises(ValueError):
            Shape([[0, 0]]).vertices = []

    def test_tangent_count_must_match(self) -> None:
        shape = Shape([[0, 0], [10, 0], [5, 5]])
        with pytest.raises(ValueError):
            shape.in_tangents = [[1, 1]]
        assert _round(shape.in_tangents) == ZERO3

    def test_parsed_path_keeps_its_vertex_count(self) -> None:
        app, _, _, mask = _solid_mask()
        path = mask.property("ADBE Mask Shape")
        path.value = Shape(TRIANGLE)
        before = project_bytes(app.project)
        with pytest.raises(ValueError):
            path.value.vertices = QUAD
        assert project_bytes(app.project) == before


class TestShapeCopies:
    def _two_layers(self):  # type: ignore[no-untyped-def]
        app = py_aep.new()
        comp = app.project.root_folder.add_comp("C", 800, 600, 1.0, 5.0, 24.0)
        a = comp.add_solid([1.0, 0.0, 0.0], "A", 200, 100, 1.0)
        b = comp.add_solid([0.0, 1.0, 0.0], "B", 400, 400, 1.0)
        mask_a = a.masks.add_property("ADBE Mask Atom")
        mask_a.property("ADBE Mask Shape").value = Shape(TRIANGLE)
        return app, comp, b, mask_a

    def test_mask_copied_to_a_bigger_layer_keeps_its_pixels(
        self, tmp_path: Path
    ) -> None:
        # AE 2026: B.maskPath.setValue(A.maskPath.value) -> the same pixel
        # vertices on the 400x400 layer as on the 200x100 one.
        app, _, b, mask_a = self._two_layers()
        mask_b = b.masks.add_property("ADBE Mask Atom")
        mask_b.property("ADBE Mask Shape").value = mask_a.property(
            "ADBE Mask Shape"
        ).value
        assert _round(mask_b.property("ADBE Mask Shape").value.vertices) == TRIANGLE
        path = tmp_path / "copy.aep"
        app.project.save(path)
        comp = parse(path).project.compositions[0]
        b2 = next(lyr for lyr in comp.layers if lyr.name == "B")
        assert (
            _round(b2.masks.properties[0].property("ADBE Mask Shape").value.vertices)
            == TRIANGLE
        )

    def test_mask_copied_to_a_shape_path_keeps_its_pixels(self) -> None:
        _, comp, _, mask_a = self._two_layers()
        group = comp.add_shape()["ADBE Root Vectors Group"]
        path = group.add_property("ADBE Vector Shape - Group").property(
            "ADBE Vector Shape"
        )
        path.value = mask_a.property("ADBE Mask Shape").value
        assert _round(path.value.vertices) == TRIANGLE


class TestFeatherPoints:
    def test_new_shape_keeps_feather_points(self, tmp_path: Path) -> None:
        app = parse(FEATHER)
        path = (
            app.project.compositions[0]
            .layers[0]
            .masks.properties[0]
            .property("ADBE Mask Shape")
        )
        value = path.value
        expected = [
            (fp.seg_loc, fp.rel_seg_loc, fp.radius) for fp in value.feather_points
        ]
        assert len(expected) == 4
        path.value = Shape(
            value.vertices,
            value.in_tangents,
            value.out_tangents,
            closed=value.closed,
            feather_points=value.feather_points,
        )
        out = tmp_path / "feather.aep"
        app.project.save(out)
        reread = parse(out).project.compositions[0].layers[0].masks.properties[0]
        points = reread.property("ADBE Mask Shape").value.feather_points
        assert [(fp.seg_loc, fp.rel_seg_loc, fp.radius) for fp in points] == expected

    def test_feather_points_must_be_feather_points(self) -> None:
        with pytest.raises(TypeError):
            Shape([[0, 0]], feather_points="x")  # type: ignore[arg-type]


class TestExpressionNul:
    def test_nul_rejected(self) -> None:
        # AE 2026 keeps only the text before a NUL ("50\0 + 1" reads "50").
        app, _, solid, _ = _solid_mask()
        opacity = solid["ADBE Transform Group"]["ADBE Opacity"]
        with pytest.raises(ValueError):
            opacity.expression = "50\x00 + 1"


class TestGroupAttributeWrites:
    @pytest.mark.parametrize(
        ("group_name", "attr", "value"),
        [
            ("ADBE Transform Group", "roto_bezier", True),
            ("ADBE Transform Group", "position", [1.0, 2.0]),
            ("ADBE Effect Parade", "value", 42),
        ],
    )
    def test_unknown_attribute_rejected(
        self, group_name: str, attr: str, value: object
    ) -> None:
        app, _, solid, _ = _solid_mask()
        group = solid[group_name]
        before = project_bytes(app.project)
        with pytest.raises(AttributeError):
            setattr(group, attr, value)
        assert project_bytes(app.project) == before
        if attr == "position":
            # Attribute access still reaches the child property.
            assert group.position.match_name == "ADBE Position"


class TestNewLayerMatchNames:
    def test_text_and_shape_layers(self) -> None:
        app = py_aep.new()
        comp = app.project.root_folder.add_comp("C", 400, 300, 1.0, 5.0, 24.0)
        assert comp.add_text("x").match_name == "ADBE Text Layer"
        assert comp.add_shape().match_name == "ADBE Vector Layer"
