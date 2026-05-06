"""Generate roundtrip test files for manual verification in After Effects.

Each output file starts from a base .aep and applies a group of related
modifications, then saves to `samples/unused/roundtrip/`. The JSX companion
script `scripts/jsx/open_roundtrip_files.jsx` can then open each file
in AE to confirm it loads without errors.

Usage::

    uv run python scripts/generate_roundtrip_files.py
    uv run python scripts/generate_roundtrip_files.py --base samples/versions/ae2025/complete.aep
    uv run python scripts/generate_roundtrip_files.py --list
    uv run python scripts/generate_roundtrip_files.py --only comp_settings comp_timing
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Add project root to path so py_aep is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from py_aep import parse as parse_aep  # noqa: E402

if TYPE_CHECKING:
    from py_aep.models.application import Application
    from py_aep.models.items.composition import CompItem
    from py_aep.models.items.folder import FolderItem
    from py_aep.models.items.footage import FootageItem
    from py_aep.models.items.item import Item
    from py_aep.models.layers.av_layer import AVLayer
    from py_aep.models.layers.layer import Layer
    from py_aep.models.properties.mask_property_group import MaskPropertyGroup
    from py_aep.models.renderqueue.render_queue_item import RenderQueueItem
    from py_aep.models.sources.solid import SolidSource

DEFAULT_BASE = ROOT / "samples" / "versions" / "ae2025" / "complete.aep"
OUTPUT_DIR = ROOT / "samples" / "unused" / "roundtrip"
DROP_FRAME_COMP_NAME = "DropFrame_Comp"
HIGH_FPS_COMP_NAME = "HighFPS_Comp"
MAIN_COMP_NAME = "Main_Comp"
VALID_BUILD_NAME = "20.1x42"


# ---------------------------------------------------------------------------
# Grouped modifications - each function applies multiple changes to one file
# ---------------------------------------------------------------------------

SCENARIOS: list[tuple[str, str, object]] = []


def _register(name: str, description: str, apply_fn: object) -> None:
    SCENARIOS.append((name, description, apply_fn))


def _get_comp(app: Application, name: str) -> CompItem:
    for comp in app.project.compositions:
        if comp.name == name:
            return comp
    raise ValueError(f"Composition not found: {name}")


def _get_item(app: Application, name: str) -> Item:
    for item in app.project.items.values():
        if item.name == name:
            return item
    raise ValueError(f"Project item not found: {name}")


def _get_folder(app: Application, name: str) -> FolderItem:
    for folder in app.project.folders:
        if folder.name == name:
            return folder
    raise ValueError(f"Folder not found: {name}")


def _get_av_layers(comp: CompItem, *, minimum: int) -> list[AVLayer]:
    from py_aep.models.layers.av_layer import AVLayer

    av_layers = [layer for layer in comp.layers if isinstance(layer, AVLayer)]
    if len(av_layers) < minimum:
        raise ValueError(
            f"{comp.name} needs at least {minimum} AV layers, "
            f"found {len(av_layers)}"
        )
    return av_layers


def _get_first_mask_layer(comp: CompItem) -> Layer:
    for layer in comp.layers:
        if layer.masks and len(layer.masks) > 0:
            return layer
    raise ValueError(f"No masked layer found in composition: {comp.name}")


def _get_first_mask(comp: CompItem) -> MaskPropertyGroup:
    from py_aep.models.properties.mask_property_group import MaskPropertyGroup

    layer = _get_first_mask_layer(comp)
    masks = layer.masks
    if masks is None or len(masks) == 0:
        raise ValueError(f"No mask found in composition: {comp.name}")
    mask = masks[0]
    if not isinstance(mask, MaskPropertyGroup):
        raise ValueError(f"First mask in {comp.name} is not a MaskPropertyGroup")
    return mask


def _get_solid_footages(
    app: Application, *, minimum: int
) -> list[tuple[FootageItem, SolidSource]]:
    from py_aep.models.sources.solid import SolidSource

    solids: list[tuple[FootageItem, SolidSource]] = []
    for item in app.project.footages:
        source = item.main_source
        if isinstance(source, SolidSource):
            solids.append((item, source))
    if len(solids) < minimum:
        raise ValueError(
            f"Project needs at least {minimum} solid footages, found {len(solids)}"
        )
    return solids


def _get_render_queue_item(app: Application) -> RenderQueueItem:
    rq = app.project.render_queue
    if rq is None or not rq.items:
        raise ValueError("Project has no render queue item to modify")
    return rq.items[0]


# -- 1. Composition settings & geometry -------------------------------------

def _comp_settings(app: Application) -> None:
    comp = _get_comp(app, DROP_FRAME_COMP_NAME)
    comp.bg_color = [0.1, 0.2, 0.3]
    comp.width = 3840
    comp.height = 2160
    comp.pixel_aspect = 2.0
    comp.renderer = "ADBE Calder"
    comp.resolution_factor = [2, 2]
    comp.preserve_nested_frame_rate = True
    comp.preserve_nested_resolution = True
    comp.motion_blur_adaptive_sample_limit = 128
    comp.motion_blur_samples_per_frame = 32

_register(
    "comp_settings",
    "DropFrame_Comp: bg_color, size, pixel_aspect, renderer, resolution, "
    "preserve_nested_*, motion_blur_samples*",
    _comp_settings,
)


# -- 2. Composition timing & work area -------------------------------------

def _comp_timing(app: Application) -> None:
    comp = _get_comp(app, DROP_FRAME_COMP_NAME)
    comp.frame_rate = 24.0
    comp.display_start_frame = 120
    comp.display_start_time = 5.0
    comp.duration = 120.0
    comp.work_area_start = 1.0
    comp.work_area_duration = 10.0
    comp.time = 6.0
    comp.drop_frame = False

_register(
    "comp_timing",
    "DropFrame_Comp: frame_rate, consistent display_start_time/frame, "
    "duration, work_area_start/duration, time, drop_frame",
    _comp_timing,
)


# -- 3. Composition flags & shutter ----------------------------------------

def _comp_flags(app: Application) -> None:
    comp = _get_comp(app, DROP_FRAME_COMP_NAME)
    comp.motion_blur = True
    comp.frame_blending = True
    comp.hide_shy_layers = True
    comp.shutter_angle = 360
    comp.shutter_phase = -180

    comp2 = _get_comp(app, HIGH_FPS_COMP_NAME)
    comp2.motion_blur = True
    comp2.frame_blending = True
    comp2.hide_shy_layers = True
    comp2.shutter_angle = 90
    comp2.shutter_phase = -45

_register(
    "comp_flags",
    "DropFrame_Comp + HighFPS_Comp: motion_blur, frame_blending, hide_shy, "
    "shutter_angle/phase",
    _comp_flags,
)


# -- 4. Layer flags & AVLayer booleans --------------------------------------

def _layer_flags(app: Application) -> None:
    from py_aep.enums import BlendingMode, Label, LayerQuality, LayerSamplingQuality

    comp = _get_comp(app, DROP_FRAME_COMP_NAME)
    layer = _get_av_layers(comp, minimum=1)[0]
    layer.comment = "roundtrip test comment"
    layer.locked = True
    layer.shy = True
    layer.solo = True
    layer.enabled = False
    layer.label = Label.RED

    layer.adjustment_layer = True
    layer.effects_active = False
    layer.motion_blur = True
    layer.collapse_transformation = True
    layer.guide_layer = True
    layer.preserve_transparency = True
    layer.quality = LayerQuality.BEST
    layer.sampling_quality = LayerSamplingQuality.BICUBIC
    layer.blending_mode = BlendingMode.MULTIPLY
    layer.audio_enabled = False

_register(
    "layer_flags",
    "DropFrame_Comp layer 1: comment, locked, shy, solo, enabled, label, "
    "AVLayer adjustment/effects/motion_blur/collapse/guide/quality/"
    "sampling/blending_mode/audio",
    _layer_flags,
)


# -- 5. Layer timing, orient & multiple layers ------------------------------

def _layer_timing(app: Application) -> None:
    from py_aep.enums import AutoOrientType, FrameBlendingType, Label

    comp = _get_comp(app, MAIN_COMP_NAME)
    av_layers = _get_av_layers(comp, minimum=8)

    av_layers[0].auto_orient = AutoOrientType.ALONG_PATH
    av_layers[1].in_point = av_layers[1].in_point + 1.0
    av_layers[2].out_point = av_layers[2].out_point - 1.0
    av_layers[3].start_time = 2.0
    av_layers[4].stretch = 50.0

    for i, lyr in enumerate(av_layers[5:8]):
        lyr.comment = f"layer {i + 1} modified"
        lyr.shy = i % 2 == 0
        lyr.label = Label.YELLOW
        lyr.frame_blending_type = FrameBlendingType.FRAME_MIX

_register(
    "layer_timing",
    "Main_Comp AV layers: auto_orient, in/out/start/stretch on separate "
    "layers, plus comment/shy/label/frame_blending",
    _layer_timing,
)


# -- 6. Project settings ---------------------------------------------------

def _project_settings(app: Application) -> None:
    from py_aep.enums import (
        BitsPerChannel,
        FramesCountType,
        TimeDisplayType,
    )

    proj = app.project
    proj.bits_per_channel = BitsPerChannel.THIRTY_TWO
    proj.time_display_type = TimeDisplayType.FRAMES
    proj.frames_count_type = FramesCountType.FC_START_1
    proj.display_start_frame = 1
    proj.transparency_grid_thumbnails = False
    proj.frames_use_feet_frames = False
    proj.linear_blending = False
    proj.linearize_working_space = False
    proj.expression_engine = "extendscript"
    proj.compensate_for_scene_referred_profiles = True

_register(
    "project_settings",
    "project bits/time display/frame count/display start/transparency/"
    "feet frames/linearize/expression engine/scene-referred settings",
    _project_settings,
)


# -- 7. Masks ---------------------------------------------------------------

def _masks(app: Application) -> None:
    from py_aep.enums import MaskFeatherFalloff, MaskMode, MaskMotionBlur

    comp = _get_comp(app, MAIN_COMP_NAME)
    mask = _get_first_mask(comp)
    mask.color = [1.0, 0.0, 0.0]
    mask.inverted = True
    mask.locked = True
    mask.mask_mode = MaskMode.SUBTRACT
    mask.mask_feather_falloff = MaskFeatherFalloff.FFO_LINEAR
    mask.mask_motion_blur = MaskMotionBlur.ON
    mask.roto_bezier = True

_register(
    "masks",
    "Main_Comp first masked layer: color, inverted, locked, "
    "mask_mode, feather_falloff, motion_blur, roto_bezier",
    _masks,
)


# -- 8. Items (names, labels, comments) & solid source colors ---------------

def _items(app: Application) -> None:
    from py_aep.enums import Label

    item_names = [
        DROP_FRAME_COMP_NAME,
        HIGH_FPS_COMP_NAME,
        MAIN_COMP_NAME,
        "NonSquarePAR_Comp",
        "Pre_Comp",
    ]
    for i, item_name in enumerate(item_names):
        item = _get_item(app, item_name)
        item.label = Label.FUCHSIA
        item.comment = f"item {i} comment"

    solid_footages = _get_solid_footages(app, minimum=3)
    for i, (_item, source) in enumerate(solid_footages[:3]):
        source.color = [0.2 * (i + 1), 0.1, 0.3 * (i + 1)]

    for folder_name in ("Compositions", "Subfolder"):
        folder = _get_folder(app, folder_name)
        folder.label = Label.CYAN

_register(
    "items",
    "named comp item labels/comments, first 3 solid source colors, named "
    "folder labels",
    _items,
)


# -- 9. Render queue & output module ----------------------------------------

def _render_queue(app: Application) -> None:
    from py_aep.enums import LogType, PostRenderAction

    rqi = _get_render_queue_item(app)
    rqi.log_type = LogType.ERRORS_AND_PER_FRAME_INFO
    rqi.queue_item_notify = True
    rqi._skip_existing_files = True
    om = rqi.output_modules[0]
    om.include_source_xmp = True
    om.post_render_action = PostRenderAction.SET_PROXY

_register(
    "render_queue",
    "log_type, queue_item_notify, skip_existing_files, "
    "output_module include_source_xmp/post_render_action",
    _render_queue,
)


# -- 10. All at once --------------------------------------------------------

def _everything(app: Application) -> None:
    from py_aep.enums import (
        AutoOrientType,
        BitsPerChannel,
        BlendingMode,
        FrameBlendingType,
        FramesCountType,
        Label,
        LayerQuality,
        LogType,
        MaskMode,
        TimeDisplayType,
    )

    app.build_name = VALID_BUILD_NAME

    proj = app.project
    proj.bits_per_channel = BitsPerChannel.THIRTY_TWO
    proj.time_display_type = TimeDisplayType.FRAMES
    proj.frames_count_type = FramesCountType.FC_START_1
    proj.display_start_frame = 1
    proj.transparency_grid_thumbnails = False
    proj.linear_blending = False
    proj.linearize_working_space = False
    proj.expression_engine = "extendscript"
    proj.compensate_for_scene_referred_profiles = True

    comp = _get_comp(app, MAIN_COMP_NAME)
    av_layers = _get_av_layers(comp, minimum=7)
    comp.bg_color = [0.5, 0.5, 0.5]
    comp.width = 1280
    comp.height = 720
    comp.frame_rate = 25.0
    comp.duration = 60.0
    comp.display_start_time = 2.0
    comp.pixel_aspect = 1.5
    comp.resolution_factor = [4, 4]
    comp.motion_blur = False
    comp.frame_blending = True
    comp.hide_shy_layers = True
    comp.shutter_angle = 90
    comp.shutter_phase = -45
    comp.preserve_nested_frame_rate = True
    comp.preserve_nested_resolution = True
    comp.work_area_start = 0.5
    comp.work_area_duration = 5.0

    primary_layer = av_layers[0]
    primary_layer.comment = "everything test"
    primary_layer.locked = True
    primary_layer.shy = True
    primary_layer.solo = False
    primary_layer.enabled = False
    primary_layer.label = Label.ORANGE
    primary_layer.auto_orient = AutoOrientType.ALONG_PATH
    primary_layer.blending_mode = BlendingMode.SCREEN
    primary_layer.quality = LayerQuality.BEST
    primary_layer.effects_active = False
    primary_layer.motion_blur = True
    primary_layer.adjustment_layer = True
    primary_layer.audio_enabled = False

    av_layers[1].in_point = av_layers[1].in_point + 0.5
    av_layers[2].out_point = av_layers[2].out_point - 0.5
    av_layers[3].start_time = 1.0
    av_layers[4].stretch = 75.0

    for i, lyr in enumerate(av_layers[5:7]):
        lyr.comment = f"everything layer {i + 1}"
        lyr.shy = True
        lyr.label = Label.YELLOW
    av_layers[5].frame_blending_type = FrameBlendingType.FRAME_MIX

    mask = _get_first_mask(comp)
    mask.inverted = True
    mask.mask_mode = MaskMode.SUBTRACT

    for item_name in [DROP_FRAME_COMP_NAME, HIGH_FPS_COMP_NAME, MAIN_COMP_NAME]:
        item = _get_item(app, item_name)
        item.label = Label.FUCHSIA

    for _item, source in _get_solid_footages(app, minimum=2)[:2]:
        source.color = [1.0, 0.0, 0.0]

    rqi = _get_render_queue_item(app)
    rqi.log_type = LogType.ERRORS_AND_PER_FRAME_INFO
    rqi.queue_item_notify = True


_register(
    "everything",
    "valid build_name + project + Main_Comp + AV layers + masked layer + "
    "items + solids + render_queue",
    _everything,
)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate(
    base_path: Path,
    output_dir: Path,
    only: list[str] | None = None,
) -> dict[str, str]:
    """Generate roundtrip files. Returns {filename: status} dict."""
    output_dir.mkdir(parents=True, exist_ok=True)
    # delete existing files
    for file in output_dir.glob("*"):
        if file.is_file():
            file.unlink()
    results: dict[str, str] = {}

    for name, _desc, apply_fn in SCENARIOS:
        if only and name not in only:
            continue
        filename = f"{name}.aep"
        out_path = output_dir / filename
        try:
            app = parse_aep(base_path)
            apply_fn(app)  # type: ignore[operator]
            app.project.save(out_path)
            results[filename] = "OK"
            print(f"  [OK]   {filename}")
        except Exception as e:
            results[filename] = f"ERROR: {e}"
            print(f"  [FAIL] {filename}: {e}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate roundtrip .aep files for AE verification."
    )
    parser.add_argument(
        "--base",
        type=Path,
        default=DEFAULT_BASE,
        help="Base .aep file (default: samples/versions/ae2025/complete.aep)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR,
        help="Output directory (default: samples/unused/roundtrip/)",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        help="Only generate these scenarios (by name)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all scenarios and exit",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete existing output directory before generating",
    )
    args = parser.parse_args()

    if args.list:
        print(f"{len(SCENARIOS)} scenarios:")
        for name, desc, _ in SCENARIOS:
            print(f"  {name}: {desc}")
        return

    if not args.base.exists():
        print(f"ERROR: Base file not found: {args.base}")
        sys.exit(1)

    print(f"Base:   {args.base}")
    print(f"Output: {args.output}")
    print()

    if args.clean and args.output.exists():
        shutil.rmtree(args.output)
        print(f"Cleaned {args.output}")
        print()

    results = generate(args.base, args.output, args.only)

    ok = sum(1 for v in results.values() if v == "OK")
    fail = len(results) - ok
    print(f"\nDone: {ok} generated, {fail} failed, {len(results)} total")

    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
