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


# -----------------------------------------------------------------------
# Item.parent_folder (setter / move)
# -----------------------------------------------------------------------


class TestParentFolderSetter:
    """Tests for moving items between folders via parent_folder."""

    def _folders(self, app):  # type: ignore[no-untyped-def]
        root = app.project.root_folder
        fwi = next(f for f in root.folders if f.name == "FolderWithItems")
        empty = next(f for f in root.folders if f.name == "EmptyFolder")
        return root, fwi, empty

    def test_move_updates_parent_folder(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        _, fwi, empty = self._folders(app)
        comp1 = next(i for i in fwi.items if i.name == "Comp1")
        comp1.parent_folder = empty
        assert comp1.parent_folder is empty

    def test_move_removes_from_old_items(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        _, fwi, empty = self._folders(app)
        comp1 = next(i for i in fwi.items if i.name == "Comp1")
        comp1.parent_folder = empty
        assert comp1 not in fwi.items

    def test_move_adds_to_new_items(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        _, fwi, empty = self._folders(app)
        comp1 = next(i for i in fwi.items if i.name == "Comp1")
        comp1.parent_folder = empty
        assert comp1 in empty.items

    def test_move_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        _, fwi, empty = self._folders(app)
        comp1 = next(i for i in fwi.items if i.name == "Comp1")
        comp1_id = comp1.id
        comp1.parent_folder = empty

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")

        comp1_2 = app2.project.items[comp1_id]
        empty2 = next(
            f for f in app2.project.root_folder.folders if f.name == "EmptyFolder"
        )
        fwi2 = next(
            f for f in app2.project.root_folder.folders if f.name == "FolderWithItems"
        )
        assert comp1_2.parent_folder is empty2
        assert comp1_2 in empty2.items
        assert comp1_2 not in fwi2.items

    def test_move_to_root(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        fwi = next(f for f in root.folders if f.name == "FolderWithItems")
        comp1 = next(i for i in fwi.items if i.name == "Comp1")
        comp1.parent_folder = root
        assert comp1.parent_folder is root
        assert comp1 in root.items
        assert comp1 not in fwi.items

    def test_move_subtree_keeps_children(self) -> None:
        """Moving a folder relocates its whole subtree."""
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        root_folder = next(f for f in root.folders if f.name == "RootFolder")
        level1 = root_folder.folders[0]
        level2 = level1.folders[0]
        child_names = [f.name for f in level2.folders]

        level2.parent_folder = root
        assert level2 in root.items
        assert level2 not in level1.items
        assert [f.name for f in level2.folders] == child_names

    def test_same_parent_noop(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        empty = next(f for f in root.folders if f.name == "EmptyFolder")
        n = len(root.items)
        empty.parent_folder = root
        assert empty.parent_folder is root
        assert len(root.items) == n

    def test_self_move_raises(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        empty = next(f for f in root.folders if f.name == "EmptyFolder")
        with pytest.raises(ValueError, match="cannot be moved inside itself"):
            empty.parent_folder = empty

    def test_move_into_descendant_raises(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        root_folder = next(f for f in root.folders if f.name == "RootFolder")
        level2 = root_folder.folders[0].folders[0]
        with pytest.raises(ValueError, match="cannot be moved inside itself"):
            root_folder.parent_folder = level2

    def test_move_root_raises(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        empty = next(f for f in root.folders if f.name == "EmptyFolder")
        with pytest.raises(ValueError, match="Cannot move the root folder"):
            root.parent_folder = empty

    def test_non_folder_target_raises(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        fwi = next(f for f in root.folders if f.name == "FolderWithItems")
        comp1 = next(i for i in fwi.items if i.name == "Comp1")
        with pytest.raises(TypeError, match="must be a FolderItem"):
            comp1.parent_folder = comp1.id  # type: ignore[assignment]

    def test_move_relocates_viewer(self) -> None:
        """An item's open-panel viewer moves with it between folders."""
        app = parse_aep(SAMPLES_DIR / "composition" / "selection_both_layers.aep")
        root = app.project.root_folder
        comp = next(
            c for c in root.compositions if c._viewer is not None and c in root.items
        )
        viewer = comp._viewer
        assert viewer in root._viewers

        folder = root.add_folder("Bin")
        comp.parent_folder = folder
        assert viewer not in root._viewers
        assert viewer in folder._viewers


# -----------------------------------------------------------------------
# Project.import_placeholder()
# -----------------------------------------------------------------------


class TestImportPlaceholder:
    """Tests for Project.import_placeholder()."""

    def test_import_placeholder_returns_footage(self) -> None:
        from py_aep.models.items.footage import FootageItem

        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        item = app.project.import_placeholder("PH", 1920, 1080, 30.0, 10.0)
        assert isinstance(item, FootageItem)

    def test_import_placeholder_name(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        item = app.project.import_placeholder("MyPlaceholder", 1920, 1080, 30.0, 10.0)
        assert item.name == "MyPlaceholder"

    def test_import_placeholder_dimensions(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        item = app.project.import_placeholder("PH", 3840, 2160, 24.0, 5.0)
        assert item.width == 3840
        assert item.height == 2160

    def test_import_placeholder_frame_rate(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        item = app.project.import_placeholder("PH", 1920, 1080, 29.97, 10.0)
        assert abs(item.frame_rate - 29.97) < 0.01

    def test_import_placeholder_duration(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        item = app.project.import_placeholder("PH", 1920, 1080, 30.0, 7.5)
        assert abs(item.duration - 7.5) < 0.01

    def test_import_placeholder_is_placeholder(self) -> None:
        from py_aep.models.sources.placeholder import PlaceholderSource

        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        item = app.project.import_placeholder("PH", 1920, 1080, 30.0, 10.0)
        assert isinstance(item.main_source, PlaceholderSource)
        assert item.asset_type == "placeholder"

    def test_import_placeholder_unique_id(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        existing_ids = set(app.project.items.keys())
        item = app.project.import_placeholder("PH", 1920, 1080, 30.0, 10.0)
        assert item.id not in existing_ids

    def test_import_placeholder_in_root_folder(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        item = app.project.import_placeholder("PH", 1920, 1080, 30.0, 10.0)
        assert item.parent_folder is app.project.root_folder
        assert item in app.project.root_folder.items

    def test_import_placeholder_registered_in_project(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        item = app.project.import_placeholder("PH", 1920, 1080, 30.0, 10.0)
        assert app.project.items[item.id] is item
        assert item in app.project.footages

    def test_import_placeholder_invalid_width(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        with pytest.raises(ValueError, match="must be >= 4"):
            app.project.import_placeholder("PH", 2, 1080, 30.0, 10.0)

    def test_import_placeholder_invalid_height(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        with pytest.raises(ValueError, match="must be >= 4"):
            app.project.import_placeholder("PH", 1920, 0, 30.0, 10.0)

    def test_import_placeholder_invalid_frame_rate(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        with pytest.raises(ValueError, match="must be >= 1"):
            app.project.import_placeholder("PH", 1920, 1080, 0.5, 10.0)

    def test_import_placeholder_invalid_duration(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        with pytest.raises(ValueError, match="duration"):
            app.project.import_placeholder("PH", 1920, 1080, 30.0, 0.0)

    def test_import_placeholder_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        item = app.project.import_placeholder("RTPH", 1280, 720, 25.0, 8.0)
        item_id = item.id

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")

        assert item_id in app2.project.items
        item2 = app2.project.items[item_id]
        assert item2.name == "RTPH"
        assert item2.width == 1280
        assert item2.height == 720
        assert abs(item2.duration - 8.0) < 0.01


# -----------------------------------------------------------------------
# FootageItem.replace_with_placeholder()
# -----------------------------------------------------------------------


class TestReplaceWithPlaceholder:
    """Tests for FootageItem.replace_with_placeholder()."""

    def test_replace_with_placeholder(self) -> None:
        from py_aep.models.sources.placeholder import PlaceholderSource

        app = parse_aep(SAMPLES_DIR / "footage" / "solid_colors.aep")
        footage = app.project.footages[0]
        footage.replace_with_placeholder("NewPH", 1920, 1080, 30.0, 10.0)
        assert isinstance(footage.main_source, PlaceholderSource)
        assert footage.name == "NewPH"
        assert footage.width == 1920
        assert footage.height == 1080

    def test_replace_with_placeholder_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "footage" / "solid_colors.aep")
        footage = app.project.footages[0]
        footage_id = footage.id
        footage.replace_with_placeholder("RtPH", 1280, 720, 24.0, 5.0)

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        item2 = app2.project.items[footage_id]
        assert item2.name == "RtPH"
        assert item2.width == 1280
        assert item2.height == 720
        assert item2.asset_type == "placeholder"


# -----------------------------------------------------------------------
# FootageItem.replace_with_solid()
# -----------------------------------------------------------------------


class TestReplaceWithSolid:
    """Tests for FootageItem.replace_with_solid()."""

    def test_replace_with_solid(self) -> None:
        from py_aep.models.sources.solid import SolidSource

        app = parse_aep(SAMPLES_DIR / "footage" / "placeholder.aep")
        footage = app.project.footages[0]
        footage.replace_with_solid([1.0, 0.0, 0.0], "RedSolid", 1920, 1080, 1.0)
        assert isinstance(footage.main_source, SolidSource)
        assert footage.name == "RedSolid"
        assert footage.width == 1920
        assert footage.height == 1080

    def test_replace_with_solid_color(self) -> None:
        app = parse_aep(SAMPLES_DIR / "footage" / "placeholder.aep")
        footage = app.project.footages[0]
        footage.replace_with_solid([0.5, 0.25, 0.75], "ColorSolid", 1920, 1080, 1.0)
        color = footage.main_source.color
        assert abs(color[0] - 0.5) < 0.01
        assert abs(color[1] - 0.25) < 0.01
        assert abs(color[2] - 0.75) < 0.01

    def test_replace_with_solid_invalid_color(self) -> None:
        app = parse_aep(SAMPLES_DIR / "footage" / "placeholder.aep")
        footage = app.project.footages[0]
        with pytest.raises(ValueError, match="must be <= 1"):
            footage.replace_with_solid([1.5, 0.0, 0.0], "Bad", 1920, 1080, 1.0)

    def test_replace_with_solid_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "footage" / "placeholder.aep")
        footage = app.project.footages[0]
        footage_id = footage.id
        footage.replace_with_solid([0.0, 1.0, 0.0], "GreenSolid", 960, 540, 1.0)

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        item2 = app2.project.items[footage_id]
        assert item2.name == "GreenSolid"
        assert item2.width == 960
        assert item2.height == 540
        assert item2.asset_type == "solid"


# -----------------------------------------------------------------------
# AVItem.set_proxy_to_none()
# -----------------------------------------------------------------------


class TestSetProxyToNone:
    """Tests for AVItem.set_proxy_to_none()."""

    def test_set_proxy_to_none_removes_proxy(self) -> None:
        app = parse_aep(SAMPLES_DIR / "item" / "proxy.aep")
        # Find an item that has a proxy
        footage = next(
            (f for f in app.project.footages if f.proxy_source is not None), None
        )
        if footage is None:
            pytest.skip("No item with proxy found in sample")
        footage.set_proxy_to_none()
        assert footage.proxy_source is None

    def test_set_proxy_to_none_noop(self) -> None:
        """Calling set_proxy_to_none when there's no proxy is a no-op."""
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        # Import a placeholder (which has no proxy)
        item = app.project.import_placeholder("PH", 1920, 1080, 30.0, 10.0)
        item.set_proxy_to_none()
        assert item.proxy_source is None

    def test_set_proxy_to_none_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "item" / "proxy.aep")
        footage = next(
            (f for f in app.project.footages if f.proxy_source is not None), None
        )
        if footage is None:
            pytest.skip("No item with proxy found in sample")
        footage_id = footage.id
        footage.set_proxy_to_none()

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        item2 = app2.project.items[footage_id]
        assert item2.proxy_source is None


# -----------------------------------------------------------------------
# AVItem.set_proxy_with_placeholder()
# -----------------------------------------------------------------------


class TestSetProxyWithPlaceholder:
    """Tests for AVItem.set_proxy_with_placeholder()."""

    def test_set_proxy_with_placeholder(self) -> None:
        from py_aep.models.sources.placeholder import PlaceholderSource

        app = parse_aep(SAMPLES_DIR / "footage" / "solid_colors.aep")
        footage = app.project.footages[0]
        footage.set_proxy_with_placeholder("ProxyPH", 960, 540, 30.0, 10.0)
        assert isinstance(footage.proxy_source, PlaceholderSource)

    def test_set_proxy_with_placeholder_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "footage" / "solid_colors.aep")
        footage = app.project.footages[0]
        footage_id = footage.id
        footage.set_proxy_with_placeholder("ProxyPH", 960, 540, 30.0, 10.0)

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        item2 = app2.project.items[footage_id]
        assert item2.proxy_source is not None

    def test_set_proxy_replaces_existing(self) -> None:
        app = parse_aep(SAMPLES_DIR / "item" / "proxy.aep")
        footage = next(
            (f for f in app.project.footages if f.proxy_source is not None), None
        )
        if footage is None:
            pytest.skip("No item with proxy found in sample")
        footage.set_proxy_with_placeholder("NewProxy", 640, 480, 25.0, 5.0)
        from py_aep.models.sources.placeholder import PlaceholderSource

        assert isinstance(footage.proxy_source, PlaceholderSource)


# -----------------------------------------------------------------------
# AVItem.set_proxy_with_solid()
# -----------------------------------------------------------------------


class TestSetProxyWithSolid:
    """Tests for AVItem.set_proxy_with_solid()."""

    def test_set_proxy_with_solid(self) -> None:
        from py_aep.models.sources.solid import SolidSource

        app = parse_aep(SAMPLES_DIR / "footage" / "solid_colors.aep")
        footage = app.project.footages[0]
        footage.set_proxy_with_solid([1.0, 0.0, 0.0], "RedProxy", 960, 540, 1.0)
        assert isinstance(footage.proxy_source, SolidSource)

    def test_set_proxy_with_solid_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "footage" / "solid_colors.aep")
        footage = app.project.footages[0]
        footage_id = footage.id
        footage.set_proxy_with_solid([0.0, 0.0, 1.0], "BlueProxy", 960, 540, 1.0)

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        item2 = app2.project.items[footage_id]
        assert item2.proxy_source is not None

    def test_set_proxy_then_remove(self) -> None:
        app = parse_aep(SAMPLES_DIR / "footage" / "solid_colors.aep")
        footage = app.project.footages[0]
        footage.set_proxy_with_solid([1.0, 1.0, 0.0], "YProxy", 640, 480, 1.0)
        assert footage.proxy_source is not None
        footage.set_proxy_to_none()
        assert footage.proxy_source is None


# -----------------------------------------------------------------------
# auto_name / increment_name
# -----------------------------------------------------------------------


class TestAutoName:
    """Tests for the auto_name naming helper."""

    def test_first_name(self) -> None:
        from py_aep.models.naming import auto_name

        assert auto_name("Comp", set()) == "Comp 1"

    def test_skips_to_2_when_base_exists(self) -> None:
        from py_aep.models.naming import auto_name

        assert auto_name("Comp", {"Comp"}) == "Comp 2"

    def test_skips_to_2_when_base_0_exists(self) -> None:
        from py_aep.models.naming import auto_name

        assert auto_name("Comp", {"Comp 0"}) == "Comp 2"

    def test_skips_existing(self) -> None:
        from py_aep.models.naming import auto_name

        existing = {"Comp 1", "Comp 2"}
        assert auto_name("Comp", existing) == "Comp 3"

    def test_skips_existing_with_base(self) -> None:
        from py_aep.models.naming import auto_name

        existing = {"Comp", "Comp 2", "Comp 3"}
        assert auto_name("Comp", existing) == "Comp 4"

    def test_uses_max_suffix(self) -> None:
        from py_aep.models.naming import auto_name

        existing = {"Comp 4"}
        assert auto_name("Comp", existing) == "Comp 5"

    def test_gap_not_filled(self) -> None:
        from py_aep.models.naming import auto_name

        existing = {"Comp 1", "Comp 5"}
        assert auto_name("Comp", existing) == "Comp 6"


# -----------------------------------------------------------------------
# None / empty name behavior
# -----------------------------------------------------------------------


class TestAutoNameFolder:
    """Tests for add_folder with None name."""

    def test_none_generates_untitled(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        folder = root.add_folder(None)
        assert folder.name.startswith("Untitled ")

    def test_none_increments(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        f1 = root.add_folder(None)
        f2 = root.add_folder(None)
        assert f1.name != f2.name

    def test_none_default_arg(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        folder = root.add_folder()
        assert folder.name.startswith("Untitled ")

    def test_empty_string_allowed(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        folder = root.add_folder("")
        assert folder.name == ""


class TestAutoNameComp:
    """Tests for add_comp with None name."""

    def test_none_generates_comp(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        comp = root.add_comp(None, 1920, 1080, 1.0, 10.0, 24.0)
        assert comp.name.startswith("Comp ")

    def test_empty_string_allowed(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        root = app.project.root_folder
        comp = root.add_comp("", 1920, 1080, 1.0, 10.0, 24.0)
        assert comp.name == ""


class TestAutoNamePlaceholder:
    """Tests for import_placeholder with None/empty name."""

    def test_none_becomes_missing_name(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        item = app.project.import_placeholder(None, 1920, 1080, 24.0, 10.0)
        assert item.name == "Missing Name"

    def test_empty_becomes_placeholder(self) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        item = app.project.import_placeholder("", 1920, 1080, 24.0, 10.0)
        assert item.name == "Placeholder"


class TestAutoNameSolid:
    """Tests for replace_with_solid with None/empty name."""

    def test_none_auto_names_from_color(self) -> None:
        app = parse_aep(SAMPLES_DIR / "footage" / "solid_colors.aep")
        footage = app.project.footages[0]
        footage.replace_with_solid([1.0, 0.0, 0.0], None, 1920, 1080)
        assert "Red Solid" in footage.name

    def test_empty_becomes_question_marks(self) -> None:
        app = parse_aep(SAMPLES_DIR / "footage" / "solid_colors.aep")
        footage = app.project.footages[0]
        footage.replace_with_solid([1.0, 0.0, 0.0], "", 1920, 1080)
        assert footage.name == "????"

    def test_replace_with_placeholder_none(self) -> None:
        app = parse_aep(SAMPLES_DIR / "footage" / "solid_colors.aep")
        footage = app.project.footages[0]
        footage.replace_with_placeholder(None, 1920, 1080, 24.0, 10.0)
        assert footage.name == "Missing Name"

    def test_replace_with_placeholder_empty(self) -> None:
        app = parse_aep(SAMPLES_DIR / "footage" / "solid_colors.aep")
        footage = app.project.footages[0]
        footage.replace_with_placeholder("", 1920, 1080, 24.0, 10.0)
        assert footage.name == "Placeholder"


class TestAutoNameProxy:
    """Tests for proxy methods with None/empty name."""

    def test_proxy_placeholder_none(self) -> None:
        app = parse_aep(SAMPLES_DIR / "footage" / "solid_colors.aep")
        footage = app.project.footages[0]
        footage.set_proxy_with_placeholder(None, 1920, 1080, 24.0, 10.0)
        assert footage.proxy_source is not None

    def test_proxy_placeholder_empty(self) -> None:
        app = parse_aep(SAMPLES_DIR / "footage" / "solid_colors.aep")
        footage = app.project.footages[0]
        footage.set_proxy_with_placeholder("", 1920, 1080, 24.0, 10.0)
        assert footage.proxy_source is not None

    def test_proxy_solid_none(self) -> None:
        app = parse_aep(SAMPLES_DIR / "footage" / "solid_colors.aep")
        footage = app.project.footages[0]
        footage.set_proxy_with_solid([0.0, 1.0, 0.0], None, 960, 540)
        assert footage.proxy_source is not None

    def test_proxy_solid_empty(self) -> None:
        app = parse_aep(SAMPLES_DIR / "footage" / "solid_colors.aep")
        footage = app.project.footages[0]
        footage.set_proxy_with_solid([0.0, 1.0, 0.0], "", 960, 540)
        assert footage.proxy_source is not None
