from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..binary.chunk import ContainerChunk, ListChunk
from ..binary.ldat_chunks import LdatChunk, Lhd3Chunk
from ..binary.mutations import LRDR_CHILD_ORDER, build_rq_settings_list
from ..binary.render_chunks import ROUT_ITEMS_PER_RQ_ITEM, ArsiChunk, RoutChunk
from ..binary.scalar_chunks import Utf8Chunk
from ..binary.utils import (
    ChunkNotFoundError,
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
    from ..binary.render_chunks import RenderSettingsItem, RoutItem
    from ..models.project import Project


def parse_render_queue(root_chunks: list[Chunk], project: Project) -> RenderQueue:
    """
    Parse the render queue from the top-level chunks.

    Args:
        root_chunks: The top-level chunks from the AEP file.
        project: The Project object being constructed, used to link comp
            references in render queue items.
    """
    try:
        lrdr_chunk = find_by_list_type(chunks=root_chunks, list_type="LRdr")
    except ChunkNotFoundError:
        # Legacy/hand-built files may omit the render-queue scaffold entirely
        # (AE always writes an LRdr, but a minimal file need not). Synthesize an
        # empty queue and attach its LRdr to the root, marked synthetic so
        # write_aep skips it - an untouched queue-less file still round-trips
        # byte-identically. The first add() materializes the tree.
        render_queue = RenderQueue._new(project)
        render_queue._lrdr.synthetic = True
        # AE writes LRdr immediately before LIST:PTRE (the workspace blob), so
        # insert at that canonical root position rather than appending past it.
        ptre_idx = next(
            (
                i
                for i, c in enumerate(root_chunks)
                if isinstance(c, ListChunk) and c.list_type == "PTRE"
            ),
            len(root_chunks),
        )
        root_chunks.insert(ptre_idx, render_queue._lrdr)
        return render_queue
    lrdr_child_chunks = lrdr_chunk.chunks
    synthesized = False

    try:
        list_settings_chunk = find_by_list_type(
            chunks=lrdr_child_chunks, list_type="list"
        )
    except ChunkNotFoundError:
        synthesized = True
        # An LRdr present but lacking its settings 'list' is degenerate;
        # rebuild it so the parse still yields an empty queue instead of
        # raising.
        list_settings_chunk, _, _ = build_rq_settings_list(synthetic=True)
        lrdr_child_chunks.append(list_settings_chunk)
    settings_lhd3 = cast(
        "Lhd3Chunk", find_by_type(chunks=list_settings_chunk.chunks, chunk_type="lhd3")
    )

    # Legacy/minimal files may omit the queue scaffolding (Rout, LItm,
    # LSIf/ARsi). Substitute synthetic placeholders attached to the tree so
    # the parse still yields an (empty) render queue; write_aep() skips
    # synthetic chunks, so untouched files round-trip byte-identically.
    try:
        rout_chunk = cast(
            "RoutChunk", find_by_type(chunks=lrdr_child_chunks, chunk_type="Rout")
        )
    except ChunkNotFoundError:
        synthesized = True
        rout_chunk = RoutChunk(synthetic=True)
        lrdr_child_chunks.append(rout_chunk)

    try:
        litm_chunk = find_by_list_type(chunks=lrdr_child_chunks, list_type="LItm")
    except ChunkNotFoundError:
        synthesized = True
        litm_chunk = ListChunk(list_type="LItm", synthetic=True)
        lrdr_child_chunks.append(litm_chunk)

    try:
        lsif_chunk = find_by_list_type(chunks=lrdr_child_chunks, list_type="LSIf")
    except ChunkNotFoundError:
        synthesized = True
        lsif_chunk = ListChunk(list_type="LSIf", synthetic=True)
        lrdr_child_chunks.append(lsif_chunk)
    try:
        arsi_chunk = cast(
            "ArsiChunk", find_by_type(chunks=lsif_chunk.chunks, chunk_type="ARsi")
        )
    except ChunkNotFoundError:
        arsi_chunk = ArsiChunk(synthetic=True)
        lsif_chunk.chunks.append(arsi_chunk)

    if synthesized:
        # The synthesized placeholders were appended out of AE's canonical LRdr
        # child order; reorder so a populated queue (after add() materializes
        # them) is written canonically. Only when we synthesized something, so
        # an untouched real file's order - hence its round-trip - is untouched.
        _canon = {t: i for i, t in enumerate(LRDR_CHILD_ORDER)}
        lrdr_child_chunks.sort(
            key=lambda c: _canon.get(
                getattr(c, "list_type", None) or c.chunk_type, len(_canon)
            )
        )

    if settings_lhd3.count == 0:
        # Empty render queue: AE writes the settings 'list' with only an lhd3
        # (no ldat). Create a synthetic ldat and attach it to the tree so the
        # model and tree agree. write_aep() skips synthetic chunks, so an
        # untouched empty queue still round-trips byte-identically; the first
        # add() flips it to non-synthetic. (AE may instead write an empty ldat
        # with count==0; reuse it when present.)
        try:
            settings_ldat = cast(
                "LdatChunk",
                find_by_type(chunks=list_settings_chunk.chunks, chunk_type="ldat"),
            )
        except ChunkNotFoundError:
            settings_ldat = LdatChunk(chunk_type="ldat", synthetic=True)
            list_settings_chunk.chunks.append(settings_ldat)
    else:
        settings_ldat = cast(
            "LdatChunk",
            find_by_type(chunks=list_settings_chunk.chunks, chunk_type="ldat"),
        )

    render_queue = RenderQueue(
        _lrdr=lrdr_chunk,
        _rs_lhd3=settings_lhd3,
        _rs_ldat=settings_ldat,
        _rout=rout_chunk,
        _litm=litm_chunk,
        _arsi=arsi_chunk,
        parent=project,
        items=[],
    )

    if settings_lhd3.count > 0:
        render_queue._items = parse_render_queue_items(
            litm_chunk=litm_chunk,
            render_settings=settings_ldat.items,
            rout_items=rout_chunk.items,
            project=project,
            render_queue=render_queue,
        )
    return render_queue


def parse_render_queue_items(
    litm_chunk: ListChunk,
    render_settings: list[RenderSettingsItem],
    rout_items: list[RoutItem],
    project: Project,
    render_queue: RenderQueue,
) -> list[RenderQueueItem]:
    """
    Parse render queue items from the child chunks of LItm.

    Each item consists of:
    - An optional RCom chunk with the item comment
    - A LIST 'list' chunk with OM metadata (lhd3 + ldat)
    - A LIST 'LOm ' chunk with output module chunks

    Args:
        litm_chunk: The LIST 'LItm' chunk containing per-item groups.
        render_settings: The parsed RenderSettingsItem list from LRdr's ldat.
        rout_items: The parsed RoutItem list from the Rout chunk.
        project: The Project object, used to resolve comp references.
        render_queue: The parent RenderQueue being constructed.
    """
    items = []
    item_index = 0
    rcom_container = None
    rcom_utf8 = None
    list_chunk = None

    for chunk in litm_chunk.chunks:
        if isinstance(chunk, ContainerChunk) and chunk.chunk_type == "RCom":
            rcom_container = chunk
            rcom_utf8 = cast(
                "Utf8Chunk",
                find_by_type(chunks=chunk.chunks, chunk_type="Utf8"),
            )
        elif isinstance(chunk, ListChunk):
            if chunk.list_type == "list":
                list_chunk = chunk
            elif chunk.list_type == "LOm " and list_chunk is not None:
                rout_start = item_index * ROUT_ITEMS_PER_RQ_ITEM
                item = parse_render_queue_item(
                    list_chunk=list_chunk,
                    lom_chunk=chunk,
                    ldat_body=render_settings[item_index],
                    rcom_container=rcom_container,
                    rcom_utf8=rcom_utf8,
                    rout_items=rout_items[
                        rout_start : rout_start + ROUT_ITEMS_PER_RQ_ITEM
                    ],
                    litm_chunk=litm_chunk,
                    project=project,
                    render_queue=render_queue,
                )
                items.append(item)
                item_index += 1
                rcom_container = None
                rcom_utf8 = None
                list_chunk = None

    return items


def parse_render_queue_item(
    list_chunk: ListChunk,
    lom_chunk: ListChunk,
    ldat_body: RenderSettingsItem,
    rcom_container: ContainerChunk | None,
    rcom_utf8: Utf8Chunk | None,
    rout_items: list[RoutItem],
    litm_chunk: ListChunk,
    project: Project,
    render_queue: RenderQueue,
) -> RenderQueueItem:
    """
    Parse a single render queue item from its component chunks.

    Args:
        list_chunk: The LIST 'list' chunk containing OM metadata.
        lom_chunk: The LIST 'LOm ' chunk containing output modules.
        ldat_body: The RenderSettingsItem for this item.
        rcom_container: The RCom ContainerChunk, or None if absent.
        rcom_utf8: The Utf8 chunk inside RCom, or None if absent.
        rout_items: This item's block of RoutItems (AE writes 5 per item).
        litm_chunk: The LIST 'LItm' chunk.
        project: The Project object, used to resolve comp references.
        render_queue: The parent RenderQueue being constructed.
    """
    om_ldat = cast(
        "LdatChunk", find_by_type(chunks=list_chunk.chunks, chunk_type="ldat")
    )
    om_ldat_items = om_ldat.items

    comp_id = ldat_body.comp_id
    comp = cast("CompItem", project.items[comp_id])

    # Group chunks by Roou - each Roou starts a new output module
    om_groups = split_on_type(lom_chunk.chunks, "Roou")

    render_queue_item = RenderQueueItem(
        _ldat=ldat_body,
        _litm=litm_chunk,
        _list_chunk=list_chunk,
        _lom=lom_chunk,
        _rcom=rcom_container,
        _rcom_utf8=rcom_utf8,
        _rout_items=rout_items,
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
