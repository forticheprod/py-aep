"""Property group and mask parsers with registry-based dispatch."""

from __future__ import annotations

import logging
import typing
from contextlib import suppress
from typing import Any

from ..kaitai import Aep
from ..kaitai.utils import (
    ChunkNotFoundError,
    filter_by_list_type,
    filter_by_type,
    find_by_list_type,
    find_by_type,
)
from ..models.properties.mask_property_group import MaskPropertyGroup
from ..models.properties.property import Property
from ..models.properties.property_group import PropertyGroup
from .effect import parse_effect
from .marker import parse_markers
from .property_value import (
    parse_property,
)
from .specialized_properties import parse_orientation, parse_shape, parse_text_document
from .utils import (
    get_chunks_by_match_name,
)

if typing.TYPE_CHECKING:
    from ..models.items.composition import CompItem

logger = logging.getLogger(__name__)

_PROPERTY_PARSERS: dict[str, typing.Callable[..., list[Property | PropertyGroup]]] = {}


def _property_parser(
    list_type: str,
) -> typing.Callable[
    [typing.Callable[..., list[Property | PropertyGroup]]],
    typing.Callable[..., list[Property | PropertyGroup]],
]:
    """Register a property parser for the given LIST subtype."""

    def decorator(
        func: typing.Callable[..., list[Property | PropertyGroup]],
    ) -> typing.Callable[..., list[Property | PropertyGroup]]:
        _PROPERTY_PARSERS[list_type] = func
        return func

    return decorator


