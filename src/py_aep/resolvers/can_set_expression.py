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

    if mn in _CANSETEXPR_FALSE_OVERRIDES:
        return False

    layer = prop._containing_layer
    layer_type = layer._ldta.layer_type

    # Camera layers cannot set expressions on Scale/Opacity
    if layer_type == 2:
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
    light_type = layer._ldta.light_type
    if light_type == 3:  # AMBIENT
        return mn not in _LIGHT_AMBIENT_NO_EXPRESSION
    if light_type == 1:  # SPOT
        return mn not in _LIGHT_SPOT_NO_EXPRESSION
    if light_type == 0:  # PARALLEL
        return mn not in _LIGHT_PARALLEL_NO_EXPRESSION
    # POINT (2) / ENVIRONMENT (4)
    return mn not in _LIGHT_POINT_NO_EXPRESSION
