"""
py_aep Validation Tool.

Compares parsed AEP values against expected JSON values (from ExtendScript export)
to validate parsing correctness.

Usage:
    aep-validate project.aep expected.json
    aep-validate project.aep expected.json --verbose
    aep-validate project.aep expected.json --category layers
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path, PureWindowsPath
from typing import TYPE_CHECKING

from py_aep import parse

if TYPE_CHECKING:
    from typing import Any

# Fields to skip to avoid circular references.
# Back-references: containing_comp, parent_folder, parent (OutputModule),
#   _parent (Layer).
# Cross-references that re-enter the object graph: _source (AVLayer > Item),
#   comp (RenderQueueItem > CompItem),
#   post_render_target_comp (OutputModule > CompItem).
# The non-circular ID fields (source_id, parent_id) are still serialized.
SKIP_FIELDS = {
    "containing_comp",
    "parent_folder",
    "parent_property",
    "parent",
    "comp",
    "post_render_target_comp",
    # Internal marker property (Property with keyframes); compared
    # separately via _compare_markers.
    "marker_property",
    # Cross-reference: LightLayer.light_source > Layer
    "light_source",
}

# @property attributes that return complex/duplicate data and should not be
# included in to_dict() serialization.
SKIP_PROPERTIES = {
    "active_camera",
    "composition_layers",
    "footage_layers",
    "selected_layers",
    # Circular: AVLayer.source > Item > layers > AVLayer...
    "source",
    # Circular: AVLayer.track_matte_layer > AVLayer
    "track_matte_layer",
    # Circular: AVItem.used_in > list[CompItem] > layers > source > AVItem...
    "used_in",
    # Duplicate/circular: Project re-serializes items already in `items` field
    "compositions",
    "folders",
    "footages",
    # Layer @property accessors derived from Layer.properties - serializing
    # them would duplicate data already present in the properties list.
    "transform",
    "effects",
    "masks",
    "text",
    # Duplicate: Property.separation_leader > Property
    "separation_leader",
    # Layer.marker @property: duplicates ADBE Marker in properties tree.
    "marker",
}


_field_names_cache: dict[type, frozenset[str] | set[str] | None] = {}


def _get_field_names(obj: Any) -> frozenset[str] | set[str] | None:
    """Get serializable field names for model objects.

    Supports both `@dataclass` models and plain-class models that use
    type annotations and/or chunk-backed descriptors (e.g. the Item
    hierarchy after the descriptor conversion).

    Results are cached per type since field names are class-level metadata.
    """
    cls = type(obj)
    if cls in _field_names_cache:
        return _field_names_cache[cls]

    names: set[str] = set()
    if is_dataclass(obj) and not isinstance(obj, type):
        names = {f.name for f in fields(obj)}
    # Collect annotations and chunk-backed descriptors from the full MRO.
    # This covers plain-class models and also dataclass subclasses that
    # add chunk descriptors in non-dataclass bases (e.g. Layer extends
    # PropertyGroup with ChunkField descriptors).
    for base in reversed(cls.__mro__):
        if base is object:
            continue
        for name in getattr(base, "__annotations__", {}):
            if not name.startswith("_"):
                names.add(name)
        for name, attr in vars(base).items():
            # ChunkField (binary-backed) and CosField (COS-dict-backed)
            # descriptors both expose a backing-store attribute name.
            is_descriptor = hasattr(attr, "chunk_attr") or hasattr(attr, "dict_attr")
            if is_descriptor and hasattr(attr, "__get__"):
                names.add(name)
    if names:
        result = frozenset(names)
        _field_names_cache[cls] = result
        return result
    # Check for public @property definitions (descriptor-backed classes
    # that replaced all class-level annotations with properties).
    for base in reversed(cls.__mro__):
        if base is object:
            continue
        for name, attr in vars(base).items():
            if not name.startswith("_") and isinstance(attr, property):
                names.add(name)
    result2: frozenset[str] | None = frozenset(names) if names else None
    _field_names_cache[cls] = result2
    return result2


_property_names_cache: dict[type, frozenset[str]] = {}


def _get_property_names(cls: type) -> frozenset[str]:
    """Get public @property names for a class, cached per type."""
    if cls in _property_names_cache:
        return _property_names_cache[cls]
    names: set[str] = set()
    for name in dir(cls):
        if name.startswith("_") or name in SKIP_FIELDS or name in SKIP_PROPERTIES:
            continue
        attr = getattr(cls, name, None)
        if isinstance(attr, property):
            names.add(name)
    result = frozenset(names)
    _property_names_cache[cls] = result
    return result


_PRIMITIVE_TYPES = (int, float, str, bool, type(None))


def to_dict(obj: Any) -> Any:
    """Convert dataclass/enum to dict recursively, skipping circular reference fields."""
    # Fast path for primitive types (majority of recursive calls)
    if isinstance(obj, _PRIMITIVE_TYPES):
        return obj
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, list):
        return [to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    field_names = _get_field_names(obj)
    if field_names is not None:
        result = {}
        for name in field_names:
            if name in SKIP_FIELDS:
                continue
            try:
                value = getattr(obj, name)
            except (AttributeError, KeyError):  # missing chunk or field
                continue
            result[name] = to_dict(value)
        # Include @property attributes (non-private, non-skipped)
        for name in _get_property_names(type(obj)):
            if name in result:
                continue
            try:
                value = getattr(obj, name)
            except (AttributeError, KeyError):  # missing chunk or field
                continue
            result[name] = to_dict(value)
        return result
    return obj


def get_enum_value(val: Any) -> Any:
    """Get enum value as int if it's an IntEnum, else return as-is."""
    if isinstance(val, Enum):
        return val.value
    return val


_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _normalize_keys(d: dict[str, Any]) -> dict[str, Any]:
    """Convert camelCase dict keys to snake_case recursively."""
    result: dict[str, Any] = {}
    for key, value in d.items():
        snake_key = _CAMEL_RE.sub("_", key).lower()
        if isinstance(value, dict):
            value = _normalize_keys(value)
        result[snake_key] = value
    return result


def compare_values(expected: Any, parsed: Any, tolerance: float = 0.001) -> bool:
    """
    Compare two values with tolerance for floats.

    Args:
        expected: Expected value from ExtendScript JSON.
        parsed: Parsed value from py_aep.
        tolerance: Float comparison tolerance.

    Returns:
        True if values match.
    """
    if expected is None and parsed is None:
        return True
    if expected is None or parsed is None:
        return False
    if isinstance(expected, bool) and isinstance(parsed, bool):
        return expected == parsed
    if isinstance(expected, (int, float)) and isinstance(parsed, (int, float)):
        return math.isclose(expected, parsed, rel_tol=tolerance, abs_tol=tolerance)
    if isinstance(expected, str) and isinstance(parsed, str):
        return expected == parsed
    if isinstance(expected, list) and isinstance(parsed, list):
        if len(expected) != len(parsed):
            return False
        return all(compare_values(e, p, tolerance) for e, p in zip(expected, parsed))
    return bool(expected == parsed)


class ValidationResult:
    """Stores validation results."""

    def __init__(self) -> None:
        self.differences: list[str] = []
        self.warnings: list[str] = []
        self.categories: dict[str, int] = {}
        self.defined_fields: set[str] = set()
        self.compared_fields: set[str] = set()

    def __len__(self) -> int:
        return len(self.differences)

    def add_diff(
        self, path: str, expected: Any, parsed: Any, category: str = "other"
    ) -> None:
        """Add a difference."""
        self.differences.append(f"{path}: expected {expected!r}, got {parsed!r}")
        self.categories[category] = self.categories.get(category, 0) + 1

    def add_warning(self, message: str) -> None:
        """Add a warning."""
        self.warnings.append(message)

    def track_field(self, class_name: str, attr: str, was_compared: bool) -> None:
        """Register a field for coverage tracking."""
        key = f"{class_name}.{attr}"
        self.defined_fields.add(key)
        if was_compared:
            self.compared_fields.add(key)


