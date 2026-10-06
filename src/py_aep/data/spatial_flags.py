"""`tdb4._spatial_static_flags` values AE writes for effect parameters."""

from __future__ import annotations

from py_aep.enums import PropertyControlType

#: `tdb4._spatial_static_flags` AE writes for an effect parameter that
#: carries a stored value, by control type (measured in AE 2026 by setting
#: one parameter of each type and decoding the result).
#:
#: Bit 0 is `static`, bit 3 `is_spatial`; **bit 1 is load-bearing** - it marks
#: the parameter as holding an instance value. Without it AE ignores the
#: `tdbs` entirely and falls back to the `parT` default, silently discarding
#: the written value (bisected one bit at a time against AE 2026).
#:
#: These differ from a layer's own properties (a spatial one has 9, a
#: colour 6), because only an effect parameter needs the instance-value
#: bits. Removing a property's last keyframe keeps whatever byte it has and
#: only sets the static bit (`tdb4_apply_static_template`).
#:
#: One-dimensional controls (slider, angle, checkbox, enum, ...) keep the
#: chunk default of `1` and are absent from this table.
EFFECT_PARAM_SPATIAL_FLAGS: dict[PropertyControlType, int] = {
    PropertyControlType.COLOR: 0x07,
    PropertyControlType.TWO_D: 0x0F,
    PropertyControlType.THREE_D: 0x0F,
}
