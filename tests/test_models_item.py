"""Tests for Item model parsing."""

from __future__ import annotations

from pathlib import Path

from conftest import get_comp, parse_project

from py_aep import parse as parse_aep
from py_aep.enums import Label

SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "models" / "item"
COMP_SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "models" / "composition"


class TestItemSelected:
    """Tests for Item.selected attribute.

    Item selection is not stored in the .aep binary format; it is a
    runtime-only property. All items should report selected=False.
    """

    def test_selected_empty(self) -> None:
        project = parse_project(SAMPLES_DIR / "selection_empty.aep")
        for item in project.items.values():
            assert item.selected is False


class TestRoundtripItemLabel:
    """Roundtrip tests for Item.label."""

    def test_modify_item_label(self, tmp_path: Path) -> None:
        project = parse_aep(COMP_SAMPLES_DIR / "bgColor.aep").project
        comp = get_comp(project, "bgColor_custom")
        original_label = comp.label

        comp.label = Label.FUCHSIA
        assert comp.label != original_label
        out = tmp_path / "modified_label.aep"
        project.save(out)

        project2 = parse_aep(out).project
        comp2 = get_comp(project2, "bgColor_custom")
        assert comp2.label == Label.FUCHSIA


class TestRoundtripItemComment:
    """Roundtrip tests for Item.comment."""

    def test_modify_item_comment(self, tmp_path: Path) -> None:
        project = parse_aep(COMP_SAMPLES_DIR / "bgColor.aep").project
        comp = get_comp(project, "bgColor_custom")

        comp.comment = "roundtrip item comment"
        out = tmp_path / "modified_comment.aep"
        project.save(out)

        project2 = parse_aep(out).project
        comp2 = get_comp(project2, "bgColor_custom")
        assert comp2.comment == "roundtrip item comment"


class TestRoundtripItemName:
    """Roundtrip tests for Item.name."""

    def test_modify_item_name(self, tmp_path: Path) -> None:
        project = parse_aep(COMP_SAMPLES_DIR / "bgColor.aep").project
        comp = get_comp(project, "bgColor_custom")

        comp.name = "Renamed Composition"
        out = tmp_path / "modified_name.aep"
        project.save(out)

        project2 = parse_aep(out).project
        comp2 = get_comp(project2, "Renamed Composition")
        assert comp2.name == "Renamed Composition"
