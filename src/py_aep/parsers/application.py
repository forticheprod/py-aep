"""Main entry point for parsing After Effects project files."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..kaitai.utils import (
    find_by_type,
)
from ..models.application import Application
from ..models.items.folder import FolderItem
from ..models.project import Project
from ..models.viewer.viewer import Viewer

if TYPE_CHECKING:
    from collections.abc import Iterator

    from ..kaitai import Aep


def _collect_viewers(folder: FolderItem) -> Iterator[Viewer]:
    """Recursively collect viewers from a folder and its subfolders."""
    yield from folder._viewers
    for item in folder.items:
        if isinstance(item, FolderItem):
            yield from _collect_viewers(item)


def parse_app(aep: Aep, project: Project) -> Application:
    """Build an [Application][] from the parsed RIFX data and project.

    Args:
        aep: The parsed Kaitai RIFX structure.
        project: The already-parsed [Project][].
    """
    root_chunks = aep.root.body.chunks
    head_chunk = find_by_type(chunks=root_chunks, chunk_type="head")

    # Collect viewer panels from the folder tree (parsed during parse_folder)
    viewers = _collect_viewers(project.root_folder)
    active_viewer = next((v for v in viewers if v.active), None)

    return Application(
        _head=head_chunk.body,
        project=project,
        active_viewer=active_viewer,
    )
