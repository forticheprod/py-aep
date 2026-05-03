from __future__ import annotations

import typing

from ..binary.utils import (
    ChunkNotFoundError,
    find_by_list_type,
    find_by_type,
)
from ..models.items.footage import FootageItem
from ..models.sources.file import FileSource
from ..models.sources.placeholder import PlaceholderSource
from ..models.sources.solid import SolidSource

if typing.TYPE_CHECKING:
    from ..binary.chunk import Chunk, ListChunk
    from ..models.items.folder import FolderItem
    from ..models.project import Project


def parse_footage(
    child_chunks: list[Chunk],
    _idta: Chunk,
    _name_utf8: Chunk,
    _cmta: Chunk | None,
    _item_list: ListChunk,
    project: Project,
    parent_folder: FolderItem,
) -> FootageItem:
    """
    Parse a footage item.

    Args:
        child_chunks: The footage item child chunks.
        _idta: The idta chunk.
        _name_utf8: The Utf8 chunk containing the item name.
        _cmta: The cmta chunk (None if no comment).
        project: The project.
        parent_folder: The item's parent folder.
    """
    pin_chunk = find_by_list_type(chunks=child_chunks, list_type="Pin ")

    pin_child_chunks = pin_chunk.chunks
    sspc_chunk = find_by_type(chunks=pin_child_chunks, chunk_type="sspc")
    opti_chunk = find_by_type(chunks=pin_child_chunks, chunk_type="opti")

    # Extract CLRS color management chunks (optional)
    try:
        clrs = find_by_list_type(chunks=pin_child_chunks, list_type="CLRS")
        try:
            linl = find_by_type(chunks=clrs.chunks, chunk_type="linl")
        except ChunkNotFoundError:
            linl = None
    except ChunkNotFoundError:
        clrs = None
        linl = None

    asset_type = getattr(opti_chunk, "asset_type", "")
    sspc_body = sspc_chunk

    main_source: FileSource | SolidSource | PlaceholderSource
    if not asset_type and hasattr(opti_chunk, "placeholder_name"):
        main_source = PlaceholderSource(_sspc=sspc_body, _clrs=clrs, _linl=linl)
    elif asset_type.startswith("Soli"):
        main_source = SolidSource(
            _sspc=sspc_body, _opti=opti_chunk, _clrs=clrs, _linl=linl
        )
    else:
        main_source = FileSource(
            _pin=pin_chunk,
            _sspc=sspc_body,
            _opti=opti_chunk,
            _linl=linl,
            _clrs=clrs,
        )

    return FootageItem(
        _idta=_idta,
        _name_utf8=_name_utf8,
        _cmta=_cmta,
        _item_list=_item_list,
        _sspc=sspc_body,
        _opti=opti_chunk,
        project=project,
        parent_folder=parent_folder,
        main_source=main_source,
    )
