from __future__ import annotations

import typing
from datetime import datetime, timedelta
from typing import Any

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

from ...binary.chunk import ContainerChunk
from ...binary.scalar_chunks import Utf8Chunk
from ..descriptors import (
    ChunkField,
)
from ..transforms import compute_fractional, compute_ratio
from .settings import (
    SettingsView,
    settings_to_number,
    settings_to_string,
)

if typing.TYPE_CHECKING:
    from typing import Iterator

    from ...binary.chunk import Chunk, ListChunk
    from ...binary.render_chunks import RenderSettingsItem
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


def _compute_ldat_frame_rate(body: RenderSettingsItem) -> float:
    """Compute render-settings frame rate from integer/fractional fields."""
    return compute_fractional(body, "frame_rate_integer", "frame_rate_fractional")


def _compute_ldat_time_span_start(body: RenderSettingsItem) -> float:
    """Compute time-span start in seconds from dividend/divisor fields."""
    if body.time_span_start_divisor == 0:
        return 0.0
    return compute_ratio(body, "time_span_start_dividend", "time_span_start_divisor")


def _compute_ldat_time_span_duration(body: RenderSettingsItem) -> float:
    """Compute time-span duration in seconds from dividend/divisor fields."""
    if body.time_span_duration_divisor == 0:
        return 0.0
    return compute_ratio(
        body,
        "time_span_duration_dividend",
        "time_span_duration_divisor",
    )


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

    queue_item_notify = ChunkField[bool]("_ldat", "queue_item_notify")
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

    _skip_existing_files = ChunkField[bool](
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
        _list_chunk: Chunk,
        _rcom_utf8: Utf8Chunk | None = None,
        parent: RenderQueue,
        comp: CompItem,
        output_modules: list[OutputModule],
    ) -> None:
        self._ldat = _ldat
        self._litm = _litm
        self._list_chunk = _list_chunk
        self._rcom_utf8 = _rcom_utf8
        self._parent_rq = parent
        self._comp = comp
        self._output_modules = output_modules

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
        if not isinstance(value, str):
            raise ValueError("Comment must be a string")
        if self._rcom_utf8 is not None:
            self._rcom_utf8.value = value
        else:
            utf8_chunk = Utf8Chunk(chunk_type="Utf8", value=value)
            rcom_chunk = ContainerChunk(
                chunk_type="RCom",
                chunks=[utf8_chunk],
            )
            idx = next(
                i for i, c in enumerate(self._litm.chunks)
                if c is self._list_chunk
            )
            self._litm.chunks.insert(idx, rcom_chunk)
            self._rcom_utf8 = utf8_chunk

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
        if not self.output_modules:
            raise AttributeError("No output modules to set skip_frames on")
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError("skip_frames must be a non-negative number")
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
        if len(value) != 2:
            raise ValueError(f"Resolution must be [x, y], got {len(value)} elements")
        x, y = round(value[0]), round(value[1])
        if x <= 0 or y <= 0:
            raise ValueError(f"Resolution divisors must be positive, got [{x}, {y}]")
        self._ldat.resolution_x = x
        self._ldat.resolution_y = y
        for om in self.output_modules:
            om._update_output_dimensions()

    @property
    def _use_this_frame_rate(self) -> float:
        """Custom frame rate value."""
        return _compute_ldat_frame_rate(self._ldat)

    @_use_this_frame_rate.setter
    def _use_this_frame_rate(self, value: float) -> None:
        fval = float(value)
        if fval < 0.1:
            raise ValueError(
                f"Frame rate must be greater than or equal to 0.1, got {fval}"
            )
        elif fval > 999:
            raise ValueError(
                f"Frame rate must be less than or equal to 999, got {fval}"
            )
        self._ldat.frame_rate_integer = int(fval)
        self._ldat.frame_rate_fractional = round((fval - int(fval)) * 65536)

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
    def settings(self, value: dict[str, Any]) -> None:
        view = self.settings
        for k, v in value.items():
            if k in view:
                try:
                    view[k] = v
                except AttributeError:
                    pass

    def _resolved_time_span(self) -> tuple[float, float]:
        """Return (start, duration) in seconds based on time span source."""
        source = TimeSpanSource.from_binary(self._ldat.time_span_source)
        if source == TimeSpanSource.LENGTH_OF_COMP:
            return 0.0, self.comp.duration
        if source == TimeSpanSource.WORK_AREA_ONLY:
            return self.comp.work_area_start, self.comp.work_area_duration
        return (
            _compute_ldat_time_span_start(self._ldat),
            _compute_ldat_time_span_duration(self._ldat),
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
        dividend_field: str,
        divisor_field: str,
        is_frames: bool = False,
    ) -> None:
        """Write a time span value, switching to CUSTOM.

        Args:
            value: Time in seconds, or frame count if `is_frames` is True.
            dividend_field: Name of the dividend field on `_ldat`.
            divisor_field: Name of the divisor field on `_ldat`.
            is_frames: When True, `value` is a frame count and is converted
                to seconds via the composition frame rate before writing.

        Raises:
            ValueError: If `value` is negative for start fields, or
                non-positive for duration fields.
        """
        is_duration = "duration" in dividend_field
        if is_duration and value <= 0:
            raise ValueError(f"Duration must be positive, got {value}")
        if not is_duration and value < 0:
            raise ValueError(f"Start time must be non-negative, got {value}")
        self._ldat.time_span_source = int(TimeSpanSource.CUSTOM)
        divisor = getattr(self._ldat, divisor_field)
        if divisor == 0:
            divisor = self._ldat.frame_rate_integer or round(self.comp.frame_rate)
            setattr(self._ldat, divisor_field, divisor)
        if is_frames:
            value = value / self.comp.frame_rate
        setattr(self._ldat, dividend_field, round(value * divisor))

    @property
    def time_span_start(self) -> float:
        """
        The time in the composition, in seconds, at which rendering will
        begin. Read / Write.

        Setting this switches the time span source to CUSTOM.
        """
        return self._resolved_time_span()[0]

    @time_span_start.setter
    def time_span_start(self, value: float) -> None:
        self._set_time_span(
            value=value,
            dividend_field="time_span_start_dividend",
            divisor_field="time_span_start_divisor",
        )

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
        self._set_time_span(
            value=value,
            dividend_field="time_span_duration_dividend",
            divisor_field="time_span_duration_divisor",
        )

    @property
    def time_span_start_frame(self) -> int:
        """The time in the composition, in frames, at which rendering will
        begin. Read / Write.

        Setting this switches the time span source to CUSTOM.
        """
        return self._resolved_time_span_frames()[0]

    @time_span_start_frame.setter
    def time_span_start_frame(self, value: int) -> None:
        self._set_time_span(
            value=value,
            dividend_field="time_span_start_dividend",
            divisor_field="time_span_start_divisor",
            is_frames=True,
        )

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
        self._set_time_span(
            value=value,
            dividend_field="time_span_duration_dividend",
            divisor_field="time_span_duration_divisor",
            is_frames=True,
        )

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

    def set_setting(self, key: str, value: Any) -> None:
        """Set a single render setting.

        Accepts enum members, int values, or string labels.

        Args:
            key: The setting key (e.g. `"Quality"`, `"Frame Rate"`).
            value: The value to set.

        Raises:
            KeyError: If the key is unknown.
            AttributeError: If the key is read-only.
            ValueError: If the value cannot be coerced to the expected type.
        """
        self.settings[key] = value

    def set_settings(self, settings: dict[str, Any]) -> None:
        """Set multiple render settings at once.

        Accepts enum members, int values, or string labels.

        Args:
            settings: Dict of setting keys to values.

        Raises:
            KeyError: If any key is unknown.
            AttributeError: If any key is read-only.
            ValueError: If any value cannot be coerced.
        """
        live = self.settings
        for key, value in settings.items():
            live[key] = value
