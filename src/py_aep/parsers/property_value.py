"""Core single-property parsing and keyframe extraction."""

from __future__ import annotations

import logging
import typing
from contextlib import suppress

if typing.TYPE_CHECKING:
    from ..models.items.composition import CompItem

from ..kaitai import Aep
from ..kaitai.utils import (
    ChunkNotFoundError,
    find_by_list_type,
    find_by_type,
)
from ..models.properties.keyframe import Keyframe
from ..models.properties.property import Property

logger = logging.getLogger(__name__)


def parse_property(
    tdbs_chunk: Aep.Chunk,
    match_name: str,
    composition: CompItem,
    property_depth: int,
) -> Property:
    """
    Parse a property.

    Args:
        tdbs_chunk: The TDBS chunk to parse.
        match_name: A special name for the property used to build unique
            naming paths. The match name is not displayed, but you can refer
            to it in scripts. Every property has a unique match-name
            identifier. Match names are stable from version to version
            regardless of the display name (the name attribute value) or any
            changes to the application. Unlike the display name, it is not
            localized.
        composition: The parent composition.
        property_depth: The nesting depth of this property (0 = layer level).
    """
    tdbs_child_chunks = tdbs_chunk.body.chunks

    tdsb_chunk = tdbs_chunk.body.tdsb

    tdb4_chunk = tdbs_chunk.body.tdb4

    try:
        cdat_body = find_by_type(chunks=tdbs_child_chunks, chunk_type="cdat").body
    except ChunkNotFoundError:
        cdat_body = None

    # Static value is read lazily by Property.value from _cdat via
    # _resolve_value.  Only extract here for non-cdat overrides.
    value = None

    # For LAYER/MASK control properties, read index from tdpi/tdli chunks.
    # tdpi stores the binary layer_id (references ldta.layer_id); convert
    # to a 1-based layer index using the composition's mapping.
    # tdli stores the 1-based mask index directly.
    with suppress(ChunkNotFoundError):
        layer_id = find_by_type(chunks=tdbs_child_chunks, chunk_type="tdpi").body.value
        if layer_id == 0 or composition._layer_id_to_index is None:
            value = 0
        else:
            value = composition._layer_id_to_index.get(layer_id, 0)
    with suppress(ChunkNotFoundError):
        value = find_by_type(chunks=tdbs_child_chunks, chunk_type="tdli").body.value

    try:
        expression_utf8 = find_by_type(chunks=tdbs_child_chunks, chunk_type="Utf8").body
    except ChunkNotFoundError:
        expression_utf8 = None

    try:
        tdum_body = find_by_type(chunks=tdbs_child_chunks, chunk_type="tdum").body
    except ChunkNotFoundError:
        tdum_body = None
    try:
        tduM_body = find_by_type(chunks=tdbs_child_chunks, chunk_type="tduM").body
    except ChunkNotFoundError:
        tduM_body = None

    keyframes = _parse_keyframes(
        tdbs_child_chunks,
        composition.time_scale,
        frame_rate=composition.frame_rate,
    )

    # Keyframe value/ease transforms are now lazy: Keyframe.value uses
    # Property._resolve_value, and Keyframe._resolve_ease handles
    # interpolation-type overrides.  Percent/color/effect scaling of both
    # values and ease speeds is applied at access time.

    # Resolve _name_utf8 from the LIST:tdbs tdsn child (always at index 1).
    tdsn = tdbs_chunk.body.tdsn
    name_utf8 = tdsn.body.chunks[0].body

    prop = Property(
        _tdsb=tdsb_chunk.body,
        _tdb4=tdb4_chunk.body,
        _expression_utf8=expression_utf8,
        _name_utf8=name_utf8,
        _tdbs=tdbs_chunk.body,
        _tdum=tdum_body,
        _tduM=tduM_body,
        _cdat=cdat_body,
        match_name=match_name,
        property_depth=property_depth,
        keyframes=keyframes,
        value=value,
    )

    return prop


def _parse_keyframes(
    tdbs_child_chunks: list[Aep.Chunk],
    time_scale: float,
    frame_rate: float,
) -> list[Keyframe]:
    """Parse keyframes from a property's child chunks.

    Args:
        tdbs_child_chunks: The child chunks of the TDBS chunk.
        time_scale: The time scale of the parent composition.
        frame_rate: The frame rate of the parent composition.
    """
    try:
        list_chunk = find_by_list_type(chunks=tdbs_child_chunks, list_type="list")
    except ChunkNotFoundError:
        return []

    ldat = list_chunk.body.ldat
    if ldat is None:
        return []

    ldat_body = ldat.body
    kf_items = ldat_body.items

    return [
        Keyframe(
            _ldat_item=kf,
            _time_scale=time_scale,
            _frame_rate=frame_rate,
        )
        for kf in kf_items
    ]
