from __future__ import annotations

import typing
from typing import Any

from py_aep.enums import (
    BlendingMode,
    FrameBlendingType,
    LayerQuality,
    LayerSamplingQuality,
    TrackMatteType,
)

from ...kaitai.descriptors import ChunkField
from ...kaitai.utils import propagate_check
from .layer import Layer

if typing.TYPE_CHECKING:
    from ..items.item import Item


def _reverse_frame_blending(value: FrameBlendingType, _body: Any) -> dict[str, int]:
    """Decompose FrameBlendingType into frame_blending + frame_blending_mode bits."""
    if value == FrameBlendingType.NO_FRAME_BLEND:
        return {"frame_blending": 0}
    return {
        "frame_blending": 1,
        "frame_blending_mode": int(value == FrameBlendingType.PIXEL_MOTION),
    }


class AVLayer(Layer):
    """
    The `AVLayer` object provides an interface to those layers that contain
    [AVItem][] objects (composition layers, footage layers, solid layers, text
    layers and sound layers).

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        comp = app.project.compositions[0]
        layer = comp.file_layers[0]
        print(layer.source)
        ```

    Info:
        `AVLayer` is a subclass of [Layer][] object. All methods and attributes
        of [Layer][] are available when working with `AVLayer`.

    Info:
        `AVLayer` is a base class for [TextLayer][] object, so `AVLayer`
        attributes and methods are available when working with [TextLayer][]
        objects.

    See: https://ae-scripting.docsforadobe.dev/layer/avlayer/
    """

    adjustment_layer: bool = ChunkField.bool("_ldta", "adjustment_layer")  # type: ignore[assignment]
    """When `True`, the layer is an adjustment layer. Read / Write."""

    audio_enabled = ChunkField.bool("_ldta", "audio_enabled")
    """When `True`, the layer's audio is enabled. This value corresponds
    to the audio toggle switch in the Timeline panel. Read / Write."""

    blending_mode = ChunkField.enum(BlendingMode, "_ldta", "blending_mode")
    """The blending mode of the layer. Read / Write."""

    collapse_transformation = ChunkField.bool("_ldta", "collapse_transformation")
    """`True` if collapse transformation is on for this layer.
    Read / Write."""

    effects_active = ChunkField.bool("_ldta", "effects_active")
    """`True` if the layer's effects are active, as indicated by the
    <f> icon next to it in the user interface. Read / Write."""

    environment_layer: bool = ChunkField.bool(  # type: ignore[assignment]
        "_ldta", "environment_layer", post_set="_on_environment_layer_set"
    )
    """`True` if this is an environment layer in a Ray-traced 3D
    composition. Setting this to `True` automatically sets
    [three_d_layer][] to `True`. Read / Write."""

    frame_blending_type = ChunkField.enum(
        FrameBlendingType,
        "_ldta",
        "frame_blending_type",
        reverse_instance_field=_reverse_frame_blending,
    )
    """The type of frame blending for the layer. Read / Write."""

    guide_layer = ChunkField.bool("_ldta", "guide_layer")
    """`True` if the layer is a guide layer. Read / Write."""

    motion_blur = ChunkField.bool("_ldta", "motion_blur")
    """`True` if motion blur is enabled for the layer. Read / Write."""

    preserve_transparency = ChunkField.bool("_ldta", "preserve_transparency")
    """`True` if preserve transparency is enabled for the layer.
    Read / Write."""

    quality = ChunkField.enum(LayerQuality, "_ldta", "quality")
    """The layer's draft quality setting. Read / Write."""

    sampling_quality = ChunkField.enum(
        LayerSamplingQuality, "_ldta", "sampling_quality"
    )
    """The layer's sampling method. Read / Write."""

    three_d_layer = ChunkField.bool(
        "_ldta", "three_d_layer", post_set="_on_three_d_layer_set"
    )
    """`True` if this layer is a 3D layer. Setting this to `True`
    automatically sets [environment_layer][] to `False`.
    Read / Write."""

    three_d_per_char = ChunkField.bool("_ldta", "three_d_per_char")
    """`True` if this layer has the Enable Per-character 3D switch set,
    allowing its characters to be animated off the plane of the text
    layer. Applies only to text layers. Read / Write."""

    track_matte_type = ChunkField.enum(TrackMatteType, "_ldta", "track_matte_type")
    """Specifies the way the track matte is applied. Read / Write."""

    _source_id = ChunkField[int]("_ldta", "source_id")
    """The ID of the source item for this layer. 0 for a text layer."""

    def _on_environment_layer_set(self) -> None:
        if self._ldta.environment_layer:
            self._ldta.three_d_layer = 1
            propagate_check(self._ldta)

    def _on_three_d_layer_set(self) -> None:
        if self._ldta.three_d_layer:
            self._ldta.environment_layer = 0
            propagate_check(self._ldta)

    @property
    def _matte_layer_id(self) -> int:
        """The ID of the layer used as a track matte for this layer.

        `0` when no track matte is applied.
        Conditional in the binary (AE >= 23 only).
        """
        # matte_layer_id is conditional in aep.ksy (only in AE >= 23)
        return getattr(self._ldta, "matte_layer_id", 0) or 0

    def _should_clamp_times(self) -> bool:
        """Whether layer timing should be clamped to source duration.

        After Effects clamps in/outPoint when queried via ExtendScript
        for non-still footage layers without time remapping enabled.
        """
        source = self.source
        if source is None:
            return False
        if hasattr(source, "main_source") and source.main_source.is_still:
            return False
        if self.time_remap_enabled:
            return False
        source_duration = getattr(source, "duration", 0)
        if source_duration <= 0:
            return False
        if self.stretch < 0:
            return False
        return True

    @property
    def in_point(self) -> float:
        """The "in" point of the layer, expressed in composition time
        (seconds). Clamped to `start_time` for non-still footage layers.
        Read / Write.
        """
        raw = float(self.start_time + self._ldta.in_point * self._stretch_factor)
        if not self._should_clamp_times():
            return raw
        return max(raw, self.start_time)

    @in_point.setter
    def in_point(self, value: float) -> None:
        self._set_raw_in_point(value)

    @property
    def out_point(self) -> float:
        """The "out" point of the layer, expressed in composition time
        (seconds). Clamped to `start_time + source.duration * stretch` for
        non-still footage layers without time remapping. Read / Write.
        """
        raw = float(self.start_time + self._ldta.out_point * self._stretch_factor)
        if not self._should_clamp_times():
            return raw
        source_duration = getattr(self.source, "duration", 0)
        max_out = float(self.start_time + source_duration * self._stretch_factor)
        return min(raw, max_out)

    @out_point.setter
    def out_point(self, value: float) -> None:
        self._set_raw_out_point(value)

    @property
    def frame_blending(self) -> bool:
        """`True` if frame blending is enabled for this layer. Read-only."""
        return self.frame_blending_type != FrameBlendingType.NO_FRAME_BLEND

    @property
    def source(self) -> Item | None:
        """The source item for this layer. `None` for a text layer. Read-only."""
        try:
            return self._source_cache
        except AttributeError:
            if self._source_id == 0:
                self._source_cache: Item | None = None
                return None
            result = self.containing_comp._project.items.get(self._source_id)
            if result is not None:
                self._source_cache = result
            return result

    @source.setter
    def source(self, value: Item) -> None:
        self._source_id = value.id if value is not None else 0
        self._source_cache = value

    @property
    def has_video(self) -> bool:
        """`True` if the layer has a video component. An `AVLayer` has video
        when its [source][] has video, or when the layer has no external source
        (text and shape layers always render video). Read-only.
        """
        source = self.source
        if source is None:
            return True
        return bool(getattr(source, "has_video", True))

    @property
    def has_audio(self) -> bool:
        """`True` if the layer has an audio component. Read-only."""
        source = self.source
        if source is None:
            return False
        return bool(getattr(source, "has_audio", False))

    @property
    def audio_active(self) -> bool:
        """`True` if the layer's audio is active at the current time.

        For this to be `True`, [audio_enabled][] must be `True`,
        [has_audio][] must be `True`, no other layer with audio may be
        soloing unless this layer is also soloed, and the current
        [time][] must be between [in_point][] and [out_point][].
        Read-only.
        """
        return self.audio_active_at_time(self.time)

    def audio_active_at_time(self, time: float) -> bool:
        """Return whether the layer's audio is active at the given time.

        For this method to return `True`, four conditions must be met:

        1. [has_audio][] must be `True`.
        2. [audio_enabled][] must be `True`.
        3. No other layer with audio in the
           [containing_comp][Layer.containing_comp] may be soloed unless
           this layer is also [soloed][Layer.solo].
        4. *time* must fall between [in_point][] (inclusive) and
           [out_point][] (exclusive).

        Args:
            time: The time in seconds.
        """
        if not self.has_audio:
            return False

        if not self.audio_enabled:
            return False

        any_solo = any(
            layer.solo
            for layer in self.containing_comp.layers
            if isinstance(layer, AVLayer) and layer.has_audio
        )
        if any_solo and not self.solo:
            return False

        if time < self.in_point or time >= self.out_point:
            return False

        return True

    @property
    def can_set_collapse_transformation(self) -> bool:
        """`True` if it is possible to set the
        [collapse_transformation][AVLayer.collapse_transformation] value.

        Returns `True` for pre-composition layers and solid layers.
        Read-only.
        """
        from ..items.composition import CompItem
        from ..items.footage import FootageItem
        from ..sources.solid import SolidSource

        source = self.source
        if source is None:
            return False
        if isinstance(source, CompItem):
            return True
        if isinstance(source, FootageItem):
            ms = source.main_source
            if isinstance(ms, SolidSource):
                return True
        return False

    @property
    def can_set_time_remap_enabled(self) -> bool:
        """`True` if it is possible to enable time remapping on this layer.

        Time remapping can be enabled when the layer's source has a
        non-zero duration (i.e. it is not a still image or text layer).
        Read-only.
        """
        source = self.source
        if source is None:
            return False
        duration = getattr(source, "duration", 0)
        return duration > 0

    @property
    def time_remap_enabled(self) -> bool:
        """`True` if time remapping is enabled for this layer. Read / Write."""
        try:
            prop = self["ADBE Time Remapping"]
        except KeyError:
            return False
        return bool(prop._animated)  # type: ignore[union-attr]

    @time_remap_enabled.setter
    def time_remap_enabled(self, value: bool) -> None:
        prop = self["ADBE Time Remapping"]
        prop._animated = value  # type: ignore[union-attr]

    @property
    def width(self) -> int:
        """The width of the layer in pixels.

        Returns the source item's width if available, otherwise falls back
        to the containing composition's width (matches ExtendScript behavior
        for source-less layers like text and shape layers). Read-only.
        """
        source = self.source
        if source is not None:
            return getattr(source, "width", 0)
        return self.containing_comp.width

    @property
    def height(self) -> int:
        """The height of the layer in pixels.

        Returns the source item's height if available, otherwise falls back
        to the containing composition's height (matches ExtendScript behavior
        for source-less layers like text and shape layers). Read-only.
        """
        source = self.source
        if source is not None:
            return getattr(source, "height", 0)
        return self.containing_comp.height

    @property
    def has_track_matte(self) -> bool:
        """
        `True` if this layer has track matte. When true, this layer's `track_matte_type`
        value controls how the matte is applied. Read-only.
        """
        return self.track_matte_type != TrackMatteType.NO_TRACK_MATTE

    @property
    def is_track_matte(self) -> bool:
        """`True` if this layer is being used as a track matte. Read-only."""
        return any(
            isinstance(layer, AVLayer) and layer._matte_layer_id == self.id
            for layer in self.containing_comp.layers
        )

    @property
    def track_matte_layer(self) -> AVLayer | None:
        """The track matte layer for this layer. Returns `None` if this layer has no
        track matte layer. Read-only."""
        if self._matte_layer_id == 0:
            return None
        layer = self.containing_comp.layers_by_id.get(self._matte_layer_id)
        if isinstance(layer, AVLayer):
            return layer
        return None

    @property
    def auto_name(self) -> str:
        """Fall back to source name, then empty string."""
        source = self.source
        if source is not None:
            return source.name
        return self._auto_name or ""

    @property
    def is_name_from_source(self) -> bool:
        """
        True if the layer has no expressly set name, but contains a named source.

        In this case, layer.name has the same value as layer.source.name.
        False if the layer has an expressly set name, or if the layer does not
        have a source. Read-only.
        """
        return self.source is not None and not self.is_name_set