def _compare_fields(
    expected: dict[str, Any],
    parsed: dict[str, Any],
    mappings: dict[str, str],
    path: str,
    category: str,
    result: ValidationResult,
    class_name: str = "",
) -> None:
    """Compare mapped fields between expected and parsed dicts.

    For each mapping entry, looks up the expected JSON key in `expected`
    and the corresponding parsed key in `parsed`, skipping undefined values,
    and records a diff when they don't match.
    """
    for exp_key, parsed_key in mappings.items():
        if class_name:
            result.defined_fields.add(f"{class_name}.{parsed_key}")
        if exp_key in expected:
            exp_val = expected[exp_key]
            if isinstance(exp_val, dict) and exp_val.get("_undefined"):
                continue
            if class_name:
                result.compared_fields.add(f"{class_name}.{parsed_key}")
            parsed_val = get_enum_value(parsed.get(parsed_key))
            if not compare_values(exp_val, parsed_val):
                result.add_diff(f"{path}.{exp_key}", exp_val, parsed_val, category)


def _compare_markers(
    expected_markers: list[dict[str, Any]],
    parsed_markers: list[dict[str, Any]],
    path: str,
    frame_rate: float,
    result: ValidationResult,
) -> None:
    """Compare a list of markers (used by both layers and compositions)."""
    if len(expected_markers) != len(parsed_markers):
        result.add_diff(
            f"{path}.numMarkers",
            len(expected_markers),
            len(parsed_markers),
            "markers",
        )
    for i, (exp_marker, parsed_marker) in enumerate(
        zip(expected_markers, parsed_markers)
    ):
        compare_marker(
            exp_marker, parsed_marker, f"{path}.markers[{i}]", frame_rate, result
        )


def _compare_guides(
    expected_guides: list[dict[str, Any]],
    parsed_guides: list[dict[str, Any]],
    path: str,
    result: ValidationResult,
) -> None:
    """Compare a list of guides."""
    if len(expected_guides) != len(parsed_guides):
        result.add_diff(
            f"{path}.numGuides",
            len(expected_guides),
            len(parsed_guides),
            "composition",
        )
    guide_mappings = {
        "orientationType": "orientation_type",
        "position": "position",
        "positionType": "position_type",
    }
    for i, (exp_guide, parsed_guide) in enumerate(zip(expected_guides, parsed_guides)):
        _compare_fields(
            exp_guide,
            parsed_guide,
            guide_mappings,
            f"{path}.guides[{i}]",
            "composition",
            result,
            class_name="Guide",
        )


def _compare_proxy_source(
    expected_item: dict[str, Any],
    parsed_item: dict[str, Any],
    path: str,
    result: ValidationResult,
) -> None:
    """Compare proxySource on an AVItem (comp or footage)."""
    exp_proxy = expected_item.get("proxySource")
    parsed_proxy = parsed_item.get("proxy_source")
    if exp_proxy and parsed_proxy:
        proxy_path = f"{path}.proxySource"
        source_mappings = {
            "alphaMode": "alpha_mode",
            "displayFrameRate": "display_frame_rate",
            "fieldSeparationType": "field_separation_type",
            "hasAlpha": "has_alpha",
            "highQualityFieldSeparation": "high_quality_field_separation",
            "invertAlpha": "invert_alpha",
            "isStill": "is_still",
            "loop": "loop",
            "nativeFrameRate": "native_frame_rate",
            "premulColor": "premul_color",
            "removePulldown": "remove_pulldown",
            "color": "color",
        }
        _compare_fields(
            exp_proxy,
            parsed_proxy,
            source_mappings,
            proxy_path,
            "footage",
            result,
            class_name="FootageSource",
        )
    elif exp_proxy and not parsed_proxy:
        result.add_diff(f"{path}.proxySource", "present", "None", "footage")
    elif not exp_proxy and parsed_proxy:
        result.add_diff(f"{path}.proxySource", "None", "present", "footage")


def _compare_children_by_match_name(
    expected_props: list[dict[str, Any]],
    parsed_props: list[dict[str, Any]],
    path: str,
    result: ValidationResult,
) -> None:
    """Match expected/parsed property children by matchName, then recurse."""
    if len(expected_props) != len(parsed_props):
        result.add_diff(
            f"{path}.numProperties",
            len(expected_props),
            len(parsed_props),
            "properties",
        )

    # Build match-name lookup.  When multiple children share the same
    # match_name (e.g. masks, duplicate effects), store them in order so we
    # can fall back to positional matching within each match_name group.
    parsed_by_match_name: dict[str, list[dict[str, Any]]] = {}
    for p in parsed_props:
        mn = p.get("match_name", "")
        if mn:
            parsed_by_match_name.setdefault(mn, []).append(p)

    # Track how many of each match_name we have consumed.
    match_name_idx: dict[str, int] = {}

    for i, exp_prop in enumerate(expected_props):
        exp_match_name = exp_prop.get("matchName", "")
        exp_name = exp_prop.get("name", f"[{i}]")
        child_path = f"{path}.{exp_name}"

        candidates = parsed_by_match_name.get(exp_match_name)
        if not candidates:
            result.add_diff(child_path, "exists", "missing", "properties")
            continue

        idx = match_name_idx.get(exp_match_name, 0)
        if idx < len(candidates):
            parsed_prop = candidates[idx]
            match_name_idx[exp_match_name] = idx + 1
        else:
            parsed_prop = candidates[-1]

        has_child_properties = "properties" in exp_prop
        exp_property_type = exp_prop.get("propertyType")
        if has_child_properties or exp_property_type == "IndexedGroup":
            compare_property_group(exp_prop, parsed_prop, child_path, result)
        else:
            compare_property(exp_prop, parsed_prop, child_path, result)


def compare_project_level(
    expected: dict[str, Any], parsed: dict[str, Any], result: ValidationResult
) -> None:
    """Compare project-level properties."""
    mappings = {
        "bitsPerChannel": "bits_per_channel",
        "transparencyGridThumbnails": "transparency_grid_thumbnails",
        "displayStartFrame": "display_start_frame",
        "framesCountType": "frames_count_type",
        "feetFramesFilmType": "feet_frames_film_type",
        "framesUseFeetFrames": "frames_use_feet_frames",
        "timeDisplayType": "time_display_type",
        "footageTimecodeDisplayStartType": "footage_timecode_display_start_type",
        "expressionEngine": "expression_engine",
        "linearBlending": "linear_blending",
        "workingSpace": "working_space",
        "linearizeWorkingSpace": "linearize_working_space",
        "workingGamma": "working_gamma",
        "gpuAccelType": "gpu_accel_type",
    }

    _compare_fields(
        expected, parsed, mappings, "Project", "project", result, class_name="Project"
    )


def compare_marker(
    expected_marker: dict[str, Any],
    parsed_marker: dict[str, Any],
    path: str,
    frame_rate: float,
    result: ValidationResult,
) -> None:
    """Compare marker properties."""
    # Calculate time from frame_time if available
    parsed_time = None
    if parsed_marker.get("frame_time") is not None:
        parsed_time = parsed_marker["frame_time"] / frame_rate

    # Compare time
    result.track_field("Marker", "time", "time" in expected_marker)
    if "time" in expected_marker:
        exp_val = expected_marker["time"]
        if not isinstance(exp_val, dict) or not exp_val.get("_undefined"):
            if not compare_values(exp_val, parsed_time):
                result.add_diff(f"{path}.time", exp_val, parsed_time, "markers")

    marker_mappings = {
        "comment": "comment",
        "chapter": "chapter",
        "url": "url",
        "duration": "duration",
        "label": "label",
        "cuePointName": "cue_point_name",
        "frameTarget": "frame_target",
        "protectedRegion": "protected_region",
        "eventCuePoint": "event_cue_point",
    }

    _compare_fields(
        expected_marker,
        parsed_marker,
        marker_mappings,
        path,
        "markers",
        result,
        class_name="Marker",
    )


