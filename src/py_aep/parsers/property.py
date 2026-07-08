"""Property group and mask parsers with registry-based dispatch."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, NamedTuple, cast

from ..binary.chunk import ListChunk
from ..binary.misc_chunks import MkifChunk
from ..binary.property_chunks import TdsbChunk
from ..binary.scalar_chunks import U4Chunk, Utf8Chunk
from ..binary.utils import (
    ChunkNotFoundError,
    filter_by_list_type,
    filter_by_type,
    find_by_list_type,
    find_by_type,
)
from ..data.match_names import VF_AXIS_PREFIX
from ..models.descriptors import _suppress_materialization
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
    get_match_name_runs,
)

if TYPE_CHECKING:
    from typing import Any, Callable

    from ..binary.chunk import Chunk
    from ..binary.misc_chunks import MkifChunk
    from ..binary.property_chunks import TdmnChunk, TdsbChunk, TdsnChunk, VfdnChunk
    from ..binary.scalar_chunks import Utf8Chunk
    from ..models.items.composition import CompItem
    from ..models.properties.property import Property

logger = logging.getLogger(__name__)


class _ParseContext(NamedTuple):
    """Per-match-name context threaded through the property dispatchers."""

    match_name: str
    chunks: list[Chunk]
    """All chunks of the match-name group (tdmn + bodies + auxiliaries)."""

    first_chunk: ListChunk
    """The first LIST chunk of the group (selects the dispatcher)."""

    child_depth: int
    effect_param_defs: dict[str, dict[str, dict[str, Any]]]
    composition: CompItem

    @property
    def tdmn(self) -> TdmnChunk:
        """The group's first match-name chunk."""
        return cast("TdmnChunk", find_by_type(chunks=self.chunks, chunk_type="tdmn"))


_PROPERTY_PARSERS: dict[
    str, Callable[[_ParseContext], list[Property | PropertyGroup]]
] = {}


def _property_parser(
    list_type: str,
) -> Callable[
    [Callable[[_ParseContext], list[Property | PropertyGroup]]],
    Callable[[_ParseContext], list[Property | PropertyGroup]],
]:
    """Register a property parser for the given LIST subtype."""

    def decorator(
        func: Callable[[_ParseContext], list[Property | PropertyGroup]],
    ) -> Callable[[_ParseContext], list[Property | PropertyGroup]]:
        _PROPERTY_PARSERS[list_type] = func
        return func

    return decorator


@_suppress_materialization()
def parse_properties(
    match_name_runs: list[tuple[str, list[Chunk]]],
    child_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
) -> list[Property | PropertyGroup]:
    """Dispatch sub-property chunks into parsed Property/PropertyGroup items.

    Iterates each match-name run, finds the first LIST chunk, and
    dispatches to the appropriate parser based on its list type.

    Args:
        match_name_runs: Sub-property chunks grouped into ordered
            match-name runs (from `get_match_name_runs`).
        child_depth: The property depth for parsed child properties.
        effect_param_defs: Project-level effect parameter definitions.
        composition: The parent composition.

    Returns:
        Ordered list of parsed properties and property groups.
    """
    properties: list[Property | PropertyGroup] = []
    for match_name, sub_prop_chunks in match_name_runs:
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
                    _ParseContext(
                        match_name=match_name,
                        chunks=sub_prop_chunks,
                        first_chunk=first_chunk,
                        child_depth=child_depth,
                        effect_param_defs=effect_param_defs,
                        composition=composition,
                    )
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
def _dispatch_sspc(ctx: _ParseContext) -> list[Property | PropertyGroup]:
    """Parse effect chunks - iterates all sspc LISTs for the match name."""
    tdmns = cast(
        "list[TdmnChunk]", filter_by_type(chunks=ctx.chunks, chunk_type="tdmn")
    )
    sspcs = filter_by_list_type(chunks=ctx.chunks, list_type="sspc")
    results: list[Property | PropertyGroup] = []
    for tdmn, sspc in zip(tdmns, sspcs):
        effect = parse_effect(
            sspc_chunk=sspc,
            group_match_name=ctx.match_name,
            property_depth=ctx.child_depth,
            effect_param_defs=ctx.effect_param_defs,
            composition=ctx.composition,
            tdmn=tdmn,
        )
        results.append(effect)
    return results


