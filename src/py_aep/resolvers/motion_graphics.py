"""Build Essential Graphics (Motion Graphics template) controllers from a
source property or layer.

The read side (parsing controllers) lives in `parsers/essential_graphics.py`
and `resolvers/essential_properties.py`. This module is the write side: it
classifies a property into an Essential Graphics controller type, builds the
root-to-leaf source-property path, and decides whether a property or layer can
be exposed - shared by `Property`/`AVLayer.add_to_motion_graphics_template`.

Path shape (the CPrp JSON): each node is `{"index", "matchName"}`. AE resolves
named groups by name (index `0xFFFFFFFF`) and indexed-group children by index.
The index model, verified against AE 2026 output (the `essential_graphics`
fixtures plus a headless run covering masks, shape contents, text animators
and effect topic groups):

- a child of an INDEXED group is its 0-based position among that group's
  children: a mask atom in the Mask Parade, a shape group in Root Vectors, a
  fill in a nested Vectors Group, a text animator in Text Animators, and an
  effect in the Effect Parade all follow this rule;
- an effect PARAM leaf is the exception: its index is the position in the
  effect's flat `parT` parameter list, where the hidden parameter-group
  header pard occupies slot 0, so visible params start at 1
  (`ADBE Fill-0002` -> 3 after `-0001`/`-0007`; `ADBE Fractal Noise-0010`
  -> 10). Effect TOPIC groups (e.g. Fractal Noise's "Transform") are pure
  UI: both AE's DOM and py_aep keep the params flat, and the stored path
  never contains a topic-group node;
- every other node resolves by name.

py_aep refuses (reports "not addable") only what it cannot produce
faithfully: an effect param whose parT definitions are unavailable, children
of `ADBE Effect Built In Params`, and by-name nodes whose match name is
ambiguous among siblings - matching how `can_import_as` gates on what py_aep
can actually produce rather than on what After Effects allows.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, NamedTuple

from ..enums.general import PropertyType
from ..enums.property import PropertyControlType, PropertyValueType

if TYPE_CHECKING:
    from ..models.items.composition import CompItem
    from ..models.layers.av_layer import AVLayer
    from ..models.layers.layer import Layer
    from ..models.properties.property import Property
    from ..models.properties.property_group import PropertyGroup

# AE stores this in a CPrp path node's index to mean "match by name".
_BY_NAME_INDEX = 0xFFFFFFFF

_TEXT_DOCUMENT = "ADBE Text Document"

# Essential Graphics controller type ids (see EssentialGraphicsController).
CONTROLLER_CHECKBOX = 1
CONTROLLER_SLIDER = 2
CONTROLLER_COLOR = 4
CONTROLLER_TEXT = 6


def _owning_layer(prop: Property) -> Layer | None:
    """Return the `Layer` that owns `prop`, or `None` if not layer-owned."""
    from ..models.layers.layer import Layer  # noqa: PLC0415

    group = prop.parent_property
    while group is not None:
        if isinstance(group, Layer):
            return group
        group = group.parent_property
    return None


class PathNode(NamedTuple):
    """One CPrp path node: a match name plus AE's child index.

    `prop_index` is `None` for by-name resolution (serialized as
    `0xFFFFFFFF`); an int is AE's hidden-param-aware child index (see the
    module docstring). Named `prop_index`, not `index`, to avoid shadowing
    `tuple.index` - mirroring `SourcePropertyRef`.
    """

    match_name: str
    prop_index: int | None


def _effect_param_index(layer: Layer, effect_mn: str, param_mn: str) -> int | None:
    """AE's parT index of `param_mn` inside effect `effect_mn`, or `None`.

    The project-level param defs preserve parT order and exclude the hidden
    parameter-group header pard (slot 0), so the AE index is `1 + position`
    (verified across the essential_graphics fixtures: `ADBE Fill-0002` -> 3,
    every `* Control-0001` -> 1).
    """
    defs = layer.containing_comp._project._effect_param_defs.get(effect_mn)
    if not defs:
        return None
    keys = list(defs)
    if param_mn not in keys:
        return None
    return 1 + keys.index(param_mn)


def _effect_param_path(prop: Property) -> tuple[list[PathNode], Layer] | None:
    """Path for a param sitting DIRECTLY inside an effect, or `None`.

    The effect node carries its 0-based Effect Parade position, the leaf its
    parT index; the parade itself resolves by name. Duplicate effect
    instances are fine - the index disambiguates them.
    """
    from ..models.layers.layer import Layer  # noqa: PLC0415

    effect = prop.parent_property
    if effect is None or not effect.is_effect:
        return None
    parade = effect.parent_property
    if parade is None or parade.match_name != "ADBE Effect Parade":
        return None
    layer = parade.parent_property
    if not isinstance(layer, Layer):
        return None
    effect_index = next(
        (i for i, e in enumerate(parade.properties) if e is effect), None
    )
    if effect_index is None:
        return None
    leaf_index = _effect_param_index(layer, effect.match_name, prop.match_name)
    if leaf_index is None:
        return None
    return (
        [
            PathNode("ADBE Effect Parade", None),
            PathNode(effect.match_name, effect_index),
            PathNode(prop.match_name, leaf_index),
        ],
        layer,
    )


def _source_property_path(prop: Property) -> tuple[list[PathNode], Layer] | None:
    """Build the root-to-leaf CPrp path from `prop`'s layer to `prop`.

    Returns `(nodes, layer)` where `nodes` runs from the layer's top-level
    group down to `prop`. Per the AE index model (validated against AE 2026
    output for masks, shape contents, text animators and effects):

    - a child of an INDEXED group carries its 0-based position among that
      group's children (a mask in the Mask Parade, a shape group in Root
      Vectors, a fill in a Vectors Group, an animator in Text Animators);
    - an effect param carries its parT slot instead (hidden header at 0,
      see `_effect_param_path`), so effect subtrees resolve only through
      that dedicated branch;
    - every other node resolves by name, refused when the match name is
      not unique among its siblings (defensive: named groups have unique
      children by AE construction, but a written by-name path must be
      provably unambiguous).

    `None` when `prop` is not owned by a layer, an effect node cannot be
    indexed, or a by-name node is ambiguous.
    """
    from ..models.layers.layer import Layer  # noqa: PLC0415

    effect_path = _effect_param_path(prop)
    if effect_path is not None:
        return effect_path

    chain: list[PathNode] = []
    node: Property | PropertyGroup = prop
    parent = prop.parent_property
    while parent is not None and not isinstance(parent, Layer):
        if parent.is_effect or parent.match_name == "ADBE Effect Parade":
            # Effect subtrees are handled by _effect_param_path only; a
            # positional index here would miss the hidden header pard.
            return None
        if parent.property_type == PropertyType.INDEXED_GROUP:
            idx = next((i for i, c in enumerate(parent.properties) if c is node), None)
            if idx is None:
                return None
            chain.append(PathNode(node.match_name, idx))
        else:
            if (
                sum(1 for c in parent.properties if c.match_name == node.match_name)
                != 1
            ):
                return None
            chain.append(PathNode(node.match_name, None))
        node = parent
        parent = parent.parent_property
    if not isinstance(parent, Layer):
        return None
    # The layer's top-level group resolves by name too.
    if sum(1 for c in parent.properties if c.match_name == node.match_name) != 1:
        return None
    chain.append(PathNode(node.match_name, None))
    return list(reversed(chain)), parent


def _path_json(nodes: list[PathNode]) -> str:
    """Serialize a CPrp path into AE's JSON (by-name nodes as `0xFFFFFFFF`)."""
    body = {
        str(i): {
            "index": (
                node.prop_index if node.prop_index is not None else _BY_NAME_INDEX
            ),
            "matchName": node.match_name,
        }
        for i, node in enumerate(nodes)
    }
    return json.dumps(body, separators=(",", ":"))


