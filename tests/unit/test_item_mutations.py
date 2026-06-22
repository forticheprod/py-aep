"""Tests for item creation and removal mutations."""

from __future__ import annotations

from pathlib import Path

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models"


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


class TestSortChildrenByName:
    """FolderItem._sort_children_by_name (used by the layered-import path)."""

    def test_orders_items_and_sfdr_blocks_alphabetically(self) -> None:
        import py_aep

        folder = py_aep.new().project.root_folder.add_folder("Layers")
        # add_comp front-inserts, so document order != stored order; mixed case
        # and a non-alphabetical sequence exercise the case-insensitive sort.
        for name in ["zebra", "alpha", "Mango", "beta"]:
            folder.add_comp(name, 100, 100, 1.0, 1.0, 30.0)

        folder._sort_children_by_name()

        expected = ["alpha", "beta", "Mango", "zebra"]
        assert [item.name for item in folder.items] == expected
        # The backing Sfdr item_list chunks are reordered to match.
        id_to_name = {id(item._item_list): item.name for item in folder.items}
        chunk_order = [
            id_to_name[id(chunk)]
            for chunk in folder._children_container
            if id(chunk) in id_to_name
        ]
        assert chunk_order == expected
