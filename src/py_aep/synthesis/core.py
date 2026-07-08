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

from typing import TYPE_CHECKING

from ..ae_version import get_ae_version_major
from ..enums import PropertyValueType
from ..models.layers.av_layer import AVLayer
from ..models.layers.camera_layer import CameraLayer
from ..models.layers.light_layer import LightLayer
from ..models.layers.parametric_mesh_layer import ParametricMeshLayer
from ..models.layers.shape_layer import ShapeLayer
from ..models.layers.text_layer import TextLayer
from ..models.properties.property import Property
from ..models.properties.property_group import (
    PropertyGroup,
    _apply_bounds,
    _derive_layer_styles_enabled,
    _reorder_and_fill,
)
from .property import (
    _PARAMETRIC_MESH_TOP_LEVEL_SPECS,
    _SKIP_FOR_CAMERA,
    _SKIP_FOR_LIGHT,
    _SKIP_FOR_REGULAR_AV,
    _SKIP_FOR_SHAPE,
    _SKIP_FOR_TEXT,
    _TOP_LEVEL_SPECS,
    _TRANSFORM_FIXED_DEFAULTS,
    _TRANSFORM_SPECS,
)

if TYPE_CHECKING:
    from ..models.layers.layer import Layer


# ---------------------------------------------------------------------------
# Recursive child synthesis + bounds application (single pass)
# ---------------------------------------------------------------------------


def synthesize_children(group: PropertyGroup, ae_major: int) -> None:
    """Register deferred child synthesis for a group.

    Child groups and leaf min/max bounds are synthesized when the group's
    `properties` are first accessed. Layer Styles keeps its collapsed
    `enabled` state eagerly derived to preserve existing behavior.
    """
    if group.match_name == "ADBE Layer Styles":
        _derive_layer_styles_enabled(
            group,
            ae_major,
            synthesize_subgroups=False,
        )
    group._deferred_ae_major = ae_major


# ---------------------------------------------------------------------------
# Top-level group synthesis
# ---------------------------------------------------------------------------


def _synthesize_missing_top_level_groups(layer: Layer, ae_major: int) -> None:
    """Add missing top-level property groups expected by ExtendScript.

    ExtendScript always reports a fixed set of top-level property groups
    on every AV layer, even when most are empty.  The binary only stores
    groups that contain data.  This function synthesizes the missing empty
    groups and reorders all groups to match the canonical ExtendScript order.
    """
    specs = _TOP_LEVEL_SPECS
    if isinstance(layer, CameraLayer):
        skip_groups = _SKIP_FOR_CAMERA
    elif isinstance(layer, LightLayer):
        skip_groups = _SKIP_FOR_LIGHT
    elif not isinstance(layer, AVLayer):
        return
    elif isinstance(layer, TextLayer):
        skip_groups = _SKIP_FOR_TEXT
    elif isinstance(layer, ShapeLayer):
        skip_groups = _SKIP_FOR_SHAPE
    elif isinstance(layer, ParametricMeshLayer):
        # Mesh layers expose a different group set AND order (Geometry
        # Options / Essential Properties after Material Assignment), so
        # they use their own full spec list instead of a skip set.
        specs = _PARAMETRIC_MESH_TOP_LEVEL_SPECS
        skip_groups = frozenset()
    else:  # AVLayer
        skip_groups = _SKIP_FOR_REGULAR_AV

    _reorder_and_fill(
        layer, specs, 1, skip=skip_groups, tail_mode="all", ae_major=ae_major
    )

    # Post-processing: Layer Sets elided flag and depth fixup.
    canonical_mns = {s.match_name for s in specs}
    for child in layer.properties:
        if child.match_name == "ADBE Layer Sets":
            child._elided = True
        if isinstance(child, PropertyGroup) and child.match_name in canonical_mns:
            child._property_depth = 1


# ---------------------------------------------------------------------------
# Transform defaults
# ---------------------------------------------------------------------------


def _set_transform_defaults(layer: Layer, ae_major: int) -> None:
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
        if (
            isinstance(layer, (TextLayer, ShapeLayer, ParametricMeshLayer))
            or layer.null_layer
        ):
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
    spatial_defaults: dict[str, list[float] | float] = {
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
    # Match names whose synthesized `value` is 0.0 (inactive separation
    # followers) while their `default` comes from spatial_defaults.
    _INACTIVE_FOLLOWER_VALUE: dict[str, float] = {
        "ADBE Position_0": 0.0,
        "ADBE Position_1": 0.0,
    }

    overrides: dict[str, tuple[float | list[float], float | list[float]]] = {}
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
        transform,
        _TRANSFORM_SPECS,
        2,
        value_overrides=overrides,
        tail_mode="none",
        ae_major=ae_major,
    )

    # For null layers where opacity was already parsed from binary,
    # override the value to 0 (matching ExtendScript behavior).
    if isinstance(layer, AVLayer) and layer.null_layer:
        opacity = transform.property("ADBE Opacity")
        if isinstance(opacity, Property) and opacity.value == 100.0:
            opacity._value = 0.0
            opacity.default_value = 0.0

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
        rotate_z = transform.property("ADBE Rotate Z")
        if rotate_z is not None:
            rotate_z._auto_name = None
    else:
        # ExtendScript always reports Scale Z = 100 for 2-D layers,
        # regardless of the binary value.
        scale_prop = transform.property("ADBE Scale")
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
        anchor = transform.property("ADBE Anchor Point")
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
    ae_major: int = get_ae_version_major(layer)

    # --- Synthesize missing top-level groups --------------------------------
    _synthesize_missing_top_level_groups(layer, ae_major)

    _set_transform_defaults(layer, ae_major)

    # --- Synthesize children & apply min/max (single recursive pass) --------
    for group in layer.properties:
        if isinstance(group, PropertyGroup):
            if group.match_name == "ADBE Transform Group":
                continue  # already handled by _set_transform_defaults
            synthesize_children(group, ae_major=ae_major)
        elif isinstance(group, Property):
            _apply_bounds(group)
            # Time Remap max defaults to 0 when no _tduM chunk provides the
            # actual source duration.
            if group.match_name == "ADBE Time Remapping" and group._tduM is None:
                group._max_value_fallback = 0
