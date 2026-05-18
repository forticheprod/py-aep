"""Property group and mask parsers with registry-based dispatch."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from ..binary.chunk import ListChunk
from ..binary.misc_chunks import MkifChunk
from ..binary.property_chunks import TdsbChunk
from ..binary.scalar_chunks import Utf8Chunk
from ..binary.utils import (
    ChunkNotFoundError,
    filter_by_list_type,
    filter_by_type,
    find_by_list_type,
    find_by_type,
)
from ..models.properties.mask_property_group import MaskPropertyGroup
from ..models.properties.property_group import PropertyGroup
from .effect import parse_effect
from .marker import parse_markers
from .property_value import (
    parse_property,
)
from .specialized_properties import (
    parse_gradient,
    parse_orientation,
    parse_shape,
    parse_text_document,
)
from .utils import (
    get_chunks_by_match_name,
)

if TYPE_CHECKING:
    from typing import Any, Callable

    from ..binary.chunk import Chunk, ContainerChunk
    from ..binary.misc_chunks import MkifChunk
    from ..binary.property_chunks import TdmnChunk, TdsbChunk
    from ..binary.scalar_chunks import Utf8Chunk
    from ..models.items.composition import CompItem
    from ..models.properties.property import Property

logger = logging.getLogger(__name__)

_PROPERTY_PARSERS: dict[str, Callable[..., list[Property | PropertyGroup]]] = {}


def _property_parser(
    list_type: str,
) -> Callable[
    [Callable[..., list[Property | PropertyGroup]]],
    Callable[..., list[Property | PropertyGroup]],
]:
    """Register a property parser for the given LIST subtype."""

    def decorator(
        func: Callable[..., list[Property | PropertyGroup]],
    ) -> Callable[..., list[Property | PropertyGroup]]:
        _PROPERTY_PARSERS[list_type] = func
        return func

    return decorator


def parse_properties(
    chunks_by_match_name: dict[str, list[Chunk]],
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Dispatch sub-property chunks into parsed Property/PropertyGroup items.

    Iterates each match-name group, finds the first LIST chunk, and
    dispatches to the appropriate parser based on its list type.

    Args:
        chunks_by_match_name: Sub-property chunks grouped by match name
            (from `get_chunks_by_match_name`).
        child_depth: The property depth for parsed child properties.
        effect_param_defs: Project-level effect parameter definitions.
        composition: The parent composition.

    Returns:
        Ordered list of parsed properties and property groups.
    """
    properties: list[Property | PropertyGroup] = []
    for match_name, sub_prop_chunks in chunks_by_match_name.items():
        # Find the first LIST chunk; non-LIST chunks (e.g. mkif for masks)
        # are auxiliary data that we skip when determining the property type.
        first_chunk = None
        for c in sub_prop_chunks:
            if isinstance(c, ListChunk):
                first_chunk = c
                break
        if first_chunk is None:
            continue

        list_type = first_chunk.list_type
        handler = _PROPERTY_PARSERS.get(list_type)
        if handler is not None:
            properties.extend(
                handler(
                    match_name,
                    sub_prop_chunks,
                    first_chunk,
                    child_depth,
                    effect_param_defs,
                    composition,
                )
            )
        else:
            logger.warning(
                "Skipping unsupported property list type '%s' (match name '%s')",
                list_type,
                match_name,
            )

    return properties


