"""Marker parsing functions.

Extracts composition and layer markers from MRST / Nmrd chunks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..binary.chunk import ListChunk
from ..binary.misc_chunks import NmhdChunk
from ..binary.scalar_chunks import Utf8Chunk
from ..binary.utils import (
    filter_by_list_type,
    filter_by_type,
    find_by_list_type,
    find_by_type,
)
from ..enums import PropertyValueType
from ..models.properties.marker import MarkerValue
from ..models.properties.property import Property
from .property_value import parse_property

if TYPE_CHECKING:
    from ..binary.property_chunks import TdmnChunk
    from ..models.items.composition import CompItem
    from ..models.properties.keyframe import Keyframe


def parse_markers(
    mrst_chunk: ListChunk,
    composition: CompItem,
    property_depth: int,
    tdmn: TdmnChunk,
) -> Property:
    """
    Parse markers from an MRST chunk.

    Returns the underlying [Property][] (the `tdbs` inside the
    `mrst` chunk, with keyframes holding marker values).

    Args:
        mrst_chunk: The MRST chunk to parse.
        composition: The parent composition.
        property_depth: The nesting depth of this property (default 1).
    """
    tdbs_chunk = find_by_list_type(chunks=mrst_chunk.chunks, list_type="tdbs")
    marker_prop = parse_property(
        tdbs_chunk=tdbs_chunk,
        match_name="ADBE Marker",
        composition=composition,
        property_depth=property_depth,
        tdmn=tdmn,
    )
    marker_prop._wrapper = mrst_chunk
    # ExtendScript reports MARKER (6420); the tdb4 flags alone would fall
    # back to OneD like any 1-D scalar.
    marker_prop._property_value_type = PropertyValueType.MARKER
    mrky_chunk = find_by_list_type(chunks=mrst_chunk.chunks, list_type="mrky")
    marker_prop._kf_value_container = mrky_chunk
    nmrd_chunks = filter_by_list_type(chunks=mrky_chunk.chunks, list_type="Nmrd")
    for i, nmrd_chunk in enumerate(nmrd_chunks):
        kf = marker_prop.keyframes[i]
        kf._cache_value(
            parse_marker(
                nmrd_chunk=nmrd_chunk,
                keyframe=kf,
            )
        )
    return marker_prop


def parse_marker(
    nmrd_chunk: ListChunk,
    keyframe: Keyframe | None = None,
    frame_time: int = 0,
) -> MarkerValue:
    """
    Parse a marker.

    Args:
        nmrd_chunk: The NMRD chunk to parse.
        keyframe: The keyframe that holds this marker value.
        frame_time: Fallback time in frames (used when no keyframe ref).
    """
    nmhd_chunk = cast(
        "NmhdChunk", find_by_type(chunks=nmrd_chunk.chunks, chunk_type="NmHd")
    )

    utf8_chunks = cast(
        "list[Utf8Chunk]", filter_by_type(chunks=nmrd_chunk.chunks, chunk_type="Utf8")
    )

    # Collect cue point param Utf8 chunks
    param_utf8s: list[Utf8Chunk] = utf8_chunks[5:]

    return MarkerValue._from_binary(
        _nmhd=nmhd_chunk,
        _comment_utf8=utf8_chunks[0],
        _chapter_utf8=utf8_chunks[1],
        _url_utf8=utf8_chunks[2],
        _frame_target_utf8=utf8_chunks[3],
        _cue_point_name_utf8=utf8_chunks[4],
        _keyframe=keyframe,
        frame_time=frame_time,
        _param_utf8s=param_utf8s,
        _nmrd=nmrd_chunk,
    )
