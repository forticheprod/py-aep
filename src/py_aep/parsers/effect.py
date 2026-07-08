"""Effect and parameter definition parsers."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, cast

from ..binary.chunk import ContainerChunk
from ..binary.misc_chunks import PardChunk
from ..binary.property_chunks import TdmnChunk, TdsbChunk, TdsnChunk
from ..binary.scalar_chunks import Utf8Chunk
from ..binary.utils import (
    ChunkNotFoundError,
    filter_by_list_type,
    find_by_list_type,
    find_by_type,
)
from ..data.match_names import MATCH_NAME_TO_AUTO_NAME
from ..enums import (
    PropertyControlType,
    PropertyType,
    PropertyValueType,
)
from ..models.descriptors import _suppress_materialization
from ..models.properties.overrides import _CANVARY_OVERRIDES, _PROPERTY_DEFAULTS
from ..models.properties.property import Property
from ..models.properties.property_group import PropertyGroup
from ..synthesis.property import PropSpec
from .utils import (
    get_chunks_by_match_name,
    get_match_name_runs,
)

if TYPE_CHECKING:
    from typing import Any, Callable

    from ..binary.chunk import Chunk, ListChunk
    from ..models.items.composition import CompItem


logger = logging.getLogger(__name__)

_PVT_DIMENSIONS: dict[PropertyValueType, int] = {
    PropertyValueType.COLOR: 4,
    PropertyValueType.ThreeD_SPATIAL: 3,
    PropertyValueType.TwoD_SPATIAL: 2,
}


def _param_def_to_spec(
    match_name: str,
    param_def: dict[str, Any],
) -> PropSpec:
    """Convert an effect parameter definition dict into a `PropSpec`.

    Args:
        match_name: The property's match name.
        param_def: The parameter definition dict from parT parsing.

    Returns:
        A `PropSpec` suitable for `Property._new()`.
    """
    pvt = param_def.get("property_value_type", PropertyValueType.OneD)
    control_type = param_def["property_control_type"]
    is_color = control_type == PropertyControlType.COLOR
    dims = _PVT_DIMENSIONS.get(pvt, 1)
    is_spatial = (
        pvt in (PropertyValueType.TwoD_SPATIAL, PropertyValueType.ThreeD_SPATIAL)
        or is_color
    )
    value, default_value = _resolve_effect_value(match_name, param_def, control_type)
    return PropSpec(
        match_name=match_name,
        auto_name=param_def.get("name") or match_name,
        value=value,
        pvt=pvt,
        dimensions=dims,
        is_spatial=is_spatial,
        color=is_color,
        integer=control_type == PropertyControlType.INTEGER,
        default_value=default_value,
        can_vary_over_time=control_type != PropertyControlType.MASK,
    )


def _resolve_effect_value(
    match_name: str,
    param_def: dict[str, Any],
    control_type: PropertyControlType,
) -> tuple[Any, Any]:
    """Resolve value and default_value for a synthesized effect property.

    Returns pre-rescale values - 2D point coordinate scaling from parT's
    0-512 range to pixel coordinates is handled separately by
    `_scale_2d_point`.

    Args:
        match_name: The property's match name.
        param_def: The parameter definition dict from parT parsing.
        control_type: The effect control type.

    Returns:
        A (value, default_value) tuple.
    """
    if control_type == PropertyControlType.ENUM:
        # parT stores 0-indexed default; ExtendScript uses 1-indexed.
        # last_value from parT is already 1-indexed and reflects the
        # current value even when the property is absent from tdgp.
        raw_default = param_def.get("default_value", 0)
        fallback = raw_default + 1
        value = param_def.get("last_value", fallback)
        return value, value
    if control_type == PropertyControlType.BOOLEAN:
        value = param_def.get("default_value", param_def.get("last_value"))
        return value, value
    # General case: last_value > default_value > override table > pard
    # default.
    value = param_def.get("last_value")
    if value is None:
        value = param_def.get("default_value")
    if value is None:
        value = _PROPERTY_DEFAULTS.get(match_name)
    if value is None:
        value = param_def.get("default")
    default_value: Any = param_def.get("default_value")
    if default_value is None:
        default_value = value
    return value, default_value


def _apply_param_def_metadata(
    prop: Property,
    param_def: dict[str, Any],
) -> None:
    """Apply parameter definition metadata to a property.

    Sets last_value, min/max bounds, nb_options, and
    property_parameters from the parameter definition dict.  Shared by
    `_synthesize_effect_property` and `_merge_param_def`.

    Args:
        prop: The property to update in place.
        param_def: The parameter definition dict.
    """
    prop.last_value = param_def.get("last_value")
    min_val = param_def.get("min_value")
    if min_val is not None:
        prop._min_value_fallback = min_val
    max_val = param_def.get("max_value")
    if max_val is not None:
        prop._max_value_fallback = max_val
    # The pard UI slider range - distinct from the valid range and the
    # source of an Essential Graphics slider controller's Smin/Smax.
    prop._slider_min = param_def.get("slider_min")
    prop._slider_max = param_def.get("slider_max")
    prop.nb_options = param_def.get("nb_options")
    # Direct write: the public setter has user-write semantics (validation
    # plus pdnm/pard chunk rewrites).
    prop._property_parameters = param_def.get("property_parameters")
    units = param_def.get("units_text")
    if units is not None:
        prop._units_text = units
    # The pard param flags carry the authoritative can-vary bit; the
    # residue table keeps the rare params where they disagree with
    # ExtendScript (e.g. the Puppet Engine dropdown).
    can_vary = param_def.get("can_vary_over_time")
    if can_vary is not None and prop.match_name not in _CANVARY_OVERRIDES:
        prop._can_vary_over_time = can_vary
    if param_def.get("expressions_disabled"):
        prop._expressions_disabled = True


def _scale_2d_point(prop: Property, width: int, height: int) -> None:
    """Scale a synthesized 2D point from parT's 0-512 range to pixel coordinates.

    parT stores 2D point defaults in a normalized 0-512 range.  This
    converts both value and default_value to composition pixel coordinates
    so they match parsed (cdat-backed) values.

    Args:
        prop: A 2D point Property whose value/default_value are in 0-512 range.
        width: The composition width in pixels.
        height: The composition height in pixels.
    """
    if isinstance(prop._value, list) and len(prop._value) >= 2:
        prop._value = [
            prop._value[0] / 512.0 * width,
            prop._value[1] / 512.0 * height,
        ]
    if isinstance(prop.default_value, list) and len(prop.default_value) >= 2:
        prop.default_value = [
            prop.default_value[0] / 512.0 * width,
            prop.default_value[1] / 512.0 * height,
        ]


def parse_effect_param_defs(
    sspc_child_chunks: list[Chunk],
) -> dict[str, dict[str, Any]]:
    """Parse effect parameter definitions from parT chunk.

    Each effect has a parT LIST containing parameter definitions that
    describe the control type, default values, and ranges.

    Args:
        sspc_child_chunks: The SSPC chunk's child chunks.

    Returns:
        Dict mapping parameter match names to definition dicts.
    """
    part_chunk = find_by_list_type(chunks=sspc_child_chunks, list_type="parT")
    param_defs: dict[str, dict[str, Any]] = {}

    chunks_by_parameter = get_chunks_by_match_name(part_chunk)
    for index, (match_name, parameter_chunks) in enumerate(chunks_by_parameter.items()):
        # Skip first, it describes parent
        if index == 0:
            continue
        param_defs[match_name] = _parse_effect_parameter_def(parameter_chunks)

    return param_defs


def _merge_param_def(prop: Property, param_def: dict[str, Any]) -> None:
    """Merge parameter definition values into a parsed property.

    Overrides auto-detected property attributes with the more precise
    values from the effect's parameter definition.

    Args:
        prop: The property to update in place.
        param_def: The parameter definition dict.
    """
    prop._auto_name = param_def["name"] or prop._auto_name
    prop._property_control_type = param_def["property_control_type"]
    prop._property_value_type = param_def.get(
        "property_value_type", prop.property_value_type
    )
    # Prefer the override table, then the pard default field. For LAYER
    # references, pard stores a meaningless 0 and we have no static
    # override, so leave default_value unset entirely.
    static_default = _PROPERTY_DEFAULTS.get(prop.match_name)
    if static_default is None:
        static_default = param_def.get("default")
    if static_default is not None:
        prop.default_value = static_default
    elif param_def["property_control_type"] != PropertyControlType.LAYER:
        prop.default_value = param_def.get("default_value")
    _apply_param_def_metadata(prop, param_def)


def _synthesize_effect_property(
    match_name: str,
    param_def: dict[str, Any],
    property_depth: int,
    *,
    parent_property: PropertyGroup,
) -> Property | PropertyGroup:
    """Create a default Property from an effect parameter definition.

    When effect parameters are at their default value, AE omits them from
    the binary tdgp chunk.  This function builds a Property (or, for group
    separators, a PropertyGroup) from the parT definition so the parsed
    output matches what ExtendScript reports.

    Args:
        match_name: The property's match name.
        param_def: The parameter definition dict from parT parsing.
        property_depth: The nesting depth for this property.
        parent_property: The effect group that owns the synthesized child.

    Returns:
        A Property or PropertyGroup with default values.
    """
    control_type = param_def["property_control_type"]
    pvt = param_def.get("property_value_type", PropertyValueType.OneD)

    if pvt == PropertyValueType.NO_VALUE:
        raw_display = param_def.get("name")
        display = (
            raw_display
            if isinstance(raw_display, str) and raw_display
            else MATCH_NAME_TO_AUTO_NAME.get(match_name, "")
        )
        return PropertyGroup._new(
            match_name,
            display,
            property_depth,
            parent_property=parent_property,
            synthetic=True,
        )

    spec = _param_def_to_spec(match_name, param_def)
    prop = Property._new(
        spec,
        property_depth,
        parent_property=parent_property,
        control_type=control_type,
        synthetic=True,
    )
    _apply_param_def_metadata(prop, param_def)
    return prop


def _parse_effect_properties(
    tdgp_chunk: ListChunk,
    param_defs: dict[str, dict[str, Any]],
    child_depth: int,
    composition: CompItem,
    parent_property: PropertyGroup,
    group_match_name: str = "",
) -> list[Property | PropertyGroup]:
    """Parse effect properties and merge with parameter definitions.

    Walks `param_defs` in canonical order, merging parsed binary
    properties or synthesizing missing ones in a single pass.  Tail
    children not in `param_defs` (e.g. Compositing Options) are appended
    in their original parsed order.

    Args:
        tdgp_chunk: The tdgp chunk containing property data.
        param_defs: Parameter definitions to merge into properties.
        child_depth: The property depth for parsed child properties.
        composition: The parent composition.
        parent_property: The effect group that owns the parsed children.

    Returns:
        List of parsed and merged properties.
    """
    from .property import parse_properties

    # Skip index-0 internal parameters (not exposed in ExtendScript).
    property_runs = [
        (name, chunks)
        for name, chunks in get_match_name_runs(tdgp_chunk)
        if not name.endswith("-0000")
    ]

    parsed = parse_properties(
        match_name_runs=property_runs,
        child_depth=child_depth,
        effect_param_defs={},
        composition=composition,
    )

    # Index parsed children by match_name for O(1) lookup.
    parsed_by_mn: dict[str, Property | PropertyGroup] = {
        p.match_name: p for p in parsed
    }

    # Single ordered walk over param_defs: merge existing or synthesize
    # missing, producing children in canonical parT order.
    ordered: list[Property | PropertyGroup] = []
    for match_name, param_def in param_defs.items():
        existing = parsed_by_mn.get(match_name)
        if existing is not None:
            if isinstance(existing, Property):
                _merge_param_def(existing, param_def)
            ordered.append(existing)
        elif match_name == "ADBE Force CPU GPU":
            # Belongs inside ADBE Effect Built In Params, not here.
            continue
        else:
            synth = _synthesize_effect_property(
                match_name,
                param_def,
                child_depth,
                parent_property=parent_property,
            )
            if (
                isinstance(synth, Property)
                and synth._property_control_type == PropertyControlType.TWO_D
            ):
                _scale_2d_point(synth, composition.width, composition.height)
            ordered.append(synth)

    # Append tail children not in param_defs (e.g. ADBE Effect Built In
    # Params) in their original parsed order.
    for child in parsed:
        if child.match_name not in param_defs:
            ordered.append(child)

    # Synthesize Compositing Options group when absent from the binary.
    # synthesize_children() will fill it from _COMPOSITING_OPTIONS_SPECS.
    if not any(c.match_name == "ADBE Effect Built In Params" for c in ordered):
        ordered.append(
            PropertyGroup._new(
                "ADBE Effect Built In Params",
                "Compositing Options",
                child_depth,
                parent_property=parent_property,
                synthetic=True,
            )
        )

    return ordered


@_suppress_materialization()
def parse_effect(
    sspc_chunk: ListChunk,
    group_match_name: str,
    property_depth: int,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
    composition: CompItem,
    tdmn: TdmnChunk,
) -> PropertyGroup:
    """
    Parse an effect.

    Args:
        sspc_chunk: The SSPC chunk to parse.
        group_match_name: A special name for the property used to build unique
            naming paths. The match name is not displayed, but you can refer
            to it in scripts. Every property has a unique match-name
            identifier. Match names are stable from version to version
            regardless of the display name (the name attribute value) or any
            changes to the application. Unlike the display name, it is not
            localized. An indexed group (`PropertyBase.property_type ==
            PropertyType.indexed_group`) may not have a name value, but
            always has a match_name value.
        property_depth: The nesting depth of this group (0 = layer level).
        effect_param_defs: Project-level effect parameter definitions, used as
            fallback when layer-level parT chunks are missing.
        composition: The parent composition.
    """
    sspc_child_chunks = sspc_chunk.chunks
    fnam_chunk = cast(
        "ContainerChunk", find_by_type(chunks=sspc_child_chunks, chunk_type="fnam")
    )

    # fnam is a ContainerChunk with a Utf8 child
    fnam_utf8 = cast(
        "Utf8Chunk", find_by_type(chunks=fnam_chunk.chunks, chunk_type="Utf8")
    )
    tdgp_chunk = find_by_list_type(chunks=sspc_child_chunks, list_type="tdgp")

    try:
        param_defs = parse_effect_param_defs(sspc_child_chunks)
    except ChunkNotFoundError:
        param_defs = {}

    # Layer-level sspc may have an empty parT when the same effect type
    # is used more than once (AE doesn't duplicate the data).  Fall back
    # to previously cached or project-level EfdG definitions.
    if not param_defs and group_match_name in effect_param_defs:
        param_defs = effect_param_defs[group_match_name]

    # Cache successful parT parsing so later instances of the same
    # effect can reuse the definitions.
    if param_defs and group_match_name not in effect_param_defs:
        effect_param_defs[group_match_name] = param_defs
    # Resolve _name_utf8 from the effect tdgp's tdsn child
    tdsn = cast("TdsnChunk", find_by_type(chunks=tdgp_chunk.chunks, chunk_type="tdsn"))
    effect_name_utf8 = tdsn.utf8

    try:
        effect_tdsb = cast(
            "TdsbChunk", find_by_type(chunks=tdgp_chunk.chunks, chunk_type="tdsb")
        )
    except ChunkNotFoundError:
        effect_tdsb = None

    effect_group = PropertyGroup(
        _tdmn=tdmn,
        _tdgp=tdgp_chunk,
        _tdsb=effect_tdsb,
        _name_utf8=effect_name_utf8,
        _fnam_utf8=fnam_utf8,
        match_name=group_match_name,
        property_depth=property_depth,
        properties=[],
    )
    effect_group._is_effect = True
    effect_group._property_type = PropertyType.INDEXED_GROUP

    properties = _parse_effect_properties(
        tdgp_chunk,
        param_defs,
        child_depth=property_depth + 1,
        composition=composition,
        parent_property=effect_group,
        group_match_name=group_match_name,
    )
    effect_group._properties = properties
    for child in properties:
        child._parent_property = effect_group

    return effect_group


_PARD_EXTRACTORS: dict[PropertyControlType, Callable[[Any, dict[str, Any]], None]] = {}


def _pard_extractor(
    *control_types: PropertyControlType,
) -> Callable[
    [Callable[[Any, dict[str, Any]], None]],
    Callable[[Any, dict[str, Any]], None],
]:
    """Register a pard field extractor for the given control type(s)."""

    def decorator(
        func: Callable[[Any, dict[str, Any]], None],
    ) -> Callable[[Any, dict[str, Any]], None]:
        for ct in control_types:
            _PARD_EXTRACTORS[ct] = func
        return func

    return decorator


@_pard_extractor(PropertyControlType.ANGLE)
def _extract_angle(body: Any, result: dict[str, Any]) -> None:
    result["last_value"] = body.last_value
    if body.default is not None:
        result["default"] = _intify(body.default)
    result["property_value_type"] = PropertyValueType.OneD


@_pard_extractor(PropertyControlType.BOOLEAN)
def _extract_boolean(body: Any, result: dict[str, Any]) -> None:
    result["last_value"] = body.last_value
    result["default_value"] = body.default
    result["min_value"] = 0
    result["max_value"] = 1


@_pard_extractor(PropertyControlType.COLOR)
def _extract_color(body: Any, result: dict[str, Any]) -> None:
    # pard stores colors as [A, R, G, B] in 0-255 range;
    # ExtendScript uses [R, G, B, A] in 0-1 range.
    a, r, g, b = body.last_color
    result["last_value"] = [r / 255.0, g / 255.0, b / 255.0, a / 255.0]
    a, r, g, b = body.default_color
    result["default_value"] = [r / 255.0, g / 255.0, b / 255.0, a / 255.0]
    result["min_value"] = -3921568.62745098
    result["max_value"] = 3921568.62745098
    result["property_value_type"] = PropertyValueType.COLOR


@_pard_extractor(PropertyControlType.ENUM)
def _extract_enum(body: Any, result: dict[str, Any]) -> None:
    result["last_value"] = body.last_value
    # nb_options is stored with the count in the high 16 bits
    nb_options = body.nb_options >> 16
    result["nb_options"] = nb_options
    result["default_value"] = body.default
    result["min_value"] = 1
    result["max_value"] = nb_options


def _intify(value: float) -> int | float:
    """Return integral floats as int, matching ExtendScript output."""
    return int(value) if float(value).is_integer() else value


@_pard_extractor(PropertyControlType.INTEGER)
def _extract_integer(body: Any, result: dict[str, Any]) -> None:
    if body.default is not None:
        result["default"] = body.default
    result["min_value"] = body.valid_min
    result["max_value"] = body.valid_max


@_pard_extractor(PropertyControlType.SCALAR)
def _extract_scalar(body: Any, result: dict[str, Any]) -> None:
    result["last_value"] = body.last_value
    if body.default is not None:
        result["default"] = _intify(body.default)
    result["min_value"] = _intify(body.valid_min)
    result["max_value"] = _intify(body.valid_max)
    result["slider_min"] = body.slider_min
    result["slider_max"] = body.slider_max


@_pard_extractor(PropertyControlType.SLIDER)
def _extract_slider(body: Any, result: dict[str, Any]) -> None:
    result["last_value"] = body.last_value
    if body.default is not None and math.isfinite(body.default):
        result["default"] = _intify(body.default)
    # Non-finite bounds mean the side is unbounded.
    if math.isfinite(body.valid_min):
        result["min_value"] = _intify(body.valid_min)
    if math.isfinite(body.valid_max):
        result["max_value"] = _intify(body.valid_max)
    if math.isfinite(body.slider_min):
        result["slider_min"] = body.slider_min
    if math.isfinite(body.slider_max):
        result["slider_max"] = body.slider_max
    # PF_ValueDisplayFlag_PERCENT is the only display flag AE serializes
    # reliably for float sliders; it maps to unitsText "percent".
    if body.displays_percent:
        result["units_text"] = "percent"


@_pard_extractor(PropertyControlType.THREE_D)
def _extract_three_d(body: Any, result: dict[str, Any]) -> None:
    result["last_value"] = [body.last_value_x, body.last_value_y, body.last_value_z]
    result["property_value_type"] = PropertyValueType.ThreeD_SPATIAL


@_pard_extractor(PropertyControlType.TWO_D)
def _extract_two_d(body: Any, result: dict[str, Any]) -> None:
    result["last_value"] = [body.last_value_x, body.last_value_y]
    result["property_value_type"] = PropertyValueType.TwoD_SPATIAL


@_pard_extractor(PropertyControlType.LAYER)
def _extract_layer(body: Any, result: dict[str, Any]) -> None:
    result["property_value_type"] = PropertyValueType.LAYER_INDEX
    result["default_value"] = 0


@_pard_extractor(PropertyControlType.MASK)
def _extract_mask(body: Any, result: dict[str, Any]) -> None:
    result["property_value_type"] = PropertyValueType.MASK_INDEX
    result["default_value"] = 0


@_pard_extractor(PropertyControlType.CURVE)
def _extract_curve(body: Any, result: dict[str, Any]) -> None:
    result["property_value_type"] = PropertyValueType.CUSTOM_VALUE


@_pard_extractor(
    PropertyControlType.GROUP,
    PropertyControlType.UNKNOWN,
    PropertyControlType.UNKNOWN_14,
    PropertyControlType.PAINT_GROUP,
)
def _extract_no_value(body: Any, result: dict[str, Any]) -> None:
    result["property_value_type"] = PropertyValueType.NO_VALUE


def _parse_effect_parameter_def(parameter_chunks: list[Chunk]) -> dict[str, Any]:
    """Parse effect parameter definition from pard chunk, returning a dict of values."""
    pard_chunk = cast(
        "PardChunk", find_by_type(chunks=parameter_chunks, chunk_type="pard")
    )

    control_type = PropertyControlType(pard_chunk.property_control_type)

    result: dict[str, Any] = {
        "name": pard_chunk.name,
        "property_control_type": control_type,
        # PF param flags bit 1 = CANNOT_TIME_VARY (the tdb4 byte is
        # unreliable for effect parameters).
        "can_vary_over_time": not (pard_chunk.param_flags & 0x02),
        "expressions_disabled": pard_chunk.expressions_disabled,
    }

    extractor = _PARD_EXTRACTORS.get(control_type)
    if extractor is not None:
        extractor(pard_chunk, result)

    try:
        pdnm_chunk = cast(
            "ContainerChunk", find_by_type(chunks=parameter_chunks, chunk_type="pdnm")
        )
        # pdnm is a ContainerChunk with a Utf8 child
        utf8_chunk = cast(
            "Utf8Chunk", find_by_type(chunks=pdnm_chunk.chunks, chunk_type="Utf8")
        )
        pdnm_data = utf8_chunk.value
        if control_type == PropertyControlType.ENUM:
            result["property_parameters"] = pdnm_data.split("|")
        elif pdnm_data:
            result["name"] = pdnm_data
    except ChunkNotFoundError:
        pass

    return result


def parse_effect_definitions(
    root_chunks: list[Chunk],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Parse project-level effect definitions from LIST:EfdG.

    EfdG contains parameter definitions for every effect type used in the
    project. Unlike layer-level sspc chunks, the EfdG definitions always
    include a parT chunk.

    Args:
        root_chunks: The root chunks of the AEP file.

    Returns:
        Dict mapping effect match names to their parameter definitions
        (effect_match_name -> param_match_name -> param_def dict).
    """
    try:
        efdg_chunk = find_by_list_type(chunks=root_chunks, list_type="EfdG")
    except ChunkNotFoundError:
        return {}

    effect_defs: dict[str, dict[str, dict[str, Any]]] = {}
    efdf_chunks = filter_by_list_type(chunks=efdg_chunk.chunks, list_type="EfDf")

    for efdf_chunk in efdf_chunks:
        efdf_child_chunks = efdf_chunk.chunks
        # First tdmn in EfDf contains the effect match name
        tdmn_chunk = find_by_type(chunks=efdf_child_chunks, chunk_type="tdmn")
        effect_match_name = cast("TdmnChunk", tdmn_chunk).value

        sspc_chunk = find_by_list_type(chunks=efdf_child_chunks, list_type="sspc")
        param_defs = parse_effect_param_defs(sspc_chunk.chunks)
        effect_defs[effect_match_name] = param_defs

    return effect_defs