@_property_parser("sspc")
def _dispatch_sspc(
    match_name: str,
    sub_prop_chunks: list[Chunk],
    first_chunk: ListChunk,
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Parse effect chunks - iterates all sspc LISTs for the match name."""
    tdmns = cast(
        "list[TdmnChunk]", filter_by_type(chunks=sub_prop_chunks, chunk_type="tdmn")
    )
    sspcs = filter_by_list_type(chunks=sub_prop_chunks, list_type="sspc")
    results: list[Property | PropertyGroup] = []
    for tdmn, sspc in zip(tdmns, sspcs):
        effect = parse_effect(
            sspc_chunk=sspc,
            group_match_name=match_name,
            property_depth=child_depth,
            effect_param_defs=effect_param_defs,
            composition=composition,
            tdmn=tdmn,
        )
        results.append(effect)
    return results


@_property_parser("tdgp")
def _dispatch_tdgp(
    match_name: str,
    sub_prop_chunks: list[Chunk],
    first_chunk: ListChunk,
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Parse property group chunks - handles masks and indexed groups."""
    tdmns = cast(
        "list[TdmnChunk]", filter_by_type(chunks=sub_prop_chunks, chunk_type="tdmn")
    )
    if match_name == "ADBE Mask Atom":
        tdgps = list(filter_by_list_type(chunks=sub_prop_chunks, list_type="tdgp"))
        mkifs = cast(
            "list[MkifChunk]",
            list(filter_by_type(chunks=sub_prop_chunks, chunk_type="mkif")),
        )
        masks: list[Property | PropertyGroup] = []
        for i, (tdmn, tdgp_c, mkif_c) in enumerate(zip(tdmns, tdgps, mkifs), 1):
            mask = _parse_mask_atom(
                tdgp_chunk=tdgp_c,
                mkif_chunk=mkif_c,
                property_depth=child_depth,
                effect_param_defs=effect_param_defs,
                composition=composition,
                tdmn=tdmn,
            )
            mask._auto_name = f"Mask {i}"
            masks.append(mask)
        return masks
    tdgps = list(filter_by_list_type(chunks=sub_prop_chunks, list_type="tdgp"))
    results: list[Property | PropertyGroup] = []
    for tdmn, tdgp_c in zip(tdmns, tdgps):
        group = parse_property_group(
            tdgp_chunk=tdgp_c,
            group_match_name=match_name,
            property_depth=child_depth,
            effect_param_defs=effect_param_defs,
            composition=composition,
            tdmn=tdmn,
        )
        results.append(group)
    return results


@_property_parser("tdbs")
def _dispatch_tdbs(
    match_name: str,
    sub_prop_chunks: list[Chunk],
    first_chunk: ListChunk,
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Parse a leaf property from a tdbs chunk."""
    tdmn = cast("TdmnChunk", find_by_type(chunks=sub_prop_chunks, chunk_type="tdmn"))
    prop = parse_property(
        tdbs_chunk=first_chunk,
        match_name=match_name,
        composition=composition,
        property_depth=child_depth,
        tdmn=tdmn,
    )
    return [prop]


@_property_parser("otst")
def _dispatch_otst(
    match_name: str,
    sub_prop_chunks: list[Chunk],
    first_chunk: ListChunk,
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Parse an orientation property from an otst chunk."""
    tdmn = cast("TdmnChunk", find_by_type(chunks=sub_prop_chunks, chunk_type="tdmn"))
    prop = parse_orientation(
        otst_chunk=first_chunk,
        match_name=match_name,
        property_depth=child_depth,
        composition=composition,
        tdmn=tdmn,
    )
    return [prop]


@_property_parser("btds")
def _dispatch_btds(
    match_name: str,
    sub_prop_chunks: list[Chunk],
    first_chunk: ListChunk,
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Parse a text document property from a btds chunk."""
    tdmn = cast("TdmnChunk", find_by_type(chunks=sub_prop_chunks, chunk_type="tdmn"))
    prop = parse_text_document(
        btds_chunk=first_chunk,
        match_name=match_name,
        property_depth=child_depth,
        composition=composition,
        tdmn=tdmn,
    )
    return [prop]


@_property_parser("om-s")
def _dispatch_oms(
    match_name: str,
    sub_prop_chunks: list[Chunk],
    first_chunk: ListChunk,
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Parse a shape/mask-path property from an om-s chunk."""
    tdmn = cast("TdmnChunk", find_by_type(chunks=sub_prop_chunks, chunk_type="tdmn"))
    prop = parse_shape(
        oms_chunk=first_chunk,
        match_name=match_name,
        property_depth=child_depth,
        composition=composition,
        tdmn=tdmn,
    )
    return [prop]


@_property_parser("GCst")
def _dispatch_gcst(
    match_name: str,
    sub_prop_chunks: list[Chunk],
    first_chunk: ListChunk,
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Parse a gradient color property from a GCst chunk."""
    tdmn = cast("TdmnChunk", find_by_type(chunks=sub_prop_chunks, chunk_type="tdmn"))
    prop = parse_gradient(
        gcst_chunk=first_chunk,
        match_name=match_name,
        property_depth=child_depth,
        composition=composition,
        tdmn=tdmn,
    )
    return [prop]


@_property_parser("mrst")
def _dispatch_mrst(
    match_name: str,
    sub_prop_chunks: list[Chunk],
    first_chunk: ListChunk,
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Parse markers from a mrst chunk."""
    tdmn = cast("TdmnChunk", find_by_type(chunks=sub_prop_chunks, chunk_type="tdmn"))
    prop = parse_markers(
        mrst_chunk=first_chunk,
        composition=composition,
        property_depth=child_depth,
        tdmn=tdmn,
    )
    return [prop]


@_property_parser("OvG2")
def _dispatch_ovg2(
    match_name: str,
    sub_prop_chunks: list[Chunk],
    first_chunk: ListChunk,
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Skip Essential Properties override metadata."""
    logger.debug("Skipping OvG2 metadata (match name '%s')", match_name)
    return []


def parse_property_group(
    tdgp_chunk: ListChunk,
    group_match_name: str,
    property_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
    tdmn: TdmnChunk,
) -> PropertyGroup:
    """
    Parse a property group.

    Args:
        tdgp_chunk: The TDGP chunk to parse.
        group_match_name: A special name for the property used to build unique
            naming paths. The match name is not displayed, but you can refer
            to it in scripts. Every property has a unique match-name
            identifier. Match names are stable from version to version
            regardless of the display name (the name attribute value) or any
            changes to the application. Unlike the display name, it is not
            localized. An indexed group
            (`PropertyBase.property_type == PropertyType.indexed_group`)
            may not have a name value, but always has a match_name value.
        property_depth: The nesting depth of this group (0 = layer level).
        effect_param_defs: Project-level effect parameter definitions, used as
            fallback when layer-level parT chunks are missing.
        composition: The parent composition.
        tdmn: The TDMN chunk for this property group.
    """
    properties = parse_properties(
        chunks_by_match_name=get_chunks_by_match_name(tdgp_chunk),
        child_depth=property_depth + 1,
        effect_param_defs=effect_param_defs,
        composition=composition,
    )

    # Try to read the group-level tdsb chunk.
    # Leaf properties always have a tdsb; groups may or may not.
    try:
        group_tdsb: TdsbChunk | None = cast(
            "TdsbChunk", find_by_type(chunks=tdgp_chunk.chunks, chunk_type="tdsb")
        )
    except ChunkNotFoundError:
        group_tdsb = None

    # Resolve _name_utf8 from the tdgp's tdsn child
    # tdsn is a ContainerChunk with a Utf8 child
    try:
        tdsn = cast(
            "ContainerChunk", find_by_type(chunks=tdgp_chunk.chunks, chunk_type="tdsn")
        )
        name_utf8: Utf8Chunk | None = cast(
            "Utf8Chunk", find_by_type(chunks=tdsn.chunks, chunk_type="Utf8")
        )
    except ChunkNotFoundError:
        name_utf8 = None

    prop_group = PropertyGroup(
        _tdmn=tdmn,
        _tdgp=tdgp_chunk,
        _tdsb=group_tdsb,
        _name_utf8=name_utf8,
        match_name=group_match_name,
        property_depth=property_depth,
        properties=properties,
    )

    return prop_group


def _parse_mask_atom(
    tdgp_chunk: ListChunk,
    mkif_chunk: MkifChunk,
    property_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
    tdmn: TdmnChunk,
) -> MaskPropertyGroup:
    """Parse a mask atom into a MaskPropertyGroup.

    Combines the child properties from the tdgp chunk with the mask-specific
    attributes (inverted, locked, mask_mode, color, mask_feather_falloff,
    mask_motion_blur) parsed from the mkif chunk, and the rotoBezier flag
    from the ADBE Mask Shape tdsb chunk.

    Args:
        tdgp_chunk: The tdgp chunk for this mask atom.
        mkif_chunk: The mkif (mask info) chunk containing mask attributes.
        property_depth: The nesting depth of this group.
        effect_param_defs: Project-level effect parameter definitions.
        composition: The parent composition.
        tdmn: The TDMN chunk for this mask atom.
    """
    base = parse_property_group(
        tdgp_chunk=tdgp_chunk,
        group_match_name="ADBE Mask Atom",
        property_depth=property_depth,
        effect_param_defs=effect_param_defs,
        composition=composition,
        tdmn=tdmn,
    )

    # Extract the mask shape's tdsb for the roto_bezier descriptor.
    mask_shape_tdsb = None
    chunks_by_mn = get_chunks_by_match_name(tdgp_chunk)
    mask_shape_chunks = chunks_by_mn.get("ADBE Mask Shape", [])
    for chunk in mask_shape_chunks:
        if isinstance(chunk, ListChunk) and chunk.list_type == "om-s":
            try:
                tdbs = find_by_list_type(chunks=chunk.chunks, list_type="tdbs")
                mask_shape_tdsb = cast(
                    "TdsbChunk", find_by_type(chunks=tdbs.chunks, chunk_type="tdsb")
                )
            except ChunkNotFoundError:
                pass
            break

    mask_group = MaskPropertyGroup(
        _tdmn=tdmn,
        _tdgp=cast("ListChunk", base._tdgp),
        _tdsb=base._tdsb,
        _name_utf8=base._name_utf8,
        _mkif=mkif_chunk,
        _mask_shape_tdsb=mask_shape_tdsb,
        match_name=base.match_name,
        property_depth=base.property_depth,
        properties=base.properties,
    )
    mask_group._property_type = base.property_type
    mask_group._is_mask = True
    return mask_group
