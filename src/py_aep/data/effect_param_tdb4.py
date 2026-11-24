"""`tdb4` fields AE writes for a stored effect parameter."""

from __future__ import annotations

from py_aep.enums import PropertyControlType

_STATIC: dict[str, int] = {
    "_spatial_static_flags": 1,
    "_pad2a": 0,
    "_value_hint_type": 0,
    "_value_hint_flag": 0,
    "_cvot_flags": 0,
    "_no_value_flags": 0,
    "_type_flags": 0,
    "_property_category": 0,
    "_reserved_48": 0,
    "_spatial_marker": 0,
}
_NUMERIC: dict[str, int] = {
    **_STATIC,
    "_value_hint_type": 0xFFFF,
    "_value_hint_flag": 0xFF,
    "_cvot_flags": 0xFF,
}

#: The `tdb4` fields After Effects writes for an effect parameter that stores
#: a static value, by control type. Each control type writes one set, across
#: every parameter stored in the AE 2025 and 2026 sample projects and the
#: built-in effect templates, and AE 2026 writes the same when a script sets
#: or keys a parameter of each type. A keyed parameter keeps the set, with the
#: static bit and the spatial marker cleared.
#:
#: Bit 1 of `_spatial_static_flags` is load-bearing. Without it AE ignores the
#: stored value and falls back to the `parT` default, bisected one bit at a
#: time against AE 2026. Bit 0 is `static`, bit 3 `is_spatial`.
EFFECT_PARAM_TDB4: dict[PropertyControlType, dict[str, int]] = {
    PropertyControlType.LAYER: {
        **_STATIC,
        "_value_hint_type": 1,
        "_type_flags": 4,
        "_property_category": 4,
        "_reserved_48": 0x80000000,
    },
    PropertyControlType.INTEGER: {
        **_NUMERIC,
        "_type_flags": 4,
        "_property_category": 4,
    },
    PropertyControlType.SCALAR: {
        **_NUMERIC,
        "_type_flags": 4,
        "_property_category": 6,
    },
    PropertyControlType.ANGLE: {
        **_NUMERIC,
        "_type_flags": 4,
        "_property_category": 6,
    },
    PropertyControlType.BOOLEAN: {
        **_STATIC,
        "_value_hint_type": 1,
        "_cvot_flags": 4,
        "_type_flags": 4,
        "_property_category": 4,
    },
    PropertyControlType.COLOR: {
        **_NUMERIC,
        "_spatial_static_flags": 7,
        "_pad2a": 1,
        "_value_hint_type": 2,
        "_type_flags": 1,
        "_property_category": 1,
        "_spatial_marker": 1,
    },
    PropertyControlType.TWO_D: {
        **_NUMERIC,
        "_spatial_static_flags": 15,
        "_pad2a": 3,
        "_type_flags": 4,
        "_property_category": 6,
        "_spatial_marker": 1,
    },
    PropertyControlType.ENUM: {
        **_STATIC,
        "_value_hint_type": 1,
        "_cvot_flags": 4,
        "_type_flags": 4,
        "_property_category": 4,
    },
    PropertyControlType.SLIDER: {
        **_NUMERIC,
        "_type_flags": 8,
        "_property_category": 9,
    },
    PropertyControlType.CURVE: {
        **_STATIC,
        "_spatial_static_flags": 7,
        "_pad2a": 1,
        "_value_hint_type": 6,
        "_cvot_flags": 7,
        "_no_value_flags": 1,
        "_type_flags": 8,
        "_spatial_marker": 1,
    },
    PropertyControlType.MASK: {
        **_STATIC,
        "_value_hint_type": 1,
        "_type_flags": 4,
        "_property_category": 4,
        "_reserved_48": 0x80000000,
    },
    PropertyControlType.THREE_D: {
        **_NUMERIC,
        "_spatial_static_flags": 15,
        "_pad2a": 3,
        "_type_flags": 8,
        "_property_category": 9,
        "_spatial_marker": 1,
    },
}