def classify_property(prop: Property) -> int | None:
    """Return the Essential Graphics controller type for `prop`, or `None`.

    Supported (per the AE Scripting Guide): Checkbox, Color, single-value
    numeric Slider, and Source Text. Classified on `property_value_type`
    (the control type is `UNKNOWN` for many transform properties, e.g.
    Opacity), with the Checkbox control type distinguishing a boolean from a
    plain numeric slider (both are 1-D value types).
    """
    if prop.match_name == _TEXT_DOCUMENT:
        return CONTROLLER_TEXT
    if prop.property_value_type == PropertyValueType.COLOR:
        return CONTROLLER_COLOR
    if prop.property_control_type == PropertyControlType.BOOLEAN:
        return CONTROLLER_CHECKBOX
    if prop.property_control_type == PropertyControlType.ENUM:
        # Dropdown params are 1-D but AE exposes them as a type-13 Dropdown
        # controller (menu entries included), which py_aep does not build.
        return None
    if prop.property_value_type == PropertyValueType.OneD:
        return CONTROLLER_SLIDER
    return None


def _already_added(comp: CompItem, layer_id: int, nodes: list[PathNode]) -> bool:
    """`True` if `comp` already exposes the same layer property.

    Compares `(match_name, index)` pairs so two instances of the same effect
    (identical match names, different parade indices) stay independently
    addable.
    """
    wanted = [(node.match_name, node.prop_index) for node in nodes]
    for ctrl in comp.motion_graphics_controllers:
        if ctrl.source_layer_id != layer_id:
            continue
        stored = [(ref.match_name, ref.prop_index) for ref in ctrl.source_property_path]
        if stored == wanted:
            return True
    return False


