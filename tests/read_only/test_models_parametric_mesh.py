"""Read-only tests for parametric mesh layers.

Validates parsing of `parametric_meshes.aep` (all six mesh types) against
the ExtendScript ground-truth JSON, and spot-checks the typed
`ParametricMeshLayer` / options API.
"""

from __future__ import annotations

from pathlib import Path

from conftest import parse_project

from py_aep.cli.validate import validate_aep
from py_aep.enums import ParametricMeshType
from py_aep.models.layers.parametric_mesh_layer import (
    CubeMeshOptions,
    CylinderMeshOptions,
    ParametricMeshLayer,
)

SAMPLE_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"
MESH_AEP = SAMPLE_DIR / "parametric_meshes.aep"
MESH_JSON = SAMPLE_DIR / "parametric_meshes.json"


class TestParametricMeshValidation:
    def test_validates_against_extendscript(self) -> None:
        """Parsed output matches the ExtendScript export exactly."""
        result = validate_aep(MESH_AEP, MESH_JSON)
        assert len(result) == 0, "\n".join(result.differences[:40])


class TestParametricMeshModel:
    def test_layer_types_and_options(self) -> None:
        project = parse_project(MESH_AEP)
        comp = project.compositions[0]
        by_name = {layer.name: layer for layer in comp.layers}

        cube = by_name["Cube Mesh Layer 1"]
        assert isinstance(cube, ParametricMeshLayer)
        assert cube.parametric_mesh_type is ParametricMeshType.CUBE
        assert isinstance(cube.parametric_mesh_options, CubeMeshOptions)

        cyl = by_name["Cylinder Mesh Layer 1"]
        assert cyl.parametric_mesh_type is ParametricMeshType.CYLINDER
        assert isinstance(cyl.parametric_mesh_options, CylinderMeshOptions)

    def test_layer_type_string_is_parametric_mesh(self) -> None:
        project = parse_project(MESH_AEP)
        cube = project.compositions[0].layers[-1]
        # AE reports these as their own type, not AVLayer.
        assert cube.layer_type == "ParametricMeshLayer"

    def test_cannot_set_collapse_transformation(self) -> None:
        project = parse_project(MESH_AEP)
        cube = project.compositions[0].layers[-1]
        assert cube.can_set_collapse_transformation is False

    def test_mesh_type_enum_binary_roundtrip(self) -> None:
        for mt in ParametricMeshType:
            assert ParametricMeshType.from_binary(mt.to_binary()) is mt
