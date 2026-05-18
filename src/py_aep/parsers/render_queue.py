from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..binary.chunk import ContainerChunk, ListChunk
from ..binary.ldat_chunks import LdatChunk, Lhd3Chunk
from ..binary.scalar_chunks import Utf8Chunk
from ..binary.utils import (
    find_by_list_type,
    find_by_type,
    split_on_type,
)
from ..models.items.composition import CompItem
from ..models.renderqueue.render_queue import RenderQueue
from ..models.renderqueue.render_queue_item import RenderQueueItem
from .output_module import parse_output_module

if TYPE_CHECKING:
    from ..binary.chunk import Chunk
    from ..binary.render_chunks import RenderSettingsItem
    from ..models.project import Project


def parse_render_queue(root_chunks: list[Chunk], project: Project) -> RenderQueue:
    """
    Parse the render queue from the top-level chunks.

    Args:
        root_chunks: The top-level chunks from the AEP file.
        project: The Project object being constructed, used to link comp
            references in render queue items.
    """
    lrdr_chunk = find_by_list_type(chunks=root_chunks, list_type="LRdr")
    lrdr_child_chunks = lrdr_chunk.chunks
    render_queue = RenderQueue(parent=project, items=[])
    items = parse_render_queue_items(lrdr_child_chunks, project, render_queue)
    render_queue._items = items
    return render_queue


def parse_render_queue_items(
    lrdr_child_chunks: list[Chunk],
    project: Project,
    render_queue: RenderQueue,
) -> list[RenderQueueItem]:
    """
    Parse render queue items from the child chunks of LRdr.

    The render queue items are stored in a LIST 'list' chunk directly under LRdr.
    Each item consists of:
    - An optional RCom chunk with the item comment
    - A LIST 'list' chunk with item metadata and settings
    - A LIST 'LOm ' chunk with output module info
    - A RenderSettingsItem with the render settings for the item
    - A Rout chunk with per-item render flags

    Args:
        lrdr_child_chunks: The child chunks of the LRdr chunk.
        project: The Project object being constructed, used to link comp
            references in render queue items.
    """
    # Parse render settings from the LIST 'list' directly under LRdr
    # This ldat contains N × item_size bytes, one block per render queue item
    list_settings_chunk = find_by_list_type(chunks=lrdr_child_chunks, list_type="list")

    settings_lhd3 = cast(
        "Lhd3Chunk", find_by_type(chunks=list_settings_chunk.chunks, chunk_type="lhd3")
    )
    num_items = settings_lhd3.count
    if num_items == 0:
        return []

    settings_ldat = cast(
        "LdatChunk", find_by_type(chunks=list_settings_chunk.chunks, chunk_type="ldat")
    )
    render_settings_chunks: list[RenderSettingsItem] = settings_ldat.items

    # LItm chunk is probably the RQItemCollection.
    litm_chunk = find_by_list_type(chunks=lrdr_child_chunks, list_type="LItm")

    # Structure: [RCom] + LIST 'list' + LIST 'LOm ' per item
    # RCom is optional and contains the item comment
    items = []
    item_index = 0
    rcom_chunk = None
    list_chunk = None

    for chunk in litm_chunk.chunks:
        if isinstance(chunk, ContainerChunk) and chunk.chunk_type == "RCom":
            # RCom is a ContainerChunk with a Utf8 child
            rcom_chunk = cast(
                "Utf8Chunk",
                find_by_type(
                    chunks=chunk.chunks,
                    chunk_type="Utf8",
                ),
            )
        elif isinstance(chunk, ListChunk):
            if chunk.list_type == "list":
                list_chunk = chunk
            elif chunk.list_type == "LOm " and list_chunk is not None:
                # We have both list_chunk and lom_chunk, parse the item
                item = parse_render_queue_item(
                    list_chunk=list_chunk,
                    lom_chunk=chunk,
                    ldat_body=render_settings_chunks[item_index],
                    rcom_utf8=rcom_chunk,
                    litm_chunk=litm_chunk,
                    project=project,
                    render_queue=render_queue,
                )
                items.append(item)
                item_index += 1
                rcom_chunk = None
                list_chunk = None

    return items


def parse_render_queue_item(
    list_chunk: ListChunk,
    lom_chunk: ListChunk,
    ldat_body: RenderSettingsItem,
    rcom_utf8: Utf8Chunk | None,
    litm_chunk: ListChunk,
    project: Project,
    render_queue: RenderQueue,
) -> RenderQueueItem:
    """
    Parse a single render queue item from its component chunks.

    Args:
        list_chunk: The LIST 'list' chunk containing item metadata.
        lom_chunk: The LIST 'LOm ' chunk containing output modules.
        ldat_body: The RenderSettingsItem for this item.
        rcom_utf8: The Utf8 chunk of the RCom, or None if absent.
        litm_chunk: The LIST 'LItm' chunk.
        project: The Project object being constructed, used to link comp
            references in render queue items.
    """
    om_ldat = cast(
        "LdatChunk", find_by_type(chunks=list_chunk.chunks, chunk_type="ldat")
    )
    om_ldat_items = om_ldat.items

    # comp_id is stored in the render settings ldat
    comp_id = ldat_body.comp_id
    comp = cast("CompItem", project.items[comp_id])

    lom_child_chunks = lom_chunk.chunks

    # Group chunks by Roou - each Roou starts a new output module
    om_groups = split_on_type(lom_child_chunks, "Roou")

    render_queue_item = RenderQueueItem(
        _ldat=ldat_body,
        _litm=litm_chunk,
        _list_chunk=list_chunk,
        _rcom_utf8=rcom_utf8,
        parent=render_queue,
        comp=comp,
        output_modules=[],
    )

    output_modules = []
    for om_index, group in enumerate(om_groups):
        output_module = parse_output_module(
            group, om_ldat_items[om_index], render_queue_item
        )
        output_modules.append(output_module)

    render_queue_item._output_modules = output_modules

    return render_queue_item
