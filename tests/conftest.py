"""Shared test fixtures and helpers for py_aep tests."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from py_aep import Application, Project
from py_aep import parse as _parse_aep

if TYPE_CHECKING:
    from py_aep.models.items.composition import CompItem
    from py_aep.models.items.folder import FolderItem
    from py_aep.models.items.footage import FootageItem
    from py_aep.models.layers.layer import Layer
    from py_aep.models.renderqueue.render_queue_item import RenderQueueItem

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


@lru_cache(maxsize=None)
def parse_project(aep_file_path: str | os.PathLike[str]) -> Project:
    """Parse an AEP file and return the Project object.

    Results are cached for the session so the same file is only parsed once.
    """
    aep_file_path = os.fspath(aep_file_path)
    return parse_app(aep_file_path).project


@lru_cache(maxsize=None)
def parse_app(aep_file_path: str | os.PathLike[str]) -> Application:
    """Parse an AEP file and return the Application object.

    Results are cached for the session so the same file is only parsed once.
    """
    return _parse_aep(aep_file_path)


@lru_cache(maxsize=None)
def load_expected(samples_dir: Path, sample_name: str) -> dict:
    """Load the expected JSON for a sample."""
    json_path = samples_dir / f"{sample_name}.json"
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def get_sample_files(samples_dir: Path) -> list[str]:
    """Get all .aep stems in a samples directory."""
    if not samples_dir.exists():
        return []
    return [f.stem for f in samples_dir.glob("*.aep")]


def get_first_layer(project: Project) -> Layer:
    """Get the first layer from the first composition that has layers."""
    assert len(project.compositions) >= 1
    for comp in project.compositions:
        if len(comp.layers) >= 1:
            return comp.layers[0]
    raise AssertionError("No composition with layers found")


def get_first_footage(project: Project) -> FootageItem | None:
    """Get the first footage item."""
    if project.footages:
        return project.footages[0]
    return None


# ---- Name-based lookup helpers for consolidated samples ----


def get_comp(project: Project, name: str) -> CompItem:
    """Get a composition by name from a project."""
    for comp in project.compositions:
        if comp.name == name:
            return comp
    raise ValueError(
        f"Composition '{name}' not found. "
        f"Available: {[c.name for c in project.compositions]}"
    )


def get_layer(project: Project, comp_name: str) -> Layer:
    """Get the first layer from a named composition."""
    comp = get_comp(project, comp_name)
    if not comp.layers:
        raise ValueError(f"Composition '{comp_name}' has no layers")
    return comp.layers[0]


def get_footage(project: Project, name: str) -> FootageItem:
    """Get a footage item by name."""
    for item in project.footages:
        if item.name == name:
            return item
    raise ValueError(
        f"Footage '{name}' not found. Available: {[f.name for f in project.footages]}"
    )


def get_folder(project: Project, name: str) -> FolderItem:
    """Get a folder by name."""
    for folder in project.folders:
        if folder.name == name:
            return folder
    raise ValueError(
        f"Folder '{name}' not found. Available: {[f.name for f in project.folders]}"
    )


def get_rqi(project: Project, comp_name: str) -> RenderQueueItem:
    """Get a render queue item by its composition name."""
    for rqi in project.render_queue.items:
        if rqi.comp.name == comp_name:
            return rqi
    raise ValueError(f"RQI for comp '{comp_name}' not found")


# ---- First-item JSON helpers (for non-consolidated single-comp samples) ----


def get_comp_from_json(expected: dict) -> dict:
    """Extract first composition from expected JSON."""
    for item in expected.get("items", []):
        if item.get("typeName") == "Composition":
            return item
    return {}


def get_layer_from_json(expected: dict) -> dict:
    """Extract first layer from expected JSON."""
    for item in expected.get("items", []):
        if "layers" in item and len(item["layers"]) > 0:
            return item["layers"][0]
    return {}


# ---- Name-based JSON lookup helpers ----


def get_comp_from_json_by_name(expected: dict, name: str) -> dict:
    """Get a specific composition from JSON by name."""
    for item in expected.get("items", []):
        if item.get("typeName") == "Composition" and item.get("name") == name:
            return item
    return {}


def get_layer_from_json_by_comp(expected: dict, comp_name: str) -> dict:
    """Get first layer from a named composition in JSON."""
    comp = get_comp_from_json_by_name(expected, comp_name)
    if comp and "layers" in comp and comp["layers"]:
        return comp["layers"][0]
    return {}


def get_footage_from_json_by_name(expected: dict, name: str) -> dict:
    """Get a specific footage item from JSON by name."""
    for item in expected.get("items", []):
        if item.get("typeName") == "Footage" and item.get("name") == name:
            return item
    return {}


def get_folder_from_json_by_name(expected: dict, name: str) -> dict:
    """Get a specific folder from JSON by name."""
    for item in expected.get("items", []):
        if item.get("typeName") == "Folder" and item.get("name") == name:
            return item
    return {}


def get_comp_marker_from_json_by_name(expected: dict, comp_name: str) -> dict:
    """Get first composition marker from a named composition in JSON."""
    comp = get_comp_from_json_by_name(expected, comp_name)
    markers = comp.get("markers", [])
    if isinstance(markers, list) and markers:
        return markers[0]
    return {}


def get_layer_marker_from_json_by_comp(expected: dict, comp_name: str) -> dict:
    """Get first layer marker value from a named composition in JSON."""
    comp = get_comp_from_json_by_name(expected, comp_name)
    if comp and "layers" in comp:
        for layer in comp["layers"]:
            for prop in layer.get("properties", []):
                if prop.get("matchName") == "ADBE Marker":
                    kfs = prop.get("keyframes", [])
                    if kfs:
                        return kfs[0].get("value", {})
    return {}
