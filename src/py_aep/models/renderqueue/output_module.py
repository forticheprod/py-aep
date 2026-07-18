from __future__ import annotations

import contextlib
import json
import math
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Mapping, cast

from py_aep.enums import (
    AudioBitDepth,
    AudioChannels,
    AudioSampleRate,
    CineonFileFormat,
    ColorManagementSystem,
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
from py_aep.enums.mappings import (
    map_output_audio,
    map_output_color_space,
    profile_id_for_name,
)

from ...binary.ldat_chunks import (
    LHD3_BLOCK_SINGLE,
    LdatChunk,
    Lhd3Chunk,
    set_lhd3_count,
)
from ...binary.misc_chunks import HdrmChunk
from ...binary.render_chunks import (
    OutputModuleSettingsItem,
    RoptChunk,
    RouuChunk,
    TiffRoptChunk,
)
from ...binary.scalar_chunks import Utf8Chunk
from ...binary.utils import find_by_type, index_by_identity
from ...color.ocio import (
    ocio_color_space_for_profile_id,
    ocio_output_profile_id,
    require_ocio_config,
    resolve_ocio_config,
)
from ...data.output_module_rules import allowed_values, constrained_keys
from ...parsers.format_options import parse_format_options
from ...resolvers.output import (
    FORMAT_ID_EXTENSIONS,
    VIDEO_CODEC_NAMES,
    resolve_output_filename,
    resolve_time_span,
)
from ..descriptors import ChunkField
from ..items.composition import CompItem
from ..validators import (
    _validate_number,
    validate_bool,
    validate_enum,
    validate_sequence,
    validate_string,
)
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
    build_resize_to_strings,
    settings_to_number,
    settings_to_string,
)

if TYPE_CHECKING:
    from typing import Any, Callable, ClassVar, Iterator

    from ...binary.chunk import Chunk
    from ...binary.render_chunks import RenderSettingsItem
    from ...parsers.templates import OutputModuleTemplate
    from ..project import Project
    from .render_queue_item import RenderQueueItem


def _validate_crop(
    peer_field: str, dimension: str
) -> Callable[[int, OutputModule], None]:
    """Factory for crop validators that check range and final dimension."""
    range_check = _validate_number(min=-30000, max=30000, integer=True)

    def validator(value: int, obj: OutputModule) -> None:
        range_check(value, obj)
        peer: int = getattr(obj, peer_field)
        parent_rqi = obj._parent_rqi
        comp_dim: int = getattr(parent_rqi.comp, dimension)
        res_attr = "resolution_x" if dimension == "width" else "resolution_y"
        divisor = getattr(parent_rqi._ldat, res_attr) or 1
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


def _validate_for_format(
    key: str, pre: Callable[..., None] | None = None
) -> Callable[[Any, OutputModule], None]:
    """Factory for validators gating a setting on the module's format
    rules (see `OutputModule._check_format_rule`).

    Args:
        key: The `OM_SETTINGS` key to look up.
        pre: Optional validator run first (e.g. enum membership for
            fields whose forgiving read transform hides the enum class
            from `ChunkField`).
    """

    def validator(value: Any, obj: OutputModule) -> None:
        if pre is not None:
            pre(value, obj)
        obj._check_format_rule(key, value)

    return validator


# -- Clamp helpers for format-option-backed keys ----------------------------
# Reading/writing through the module keeps _CLAMP_ACCESSORS free of
# isinstance lambdas; every writer is a raw write (validation bypass).


def _xml_options_of(om: OutputModule, attr: str) -> Any:
    fo = om._format_options
    if isinstance(fo, XmlFormatOptions):
        return getattr(fo, attr)
    return None


