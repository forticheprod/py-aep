"""Tests for item creation and removal mutations."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep import parse as parse_aep

SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "models"


class TestAddFolder:
    """Tests for FolderItem.add_folder()."""

    def test_add_folder_returns_folder(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        folder = root.add_folder("NewFolder")
        assert folder.name == "NewFolder"

    def test_add_folder_adds_to_items(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        n = len(root.items)
        root.add_folder("NewFolder")
        assert len(root.items) == n + 1

    def test_add_folder_registers_in_project(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        folder = root.add_folder("NewFolder")
        assert app.project.items[folder.id] is folder

    def test_add_folder_unique_id(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        existing_ids = set(app.project.items.keys())
        folder = root.add_folder("NewFolder")
        assert folder.id not in existing_ids

    def test_add_folder_parent_folder(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        folder = root.add_folder("NewFolder")
        assert folder.parent_folder is root

    def test_add_folder_nested(self) -> None:
        """Add a folder inside a non-root folder."""
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        parent = root.add_folder("Parent")
        child = parent.add_folder("Child")
        assert child.parent_folder is parent
        assert child in parent.items
        assert child.name == "Child"

    def test_add_folder_empty(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        folder = root.add_folder("EmptyNew")
        assert folder.num_items == 0

    def test_add_folder_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        folder = root.add_folder("RoundTripFolder")
        folder_id = folder.id

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")

        assert folder_id in app2.project.items
        found = app2.project.items[folder_id]
        assert found.name == "RoundTripFolder"
        assert found.type_name == "Folder"

    def test_add_folder_nested_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        parent = root.add_folder("Parent")
        child = parent.add_folder("Child")
        parent_id = parent.id
        child_id = child.id

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")

        parent2 = app2.project.items[parent_id]
        child2 = app2.project.items[child_id]
        assert parent2.name == "Parent"
        assert child2.name == "Child"
        assert child2.parent_folder is parent2

    def test_add_multiple_folders(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        n = len(root.items)
        f1 = root.add_folder("A")
        f2 = root.add_folder("B")
        f3 = root.add_folder("C")
        assert len(root.items) == n + 3
        assert f1.id != f2.id != f3.id


# -----------------------------------------------------------------------
# FolderItem.add_comp()
# -----------------------------------------------------------------------


class TestAddComp:
    """Tests for FolderItem.add_comp()."""

    def test_add_comp_returns_compitem(self) -> None:
        from py_aep.models.items.composition import CompItem

        app = parse_aep(SAMPLES_DIR / "composition" / "bgColor_custom.aep")
        root = app.project.root_folder
        comp = root.add_comp("NewComp", 1920, 1080, 1.0, 10.0, 24.0)
        assert isinstance(comp, CompItem)

    def test_add_comp_name(self) -> None:
        app = parse_aep(SAMPLES_DIR / "composition" / "bgColor_custom.aep")
        root = app.project.root_folder
        comp = root.add_comp("TestComp", 1920, 1080, 1.0, 5.0, 30.0)
        assert comp.name == "TestComp"

    def test_add_comp_dimensions(self) -> None:
        app = parse_aep(SAMPLES_DIR / "composition" / "bgColor_custom.aep")
        root = app.project.root_folder
        comp = root.add_comp("DimComp", 3840, 2160, 1.0, 10.0, 24.0)
        assert comp.width == 3840
        assert comp.height == 2160

    def test_add_comp_frame_rate(self) -> None:
        app = parse_aep(SAMPLES_DIR / "composition" / "bgColor_custom.aep")
        root = app.project.root_folder
        comp = root.add_comp("FpsComp", 1920, 1080, 1.0, 10.0, 29.97)
        assert abs(comp.frame_rate - 29.97) < 0.01

    def test_add_comp_duration(self) -> None:
        app = parse_aep(SAMPLES_DIR / "composition" / "bgColor_custom.aep")
        root = app.project.root_folder
        comp = root.add_comp("DurComp", 1920, 1080, 1.0, 15.5, 24.0)
        assert abs(comp.duration - 15.5) < 0.01

    def test_add_comp_pixel_aspect(self) -> None:
        app = parse_aep(SAMPLES_DIR / "composition" / "bgColor_custom.aep")
        root = app.project.root_folder
        comp = root.add_comp("PAComp", 720, 480, 0.9091, 10.0, 29.97)
        assert abs(comp.pixel_aspect - 0.9091) < 0.001

    def test_add_comp_no_layers(self) -> None:
        app = parse_aep(SAMPLES_DIR / "composition" / "bgColor_custom.aep")
        root = app.project.root_folder
        comp = root.add_comp("EmptyComp", 1920, 1080, 1.0, 10.0, 24.0)
        assert len(comp.layers) == 0

    def test_add_comp_unique_id(self) -> None:
        app = parse_aep(SAMPLES_DIR / "composition" / "bgColor_custom.aep")
        root = app.project.root_folder
        existing_ids = set(app.project.items.keys())
        comp = root.add_comp("IDComp", 1920, 1080, 1.0, 10.0, 24.0)
        assert comp.id not in existing_ids

    def test_add_comp_parent_folder(self) -> None:
        app = parse_aep(SAMPLES_DIR / "composition" / "bgColor_custom.aep")
        root = app.project.root_folder
        comp = root.add_comp("ParentComp", 1920, 1080, 1.0, 10.0, 24.0)
        assert comp.parent_folder is root

    def test_add_comp_registered_in_project(self) -> None:
        app = parse_aep(SAMPLES_DIR / "composition" / "bgColor_custom.aep")
        root = app.project.root_folder
        comp = root.add_comp("RegComp", 1920, 1080, 1.0, 10.0, 24.0)
        assert app.project.items[comp.id] is comp
        assert comp in app.project.compositions

    def test_add_comp_in_subfolder(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        folder = root.add_folder("SubFolder")
        comp = folder.add_comp("SubComp", 1280, 720, 1.0, 5.0, 25.0)
        assert comp.parent_folder is folder
        assert comp in folder.items

    def test_add_comp_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "composition" / "bgColor_custom.aep")
        root = app.project.root_folder
        comp = root.add_comp("RTComp", 1920, 1080, 1.0, 10.0, 24.0)
        comp_id = comp.id

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")

        assert comp_id in app2.project.items
        comp2 = app2.project.items[comp_id]
        assert comp2.name == "RTComp"
        assert comp2.type_name == "Composition"

    def test_add_comp_roundtrip_preserves_settings(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "composition" / "bgColor_custom.aep")
        root = app.project.root_folder
        comp = root.add_comp("Settings", 3840, 2160, 1.0, 30.0, 60.0)
        comp_id = comp.id

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")

        from py_aep.models.items.composition import CompItem

        comp2 = app2.project.items[comp_id]
        assert isinstance(comp2, CompItem)
        assert comp2.width == 3840
        assert comp2.height == 2160
        assert abs(comp2.frame_rate - 60.0) < 0.01
        assert abs(comp2.duration - 30.0) < 0.01

    def test_add_comp_from_scratch_roundtrip(self, tmp_path: Path) -> None:
        """Test add_comp when no existing comp to clone from (folder-only project)."""
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        # Remove all comps from project to force from-scratch path
        for comp in list(app.project.compositions):
            comp.remove()
        # Now there are no compositions to clone from
        assert len(app.project.compositions) == 0

        comp = root.add_comp("Scratch", 1280, 720, 1.0, 5.0, 25.0)
        comp_id = comp.id

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")

        from py_aep.models.items.composition import CompItem

        comp2 = app2.project.items[comp_id]
        assert isinstance(comp2, CompItem)
        assert comp2.name == "Scratch"
        assert comp2.width == 1280
        assert comp2.height == 720


# -----------------------------------------------------------------------
# Item.remove()
# -----------------------------------------------------------------------


class TestItemRemove:
    """Tests for Item.remove()."""

    def test_remove_folder_from_root(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        n = len(root.items)
        # Find the first folder
        from py_aep.models.items.folder import FolderItem

        folder = next(i for i in root.items if isinstance(i, FolderItem))
        folder_id = folder.id
        folder.remove()
        assert len(root.items) == n - 1
        assert folder_id not in app.project.items

    def test_remove_root_folder_raises(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        with pytest.raises(ValueError, match="Cannot remove the root folder"):
            app.project.root_folder.remove()

    def test_remove_comp_from_project(self) -> None:
        app = parse_aep(SAMPLES_DIR / "composition" / "bgColor_custom.aep")
        root = app.project.root_folder
        comp = app.project.compositions[0]
        comp_id = comp.id
        n_items = len(root.items)
        comp.remove()
        assert len(root.items) == n_items - 1
        assert comp_id not in app.project.items

    def test_remove_added_folder(self) -> None:
        """Remove a folder that was just added."""
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        n = len(root.items)
        folder = root.add_folder("Temp")
        assert len(root.items) == n + 1
        folder.remove()
        assert len(root.items) == n

    def test_remove_folder_recursive(self) -> None:
        """Removing a folder should recursively remove its children."""
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        # Create nested structure
        parent = root.add_folder("Parent")
        child = parent.add_folder("Child")
        parent_id = parent.id
        child_id = child.id

        parent.remove()
        assert parent_id not in app.project.items
        assert child_id not in app.project.items

    def test_remove_comp_cleans_layers(self) -> None:
        """Removing a comp that is used as a layer source should clean up layers."""
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        # Find a comp that is nested in another comp
        # First check if any comp is used as a layer source
        from py_aep.models.items.composition import CompItem
        from py_aep.models.layers.av_layer import AVLayer

        for comp in app.project.compositions:
            for layer in comp.layers:
                if isinstance(layer, AVLayer) and layer._source_id:
                    source_item = app.project.items.get(layer._source_id)
                    if isinstance(source_item, CompItem):
                        # Found a comp used as a layer source
                        source_id = source_item.id
                        parent_comp = comp
                        source_item.remove()
                        # Layer referencing the removed comp should be gone
                        for remaining_layer in parent_comp.layers:
                            if isinstance(remaining_layer, AVLayer):
                                assert remaining_layer._source_id != source_id
                        return
        pytest.skip("No nested comp found in sample")

    def test_remove_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        # Add and remove a folder
        folder = root.add_folder("ToDelete")
        folder_id = folder.id
        folder.remove()

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        assert folder_id not in app2.project.items

    def test_remove_comp_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "composition" / "bgColor_custom.aep")
        comp = app.project.compositions[0]
        comp_id = comp.id
        comp.remove()

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        assert comp_id not in app2.project.items
        assert len(app2.project.compositions) == 0

    def test_add_and_remove_comp_roundtrip(self, tmp_path: Path) -> None:
        """Add a comp, save, verify it's there, remove it, save again, verify gone."""
        app = parse_aep(SAMPLES_DIR / "composition" / "bgColor_custom.aep")
        root = app.project.root_folder
        comp = root.add_comp("Ephemeral", 1920, 1080, 1.0, 5.0, 24.0)
        comp_id = comp.id

        # Save with the new comp
        app.project.save(tmp_path / "with_comp.aep")
        app2 = parse_aep(tmp_path / "with_comp.aep")
        assert comp_id in app2.project.items

        # Remove and save again
        app2.project.items[comp_id].remove()
        app2.project.save(tmp_path / "without_comp.aep")
        app3 = parse_aep(tmp_path / "without_comp.aep")
        assert comp_id not in app3.project.items
