"""Tests for layer selection parsing from otln chunks."""

from __future__ import annotations

from pathlib import Path

from conftest import parse_project

SELECTION_DIR = Path(__file__).parent.parent / "samples" / "models" / "selection"
COMP_SELECTION_DIR = Path(__file__).parent.parent / "samples" / "models" / "composition"


class TestLayerSelectedRead:
    """Read layer.selected from otln entries."""

    def test_no_selection(self) -> None:
        project = parse_project(SELECTION_DIR / "no_selection_everything_collapsed.aep")
        comp = project.compositions[0]
        assert comp.layers[0].selected is False

    def test_no_selection_two_layers(self) -> None:
        project = parse_project(SELECTION_DIR / "no_selection_two_layers.aep")
        comp = project.compositions[0]
        assert comp.layers[0].selected is False
        assert comp.layers[1].selected is False

    def test_layer_selected(self) -> None:
        project = parse_project(SELECTION_DIR / "selection_layer.aep")
        comp = project.compositions[0]
        assert comp.layers[0].selected is True

    def test_property_selected_implies_layer_selected(self) -> None:
        """When a property is selected, its layer is also selected."""
        for name in [
            "selection_anchor",
            "selection_position",
            "selection_scale",
            "selection_rotation",
            "selection_opacity",
            "selection_transform",
        ]:
            project = parse_project(SELECTION_DIR / f"{name}.aep")
            comp = project.compositions[0]
            assert comp.layers[0].selected is True, f"Failed for {name}"

    def test_effect_property_selected_implies_layer_selected(self) -> None:
        """Layer is selected when an effect property is selected."""
        for name in [
            "selection_dropshadow_enabled_opacity",
            "selection_fill_opacity",
        ]:
            project = parse_project(SELECTION_DIR / f"{name}.aep")
            comp = project.compositions[0]
            assert comp.layers[0].selected is True, f"Failed for {name}"

    def test_text_property_selected_implies_layer_selected(self) -> None:
        project = parse_project(SELECTION_DIR / "selection_text_source_text.aep")
        comp = project.compositions[0]
        assert comp.layers[0].selected is True

    def test_3d_property_selected_implies_layer_selected(self) -> None:
        project = parse_project(SELECTION_DIR / "selection_3d_scale.aep")
        comp = project.compositions[0]
        assert comp.layers[0].selected is True

    def test_two_layer_first_selected(self) -> None:
        project = parse_project(COMP_SELECTION_DIR / "selection_first_layer.aep")
        comp = project.compositions[0]
        assert comp.layers[0].selected is True
        assert comp.layers[1].selected is False

    def test_two_layer_both_selected(self) -> None:
        project = parse_project(COMP_SELECTION_DIR / "selection_both_layers.aep")
        comp = project.compositions[0]
        assert comp.layers[0].selected is True
        assert comp.layers[1].selected is True

    def test_two_layer_none_selected(self) -> None:
        project = parse_project(COMP_SELECTION_DIR / "selection_empty.aep")
        comp = project.compositions[0]
        assert comp.layers[0].selected is False
        assert comp.layers[1].selected is False

    def test_second_layer_selected(self) -> None:
        project = parse_project(
            COMP_SELECTION_DIR / "selection_second_layer_anchor_and_position.aep"
        )
        comp = project.compositions[0]
        assert comp.layers[0].selected is False
        assert comp.layers[1].selected is True


class TestSelectedLayers:
    """CompItem.selected_layers property."""

    def test_selected_layers_none(self) -> None:
        project = parse_project(SELECTION_DIR / "no_selection_two_layers.aep")
        comp = project.compositions[0]
        assert comp.selected_layers == []

    def test_selected_layers_one(self) -> None:
        project = parse_project(SELECTION_DIR / "selection_layer.aep")
        comp = project.compositions[0]
        assert len(comp.selected_layers) == 1
        assert comp.selected_layers[0] is comp.layers[0]

    def test_selected_layers_both(self) -> None:
        project = parse_project(COMP_SELECTION_DIR / "selection_both_layers.aep")
        comp = project.compositions[0]
        assert len(comp.selected_layers) == 2

    def test_selected_layers_first_only(self) -> None:
        project = parse_project(COMP_SELECTION_DIR / "selection_first_layer.aep")
        comp = project.compositions[0]
        assert len(comp.selected_layers) == 1
        assert comp.selected_layers[0] is comp.layers[0]


class TestLayerSelectedWrite:
    """Write layer.selected via otln entry."""

    def test_round_trip(self, tmp_path: Path) -> None:
        """Toggle selection, save, re-parse, verify."""
        from py_aep import parse as parse_aep

        app = parse_aep(SELECTION_DIR / "selection_layer.aep")
        app.project.compositions[0].layers[0].selected = False

        out = tmp_path / "deselected.aep"
        app.project.save(out)

        app2 = parse_aep(out)
        assert app2.project.compositions[0].layers[0].selected is False
