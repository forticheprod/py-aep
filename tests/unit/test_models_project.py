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


class TestAllocateItemId:
    """Tests for Project._allocate_item_id()."""

    def test_first_call_returns_max_plus_one(self) -> None:
        project = parse_aep(LAYER_SAMPLES_DIR / "type.aep").project
        # _head.next_item_id is set by AE and equals max(item_ids) + 1
        expected = project._head.next_item_id
        assert project._allocate_item_id() == expected
        # After allocation, the counter should be incremented
        assert project._head.next_item_id == expected + 1

    def test_successive_calls_increment(self) -> None:
        project = parse_aep(LAYER_SAMPLES_DIR / "type.aep").project
        first = project._allocate_item_id()
        assert project._allocate_item_id() == first + 1
        assert project._allocate_item_id() == first + 2


class TestAllocateLayerId:
    """Tests for Project._allocate_layer_id()."""

    def test_first_call_returns_max_plus_one(self) -> None:
        project = parse_aep(LAYER_SAMPLES_DIR / "type.aep").project
        max_layer = max(
            (lyr.id for comp in project.compositions for lyr in comp.layers),
            default=0,
        )
        assert project._allocate_layer_id() == max_layer + 1

    def test_successive_calls_increment(self) -> None:
        project = parse_aep(LAYER_SAMPLES_DIR / "type.aep").project
        first = project._allocate_layer_id()
        assert project._allocate_layer_id() == first + 1
        assert project._allocate_layer_id() == first + 2

    def test_includes_viewer_pseudo_layer_ids(self) -> None:
        # bgColor.aep has no real layers, but its comp viewers carry ldta
        # pseudo-layers (DLay/SLay/CLay/SecL) that AE allocates from the
        # same project-wide counter.
        project = parse_aep(COMP_SAMPLES_DIR / "bgColor.aep").project
        assert all(not comp.layers for comp in project.compositions)
        existing = set(_all_ldta_ids(project))
        assert existing
        assert project._allocate_layer_id() == max(existing) + 1

    def test_new_layer_and_comp_ids_unique_project_wide(self) -> None:
        project = parse_aep(COMP_SAMPLES_DIR / "bgColor.aep").project
        project.compositions[0].add_null()
        project.root_folder.add_comp("New", 100, 100, 1.0, 5.0, 25.0)
        all_ids = _all_ldta_ids(project)
        assert len(all_ids) == len(set(all_ids))


class TestSaveExistingPath:
    """Project.save() must refuse to overwrite an existing file."""

    def test_save_to_existing_path_raises_file_exists(self, tmp_path: Path) -> None:
        project = parse_aep(LAYER_SAMPLES_DIR / "type.aep").project
        out = tmp_path / "out.aep"
        out.write_bytes(b"stub")
        with pytest.raises(FileExistsError):
            project.save(out)
        assert out.read_bytes() == b"stub"
