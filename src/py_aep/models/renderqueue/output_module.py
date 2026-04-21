from __future__ import annotations

import json
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, cast

from py_aep.enums import (
    AudioBitDepth,
    AudioChannels,
    AudioSampleRate,
    CineonFileFormat,
    ConvertToLinearLight,
    GetSettingsFormat,
    OutputAudio,
    OutputChannels,
    OutputColorDepth,
    OutputColorMode,
    OutputFormat,
    PostRenderAction,
    PostRenderActionSetting,
    ResizeQuality,
)
from py_aep.enums.mappings import map_output_audio, map_output_color_space

from ...kaitai.descriptors import ChunkField
from ...kaitai.transforms import strip_null
from ...kaitai.utils import propagate_check
from ...resolvers.output import (
    FORMAT_ID_EXTENSIONS,
    VIDEO_CODEC_NAMES,
    resolve_output_filename,
    resolve_time_span,
)
from ..items.composition import CompItem
from ..validators import validate_number
from .format_options import (
    CineonFormatOptions,
    JpegFormatOptions,
    OpenExrFormatOptions,
    PngFormatOptions,
    TargaFormatOptions,
    TiffFormatOptions,
    XmlFormatOptions,
)
from .settings import (
    SettingsView,
    settings_to_number,
    settings_to_string,
)

if TYPE_CHECKING:
    from ...kaitai import Aep
    from ..project import Project
    from .render_queue_item import RenderQueueItem


def _validate_crop(peer_field: str, dimension: str) -> Callable[[int, Any], None]:
    """Factory for crop validators that check range and final dimension."""
    range_check = validate_number(min=-30000, max=30000, integer=True)

    def validator(value: int, obj: Any) -> None:
        range_check(value, obj)
        peer: int = getattr(obj, peer_field)
        comp_dim: int = getattr(obj._parent_rqi.comp, dimension)
        res_attr = "resolution_x" if dimension == "width" else "resolution_y"
        divisor = getattr(obj._parent_rqi._ldat, res_attr) or 1
        dim = math.ceil(comp_dim / divisor)
        remaining = dim - value - peer
        if remaining < 1:
            raise ValueError(
                f"Crop would reduce {dimension} to {remaining}px (must be >= 1)"
            )

    return validator


# Depth pairs: no-alpha <-> alpha
_DEPTH_PLUS = {24: 32, 48: 64, 96: 128}
_DEPTH_MINUS = {32: 24, 64: 48, 128: 96}


# ---------------------------------------------------------------------------
# OM_SETTINGS: ExtendScript key -> (attribute, optional enum class)
# ---------------------------------------------------------------------------

OM_SETTINGS: dict[str, tuple[str, type | None]] = {
    "Audio Bit Depth": ("_audio_bit_depth", AudioBitDepth),
    "Audio Channels": ("_audio_channels", AudioChannels),
    "Audio Sample Rate": ("_audio_sample_rate", AudioSampleRate),
    "Channels": ("_channels", OutputChannels),
    "Color": ("_color_mode", OutputColorMode),
    "Convert to Linear Light": ("_convert_to_linear_light", ConvertToLinearLight),
    "Crop Bottom": ("_crop_bottom", None),
    "Crop Left": ("_crop_left", None),
    "Crop Right": ("_crop_right", None),
    "Crop Top": ("_crop_top", None),
    "Crop": ("_crop", None),
    "Depth": ("_depth", OutputColorDepth),
    "Format": ("_format", OutputFormat),
    "Include Project Link": ("_include_project_link", None),
    "Include Source XMP Metadata": ("include_source_xmp", None),
    "Lock Aspect Ratio": ("_lock_aspect_ratio", None),
    "Output Audio": ("_output_audio", OutputAudio),
    "Output Color Space": ("_output_color_space_setting", None),
    "Output File Info": ("_output_file_info", None),
    "Post-Render Action": ("_post_render_action_setting", PostRenderActionSetting),
    "Preserve RGB": ("_preserve_rgb", None),
    "Resize Quality": ("_resize_quality", ResizeQuality),
    "Resize to": ("_resize_to", None),
    "Resize": ("_resize", None),
    "Starting #": ("_starting_number", None),
    "Use Comp Frame Number": ("_use_comp_frame_number", None),
    "Use Region of Interest": ("_use_region_of_interest", None),
    "Video Output": ("_video_output", None),
}