@_property_parser("tdgp")
def _dispatch_tdgp(ctx: _ParseContext) -> list[Property | PropertyGroup]:
    """Parse property group chunks - handles masks and indexed groups."""
    tdmns = cast(
        "list[TdmnChunk]", filter_by_type(chunks=ctx.chunks, chunk_type="tdmn")
    )
    if ctx.match_name == "ADBE Mask Atom":
        tdgps = list(filter_by_list_type(chunks=ctx.chunks, list_type="tdgp"))
        mkifs = cast(
            "list[MkifChunk]",
            list(filter_by_type(chunks=ctx.chunks, chunk_type="mkif")),
        )
        masks: list[Property | PropertyGroup] = []
        for i, (tdmn, tdgp_c, mkif_c) in enumerate(zip(tdmns, tdgps, mkifs), 1):
            mask = _parse_mask_atom(
                tdgp_chunk=tdgp_c,
                mkif_chunk=mkif_c,
                property_depth=ctx.child_depth,
                effect_param_defs=ctx.effect_param_defs,
                composition=ctx.composition,
                tdmn=tdmn,
            )
            mask._auto_name = f"Mask {i}"
            masks.append(mask)
        return masks
    tdgps = list(filter_by_list_type(chunks=ctx.chunks, list_type="tdgp"))
    results: list[Property | PropertyGroup] = []
    for tdmn, tdgp_c in zip(tdmns, tdgps):
        group = parse_property_group(
            tdgp_chunk=tdgp_c,
            group_match_name=ctx.match_name,
            property_depth=ctx.child_depth,
            effect_param_defs=ctx.effect_param_defs,
            composition=ctx.composition,
            tdmn=tdmn,
        )
        results.append(group)
    return results


@_property_parser("tdbs")
def _dispatch_tdbs(ctx: _ParseContext) -> list[Property | PropertyGroup]:
    """Parse a leaf property from a tdbs chunk."""
    prop = parse_property(
        tdbs_chunk=ctx.first_chunk,
        match_name=ctx.match_name,
        composition=ctx.composition,
        property_depth=ctx.child_depth,
        tdmn=ctx.tdmn,
    )
    # A media-replacement slot (`ADBE Layer Source Alternate`) carries blsv/blsi
    # beside its tdbs in the group run; attach them so the Property can decode
    # `can_set_alternate_source` / `alternate_source`. Gated on the match name
    # so the scans do not run for every leaf on the hot parse path.
    if ctx.match_name == "ADBE Layer Source Alternate":
        blsi = filter_by_type(chunks=ctx.chunks, chunk_type="blsi")
        if blsi:
            prop._blsi = cast(U4Chunk, blsi[0])
            blsv = filter_by_type(chunks=ctx.chunks, chunk_type="blsv")
            if blsv:
                prop._blsv = cast(U4Chunk, blsv[0])
    # AE 26+ writes a vfdn sibling (the axis display name from the font)
    # after an active variable-font axis slot's tdbs.
    if ctx.match_name.startswith(VF_AXIS_PREFIX):
        vfdn = filter_by_type(chunks=ctx.chunks, chunk_type="vfdn")
        if vfdn:
            prop._vfdn = cast("VfdnChunk", vfdn[0])
    return [prop]


@_property_parser("otst")
def _dispatch_otst(ctx: _ParseContext) -> list[Property | PropertyGroup]:
    """Parse an orientation property from an otst chunk."""
    prop = parse_orientation(
        otst_chunk=ctx.first_chunk,
        match_name=ctx.match_name,
        property_depth=ctx.child_depth,
        composition=ctx.composition,
        tdmn=ctx.tdmn,
    )
    return [prop]


