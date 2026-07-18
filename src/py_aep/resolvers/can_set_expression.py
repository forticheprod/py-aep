"""Resolver for `Property.can_set_expression`.

Determines whether an After Effects expression can be set on a given
property.  Rules are derived from sample-based analysis of the AE binary
format, with explicit match-name overrides for known outliers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from py_aep.enums import PropertyControlType, PropertyValueType
from py_aep.models.properties.overrides import (
    _CAMERA_NO_EXPRESSION,
    _CANSETEXPR_2D_ONLY,
    _CANSETEXPR_3D_ONLY,
    _CANSETEXPR_FALSE_OVERRIDES,
    _CANSETEXPR_TRUE_OVERRIDES,
    _LIGHT_AMBIENT_NO_EXPRESSION,
    _LIGHT_NO_EXPRESSION,
    _LIGHT_PARALLEL_NO_EXPRESSION,
    _LIGHT_POINT_NO_EXPRESSION,
    _LIGHT_SPOT_NO_EXPRESSION,
    _PARAMETRIC_MESH_CHECKBOX_STREAMS,
    _PARAMETRIC_MESH_EXPRESSION_OK,
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
        PropertyValueType.LAYER_INDEX,
        PropertyValueType.CUSTOM_VALUE,
    }
)

# Effect properties matching one of these (control_type, vector, spatial,
# integer) tuples are non-expressionable unless explicitly listed in
# _CANSETEXPR_TRUE_OVERRIDES.
#
# Derived from sample analysis: within effects, these tdb4 flag
# combinations correspond to UI controls (integer sliders, boolean
# toggles, color pickers, 2D/3D point controls) that AE does not allow
# expressions on.
_EFFECT_NON_EXPRESSIONABLE: frozenset[tuple[int, bool, bool, bool]] = frozenset(
    {
        (PropertyControlType.SCALAR, False, False, True),  # integer sliders
        (PropertyControlType.BOOLEAN, False, False, True),  # boolean toggles
        (PropertyControlType.COLOR, False, False, False),  # color pickers
        (PropertyControlType.TWO_D, False, True, True),  # integer 2D points
        (PropertyControlType.THREE_D, True, True, False),  # 3D position controls
    }
)


def resolve_can_set_expression(prop: Property) -> bool:
    """Compute `can_set_expression` for a property.

    Args:
        prop: The property to evaluate.

    Returns:
        Whether an expression can be set on this property.
    """
    mn = prop.match_name

    if prop.is_separation_follower:
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

    if mn in _CANSETEXPR_TRUE_OVERRIDES:
        return True

    # Effect parameters whose pard definition disables expressions.
    if prop._expressions_disabled:
        return False

    if pvt in _PVT_ALWAYS_FALSE:
        return False

    # Non-expressionable effect signatures - a small set of
    # (control_type, vector, spatial, integer) flag combinations.
    if prop._is_in_effect() and not prop.is_dropdown_effect:
        key = (
            prop.property_control_type,
            bool(prop._vector),
            bool(prop._is_spatial_raw),
            bool(prop._integer),
        )
        if key in _EFFECT_NON_EXPRESSIONABLE:
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

    # AV/Text/Shape/3DModel: 3D-dependent properties
    if mn in _CANSETEXPR_3D_ONLY:
        return bool(layer._ldta.three_d_layer)

    # Properties expressionable only on 2D layers
    if mn in _CANSETEXPR_2D_ONLY:
        return layer.null_layer or not bool(layer._ldta.three_d_layer)

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
    # POINT (2) / ENVIRONMENT (4)
    return mn not in _LIGHT_POINT_NO_EXPRESSION


def _can_set_expression_parametric_mesh(
    prop: Property, layer: Any, mn: str
) -> bool | None:
    """Determine can_set_expression for a property on a parametric mesh layer.

    Returns a bool for mesh-specific rules, or `None` to fall through to
    the generic (layer-type-agnostic) resolution. Rules verified against
    AE 2026 ExtendScript (parametric_meshes.json):

    * A fixed set of streams is never expressionable (`Light Transmission`,
      `Displacement Intensity`, the material texture-projection params).
    * `Shadow Color` and the Plane geometry streams are always expressionable.
    * Mesh-option / bevel streams are expressionable only when they belong
      to the layer's ACTIVE mesh type; checkbox toggles (caps / invert
      slice) are expressionable regardless of active type.
    """
    if mn in _PARAMETRIC_MESH_NO_EXPRESSION:
        return False
    if mn in _PARAMETRIC_MESH_EXPRESSION_OK:
        return True
    parent = prop.parent_property
    group_mn = parent.match_name if parent is not None else ""
    group_type = _PARAMETRIC_MESH_GROUP_TYPE.get(group_mn)
    if group_type is not None:
        if mn in _PARAMETRIC_MESH_CHECKBOX_STREAMS:
            return True
        return bool(group_type == layer._ldta.light_and_mesh_type)
    return None