def compare_layer(
    expected_layer: dict[str, Any],
    parsed_layer: dict[str, Any],
    path: str,
    comp_duration: float,
    frame_rate: float,
    result: ValidationResult,
) -> None:
    """Compare layer properties."""
    layer_mappings = {
        "name": "name",
        "id": "id",
        "time": "time",
        "comment": "comment",
        "enabled": "enabled",
        "canSetEnabled": "can_set_enabled",
        "hasVideo": "has_video",
        "hasAudio": "has_audio",
        "canSetCollapseTransformation": "can_set_collapse_transformation",
        "canSetTimeRemapEnabled": "can_set_time_remap_enabled",
        "inPoint": "in_point",
        "outPoint": "out_point",
        "startTime": "start_time",
        "stretch": "stretch",
        "label": "label",
        "locked": "locked",
        "nullLayer": "null_layer",
        "shy": "shy",
        "solo": "solo",
        "isNameSet": "is_name_set",
        "autoOrient": "auto_orient",
        "matchName": "match_name",
        "layerType": "layer_type",
        "hasTrackMatte": "has_track_matte",
        "isTrackMatte": "is_track_matte",
        "isNameFromSource": "is_name_from_source",
        # AVLayer specific
        "adjustmentLayer": "adjustment_layer",
        "audioActive": "audio_active",
        "audioEnabled": "audio_enabled",
        "blendingMode": "blending_mode",
        "collapseTransformation": "collapse_transformation",
        "effectsActive": "effects_active",
        "environmentLayer": "environment_layer",
        "frameBlending": "frame_blending",
        "frameBlendingType": "frame_blending_type",
        "guideLayer": "guide_layer",
        "height": "height",
        "width": "width",
        "motionBlur": "motion_blur",
        "preserveTransparency": "preserve_transparency",
        "quality": "quality",
        "samplingQuality": "sampling_quality",
        "threeDLayer": "three_d_layer",
        "timeRemapEnabled": "time_remap_enabled",
        "trackMatteType": "track_matte_type",
        "sourceId": "_source_id",
        "lightType": "light_type",
        "threeDPerChar": "three_d_per_char",
    }

    _compare_fields(
        expected_layer,
        parsed_layer,
        layer_mappings,
        path,
        "layers",
        result,
        class_name="Layer",
    )

    # Compare index (ExtendScript is 1-based, parsed is 0-based)
    result.track_field("Layer", "index", "index" in expected_layer)
    result.track_field("Layer", "light_source_id", "lightSource" in expected_layer)
    if "index" in expected_layer:
        exp_index = expected_layer["index"]
        parsed_index = parsed_layer.get("index")
        if parsed_index is not None and exp_index != parsed_index + 1:
            result.add_diff(f"{path}.index", exp_index, parsed_index + 1, "layers")

    # Compare lightSource (Layer reference -> compare by layer index)
    if "lightSource" in expected_layer:
        exp_ls = expected_layer["lightSource"]
        parsed_ls_id = parsed_layer.get("_light_source_id", 0)
        if exp_ls is None:
            if parsed_ls_id != 0:
                result.add_diff(f"{path}.lightSource", None, parsed_ls_id, "layers")
        elif isinstance(exp_ls, dict):
            exp_ls_index = exp_ls.get("index")
            if exp_ls_index is not None and parsed_ls_id == 0:
                result.add_diff(f"{path}.lightSource", exp_ls_index, None, "layers")

    # Compare all property groups via the properties list.
    _compare_children_by_match_name(
        expected_layer.get("properties", []),
        parsed_layer.get("properties", []),
        path,
        result,
    )


