"""Roundtrip tests for CompItem.add_parametric_mesh."""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import parse_project_fresh

from py_aep import parse as parse_aep
from py_aep.enums import LayerType, ParametricMeshType
from py_aep.models.layers.parametric_mesh_layer import ParametricMeshLayer

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models"
# comp_misc.aep has an empty Advanced-3D comp named "comment" (100x100, 1s).
BASE_AEP = SAMPLES_DIR / "composition" / "comp_misc.aep"

# First numeric ParaMeshField per mesh type, for the value-persistence check.
_FIRST_FIELD: dict[ParametricMeshType, str] = {
    ParametricMeshType.CUBE: "width",
    ParametricMeshType.SPHERE: "radius",
    ParametricMeshType.PLANE: "width",
    ParametricMeshType.TORUS: "ring_radius",
    ParametricMeshType.CONE: "top_radius",
    ParametricMeshType.CYLINDER: "radius",
}


def _save_reparse(project, tmp_path: Path):
    out = tmp_path / "mesh.aep"
    project.save(out)
    return parse_project_fresh(out)


class TestAddParametricMesh:
    @pytest.mark.parametrize("mesh_type", list(ParametricMeshType))
    def test_creates_correct_type(self, mesh_type: ParametricMeshType) -> None:
        project = parse_aep(BASE_AEP).project
        comp = project.compositions[0]
        layer = comp.add_parametric_mesh(mesh_type=mesh_type)
        assert isinstance(layer, ParametricMeshLayer)
        assert layer.parametric_mesh_type is mesh_type
        assert layer._ldta.layer_type == LayerType.PARAMETRIC_MESH
        assert layer.three_d_layer is True

    @pytest.mark.parametrize("mesh_type", list(ParametricMeshType))
    def test_type_and_value_persist_through_save(
        self, mesh_type: ParametricMeshType, tmp_path: Path
    ) -> None:
        project = parse_aep(BASE_AEP).project
        comp = project.compositions[0]
        layer = comp.add_parametric_mesh(
            name=f"M {mesh_type.name}", mesh_type=mesh_type
        )
        field = _FIRST_FIELD[mesh_type]
        setattr(layer.parametric_mesh_options, field, 321.0)

        fresh = _save_reparse(project, tmp_path)
        fresh_layer = next(
            lyr
            for lyr in fresh.compositions[0].layers
            if lyr.name == f"M {mesh_type.name}"
        )
        assert fresh_layer.parametric_mesh_type is mesh_type
        assert getattr(fresh_layer.parametric_mesh_options, field) == pytest.approx(
            321.0
        )

    def test_auto_name_clears_name_set(self) -> None:
        project = parse_aep(BASE_AEP).project
        comp = project.compositions[0]
        layer = comp.add_parametric_mesh(mesh_type=ParametricMeshType.CUBE)
        # AE leaves the ldta name bit clear for an auto-generated name.
        assert layer._ldta.name_set is False

    def test_rename_sets_name_bit(self, tmp_path: Path) -> None:
        # AE 2026 (headless rename experiment on parametric_meshes.aep):
        # renaming a mesh layer sets the ldta name bit, and it stays set
        # even when renamed back to the original default name - unlike
        # other sourceless layers, where renames leave the bit clear.
        sample = SAMPLES_DIR / "layer" / "parametric_meshes.aep"
        project = parse_aep(sample).project
        comp = project.compositions[0]
        comp.layers[0].name = "Renamed Mesh"
        default = comp.layers[1].name
        comp.layers[1].name = "Temp Name"
        comp.layers[1].name = default

        fresh = _save_reparse(project, tmp_path)
        fresh_layers = fresh.compositions[0].layers
        assert fresh_layers[0]._ldta.name_set is True
        assert fresh_layers[1]._ldta.name_set is True
        assert fresh_layers[2]._ldta.name_set is False

    def test_explicit_name_sets_name_bit(self) -> None:
        project = parse_aep(BASE_AEP).project
        comp = project.compositions[0]
        layer = comp.add_parametric_mesh(
            name="My Cube", mesh_type=ParametricMeshType.CUBE
        )
        assert layer.name == "My Cube"
        assert layer._ldta.name_set is True

    def test_ldta_uses_comp_timebase(self) -> None:
        project = parse_aep(BASE_AEP).project
        comp = project.compositions[0]
        layer = comp.add_parametric_mesh(mesh_type=ParametricMeshType.CUBE)
        time_base = comp._cdta.internal_timebase
        assert layer._ldta.out_point_divisor == time_base
        assert layer._ldta.in_point_divisor == time_base

    def test_effects_active_cleared(self) -> None:
        project = parse_aep(BASE_AEP).project
        comp = project.compositions[0]
        layer = comp.add_parametric_mesh(mesh_type=ParametricMeshType.CUBE)
        assert layer._ldta.effects_active is False
