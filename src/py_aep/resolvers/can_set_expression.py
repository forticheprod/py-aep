"""Resolver for `Property.can_set_expression`.

After Effects allows an expression on a stream the Timeline shows, whose
value is not empty, that can vary over time, and - for an effect
parameter - whose parameter type is not a layer, a mask reference or a
group. Checked against every ExtendScript `canSetExpression` in the sample
corpus.

What the Timeline hides depends, for a layer property, on the layer's
state (a 3D-only property on a 2D layer, another renderer's material
options, another light type's options), which the `overrides` tables state. For
an effect parameter it depends on the effect's plugin: AE stores that in
the stream's `tdsb`, recomputing it when it opens a project, so a stored
flag is trusted there and a synthesized parameter falls back on its
`PF_PUI_INVISIBLE` flag. Layer properties never read the stored flag: it
would go stale on a py-side edit of the layer (the 3-D switch, the light
type, the comp renderer) and stay stale once saved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from py_aep.enums import PropertyControlType, PropertyValueType
from py_aep.models.properties.overrides import (
    _CAMERA_NO_EXPRESSION,
    _CANSETEXPR_2D_ONLY,
    _CANSETEXPR_3D_ONLY,
    _CANSETEXPR_EXTRUSION_DEPTHS,
    _CANSETEXPR_FALSE_OVERRIDES,
    _CANSETEXPR_RENDERER_3D_ONLY,
    _LIGHT_AMBIENT_NO_EXPRESSION,
    _LIGHT_ENVIRONMENT_NO_EXPRESSION,
    _LIGHT_NO_EXPRESSION,
    _LIGHT_PARALLEL_NO_EXPRESSION,
    _LIGHT_POINT_NO_EXPRESSION,
    _LIGHT_SPOT_NO_EXPRESSION,
    _MODEL_LAYER_HIDDEN_MATERIALS,
    _PARAMETRIC_MESH_CHECKBOX_STREAMS,
    _PARAMETRIC_MESH_GROUP_TYPE,
    _PARAMETRIC_MESH_NO_EXPRESSION,
)

if TYPE_CHECKING:
    from typing import Any

    from py_aep.models.properties.property import Property

# PVT sets where can_set_expression is always True / False regardless
# of other signals.
_PVT_ALWAYS_TRUE: frozenset[int] = frozenset(
    {
        PropertyValueType.TEXT_DOCUMENT,
        PropertyValueType.SHAPE,
    }
)
_PVT_ALWAYS_FALSE: frozenset[int] = frozenset(
    {
        PropertyValueType.NO_VALUE,
        PropertyValueType.MARKER,
    }
)

# Effect parameter types that never take an expression: a layer or mask
# reference, and group markers.
_NON_EXPRESSION_PARAM_TYPES: frozenset[int] = frozenset(
    {
        PropertyControlType.LAYER,
        PropertyControlType.PAINT_GROUP,
        PropertyControlType.MASK,
        PropertyControlType.GROUP,
        PropertyControlType.UNKNOWN_14,
    }
)

# Hidden, but still expressionable: AE exempts these paint streams.
_HIDDEN_BUT_EXPRESSIONABLE: frozenset[str] = frozenset(
    {"ADBE Paint Transfer Mode", "ADBE Paint Duration"}
)

# `CompItem.renderer` of Classic 3D, which draws a 3D layer as a flat plane.
_CLASSIC_3D = "ADBE Advanced 3d"

# Shape stroke Line Join value for a miter join.
_MITER_JOIN = 1


def resolve_can_set_expression(prop: Property) -> bool:
    """Compute `can_set_expression` for a property.

    Args:
        prop: The property to evaluate.

    Returns:
        Whether an expression can be set on this property.
    """
    mn = prop.match_name

    # Separation moves expressibility from the leader to its followers.
    # Measured on AE 2026: unseparated, the leader takes an expression and no
    # follower does; separated, the leader refuses one and X / Y accept, with
    # Z joining them only on a 3D layer.
    if prop.is_separation_follower:
        leader = prop.separation_leader
        if leader is None or not leader.dimensions_separated:
            return False
        if prop.separation_dimension == 2:
            return prop._containing_layer.is_3d
        return True
    if prop.is_separation_leader and prop.dimensions_separated:
        return False

    # An UNAPPLIED text-animator pool property cannot have an expression;
    # once applied (materialized in binary) it can, like any property.
    parent = prop.parent_property
    if (
        parent is not None
        and parent.match_name == "ADBE Text Animator Properties"
        and not prop._is_live()
    ):
        return False

    pvt = prop.property_value_type
    if pvt in _PVT_ALWAYS_TRUE:
        return True

    if mn == "ADBE Time Remapping":
        layer = prop._containing_layer
        return bool(getattr(layer, "time_remap_enabled", False))

    if not prop.can_vary_over_time:
        return False

    if pvt in _PVT_ALWAYS_FALSE:
        return False

    if prop._is_in_effect():
        # What the plugin hides: AE's stored flag, then the parameter's
        # PF_PUI_INVISIBLE flag, all a synthesized parameter has.
        tdsb = prop._tdsb
        stored_hidden = tdsb is not None and not tdsb.synthetic and tdsb.hidden
        if stored_hidden and mn not in _HIDDEN_BUT_EXPRESSIONABLE:
            return False
        if prop._expressions_disabled:
            return False
        return prop.property_control_type not in _NON_EXPRESSION_PARAM_TYPES

    if pvt in (PropertyValueType.LAYER_INDEX, PropertyValueType.CUSTOM_VALUE):
        return False

    layer = prop._containing_layer
    layer_type = layer._ldta.layer_type

    # Parametric mesh layers have their own expression rules.
    if layer_type == 7:
        mesh_result = _can_set_expression_parametric_mesh(prop, layer, mn)
        if mesh_result is not None:
            return mesh_result

    if mn in _CANSETEXPR_FALSE_OVERRIDES:
        return False

    # Camera layers cannot set expressions on Scale/Opacity
    if layer_type == 2:
        # Point of Interest (the camera's anchor point) is expressionable
        # only on a two-node camera (orient towards POI); a one-node camera
        # leaves the POI inactive (probed AE 2026). poi_auto_orient is the
        # ldta bit set for the two-node rig.
        if mn == "ADBE Anchor Point":
            return bool(layer._ldta.poi_auto_orient)
        return mn not in _CAMERA_NO_EXPRESSION

    # Light layers have complex rules depending on light type
    if layer_type == 1:
        return _can_set_expression_light(layer, mn)

    three_d = bool(layer._ldta.three_d_layer)
    renderer = layer.containing_comp.renderer

    if (
        layer_type == 5
        and mn in _MODEL_LAYER_HIDDEN_MATERIALS
        and parent is not None
        and parent.match_name == "ADBE Material Options Group"
    ):
        return False

    if mn in _CANSETEXPR_3D_ONLY:
        return three_d

    # A mesh or model layer's own Shadow Color, under Compositing Options,
    # shows under every renderer (probed on AE 2026).
    if (
        mn == "ADBE Shadow Color"
        and parent is not None
        and parent.match_name == "ADBE Compositing Options Group"
    ):
        return True

    only_under = _CANSETEXPR_RENDERER_3D_ONLY.get(mn)
    if only_under is not None:
        return three_d and renderer == only_under

    classic_3d = three_d and renderer == _CLASSIC_3D
    if mn in _CANSETEXPR_2D_ONLY:
        return layer.null_layer or layer_type in (5, 7) or not classic_3d

    if mn in _CANSETEXPR_EXTRUSION_DEPTHS:
        return not (classic_3d and layer_type in (3, 4))

    # AE shows a stroke's miter limit only while it joins by miter.
    if mn == "ADBE Vector Stroke Miter Limit" and parent is not None:
        join = parent.property("ADBE Vector Stroke Line Join")
        return join.value == _MITER_JOIN

    return True


def _can_set_expression_light(layer: Any, mn: str) -> bool:
    """Determine can_set_expression for a property on a light layer."""
    if mn in _LIGHT_NO_EXPRESSION:
        return False
    light_type = layer._ldta.light_and_mesh_type
    if light_type == 3:  # AMBIENT
        return mn not in _LIGHT_AMBIENT_NO_EXPRESSION
    if light_type == 1:  # SPOT
        return mn not in _LIGHT_SPOT_NO_EXPRESSION
    if light_type == 0:  # PARALLEL
        return mn not in _LIGHT_PARALLEL_NO_EXPRESSION
    if light_type == 4:  # ENVIRONMENT
        return mn not in _LIGHT_ENVIRONMENT_NO_EXPRESSION
    return mn not in _LIGHT_POINT_NO_EXPRESSION


def _can_set_expression_parametric_mesh(
    prop: Property, layer: Any, mn: str
) -> bool | None:
    """Determine can_set_expression for a property on a parametric mesh layer.

    Returns a bool for mesh-specific rules, or `None` to fall through to
    the generic (layer-type-agnostic) resolution. Rules verified against
    AE 2026 ExtendScript (parametric_meshes.json):

    * A fixed set of streams is never expressionable (`Displacement
      Intensity`, the material texture-projection params).
    * Mesh-option / bevel streams are expressionable only when they belong
      to the layer's ACTIVE mesh type; checkbox toggles (caps / invert
      slice) are expressionable regardless of active type.
    """
    if mn in _PARAMETRIC_MESH_NO_EXPRESSION:
        return False
    parent = prop.parent_property
    group_mn = parent.match_name if parent is not None else ""
    group_type = _PARAMETRIC_MESH_GROUP_TYPE.get(group_mn)
    if group_type is not None:
        if mn in _PARAMETRIC_MESH_CHECKBOX_STREAMS:
            return True
        return bool(group_type == layer._ldta.light_and_mesh_type)
    return None
