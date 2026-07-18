from __future__ import annotations

import copy
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Mapping, cast

from py_aep.enums import (
    ColorDepthSetting,
    DiskCacheSetting,
    EffectsSetting,
    FieldRender,
    FrameBlendingSetting,
    FrameRateSetting,
    GetSettingsFormat,
    GuideLayers,
    LogType,
    MotionBlurSetting,
    ProxyUseSetting,
    PulldownSetting,
    RenderQuality,
    RQItemStatus,
    SoloSwitchesSetting,
    TimeSpanSource,
)

from ...binary.chunk import ContainerChunk, ListChunk
from ...binary.ldat_chunks import (
    LHD3_BLOCK_SINGLE,
    LdatChunk,
    Lhd3Chunk,
    set_lhd3_count,
)
from ...binary.mutations import build_om_container, build_rout_block, clone_chunk_tree
from ...binary.render_chunks import RenderSettingsItem, RoutItem
from ...binary.scalar_chunks import Utf8Chunk
from ...binary.utils import find_by_type, index_by_identity, split_on_type
from ..descriptors import (
    ChunkField,
)
from ..validators import (
    _validate_number,
    validate_bool,
    validate_positive_int,
    validate_positive_number,
    validate_sequence,
    validate_string,
)
from .settings import (
    SettingsView,
    settings_to_number,
    settings_to_string,
)

if TYPE_CHECKING:
    from typing import Any, Iterator

    from ..items.composition import CompItem
    from ..project import Project
    from .output_module import OutputModule
    from .render_queue import RenderQueue

_AEP_EPOCH = datetime(1904, 1, 1)


def _start_time_from_binary(value: int) -> datetime | None:
    """Convert Mac HFS+ epoch timestamp to datetime, or None if 0."""
    if not value:
        return None
    return _AEP_EPOCH + timedelta(seconds=value)


# ---------------------------------------------------------------------------
# RENDER_SETTINGS: ExtendScript key -> (attribute, optional enum class)
# ---------------------------------------------------------------------------

RENDER_SETTINGS: dict[str, tuple[str, type | None]] = {
    "3:2 Pulldown": ("_pulldown", PulldownSetting),
    "Color Depth": ("_color_depth", ColorDepthSetting),
    "Disk Cache": ("_disk_cache", DiskCacheSetting),
    "Effects": ("_effects", EffectsSetting),
    "Field Render": ("_field_render", FieldRender),
    "Frame Blending": ("_frame_blending", FrameBlendingSetting),
    "Frame Rate": ("_frame_rate_setting", FrameRateSetting),
    "Guide Layers": ("_guide_layers", GuideLayers),
    "Motion Blur": ("_motion_blur", MotionBlurSetting),
    "Proxy Use": ("_proxy_use", ProxyUseSetting),
    "Quality": ("_quality", RenderQuality),
    "Resolution": ("_resolution", None),
    "Skip Existing Files": ("_skip_existing_files", None),
    "Solo Switches": ("_solo_switches", SoloSwitchesSetting),
    "Time Span Duration": ("time_span_duration", None),
    "Time Span End": ("time_span_end", None),
    "Time Span Start": ("time_span_start", None),
    "Time Span": ("_time_span_source", TimeSpanSource),
    "Use comp's frame rate": ("_comp_frame_rate", None),
    "Use this frame rate": ("_use_this_frame_rate", None),
}