def compare_property(
    expected_prop: dict[str, Any],
    parsed_prop: dict[str, Any],
    path: str,
    result: ValidationResult,
) -> None:
    """Compare a single property (leaf node).

    Args:
        expected_prop: Expected property from ExtendScript JSON.
        parsed_prop: Parsed property from py_aep.
        path: Dotted path for error messages.
        result: ValidationResult to accumulate differences.
    """
    property_mappings = {
        "name": "name",
        "matchName": "match_name",
        "enabled": "enabled",
        "canSetEnabled": "can_set_enabled",
        "canSetExpression": "can_set_expression",
        "canVaryOverTime": "can_vary_over_time",
        "expression": "expression",
        "expressionEnabled": "expression_enabled",
        "propertyValueType": "property_value_type",
        "propertyDepth": "property_depth",
        "dimensionsSeparated": "dimensions_separated",
        "isSpatial": "is_spatial",
        "elided": "elided",
        "isEffect": "is_effect",
        "isMask": "is_mask",
        "isModified": "is_modified",
        "isSeparationLeader": "is_separation_leader",
        "isSeparationFollower": "is_separation_follower",
        "unitsText": "units_text",
        "separationDimension": "separation_dimension",
        "canSetAlternateSource": "can_set_alternate_source",
    }

    _compare_fields(
        expected_prop,
        parsed_prop,
        property_mappings,
        path,
        "properties",
        result,
        class_name="Property",
    )

    # Track manually-compared fields
    result.track_field("Property", "property_index", "propertyIndex" in expected_prop)
    result.track_field("Property", "value", "value" in expected_prop)
    result.track_field("Property", "keyframes", "numKeys" in expected_prop)
    result.track_field(
        "Property",
        "min_value",
        "hasMin" in expected_prop and bool(expected_prop.get("hasMin")),
    )
    result.track_field(
        "Property",
        "max_value",
        "hasMax" in expected_prop and bool(expected_prop.get("hasMax")),
    )

    # Compare propertyIndex (ExtendScript is 1-based, parsed is 0-based)
    if "propertyIndex" in expected_prop:
        exp_pi = expected_prop["propertyIndex"]
        parsed_pi = parsed_prop.get("property_index")
        if parsed_pi is not None and exp_pi != parsed_pi + 1:
            result.add_diff(
                f"{path}.propertyIndex", exp_pi, parsed_pi + 1, "properties"
            )

    # Compare value
    if "value" in expected_prop:
        exp_val = expected_prop["value"]
        parsed_val = parsed_prop.get("value")
        if not isinstance(exp_val, dict) or not exp_val.get("_undefined"):
            if parsed_val is None:
                result.add_diff(f"{path}.value", exp_val, parsed_val, "properties")
            elif not compare_values(exp_val, parsed_val):
                result.add_diff(f"{path}.value", exp_val, parsed_val, "properties")

    # Compare numKeys vs len(keyframes)
    if "numKeys" in expected_prop:
        exp_num_keys = expected_prop["numKeys"]
        parsed_keyframes = parsed_prop.get("keyframes", [])
        parsed_num_keys = len(parsed_keyframes) if parsed_keyframes else 0
        if exp_num_keys != parsed_num_keys:
            result.add_diff(
                f"{path}.numKeys", exp_num_keys, parsed_num_keys, "properties"
            )

    # Compare individual keyframes
    exp_keyframes = expected_prop.get("keyframes", [])
    parsed_keyframes = parsed_prop.get("keyframes", [])
    for ki, (exp_kf, parsed_kf) in enumerate(zip(exp_keyframes, parsed_keyframes)):
        compare_keyframe(exp_kf, parsed_kf, f"{path}.keyframes[{ki}]", result)

    # Compare has_min/has_max PRESENCE first - this catches both over-reporting
    # (py reports a bound ExtendScript says is absent) and under-reporting,
    # which the value comparisons below cannot (they only run when ES reports
    # the bound present).
    if "hasMin" in expected_prop:
        exp_has_min = bool(expected_prop["hasMin"])
        parsed_has_min = bool(parsed_prop.get("has_min"))
        if exp_has_min != parsed_has_min:
            result.add_diff(f"{path}.hasMin", exp_has_min, parsed_has_min, "properties")
    if "hasMax" in expected_prop:
        exp_has_max = bool(expected_prop["hasMax"])
        parsed_has_max = bool(parsed_prop.get("has_max"))
        if exp_has_max != parsed_has_max:
            result.add_diff(f"{path}.hasMax", exp_has_max, parsed_has_max, "properties")

    # Compare min/max values only when BOTH sides report the bound present.
    # The presence check above already flags an under-reported bound; gating
    # the value comparison on the parsed side too avoids a redundant second
    # diff (.minValue: 0 vs None) for the same root cause.
    if expected_prop.get("hasMin") and parsed_prop.get("has_min"):
        if "minValue" in expected_prop:
            exp_min = expected_prop["minValue"]
            parsed_min = parsed_prop.get("min_value")
            if not compare_values(exp_min, parsed_min):
                result.add_diff(f"{path}.minValue", exp_min, parsed_min, "properties")

    if expected_prop.get("hasMax") and parsed_prop.get("has_max"):
        if "maxValue" in expected_prop:
            exp_max = expected_prop["maxValue"]
            parsed_max = parsed_prop.get("max_value")
            if not compare_values(exp_max, parsed_max):
                result.add_diff(f"{path}.maxValue", exp_max, parsed_max, "properties")

    # Compare TextDocument value
    if "textDocument" in expected_prop:
        parsed_value = parsed_prop.get("value")
        if isinstance(parsed_value, dict):
            compare_text_document(
                expected_prop["textDocument"],
                parsed_value,
                f"{path}.textDocument",
                result,
            )

    # Compare Shape value
    if "shapeValue" in expected_prop:
        parsed_value = parsed_prop.get("value")
        if isinstance(parsed_value, dict):
            compare_shape_value(
                expected_prop["shapeValue"],
                parsed_value,
                f"{path}.shapeValue",
                result,
            )

    # Compare alternateSource (Media Replacement wrapper reference). to_dict
    # serializes the AVItem fully, so id/name are available; compare on id (the
    # binary blsi item id, the strongest invariant) then name.
    result.track_field(
        "Property", "alternate_source", "alternateSource" in expected_prop
    )
    if "alternateSource" in expected_prop:
        exp_alt = expected_prop["alternateSource"]
        parsed_alt = parsed_prop.get("alternate_source")
        if exp_alt is None:
            if parsed_alt is not None:
                pid = (
                    parsed_alt.get("id") if isinstance(parsed_alt, dict) else parsed_alt
                )
                result.add_diff(f"{path}.alternateSource", None, pid, "properties")
        elif isinstance(exp_alt, dict):
            if not isinstance(parsed_alt, dict):
                result.add_diff(f"{path}.alternateSource", exp_alt, None, "properties")
            else:
                for key in ("id", "name"):
                    if exp_alt.get(key) != parsed_alt.get(key):
                        result.add_diff(
                            f"{path}.alternateSource.{key}",
                            exp_alt.get(key),
                            parsed_alt.get(key),
                            "properties",
                        )

    # Compare essentialPropertySource (originating source of an Essential
    # Property). ExtendScript emits a {sourceType, ...} descriptor: an AVLayer
    # source (Media Replacement Footage) is compared on name + index (index is
    # 1-based, parsed is 0-based; the containing-comp name is not serialized by
    # to_dict - circular-ref guard - so comp is not compared). A Property source
    # is compared on matchName.
    result.track_field(
        "Property",
        "essential_property_source",
        "essentialPropertySource" in expected_prop,
    )
    if "essentialPropertySource" in expected_prop:
        exp_eps = expected_prop["essentialPropertySource"]
        parsed_eps = parsed_prop.get("essential_property_source")
        if exp_eps is None:
            if parsed_eps is not None:
                pname = (
                    parsed_eps.get("name")
                    if isinstance(parsed_eps, dict)
                    else parsed_eps
                )
                result.add_diff(
                    f"{path}.essentialPropertySource", None, pname, "properties"
                )
        elif not isinstance(parsed_eps, dict):
            result.add_diff(
                f"{path}.essentialPropertySource", exp_eps, None, "properties"
            )
        elif exp_eps.get("sourceType") == "AVLayer":
            if exp_eps.get("name") != parsed_eps.get("name"):
                result.add_diff(
                    f"{path}.essentialPropertySource.name",
                    exp_eps.get("name"),
                    parsed_eps.get("name"),
                    "properties",
                )
            exp_idx = exp_eps.get("index")
            parsed_idx = parsed_eps.get("index")
            if (
                exp_idx is not None
                and parsed_idx is not None
                and exp_idx != parsed_idx + 1
            ):
                result.add_diff(
                    f"{path}.essentialPropertySource.index",
                    exp_idx,
                    parsed_idx + 1,
                    "properties",
                )
        elif exp_eps.get("sourceType") == "Property":
            if exp_eps.get("matchName") != parsed_eps.get("match_name"):
                result.add_diff(
                    f"{path}.essentialPropertySource.matchName",
                    exp_eps.get("matchName"),
                    parsed_eps.get("match_name"),
                    "properties",
                )


def compare_shape_value(
    expected_shape: dict[str, Any],
    parsed_shape: dict[str, Any],
    path: str,
    result: ValidationResult,
) -> None:
    """Compare a Shape value (mask path or shape layer path).

    Args:
        expected_shape: Expected shape from ExtendScript JSON.
        parsed_shape: Parsed shape dict from py_aep.
        path: Dotted path for error messages.
        result: ValidationResult to accumulate differences.
    """
    shape_mappings: dict[str, str] = {
        "closed": "closed",
        "vertices": "vertices",
        "inTangents": "in_tangents",
        "outTangents": "out_tangents",
    }
    _compare_fields(
        expected_shape,
        parsed_shape,
        shape_mappings,
        path,
        "shape",
        result,
        class_name="Shape",
    )

    # Compare feather data: ExtendScript exposes parallel arrays,
    # py_aep stores a list of FeatherPoint objects.
    feather_field_map: dict[str, str] = {
        "featherSegLocs": "seg_loc",
        "featherRelSegLocs": "rel_seg_loc",
        "featherRadii": "radius",
        "featherTypes": "type",
        "featherInterps": "interp",
        "featherTensions": "tension",
        "featherRelCornerAngles": "rel_corner_angle",
    }
    parsed_fps = parsed_shape.get("feather_points", [])
    for exp_key, fp_attr in feather_field_map.items():
        result.defined_fields.add(f"Shape.{fp_attr}")
        if exp_key in expected_shape:
            exp_val = expected_shape[exp_key]
            if isinstance(exp_val, dict) and exp_val.get("_undefined"):
                continue
            result.compared_fields.add(f"Shape.{fp_attr}")
            parsed_val = [fp.get(fp_attr) for fp in parsed_fps]
            if not compare_values(exp_val, parsed_val):
                result.add_diff(f"{path}.{exp_key}", exp_val, parsed_val, "shape")


