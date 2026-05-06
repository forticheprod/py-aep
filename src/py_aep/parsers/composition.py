from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..binary.composition_chunks import CdtaChunk
from ..binary.item_chunks import IdtaChunk
from ..binary.layer_chunks import LdtaChunk
from ..binary.misc_chunks import EwotChunk, PrinChunk
from ..binary.scalar_chunks import CmtaChunk, U1Chunk, Utf8Chunk
from ..binary.utils import (
    ChunkNotFoundError,
    filter_by_list_type,
    find_by_list_type,
    find_by_type,
)
from ..models.items.composition import CompItem
from .essential_graphics import parse_essential_graphics
from .layer import parse_layer

if TYPE_CHECKING:
    from ..binary.chunk import Chunk, ListChunk
    from ..binary.misc_chunks import EwotItem, OtlnItem
    from ..models.items.folder import FolderItem
    from ..models.layers.layer import Layer
    from ..models.project import Project
    from ..models.properties.property import Property


def parse_composition(
    child_chunks: list[Chunk],
    _idta: IdtaChunk,
    _name_utf8: Utf8Chunk,
    _cmta: CmtaChunk | None,
    _item_list: ListChunk,
    project: Project,
    parent_folder: FolderItem,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    otln_entries: list[OtlnItem] | None = None,
) -> CompItem:
    """
    Parse a composition item.

    Args:
        child_chunks: child chunks of the composition LIST chunk.
        _idta: The idta chunk.
        _name_utf8: The Utf8 chunk containing the composition name.
        _cmta: The cmta chunk (None if no comment).
        project: The project.
        parent_folder: The composition's parent folder.
        effect_param_defs: Project-level effect parameter definitions, used as
            fallback when layer-level parT chunks are missing.
    """
    cdta_chunk = cast("CdtaChunk", find_by_type(chunks=child_chunks, chunk_type="cdta"))
    try:
        cdrp_chunk = cast("U1Chunk", find_by_type(chunks=child_chunks, chunk_type="cdrp"))
    except ChunkNotFoundError:
        cdrp_chunk = None

    prin_list = find_by_list_type(chunks=child_chunks, list_type="PRin")
    prin_chunk = cast("PrinChunk", find_by_type(chunks=prin_list.chunks, chunk_type="prin"))

    composition = CompItem(
        _cdrp=cdrp_chunk,
        _cdta=cdta_chunk,
        _cmta=_cmta,
        _idta=_idta,
        _item_list=_item_list,
        _name_utf8=_name_utf8,
        _prin=prin_chunk,
        project=project,
        parent_folder=parent_folder,
    )

    composition._marker_property = _get_markers(
        child_chunks=child_chunks,
        composition=composition,
    )

    eg_result = parse_essential_graphics(child_chunks)
    if eg_result is not None:
        composition._eg_template_name_utf8 = eg_result[0]
        composition._eg_controllers = list(eg_result[1])

    # Parse composition's layers
    layer_sub_chunks = filter_by_list_type(chunks=child_chunks, list_type="Layr")

    # Build layer_id-to-index mapping for Layer control effect properties.
    # ExtendScript reports 1-based layer indices; the binary stores internal
    # layer IDs (ldta.layer_id).  Pre-scan all layer chunks so the mapping
    # is available when parsing effect properties.
    for idx, lc in enumerate(layer_sub_chunks, 1):
        ldta = cast("LdtaChunk", find_by_type(chunks=lc.chunks, chunk_type="ldta"))
        composition._layer_id_to_index[ldta.layer_id] = idx

    for layer_chunk in layer_sub_chunks:
        layer = parse_layer(
            layer_chunk=layer_chunk,
            composition=composition,
            effect_param_defs=effect_param_defs,
        )
        composition.layers.append(layer)

    # Link effect ewot entries for chunk-backed selected state
    ewot_entries = _collect_ewot_entries(child_chunks)
    entry_idx = 0
    for layer in composition.layers:
        if layer.effects is None:
            continue
        for effect in layer.effects:
            if entry_idx < len(ewot_entries):
                effect._ewot_entry = ewot_entries[entry_idx]
            entry_idx += 1

    # Apply layer selection from otln entries
    if otln_entries is not None:
        _apply_otln_to_layers(otln_entries, composition.layers)

    return composition


def _collect_ewot_entries(child_chunks: list[Chunk]) -> list[EwotItem]:
    """Collect effect-group ewot entries from LIST:Ewst / ewot chunks.

    The `ewot` chunk inside `LIST:Ewst` stores per-property flags for
    the effect workspace.  Each entry is 4 bytes: the first byte contains
    flags where bit 6 (`0x40`) indicates *selected*.  Entries whose first
    byte has bit 7 (`0x80`) set are child properties of an effect; entries
    **without** bit 7 are effect-group-level entries.

    Args:
        child_chunks: The composition item's child chunks.

    Returns:
        Ordered list of ewot entries, one per effect across all layers.
    """
    entries: list[EwotItem] = []
    ewst_chunks = filter_by_list_type(chunks=child_chunks, list_type="Ewst")
    for ewst_chunk in ewst_chunks:
        try:
            ewot_chunk = cast("EwotChunk", find_by_type(chunks=ewst_chunk.chunks, chunk_type="ewot"))
        except ChunkNotFoundError:
            continue

        for entry in ewot_chunk.items:
            # Entries without is_child_property are effect group nodes
            if not entry.is_child_property:
                entries.append(entry)

    return entries


def _get_markers(
    child_chunks: list[Chunk], composition: CompItem
) -> Property | None:
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


def _apply_otln_to_layers(entries: list[OtlnItem], layers: list[Layer]) -> None:
    """Store otln root entries on matching layers.

    Layer boundaries are found using `is_layer_marker` entries that appear
    exactly once per layer. The first entry of each layer block is the
    layer root (a GROUP entry with `is_property=0`, `is_sub_entry=0`).
    """
    if not entries or not layers:
        return
    markers = [i for i, e in enumerate(entries) if e.is_layer_marker]
    if len(markers) != len(layers):
        return
    # First layer always starts at index 0
    layer_starts = [0]
    for m in markers[:-1]:
        # Scan forward from marker to find next GROUP entry (next layer root)
        for j in range(m + 1, len(entries)):
            e = entries[j]
            if not e.is_property and not e.is_sub_entry:
                layer_starts.append(j)
                break
    for layer_idx, layer in enumerate(layers):
        if layer_idx < len(layer_starts):
            layer._otln_entry = entries[layer_starts[layer_idx]]