class RenderQueueItem:
    """
    The `RenderQueueItem` object represents an individual item in the render
    queue. It provides access to the specific settings for an item to be
    rendered.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        rq_item = app.project.render_queue.items[0]
        print(rq_item.status)
        for output_module in rq_item:
            ...
        ```

    See: https://ae-scripting.docsforadobe.dev/renderqueue/renderqueueitem/
    """

    elapsed_seconds = ChunkField[int]("_ldat", "elapsed_seconds", read_only=True)
    """The number of seconds that have elapsed in rendering this item.
    Read-only."""

    log_type = ChunkField.enum(
        LogType,
        "_ldat",
        "log_type",
    )
    """A log type for this item, indicating which events should be logged
    while this item is being rendered. Read / Write."""

    name = ChunkField[str](
        "_ldat",
        "template_name",
    )
    """The name of the render settings template used for this item.
    Read / Write."""

    queue_item_notify = ChunkField.bool("_ldat", "queue_item_notify", min_version=22)
    """When `True`, a user notification is enabled for this render queue
    item, signaling the user upon render completion. Read / Write."""

    start_time: ChunkField[datetime | None] = ChunkField(
        "_ldat",
        "start_time",
        transform=_start_time_from_binary,
        read_only=True,
    )
    """The date and time when rendering of this item started, or `None` if
    the item has not started rendering. Read-only."""

    status = ChunkField.enum(
        RQItemStatus,
        "_ldat",
        "status",
        post_set="_on_status_changed",
    )
    """The current render status of the item. Read / Write."""

    def _on_status_changed(self) -> None:
        """Reset start_time and elapsed_seconds for non-terminal statuses."""
        if self.status in self._RESET_STATUSES:
            self._ldat.start_time = 0
            self._ldat.elapsed_seconds = 0

    _color_depth = ChunkField.enum(
        ColorDepthSetting,
        "_ldat",
        "color_depth",
    )

    _disk_cache = ChunkField.enum(
        DiskCacheSetting,
        "_ldat",
        "disk_cache",
    )

    _effects = ChunkField.enum(
        EffectsSetting,
        "_ldat",
        "effects",
    )

    _field_render = ChunkField.enum(
        FieldRender,
        "_ldat",
        "field_render",
    )

    _frame_blending = ChunkField.enum(
        FrameBlendingSetting,
        "_ldat",
        "frame_blending",
    )

    _frame_rate_setting = ChunkField.enum(
        FrameRateSetting,
        "_ldat",
        "use_this_frame_rate",
    )

    _guide_layers = ChunkField.enum(
        GuideLayers,
        "_ldat",
        "guide_layers",
    )

    _motion_blur = ChunkField.enum(
        MotionBlurSetting,
        "_ldat",
        "motion_blur",
    )

    _proxy_use = ChunkField.enum(
        ProxyUseSetting,
        "_ldat",
        "proxy_use",
    )

    _pulldown = ChunkField.enum(
        PulldownSetting,
        "_ldat",
        "pulldown",
    )

    _quality = ChunkField.enum(
        RenderQuality,
        "_ldat",
        "quality",
    )

    _skip_existing_files = ChunkField.bool(
        "_ldat",
        "skip_existing_files",
    )

    _solo_switches = ChunkField.enum(
        SoloSwitchesSetting,
        "_ldat",
        "solo_switches",
    )

    _time_span_source = ChunkField.enum(
        TimeSpanSource,
        "_ldat",
        "time_span_source",
    )

    def __init__(
        self,
        *,
        _ldat: RenderSettingsItem,
        _litm: ListChunk,
        _list_chunk: ListChunk,
        _lom: ListChunk,
        _rcom: ContainerChunk | None = None,
        _rcom_utf8: Utf8Chunk | None = None,
        _rout_items: list[RoutItem],
        parent: RenderQueue,
        comp: CompItem,
        output_modules: list[OutputModule],
    ) -> None:
        self._ldat = _ldat
        self._litm = _litm
        self._list_chunk = _list_chunk
        self._lom = _lom
        self._rcom = _rcom
        self._rcom_utf8 = _rcom_utf8
        self._rout_items = _rout_items
        self._parent_rq = parent
        self._comp = comp
        self._output_modules = output_modules

    @classmethod
    def _new(
        cls,
        comp: CompItem,
        *,
        parent: RenderQueue,
    ) -> RenderQueueItem:
        """Create a new RenderQueueItem for a composition.

        Constructs all backing chunks from scratch with default render
        settings and a single output module. If default templates are
        available from AE preferences, their settings are applied.

        Args:
            comp: The composition to render.
            parent: The parent RenderQueue.

        Returns:
            The new RenderQueueItem model.
        """
        project = parent.parent

        # Create render settings with comp-specific values; the remaining
        # fields default to AE's factory "Best Settings" render template.
        rs_item = RenderSettingsItem(comp_id=comp.id)
        # AE writes a fixed 30 in this "use this frame rate" slot for a fresh
        # item (the active setting is "use comp's frame rate", so it's an
        # unused placeholder); the real rate comes from the comp.
        rs_item.frame_rate_integer = 30
        # Match a freshly-added AE item: status NEEDS_OUTPUT (no output file
        # yet) and time span = work area (the source stores zero dividend/
        # divisor; the span is derived from the comp's work area).
        rs_item.status = RQItemStatus.NEEDS_OUTPUT.to_binary()
        rs_item.time_span_source = int(TimeSpanSource.WORK_AREA_ONLY)
        rs_item.time_span_start_divisor = 0
        rs_item.time_span_duration_divisor = 0

        # When ae_preferences_dir was supplied, overlay the user's configured
        # default render-settings template. Only _TEMPLATE_FIELDS are copied,
        # so status / time-span / reserved defaults above are preserved.
        if project._ae_preferences_dir is not None:
            templates = project._get_render_templates()
            default_idx = project._default_render_template_index
            if default_idx is not None and default_idx < len(templates):
                rs_item.copy_settings_from(templates[default_idx])

        rqi = cls(
            _ldat=rs_item,
            _litm=parent._litm,
            _list_chunk=build_om_container(),
            _lom=ListChunk(list_type="LOm ", chunks=[]),
            _rcom=None,
            _rcom_utf8=None,
            _rout_items=build_rout_block(),
            parent=parent,
            comp=comp,
            output_modules=[],
        )

        rqi.add()

        return rqi

    def add(self) -> OutputModule:
        """Add an output module to this render queue item.

        Creates a new [OutputModule][] with default settings (or the
        default template if `ae_preferences_dir` was passed to `parse()`).

        Returns:
            The newly created [OutputModule][].
        """
        from .output_module import OutputModule

        om, lom_chunks = OutputModule._new(
            render_settings_ldat=self._ldat,
            parent=self,
        )

        # A render queue item stores all its output modules in one LOm (split
        # by Roou) and one OM-metadata list. Keep the list's lhd3 capacity
        # counters in sync with the module count (block 1: _count_b /
        # _counter_a / _counter_b all equal `count`), or AE rejects the file
        # with "Invalid read length".
        self._lom.chunks.extend(lom_chunks)

        om_ldat = cast(
            "LdatChunk",
            find_by_type(chunks=self._list_chunk.chunks, chunk_type="ldat"),
        )
        om_ldat.items.append(om._om_ldat)

        om_lhd3 = cast(
            "Lhd3Chunk",
            find_by_type(chunks=self._list_chunk.chunks, chunk_type="lhd3"),
        )
        set_lhd3_count(om_lhd3, om_lhd3.count + 1, LHD3_BLOCK_SINGLE)

        self._output_modules.append(om)
        return om

    def __iter__(self) -> Iterator[OutputModule]:
        """Allow iteration over Output Modules."""
        return iter(self.output_modules)

    def __repr__(self) -> str:
        return (
            f"RenderQueueItem(name={self.name!r}, status={self.status!r}, "
            f"comp_name={self.comp_name!r})"
        )

    @property
    def comp(self) -> CompItem:
        """The composition that will be rendered by this render-queue item.
        Read-only."""
        return self._comp

    @property
    def output_modules(self) -> list[OutputModule]:
        """The list of Output Modules for the item. Read-only."""
        return self._output_modules

    @property
    def parent(self) -> RenderQueue:
        """The [RenderQueue][] containing this item. Read-only."""
        return self._parent_rq

    @property
    def _project(self) -> Project:
        """The project this render queue item belongs to."""
        return self.parent.parent

    _RESET_STATUSES = frozenset(
        {
            RQItemStatus.QUEUED,
            RQItemStatus.UNQUEUED,
            RQItemStatus.NEEDS_OUTPUT,
            RQItemStatus.WILL_CONTINUE,
        }
    )

    @property
    def render(self) -> bool:
        """When `True`, the item will be rendered when the render queue is
        started. Read / Write."""
        return self.status != RQItemStatus.UNQUEUED

    @render.setter
    def render(self, value: bool) -> None:
        validate_bool(value)
        self.status = RQItemStatus.QUEUED if value else RQItemStatus.UNQUEUED

    @property
    def comment(self) -> str:
        """A comment that describes the render queue item. This shows in the
        Render Queue panel. Read / Write."""
        if self._rcom_utf8 is None:
            return ""
        return str(self._rcom_utf8.value)

    @comment.setter
    def comment(self, value: str) -> None:
        validate_string(value)
        if self._rcom_utf8 is not None:
            self._rcom_utf8.value = value
        elif value:
            utf8_chunk = Utf8Chunk(value=value)
            rcom_chunk = ContainerChunk(
                chunk_type="RCom",
                chunks=[utf8_chunk],
            )
            idx = next(
                i for i, c in enumerate(self._litm.chunks) if c is self._list_chunk
            )
            self._litm.chunks.insert(idx, rcom_chunk)
            self._rcom_utf8 = utf8_chunk
            self._rcom = rcom_chunk

    @property
    def skip_frames(self) -> int:
        """The number of frames to skip when rendering this item. Use this to
        do rendering tests that are faster than a full render. A value of 0
        skip no frames, and results in regular rendering of all frames. A
        value of 1 skips every other frame. This is equivalent to "rendering
        on twos." Higher values skip a larger number of frames. The total
        length of time remains unchanged. For example, if skip has a value of
        1, a sequence output would have half the number of frames and in movie
        output, each frame would be double the duration.

        Read / Write.
        """
        if self.output_modules:
            om_frame_rate: int = self.output_modules[0]._roou.frame_rate
            if om_frame_rate > 0:
                return round(self.comp.frame_rate / om_frame_rate) - 1
        return 0

    @skip_frames.setter
    def skip_frames(self, value: int) -> None:
        _validate_number(min=0, max=99, integer=True)(value)
        new_frame_rate = round(self.comp.frame_rate / (value + 1))
        for om in self.output_modules:
            om._roou.frame_rate = new_frame_rate

    @property
    def num_output_modules(self) -> int:
        """
        Return the number of output modules for this render queue item. Read-only.

        Note:
            Equivalent to `len(item.output_modules)`
        """
        return len(self.output_modules)

    @property
    def _resolution(self) -> list[int]:
        """Resolution as [x, y] divisors."""
        return [self._ldat.resolution_x, self._ldat.resolution_y]

    @_resolution.setter
    def _resolution(self, value: list[int]) -> None:
        # [0, 0] is a legal value meaning "Current Settings".
        validate_sequence(length=2, min=0, max=99, integer=True)(value)
        # A HALF-zero pair is not: zero is only meaningful as the both-axes
        # "Current Settings" sentinel. AE's own dialog can only ever produce
        # [0, 0] or a pair with both axes >= 1, and `setSettings` on a
        # half-zero pair NATIVE-CRASHES AE 2026 (probed: [0, 5] and [5, 0]
        # crash; [0, 0], [3, 7] and [99, 99] are all fine). py_aep has no
        # coherent reading for it either - `_effective_dimensions` degrades
        # the 0 to 1, silently rendering full width at a fraction of the
        # height.
        if (value[0] == 0) != (value[1] == 0):
            raise ValueError(
                f'Resolution divisors must both be zero ("Current Settings") '
                f"or both be positive, got [{value[0]}, {value[1]}]"
            )
        self._ldat.resolution_x = value[0]
        self._ldat.resolution_y = value[1]
        for om in self.output_modules:
            om._update_output_dimensions()

    @property
    def _use_this_frame_rate(self) -> float:
        """Custom frame rate value."""
        return self._ldat.frame_rate

    @_use_this_frame_rate.setter
    def _use_this_frame_rate(self, value: float) -> None:
        _validate_number(min=0.1, max=999)(value)
        self._ldat.frame_rate = value

    @property
    def _comp_frame_rate(self) -> float:
        """The composition's frame rate (read-only)."""
        return self.comp.frame_rate

    @property
    def settings(self) -> SettingsView:
        """[SettingsView][py_aep.models.settings.SettingsView] dict
        built live from the binary chunk, with ExtendScript-compatible keys
        matching `get_settings()` output.

        Supports item assignment:

        Example:
            ```python
            rqi.settings["Quality"] = RenderQuality.BEST
            ```
        """
        return SettingsView(self, RENDER_SETTINGS)

    @settings.setter
    def settings(self, value: Mapping[str, Any]) -> None:
        if not isinstance(value, Mapping):
            raise ValueError("Settings must be a dictionary of key-value pairs")
        view = self.settings
        for k, v in value.items():
            view[k] = v

    def _resolved_time_span(self) -> tuple[float, float]:
        """Return (start, duration) in seconds based on time span source."""
        source = TimeSpanSource.from_binary(self._ldat.time_span_source)
        if source == TimeSpanSource.LENGTH_OF_COMP:
            return 0.0, self.comp.duration
        if source == TimeSpanSource.WORK_AREA_ONLY:
            return self.comp.work_area_start, self.comp.work_area_duration
        return (
            self._ldat.time_span_start,
            self._ldat.time_span_duration,
        )

    def _resolved_time_span_frames(self) -> tuple[int, int]:
        """Return (start, duration) in frames based on time span source."""
        source = TimeSpanSource.from_binary(self._ldat.time_span_source)
        fr = self.comp.frame_rate
        if source == TimeSpanSource.LENGTH_OF_COMP:
            return 0, round(self.comp.duration * fr)
        if source == TimeSpanSource.WORK_AREA_ONLY:
            return (
                round(self.comp.work_area_start * fr),
                round(self.comp.work_area_duration * fr),
            )
        start_sec, dur_sec = self._resolved_time_span()
        return round(start_sec * fr), round(dur_sec * fr)

    def _set_time_span(
        self,
        value: float | int,
        field: str,
        is_frames: bool = False,
    ) -> None:
        """Write a time span value, switching to CUSTOM.

        Setting the start keeps the END time fixed and recomputes the duration; setting
        the duration keeps the start. Unlike AE scripting which accepts degenerate spans
        and silently renders garbage (a start before 0 renders void
        lead-in frames, an end before the start renders a single frame) -
        py_aep validates the values like AE's own dialog.

        Args:
            value: Time in seconds, or frame count if `is_frames` is True.
            field: Either "start" or "duration".
            is_frames: When True, `value` is a frame count and is converted
                to seconds via the composition frame rate before writing.

        Raises:
            ValueError: If a start is negative, or if either field would
                leave a duration shorter than one frame (AE's own
                scripting bound); a start keeps the end fixed.
        """
        frame_duration = 1.0 / self.comp.frame_rate
        seconds = value / self.comp.frame_rate if is_frames else float(value)
        # Both fields resolve the span BEFORE switching the source to
        # CUSTOM: a WORK_AREA_ONLY / LENGTH_OF_COMP item takes its span
        # from the comp, so CUSTOM has to carry the resolved values over
        # or the untouched field silently jumps to a stale ldat value.
        old_start, old_duration = self._resolved_time_span()
        if field == "duration":
            if seconds < frame_duration - 1e-9:
                raise ValueError(
                    f"Duration must be at least one frame "
                    f"({frame_duration:.6g}s), got {seconds}"
                )
            self._ldat.time_span_source = int(TimeSpanSource.CUSTOM)
            self._ldat.time_span_start = old_start
            self._ldat.time_span_duration = seconds
            return
        if seconds < 0:
            raise ValueError(f"Start time must be non-negative, got {seconds}")
        new_duration = old_start + old_duration - seconds
        if new_duration <= 0:
            raise ValueError(
                f"Start time {seconds} is at or past the span end "
                f"({old_start + old_duration})"
            )
        # The same one-frame floor the duration path enforces: reaching it
        # through the start must not be a back door to a degenerate span.
        if new_duration < frame_duration - 1e-9:
            raise ValueError(
                f"Start time {seconds} leaves a duration shorter than one "
                f"frame ({frame_duration:.6g}s), got {new_duration}"
            )
        self._ldat.time_span_source = int(TimeSpanSource.CUSTOM)
        self._ldat.time_span_start = seconds
        self._ldat.time_span_duration = new_duration

    @property
    def time_span_start(self) -> float:
        """
        The time in the composition, in seconds, at which rendering will
        begin. Read / Write.

        Setting this keeps the span END fixed - the duration is
        recomputed - and switches the time span source to CUSTOM.
        """
        return self._resolved_time_span()[0]

    @time_span_start.setter
    def time_span_start(self, value: float) -> None:
        self._set_time_span(value, "start")

    @property
    def time_span_duration(self) -> float:
        """
        The duration in seconds of the composition to be rendered. The
        duration is determined by subtracting the start time from the end
        time. Read / Write.

        Setting this switches the time span source to CUSTOM.
        """
        return self._resolved_time_span()[1]

    @time_span_duration.setter
    def time_span_duration(self, value: float) -> None:
        self._set_time_span(value, "duration")

    @property
    def time_span_start_frame(self) -> int:
        """The time in the composition, in frames, at which rendering will
        begin. Read / Write.

        Setting this keeps the span END fixed - the duration is
        recomputed - and switches the time span source to CUSTOM.
        """
        return self._resolved_time_span_frames()[0]

    @time_span_start_frame.setter
    def time_span_start_frame(self, value: int) -> None:
        self._set_time_span(value, "start", is_frames=True)

    @property
    def time_span_duration_frames(self) -> int:
        """The duration in frames of the composition to be rendered. The
        duration is determined by subtracting the start time from the end
        time. Read / Write.

        Setting this switches the time span source to CUSTOM.
        """
        return self._resolved_time_span_frames()[1]

    @time_span_duration_frames.setter
    def time_span_duration_frames(self, value: int) -> None:
        self._set_time_span(value, "duration", is_frames=True)

    @property
    def time_span_end(self) -> float:
        """
        The time in the composition, in seconds, at which rendering will
        end. Read / Write.

        Setting this adjusts the duration, keeping the start unchanged,
        and switches the time span source to CUSTOM.
        """
        ts_start, ts_duration = self._resolved_time_span()
        return ts_start + ts_duration

    @time_span_end.setter
    def time_span_end(self, value: float) -> None:
        validate_positive_number(value)
        self.time_span_duration = value - self.time_span_start

    @property
    def time_span_end_frame(self) -> int:
        """
        The time in the composition, in frames, at which rendering will
        end. Read / Write.

        Setting this adjusts the duration in frames, keeping the start
        unchanged, and switches the time span source to CUSTOM.
        """
        return self.time_span_start_frame + self.time_span_duration_frames

    @time_span_end_frame.setter
    def time_span_end_frame(self, value: int) -> None:
        validate_positive_int(value)
        self.time_span_duration_frames = value - self.time_span_start_frame

    @property
    def comp_name(self) -> str:
        """The name of the composition being rendered."""
        return self.comp.name

    def get_settings(
        self,
        format: GetSettingsFormat = GetSettingsFormat.STRING,
    ) -> dict[str, Any]:
        """Return render settings in the specified format.

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
        """Return a single render setting in the specified format.

        Args:
            key: The setting key (e.g. `"Quality"`, `"Frame Rate"`).
            format: The output format.
        """
        return self.get_settings(format)[key]

    @property
    def templates(self) -> list[str]:
        """Available render settings template names.

        Requires `ae_preferences_dir` to have been passed to `parse()`.
        Returns an empty list if no preferences directory was provided.
        """
        try:
            return [
                t.clean_template_name for t in self._project._get_render_templates()
            ]
        except ValueError:
            return []

    def apply_template(self, name: str) -> None:
        """Apply a render settings template by name.

        Looks up the template from the AE preferences data (requires
        `ae_preferences_dir` in `parse()`) and copies its settings to
        this render queue item.

        Args:
            name: Template name (e.g. `"Best Settings"`, `"Draft Settings"`).

        Raises:
            ValueError: If the template name is not found.
        """
        rs_items = self._project._get_render_templates()
        for t in rs_items:
            if t.clean_template_name == name:
                self._ldat.copy_settings_from(t)
                for om in self._output_modules:
                    om._update_output_dimensions()
                return
        names = [t.clean_template_name for t in rs_items]
        raise ValueError(f"Template {name!r} not found. Available: {names}")

    def remove(self) -> None:
        """Remove this item from the render queue."""
        rq = self._parent_rq
        idx = rq._items.index(self)

        del rq._rs_ldat.items[idx]
        set_lhd3_count(rq._rs_lhd3, rq._rs_lhd3.count - 1, LHD3_BLOCK_SINGLE)

        # AE stores a fixed block of Rout items per RQ item. Delete the whole
        # contiguous block (located by identity of its first entry) and refresh
        # the count, mirroring RenderQueue.add.
        rout_start = index_by_identity(rq._rout.items, self._rout_items[0])
        del rq._rout.items[rout_start : rout_start + len(self._rout_items)]
        rq._rout.count = len(rq._rout.items)

        # RCom, list, LOm chunks removed from LItm by identity
        chunks = self._litm.chunks
        if self._rcom is not None:
            del chunks[index_by_identity(chunks, self._rcom)]
        del chunks[index_by_identity(chunks, self._list_chunk)]
        del chunks[index_by_identity(chunks, self._lom)]

        del rq._items[idx]

        # Removing the last item empties the queue: clear the LSIf/ARsi
        # non-empty marker AE set (the inverse of RenderQueue.add). Verified
        # in AE 2026: it writes 0 here for an empty queue (and normalizes a
        # stale 1 back to 0 on save). The other ARsi state bytes are session
        # UI state with no fixed empty value, so they are left as-is.
        if not rq._items:
            rq._arsi.queue_nonempty = 0
            # An empty queue's settings 'list' holds only an lhd3 (AE writes no
            # ldat). Re-hide the now-empty ldat so the written shape matches a
            # freshly-empty AE queue. add() flips it back on the next add.
            rq._rs_ldat.synthetic = True

    def duplicate(self) -> RenderQueueItem:
        """Create a duplicate of this item in the render queue.

        Returns the new [RenderQueueItem][]. If the original item's status is
        `DONE` or `ERR_STOPPED`, the duplicate's status is set to `QUEUED`.
        """
        rq = self._parent_rq
        idx = rq._items.index(self)

        new_rsi = copy.deepcopy(self._ldat)

        # status holds the raw binary value (ExtendScript value minus 3013),
        # so compare and assign in that encoding via to_binary().
        if RQItemStatus.from_binary(new_rsi.status) in (
            RQItemStatus.DONE,
            RQItemStatus.ERR_STOPPED,
        ):
            new_rsi.status = RQItemStatus.QUEUED.to_binary()

        new_rout_items = [copy.deepcopy(ri) for ri in self._rout_items]

        new_list_chunk = cast("ListChunk", clone_chunk_tree(self._list_chunk))
        new_lom = cast("ListChunk", clone_chunk_tree(self._lom))

        new_rcom: ContainerChunk | None = None
        new_rcom_utf8: Utf8Chunk | None = None
        if self._rcom is not None:
            new_rcom = cast("ContainerChunk", clone_chunk_tree(self._rcom))
            if new_rcom.chunks:
                new_rcom_utf8 = cast("Utf8Chunk", new_rcom.chunks[0])

        rq._rs_ldat.items.insert(idx + 1, new_rsi)
        set_lhd3_count(rq._rs_lhd3, rq._rs_lhd3.count + 1, LHD3_BLOCK_SINGLE)

        # Insert the duplicated Rout block right after this item's block
        # (located by identity of its first entry) and refresh the count.
        rout_start = index_by_identity(rq._rout.items, self._rout_items[0])
        insert_at = rout_start + len(self._rout_items)
        rq._rout.items[insert_at:insert_at] = new_rout_items
        rq._rout.count = len(rq._rout.items)

        # Insert chunks into LItm after this item's chunks (by identity)
        lom_idx = index_by_identity(self._litm.chunks, self._lom)
        insert_at = lom_idx + 1
        if new_rcom is not None:
            self._litm.chunks.insert(insert_at, new_rcom)
            insert_at += 1
        self._litm.chunks.insert(insert_at, new_list_chunk)
        insert_at += 1
        self._litm.chunks.insert(insert_at, new_lom)

        from ...parsers.output_module import parse_output_module  # noqa: PLC0415

        new_om_ldat = cast(
            "LdatChunk", find_by_type(chunks=new_list_chunk.chunks, chunk_type="ldat")
        )
        om_groups = split_on_type(chunks=new_lom.chunks, chunk_type="Roou")

        # Build model first (OMs need parent ref)
        new_item = RenderQueueItem(
            _ldat=new_rsi,
            _litm=self._litm,
            _list_chunk=new_list_chunk,
            _lom=new_lom,
            _rcom=new_rcom,
            _rcom_utf8=new_rcom_utf8,
            _rout_items=new_rout_items,
            parent=rq,
            comp=self._comp,
            output_modules=[],
        )

        output_modules = []
        for i, om_group in enumerate(om_groups):
            om = parse_output_module(om_group, new_om_ldat.items[i], new_item)
            output_modules.append(om)
        new_item._output_modules = output_modules

        # Insert into model list after original
        rq._items.insert(idx + 1, new_item)

        return new_item
