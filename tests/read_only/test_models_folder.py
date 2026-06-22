"""Tests for Folder model parsing."""

from __future__ import annotations

from pathlib import Path

from conftest import (
    get_folder,
    get_folder_from_json_by_name,
    load_expected,
    parse_project,
)

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "folder"


class TestFolderBasic:
    """Tests for basic folder attributes."""

    def test_empty(self) -> None:
        project = parse_project(SAMPLES_DIR / "folder.aep")
        expected = load_expected(SAMPLES_DIR, "folder")
        folder_json = get_folder_from_json_by_name(expected, "EmptyFolder")
        folder = get_folder(project, "EmptyFolder")
        assert folder.name == folder_json["name"] == "EmptyFolder"

    def test_name_renamed(self) -> None:
        project = parse_project(SAMPLES_DIR / "folder.aep")
        expected = load_expected(SAMPLES_DIR, "folder")
        folder_json = get_folder_from_json_by_name(expected, "RenamedFolder")
        folder = get_folder(project, "RenamedFolder")
        assert folder.name == folder_json["name"] == "RenamedFolder"

    def test_comment(self) -> None:
        project = parse_project(SAMPLES_DIR / "folder.aep")
        expected = load_expected(SAMPLES_DIR, "folder")
        folder_json = get_folder_from_json_by_name(expected, "comment")
        folder = get_folder(project, "comment")
        assert folder.comment == folder_json["comment"] == "Folder comment"


class TestFolderLabel:
    """Tests for folder label attribute."""

    def test_label_1(self) -> None:
        project = parse_project(SAMPLES_DIR / "folder.aep")
        expected = load_expected(SAMPLES_DIR, "folder")
        folder_json = get_folder_from_json_by_name(expected, "label_1")
        folder = get_folder(project, "label_1")
        assert folder.label.value == folder_json["label"] == 1

    def test_label_5(self) -> None:
        project = parse_project(SAMPLES_DIR / "folder.aep")
        expected = load_expected(SAMPLES_DIR, "folder")
        folder_json = get_folder_from_json_by_name(expected, "label_5")
        folder = get_folder(project, "label_5")
        assert folder.label.value == folder_json["label"] == 5

    def test_label_10(self) -> None:
        project = parse_project(SAMPLES_DIR / "folder.aep")
        expected = load_expected(SAMPLES_DIR, "folder")
        folder_json = get_folder_from_json_by_name(expected, "label_10")
        folder = get_folder(project, "label_10")
        assert folder.label.value == folder_json["label"] == 10


class TestFolderNesting:
    """Tests for folder nesting."""

    def test_parentFolder_nested(self) -> None:
        project = parse_project(SAMPLES_DIR / "folder.aep")
        nested = [f for f in project.folders if f.parent_folder]
        assert len(nested) >= 3

    def test_numItems_3(self) -> None:
        project = parse_project(SAMPLES_DIR / "folder.aep")
        expected = load_expected(SAMPLES_DIR, "folder")
        folder_json = get_folder_from_json_by_name(expected, "FolderWithItems")
        folder = get_folder(project, "FolderWithItems")
        assert folder_json["numItems"] == 3
        assert len(folder.items) == folder_json["numItems"]
        assert all(hasattr(item, "id") for item in folder.items)
