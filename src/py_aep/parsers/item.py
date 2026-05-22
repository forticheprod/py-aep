from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..binary.chunk import ListChunk
from ..binary.item_chunks import CmtaChunk, IdtaChunk
from ..binary.ldat_chunks import LdatChunk, Lhd3Chunk
from ..binary.scalar_chunks import Utf8Chunk
from ..binary.utils import (
    ChunkNotFoundError,
    filter_by_list_type,
    find_by_list_type,
    find_by_type,
)
from ..enums import ItemType
from ..models.guide import Guide
from ..models.items.folder import FolderItem
from .composition import parse_composition
from .footage import parse_footage
from .view import parse_viewers

if TYPE_CHECKING:
    from ..binary.chunk import Chunk
    from ..models.items.composition import CompItem
    from ..models.items.footage import FootageItem
    from ..models.project import Project


def parse_item(
    item_chunk: ListChunk,
    project: Project,
    parent_folder: FolderItem,
) -> CompItem | FolderItem | FootageItem:
    """
    Parse an item (composition, footage or folder).

    Args:
        item_chunk: The LIST chunk to parse.
        project: The project.
        parent_folder: The parent folder.
    """
    child_chunks = item_chunk.chunks

    idta = cast("IdtaChunk", find_by_type(chunks=child_chunks, chunk_type="idta"))
    name_utf8 = cast("Utf8Chunk", find_by_type(chunks=child_chunks, chunk_type="Utf8"))
    try:
        cmta: CmtaChunk | None = cast(
            "CmtaChunk", find_by_type(chunks=child_chunks, chunk_type="cmta")
        )
    except ChunkNotFoundError:
        cmta = None

    try:
        gide: ListChunk | None = find_by_list_type(
            chunks=item_chunk.chunks, list_type="Gide"
        )
    except ChunkNotFoundError:
        gide = None

    item_type = idta.item_type

    item: FolderItem | FootageItem | CompItem
    if item_type == ItemType.FOLDER:
        item = parse_folder(
            is_root=False,
            child_chunks=child_chunks,
            project=project,
            _idta=idta,
            _name_utf8=name_utf8,
            _cmta=cmta,
            _item_list=item_chunk,
            _gide=gide,
            parent_folder=parent_folder,
        )

    elif item_type == ItemType.FOOTAGE:
        item = parse_footage(
            child_chunks=child_chunks,
            _idta=idta,
            _name_utf8=name_utf8,
            _cmta=cmta,
            _item_list=item_chunk,
            _gide=gide,
            project=project,
            parent_folder=parent_folder,
        )

    elif item_type == ItemType.COMPOSITION:
        item = parse_composition(
            child_chunks=child_chunks,
            _idta=idta,
            _name_utf8=name_utf8,
            _cmta=cmta,
            _item_list=item_chunk,
            _gide=gide,
            project=project,
            parent_folder=parent_folder,
            effect_param_defs=project._effect_param_defs,
        )

    else:
        raise ValueError(f"Unknown item type: {item_type}")

    item._guides = _parse_guides(child_chunks)
    project.items[item.id] = item

    return item


def parse_folder(
    is_root: bool,
    child_chunks: list[Chunk],
    project: Project,
    _idta: IdtaChunk | None,
    _name_utf8: Utf8Chunk | None,
    _cmta: CmtaChunk | None,
    _item_list: ListChunk,
    _gide: ListChunk | None,
    parent_folder: FolderItem | None,
) -> FolderItem:
    """
    Parse a folder item.

    Args:
        is_root: Whether the folder is the root folder (ID 0).
        child_chunks: child chunks of the folder LIST chunk.
        project: The project.
        _idta: The idta chunk (None for the root folder).
        _name_utf8: The Utf8 chunk containing the folder name.
        _cmta: The cmta chunk (None if no comment).
        _item_list: The LIST chunk for creating new chunks.
        _gide: The LIST chunk for guides (None if no guides).
        parent_folder: The folder's parent folder.
    """
    if is_root:
        folder_chunks = child_chunks
        children_container = _item_list.chunks
    else:
        sfdr_chunk = find_by_list_type(chunks=child_chunks, list_type="Sfdr")
        folder_chunks = sfdr_chunk.chunks
        children_container = sfdr_chunk.chunks

    folder = FolderItem(
        _idta=_idta,
        _name_utf8=_name_utf8,
        _cmta=_cmta,
        _item_list=_item_list,
        _gide=_gide,
        _children_container=children_container,
        project=project,
        parent_folder=parent_folder,
    )
    if is_root:
        # Avoid mutating chunk fields
        folder.__dict__["name"] = "root"
    child_item_chunks = filter_by_list_type(chunks=folder_chunks, list_type="Item")
    for child_item_chunk in child_item_chunks:
        child_item = parse_item(
            item_chunk=child_item_chunk,
            project=project,
            parent_folder=folder,
        )
        folder.items.append(child_item)

    folder._viewers = parse_viewers(folder_chunks, folder.items)

    return folder


def _parse_guides(child_chunks: list[Chunk]) -> list[Guide]:
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

    list_chunk = find_by_list_type(chunks=gide_list.chunks, list_type="list")
    lhd3 = cast("Lhd3Chunk", find_by_type(chunks=list_chunk.chunks, chunk_type="lhd3"))
    if lhd3.count == 0:
        return []

    ldat = cast("LdatChunk", find_by_type(chunks=list_chunk.chunks, chunk_type="ldat"))
    return [Guide(_guide_item=item) for item in ldat.items]