@_property_parser("btds")
def _dispatch_btds(ctx: _ParseContext) -> list[Property | PropertyGroup]:
    """Parse a text document property from a btds chunk."""
    prop = parse_text_document(
        btds_chunk=ctx.first_chunk,
        match_name=ctx.match_name,
        property_depth=ctx.child_depth,
        composition=ctx.composition,
        tdmn=ctx.tdmn,
    )
    return [prop]


@_property_parser("om-s")
def _dispatch_oms(ctx: _ParseContext) -> list[Property | PropertyGroup]:
    """Parse a shape/mask-path property from an om-s chunk."""
    prop = parse_shape(
        oms_chunk=ctx.first_chunk,
        match_name=ctx.match_name,
        property_depth=ctx.child_depth,
        composition=ctx.composition,
        tdmn=ctx.tdmn,
    )
    return [prop]


@_property_parser("GCst")
def _dispatch_gcst(ctx: _ParseContext) -> list[Property | PropertyGroup]:
    """Parse a gradient color property from a GCst chunk."""
    prop = parse_gradient(
        gcst_chunk=ctx.first_chunk,
        match_name=ctx.match_name,
        property_depth=ctx.child_depth,
        composition=ctx.composition,
        tdmn=ctx.tdmn,
    )
    return [prop]


@_property_parser("mrst")
def _dispatch_mrst(ctx: _ParseContext) -> list[Property | PropertyGroup]:
    """Parse markers from a mrst chunk."""
    prop = parse_markers(
        mrst_chunk=ctx.first_chunk,
        composition=ctx.composition,
        property_depth=ctx.child_depth,
        tdmn=ctx.tdmn,
    )
    return [prop]


@_property_parser("OvG2")
def _dispatch_ovg2(ctx: _ParseContext) -> list[Property | PropertyGroup]:
    """Parse the Essential Properties override group ("ADBE Layer Overrides").

    The match-name run holds the `LIST:OvG2` metadata block (override count +
    controller UUIDs, already parsed at the layer level into
    `Layer.essential_property_uuids`) followed by a sibling `LIST:tdgp` that
    carries the override properties themselves.

    All override groups are exposed (media replacement and grouped/regular
    controllers alike). Leaf properties are re-classed to
    `_EssentialOverrideProperty` so their derived metadata (enabled, bounds,
    is_modified) reflects the Essential Graphics source property rather than the
    override leaf's own partial-copy chunks - the leaf's `value` stays its own.
    """
    tdgps = list(filter_by_list_type(chunks=ctx.chunks, list_type="tdgp"))
    if not tdgps:
        return []
    group = parse_property_group(
        tdgp_chunk=tdgps[0],
        group_match_name=ctx.match_name,
        property_depth=ctx.child_depth,
        effect_param_defs=ctx.effect_param_defs,
        composition=ctx.composition,
        tdmn=ctx.tdmn,
    )
    _reclass_override_leaves(group)
    return [group]


def _reclass_override_leaves(group: PropertyGroup) -> None:
    """Re-class the leaf `Property` children of an override group to
    `_EssentialOverrideProperty`. Group nodes recurse; any `Property` subclass
    (e.g. a specialized property) is left as-is - only plain leaves convert."""
    from ..models.properties.property import Property, _EssentialOverrideProperty

    for child in group.properties:
        if isinstance(child, PropertyGroup):
            _reclass_override_leaves(child)
        elif type(child) is Property:
            child.__class__ = _EssentialOverrideProperty


@_suppress_materialization()
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
        match_name_runs=get_match_name_runs(tdgp_chunk),
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
    try:
        tdsn = cast(
            "TdsnChunk", find_by_type(chunks=tdgp_chunk.chunks, chunk_type="tdsn")
        )
        name_utf8: Utf8Chunk | None = tdsn.utf8
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


@_suppress_materialization()
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
