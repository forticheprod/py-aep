"""Output module resolution logic.

Resolves After Effects output filename templates, computes effective
render dimensions, and formats timecodes.
"""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, Any, Mapping

from ..enums import OutputChannels, OutputColorDepth, TimeSpanSource

if TYPE_CHECKING:
    from ..models.items.composition import CompItem

# Roou format_id (4-char) to file extension.
FORMAT_ID_EXTENSIONS: dict[str, str] = {
    "H264": "mp4",
    ".AVI": "avi",
    "MooV": "mov",
    "Mp3 ": "mp3",
    "wao_": "wav",
    "TIF ": "tif",
    "8BPS": "psd",
    "png!": "png",
    "JPEG": "jpg",
    "oEXR": "exr",
    "AIFF": "aif",
    "SGI ": "sgi",
    "IFF ": "iff",
    "TPIC": "tga",
    "RHDR": "hdr",
}

FIELD_ORDER_NAMES: dict[int, str] = {
    0: "Both",  # Off/Progressive - renders both fields
    1: "UFF",  # Upper field first
    2: "LFF",  # Lower field first
}

PULLDOWN_PHASE_NAMES: dict[int, str] = {
    0: "",
    1: "WSSWW",
    2: "SSWWW",
    3: "SWWWS",
    4: "WWWSS",
    5: "WWSSW",
}

OUTPUT_CHANNELS_NAMES: dict[OutputChannels, str] = {
    OutputChannels.RGB: "RGB",
    OutputChannels.RGBA: "RGBA",
    OutputChannels.ALPHA: "Alpha",
}

OUTPUT_COLOR_DEPTH_NAMES: dict[OutputColorDepth, str] = {
    OutputColorDepth.MILLIONS_OF_COLORS: "Millions",
    OutputColorDepth.MILLIONS_OF_COLORS_PLUS: "Millions+",
    OutputColorDepth.TRILLIONS_OF_COLORS: "Trillions",
    OutputColorDepth.TRILLIONS_OF_COLORS_PLUS: "Trillions+",
    OutputColorDepth.FLOATING_POINT: "Floating Point",
    OutputColorDepth.FLOATING_POINT_PLUS: "Floating Point+",
}

PROJECT_COLOR_DEPTH_NAMES: dict[int, str] = {
    8: "8bit",
    16: "16bit",
    32: "32bit",
}

# Mapping of video codec FourCC codes to friendly names
VIDEO_CODEC_NAMES: dict[str, str] = {
    "CTXF": "H.264",
    "FXTC": "H.264",
    "avc1": "H.264",
    "ap4h": "ProRes 4444",
    "apch": "ProRes 422 HQ",
    "apcn": "ProRes 422",
    "apcs": "ProRes 422 LT",
    "apco": "ProRes 422 Proxy",
}


def calculate_aspect_ratio(width: int, height: int) -> str:
    """Calculate simplified aspect ratio string (e.g., '16x9').

    Args:
        width: Frame width in pixels.
        height: Frame height in pixels.

    Returns:
        Aspect ratio string like '16x9', '4x3', etc.
    """
    gcd = math.gcd(width, height)
    return f"{width // gcd}x{height // gcd}"


def format_frame_number(frame: int, fps: float) -> str:
    """Format frame number in After Effects feet+frames format.

    AE uses a feet+frames format where each foot is 16 frames (like 35mm
    film). Format is FFFF+RR where FFFF is feet and RR is remaining frames.

    Args:
        frame: Frame number (0-based).
        fps: Frames per second (not used in this format).

    Returns:
        Formatted frame string like '0045+00' (45 feet, 0 frames).
    """
    frames_per_foot = 16  # Standard 35mm film: 16 frames per foot
    feet = frame // frames_per_foot
    remaining_frames = frame % frames_per_foot
    return f"{feet:04d}+{remaining_frames:02d}"


def format_timecode(
    seconds: float,
    fps: float,
    is_duration: bool = False,
) -> str:
    """Format time as timecode string with dashes.

    Args:
        seconds: Time in seconds.
        fps: Frames per second.
        is_duration: If True, uses ceiling for frame calculation (for
            durations). If False, uses floor (for absolute times).

    Returns:
        Timecode string like '0-00-00-00' (hours-minutes-seconds-frames).
    """
    fps_int = int(fps) if fps else 1
    # Use ceiling for durations, floor for absolute times
    if is_duration:
        total_frames = math.ceil(seconds * fps_int)
    else:
        total_frames = int(seconds * fps_int)

    frames = total_frames % fps_int
    total_seconds = total_frames // fps_int
    secs = total_seconds % 60
    total_minutes = total_seconds // 60
    mins = total_minutes % 60
    hours = total_minutes // 60

    return f"{hours}-{mins:02d}-{secs:02d}-{frames:02d}"