def _set_xml_param_raw(om: OutputModule, param_key: str, value: int) -> None:
    fo = om._format_options
    if isinstance(fo, XmlFormatOptions):
        fo._set_param(param_key, str(value))


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

    include_source_xmp = ChunkField.bool(
        "_om_ldat",
        "include_source_xmp",
    )
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
        validate=_validate_for_format("Audio Bit Depth"),
    )

    _audio_channels = ChunkField.enum(
        AudioChannels,
        "_roou",
        "audio_channels",
        validate=_validate_for_format("Audio Channels"),
        post_set="_clamp_audio_dependents",
    )

    _audio_sample_rate = ChunkField.enum(
        AudioSampleRate,
        "_roou",
        "audio_sample_rate",
        validate=_validate_for_format("Audio Sample Rate"),
    )

    _channels = ChunkField.enum(
        OutputChannels,
        "_om_ldat",
        "channels",
        validate=_validate_for_format("Channels"),
        post_set="_sync_after_channels",
    )

    _color_mode = ChunkField.enum(
        OutputColorMode,
        "_roou",
        "color_premultiplied",
        validate=_validate_for_format("Color"),
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

    # Forgiving read transforms: AE-saved files can hold an out-of-enum
    # depth (garbage bytes observed in dpx_fido.aep, frame_rate.aep) or an
    # unknown format id (third-party output plugins); reads fall back to
    # the raw value, writes stay strict via validate_enum.
    _depth = ChunkField.enum(
        OutputColorDepth,
        "_roou",
        "depth",
        allow_out_of_enum_values=True,
        validate=_validate_for_format("Depth", pre=validate_enum(OutputColorDepth)),
    )

    _format = ChunkField.enum(
        OutputFormat,
        "_roou",
        "format_id",
        allow_out_of_enum_values=True,
        reverse=OutputFormat.to_format_id,
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
        _om_ldat: OutputModuleSettingsItem,
        _roou: RouuChunk,
        _alas_utf8: Utf8Chunk | None,
        _file_name_utf8: Utf8Chunk | None,
        _name_utf8: Utf8Chunk | None,
        _render_settings_ldat: RenderSettingsItem,
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
        # Format options validate their writes against this module's
        # format rules; the back-reference is (re)assigned here and in
        # _apply_output_template - the only two places an OM gains a
        # format-options object.
        if format_options is not None:
            format_options._parent_om = self
        # Non-zero while inside batch_edit(): per-write format rules and
        # clamps are deferred to the batch exit.
        self._batch_depth = 0

    @classmethod
    def _new(
        cls,
        *,
        render_settings_ldat: RenderSettingsItem,
        parent: RenderQueueItem,
    ) -> tuple[OutputModule, list[Chunk]]:
        """Create a new output module: a fresh TIFF image sequence.

        Builds the chunks After Effects writes for a freshly added output
        module - a simple image sequence with an empty `Ropt` and no output
        file set yet (so no `Als2` alias and an empty file name). This needs
        no preferences. Codec-based formats (H.264/AVI) are not reproduced
        because their format options are not available without an open AE.

        Args:
            render_settings_ldat: The render settings item for the parent
                render queue item (used for dimension resolution).
            parent: The parent RenderQueueItem.

        Returns:
            A tuple of (OutputModule model, list of chunks for LIST:LOm).
        """
        om_ldat_item = OutputModuleSettingsItem()
        roou = RouuChunk()  # defaults reproduce AE's fresh image-sequence Rouu
        ropt = TiffRoptChunk()  # AE's exact 602-byte TIFF format options
        hdrm = HdrmChunk()
        hdr_json = Utf8Chunk(value="{}")
        name_utf8 = Utf8Chunk(value="TIFF Sequence with Alpha")
        # A freshly added module has no output file: AE leaves the file name
        # empty and writes no Als2 alias (it is created when a path is set).
        file_name_utf8 = Utf8Chunk()

        lom_chunks: list[Chunk] = [
            roou,
            ropt,
            hdrm,
            hdr_json,
            name_utf8,
            file_name_utf8,
        ]

        om = cls(
            _om_ldat=om_ldat_item,
            _roou=roou,
            _alas_utf8=None,
            _file_name_utf8=file_name_utf8,
            _name_utf8=name_utf8,
            _render_settings_ldat=render_settings_ldat,
            parent=parent,
            format_options=None,
        )
        om._finalize_roou()  # resolve output dimensions to the comp

        return om, lom_chunks

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
        return self._name_utf8.value

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
        if comp_id is None or self.post_render_action in (
            PostRenderAction.NONE,
            PostRenderAction.IMPORT,
        ):
            return self._parent_rqi.comp
        return cast("CompItem", self._project.items[comp_id])

    @post_render_target_comp.setter
    def post_render_target_comp(self, comp: CompItem) -> None:
        if not isinstance(comp, CompItem):
            raise ValueError("post_render_target_comp must be a CompItem")
        if comp.id not in self._project.items:
            raise ValueError("post_render_target_comp must be an item in the project")
        self._om_ldat.post_render_target_comp_id = comp.id

    @property
    def settings(self) -> SettingsView:
        """[SettingsView][py_aep.models.settings.SettingsView] dict with
        ExtendScript-compatible keys. Includes `"Video Output"`,
        `"Audio Bit Depth"`, `"Preserve RGB"`, `"Convert to Linear Light"`,
        etc. Matches the format from
        `OutputModule.get_settings(GetSettingsFormat.NUMBER)`.
        """
        return SettingsView(self, OM_SETTINGS)

    @settings.setter
    def settings(self, value: Mapping[str, Any]) -> None:
        if not isinstance(value, Mapping):
            raise ValueError("Settings must be a dictionary of key-value pairs")
        view = self.settings
        # One transaction: the keys of a settings dict are coupled, so they
        # must apply in any order, and a key that raises has to roll the
        # whole dict back - an earlier key's `post_set` clamp may already
        # have moved its dependents, leaving neither the old state nor the
        # requested one.
        with self.batch_edit():
            for k, v in value.items():
                # A full `settings` dict includes read-only keys (e.g.
                # "Format", "Channels"); skip any key whose value is
                # unchanged so a round-tripped dict applies cleanly, while a
                # real write to a read-only key still raises. An unknown key
                # short-circuits to `__setitem__`, which names the valid keys
                # (reading it here would raise a bare KeyError).
                if k in OM_SETTINGS and view[k] == v:
                    continue
                view[k] = v

    @property
    def _video_output(self) -> bool:
        return bool(self._roou.width > 0 or self._roou.height > 0)

    @_video_output.setter
    def _video_output(self, value: bool) -> None:
        validate_bool(value)
        # Format gate is necessary: turning video on for an audio
        # format would write comp dimensions into an audio-only Rouu.
        _validate_for_format("Video Output")(value, self)
        if value:
            w, h = self._effective_dimensions
            self._roou.width = w
            self._roou.height = h
        else:
            self._roou.width = 0
            self._roou.height = 0

    @property
    def _output_audio(self) -> OutputAudio:
        """Output audio setting (derived from two binary sources)."""
        audio_enabled = self._roou.audio_disabled_hi != 0xFF
        return map_output_audio(audio_enabled, bool(self._om_ldat.output_audio))

    @_output_audio.setter
    def _output_audio(self, value: OutputAudio) -> None:
        _validate_for_format("Output Audio")(value, self)
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

    def _rules_context(self) -> dict[str, object]:
        """Current setting values used to match conditional rules.

        Only cleanly-decoded values enter the context: a raw fallback
        (an out-of-enum byte or param from a real file), an absent
        format-option param, or a missing format-options object leaves
        its key absent, so the rules that condition on it simply do not
        apply (permissive degradation).
        """
        context: dict[str, object] = {}
        for key in ("Channels", "Audio Channels", "Audio Sample Rate"):
            try:
                value = getattr(self, OM_SETTINGS[key][0])
            except ValueError:
                # Enum transform without a from_binary fallback (e.g.
                # OutputChannels) raises on an out-of-enum stored byte.
                continue
            if isinstance(value, IntEnum):
                context[key] = value
        fo = self._format_options
        if isinstance(fo, XmlFormatOptions):
            for key, value in (
                ("Audio Codec", fo.audio_codec),
                ("Video Codec", fo.video_codec),
                ("Audio Format", fo.mpeg_audio_format),
                ("Audio Layer", fo.mpeg_audio_layer),
                ("Multiplexer", fo.mpeg_multiplexer),
            ):
                if isinstance(value, IntEnum):
                    context[key] = value
            if isinstance(fo.bitrate, int):
                context["BitRate"] = fo.bitrate
        elif isinstance(fo, CineonFormatOptions):
            if isinstance(fo.file_format, IntEnum):
                context["File Format"] = fo.file_format
        return context

    def _check_format_rule(self, key: str, value: Any) -> None:
        """Raise if `value` violates `allowed_values(format, key)` right now
        (write-time semantics: the other fields are read as they are now).

        Batch mode defers to the batch_edit exit validation. Unknown format
        ids - third-party output plugins whose 4cc is not in `OutputFormat` -
        skip the check entirely.
        """
        if self._batch_depth:
            return
        fmt = self._format
        if not isinstance(fmt, OutputFormat):
            return
        allowed = allowed_values(fmt, key, self._rules_context())
        if allowed is None or value in allowed:
            return
        labels = ", ".join(
            # `label` (output-module enums) > `name` (plain IntEnums, which
            # str() to their bare value on 3.11+) > str (ints, strings).
            getattr(v, "label", None) or getattr(v, "name", None) or str(v)
            for v in sorted(allowed, key=lambda v: (isinstance(v, str), v))
        )
        raise ValueError(
            f"{key} {value!r} is not available for format {fmt.label!r}. "
            f"Allowed: {labels}"
        )

    # Bypass accessors used by `_apply_singleton_clamps`: clamps write the
    # chunk field / raw param directly (never through the descriptor) so a
    # clamp can never recurse into validation. Table invariants in
    # tests/unit/test_output_module_rules.py prove clamped values are
    # always inside the format's own allowed sets.
    _CLAMP_ACCESSORS: ClassVar[
        dict[
            str,
            tuple[Callable[[OutputModule], Any], Callable[[OutputModule, Any], None]],
        ]
    ] = {
        "Color": (
            lambda om: om._color_mode,
            lambda om, v: setattr(om._roou, "color_premultiplied", int(v)),
        ),
        "Depth": (
            lambda om: om._depth,
            lambda om, v: setattr(om._roou, "depth", int(v)),
        ),
        "Audio Sample Rate": (
            lambda om: om._audio_sample_rate,
            lambda om, v: setattr(
                om._roou, "audio_sample_rate", AudioSampleRate.to_binary(v)
            ),
        ),
        "Audio Channels": (
            lambda om: om._audio_channels,
            lambda om, v: setattr(om._roou, "audio_channels", int(v)),
        ),
        "Audio Bit Depth": (
            lambda om: om._audio_bit_depth,
            lambda om, v: setattr(om._roou, "audio_bit_depth", int(v)),
        ),
        "Audio Format": (
            lambda om: _xml_options_of(om, "mpeg_audio_format"),
            lambda om, v: _set_xml_param_raw(om, "ADBEMPEGAudioFormat", int(v)),
        ),
    }

    def _apply_singleton_clamps(self, keys: tuple[str, ...]) -> None:
        """Force dependent settings whose allowed set became a singleton.

        Mirrors AE's dialog re-resolving dependent dropdowns after a
        context change (codec, bitrate, channels). Only fires when the
        rules leave exactly one legal value; multi-valued sets are left
        alone (the stored value may be stale until the user writes it,
        per the write-time validation contract). The context is rebuilt
        per key so an earlier clamp (e.g. GSM forcing mono) feeds the
        later ones.
        """
        if self._batch_depth:
            return  # deferred to the batch_edit exit validation
        fmt = self._format
        if not isinstance(fmt, OutputFormat):
            return
        for key in keys:
            allowed = allowed_values(fmt, key, self._rules_context())
            if allowed is None or len(allowed) != 1:
                continue
            forced = next(iter(allowed))
            getter, setter = self._CLAMP_ACCESSORS[key]
            try:
                current = getter(self)
            except ValueError:
                continue  # out-of-enum stored byte: leave it alone
            if current != forced:
                setter(self, forced)

    # Current-value getters for whole-state validation. Enum-backed OM
    # reads can raise on out-of-enum stored bytes; `validate_state`
    # treats that (and raw fallbacks) as "unclean context -> skip".
    _STATE_GETTERS: ClassVar[dict[str, Callable[[OutputModule], Any]]] = {
        "Video Output": lambda om: om._video_output,
        "Output Audio": lambda om: om._output_audio,
        "Channels": lambda om: om._channels,
        "Depth": lambda om: om._depth,
        "Color": lambda om: om._color_mode,
        "Audio Sample Rate": lambda om: om._audio_sample_rate,
        "Audio Channels": lambda om: om._audio_channels,
        "Audio Bit Depth": lambda om: om._audio_bit_depth,
        "Audio Codec": lambda om: _xml_options_of(om, "audio_codec"),
        "Video Codec": lambda om: _xml_options_of(om, "video_codec"),
        "Audio Format": lambda om: _xml_options_of(om, "mpeg_audio_format"),
        "Multiplexer": lambda om: _xml_options_of(om, "mpeg_multiplexer"),
        "BitRate": lambda om: _xml_options_of(om, "bitrate"),
        "Audio Bitrate": lambda om: _xml_options_of(om, "audio_bitrate"),
    }

    # Keys whose stored value is a plain int/bool by design (everything
    # else must decode to an enum member to be checked).
    _RAW_VALUE_KEYS: ClassVar[frozenset] = frozenset(
        {"Video Output", "BitRate", "Audio Bitrate"}
    )

    # Keys inert while the corresponding output stream is disabled: AE
    # leaves stale bytes there and so do we.
    _AUDIO_STATE_KEYS: ClassVar[frozenset] = frozenset(
        {
            "Audio Sample Rate",
            "Audio Channels",
            "Audio Bit Depth",
            "Audio Bitrate",
            "BitRate",
        }
    )
    _VIDEO_STATE_KEYS: ClassVar[frozenset] = frozenset(
        {"Channels", "Depth", "Color", "Video Codec"}
    )

    def validate_state(self) -> list[tuple[str, Any, frozenset]]:
        """Check every rule-covered setting against the current context.

        Returns a list of `(key, value, allowed)` violations (empty when
        the state is consistent). Used by `batch_edit` on exit and by the
        corpus self-validation test; also useful to lint a parsed file.

        Stale-by-design values are skipped: settings of a disabled
        audio/video stream, absent format-option params, and raw
        fallbacks from out-of-enum stored bytes (the binary is trusted).
        """
        violations: list[tuple[str, Any, frozenset]] = []
        fmt = self._format
        if not isinstance(fmt, OutputFormat):
            return violations
        context = self._rules_context()
        audio_on = self._output_audio != OutputAudio.OFF
        video_on = self._video_output
        for key in sorted(constrained_keys(fmt)):
            if not audio_on and key in self._AUDIO_STATE_KEYS:
                continue
            if not video_on and key in self._VIDEO_STATE_KEYS:
                continue
            allowed = allowed_values(fmt, key, context)
            if allowed is None:
                continue
            try:
                value = self._STATE_GETTERS[key](self)
            except ValueError:
                continue  # out-of-enum stored byte: unclean, skip
            if value is None:
                continue
            if key in self._RAW_VALUE_KEYS:
                if not isinstance(value, int):
                    continue  # raw string fallback (garbage param): skip
            elif not isinstance(value, IntEnum):
                continue  # raw fallback: unclean, skip
            if key == "Audio Sample Rate" and value == AudioSampleRate.OFF:
                # from_binary maps any unknown stored rate to OFF, so OFF
                # under enabled audio is an unclean legacy value, not a
                # user choice (OFF is never in an allowed set).
                continue
            if value not in allowed:
                violations.append((key, value, allowed))
        return violations

    def _snapshot_state(self) -> tuple[bytes, bytes, bytes | None, str | None, bool]:
        """Capture the batch rollback state (settings + format header/options)."""
        lom_chunks = self._parent_rqi._lom.chunks
        try:
            start, end = self._block_span(lom_chunks)
        except ValueError:
            # _block_span locates this module's Roou by identity; it is
            # gone exactly when the module was removed.
            raise RuntimeError(
                "This output module was removed from its render queue "
                "item; it can no longer be edited."
            ) from None
        ropt_bytes: bytes | None = None
        for i in range(start, end):
            if lom_chunks[i].chunk_type == "Ropt":
                ropt_bytes = lom_chunks[i].tobytes()
                break
        hdr10_value: str | None = None
        fo = self._format_options
        if isinstance(fo, PngFormatOptions) and fo._hdr10_utf8 is not None:
            hdr10_value = fo._hdr10_utf8.value
        return (
            self._om_ldat.tobytes(),
            self._roou.tobytes(),
            ropt_bytes,
            hdr10_value,
            fo is not None,
        )

    def _restore_state(
        self, snapshot: tuple[bytes, bytes, bytes | None, str | None, bool]
    ) -> None:
        """Roll the module back to a `_snapshot_state` capture."""
        ldat_bytes, roou_bytes, ropt_bytes, hdr10_value, had_options = snapshot
        # In-place field copy keeps the item's identity in the ldat list.
        restored_item = OutputModuleSettingsItem.frombytes(ldat_bytes)
        assert isinstance(restored_item, OutputModuleSettingsItem)
        self._om_ldat.restore_from(restored_item)
        lom_chunks = self._parent_rqi._lom.chunks
        start, end = self._block_span(lom_chunks)
        new_roou = RouuChunk.frombytes(roou_bytes, chunk_type="Roou")
        assert isinstance(new_roou, RouuChunk)
        lom_chunks[start] = new_roou
        self._roou = new_roou
        if ropt_bytes is not None:
            for i in range(start, end):
                if lom_chunks[i].chunk_type == "Ropt":
                    lom_chunks[i] = RoptChunk.frombytes(ropt_bytes, chunk_type="Ropt")
                    break
        # Restore the PNG HDR10 sidecar before re-deriving the wrapper
        # (the wrapper caches the parsed JSON).
        fo = self._format_options
        if (
            hdr10_value is not None
            and isinstance(fo, PngFormatOptions)
            and fo._hdr10_utf8 is not None
        ):
            fo._hdr10_utf8.value = hdr10_value
        # Detach the outgoing wrapper. A reference the caller fetched
        # before the rollback wraps an Ropt that is no longer in the tree,
        # so its writes must hit the "detached" guard rather than land in
        # an orphaned body and be silently dropped from the saved file.
        if fo is not None:
            fo._detached = True
        # A module built without a format-options wrapper (_new) must
        # come out of a rollback the same way.
        if had_options:
            self._format_options = parse_format_options(lom_chunks[start:end])
            if self._format_options is not None:
                self._format_options._parent_om = self
        else:
            self._format_options = None

    @contextlib.contextmanager
    def batch_edit(self) -> Iterator[OutputModule]:
        """Edit several coupled settings as one transaction.

        Inside the block, per-write format validation and clamps are
        deferred, so coupled settings can be written in any order. On
        exit the final state is validated as a whole: any violation (or
        an exception in the block) rolls the module back to its state at
        entry and raises a single `ValueError` listing every violation.

        Covers the output-module settings, the format header (`Rouu`)
        and the format options (`Ropt` + PNG HDR10 sidecar). File path
        and module name writes are not rolled back. References held to
        `format_options` across a failed batch are stale - re-fetch.
        Nested batches are reentrant; the outermost one validates.

        Example:
            ```python
            with om.batch_edit():
                om.format_options.audio_codec = AudioCodec.GSM_6_10
                om.settings["Audio Channels"] = AudioChannels.MONO
                om.settings["Audio Sample Rate"] = 22050
            ```
        """
        if self._batch_depth:
            self._batch_depth += 1
            try:
                yield self
            finally:
                self._batch_depth -= 1
            return
        snapshot = self._snapshot_state()
        old_channels = self._om_ldat.channels
        self._batch_depth = 1
        try:
            yield self
        except BaseException:
            self._restore_state(snapshot)
            raise
        finally:
            self._batch_depth = 0
        # A channels change re-resolves exactly once, at exit (AE
        # re-resolves when the dropdown changes) - the same work
        # `_sync_after_channels` does for a bare write, which defers to
        # here. Both halves must run: clamping Color only on the bare path
        # would make a batch REJECT a write that succeeds outside one. A
        # batch that never changed channels keeps explicit Depth writes
        # as-is; the parity rules then decide whether the pair is legal.
        if self._om_ldat.channels != old_channels:
            self._pair_depth_to_channels()
            self._apply_singleton_clamps(("Color",))
        violations = self.validate_state()
        if violations:
            self._restore_state(snapshot)

            def _fmt(v: Any) -> str:
                return getattr(v, "name", None) or str(v)

            details = "; ".join(
                f"{key}: {_fmt(value)} not in "
                f"{{{', '.join(sorted(_fmt(v) for v in allowed))}}}"
                for key, value, allowed in violations
            )
            raise ValueError(f"batch_edit rolled back, invalid final state: {details}")

    def _pair_depth_to_channels(self) -> None:
        """Re-pair the depth to the alpha choice (RGBA <-> `+` depths)."""
        depth_val = int(self._depth)
        is_rgba = self._om_ldat.channels == int(OutputChannels.RGBA)
        target = _DEPTH_PLUS if is_rgba else _DEPTH_MINUS
        if depth_val in target:
            self._roou.depth = target[depth_val]

    def _sync_after_channels(self) -> None:
        """Re-resolve depth and color after a `_channels` write.

        Depth keeps its alpha pairing (RGBA <-> `+` depth variants); the
        Color mode is clamped when the new channels leave a single legal
        value (EXR forces premultiplied, PNG forces straight - only
        meaningful when alpha is included). Inside a batch the whole
        re-resolution is deferred to the exit (an in-batch pairing flip
        would make the batch outcome order-dependent).
        """
        if self._batch_depth:
            return
        self._pair_depth_to_channels()
        self._apply_singleton_clamps(("Color",))

    def _clamp_audio_dependents(self) -> None:
        """Re-resolve audio settings after an `_audio_channels` write."""
        self._apply_singleton_clamps(("Audio Sample Rate", "Audio Bit Depth"))

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
            return rqi._use_this_frame_rate
        return rqi.comp.frame_rate

    def _update_output_dimensions(self) -> None:
        """Recompute _roou.width and _roou.height from current settings.

        When resize is enabled, _roou.width/height hold the resize targets
        and must not be overwritten. When video output is off (audio
        formats, audio-only movies) the dimensions must stay 0: writing
        comp dimensions here would flip video output on - the exact
        corruption the `Video Output` format gate exists to prevent -
        via a mundane crop/resize/ROI write.
        """
        if not self._video_output:
            return
        if self._om_ldat.resize:
            return

        self._roou.width, self._roou.height = self._effective_dimensions

    def _finalize_roou(self) -> None:
        """Apply the runtime touches AE adds to a freshly built/applied Rouu.

        After Effects writes two things on top of the stored format header:
        the `applied_marker` byte, and the comp-resolved output dimensions
        for video formats (audio-only formats keep width/height=0).
        """
        self._roou.applied_marker = 1
        if self._roou.width > 0:  # video format; audio keeps 0
            self._update_output_dimensions()

    @property
    def _output_color_space(self) -> str | None:
        """Output color space derived from ICC profile and working space."""
        return map_output_color_space(
            self._om_ldat.output_profile_id,
            bool(self._om_ldat.output_color_space_working),
            self._project.working_space,
        )

    @property
    def output_color_space(self) -> str:
        """The output color space (Output Module Settings > Color Management).
        Read / Write.

        Reading returns the name of an Adobe ICC profile (e.g. `"ARRI LogC3
        Wide Color Gamut - EI 800"`), the OCIO color-space name (reverse-mapped
        from the id via the project's OCIO configuration), or - when set to the
        working color space - the project's working-space name (mirroring AE).

        Writable as `"Working Color Space"`, a catalogued Adobe ICC profile name
        (Adobe CMS mode; the 16-byte profile ID is written, no ICC bytes needed),
        or - in OCIO mode - any color space, role, alias, or `display/view` pair
        of the project's OCIO configuration (the 16-byte id is computed from the
        config; see [ocio_output_profile_id][py_aep.color.ocio.ocio_output_profile_id]).

        Note:
            Not exposed in ExtendScript."""
        project = self._project
        ldat = self._om_ldat
        if (
            project.color_management_system == ColorManagementSystem.OCIO
            and not ldat.output_color_space_working
        ):
            config = resolve_ocio_config(project.ocio_configuration_file)
            if config is not None:
                name = ocio_color_space_for_profile_id(
                    config, bytes(ldat.output_profile_id)
                )
                if name is not None:
                    return name
        return self._output_color_space or ""

    @output_color_space.setter
    def output_color_space(self, value: str) -> None:
        validate_string(value)
        ldat = self._om_ldat
        if value == "Working Color Space":
            ldat.output_color_space_working = 1
            ldat.output_profile_id = b"\xff" * 16
            return
        project = self._project
        if project.color_management_system == ColorManagementSystem.OCIO:
            config = require_ocio_config(
                project.ocio_configuration_file,
                f"compute the output color space id for {value!r}",
            )
            ldat.output_color_space_working = 0
            ldat.output_profile_id = ocio_output_profile_id(config, value)
            return
        profile_id = profile_id_for_name(value)
        if profile_id is None:
            raise NotImplementedError(
                f"Output color space {value!r} is not a known Adobe ICC profile."
            )
        ldat.output_color_space_working = 0
        ldat.output_profile_id = profile_id

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
            return self._roou.starting_number
        rqi = self._parent_rqi
        start_seconds = rqi.time_span_start
        frame_rate = rqi.comp.frame_rate
        return int(round(start_seconds * frame_rate))

    @_starting_number.setter
    def _starting_number(self, value: int) -> None:
        _validate_number(min=0, max=9999999, integer=True)(value)
        self._roou.starting_number = value

    @property
    def _resize_to(self) -> list[int]:
        """Resize dimensions as [width, height]."""
        return [self._roou.width, self._roou.height]

    @_resize_to.setter
    def _resize_to(self, value: list[int]) -> None:
        validate_sequence(min=1, max=30000, length=2, integer=True)(value)
        if not self._video_output:
            # Writing resize targets into the Rouu would flip video
            # output on (dimensions ARE the video-output flag).
            raise ValueError(
                "'Resize to' requires video output, which is off "
                "(and unavailable for audio formats)."
            )
        self._roou.width, self._roou.height = value

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
        text = self._alas_utf8.value
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
        return self._roou.video_codec or None

    @property
    def _resolve_extension(self) -> str | None:
        """Derive file extension from format_id, with Cineon special case."""
        format_id = self._roou.format_id
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
        return self._file_name_utf8.value

    @property
    def file_template(self) -> str:
        """The raw file path template, may contain `[compName]` and
        `[fileExtension]` variables. Read / Write."""
        return self._build_file_template(
            self._folder_path, self._file_name_template, self._is_folder
        )

    @file_template.setter
    def file_template(self, value: str) -> None:
        validate_string(value)
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
            text = self._alas_utf8.value
            data = json.loads(text) if text else {}
            if not isinstance(data, dict):
                data = {}
            data["fullpath"] = folder_path
            self._alas_utf8.value = json.dumps(data)

        if self._file_name_utf8 is not None:
            self._file_name_utf8.value = file_name

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
            return settings_to_string(
                self.settings, build_resize_to_strings(self._project._preferences)
            )
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

    @property
    def templates(self) -> list[str]:
        """Available output module template names.

        Requires `ae_preferences_dir` to have been passed to `parse()`.
        Returns an empty list if no preferences directory was provided.
        """
        try:
            return [t.name for t in self._project._get_output_templates()]
        except ValueError:
            return []

    def apply_template(self, name: str) -> None:
        """Apply an output module template by name.

        Copies the template's settings (channels, resize, crop, audio,
        post-render action, etc.) and format info (Rouu data) to this
        output module.

        The `format_options` object is rebuilt for the new format:
        references held to the previous one are stale afterwards -
        re-fetch `om.format_options`.

        Requires `ae_preferences_dir` to have been passed to `parse()`.

        Args:
            name: Template name (e.g. `"Lossless"`, `"H.264 - Match Render Settings - 15 Mbps"`).

        Raises:
            ValueError: If the template name is not found.
        """
        templates = self._project._get_output_templates()
        for template in templates:
            if template.name == name:
                self._apply_output_template(template)
                return
        names = [t.name for t in templates]
        raise ValueError(f"Template {name!r} not found. Available: {names}")

    def _block_span(self, lom_chunks: list[Chunk]) -> tuple[int, int]:
        """Return `[start, end)` indices of this module's chunk block in LOm.

        The block starts at this module's `Roou` (located by identity, as
        attrs `__eq__` is structural) and runs to the next `Roou` or the
        end of the list - the same span the parser builds with
        `split_on_type(lom_chunks, "Roou")`.
        """
        start = index_by_identity(lom_chunks, self._roou)
        end = len(lom_chunks)
        for i in range(start + 1, len(lom_chunks)):
            if lom_chunks[i].chunk_type == "Roou":
                end = i
                break
        return start, end

    def _apply_output_template(self, template: OutputModuleTemplate) -> None:
        """Apply a parsed output-module template to this module's chunks.

        Sets the per-module settings, the format header (`Rouu`), the format
        options (`Ropt`, from the prefs "Output File Options" section), and
        the module name.

        Note:
            The `Ropt` and name match After Effects byte-for-byte, but the
            `Rouu` header and the settings come from the on-disk preferences
            representation, which AE transforms when it applies a template -
            so those two are not yet byte-identical to AE's runtime output.
        """
        lom_chunks = self._parent_rqi._lom.chunks
        self._om_ldat.copy_settings_from(template.settings)

        # The LOm list holds every output module of the RQ item back to back.
        # Locate this module's own block (its Roou up to the next Roou) by
        # identity so edits below never touch a sibling module.
        roou_idx, block_end = self._block_span(lom_chunks)

        if template.format_info is not None:
            new_roou = RouuChunk.frombytes(template.format_info, chunk_type="Roou")
            assert isinstance(new_roou, RouuChunk)
            lom_chunks[roou_idx] = new_roou
            self._roou = new_roou
            self._finalize_roou()  # marker bit + comp-resolved dimensions

        # Replace the Ropt with the template's format options (or an empty
        # Ropt for formats that have none, e.g. AIFF). Scope the search to
        # this module's block so a sibling module's Ropt is never hit.
        new_ropt: Chunk = (
            RoptChunk.frombytes(template.format_options, chunk_type="Ropt")
            if template.format_options is not None
            else RoptChunk()
        )
        for i in range(roou_idx, block_end):
            if lom_chunks[i].chunk_type == "Ropt":
                lom_chunks[i] = new_ropt
                break

        # The new Ropt may be a different format from the one _format_options
        # wrapped at parse time, so re-derive it from this module's block the
        # same way parsing does. Detach the outgoing wrapper first: a
        # reference the caller fetched before this call wraps the replaced
        # Ropt, so its writes must hit the "detached" guard rather than land
        # in an orphaned body and be silently dropped from the saved file.
        if self._format_options is not None:
            self._format_options._detached = True
        self._format_options = parse_format_options(lom_chunks[roou_idx:block_end])
        if self._format_options is not None:
            self._format_options._parent_om = self

        if self._name_utf8 is not None:
            self._name_utf8.value = template.name

    def remove(self) -> None:
        """Remove this output module from the render queue item.

        Raises:
            RuntimeError: If this is the last output module (AE requires
                at least one).
        """
        if len(self._parent_rqi._output_modules) <= 1:
            raise RuntimeError("Cannot remove the last output module")

        rqi = self._parent_rqi
        om_idx = rqi._output_modules.index(self)

        # Remove this module's chunk block from LOm (its Roou to the next Roou
        # or end). Located by identity and bounded the same way the parser
        # splits modules, so byte-equal sibling modules are never hit.
        lom_chunks = rqi._lom.chunks
        roou_idx, end_idx = self._block_span(lom_chunks)
        del lom_chunks[roou_idx:end_idx]

        om_ldat = cast(
            "LdatChunk",
            find_by_type(chunks=rqi._list_chunk.chunks, chunk_type="ldat"),
        )
        del om_ldat.items[om_idx]

        om_lhd3 = cast(
            "Lhd3Chunk",
            find_by_type(chunks=rqi._list_chunk.chunks, chunk_type="lhd3"),
        )
        set_lhd3_count(om_lhd3, om_lhd3.count - 1, LHD3_BLOCK_SINGLE)

        del rqi._output_modules[om_idx]