class OutputModule:
    """
    An `OutputModule` object of a [RenderQueueItem][] generates a single file or
    sequence via a render operation, and contains attributes and methods
    relating to the file to be rendered.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        om = app.project.render_queue.items[0].output_modules[0]
        print(om.file)
        ```

    See: https://ae-scripting.docsforadobe.dev/renderqueue/outputmodule/
    """

    include_source_xmp = ChunkField.bool("_om_ldat", "include_source_xmp")
    """When `True`, writes all source footage XMP metadata to the output file.
    Read / Write."""

    post_render_action = ChunkField.enum(
        PostRenderAction,
        "_om_ldat",
        "post_render_action",
    )
    """
    An action to perform when rendering is complete.
    Read / Write.
    """

    _audio_bit_depth = ChunkField.enum(
        AudioBitDepth,
        "_roou",
        "audio_bit_depth",
    )

    _audio_channels = ChunkField.enum(
        AudioChannels,
        "_roou",
        "audio_channels",
    )

    _audio_sample_rate = ChunkField.enum(
        AudioSampleRate,
        "_roou",
        "audio_sample_rate",
    )

    _channels = ChunkField.enum(
        OutputChannels,
        "_om_ldat",
        "channels",
        post_set="_sync_depth_to_channels",
    )

    _color_mode = ChunkField.enum(
        OutputColorMode,
        "_roou",
        "color_premultiplied",
    )

    _convert_to_linear_light = ChunkField.enum(
        ConvertToLinearLight,
        "_om_ldat",
        "convert_to_linear_light",
    )

    _crop = ChunkField.bool(
        "_om_ldat",
        "crop",
        post_set="_update_output_dimensions",
    )

    _crop_bottom = ChunkField[int](
        "_om_ldat",
        "crop_bottom",
        validate=_validate_crop("_crop_top", "height"),
        post_set="_update_output_dimensions",
    )

    _crop_left = ChunkField[int](
        "_om_ldat",
        "crop_left",
        validate=_validate_crop("_crop_right", "width"),
        post_set="_update_output_dimensions",
    )

    _crop_right = ChunkField[int](
        "_om_ldat",
        "crop_right",
        validate=_validate_crop("_crop_left", "width"),
        post_set="_update_output_dimensions",
    )

    _crop_top = ChunkField[int](
        "_om_ldat",
        "crop_top",
        validate=_validate_crop("_crop_bottom", "height"),
        post_set="_update_output_dimensions",
    )

    _depth = ChunkField.enum(
        OutputColorDepth,
        "_roou",
        "depth",
    )

    _format = ChunkField[OutputFormat](
        "_roou",
        "format_id",
        reverse_seq_field=OutputFormat.to_format_id,
        transform=OutputFormat.from_format_id,
        read_only=True,
    )
    """Read-only for now as a lot of things must be updated when changing format"""

    _include_project_link = ChunkField.bool(
        "_om_ldat",
        "include_project_link",
    )

    _lock_aspect_ratio = ChunkField.bool(
        "_om_ldat",
        "lock_aspect_ratio",
    )

    _post_render_action_setting = ChunkField.enum(
        PostRenderActionSetting,
        "_om_ldat",
        "post_render_action",
    )

    _preserve_rgb = ChunkField.bool(
        "_om_ldat",
        "preserve_rgb",
    )

    _resize = ChunkField.bool(
        "_om_ldat",
        "resize",
        post_set="_update_output_dimensions",
    )

    _resize_quality = ChunkField.enum(
        ResizeQuality,
        "_om_ldat",
        "resize_quality",
    )

    _use_comp_frame_number = ChunkField.bool(
        "_om_ldat",
        "use_comp_frame_number",
    )

    _use_region_of_interest = ChunkField.bool(
        "_om_ldat",
        "use_region_of_interest",
        post_set="_update_output_dimensions",
    )

    def __init__(
        self,
        *,
        _om_ldat: Aep.OutputModuleSettingsLdatBody,
        _roou: Aep.RoouBody,
        _alas_utf8: Aep.Utf8Body | None,
        _file_name_utf8: Aep.Utf8Body | None,
        _name_utf8: Aep.Utf8Body | None,
        _render_settings_ldat: Aep.RenderSettingsLdatBody,
        parent: RenderQueueItem,
        format_options: (
            CineonFormatOptions
            | JpegFormatOptions
            | OpenExrFormatOptions
            | PngFormatOptions
            | TargaFormatOptions
            | TiffFormatOptions
            | XmlFormatOptions
            | None
        ),
    ) -> None:
        self._om_ldat = _om_ldat
        self._roou = _roou
        self._alas_utf8 = _alas_utf8
        self._file_name_utf8 = _file_name_utf8
        self._name_utf8 = _name_utf8
        self._render_settings_ldat = _render_settings_ldat
        self._parent_rqi = parent
        self._format_options = format_options

    @property
    def format_options(
        self,
    ) -> (
        CineonFormatOptions
        | JpegFormatOptions
        | OpenExrFormatOptions
        | PngFormatOptions
        | TargaFormatOptions
        | TiffFormatOptions
        | XmlFormatOptions
        | None
    ):
        """
        Format-specific render options for this output module. The concrete
        type depends on the output format:

        - [CineonFormatOptions][] for Cineon/DPX sequences
        - [JpegFormatOptions][] for JPEG sequences
        - [OpenExrFormatOptions][] for OpenEXR sequences
        - [PngFormatOptions][] for PNG sequences
        - [TargaFormatOptions][] for Targa sequences
        - [TiffFormatOptions][] for TIFF sequences
        - [XmlFormatOptions][] for XML-based formats (AVI, H.264, MP3,
          QuickTime, WAV)
        - `None` for formats without parsed format options

        Read-only.
        """
        return self._format_options

    @property
    def name(self) -> str:
        """The name of the output module, as shown in the user interface.
        Read-only."""
        if self._name_utf8 is None:
            return ""
        return strip_null(str(self._name_utf8.contents))

    @property
    def parent(self) -> RenderQueueItem:
        """
        Reference to parent RenderQueueItem, used for resolving file paths
        and accessing comp and render settings. Read-only.
        """
        return self._parent_rqi

    @property
    def post_render_target_comp(self) -> CompItem:
        """
        The [CompItem][] to use for post-render actions that require a comp.
        Only used when `post_render_action` is `IMPORT_AND_REPLACE` or
        `SET_PROXY`. Read-only.
        """
        comp_id = self._om_ldat.post_render_target_comp_id or None
        if (
            self.post_render_action in (PostRenderAction.NONE, PostRenderAction.IMPORT)
            or comp_id is None
        ):
            return self._parent_rqi.comp
        return cast(CompItem, self._project.items[comp_id])

    @property
    def settings(self) -> SettingsView:
        """[SettingsView][py_aep.models.settings.SettingsView] dict with
        ExtendScript-compatible keys. Includes `"Video Output"`,
        `"Audio Bit Depth"`, `"Output Color Space"`, `"Preserve RGB"`,
        `"Convert to Linear Light"`, etc. Matches the format from
        `OutputModule.get_settings(GetSettingsFormat.NUMBER)`.
        """
        return SettingsView(self, OM_SETTINGS)

    @property
    def _video_output(self) -> bool:
        return bool(self._roou.width > 0 or self._roou.height > 0)

    @_video_output.setter
    def _video_output(self, value: bool) -> None:
        if value:
            w, h = self._effective_dimensions
            self._roou.width = w
            self._roou.height = h
        else:
            self._roou.width = 0
            self._roou.height = 0
        propagate_check(self._roou)

    @property
    def _output_audio(self) -> OutputAudio:
        """Output audio setting (derived from two binary sources)."""
        audio_enabled = self._roou.audio_disabled_hi != 0xFF
        return map_output_audio(audio_enabled, self._om_ldat.output_audio)

    @_output_audio.setter
    def _output_audio(self, value: OutputAudio) -> None:
        if value == OutputAudio.OFF:
            self._roou.audio_disabled_hi = 0xFF
            self._om_ldat.output_audio = 0
        elif value == OutputAudio.AUTO:
            self._roou.audio_disabled_hi = 0x00
            self._om_ldat.output_audio = 1
        elif value == OutputAudio.ON:
            self._roou.audio_disabled_hi = 0x00
            self._om_ldat.output_audio = 0
        else:
            raise ValueError(
                f"Unsupported OutputAudio value: {value}. Expected "
                "OutputAudio.OFF, OutputAudio.AUTO, or OutputAudio.ON."
            )
        propagate_check(self._roou)
        propagate_check(self._om_ldat)

    def _sync_depth_to_channels(self) -> None:
        """Sync depth to match channel alpha setting after _channels changes."""
        depth_val = int(self._depth)
        is_rgba = self._om_ldat.channels == int(OutputChannels.RGBA)
        target = _DEPTH_PLUS if is_rgba else _DEPTH_MINUS
        if depth_val in target:
            self._roou.depth = target[depth_val]
            propagate_check(self._roou)

    @property
    def _effective_dimensions(self) -> tuple[int, int]:
        """Effective render dimensions after resolution, resize, crop/ROI.

        AE order: resolution -> resize -> crop/ROI.
        """
        comp = self._parent_rqi.comp
        res_x = self._parent_rqi._ldat.resolution_x or 1
        res_y = self._parent_rqi._ldat.resolution_y or 1

        w = math.ceil(comp.width / res_x)
        h = math.ceil(comp.height / res_y)

        if self._om_ldat.resize:
            w, h = self._roou.width, self._roou.height

        if self._om_ldat.use_region_of_interest and comp._viewer and comp._viewer.views:
            viewer = comp._viewer
            opts = viewer.views[viewer.active_view_index].options
            w = opts.roi_right - opts.roi_left
            h = opts.roi_bottom - opts.roi_top
        elif self._om_ldat.crop:
            w -= self._om_ldat.crop_left + self._om_ldat.crop_right
            h -= self._om_ldat.crop_top + self._om_ldat.crop_bottom

        return max(w, 1), max(h, 1)

    @property
    def _effective_frame_rate(self) -> float:
        """Effective frame rate: custom if enabled, else comp frame rate."""
        rqi = self._parent_rqi
        if rqi._ldat.use_this_frame_rate:
            return rqi._ldat.frame_rate  # type: ignore[no-any-return]
        return rqi.comp.frame_rate

    def _update_output_dimensions(self) -> None:
        """Recompute _roou.width and _roou.height from current settings.

        When resize is enabled, _roou.width/height hold the resize targets
        and must not be overwritten.
        """
        if self._om_ldat.resize:
            return

        self._roou.width, self._roou.height = self._effective_dimensions
        propagate_check(self._roou)

    @property
    def _output_color_space(self) -> str | None:
        """Output color space derived from ICC profile and working space."""
        return map_output_color_space(
            self._om_ldat.output_profile_id,
            self._om_ldat.output_color_space_working,
            self._project.working_space,
        )

    @property
    def _output_color_space_setting(self) -> str:
        """Output color space (read-only)."""
        return self._output_color_space or ""

    @property
    def _output_file_info(self) -> dict[str, str]:
        """Output file info (read-only)."""
        file_template = self.file_template
        folder_path = self._folder_path
        file_name_template = self._file_name_template
        if "\\" in file_name_template or "/" in file_name_template:
            sep = "\\" if "\\" in file_name_template else "/"
            last_sep_idx = file_name_template.rfind(sep)
            subfolder_path = file_name_template[:last_sep_idx]
            file_name = file_name_template[last_sep_idx + 1 :]
        else:
            subfolder_path = ""
            file_name = file_name_template
        return {
            "Full Flat Path": file_template,
            "Base Path": folder_path,
            "Subfolder Path": subfolder_path,
            "File Name": file_name,
            "File Template": file_name_template,
        }

    @property
    def _starting_number(self) -> int:
        """Starting frame number."""
        if not self._om_ldat.use_comp_frame_number:
            return int(self._roou.starting_number)
        rqi = self._parent_rqi
        start_seconds = rqi.time_span_start
        frame_rate = rqi.comp.frame_rate
        return int(round(start_seconds * frame_rate))

    @_starting_number.setter
    def _starting_number(self, value: int) -> None:
        v = int(value)
        if v < 0 or v > 9999999:
            raise ValueError(f"Starting number must be between 0 and 9999999, got {v}")
        self._roou.starting_number = v
        propagate_check(self._roou)

    @property
    def _resize_to(self) -> list[int]:
        """Resize dimensions as [width, height]."""
        return [self._roou.width, self._roou.height]

    @_resize_to.setter
    def _resize_to(self, value: list[int]) -> None:
        if len(value) != 2:
            raise ValueError(
                f"Resize must be [width, height], got {len(value)} elements"
            )
        w, h = int(value[0]), int(value[1])
        if not (1 <= w <= 30000 and 1 <= h <= 30000):
            raise ValueError(
                f"Resize dimensions must be between 1 and 30000, got [{w}, {h}]"
            )
        self._roou.width = w
        self._roou.height = h
        propagate_check(self._roou)

    @staticmethod
    def _build_file_template(
        folder_path: str,
        file_name_template: str,
        is_folder: bool,
    ) -> str:
        """Build the full output file template path from components.

        Combines the output folder path and file name template into a single
        path string, using the path separator found in the folder path.

        Args:
            folder_path: The output folder path from alas data.
            file_name_template: The file name template
                (e.g., `[compName].[fileExtension]`).
            is_folder: Whether the alas path points to a folder.

        Returns:
            The complete file template path.
        """
        if not folder_path:
            return ""

        if not file_name_template:
            return folder_path

        if is_folder:
            path_sep = "\\" if "\\" in folder_path else "/"
            cleaned_path = folder_path.rstrip(path_sep)
            return f"{cleaned_path}{path_sep}{file_name_template}"

        return folder_path

    @property
    def _alas_data(self) -> dict[str, Any]:
        """Parsed JSON from the alas chunk."""
        if self._alas_utf8 is None:
            return {}
        text = strip_null(str(self._alas_utf8.contents))
        if not text:
            return {}
        data = json.loads(text)
        return data if isinstance(data, dict) else {}

    @property
    def _is_folder(self) -> bool:
        """Whether the alas path points to a folder."""
        return bool(self._alas_data.get("target_is_folder", False))

    @property
    def _video_codec(self) -> str | None:
        """The four-character video codec identifier."""
        return strip_null(self._roou.video_codec) or None

    @property
    def _resolve_extension(self) -> str | None:
        """Derive file extension from format_id, with Cineon special case."""
        format_id = strip_null(self._roou.format_id)
        if format_id == "sDPX":
            fo = self._format_options
            if isinstance(fo, CineonFormatOptions):
                return "dpx" if fo.file_format == CineonFileFormat.DPX else "cin"
            return "dpx"
        return FORMAT_ID_EXTENSIONS.get(format_id, None)

    @property
    def _folder_path(self) -> str:
        """The output folder path from the alas chunk."""
        return str(self._alas_data.get("fullpath", ""))

    @property
    def _file_name_template(self) -> str:
        """The file name template from the Utf8 chunk."""
        if self._file_name_utf8 is None:
            return ""
        return strip_null(str(self._file_name_utf8.contents))

    @property
    def file_template(self) -> str:
        """The raw file path template, may contain `[compName]` and
        `[fileExtension]` variables. Read / Write."""
        return self._build_file_template(
            self._folder_path, self._file_name_template, self._is_folder
        )

    @file_template.setter
    def file_template(self, value: str) -> None:
        if self._is_folder:
            path_sep = "\\" if "\\" in value else "/"
            last_sep = value.rfind(path_sep)
            if last_sep >= 0:
                folder_path = value[: last_sep + 1]
                file_name = value[last_sep + 1 :]
            else:
                folder_path = self._folder_path
                file_name = value
        else:
            folder_path = value
            file_name = ""

        if self._alas_utf8 is not None:
            text = strip_null(str(self._alas_utf8.contents))
            data = json.loads(text) if text else {}
            if not isinstance(data, dict):
                data = {}
            data["fullpath"] = folder_path
            self._alas_utf8.contents = json.dumps(data)
            propagate_check(self._alas_utf8)

        if self._file_name_utf8 is not None:
            self._file_name_utf8.contents = file_name
            propagate_check(self._file_name_utf8)

    @property
    def _project(self) -> Project:
        """The project this output module belongs to."""
        return self.parent._project

    @property
    def file(self) -> str:
        """The full path for the file this output module is set to render.

        Resolves template variables like `[compName]`, `[width]`, `[frameRate]`,
        etc. to their actual values based on the composition and render settings.
        Read / Write.
        """
        comp = self.parent.comp
        rq_settings = self.parent.settings

        extension = self._resolve_extension
        om_channels = self.settings["Channels"]
        om_depth = self.settings["Depth"]
        compressor = (
            VIDEO_CODEC_NAMES.get(self._video_codec, self._video_codec)
            if self._video_codec
            else None
        )

        effective_width, effective_height = self._effective_dimensions
        effective_frame_rate = self._effective_frame_rate
        time_span = resolve_time_span(comp, rq_settings, effective_frame_rate)

        project = self._project
        project_name = Path(project.file).stem if project.file else "Untitled Project"

        return resolve_output_filename(
            self.file_template,
            project_name=project_name,
            comp_name=comp.name,
            render_settings_name=self.parent.name,
            output_module_name=self.name,
            width=effective_width,
            height=effective_height,
            frame_rate=effective_frame_rate,
            start_frame=time_span["start_frame"],
            end_frame=time_span["end_frame"],
            duration_frames=time_span["duration_frames"],
            start_time=time_span["start_time"],
            end_time=time_span["end_time"],
            duration_time=time_span["duration_time"],
            channels=om_channels,
            project_color_depth=int(project.bits_per_channel),
            output_color_depth=om_depth,
            compressor=compressor,
            field_render=rq_settings["Field Render"],
            pulldown_phase=rq_settings["3:2 Pulldown"],
            file_extension=extension,
        )

    @file.setter
    def file(self, value: str) -> None:
        self.file_template = value

    def get_settings(
        self,
        format: GetSettingsFormat = GetSettingsFormat.STRING,
    ) -> dict[str, Any]:
        """Return output module settings in the specified format.

        Args:
            format: The output format.
                `GetSettingsFormat.NUMBER` returns numeric values (enums unwrapped to ints).
                `GetSettingsFormat.STRING` returns all values as strings
        """
        if format == GetSettingsFormat.STRING:
            return settings_to_string(self.settings)
        if format == GetSettingsFormat.NUMBER:
            return settings_to_number(self.settings)
        raise ValueError(f"Unsupported format: {format!r}")

    def get_setting(
        self,
        key: str,
        format: GetSettingsFormat = GetSettingsFormat.STRING,
    ) -> Any:
        """Return a single output module setting in the specified format.

        Args:
            key: The setting key (e.g. `"Video Output"`, `"Audio Bit Depth"`).
            format: The output format.
        """
        return self.get_settings(format)[key]
