"""Generate roundtrip test files for manual verification in After Effects.

Each output file starts from a base .aep and applies a group of related
modifications, then saves to `samples/roundtrip/`. The JSX companion
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

DEFAULT_BASE = ROOT / "samples" / "versions" / "ae2025" / "complete.aep"
OUTPUT_DIR = ROOT / "samples" / "roundtrip"


# ---------------------------------------------------------------------------
# Grouped modifications - each function applies multiple changes to one file
# ---------------------------------------------------------------------------

SCENARIOS: list[tuple[str, str, object]] = []


def _register(name: str, description: str, apply_fn: object) -> None:
    SCENARIOS.append((name, description, apply_fn))


# -- 1. Composition settings & geometry -------------------------------------

def _comp_settings(app: Application) -> None:
    comp = app.project.compositions[0]
    comp.bg_color = [0.1, 0.2, 0.3]
    comp.width = 3840
    comp.height = 2160
    comp.pixel_aspect = 2.0
    comp.renderer = "ADBE Calder"
    comp.resolution_factor = [2, 2]
    comp.draft3d = True
    comp.preserve_nested_frame_rate = True
    comp.preserve_nested_resolution = True
    comp.motion_blur_adaptive_sample_limit = 128
    comp.motion_blur_samples_per_frame = 32

_register(
    "comp_settings",
    "bg_color, size, pixel_aspect, renderer, resolution, draft3d, "
    "preserve_nested_*, motion_blur_samples*",
    _comp_settings,
)


# -- 2. Composition timing & work area -------------------------------------

def _comp_timing(app: Application) -> None:
    comp = app.project.compositions[0]
    comp.frame_rate = 24.0
    comp.display_start_time = 5.0
    comp.duration = 120.0
    comp.work_area_start = 1.0
    comp.work_area_duration = 10.0
    comp.time = 6.0
    comp.display_start_frame = 10
    comp.drop_frame = True

_register(
    "comp_timing",
    "frame_rate, display_start_time, duration, work_area_start/duration, "
    "time, display_start_frame, drop_frame",
    _comp_timing,
)


# -- 3. Composition flags & shutter ----------------------------------------

def _comp_flags(app: Application) -> None:
    comp = app.project.compositions[0]
    comp.motion_blur = False
    comp.frame_blending = False
    comp.hide_shy_layers = False
    comp.shutter_angle = 360
    comp.shutter_phase = -180
    # Modify a second comp too
    comp2 = app.project.compositions[1]
    comp2.motion_blur = True
    comp2.frame_blending = True
    comp2.hide_shy_layers = True
    comp2.shutter_angle = 90
    comp2.shutter_phase = -45

_register(
    "comp_flags",
    "motion_blur, frame_blending, hide_shy, shutter_angle/phase on 2 comps",
    _comp_flags,
)


# -- 4. Layer flags & AVLayer booleans --------------------------------------

def _layer_flags(app: Application) -> None:
    from py_aep.enums import BlendingMode, Label, LayerQuality, LayerSamplingQuality

    comp = app.project.compositions[0]
    layer = comp.layers[0]
    layer.comment = "roundtrip test comment"
    layer.locked = True
    layer.shy = True
    layer.solo = True
    layer.enabled = False
    layer.selected = True
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
    "comment, locked, shy, solo, enabled, selected, label, "
    "AVLayer: adjustment, effects, motion_blur, collapse, guide, quality, "
    "sampling, blending_mode, audio",
    _layer_flags,
)


# -- 5. Layer timing, orient & multiple layers ------------------------------

def _layer_timing(app: Application) -> None:
    from py_aep.enums import AutoOrientType, FrameBlendingType, Label
    from py_aep.models.layers.av_layer import AVLayer

    comp = app.project.compositions[0]
    layer = comp.layers[0]
    layer.auto_orient = AutoOrientType.ALONG_PATH
    layer.in_point = layer.in_point + 1.0
    layer.out_point = layer.out_point - 1.0
    layer.start_time = 2.0
    layer.stretch = 50.0

    # Modify several layers with different settings
    for i, lyr in enumerate(comp.layers[1:4]):
        lyr.comment = f"layer {i + 1} modified"
        lyr.shy = i % 2 == 0
        lyr.label = Label.YELLOW
        if isinstance(lyr, AVLayer):
            lyr.frame_blending_type = FrameBlendingType.FRAME_MIX

_register(
    "layer_timing",
    "auto_orient, in/out_point, start_time, stretch, "
    "multi-layer comment/shy/label/frame_blending",
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
    proj.bits_per_channel = BitsPerChannel.SIXTEEN
    proj.time_display_type = TimeDisplayType.FRAMES
    proj.frames_count_type = FramesCountType.FC_START_1
    proj.display_start_frame = 0
    proj.transparency_grid_thumbnails = True
    proj.frames_use_feet_frames = True
    proj.linear_blending = True
    proj.linearize_working_space = True
    proj.expression_engine = "javascript-1.0"
    proj.compensate_for_scene_referred_profiles = True

_register(
    "project_settings",
    "bits_per_channel, time_display_type, frames_count_type, "
    "display_start_frame, transparency_grid, feet_frames, "
    "linear_blending, linearize_working_space, expression_engine, "
    "compensate_for_scene_referred",
    _project_settings,
)


# -- 7. Masks ---------------------------------------------------------------

def _masks(app: Application) -> None:
    from py_aep.enums import MaskFeatherFalloff, MaskMode, MaskMotionBlur

    comp = app.project.compositions[0]
    for layer in comp.layers:
        if not layer.masks:
            continue
        mask = layer.masks[0]
        mask.enabled = not mask.enabled
        mask.color = [1.0, 0.0, 0.0]
        mask.inverted = True
        mask.locked = True
        mask.mask_mode = MaskMode.SUBTRACT
        mask.mask_feather_falloff = MaskFeatherFalloff.LINEAR
        mask.mask_motion_blur = MaskMotionBlur.ON
        mask.roto_bezier = True
        return

_register(
    "masks",
    "enabled, color, inverted, locked, mask_mode, "
    "feather_falloff, motion_blur, roto_bezier",
    _masks,
)


# -- 8. Items (names, labels, comments) & solid source colors ---------------

def _items(app: Application) -> None:
    from py_aep.enums import Label
    from py_aep.models.sources.solid import SolidSource

    proj = app.project
    # Rename and relabel items
    for i, item in enumerate(list(proj.items.values())[:5]):
        item.label = Label.FUCHSIA
        item.comment = f"item {i} comment"

    # Change solid source colors
    solid_count = 0
    for item in proj.footages:
        if isinstance(item.main_source, SolidSource) and solid_count < 3:
            item.main_source.color = [
                0.2 * (solid_count + 1),
                0.1,
                0.3 * (solid_count + 1),
            ]
            solid_count += 1

    # Modify folder labels
    for folder in proj.folders[:2]:
        folder.label = Label.CYAN

_register(
    "items",
    "item labels/comments, solid source colors, folder labels",
    _items,
)


# -- 9. Render queue & output module ----------------------------------------

def _render_queue(app: Application) -> None:
    from py_aep.enums import LogType, PostRenderAction

    rq = app.project.render_queue
    if not rq or not rq.items:
        return
    rqi = rq.items[0]
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
        Label,
        LayerQuality,
        LogType,
        MaskMode,
        TimeDisplayType,
    )
    from py_aep.models.sources.solid import SolidSource

    app.build_name = "99.9x999"

    # Project
    proj = app.project
    proj.bits_per_channel = BitsPerChannel.SIXTEEN
    proj.time_display_type = TimeDisplayType.FRAMES
    proj.transparency_grid_thumbnails = True
    proj.linear_blending = True
    proj.expression_engine = "javascript-1.0"
    proj.compensate_for_scene_referred_profiles = True

    # Composition
    comp = proj.compositions[0]
    comp.bg_color = [0.5, 0.5, 0.5]
    comp.width = 1280
    comp.height = 720
    comp.frame_rate = 25.0
    comp.duration = 60.0
    comp.display_start_time = 2.0
    comp.pixel_aspect = 1.0
    comp.resolution_factor = [4, 4]
    comp.motion_blur = False
    comp.frame_blending = False
    comp.hide_shy_layers = True
    comp.shutter_angle = 90
    comp.shutter_phase = -45
    comp.draft3d = True
    comp.preserve_nested_frame_rate = True
    comp.work_area_start = 0.5
    comp.work_area_duration = 5.0
    comp.drop_frame = True

    # Layer flags + AVLayer
    layer = comp.layers[0]
    layer.comment = "everything test"
    layer.locked = True
    layer.shy = True
    layer.solo = True
    layer.enabled = False
    layer.label = Label.ORANGE
    layer.auto_orient = AutoOrientType.ALONG_PATH
    layer.in_point = layer.in_point + 0.5
    layer.out_point = layer.out_point - 0.5
    layer.start_time = 1.0
    layer.stretch = 75.0
    layer.blending_mode = BlendingMode.SCREEN
    layer.quality = LayerQuality.BEST
    layer.effects_active = False
    layer.motion_blur = True
    layer.adjustment_layer = True
    layer.audio_enabled = False

    # Multiple layers
    for i, lyr in enumerate(comp.layers[1:3]):
        lyr.comment = f"everything layer {i + 1}"
        lyr.shy = True
        lyr.label = Label.YELLOW

    # Masks
    for lyr in comp.layers:
        if lyr.masks:
            lyr.masks[0].enabled = False
            lyr.masks[0].inverted = True
            lyr.masks[0].mask_mode = MaskMode.SUBTRACT
            break

    # Item labels
    for item in list(proj.items.values())[:3]:
        item.label = Label.FUCHSIA

    # Solid colors
    for item in proj.footages[:2]:
        if isinstance(item.main_source, SolidSource):
            item.main_source.color = [1.0, 0.0, 0.0]

    # Render queue
    rq = proj.render_queue
    rq.items[0].log_type = LogType.ERRORS_AND_PER_FRAME_INFO
    rq.items[0].queue_item_notify = True

_register(
    "everything",
    "app + project + comp + layer + AVLayer + masks + items + "
    "solids + render_queue - all at once",
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
        help="Output directory (default: samples/roundtrip/)",
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
