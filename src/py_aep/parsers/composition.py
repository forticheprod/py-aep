from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..binary.utils import filter_by_list_type, find_by_list_type
from ..models.items.composition import CompItem
from .layer import parse_layer
from .source import parse_source

if TYPE_CHECKING:
    from ..binary.chunk import Chunk, ListChunk
    from ..binary.item_chunks import CmtaChunk, IdtaChunk
    from ..binary.scalar_chunks import Utf8Chunk
    from ..models.items.folder import FolderItem
    from ..models.project import Project
    from ..models.properties.property import Property


def parse_composition(
    child_chunks: list[Chunk],
    _idta: IdtaChunk,
    _name_utf8: Utf8Chunk,
    _cmta: CmtaChunk | None,
    _item_list: ListChunk,
    _gide: ListChunk | None,
    project: Project,
    parent_folder: FolderItem,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
) -> CompItem:
    """
    Parse a composition item.

    Args:
        child_chunks: child chunks of the composition LIST chunk.
        _idta: The idta chunk.
        _name_utf8: The Utf8 chunk containing the composition name.
        _cmta: The cmta chunk (None if no comment).
        _item_list: The LIST chunk for creating new chunks.
        _gide: The LIST chunk for guides (None if no guides).
        project: The project.
        parent_folder: The composition's parent folder.
        effect_param_defs: Project-level effect parameter definitions, used as
            fallback when layer-level parT chunks are missing.
    """
    pin_chunks = filter_by_list_type(chunks=child_chunks, list_type="Pin ")
    proxy_source = parse_source(pin_chunks[0]) if pin_chunks else None

    return CompItem(
        _child_chunks=child_chunks,
        _cmta=_cmta,
        _idta=_idta,
        _item_list=_item_list,
        _gide=_gide,
        _pin_chunks=pin_chunks,
        _name_utf8=_name_utf8,
        project=project,
        parent_folder=parent_folder,
        effect_param_defs=effect_param_defs,
        proxy_source=proxy_source,
    )


def _get_markers(child_chunks: list[Chunk], composition: CompItem) -> Property | None:
    """
    Get the composition markers.

    Marker keyframe times in the binary format are stored in absolute
    composition time (not relative to the SecL layer's start time).

    Args:
        child_chunks: child chunks of the composition LIST chunk.
        composition: The parent composition.
    """
    markers_layer_chunk = find_by_list_type(chunks=child_chunks, list_type="SecL")
    markers_layer = parse_layer(
        layer_chunk=markers_layer_chunk,
        composition=composition,
        effect_param_defs={},
    )
    if markers_layer.marker is None:
        return None

    return markers_layer.marker