def compare_keyframe(
    expected_kf: dict[str, Any],
    parsed_kf: dict[str, Any],
    path: str,
    result: ValidationResult,
) -> None:
    """Compare a single keyframe's attributes.

    Args:
        expected_kf: Expected keyframe from ExtendScript JSON.
        parsed_kf: Parsed keyframe from py_aep.
        path: Dotted path for error messages.
        result: ValidationResult to accumulate differences.
    """
    # Track manually-compared fields
    result.track_field("Keyframe", "value", "value" in expected_kf)
    result.track_field("Keyframe", "in_temporal_ease", "inTemporalEase" in expected_kf)
    result.track_field(
        "Keyframe", "out_temporal_ease", "outTemporalEase" in expected_kf
    )

    # Compare value
    if "value" in expected_kf and parsed_kf.get("value") is not None:
        exp_val = expected_kf["value"]
        parsed_val = parsed_kf["value"]
        if isinstance(exp_val, dict) and "vertices" in exp_val:
            # Shape keyframe value - compare as shape
            if isinstance(parsed_val, dict):
                compare_shape_value(exp_val, parsed_val, f"{path}.value", result)
        elif isinstance(exp_val, dict) and isinstance(parsed_val, dict):
            # Dict value (e.g. marker) - normalize keys and compare matching
            normalized = _normalize_keys(exp_val)
            for key, nval in normalized.items():
                pval = parsed_val.get(key)
                if pval is not None and not compare_values(nval, pval):
                    result.add_diff(f"{path}.value.{key}", nval, pval, "keyframes")
        elif not isinstance(exp_val, dict) or not exp_val.get("_undefined"):
            if not compare_values(exp_val, parsed_val):
                result.add_diff(f"{path}.value", exp_val, parsed_val, "keyframes")

    # Compare interpolation types and boolean flags
    kf_mappings = {
        "time": "time",
        "inInterpolationType": "in_interpolation_type",
        "outInterpolationType": "out_interpolation_type",
        "temporalAutoBezier": "temporal_auto_bezier",
        "temporalContinuous": "temporal_continuous",
        "spatialAutoBezier": "spatial_auto_bezier",
        "spatialContinuous": "spatial_continuous",
        "roving": "roving",
        "label": "label",
        "inSpatialTangent": "in_spatial_tangent",
        "outSpatialTangent": "out_spatial_tangent",
    }

    _compare_fields(
        expected_kf,
        parsed_kf,
        kf_mappings,
        path,
        "keyframes",
        result,
        class_name="Keyframe",
    )

    # Compare temporal ease
    for ease_key, parsed_key in [
        ("inTemporalEase", "in_temporal_ease"),
        ("outTemporalEase", "out_temporal_ease"),
    ]:
        if ease_key in expected_kf:
            exp_ease = expected_kf[ease_key]
            parsed_ease = parsed_kf.get(parsed_key, [])
            if len(exp_ease) != len(parsed_ease):
                result.add_diff(
                    f"{path}.{ease_key}.length",
                    len(exp_ease),
                    len(parsed_ease),
                    "keyframes",
                )
            for ei, (exp_e, parsed_e) in enumerate(zip(exp_ease, parsed_ease)):
                exp_speed = exp_e.get("speed") if isinstance(exp_e, dict) else None
                exp_influence = (
                    exp_e.get("influence") if isinstance(exp_e, dict) else None
                )
                parsed_speed = (
                    parsed_e.get("speed") if isinstance(parsed_e, dict) else None
                )
                parsed_influence = (
                    parsed_e.get("influence") if isinstance(parsed_e, dict) else None
                )
                if not compare_values(exp_speed, parsed_speed):
                    result.add_diff(
                        f"{path}.{ease_key}[{ei}].speed",
                        exp_speed,
                        parsed_speed,
                        "keyframes",
                    )
                if not compare_values(exp_influence, parsed_influence):
                    result.add_diff(
                        f"{path}.{ease_key}[{ei}].influence",
                        exp_influence,
                        parsed_influence,
                        "keyframes",
                    )


def compare_text_document(
    expected_doc: dict[str, Any],
    parsed_doc: dict[str, Any],
    path: str,
    result: ValidationResult,
) -> None:
    """Compare TextDocument properties.

    Args:
        expected_doc: Expected TextDocument from ExtendScript JSON.
        parsed_doc: Parsed TextDocument from py_aep.
        path: Dotted path for error messages.
        result: ValidationResult to accumulate differences.
    """
    # fontFamily/fontStyle/fontLocation are intentionally omitted: AE does not
    # store them in the .aep. It resolves them at runtime by feeding the stored
    # PostScript name to CoolType against the host's installed font database, so
    # the ExtendScript ground truth is host-dependent (e.g. a live Windows font
    # path) and there is nothing in the binary to decode. `font` (the stored
    # PostScript name) is compared instead.
    if isinstance(expected_doc.get("text"), str) and "\r" in expected_doc["text"]:
        # ExtendScript reports AE's CR line breaks; TextDocument.text
        # normalizes them to LF by design.
        expected_doc = dict(expected_doc)
        expected_doc["text"] = expected_doc["text"].replace("\r", "\n")
    text_mappings = {
        "text": "text",
        "font": "font",
        "fontSize": "font_size",
        "fauxBold": "faux_bold",
        "fauxItalic": "faux_italic",
        "autoKernType": "auto_kern_type",
        "kerning": "kerning",
        "tracking": "tracking",
        "leading": "leading",
        "leadingType": "leading_type",
        "autoLeading": "auto_leading",
        "baselineShift": "baseline_shift",
        "horizontalScale": "horizontal_scale",
        "verticalScale": "vertical_scale",
        "tsume": "tsume",
        "allCaps": "all_caps",
        "smallCaps": "small_caps",
        "superscript": "superscript",
        "subscript": "subscript",
        "fontBaselineOption": "font_baseline_option",
        "fontCapsOption": "font_caps_option",
        "baselineDirection": "baseline_direction",
        "ligature": "ligature",
        "noBreak": "no_break",
        "digitSet": "digit_set",
        "lineJoinType": "line_join_type",
        "fillColor": "fill_color",
        "applyFill": "apply_fill",
        "strokeColor": "stroke_color",
        "applyStroke": "apply_stroke",
        "strokeWidth": "stroke_width",
        "strokeOverFill": "stroke_over_fill",
        "justification": "justification",
        "direction": "direction",
        "firstLineIndent": "first_line_indent",
        "startIndent": "start_indent",
        "endIndent": "end_indent",
        "spaceBefore": "space_before",
        "spaceAfter": "space_after",
        "everyLineComposer": "every_line_composer",
        "hangingRoman": "hanging_roman",
        "autoHyphenate": "auto_hyphenate",
        "composerEngine": "composer_engine",
        "paragraphCount": "paragraph_count",
        "boxText": "box_text",
        "pointText": "point_text",
        "boxTextSize": "box_text_size",
        "boxTextPos": "box_text_pos",
        "boxVerticalAlignment": "box_vertical_alignment",
        "boxAutoFitPolicy": "box_auto_fit_policy",
        "boxFirstBaselineAlignment": "box_first_baseline_alignment",
        "boxFirstBaselineAlignmentMinimum": "box_first_baseline_alignment_minimum",
        "boxInsetSpacing": "box_inset_spacing",
        "boxOverflow": "box_overflow",
        "lineOrientation": "line_orientation",
        "composedLineCount": "composed_line_count",
        "paragraphRanges": "paragraph_ranges",
        "composedLineRanges": "composed_line_ranges",
    }

    _compare_fields(
        expected_doc,
        parsed_doc,
        text_mappings,
        path,
        "textdocument",
        result,
        class_name="TextDocument",
    )


def compare_property_group(
    expected_group: dict[str, Any],
    parsed_group: dict[str, Any],
    path: str,
    result: ValidationResult,
) -> None:
    """Compare a property group (effects group, transform group, etc.).

    Recursively compares nested properties and property groups.

    Args:
        expected_group: Expected property group from ExtendScript JSON.
        parsed_group: Parsed property group from py_aep.
        path: Dotted path for error messages.
        result: ValidationResult to accumulate differences.
    """
    group_mappings = {
        "name": "name",
        "matchName": "match_name",
        "enabled": "enabled",
        "canSetEnabled": "can_set_enabled",
        "elided": "elided",
        "isEffect": "is_effect",
        "isMask": "is_mask",
        "isModified": "is_modified",
        "propertyDepth": "property_depth",
        "color": "color",
        "maskFeatherFalloff": "mask_feather_falloff",
        "maskMode": "mask_mode",
        "maskMotionBlur": "mask_motion_blur",
        "inverted": "inverted",
        "locked": "locked",
        "rotoBezier": "roto_bezier",
    }

    _compare_fields(
        expected_group,
        parsed_group,
        group_mappings,
        path,
        "properties",
        result,
        class_name="PropertyGroup",
    )

    # Compare propertyIndex (ExtendScript is 1-based, parsed is 0-based)
    result.track_field(
        "PropertyGroup", "property_index", "propertyIndex" in expected_group
    )
    if "propertyIndex" in expected_group:
        exp_pi = expected_group["propertyIndex"]
        parsed_pi = parsed_group.get("property_index")
        if parsed_pi is not None and exp_pi != parsed_pi + 1:
            result.add_diff(
                f"{path}.propertyIndex", exp_pi, parsed_pi + 1, "properties"
            )

    # Compare child properties
    _compare_children_by_match_name(
        expected_group.get("properties", []),
        parsed_group.get("properties", []),
        path,
        result,
    )


