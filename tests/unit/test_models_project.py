"""Tests for Project model parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep import parse as parse_aep
from py_aep.binary.utils import recursive_find

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "project"
VIEW_SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "view"
VERSIONS_DIR = Path(__file__).parent.parent.parent / "samples" / "versions"
LAYER_SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"
COMP_SAMPLES_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "composition"
)


def _all_ldta_ids(project) -> list[int]:
    """All ldta layer ids in the project, including viewer pseudo-layers."""
    return [
        ldta.layer_id
        for comp in project.compositions
        for ldta in recursive_find(comp._item_list.chunks, chunk_type="ldta")
    ]


class TestAllocateId:
    """Tests for Project._allocate_id() - AE keeps ONE counter for item
    ids and layer ids (incl. viewer pseudo-layers), persisted in
    `head.next_item_id` and trusted on open (probed in AE 2026)."""

    def test_first_call_returns_counter_value(self) -> None:
        project = parse_aep(LAYER_SAMPLES_DIR / "type.aep").project
        # In an AE-written file next_item_id is already > max(all ids).
        expected = project._head.next_item_id
        assert project._allocate_id() == expected
        assert project._head.next_item_id == expected + 1

    def test_successive_calls_increment(self) -> None:
        project = parse_aep(LAYER_SAMPLES_DIR / "type.aep").project
        first = project._allocate_id()
        assert project._allocate_id() == first + 1
        assert project._allocate_id() == first + 2

    def test_counter_above_all_ids(self) -> None:
        # Every id (item ids AND ldta layer ids, incl. viewer
        # pseudo-layers) must stay below the counter.
        project = parse_aep(COMP_SAMPLES_DIR / "bgColor.aep").project
        all_ids = set(_all_ldta_ids(project)) | set(project.items.keys())
        assert project._allocate_id() > max(all_ids)

    def test_reconciles_drifted_counter(self) -> None:
        # Files written by earlier py_aep versions can carry a counter
        # below the live layer ids; the first allocation must reconcile
        # (AE trusts the counter and would mint duplicate ids otherwise).
        project = parse_aep(COMP_SAMPLES_DIR / "bgColor.aep").project
        all_ids = set(_all_ldta_ids(project)) | set(project.items.keys())
        project._head.next_item_id = 2  # force drift
        assert project._allocate_id() == max(all_ids) + 1
        assert project._head.next_item_id == max(all_ids) + 2

    def test_new_layer_and_comp_ids_unique_project_wide(self) -> None:
        project = parse_aep(COMP_SAMPLES_DIR / "bgColor.aep").project
        project.compositions[0].add_null()
        project.root_folder.add_comp("New", 100, 100, 1.0, 5.0, 25.0)
        all_ids = _all_ldta_ids(project) + list(project.items.keys())
        assert len(all_ids) == len(set(all_ids))
        # The persisted counter must remain above every live id.
        assert project._head.next_item_id > max(all_ids)


class TestSaveExistingPath:
    """Project.save() must refuse to overwrite an existing file."""

    def test_save_to_existing_path_raises_file_exists(self, tmp_path: Path) -> None:
        project = parse_aep(LAYER_SAMPLES_DIR / "type.aep").project
        out = tmp_path / "out.aep"
        out.write_bytes(b"stub")
        with pytest.raises(FileExistsError):
            project.save(out)
        assert out.read_bytes() == b"stub"
