"""Core single-property parsing and keyframe extraction."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from ..binary.chunk import ListChunk
from ..binary.ldat_chunks import LdatChunk
from ..binary.property_chunks import (
    CdatChunk,
    Tdb4Chunk,
    TdsbChunk,
    TdsnChunk,
    TdumChunk,
)
from ..binary.scalar_chunks import S4Chunk, Utf8Chunk
from ..binary.utils import (
    ChunkNotFoundError,
    find_by_list_type,
    find_by_type,
)
from ..models.descriptors import _suppress_materialization
from ..models.properties.keyframe import Keyframe
from ..models.properties.property import Property

if TYPE_CHECKING:
    from ..binary.chunk import Chunk
    from ..binary.property_chunks import TdmnChunk
    from ..models.items.composition import CompItem

logger = logging.getLogger(__name__)


@_suppress_materialization()
def parse_property(
    tdbs_chunk: ListChunk,
    match_name: str,
    composition: CompItem,
    property_depth: int,
    tdmn: TdmnChunk,
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
    tdbs_child_chunks = tdbs_chunk.chunks

    tdsb_chunk = cast(
        "TdsbChunk", find_by_type(chunks=tdbs_child_chunks, chunk_type="tdsb")
    )

    tdb4_chunk = cast(
        "Tdb4Chunk", find_by_type(chunks=tdbs_child_chunks, chunk_type="tdb4")
    )

    try:
        cdat: CdatChunk | None = cast(
            "CdatChunk", find_by_type(chunks=tdbs_child_chunks, chunk_type="cdat")
        )
    except ChunkNotFoundError:
        cdat = None

    # Static value is read lazily by Property.value from _cdat via
    # _resolve_value.  Only extract here for non-cdat overrides.
    value = None

    # For LAYER control properties, keep the tdpi chunk reference so the
    # layer index can be resolved lazily (it changes on layer reorder).
    # tdli stores the 1-based mask index directly and is stable.
    tdpi: S4Chunk | None = None
    try:
        tdpi = cast(
            "S4Chunk", find_by_type(chunks=tdbs_child_chunks, chunk_type="tdpi")
        )
    except ChunkNotFoundError:
        pass
    try:
        value = cast(
            "S4Chunk", find_by_type(chunks=tdbs_child_chunks, chunk_type="tdli")
        ).value
    except ChunkNotFoundError:
        pass

    try:
        expression_utf8 = cast(
            "Utf8Chunk", find_by_type(chunks=tdbs_child_chunks, chunk_type="Utf8")
        )
    except ChunkNotFoundError:
        expression_utf8 = None

    try:
        tdum = cast(
            "TdumChunk", find_by_type(chunks=tdbs_child_chunks, chunk_type="tdum")
        )
    except ChunkNotFoundError:
        tdum = None
    try:
        tduM = cast(
            "TdumChunk", find_by_type(chunks=tdbs_child_chunks, chunk_type="tduM")
        )
    except ChunkNotFoundError:
        tduM = None

    keyframes = _parse_keyframes(
        tdbs_child_chunks,
        composition.time_scale,
        frame_rate=composition.frame_rate,
    )

    # Resolve _name_utf8 from the LIST:tdbs tdsn child.
    tdsn = cast("TdsnChunk", find_by_type(chunks=tdbs_child_chunks, chunk_type="tdsn"))
    name_utf8 = tdsn.utf8

    prop = Property(
        _tdmn=tdmn,
        _tdsb=tdsb_chunk,
        _tdb4=tdb4_chunk,
        _expression_utf8=expression_utf8,
        _name_utf8=name_utf8,
        _tdbs=tdbs_chunk,
        _tdum=tdum,
        _tduM=tduM,
        _cdat=cdat,
        _tdpi=tdpi,
        _composition=composition,
        match_name=match_name,
        property_depth=property_depth,
        keyframes=keyframes,
        value=value,
    )

    return prop


def _parse_keyframes(
    tdbs_child_chunks: list[Chunk],
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

    try:
        ldat = cast(
            "LdatChunk", find_by_type(chunks=list_chunk.chunks, chunk_type="ldat")
        )
    except ChunkNotFoundError:
        return []

    kf_items = ldat.items

    return [
        Keyframe(
            _ldat_item=kf,
            _time_scale=time_scale,
            _frame_rate=frame_rate,
        )
        for kf in kf_items
    ]
