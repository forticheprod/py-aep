"""Path coordinates, digit for digit against ExtendScript.

After Effects places the stored points in float32 and reports each
coordinate as 16.16 fixed point, so `Shape.vertices` and the tangents come
back on a 1 / 65536 pixel grid. The sample JSON holds 15 significant digits,
enough to tell one grid step from the next.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import get_comp, parse_project

from py_aep.models.properties.property import Property
from py_aep.models.properties.shape import Shape

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples"


def _digits(points: list[list[float]]) -> tuple[float, ...]:
    return tuple(float(f"{c:.15g}") for point in points for c in point)


def _exported_shapes(node: object, found: set) -> None:
    if isinstance(node, dict):
        if "vertices" in node and "inTangents" in node:
            found.add(
                (
                    _digits(node["vertices"]),
                    _digits(node["inTangents"]),
                    _digits(node["outTangents"]),
                )
            )
        for value in node.values():
            _exported_shapes(value, found)
    elif isinstance(node, list):
        for value in node:
            _exported_shapes(value, found)


def _stored_shapes(project) -> list[Shape]:
    shapes = []
    for comp in project.compositions:
        stack = list(comp.layers)
        while stack:
            node = stack.pop()
            if not isinstance(node, Property):
                stack.extend(node.properties)
                continue
            values = [node.value]
            for keyframe in node.keyframes:
                values.append(keyframe.value)
            for value in values:
                if isinstance(value, Shape) and not value._is_roto_bezier():
                    shapes.append(value)
    return shapes


class TestPathCoordinates:
    @pytest.mark.parametrize(
        "sample",
        [
            "models/property/shape_basic",
            "models/property/shape_feather",
            "models/property/mask",
            "versions/ae2018/complete",
            "versions/ae2026/complete",
        ],
    )
    def test_every_path_is_in_the_export(self, sample: str) -> None:
        with (SAMPLES_DIR / f"{sample}.json").open(encoding="utf-8") as f:
            exported: set = set()
            _exported_shapes(json.load(f), exported)
        shapes = _stored_shapes(parse_project(SAMPLES_DIR / f"{sample}.aep"))
        assert shapes
        for shape in shapes:
            key = (
                _digits(shape.vertices),
                _digits(shape.in_tangents),
                _digits(shape.out_tangents),
            )
            assert key in exported

    def test_oval_handles(self) -> None:
        # AE 2026 after reopening the file. 200 + 55.23 and 200 - 55.23 land
        # on an odd count of 1 / 65536, which AE's float32 rounding moves up
        # to the even one.
        project = parse_project(SAMPLES_DIR / "models/property/shape_basic.aep")
        layer = get_comp(project, "shape_closed_oval").layers[0]
        shape = layer.masks.properties[0].property("ADBE Mask Shape").value
        assert shape.vertices == [
            [200.0, 50.0],
            [100.0, 200.0],
            [200.0, 350.0],
            [300.0, 200.0],
        ]
        assert shape.in_tangents == [
            [55.230010986328125, 0.0],
            [0.0, -55.22998046875],
            [-55.22998046875, 0.0],
            [0.0, 55.230010986328125],
        ]
        assert shape.out_tangents == [
            [-55.22998046875, 0.0],
            [0.0, 55.230010986328125],
            [55.230010986328125, 0.0],
            [0.0, -55.22998046875],
        ]