def parse_properties(
    chunks_by_match_name: dict[str, list[Aep.Chunk]],
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
        try:
            first_chunk = find_by_type(chunks=sub_prop_chunks, chunk_type="LIST")
        except ChunkNotFoundError:
            continue

        list_type = first_chunk.body.list_type
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
    sub_prop_chunks: list[Aep.Chunk],
    first_chunk: Aep.Chunk,
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Parse effect chunks - iterates all sspc LISTs for the match name."""
    return [
        parse_effect(
            sspc_chunk=chunk,
            group_match_name=match_name,
            property_depth=child_depth,
            effect_param_defs=effect_param_defs,
            composition=composition,
        )
        for chunk in filter_by_list_type(chunks=sub_prop_chunks, list_type="sspc")
    ]


@_property_parser("tdgp")
def _dispatch_tdgp(
    match_name: str,
    sub_prop_chunks: list[Aep.Chunk],
    first_chunk: Aep.Chunk,
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Parse property group chunks - handles masks and indexed groups."""
    if match_name == "ADBE Mask Atom":
        masks: list[Property | PropertyGroup] = [
            _parse_mask_atom(
                tdgp_chunk=tdgp_c,
                mkif_chunk=mkif_c,
                property_depth=child_depth,
                effect_param_defs=effect_param_defs,
                composition=composition,
            )
            for tdgp_c, mkif_c in zip(
                filter_by_list_type(chunks=sub_prop_chunks, list_type="tdgp"),
                filter_by_type(chunks=sub_prop_chunks, chunk_type="mkif"),
            )
        ]
        for i, mask in enumerate(masks, 1):
            mask._auto_name = f"Mask {i}"
        return masks
    return [
        parse_property_group(
            tdgp_chunk=tdgp_c,
            group_match_name=match_name,
            property_depth=child_depth,
            effect_param_defs=effect_param_defs,
            composition=composition,
        )
        for tdgp_c in filter_by_list_type(chunks=sub_prop_chunks, list_type="tdgp")
    ]


@_property_parser("tdbs")
def _dispatch_tdbs(
    match_name: str,
    sub_prop_chunks: list[Aep.Chunk],
    first_chunk: Aep.Chunk,
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Parse a leaf property from a tdbs chunk."""
    return [
        parse_property(
            tdbs_chunk=first_chunk,
            match_name=match_name,
            composition=composition,
            property_depth=child_depth,
        )
    ]


@_property_parser("otst")
def _dispatch_otst(
    match_name: str,
    sub_prop_chunks: list[Aep.Chunk],
    first_chunk: Aep.Chunk,
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Parse an orientation property from an otst chunk."""
    return [
        parse_orientation(
            otst_chunk=first_chunk,
            match_name=match_name,
            property_depth=child_depth,
            composition=composition,
        )
    ]


@_property_parser("btds")
def _dispatch_btds(
    match_name: str,
    sub_prop_chunks: list[Aep.Chunk],
    first_chunk: Aep.Chunk,
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Parse a text document property from a btds chunk."""
    return [
        parse_text_document(
            btds_chunk=first_chunk,
            match_name=match_name,
            property_depth=child_depth,
            composition=composition,
        )
    ]


@_property_parser("om-s")
def _dispatch_oms(
    match_name: str,
    sub_prop_chunks: list[Aep.Chunk],
    first_chunk: Aep.Chunk,
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Parse a shape/mask-path property from an om-s chunk."""
    return [
        parse_shape(
            oms_chunk=first_chunk,
            match_name=match_name,
            property_depth=child_depth,
            composition=composition,
        )
    ]


@_property_parser("mrst")
def _dispatch_mrst(
    match_name: str,
    sub_prop_chunks: list[Aep.Chunk],
    first_chunk: Aep.Chunk,
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Parse markers from a mrst chunk."""
    return [
        parse_markers(
            mrst_chunk=first_chunk,
            composition=composition,
            property_depth=child_depth,
        )
    ]


@_property_parser("OvG2")
def _dispatch_ovg2(
    match_name: str,
    sub_prop_chunks: list[Aep.Chunk],
    first_chunk: Aep.Chunk,
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Skip Essential Properties override metadata."""
    logger.debug("Skipping OvG2 metadata (match name '%s')", match_name)
    return []


def parse_property_group(
    tdgp_chunk: Aep.Chunk,
    group_match_name: str,
    property_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
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
        group_tdsb = find_by_type(chunks=tdgp_chunk.body.chunks, chunk_type="tdsb")
        group_tdsb_body = group_tdsb.body
    except ChunkNotFoundError:
        group_tdsb_body = None

    # Resolve _name_utf8 from the tdgp's tdsn child
    try:
        name_utf8 = (
            find_by_type(chunks=tdgp_chunk.body.chunks, chunk_type="tdsn")
            .body.chunks[0]
            .body
        )
    except ChunkNotFoundError:
        name_utf8 = None

    prop_group = PropertyGroup(
        _tdgp=tdgp_chunk.body,
        _tdsb=group_tdsb_body,
        _name_utf8=name_utf8,
        match_name=group_match_name,
        property_depth=property_depth,
        properties=properties,
    )

    return prop_group


def _parse_mask_atom(
    tdgp_chunk: Aep.Chunk,
    mkif_chunk: Aep.Chunk,
    property_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
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
    """
    base = parse_property_group(
        tdgp_chunk=tdgp_chunk,
        group_match_name="ADBE Mask Atom",
        property_depth=property_depth,
        effect_param_defs=effect_param_defs,
        composition=composition,
    )

    # Extract the mask shape's tdsb body for the roto_bezier descriptor.
    mask_shape_tdsb_body = None
    chunks_by_mn = get_chunks_by_match_name(tdgp_chunk)
    mask_shape_chunks = chunks_by_mn.get("ADBE Mask Shape", [])
    for chunk in mask_shape_chunks:
        if chunk.chunk_type == "LIST" and chunk.body.list_type == "om-s":
            with suppress(ChunkNotFoundError):
                tdbs = find_by_list_type(chunks=chunk.body.chunks, list_type="tdbs")
                mask_shape_tdsb_body = tdbs.body.tdsb.body
            break

    mask_group = MaskPropertyGroup(
        _tdgp=base._tdgp,
        _tdsb=base._tdsb,
        _name_utf8=base._name_utf8,
        _mkif=mkif_chunk.body,
        _mask_shape_tdsb=mask_shape_tdsb_body,
        match_name=base.match_name,
        property_depth=base.property_depth,
        properties=base.properties,
    )
    mask_group._property_type = base.property_type
    mask_group._is_mask = True
    return mask_group
