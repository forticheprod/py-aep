from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING

from ..kaitai import Aep
from ..kaitai.utils import (
    ChunkNotFoundError,
    filter_by_list_type,
    find_by_list_type,
    find_by_type,
)
from ..models.guide import Guide
from ..models.items.folder import FolderItem
from .composition import parse_composition
from .footage import parse_footage
from .view import parse_viewers

if TYPE_CHECKING:
    from ..models.items.composition import CompItem
    from ..models.items.footage import FootageItem
    from ..models.project import Project


def parse_item(
    item_chunk: Aep.Chunk,
    project: Project,
    parent_folder: FolderItem,
    otln_entries: list[Aep.OtlnEntry] | None = None,
) -> CompItem | FolderItem | FootageItem:
    """
    Parse an item (composition, footage or folder).

    Args:
        item_chunk: The LIST chunk to parse.
        project: The project.
        parent_folder: The parent folder.
        otln_entries: Otln entries for this composition (from the
            associated LIST:FEE chunk). `None` for non-compositions.
    """
    child_chunks = item_chunk.body.chunks

    idta_body = find_by_type(chunks=child_chunks, chunk_type="idta").body
    name_utf8 = find_by_type(chunks=child_chunks, chunk_type="Utf8").body
    try:
        cmta_body = find_by_type(chunks=child_chunks, chunk_type="cmta").body
    except ChunkNotFoundError:
        cmta_body = None

    item_type = idta_body.item_type

    item: FolderItem | FootageItem | CompItem
    if item_type == Aep.ItemType.folder:
        item = parse_folder(
            is_root=False,
            child_chunks=child_chunks,
            project=project,
            _idta=idta_body,
            _name_utf8=name_utf8,
            _cmta=cmta_body,
            _item_list=item_chunk.body,
            parent_folder=parent_folder,
        )

    elif item_type == Aep.ItemType.footage:
        item = parse_footage(
            child_chunks=child_chunks,
            _idta=idta_body,
            _name_utf8=name_utf8,
            _cmta=cmta_body,
            _item_list=item_chunk.body,
            project=project,
            parent_folder=parent_folder,
        )

    elif item_type == Aep.ItemType.composition:
        item = parse_composition(
            child_chunks=child_chunks,
            _idta=idta_body,
            _name_utf8=name_utf8,
            _cmta=cmta_body,
            _item_list=item_chunk.body,
            project=project,
            parent_folder=parent_folder,
            effect_param_defs=project._effect_param_defs,
            otln_entries=otln_entries,
        )

    else:
        raise ValueError(f"Unknown item type: {item_type}")

    item._guides = _parse_guides(child_chunks)
    project.items[item.id] = item

    return item


def parse_folder(
    is_root: bool,
    child_chunks: list[Aep.Chunk],
    project: Project,
    _idta: Aep.IdtaBody | None,
    _name_utf8: Aep.Utf8Body | None,
    _cmta: Aep.Utf8Body | None,
    _item_list: Aep.ListBody | None,
    parent_folder: FolderItem | None,
) -> FolderItem:
    """
    Parse a folder item.

    Args:
        is_root: Whether the folder is the root folder (ID 0).
        child_chunks: child chunks of the folder LIST chunk.
        project: The project.
        _idta: The idta chunk body (None for the root folder).
        _name_utf8: The Utf8 chunk body containing the folder name.
        _cmta: The cmta chunk body (None if no comment).
        _item_list: The LIST body for creating new chunks.
        parent_folder: The folder's parent folder.
    """
    folder = FolderItem(
        _idta=_idta,
        _name_utf8=_name_utf8,
        _cmta=_cmta,
        _item_list=_item_list,
        project=project,
        parent_folder=parent_folder,
    )
    if is_root:
        # Avoid mutating chunk fields
        folder.__dict__["name"] = "root"
        folder_chunks = child_chunks
    else:
        sfdr_chunk = find_by_list_type(chunks=child_chunks, list_type="Sfdr")
        folder_chunks = sfdr_chunk.body.chunks
    otln_map = _build_otln_map(folder_chunks)
    child_item_chunks = filter_by_list_type(chunks=folder_chunks, list_type="Item")
    for child_item_chunk in child_item_chunks:
        idta = find_by_type(chunks=child_item_chunk.body.chunks, chunk_type="idta")
        child_item = parse_item(
            item_chunk=child_item_chunk,
            project=project,
            parent_folder=folder,
            otln_entries=otln_map.get(idta.body.item_id),
        )
        folder.items.append(child_item)

    folder._viewers = parse_viewers(folder_chunks, folder.items)

    return folder


def _build_otln_map(
    folder_chunks: list[Aep.Chunk],
) -> dict[int, list[Aep.OtlnEntry]]:
    """Build a mapping of composition item ID to otln entries.

    Each LIST:FEE immediately follows its composition's LIST:Item in
    the folder chunk list. The otln chunk inside FEE stores per-entry
    collapsed and selected flags for the composition's timeline outline.
    """
    otln_map: dict[int, list[Aep.OtlnEntry]] = {}
    last_comp_id: int | None = None
    for chunk in folder_chunks:
        if chunk.chunk_type != "LIST":
            continue
        lt = chunk.body.list_type
        if lt == "Item":
            idta = find_by_type(chunks=chunk.body.chunks, chunk_type="idta")
            if idta.body.item_type == Aep.ItemType.composition:
                last_comp_id = idta.body.item_id
            else:
                last_comp_id = None
        elif lt == "FEE " and last_comp_id is not None:
            with suppress(ChunkNotFoundError):
                otln_map[last_comp_id] = find_by_type(
                    chunks=chunk.body.chunks, chunk_type="otln"
                ).body.entries
            last_comp_id = None
    return otln_map


def _parse_guides(child_chunks: list[Aep.Chunk]) -> list[Guide]:
    """Parse composition guides from the LIST:Gide chunk.

    Args:
        child_chunks: child chunks of the item LIST chunk.

    Returns:
        List of Guide objects, empty if no guides are defined.
    """
    try:
        gide_list = find_by_list_type(chunks=child_chunks, list_type="Gide")
    except ChunkNotFoundError:
        return []

    list_chunk = find_by_list_type(chunks=gide_list.body.chunks, list_type="list")
    lhd3 = list_chunk.body.lhd3
    if lhd3.body.count == 0:
        return []

    ldat = list_chunk.body.ldat
    return [Guide(_guide_item=item) for item in ldat.body.items]