class PropertyControllerPlan(NamedTuple):
    """Everything `CompItem` needs to add a property controller."""

    controller_type: int
    nodes: list[PathNode]
    path_json: str
    layer: Layer


def property_controller_plan(
    prop: Property, comp: CompItem
) -> PropertyControllerPlan | None:
    """Resolve everything needed to add `prop` to `comp`'s EGP, or `None`.

    `None` covers: an unsupported property type, a path py_aep cannot
    serialize (see `_source_property_path`), a layer not in `comp`, or a
    property already exposed.
    """
    controller_type = classify_property(prop)
    if controller_type is None:
        return None
    resolved = _source_property_path(prop)
    if resolved is None:
        return None
    nodes, layer = resolved
    if layer.containing_comp is not comp:
        return None
    if _already_added(comp, layer._ldta.layer_id, nodes):
        return None
    return PropertyControllerPlan(controller_type, nodes, _path_json(nodes), layer)


def can_add_property(prop: Property, comp: CompItem) -> bool:
    """Whether `prop` can be added to `comp`'s Essential Graphics panel."""
    return property_controller_plan(prop, comp) is not None


def font_caps_json(prop: Property) -> str:
    """Build the Source Text controller's font-caps JSON from the property's
    current TextDocument (AE 2025 key order)."""
    from ..models.text.text_document import TextDocument  # noqa: PLC0415

    value = prop.value
    font = ""
    size: int | float = 0
    if isinstance(value, TextDocument):
        font = value.font or ""
        fs = value.font_size
        if fs is not None:
            size = int(fs) if float(fs).is_integer() else fs
    return json.dumps(
        {
            "capPropFontEdit": False,
            "capPropFontFauxStyleEdit": False,
            "capPropFontSizeEdit": False,
            "fontEditValue": font,
            "fontFSAllCapsValue": False,
            "fontFSBoldValue": False,
            "fontFSItalicValue": False,
            "fontFSSmallCapsValue": False,
            "fontSizeEditValue": size,
        },
        separators=(",", ":"),
    )


def media_controller_path() -> tuple[list[PathNode], str]:
    """The fixed CPrp path of a Media Replacement controller.

    AE always targets the layer's `ADBE Layer Source Alternate` leaf (under
    Source Options), both nodes by name.
    """
    nodes = [
        PathNode("ADBE Source Options Group", None),
        PathNode("ADBE Layer Source Alternate", None),
    ]
    return nodes, _path_json(nodes)


def can_add_layer(layer: AVLayer, comp: CompItem) -> bool:
    """Whether `layer` can be added to `comp`'s EGP as a Media Replacement.

    Mirrors the eligibility rules of `AVLayer.canAddToMotionGraphicsTemplate`:
    the layer must be a Media Replacement layer (has video, not an adjustment
    or null layer, source is a footage/comp item that is not a solid), must
    live in `comp`, and must not already be exposed.
    """
    from ..models.items.composition import CompItem as _CompItem  # noqa: PLC0415
    from ..models.items.footage import FootageItem  # noqa: PLC0415
    from ..models.sources.solid import SolidSource  # noqa: PLC0415

    if layer.containing_comp is not comp:
        return False
    if not layer.has_video or layer.adjustment_layer or layer.null_layer:
        return False
    source = layer.source
    if isinstance(source, FootageItem):
        if isinstance(source.main_source, SolidSource):
            return False
    elif not isinstance(source, _CompItem):
        return False
    # Only an existing MEDIA controller blocks the layer; property
    # controllers (slider/checkbox/...) on the same layer coexist with a
    # Media Replacement in AE.
    nodes, _ = media_controller_path()
    return not _already_added(comp, layer._ldta.layer_id, nodes)