def effect_definition_entries(
    root_chunks: list[Chunk],
) -> list[tuple[str, str, ListChunk]]:
    """All effect definitions in `LIST:EfdG` as `(match_name, display, sspc)`.

    AE stores a complete `LIST:sspc` template (`fnam` + `parT` + value
    `tdgp` + `pgui`) for every effect type used in the project, so any
    such effect can be re-applied by cloning that template. Returns `[]`
    when the project has no `LIST:EfdG`. The walk is project-stable (AE
    never re-reads it after parse), so callers cache the result rather
    than re-walking per lookup.
    """
    try:
        efdg_chunk = find_by_list_type(chunks=root_chunks, list_type="EfdG")
    except ChunkNotFoundError:
        return []

    entries: list[tuple[str, str, ListChunk]] = []
    for efdf_chunk in filter_by_list_type(chunks=efdg_chunk.chunks, list_type="EfDf"):
        match_name = cast(
            "TdmnChunk", find_by_type(chunks=efdf_chunk.chunks, chunk_type="tdmn")
        ).value
        sspc_chunk = find_by_list_type(chunks=efdf_chunk.chunks, list_type="sspc")
        fnam = cast(
            "ContainerChunk", find_by_type(chunks=sspc_chunk.chunks, chunk_type="fnam")
        )
        display = cast(
            "Utf8Chunk", find_by_type(chunks=fnam.chunks, chunk_type="Utf8")
        ).value
        entries.append((match_name, display, sspc_chunk))
    return entries


def match_effect_definition(
    entries: list[tuple[str, str, ListChunk]], name: str
) -> tuple[str, str, ListChunk] | None:
    """Find the definition matching `name` in `entries`.

    `name` is matched against the effect match name across all entries
    first, then against the `fnam` display name.

    Returns:
        `(match_name, display_name, def_sspc)` for the matching
        definition, or `None`.
    """
    for entry in entries:
        if name == entry[0]:
            return entry
    for entry in entries:
        if name == entry[1]:
            return entry
    return None