def compare_comp_item(
    expected_item: dict[str, Any],
    parsed_comp: dict[str, Any],
    path: str,
    result: ValidationResult,
) -> None:
    """Compare composition item properties."""
    comp_mappings = {
        "name": "name",
        "id": "id",
        "comment": "comment",
        "label": "label",
        "time": "time",
        "duration": "duration",
        "frameRate": "frame_rate",
        "width": "width",
        "height": "height",
        "displayStartTime": "display_start_time",
        "displayStartFrame": "display_start_frame",
        "dropFrame": "drop_frame",
        "bgColor": "bg_color",
        "pixelAspect": "pixel_aspect",
        "shutterPhase": "shutter_phase",
        "shutterAngle": "shutter_angle",
        "motionBlur": "motion_blur",
        "motionBlurAdaptiveSampleLimit": "motion_blur_adaptive_sample_limit",
        "motionBlurSamplesPerFrame": "motion_blur_samples_per_frame",
        "workAreaStart": "work_area_start",
        "workAreaDuration": "work_area_duration",
        "preserveNestedResolution": "preserve_nested_resolution",
        "preserveNestedFrameRate": "preserve_nested_frame_rate",
        "frameBlending": "frame_blending",
        "hideShyLayers": "hide_shy_layers",
        "resolutionFactor": "resolution_factor",
        "draft3d": "draft3d",
        "hasVideo": "has_video",
        "isMediaReplacementCompatible": "is_media_replacement_compatible",
        "renderer": "renderer",
        "motionGraphicsTemplateName": "motion_graphics_template_name",
        "motionGraphicsTemplateControllerCount": "motion_graphics_template_controller_count",
        "motionGraphicsTemplateControllerNames": "motion_graphics_template_controller_names",
    }

    _compare_fields(
        expected_item,
        parsed_comp,
        comp_mappings,
        path,
        "composition",
        result,
        class_name="CompItem",
    )

    # Compare layer counts
    exp_layers = expected_item.get("layers", [])
    parsed_layers = parsed_comp.get("layers", [])
    if len(exp_layers) != len(parsed_layers):
        result.add_diff(
            f"{path}.numLayers", len(exp_layers), len(parsed_layers), "composition"
        )

    # Compare each layer
    comp_duration = expected_item.get("duration", 60.0)
    frame_rate = expected_item.get("frameRate", 24.0)
    for i, (exp_layer, parsed_layer) in enumerate(zip(exp_layers, parsed_layers)):
        compare_layer(
            exp_layer,
            parsed_layer,
            f"{path}.layers[{i}]",
            comp_duration,
            frame_rate,
            result,
        )

    # Compare markers
    _compare_markers(
        expected_item.get("markers", []),
        parsed_comp.get("markers", []),
        path,
        expected_item.get("frameRate", 24.0),
        result,
    )

    # Compare guides
    _compare_guides(
        expected_item.get("guides", []),
        parsed_comp.get("guides", []),
        path,
        result,
    )

    # Compare proxySource
    _compare_proxy_source(expected_item, parsed_comp, path, result)


def compare_folder_hierarchy(
    expected_items: list[dict[str, Any]],
    parsed_items: dict[int, dict[str, Any]],
    result: ValidationResult,
) -> None:
    """Compare folder hierarchy."""
    expected_folders = {}
    for item in expected_items:
        if item.get("itemType") == "FolderItem":
            expected_folders[item["id"]] = item

    parsed_folders = {}
    for item_id, item in parsed_items.items():
        if item.get("type_name") == "Folder":
            parsed_folders[item_id] = item

    for folder_id, exp_folder in expected_folders.items():
        if folder_id not in parsed_folders:
            result.add_diff(
                f"Folder[{exp_folder['name']}]", "exists", "missing", "folders"
            )
        else:
            parsed_folder = parsed_folders[folder_id]
            if exp_folder["name"] != parsed_folder.get("name"):
                result.add_diff(
                    f"Folder[id={folder_id}].name",
                    exp_folder["name"],
                    parsed_folder.get("name"),
                    "folders",
                )


def compare_footage_item(
    expected_item: dict[str, Any],
    parsed_item: dict[str, Any],
    path: str,
    result: ValidationResult,
) -> None:
    """Compare footage item properties and its main source.

    Args:
        expected_item: Expected FootageItem from ExtendScript JSON.
        parsed_item: Parsed FootageItem from py_aep.
        path: Dotted path for error messages.
        result: ValidationResult to accumulate differences.
    """
    footage_mappings = {
        "name": "name",
        "id": "id",
        "comment": "comment",
        "label": "label",
        "time": "time",
        "duration": "duration",
        "frameRate": "frame_rate",
        "width": "width",
        "height": "height",
        "pixelAspect": "pixel_aspect",
        "footageMissing": "footage_missing",
        "hasVideo": "has_video",
        "isMediaReplacementCompatible": "is_media_replacement_compatible",
    }

    _compare_fields(
        expected_item,
        parsed_item,
        footage_mappings,
        path,
        "footage",
        result,
        class_name="FootageItem",
    )

    # Compare mainSource (FootageSource fields)
    exp_source = expected_item.get("mainSource")
    parsed_source = parsed_item.get("main_source")
    if exp_source and parsed_source:
        source_path = f"{path}.mainSource"

        source_mappings = {
            "alphaMode": "alpha_mode",
            "displayFrameRate": "display_frame_rate",
            "fieldSeparationType": "field_separation_type",
            "hasAlpha": "has_alpha",
            "highQualityFieldSeparation": "high_quality_field_separation",
            "invertAlpha": "invert_alpha",
            "isStill": "is_still",
            "loop": "loop",
            "nativeFrameRate": "native_frame_rate",
            "premulColor": "premul_color",
            "removePulldown": "remove_pulldown",
            "color": "color",
        }

        _compare_fields(
            exp_source,
            parsed_source,
            source_mappings,
            source_path,
            "footage",
            result,
            class_name="FootageSource",
        )

        # AE returns native_frame_rate when conformFrameRate is 0
        result.track_field(
            "FootageSource",
            "conform_frame_rate",
            "conformFrameRate" in exp_source,
        )
        exp_cfr = exp_source.get("conformFrameRate")
        parsed_cfr = parsed_source.get("conform_frame_rate", 0)
        if exp_cfr is not None:
            if not compare_values(exp_cfr, parsed_cfr):
                # When parsed conform is 0, AE may report native_frame_rate
                native = parsed_source.get("native_frame_rate", 0)
                if parsed_cfr == 0 and compare_values(exp_cfr, native):
                    pass  # AE reported native rate as conform rate
                else:
                    result.add_diff(
                        f"{source_path}.conformFrameRate",
                        exp_cfr,
                        parsed_cfr,
                        "footage",
                    )

        # Track manually-compared fields
        result.track_field("FootageSource", "file", "filePath" in exp_source)
        result.track_field(
            "FootageSource",
            "missing_footage_path",
            "missingFootagePath" in exp_source,
        )
        # FileSource-specific fields
        if "filePath" in exp_source:
            exp_file = exp_source["filePath"]
            parsed_file = parsed_source.get("file", "")
            # Compare only the filename portion. PureWindowsPath splits on
            # both / and \ on every host OS (AE stores Windows-style paths,
            # and a parsed sequence frame path mixes the two); plain Path
            # fails to split backslashes when the validator runs on POSIX.
            if exp_file and parsed_file:
                exp_name = PureWindowsPath(exp_file).name
                parsed_name = PureWindowsPath(parsed_file).name
                if exp_name != parsed_name:
                    result.add_diff(
                        f"{source_path}.fileName",
                        exp_name,
                        parsed_name,
                        "footage",
                    )

        if "missingFootagePath" in exp_source:
            exp_missing = exp_source["missingFootagePath"]
            parsed_missing = parsed_source.get("missing_footage_path", "")
            if exp_missing and exp_missing != parsed_missing:
                result.add_diff(
                    f"{source_path}.missingFootagePath",
                    exp_missing,
                    parsed_missing,
                    "footage",
                )

    # Compare proxySource
    _compare_proxy_source(expected_item, parsed_item, path, result)


