from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..binary.footage_chunks import OptiChunk, SspcChunk
from ..binary.item_chunks import IdtaChunk
from ..binary.scalar_chunks import CmtaChunk, Utf8Chunk
from ..binary.utils import (
    filter_by_list_type,
    find_by_type,
)
from ..models.items.footage import FootageItem
from ..models.sources.file import FileSource
from ..models.sources.placeholder import PlaceholderSource
from ..models.sources.solid import SolidSource
from .source import parse_source

if TYPE_CHECKING:
    from ..binary.chunk import Chunk, ListChunk
    from ..models.items.folder import FolderItem
    from ..models.project import Project


def parse_footage(
    child_chunks: list[Chunk],
    _idta: IdtaChunk,
    _name_utf8: Utf8Chunk,
    _cmta: CmtaChunk | None,
    _item_list: ListChunk,
    _gide: ListChunk | None,
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
        _item_list: The LIST chunk for creating new chunks.
        _gide: The LIST chunk for guides (None if no guides).
        project: The project.
        parent_folder: The item's parent folder.
    """
    pin_chunks = filter_by_list_type(chunks=child_chunks, list_type="Pin ")
    pin_chunk = pin_chunks[0]

    pin_child_chunks = pin_chunk.chunks
    sspc_chunk = cast("SspcChunk", find_by_type(chunks=pin_child_chunks, chunk_type="sspc"))
    opti_chunk = cast("OptiChunk", find_by_type(chunks=pin_child_chunks, chunk_type="opti"))

    main_source = parse_source(pin_chunk)
    proxy_source: FileSource | SolidSource | PlaceholderSource | None = (
        parse_source(pin_chunks[1]) if len(pin_chunks) > 1 else None
    )

    return FootageItem(
        _idta=_idta,
        _name_utf8=_name_utf8,
        _cmta=_cmta,
        _item_list=_item_list,
        _gide=_gide,
        _sspc=sspc_chunk,
        _opti=opti_chunk,
        project=project,
        parent_folder=parent_folder,
        main_source=main_source,
        proxy_source=proxy_source,
    )
