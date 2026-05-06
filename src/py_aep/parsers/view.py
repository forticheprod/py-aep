from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..binary.misc_chunks import FipsChunk
from ..binary.scalar_chunks import AsciiChunk, U1Chunk
from ..binary.utils import (
    ChunkNotFoundError,
    filter_by_type,
    find_by_type,
    group_chunks,
)
from ..models.items.av_item import AVItem
from ..models.viewer.view import View
from ..models.viewer.view_options import ViewOptions
from ..models.viewer.viewer import Viewer

if TYPE_CHECKING:
    from ..binary.chunk import Chunk
    from ..models.items.item import Item


def parse_viewers(
    folder_chunks: list[Chunk],
    items: list[Item],
) -> list[Viewer]:
    """Parse viewer panels from folder-level chunks.

    Each item in the folder is followed by a viewer block bounded by
    `fvdv` (start) and `fifl` (end).  The Nth viewer block belongs to the
    Nth item in the folder.

    Viewer objects (panel state) are only created when a `fitt` chunk is
    present (open panel). Views (from `fips` chunks) are assigned to the
    viewer, and the viewer is linked back to AVItems for OutputModule ROI.

    Args:
        folder_chunks: Chunks from a `LIST:Fold` or `LIST:Sfdr` body.
        items: Ordered list of items in this folder, used to resolve
            each viewer block to its item.

    Returns:
        A list of parsed [Viewer][py_aep.models.viewer.viewer.Viewer] objects.
    """
    blocks = group_chunks(folder_chunks, "fvdv", "fifl")
    viewers: list[Viewer] = []
    for i, block in enumerate(blocks):
        item = items[i] if i < len(items) else None
        viewer = _build_viewer(block)
        if viewer is not None:
            viewer._views = _parse_views(block, item, viewer)
            if isinstance(item, AVItem):
                item._viewer = viewer
            viewers.append(viewer)
    return viewers


def _parse_views(
    block: list[Chunk],
    item: Item | None,
    viewer: Viewer,
) -> list[View]:
    """Parse view objects from a viewer block.

    Each locked view has 4 viewport slots (fips chunks) for the 3D
    viewport layout. One View is created per locked view, using the
    first viewport slot's options.

    Args:
        block: The sequence of chunks from `fvdv` to `fifl`.
        item: The item this viewer belongs to (for ROI validation).
        viewer: The parent viewer that owns these views.

    Returns:
        A list of [View][py_aep.models.viewer.view.View] objects.
    """
    fips_chunks = cast("list[FipsChunk]", filter_by_type(block, "fips"))
    av_item = item if isinstance(item, AVItem) else None
    # Each locked view owns 4 consecutive fips (3D viewport slots).
    # Create one View per group of 4, using the first slot.
    views: list[View] = []
    for i in range(0, len(fips_chunks), 4):
        fips = fips_chunks[i]
        views.append(
            View(
                _viewer=viewer,
                options=ViewOptions(_fips=fips, _item=av_item),
            )
        )
    return views


def _build_viewer(
    block: list[Chunk],
) -> Viewer | None:
    """Build a Viewer from a block of folder-level chunks.

    A Viewer represents an open panel.  Blocks without a `fitt` chunk
    have no open panel and return `None`.

    Args:
        block: The sequence of chunks from `fvdv` to `fifl`.

    Returns:
        A [Viewer][py_aep.models.viewer.viewer.Viewer] instance, or `None` if the
        block does not contain a recognised viewer type.
    """
    try:
        fitt = cast("AsciiChunk", find_by_type(block, "fitt"))
    except ChunkNotFoundError:
        return None

    foac = cast("U1Chunk", find_by_type(block, "foac"))
    fiac = cast("U1Chunk", find_by_type(block, "fiac"))

    return Viewer(
        _fitt=fitt,
        _foac=foac,
        _fiac=fiac,
    )