def compare_settings(
    expected_settings: dict[str, Any],
    parsed_settings: dict[str, Any] | None,
    path: str,
    result: ValidationResult,
) -> None:
    """Compare render settings.

    Render settings are now stored as raw integer values with ExtendScript keys.
    """
    if parsed_settings is None:
        result.add_diff(f"{path}", "exists", "missing", "renderqueue")
        return

    # Map expected JSON keys to parsed keys (both use AE getSettings keys)
    settings_mappings: dict[str, str] = {}
    for key in (
        "Quality",
        "Effects",
        "Proxy Use",
        "Motion Blur",
        "Frame Blending",
        "Field Render",
        "Guide Layers",
        "Solo Switches",
        "Color Depth",
        "Time Span",
        "Time Span Start",
        "Time Span Duration",
        "Time Span End",
        "Use comp's frame rate",
        "Use this frame rate",
        "Frame Rate",
        "Skip Existing Files",
        "Disk Cache",
        "3:2 Pulldown",
    ):
        settings_mappings[key] = key

    _compare_fields(
        expected_settings,
        parsed_settings,
        settings_mappings,
        path,
        "renderqueue",
        result,
        class_name="RenderSettings",
    )


def compare_output_module_settings(
    expected_settings: dict[str, Any],
    parsed_settings: dict[str, Any] | None,
    path: str,
    result: ValidationResult,
) -> None:
    """Compare output module settings.

    Output module settings are stored as a dict with ExtendScript keys.
    """
    if expected_settings is None:
        return
    if parsed_settings is None:
        result.add_diff(f"{path}", "exists", "missing", "renderqueue")
        return

    # Compare output module settings with identical keys
    om_settings_mappings: dict[str, str] = {}
    for key in (
        "Video Output",
        "Output Audio",
        "Format",
        "Channels",
        "Depth",
        "Color",
        "Lock Aspect Ratio",
        "Resize",
        "Resize Quality",
        "Audio Bit Depth",
        "Audio Channels",
        "Audio Sample Rate",
        "Include Source XMP Metadata",
        "Include Project Link",
        "Post-Render Action",
        "Use Region of Interest",
        "Use Comp Frame Number",
        "Starting #",
        "Crop",
    ):
        om_settings_mappings[key] = key

    _compare_fields(
        expected_settings,
        parsed_settings,
        om_settings_mappings,
        path,
        "renderqueue",
        result,
        class_name="OMSettings",
    )


def compare_render_queue(
    expected_rq: dict[str, Any],
    parsed_rq: dict[str, Any],
    result: ValidationResult,
    verbose: bool = False,
) -> None:
    """Compare render queue items."""
    expected_items = expected_rq.get("items", [])
    parsed_items = parsed_rq.get("items", [])

    if len(expected_items) != len(parsed_items):
        result.add_diff(
            "RenderQueue.numItems",
            len(expected_items),
            len(parsed_items),
            "renderqueue",
        )
        if verbose:
            print(
                f"  Item count mismatch: expected {len(expected_items)}, got {len(parsed_items)}"
            )

    # Compare each render queue item
    for i, exp_item in enumerate(expected_items):
        if i >= len(parsed_items):
            result.add_diff(f"RenderQueueItem[{i}]", "exists", "missing", "renderqueue")
            continue

        parsed_item = parsed_items[i]
        path = f"RenderQueueItem[{i}]"

        # Compare RQ item-level fields
        rqi_mappings = {
            "status": "status",
            "render": "render",
            "skipFrames": "skip_frames",
            "logType": "log_type",
            "elapsedSeconds": "elapsed_seconds",
            "comment": "comment",
            "compName": "comp_name",
            "queueItemNotify": "queue_item_notify",
            "timeSpanStart": "time_span_start",
            "timeSpanDuration": "time_span_duration",
        }
        _compare_fields(
            exp_item,
            parsed_item,
            rqi_mappings,
            path,
            "renderqueue",
            result,
            class_name="RenderQueueItem",
        )

        # Compare render settings
        if "settings" in exp_item:
            compare_settings(
                exp_item["settings"],
                parsed_item.get("settings"),
                f"{path}.settings",
                result,
            )

        # Compare output modules
        exp_oms = exp_item.get("outputModules", [])
        parsed_oms = parsed_item.get("output_modules", [])

        if len(exp_oms) != len(parsed_oms):
            result.add_diff(
                f"{path}.numOutputModules",
                len(exp_oms),
                len(parsed_oms),
                "renderqueue",
            )

        for j, exp_om in enumerate(exp_oms):
            if j >= len(parsed_oms):
                result.add_diff(
                    f"{path}.outputModule[{j}]", "exists", "missing", "renderqueue"
                )
                continue

            parsed_om = parsed_oms[j]
            om_path = f"{path}.outputModule[{j}]"

            # Compare output module-level fields
            om_mappings = {
                "name": "name",
                "includeSourceXMP": "include_source_xmp",
                "postRenderAction": "post_render_action",
            }
            _compare_fields(
                exp_om,
                parsed_om,
                om_mappings,
                om_path,
                "renderqueue",
                result,
                class_name="OutputModule",
            )

            # Compare output module file (path comparison)
            result.track_field("OutputModule", "file", "file" in exp_om)
            if "file" in exp_om:
                exp_file = exp_om["file"]
                parsed_file = parsed_om.get("file", "")
                if exp_file and parsed_file:
                    # See the footage-source note: PureWindowsPath keeps
                    # basename extraction host-OS-independent.
                    exp_name = PureWindowsPath(exp_file).name
                    parsed_name = PureWindowsPath(str(parsed_file)).name
                    if exp_name != parsed_name:
                        result.add_diff(
                            f"{om_path}.fileName",
                            exp_name,
                            parsed_name,
                            "renderqueue",
                        )

            # Compare output module settings
            if "settings" in exp_om:
                compare_output_module_settings(
                    exp_om["settings"],
                    parsed_om["settings"],
                    f"{om_path}.settings",
                    result,
                )


def compare_viewer(
    expected_viewer: dict[str, Any],
    parsed_viewer: dict[str, Any],
    result: ValidationResult,
) -> None:
    """Compare active viewer properties.

    Args:
        expected_viewer: Expected activeViewer from ExtendScript JSON.
        parsed_viewer: Parsed active_viewer dict from py_aep.
        result: ValidationResult to accumulate differences.
    """
    viewer_mappings: dict[str, str] = {
        "type": "type",
    }
    _compare_fields(
        expected_viewer,
        parsed_viewer,
        viewer_mappings,
        "Viewer",
        "viewer",
        result,
        class_name="Viewer",
    )

    exp_views = expected_viewer.get("views", [])
    parsed_views: list[dict[str, Any]] = parsed_viewer.get("views", [])
    if len(exp_views) != len(parsed_views):
        result.add_diff(
            "Viewer.views.length",
            len(exp_views),
            len(parsed_views),
            "viewer",
        )

    for i, (exp_view, parsed_view) in enumerate(zip(exp_views, parsed_views)):
        path = f"Viewer.views[{i}]"

        exp_opts = exp_view.get("options", {})
        parsed_opts = parsed_view.get("options", {})
        opts_path = f"{path}.options"
        opts_mappings: dict[str, str] = {
            "channels": "channels",
            "checkerboards": "checkerboards",
            "exposure": "exposure",
            "fastPreview": "fast_preview",
            "zoom": "zoom",
            "guidesVisibility": "guides_visibility",
            "guidesSnap": "guides_snap",
            "guidesLocked": "guides_locked",
            "rulers": "rulers",
        }
        _compare_fields(
            exp_opts,
            parsed_opts,
            opts_mappings,
            opts_path,
            "viewer",
            result,
            class_name="ViewOptions",
        )