def resolve_output_filename(
    file_template: str,
    project_name: str | None = None,
    comp_name: str | None = None,
    render_settings_name: str | None = None,
    output_module_name: str = "",
    width: int | None = None,
    height: int | None = None,
    frame_rate: float | None = None,
    start_frame: int | None = None,
    end_frame: int | None = None,
    duration_frames: int | None = None,
    start_time: float | None = None,
    end_time: float | None = None,
    duration_time: float | None = None,
    channels: OutputChannels | None = None,
    project_color_depth: int | None = None,
    output_color_depth: OutputColorDepth | None = None,
    compressor: str | None = None,
    field_render: int | None = None,
    pulldown_phase: int | None = None,
    file_extension: str | None = None,
) -> str:
    """Resolve an After Effects output filename template to the actual filename.

    After Effects stores output paths with template variables like
    `[compName]` and `[fileExtension]`. This function resolves those
    variables to produce the actual filename that would be rendered.

    Args:
        file_template: The file path containing template variables.
            e.g., `C:/Output/[compName].[fileExtension]`
        project_name: The project name (without .aep extension) for
            `[projectName]`.
        comp_name: The composition name for `[compName]`.
        render_settings_name: The render settings template name for
            `[renderSettingsName]`.
        output_module_name: The output module name for
            `[outputModuleName]`.
        width: The composition width for `[width]`.
        height: The composition height for `[height]`.
        frame_rate: The frame rate for `[frameRate]` and timecodes.
        start_frame: The start frame for `[startFrame]`
            (feet+frames format).
        end_frame: The end frame for `[endFrame]`
            (feet+frames format).
        duration_frames: The duration in frames for `[durationFrames]`
            (feet+frames format).
        start_time: The start time in seconds for `[startTimecode]`
            (uses floor).
        end_time: The end time in seconds for `[endTimecode]`
            (uses floor).
        duration_time: The duration in seconds for `[durationTimecode]`
            (uses ceiling).
        channels: The output channels setting for `[channels]`.
        project_color_depth: The project bits per channel (8/16/32) for
            `[projectColorDepth]`.
        output_color_depth: The output color depth for
            `[outputColorDepth]`.
        compressor: The video codec/compressor name for `[compressor]`.
        field_render: The field render setting for `[fieldOrder]`.
        pulldown_phase: The 3:2 pulldown phase for `[pulldownPhase]`.
        file_extension: The file extension for `[fileExtension]`.

    Returns:
        The resolved file path, or an empty string if file_template is None.
    """
    if not file_template:
        return ""

    fps = frame_rate or 24.0

    # Precompute formatted frame rate string
    frame_rate_str: str | None = None
    if frame_rate is not None:
        frame_rate_str = (
            str(int(frame_rate)) if frame_rate == int(frame_rate) else str(frame_rate)
        )

    # Build substitution map: template_key -> resolved_value
    # Entries with None values are skipped during application
    substitutions: dict[str, str | None] = {
        "projectName": project_name,
        "compName": comp_name,
        "renderSettingsName": render_settings_name,
        "outputModuleName": output_module_name,
        "width": str(width) if width is not None else None,
        "height": str(height) if height is not None else None,
        "frameRate": frame_rate_str,
        "aspectRatio": (
            calculate_aspect_ratio(width, height)
            if width is not None and height is not None
            else None
        ),
        "startFrame": (
            format_frame_number(start_frame, fps) if start_frame is not None else None
        ),
        "endFrame": (
            format_frame_number(end_frame, fps) if end_frame is not None else None
        ),
        "durationFrames": (
            format_frame_number(duration_frames, fps)
            if duration_frames is not None
            else None
        ),
        "startTimecode": (
            format_timecode(start_time, fps, is_duration=False)
            if start_time is not None
            else None
        ),
        "endTimecode": (
            format_timecode(end_time, fps, is_duration=False)
            if end_time is not None
            else None
        ),
        "durationTimecode": (
            format_timecode(duration_time, fps, is_duration=True)
            if duration_time is not None
            else None
        ),
        "channels": (
            OUTPUT_CHANNELS_NAMES.get(channels, "RGB") if channels is not None else None
        ),
        "projectColorDepth": (
            PROJECT_COLOR_DEPTH_NAMES.get(project_color_depth, "8bit")
            if project_color_depth is not None
            else None
        ),
        "outputColorDepth": (
            OUTPUT_COLOR_DEPTH_NAMES.get(output_color_depth, "Millions")
            if output_color_depth is not None
            else None
        ),
        "compressor": compressor,
        "fieldOrder": (
            FIELD_ORDER_NAMES.get(field_render, "Off")
            if field_render is not None
            else None
        ),
        "pulldownPhase": (
            PULLDOWN_PHASE_NAMES.get(pulldown_phase, "Off")
            if pulldown_phase is not None
            else None
        ),
        "projectFolder": "",  # Always resolves to empty string
        "fileExtension": file_extension,
    }

    result = file_template
    for key, value in substitutions.items():
        if value is not None:
            result = re.sub(rf"\[{key}\]", value, result, flags=re.IGNORECASE)

    return result


def resolve_time_span(
    comp: CompItem,
    rq_settings: Mapping[str, Any],
    effective_frame_rate: float,
) -> dict[str, Any]:
    """Compute time span values based on render settings.

    Determines start/end frames, timecodes, and duration based on the
    Time Span mode (Work Area, Length of Comp, or Custom).

    Args:
        comp: The composition being rendered.
        rq_settings: The render settings dict.
        effective_frame_rate: The effective frame rate for rendering.

    Returns:
        Dict with keys: start_frame, end_frame, duration_frames,
        start_time, end_time, duration_time.
    """
    time_span_mode = rq_settings["Time Span"]

    if time_span_mode == TimeSpanSource.LENGTH_OF_COMP:
        time_span_start = 0.0
        duration_time = comp.duration
        time_span_end = comp.duration
        duration_frames = round(comp.duration * effective_frame_rate)
        first_rendered_frame = int(comp.display_start_time * effective_frame_rate)
    else:
        time_span_start = rq_settings["Time Span Start"]
        duration_time = rq_settings["Time Span Duration"]
        time_span_end = rq_settings["Time Span End"]
        duration_frames = round(duration_time * effective_frame_rate)
        first_rendered_frame = int(
            comp.display_start_time * effective_frame_rate
        ) + int(time_span_start * effective_frame_rate)

    start_frame = first_rendered_frame
    end_frame = first_rendered_frame + duration_frames

    return {
        "start_frame": start_frame,
        "end_frame": end_frame,
        "duration_frames": duration_frames,
        "start_time": comp.display_start_time + time_span_start,
        "end_time": comp.display_start_time + time_span_end,
        "duration_time": duration_time,
    }
