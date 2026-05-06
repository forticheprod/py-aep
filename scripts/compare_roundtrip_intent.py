# ruff: noqa: UP006, UP032, UP045

"""Compare roundtrip generator intent vs AE JSON exports vs py_aep parse.

This script replays each scenario from `generate_roundtrip_files.py` in memory to
capture the intended values, then compares those values against:

- the `.json` exported later from After Effects
- the values parsed from the saved roundtrip `.aep` with `py_aep`

By default it prints only mismatches. Use `--show-ok` to also print scenarios
that fully match.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Mapping, Optional, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(ROOT / "src"))

import generate_roundtrip_files as generator  # noqa: E402

from py_aep import parse as parse_aep  # noqa: E402

if TYPE_CHECKING:
    from py_aep.models.application import Application

JsonDoc = Mapping[str, Any]
AppGetter = Callable[[Any], Any]
JsonGetter = Callable[[JsonDoc], Any]
DEFAULT_TOLERANCE = 1e-6
JSON_AV_LAYER_TYPES = ("AVLayer", "TextLayer", "ShapeLayer")


@dataclass(frozen=True)
class FieldCheck:
    """One expected field comparison for a roundtrip scenario."""

    label: str
    get_app: AppGetter
    get_json: Optional[JsonGetter] = None
    tolerance: float = DEFAULT_TOLERANCE


@dataclass(frozen=True)
class ObservedValue:
    """Observed value or lookup failure from one comparison source."""

    kind: str
    value: Any = None
    detail: str = ""


def _snake_to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return _normalize_value(value.value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_normalize_value(item) for item in value]
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _normalize_value(item)
            for key, item in value.items()
        }
    return value


def _values_equal(left: Any, right: Any, tolerance: float) -> bool:
    if isinstance(left, bool) and isinstance(right, bool):
        return True if left == right else False

    if isinstance(left, bool) or isinstance(right, bool):
        return False

    if left is None or right is None:
        return left is None and right is None

    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(
            _to_float(left),
            _to_float(right),
            rel_tol=tolerance,
            abs_tol=tolerance,
        )

    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return False
        return all(
            _values_equal(left_item, right_item, tolerance)
            for left_item, right_item in zip(left, right)
        )

    if isinstance(left, dict) and isinstance(right, dict):
        if set(left.keys()) != set(right.keys()):
            return False
        return all(
            _values_equal(left[key], right[key], tolerance)
            for key in left
        )

    return True if left == right else False


def _to_float(value: Any) -> float:
    return float(value)


def _observe_app(getter: AppGetter, app: Application) -> ObservedValue:
    try:
        return ObservedValue("value", _normalize_value(getter(app)))
    except Exception as exc:  # noqa: BLE001
        return ObservedValue("error", detail=f"{type(exc).__name__}: {exc}")


def _observe_json(
    getter: Optional[JsonGetter],
    json_doc: JsonDoc,
) -> ObservedValue:
    if getter is None:
        return ObservedValue("na", detail="Not exported in AE JSON")
    try:
        return ObservedValue("value", _normalize_value(getter(json_doc)))
    except Exception as exc:  # noqa: BLE001
        return ObservedValue("error", detail=f"{type(exc).__name__}: {exc}")


def _observed_equal(
    expected: ObservedValue,
    actual: ObservedValue,
    tolerance: float,
) -> bool:
    if expected.kind != "value" or actual.kind != "value":
        return False
    return _values_equal(expected.value, actual.value, tolerance)


def _format_observed(observed: ObservedValue) -> str:
    if observed.kind == "value":
        try:
            return json.dumps(observed.value, ensure_ascii=False, sort_keys=True)
        except TypeError:
            return repr(observed.value)
    if observed.kind == "na":
        return "N/A"
    return f"<{observed.detail}>"


def _json_items(doc: JsonDoc) -> Sequence[JsonDoc]:
    items = doc.get("items")
    if not isinstance(items, list):
        raise KeyError("items")
    result = []
    for item in items:
        if isinstance(item, dict):
            result.append(item)
    return result


def _json_find_item(doc: JsonDoc, name: str) -> JsonDoc:
    for item in _json_items(doc):
        if item.get("name") == name:
            return item
    raise KeyError(f"Item not found: {name}")


def _json_find_comp(doc: JsonDoc, name: str) -> JsonDoc:
    comp = _json_find_item(doc, name)
    if comp.get("itemType") != "CompItem":
        raise TypeError(f"Item is not a CompItem: {name}")
    return comp


def _json_find_folder(doc: JsonDoc, name: str) -> JsonDoc:
    folder = _json_find_item(doc, name)
    if folder.get("itemType") != "FolderItem":
        raise TypeError(f"Item is not a FolderItem: {name}")
    return folder


def _json_get_av_layers(doc: JsonDoc, comp_name: str) -> List[JsonDoc]:
    comp = _json_find_comp(doc, comp_name)
    layers = comp.get("layers")
    if not isinstance(layers, list):
        raise KeyError("layers")
    result = []
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        if layer.get("layerType") in JSON_AV_LAYER_TYPES:
            result.append(layer)
    return result


def _json_find_property_group(
    properties: Sequence[JsonDoc],
    match_name: str,
) -> JsonDoc:
    for prop in properties:
        if prop.get("matchName") == match_name:
            return prop
    raise KeyError(f"Property group not found: {match_name}")


def _json_get_first_mask(doc: JsonDoc, comp_name: str) -> JsonDoc:
    comp = _json_find_comp(doc, comp_name)
    layers = comp.get("layers")
    if not isinstance(layers, list):
        raise KeyError("layers")

    for layer in layers:
        if not isinstance(layer, dict):
            continue
        properties = layer.get("properties")
        if not isinstance(properties, list):
            continue
        typed_properties = [prop for prop in properties if isinstance(prop, dict)]
        masks_group = _json_find_property_group(
            typed_properties,
            "ADBE Mask Parade",
        )
        masks = masks_group.get("properties")
        if isinstance(masks, list) and masks:
            typed_masks = [mask for mask in masks if isinstance(mask, dict)]
            if not typed_masks:
                continue
            first_mask = typed_masks[0]
            if not isinstance(first_mask, dict):
                raise TypeError("First mask is not an object")
            return first_mask

    raise KeyError(f"No mask found in {comp_name}")


def _json_get_solid_footages(doc: JsonDoc) -> List[JsonDoc]:
    solids = []
    for item in _json_items(doc):
        if item.get("itemType") != "FootageItem":
            continue
        main_source = item.get("mainSource")
        if not isinstance(main_source, dict):
            continue
        if main_source.get("sourceType") == "SolidSource":
            solids.append(item)
    return solids


def _json_get_render_queue_item(doc: JsonDoc, index: int = 0) -> JsonDoc:
    render_queue = doc.get("renderQueue")
    if not isinstance(render_queue, dict):
        raise KeyError("renderQueue")
    items = render_queue.get("items")
    if not isinstance(items, list):
        raise KeyError("renderQueue.items")
    item = items[index]
    if not isinstance(item, dict):
        raise TypeError("Render queue item is not an object")
    return item


def _json_get_output_module(
    doc: JsonDoc,
    rq_index: int = 0,
    om_index: int = 0,
) -> JsonDoc:
    rq_item = _json_get_render_queue_item(doc, rq_index)
    output_modules = rq_item.get("outputModules")
    if not isinstance(output_modules, list):
        raise KeyError("outputModules")
    output_module = output_modules[om_index]
    if not isinstance(output_module, dict):
        raise TypeError("Output module is not an object")
    return output_module


def _make_root_json_getter(key: str) -> JsonGetter:
    def getter(doc: JsonDoc) -> Any:
        return doc[key]

    return getter


def _make_project_attr_getter(attr: str) -> AppGetter:
    def getter(app: Application) -> Any:
        return getattr(app.project, attr)

    return getter


def _make_app_attr_getter(attr: str) -> AppGetter:
    def getter(app: Application) -> Any:
        return getattr(app, attr)

    return getter


def _make_comp_attr_getter(comp_name: str, attr: str) -> AppGetter:
    def getter(app: Application) -> Any:
        return getattr(generator._get_comp(app, comp_name), attr)

    return getter


def _make_comp_json_getter(comp_name: str, key: str) -> JsonGetter:
    def getter(doc: JsonDoc) -> Any:
        return _json_find_comp(doc, comp_name)[key]

    return getter


def _make_av_layer_attr_getter(comp_name: str, index: int, attr: str) -> AppGetter:
    def getter(app: Application) -> Any:
        comp = generator._get_comp(app, comp_name)
        av_layers = generator._get_av_layers(comp, minimum=index + 1)
        return getattr(av_layers[index], attr)

    return getter


def _make_av_layer_json_getter(comp_name: str, index: int, key: str) -> JsonGetter:
    def getter(doc: JsonDoc) -> Any:
        return _json_get_av_layers(doc, comp_name)[index][key]

    return getter


def _make_item_attr_getter(item_name: str, attr: str) -> AppGetter:
    def getter(app: Application) -> Any:
        return getattr(generator._get_item(app, item_name), attr)

    return getter


def _make_item_json_getter(item_name: str, key: str) -> JsonGetter:
    def getter(doc: JsonDoc) -> Any:
        return _json_find_item(doc, item_name)[key]

    return getter


def _make_folder_attr_getter(folder_name: str, attr: str) -> AppGetter:
    def getter(app: Application) -> Any:
        return getattr(generator._get_folder(app, folder_name), attr)

    return getter


def _make_folder_json_getter(folder_name: str, key: str) -> JsonGetter:
    def getter(doc: JsonDoc) -> Any:
        return _json_find_folder(doc, folder_name)[key]

    return getter


def _make_mask_attr_getter(comp_name: str, attr: str) -> AppGetter:
    def getter(app: Application) -> Any:
        comp = generator._get_comp(app, comp_name)
        return getattr(generator._get_first_mask(comp), attr)

    return getter


def _make_mask_json_getter(comp_name: str, key: str) -> JsonGetter:
    def getter(doc: JsonDoc) -> Any:
        return _json_get_first_mask(doc, comp_name)[key]

    return getter


def _make_solid_source_attr_getter(index: int, attr: str) -> AppGetter:
    def getter(app: Application) -> Any:
        solid_sources = generator._get_solid_footages(app, minimum=index + 1)
        return getattr(solid_sources[index][1], attr)

    return getter


def _make_solid_source_json_getter(index: int, key: str) -> JsonGetter:
    def getter(doc: JsonDoc) -> Any:
        return _json_get_solid_footages(doc)[index]["mainSource"][key]

    return getter


def _make_render_queue_attr_getter(attr: str) -> AppGetter:
    def getter(app: Application) -> Any:
        return getattr(generator._get_render_queue_item(app), attr)

    return getter


def _make_render_queue_json_getter(key: str) -> JsonGetter:
    def getter(doc: JsonDoc) -> Any:
        return _json_get_render_queue_item(doc)[key]

    return getter


def _make_output_module_attr_getter(attr: str) -> AppGetter:
    def getter(app: Application) -> Any:
        return getattr(generator._get_render_queue_item(app).output_modules[0], attr)

    return getter


def _make_output_module_json_getter(key: str) -> JsonGetter:
    def getter(doc: JsonDoc) -> Any:
        return _json_get_output_module(doc)[key]

    return getter


def _field(
    label: str,
    get_app: AppGetter,
    get_json: Optional[JsonGetter] = None,
    tolerance: float = DEFAULT_TOLERANCE,
) -> FieldCheck:
    return FieldCheck(label, get_app, get_json, tolerance)


def _project_field(
    attr: str,
    json_key: Optional[str] = None,
    use_json: bool = True,
    tolerance: float = DEFAULT_TOLERANCE,
) -> FieldCheck:
    key = json_key or _snake_to_camel(attr.lstrip("_"))
    return _field(
        "project.{}".format(attr),
        _make_project_attr_getter(attr),
        _make_root_json_getter(key) if use_json else None,
        tolerance,
    )


def _app_field(
    attr: str,
    json_key: Optional[str] = None,
    use_json: bool = True,
    tolerance: float = DEFAULT_TOLERANCE,
) -> FieldCheck:
    key = json_key or _snake_to_camel(attr.lstrip("_"))
    return _field(
        "application.{}".format(attr),
        _make_app_attr_getter(attr),
        _make_root_json_getter(key) if use_json else None,
        tolerance,
    )


def _comp_field(
    comp_name: str,
    attr: str,
    json_key: Optional[str] = None,
    use_json: bool = True,
    tolerance: float = DEFAULT_TOLERANCE,
) -> FieldCheck:
    key = json_key or _snake_to_camel(attr.lstrip("_"))
    return _field(
        "{}.{}".format(comp_name, attr),
        _make_comp_attr_getter(comp_name, attr),
        _make_comp_json_getter(comp_name, key) if use_json else None,
        tolerance,
    )


def _av_layer_field(
    comp_name: str,
    index: int,
    attr: str,
    json_key: Optional[str] = None,
    use_json: bool = True,
    tolerance: float = DEFAULT_TOLERANCE,
) -> FieldCheck:
    key = json_key or _snake_to_camel(attr.lstrip("_"))
    return _field(
        "{}.av_layer[{}].{}".format(comp_name, index, attr),
        _make_av_layer_attr_getter(comp_name, index, attr),
        _make_av_layer_json_getter(comp_name, index, key) if use_json else None,
        tolerance,
    )


def _item_field(
    item_name: str,
    attr: str,
    json_key: Optional[str] = None,
    use_json: bool = True,
    tolerance: float = DEFAULT_TOLERANCE,
) -> FieldCheck:
    key = json_key or _snake_to_camel(attr.lstrip("_"))
    return _field(
        "item[{}].{}".format(item_name, attr),
        _make_item_attr_getter(item_name, attr),
        _make_item_json_getter(item_name, key) if use_json else None,
        tolerance,
    )


def _folder_field(
    folder_name: str,
    attr: str,
    json_key: Optional[str] = None,
    use_json: bool = True,
    tolerance: float = DEFAULT_TOLERANCE,
) -> FieldCheck:
    key = json_key or _snake_to_camel(attr.lstrip("_"))
    return _field(
        "folder[{}].{}".format(folder_name, attr),
        _make_folder_attr_getter(folder_name, attr),
        _make_folder_json_getter(folder_name, key) if use_json else None,
        tolerance,
    )


def _mask_field(
    comp_name: str,
    attr: str,
    json_key: Optional[str] = None,
    use_json: bool = True,
    tolerance: float = DEFAULT_TOLERANCE,
) -> FieldCheck:
    key = json_key or _snake_to_camel(attr.lstrip("_"))
    return _field(
        "{}.first_mask.{}".format(comp_name, attr),
        _make_mask_attr_getter(comp_name, attr),
        _make_mask_json_getter(comp_name, key) if use_json else None,
        tolerance,
    )


def _solid_source_field(
    index: int,
    attr: str,
    json_key: Optional[str] = None,
    use_json: bool = True,
    tolerance: float = DEFAULT_TOLERANCE,
) -> FieldCheck:
    key = json_key or _snake_to_camel(attr.lstrip("_"))
    return _field(
        "solid_source[{}].{}".format(index, attr),
        _make_solid_source_attr_getter(index, attr),
        _make_solid_source_json_getter(index, key) if use_json else None,
        tolerance,
    )


def _render_queue_item_field(
    attr: str,
    json_key: Optional[str] = None,
    use_json: bool = True,
    tolerance: float = DEFAULT_TOLERANCE,
) -> FieldCheck:
    key = json_key or _snake_to_camel(attr.lstrip("_"))
    return _field(
        "render_queue[0].{}".format(attr),
        _make_render_queue_attr_getter(attr),
        _make_render_queue_json_getter(key) if use_json else None,
        tolerance,
    )


def _output_module_field(
    attr: str,
    json_key: Optional[str] = None,
    use_json: bool = True,
    tolerance: float = DEFAULT_TOLERANCE,
) -> FieldCheck:
    key = json_key or _snake_to_camel(attr.lstrip("_"))
    return _field(
        "render_queue[0].output_module[0].{}".format(attr),
        _make_output_module_attr_getter(attr),
        _make_output_module_json_getter(key) if use_json else None,
        tolerance,
    )


SCENARIO_CHECKS = {
    "comp_settings": [
        _comp_field(generator.DROP_FRAME_COMP_NAME, "bg_color"),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "width"),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "height"),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "pixel_aspect"),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "renderer"),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "resolution_factor"),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "preserve_nested_frame_rate"),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "preserve_nested_resolution"),
        _comp_field(
            generator.DROP_FRAME_COMP_NAME,
            "motion_blur_adaptive_sample_limit",
        ),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "motion_blur_samples_per_frame"),
    ],
    "comp_timing": [
        _comp_field(generator.DROP_FRAME_COMP_NAME, "frame_rate"),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "display_start_frame"),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "display_start_time"),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "duration"),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "work_area_start"),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "work_area_duration"),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "time"),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "drop_frame"),
    ],
    "comp_flags": [
        _comp_field(generator.DROP_FRAME_COMP_NAME, "motion_blur"),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "frame_blending"),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "hide_shy_layers"),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "shutter_angle"),
        _comp_field(generator.DROP_FRAME_COMP_NAME, "shutter_phase"),
        _comp_field(generator.HIGH_FPS_COMP_NAME, "motion_blur"),
        _comp_field(generator.HIGH_FPS_COMP_NAME, "frame_blending"),
        _comp_field(generator.HIGH_FPS_COMP_NAME, "hide_shy_layers"),
        _comp_field(generator.HIGH_FPS_COMP_NAME, "shutter_angle"),
        _comp_field(generator.HIGH_FPS_COMP_NAME, "shutter_phase"),
    ],
    "layer_flags": [
        _av_layer_field(generator.DROP_FRAME_COMP_NAME, 0, "comment"),
        _av_layer_field(generator.DROP_FRAME_COMP_NAME, 0, "locked"),
        _av_layer_field(generator.DROP_FRAME_COMP_NAME, 0, "shy"),
        _av_layer_field(generator.DROP_FRAME_COMP_NAME, 0, "solo"),
        _av_layer_field(generator.DROP_FRAME_COMP_NAME, 0, "enabled"),
        _av_layer_field(generator.DROP_FRAME_COMP_NAME, 0, "label"),
        _av_layer_field(generator.DROP_FRAME_COMP_NAME, 0, "adjustment_layer"),
        _av_layer_field(generator.DROP_FRAME_COMP_NAME, 0, "effects_active"),
        _av_layer_field(generator.DROP_FRAME_COMP_NAME, 0, "motion_blur"),
        _av_layer_field(
            generator.DROP_FRAME_COMP_NAME,
            0,
            "collapse_transformation",
        ),
        _av_layer_field(generator.DROP_FRAME_COMP_NAME, 0, "guide_layer"),
        _av_layer_field(
            generator.DROP_FRAME_COMP_NAME,
            0,
            "preserve_transparency",
        ),
        _av_layer_field(generator.DROP_FRAME_COMP_NAME, 0, "quality"),
        _av_layer_field(generator.DROP_FRAME_COMP_NAME, 0, "sampling_quality"),
        _av_layer_field(generator.DROP_FRAME_COMP_NAME, 0, "blending_mode"),
        _av_layer_field(generator.DROP_FRAME_COMP_NAME, 0, "audio_enabled"),
    ],
    "layer_timing": [
        _av_layer_field(generator.MAIN_COMP_NAME, 0, "auto_orient"),
        _av_layer_field(generator.MAIN_COMP_NAME, 1, "in_point"),
        _av_layer_field(generator.MAIN_COMP_NAME, 2, "out_point"),
        _av_layer_field(generator.MAIN_COMP_NAME, 3, "start_time"),
        _av_layer_field(generator.MAIN_COMP_NAME, 4, "stretch"),
        _av_layer_field(generator.MAIN_COMP_NAME, 5, "comment"),
        _av_layer_field(generator.MAIN_COMP_NAME, 5, "shy"),
        _av_layer_field(generator.MAIN_COMP_NAME, 5, "label"),
        _av_layer_field(generator.MAIN_COMP_NAME, 5, "frame_blending_type"),
        _av_layer_field(generator.MAIN_COMP_NAME, 6, "comment"),
        _av_layer_field(generator.MAIN_COMP_NAME, 6, "shy"),
        _av_layer_field(generator.MAIN_COMP_NAME, 6, "label"),
        _av_layer_field(generator.MAIN_COMP_NAME, 6, "frame_blending_type"),
        _av_layer_field(generator.MAIN_COMP_NAME, 7, "comment"),
        _av_layer_field(generator.MAIN_COMP_NAME, 7, "shy"),
        _av_layer_field(generator.MAIN_COMP_NAME, 7, "label"),
        _av_layer_field(generator.MAIN_COMP_NAME, 7, "frame_blending_type"),
    ],
    "project_settings": [
        _project_field("bits_per_channel"),
        _project_field("time_display_type"),
        _project_field("frames_count_type"),
        _project_field("display_start_frame"),
        _project_field("transparency_grid_thumbnails"),
        _project_field("frames_use_feet_frames"),
        _project_field("linear_blending"),
        _project_field("linearize_working_space"),
        _project_field("expression_engine"),
        _project_field("compensate_for_scene_referred_profiles"),
    ],
    "masks": [
        _mask_field(generator.MAIN_COMP_NAME, "color"),
        _mask_field(generator.MAIN_COMP_NAME, "inverted"),
        _mask_field(generator.MAIN_COMP_NAME, "locked"),
        _mask_field(generator.MAIN_COMP_NAME, "mask_mode"),
        _mask_field(generator.MAIN_COMP_NAME, "mask_feather_falloff"),
        _mask_field(generator.MAIN_COMP_NAME, "mask_motion_blur"),
        _mask_field(generator.MAIN_COMP_NAME, "roto_bezier"),
    ],
    "items": [
        _item_field(generator.DROP_FRAME_COMP_NAME, "label"),
        _item_field(generator.DROP_FRAME_COMP_NAME, "comment"),
        _item_field(generator.HIGH_FPS_COMP_NAME, "label"),
        _item_field(generator.HIGH_FPS_COMP_NAME, "comment"),
        _item_field(generator.MAIN_COMP_NAME, "label"),
        _item_field(generator.MAIN_COMP_NAME, "comment"),
        _item_field("NonSquarePAR_Comp", "label"),
        _item_field("NonSquarePAR_Comp", "comment"),
        _item_field("Pre_Comp", "label"),
        _item_field("Pre_Comp", "comment"),
        _solid_source_field(0, "color"),
        _solid_source_field(1, "color"),
        _solid_source_field(2, "color"),
        _folder_field("Compositions", "label"),
        _folder_field("Subfolder", "label"),
    ],
    "render_queue": [
        _render_queue_item_field("log_type"),
        _render_queue_item_field("queue_item_notify"),
        _render_queue_item_field(
            "_skip_existing_files",
            use_json=False,
        ),
        _output_module_field("include_source_xmp", json_key="includeSourceXMP"),
        _output_module_field("post_render_action"),
    ],
    "everything": [
        _app_field("build_name", use_json=False),
        _project_field("bits_per_channel"),
        _project_field("time_display_type"),
        _project_field("frames_count_type"),
        _project_field("display_start_frame"),
        _project_field("transparency_grid_thumbnails"),
        _project_field("linear_blending"),
        _project_field("linearize_working_space"),
        _project_field("expression_engine"),
        _project_field("compensate_for_scene_referred_profiles"),
        _comp_field(generator.MAIN_COMP_NAME, "bg_color"),
        _comp_field(generator.MAIN_COMP_NAME, "width"),
        _comp_field(generator.MAIN_COMP_NAME, "height"),
        _comp_field(generator.MAIN_COMP_NAME, "frame_rate"),
        _comp_field(generator.MAIN_COMP_NAME, "duration"),
        _comp_field(generator.MAIN_COMP_NAME, "display_start_time"),
        _comp_field(generator.MAIN_COMP_NAME, "pixel_aspect"),
        _comp_field(generator.MAIN_COMP_NAME, "resolution_factor"),
        _comp_field(generator.MAIN_COMP_NAME, "motion_blur"),
        _comp_field(generator.MAIN_COMP_NAME, "frame_blending"),
        _comp_field(generator.MAIN_COMP_NAME, "hide_shy_layers"),
        _comp_field(generator.MAIN_COMP_NAME, "shutter_angle"),
        _comp_field(generator.MAIN_COMP_NAME, "shutter_phase"),
        _comp_field(generator.MAIN_COMP_NAME, "preserve_nested_frame_rate"),
        _comp_field(generator.MAIN_COMP_NAME, "preserve_nested_resolution"),
        _comp_field(generator.MAIN_COMP_NAME, "work_area_start"),
        _comp_field(generator.MAIN_COMP_NAME, "work_area_duration"),
        _av_layer_field(generator.MAIN_COMP_NAME, 0, "comment"),
        _av_layer_field(generator.MAIN_COMP_NAME, 0, "locked"),
        _av_layer_field(generator.MAIN_COMP_NAME, 0, "shy"),
        _av_layer_field(generator.MAIN_COMP_NAME, 0, "solo"),
        _av_layer_field(generator.MAIN_COMP_NAME, 0, "enabled"),
        _av_layer_field(generator.MAIN_COMP_NAME, 0, "label"),
        _av_layer_field(generator.MAIN_COMP_NAME, 0, "auto_orient"),
        _av_layer_field(generator.MAIN_COMP_NAME, 0, "blending_mode"),
        _av_layer_field(generator.MAIN_COMP_NAME, 0, "quality"),
        _av_layer_field(generator.MAIN_COMP_NAME, 0, "effects_active"),
        _av_layer_field(generator.MAIN_COMP_NAME, 0, "motion_blur"),
        _av_layer_field(generator.MAIN_COMP_NAME, 0, "adjustment_layer"),
        _av_layer_field(generator.MAIN_COMP_NAME, 0, "audio_enabled"),
        _av_layer_field(generator.MAIN_COMP_NAME, 1, "in_point"),
        _av_layer_field(generator.MAIN_COMP_NAME, 2, "out_point"),
        _av_layer_field(generator.MAIN_COMP_NAME, 3, "start_time"),
        _av_layer_field(generator.MAIN_COMP_NAME, 4, "stretch"),
        _av_layer_field(generator.MAIN_COMP_NAME, 5, "comment"),
        _av_layer_field(generator.MAIN_COMP_NAME, 5, "shy"),
        _av_layer_field(generator.MAIN_COMP_NAME, 5, "label"),
        _av_layer_field(generator.MAIN_COMP_NAME, 5, "frame_blending_type"),
        _av_layer_field(generator.MAIN_COMP_NAME, 6, "comment"),
        _av_layer_field(generator.MAIN_COMP_NAME, 6, "shy"),
        _av_layer_field(generator.MAIN_COMP_NAME, 6, "label"),
        _mask_field(generator.MAIN_COMP_NAME, "inverted"),
        _mask_field(generator.MAIN_COMP_NAME, "mask_mode"),
        _item_field(generator.DROP_FRAME_COMP_NAME, "label"),
        _item_field(generator.HIGH_FPS_COMP_NAME, "label"),
        _item_field(generator.MAIN_COMP_NAME, "label"),
        _solid_source_field(0, "color"),
        _solid_source_field(1, "color"),
        _render_queue_item_field("log_type"),
        _render_queue_item_field("queue_item_notify"),
    ],
}


def _scenario_map() -> Dict[str, Sequence[Any]]:
    return {name: (description, apply_fn) for name, description, apply_fn in generator.SCENARIOS}


def _compare_scenario(
    name: str,
    description: str,
    apply_fn: Callable[[Application], None],
    checks: Sequence[FieldCheck],
    base_path: Path,
    roundtrip_dir: Path,
) -> Dict[str, Any]:
    scenario_aep = roundtrip_dir / "{}.aep".format(name)
    scenario_json = roundtrip_dir / "{}.json".format(name)

    if not scenario_aep.exists():
        raise FileNotFoundError("Missing scenario AEP: {}".format(scenario_aep))
    if not scenario_json.exists():
        raise FileNotFoundError("Missing scenario JSON: {}".format(scenario_json))

    intended_app = parse_aep(base_path)
    apply_fn(intended_app)

    parsed_app = parse_aep(scenario_aep)
    with scenario_json.open("r", encoding="utf-8") as handle:
        exported_json = json.load(handle)

    mismatches: List[Dict[str, Any]] = []

    for check in checks:
        intent_value = _observe_app(check.get_app, intended_app)
        ae_value = _observe_json(check.get_json, exported_json)
        parsed_value = _observe_app(check.get_app, parsed_app)

        ae_matches = True
        if check.get_json is not None:
            ae_matches = _observed_equal(intent_value, ae_value, check.tolerance)

        parsed_matches = _observed_equal(intent_value, parsed_value, check.tolerance)

        ae_vs_parsed = True
        if check.get_json is not None:
            ae_vs_parsed = _observed_equal(ae_value, parsed_value, check.tolerance)

        if ae_matches and parsed_matches and ae_vs_parsed:
            continue

        flags: List[str] = []
        if check.get_json is not None and not ae_matches:
            flags.append("AE!=intent")
        if not parsed_matches:
            flags.append("py_aep!=intent")
        if check.get_json is not None and not ae_vs_parsed:
            flags.append("AE!=py_aep")

        mismatches.append(
            {
                "field": check.label,
                "flags": flags,
                "intent": _format_observed(intent_value),
                "ae_json": _format_observed(ae_value),
                "py_aep": _format_observed(parsed_value),
            }
        )

    return {
        "name": name,
        "description": description,
        "total_checks": len(checks),
        "mismatches": mismatches,
    }


def _print_results(results: Sequence[Dict[str, Any]], show_ok: bool) -> None:
    for result in results:
        mismatch_count = len(result["mismatches"])
        if mismatch_count == 0:
            if show_ok:
                print("[OK] {} ({})".format(result["name"], result["total_checks"]))
            continue

        print(
            "[MISMATCH] {} - {} / {} checks".format(
                result["name"],
                mismatch_count,
                result["total_checks"],
            )
        )
        print("  {}".format(result["description"]))
        for mismatch in result["mismatches"]:
            print("  - {} [{}]".format(mismatch["field"], ", ".join(mismatch["flags"])))
            print("      intent: {}".format(mismatch["intent"]))
            print("      ae:     {}".format(mismatch["ae_json"]))
            print("      py_aep: {}".format(mismatch["py_aep"]))
        print()

    scenario_count = len(results)
    mismatch_scenarios = sum(1 for result in results if result["mismatches"])
    mismatch_fields = sum(len(result["mismatches"]) for result in results)
    total_fields = sum(result["total_checks"] for result in results)
    print(
        "Summary: {} scenario(s), {} with mismatches, {} mismatching field(s) "
        "out of {} check(s)".format(
            scenario_count,
            mismatch_scenarios,
            mismatch_fields,
            total_fields,
        )
    )


def _write_report(report_path: Path, results: Sequence[Dict[str, Any]]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(list(results), handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare roundtrip intent vs AE JSON vs py_aep parse.",
    )
    parser.add_argument(
        "--base",
        type=Path,
        default=generator.DEFAULT_BASE,
        help="Base .aep used by the generator",
    )
    parser.add_argument(
        "--roundtrip-dir",
        type=Path,
        default=generator.OUTPUT_DIR,
        help="Directory containing generated .aep/.json pairs",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        help="Only compare these scenario names",
    )
    parser.add_argument(
        "--show-ok",
        action="store_true",
        help="Also print scenarios with no mismatches",
    )
    parser.add_argument(
        "--json-report",
        type=Path,
        help="Optional path to write a JSON report",
    )
    parser.add_argument(
        "--fail-on-mismatch",
        action="store_true",
        help="Exit with status 1 if any mismatches are found",
    )
    args = parser.parse_args()

    scenario_map = _scenario_map()
    selected_names = args.only or [name for name, _desc, _fn in generator.SCENARIOS]

    unknown = sorted(name for name in selected_names if name not in scenario_map)
    if unknown:
        raise SystemExit("Unknown scenario(s): {}".format(", ".join(unknown)))

    results = []
    for name in selected_names:
        description, apply_fn = scenario_map[name]
        checks = SCENARIO_CHECKS[name]
        results.append(
            _compare_scenario(
                name=name,
                description=description,
                apply_fn=apply_fn,
                checks=checks,
                base_path=args.base,
                roundtrip_dir=args.roundtrip_dir,
            )
        )

    _print_results(results, show_ok=args.show_ok)

    if args.json_report is not None:
        _write_report(args.json_report, results)
        print("Wrote JSON report to {}".format(args.json_report))

    has_mismatches = any(result["mismatches"] for result in results)
    if has_mismatches and args.fail_on_mismatch:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