def validate_aep(
    aep_path: Path,
    json_path: Path,
    verbose: bool = False,
    category_filter: str | None = None,
) -> ValidationResult:
    """
    Validate parsed AEP against expected JSON.

    Args:
        aep_path: Path to .aep file.
        json_path: Path to expected JSON (from ExtendScript export).
        verbose: Whether to print detailed progress.
        category_filter: Only show differences from this category.

    Returns:
        ValidationResult containing all differences.
    """
    result = ValidationResult()

    # Parse AEP
    if verbose:
        print(f"Parsing: {aep_path.name}")
    app = parse(aep_path)
    project = app.project
    parsed = to_dict(project)

    # Load expected JSON
    with json_path.open(encoding="utf-8") as f:
        expected = json.load(f)

    # Compare project-level properties
    if verbose:
        print("\n=== Comparing Project Properties ===")
    compare_project_level(expected, parsed, result)

    # Get expected items
    expected_items = expected.get("items", [])
    comps = [i for i in expected_items if i.get("itemType") == "CompItem"]

    # Compare compositions
    if verbose:
        print("\n=== Comparing Compositions ===")
    parsed_by_id = {comp.id: to_dict(comp) for comp in project.compositions}

    for exp_item in comps:
        item_id = exp_item["id"]
        item_name = exp_item["name"]

        if item_id not in parsed_by_id:
            result.add_diff(f"Comp[{item_name}]", "exists", "missing", "composition")
            if verbose:
                print(f"  {item_name} (id={item_id}): MISSING!")
            continue

        parsed_comp = parsed_by_id[item_id]
        before_count = len(result)
        compare_comp_item(exp_item, parsed_comp, f"Comp[{item_name}]", result)

        if verbose:
            diff_count = len(result) - before_count
            if diff_count > 0:
                print(f"  {item_name} (id={item_id}): {diff_count} differences")
            else:
                print(f"  {item_name} (id={item_id}): OK")

    # Compare folder hierarchy
    if verbose:
        print("\n=== Comparing Folder Hierarchy ===")
    compare_folder_hierarchy(expected_items, parsed.get("items", {}), result)

    # Compare footage items
    if verbose:
        print("\n=== Comparing Footage Items ===")
    expected_footage = [i for i in expected_items if i.get("itemType") == "FootageItem"]
    parsed_items_dict = parsed.get("items", {})
    parsed_footage_by_id = {
        item_id: item
        for item_id, item in parsed_items_dict.items()
        if item.get("type_name") == "Footage"
    }

    for exp_fi in expected_footage:
        fi_id = exp_fi["id"]
        fi_name = exp_fi["name"]

        parsed_fi = parsed_footage_by_id.get(fi_id)
        if parsed_fi is None:
            result.add_diff(f"Footage[{fi_name}]", "exists", "missing", "footage")
            if verbose:
                print(f"  {fi_name} (id={fi_id}): MISSING!")
            continue

        before_count = len(result)
        compare_footage_item(exp_fi, parsed_fi, f"Footage[{fi_name}]", result)

        if verbose:
            diff_count = len(result) - before_count
            if diff_count > 0:
                print(f"  {fi_name} (id={fi_id}): {diff_count} differences")
            else:
                print(f"  {fi_name} (id={fi_id}): OK")

    # Compare render queue
    if verbose:
        print("\n=== Comparing Render Queue ===")
    expected_rq = expected.get("renderQueue", {})
    compare_render_queue(expected_rq, parsed.get("render_queue", {}), result, verbose)

    # Compare active viewer
    expected_viewer = expected.get("activeViewer")
    if expected_viewer is not None and app.active_viewer is not None:
        if verbose:
            print("\n=== Comparing Viewer ===")
        parsed_viewer = to_dict(app.active_viewer)
        compare_viewer(expected_viewer, parsed_viewer, result)
        if verbose:
            print("  Done")
    elif expected_viewer is not None and verbose:
        print("\n=== Comparing Viewer ===")
        print("  Skipped (no viewer data in binary)")

    return result


def print_results(
    result: ValidationResult, verbose: bool = False, category_filter: str | None = None
) -> None:
    """Print validation results."""
    print("\n" + "=" * 60)

    if not result.differences:
        print("SUCCESS: All parsed values match expected values!")
        return

    filtered_diffs = result.differences
    if category_filter:
        # Filter by category prefix
        filtered_diffs = [
            d for d in result.differences if category_filter.lower() in d.lower()
        ]

    print(f"TOTAL DIFFERENCES FOUND: {len(result.differences)}")

    if category_filter:
        print(f"(Showing {len(filtered_diffs)} matching filter '{category_filter}')")

    print("\nDifferences by category:")
    for cat, count in sorted(result.categories.items()):
        print(f"  {cat}: {count}")

    if verbose and filtered_diffs:
        print("\nAll differences:")
        for d in filtered_diffs[:200]:  # Limit output
            print(f"  {d}")
        if len(filtered_diffs) > 200:
            print(f"  ... and {len(filtered_diffs) - 200} more")


def print_coverage(result: ValidationResult) -> None:
    """Print field coverage report."""
    compared = sorted(result.compared_fields)
    not_compared = sorted(result.defined_fields - result.compared_fields)

    print(f"\n{'=' * 60}")
    print("FIELD COVERAGE REPORT")
    print(f"{'=' * 60}")
    print(f"\nCompared ({len(compared)}):\n  " + "\n  ".join(compared))
    print(f"\nNot compared ({len(not_compared)}):")
    if not_compared:
        print("  " + "\n  ".join(not_compared))
    else:
        print("  (none)")


def main(args: list[str] | None = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate parsed AEP values against expected JSON from ExtendScript export.",
    )
    parser.add_argument("aep_file", type=Path, help="Path to .aep file")
    parser.add_argument("json_file", type=Path, help="Path to expected JSON file")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print detailed progress"
    )
    parser.add_argument(
        "-c",
        "--category",
        choices=[
            "project",
            "composition",
            "layers",
            "properties",
            "markers",
            "folders",
            "footage",
            "keyframes",
            "textdocument",
            "renderqueue",
            "viewer",
        ],
        help="Filter differences by category",
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Print field coverage report (compared vs not-compared fields)",
    )

    parsed_args = parser.parse_args(args)

    if not parsed_args.aep_file.exists():
        print(f"Error: AEP file not found: {parsed_args.aep_file}")
        return 1

    if not parsed_args.json_file.exists():
        print(f"Error: JSON file not found: {parsed_args.json_file}")
        return 1

    print(f"Validating: {parsed_args.aep_file.name}")
    print(f"Expected:   {parsed_args.json_file.name}")

    result = validate_aep(
        parsed_args.aep_file,
        parsed_args.json_file,
        verbose=parsed_args.verbose,
        category_filter=parsed_args.category,
    )

    print_results(
        result, verbose=parsed_args.verbose, category_filter=parsed_args.category
    )

    if parsed_args.coverage:
        print_coverage(result)

    return 0 if not result.differences else 1


if __name__ == "__main__":
    sys.exit(main())
