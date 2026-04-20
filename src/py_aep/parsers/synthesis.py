"""Property synthesis - single-pass post-processing for parsed layers.

After binary parsing produces a raw property tree, this module runs one
pass over it to:

* Set `default_value` on transform properties parsed from the binary.
* Synthesize missing transform properties (AE always exposes twelve).
* Reorder top-level layer groups to match the canonical ExtendScript order.
* Synthesize missing children in standard property groups
  (Material Options, Geometry Options, Layer Styles, Mask atoms, etc.).
* Set `min_value` / `max_value` on properties with known bounds.

The single public entry point is `synthesize_layer_properties`, called
once per layer at the end of `parse_layer`.

Note:
    Effect parameter synthesis remains a separate dynamic step inside
    `parse_effect()`, because it relies on binary parT/pard data rather
    than static spec tables.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..enums import PropertyValueType
from ..models.layers.av_layer import AVLayer
from ..models.layers.camera_layer import CameraLayer
from ..models.layers.light_layer import LightLayer
from ..models.layers.shape_layer import ShapeLayer
from ..models.layers.text_layer import TextLayer
from ..models.properties.overrides import _PROPERTY_MIN_MAX
from ..models.properties.property import Property
from ..models.properties.property_group import PropertyGroup, _reorder_and_fill
from ..models.properties.specs import (
    _GROUP_CHILD_SPECS,
    _LAYER_STYLE_CHILD_SPECS,
    _REGULAR_AV_ONLY_GROUPS,
    _SHAPE_ONLY_GROUPS,
    _TEXT_ONLY_GROUPS,
    _TOP_LEVEL_SPECS,
    _TRANSFORM_FIXED_DEFAULTS,
    _TRANSFORM_SPECS,
)

if TYPE_CHECKING:
    from ..models.layers.layer import Layer


# ---------------------------------------------------------------------------
# Recursive child synthesis + bounds application (single pass)
# ---------------------------------------------------------------------------


def _apply_bounds(prop: Property) -> None:
    """Apply min/max override from `_PROPERTY_MIN_MAX` if one exists."""
    bounds = _PROPERTY_MIN_MAX.get(prop.match_name)
    if bounds is not None:
        prop._min_value_fallback = bounds[0]
        prop._max_value_fallback = bounds[1]


def synthesize_children(group: PropertyGroup) -> None:
    """Synthesize missing children and apply min/max bounds in one pass.

    For groups with known canonical children (`_GROUP_CHILD_SPECS`),
    reorders and fills via `_reorder_and_fill`.  For Layer Styles,
    also derives the collapsed `enabled` state.

    After synthesis, applies `_PROPERTY_MIN_MAX` overrides to all leaf
    `Property` children and recurses into child `PropertyGroup` nodes.
    This replaces the former separate `_apply_min_max_bounds` walk.
    """
    specs = _GROUP_CHILD_SPECS.get(group.match_name)
    if specs is not None:
        _reorder_and_fill(group, specs, group.property_depth + 1)
        # Don't return: recurse into preserved sub-groups below.

    if group.match_name == "ADBE Layer Styles":
        _derive_layer_styles_enabled(group)

    for child in group.properties:
        if isinstance(child, PropertyGroup):
            synthesize_children(child)
        elif isinstance(child, Property):
            _apply_bounds(child)


def _derive_layer_styles_enabled(group: PropertyGroup) -> None:
    """Derive the collapsed `enabled` state for Layer Styles.

    ExtendScript reports the Layer Styles group as disabled when no
    individual style is enabled, and Blend Options mirrors the parent.
    """
    any_style_enabled = False
    blend_options: PropertyGroup | None = None
    for child in group.properties:
        if not isinstance(child, PropertyGroup):
            continue
        child_specs = _LAYER_STYLE_CHILD_SPECS.get(child.match_name)
        if child_specs is not None:
            _reorder_and_fill(child, child_specs, child.property_depth + 1)
        # Blend Options mirrors the parent; skip for the check
        if child.match_name == "ADBE Blend Options Group":
            blend_options = child
        elif child.enabled:
            any_style_enabled = True
    # Avoid mutating chunk fields (preserves round-trip)
    group.__dict__["enabled"] = any_style_enabled
    if blend_options is not None:
        blend_options.__dict__["enabled"] = any_style_enabled


# ---------------------------------------------------------------------------
# Top-level group synthesis
# ---------------------------------------------------------------------------


def _synthesize_missing_top_level_groups(layer: Layer) -> None:
    """Add missing top-level property groups expected by ExtendScript.

    ExtendScript always reports a fixed set of top-level property groups
    on every AV layer, even when most are empty.  The binary only stores
    groups that contain data.  This function synthesizes the missing empty
    groups and reorders all groups to match the canonical ExtendScript order.
    """
    if isinstance(layer, (CameraLayer, LightLayer)):
        # Light/Camera layers only need Marker synthesized; all other
        # AVLayer-specific groups are irrelevant.
        skip_groups = frozenset(
            s.match_name for s in _TOP_LEVEL_SPECS if s.match_name != "ADBE Marker"
        )
    elif not isinstance(layer, AVLayer):
        return
    elif isinstance(layer, TextLayer):
        skip_groups = _REGULAR_AV_ONLY_GROUPS | _SHAPE_ONLY_GROUPS
    elif isinstance(layer, ShapeLayer):
        skip_groups = _REGULAR_AV_ONLY_GROUPS | _TEXT_ONLY_GROUPS
    else:
        skip_groups = _TEXT_ONLY_GROUPS | _SHAPE_ONLY_GROUPS

    _reorder_and_fill(layer, _TOP_LEVEL_SPECS, 1, skip=skip_groups, tail_mode="all")

    # Post-processing: Layer Sets elided flag and depth fixup.
    canonical_mns = {s.match_name for s in _TOP_LEVEL_SPECS}
    for child in layer.properties:
        if child.match_name == "ADBE Layer Sets":
            child._elided = True
        if isinstance(child, PropertyGroup) and child.match_name in canonical_mns:
            child._property_depth = 1


# ---------------------------------------------------------------------------
# Transform defaults
# ---------------------------------------------------------------------------


def _set_transform_defaults(layer: Layer) -> None:
    """Assign defaults and synthesize missing transform properties.

    After Effects always exposes twelve transform properties via ExtendScript
    regardless of whether the layer is 2-D or 3-D.  The binary format, however,
    only stores properties relevant to the current layer state.  This function:

    1. Sets `default_value` on every transform property already parsed from
       the binary so that `Property.is_modified` works correctly.
    2. Creates `Property` objects for any of the twelve canonical properties
       that are absent from the binary.
    3. Re-orders `transform.properties` to match the canonical ExtendScript
       order.
    4. Applies context-dependent naming (Rotation vs Z Rotation, Point of
       Interest vs Anchor Point).
    5. Applies min/max bounds on transform leaf properties.

    Spatial defaults (Anchor Point, Position, and the X / Y separated followers)
    depend on layer dimensions and are computed here; all other defaults are
    fixed constants defined in `_TRANSFORM_FIXED_DEFAULTS`.
    """
    transform = layer.transform
    if transform is None:
        return

    # Anchor Point is relative to the layer itself (source dimensions),
    # while Position is relative to the containing composition.
    comp_w = layer.containing_comp.width
    comp_h = layer.containing_comp.height
    if isinstance(layer, AVLayer):
        if isinstance(layer, (TextLayer, ShapeLayer)) or layer.null_layer:
            # Source-less AVLayers: anchor defaults to origin
            anchor_w = 0
            anchor_h = 0
        else:
            anchor_w = layer.width
            anchor_h = layer.height
    else:
        anchor_w = comp_w
        anchor_h = comp_h

    # Spatial defaults depend on layer dimensions.
    spatial_defaults: dict[str, Any] = {
        "ADBE Anchor Point": [anchor_w / 2.0, anchor_h / 2.0, 0.0],
        "ADBE Position": [comp_w / 2.0, comp_h / 2.0, 0.0],
        "ADBE Position_0": comp_w / 2.0,
        "ADBE Position_1": comp_h / 2.0,
    }

    # --- Phase 1: set default_value on properties parsed from binary --------
    existing: dict[str, Property] = {}
    for prop in transform.properties:
        if isinstance(prop, Property):
            existing[prop.match_name] = prop
            # Pad 2D Scale to 3D with Z=100 (ExtendScript always reports 3D)
            if (
                prop.match_name == "ADBE Scale"
                and isinstance(prop._value, list)
                and len(prop._value) == 2
            ):
                prop._value = prop._value + [1.0]
                # Avoid mutating chunk fields
                prop.__dict__["dimensions"] = 3
                prop.__dict__["property_value_type"] = PropertyValueType.ThreeD
                for kf in prop.keyframes:
                    raw = kf._extract_raw_value()
                    if isinstance(raw, list) and len(raw) == 2:
                        kf._value = raw + [1.0]
            if prop.default_value is not None:
                continue  # already set (e.g. by effect param defs)
            default = _TRANSFORM_FIXED_DEFAULTS.get(prop.match_name)
            if default is None:
                default = spatial_defaults.get(prop.match_name)
            if default is not None:
                # When the parser stores a vector property as a scalar
                # (e.g. Orientation parsed as 0.0 instead of [0,0,0]),
                # coerce the default to match the actual value type.
                if isinstance(default, list) and not isinstance(
                    prop.value, (list, tuple)
                ):
                    default = default[0] if default else 0.0
                prop.default_value = default

    # --- Phase 2: synthesize missing properties & reorder -------------------
    # Match names whose synthesized *value* is 0.0 (inactive separation
    # followers) while their *default* comes from spatial_defaults.
    _INACTIVE_FOLLOWER_VALUE: dict[str, float] = {
        "ADBE Position_0": 0.0,
        "ADBE Position_1": 0.0,
    }

    overrides: dict[str, tuple[Any, Any]] = {}
    for spec in _TRANSFORM_SPECS:
        mn = spec.match_name
        default = _TRANSFORM_FIXED_DEFAULTS.get(mn)
        if default is None:
            default = spatial_defaults.get(mn)
        value: list[float] | float | None = _INACTIVE_FOLLOWER_VALUE.get(mn)
        if value is None:
            value = default
        if value is None:
            value = [0.0] * spec.dimensions if spec.dimensions > 1 else 0.0
        if default is None:
            default = value
        overrides[mn] = (value, default)

    _reorder_and_fill(
        transform, _TRANSFORM_SPECS, 2, value_overrides=overrides, tail_mode="none"
    )

    # --- Phase 3: context-dependent naming ----------------------------------
    # ExtendScript displays "ADBE Rotate Z" as "Rotation" on 2-D layers
    # and "Z Rotation" on 3-D layers.  Camera and Light layers are always 3-D.
    is_3d = isinstance(layer, (CameraLayer, LightLayer)) or (
        isinstance(layer, AVLayer) and layer.three_d_layer
    )
    if is_3d:
        # _reorder_and_fill set _auto_name="Rotation" from the spec;
        # undo it so the sentinel _name_utf8 falls through to
        # MATCH_NAME_TO_AUTO_NAME -> "Z Rotation".
        rotate_z = next(
            (p for p in transform.properties if p.match_name == "ADBE Rotate Z"),
            None,
        )
        if rotate_z is not None:
            rotate_z._auto_name = None
    else:
        # ExtendScript always reports Scale Z = 100 for 2-D layers,
        # regardless of the binary value.
        scale_prop = next(
            (p for p in transform.properties if p.match_name == "ADBE Scale"),
            None,
        )
        if isinstance(scale_prop, Property):
            # For parsed properties (cdat path), _resolve_value applies
            # the override; for synthesized properties (_value path),
            # fix the user-facing value directly.
            scale_prop._scale_z_override = 100.0
            if isinstance(scale_prop._value, list) and len(scale_prop._value) >= 3:
                scale_prop._value[2] = 100.0
            for kf in scale_prop.keyframes:
                raw = kf._extract_raw_value()
                if isinstance(raw, list) and len(raw) >= 3:
                    kf._value = raw
                    kf._value[2] = 1.0

    # Camera and Light layers show "Point of Interest" instead of
    # "Anchor Point" in the Transform group.
    if isinstance(layer, (CameraLayer, LightLayer)):
        anchor = next(
            (p for p in transform.properties if p.match_name == "ADBE Anchor Point"),
            None,
        )
        if anchor is not None:
            anchor._auto_name = "Point of Interest"

    # --- Phase 4: set min/max on transform properties -----------------------
    for child in transform.properties:
        if isinstance(child, Property):
            _apply_bounds(child)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def synthesize_layer_properties(layer: Layer) -> None:
    """Run the full post-parse property synthesis pass on a layer.

    This is the single entry point for all static property enrichment:
    transform defaults, top-level group ordering, recursive child
    synthesis, and min/max bounds application.

    Called once per layer at the end of `parse_layer`.

    Args:
        layer: The layer whose property tree should be finalized.
    """
    _set_transform_defaults(layer)

    # --- Synthesize missing top-level groups --------------------------------
    _synthesize_missing_top_level_groups(layer)

    # --- Synthesize children & apply min/max (single recursive pass) --------
    for group in layer.properties:
        if isinstance(group, PropertyGroup):
            if group.match_name == "ADBE Transform Group":
                continue  # already handled by _set_transform_defaults
            synthesize_children(group)
