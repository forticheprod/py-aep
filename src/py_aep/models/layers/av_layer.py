from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from py_aep.enums import (
    BlendingMode,
    FrameBlendingType,
    LayerQuality,
    LayerSamplingQuality,
    LayerType,
    TrackMatteType,
)

from ...ae_version import requires_version
from ...binary.layer_chunks import LdtaChunk
from ..descriptors import ChunkField
from ..items.av_item import AVItem
from ..properties.property import Property
from ..validators import validate_enum, validate_number
from .layer import Layer

if TYPE_CHECKING:
    from ..items.composition import CompItem


def _would_create_cycle(target_comp: CompItem, new_source: AVItem) -> bool:
    """Check if using `new_source` as a layer source would create a cycle.

    Walks UP from `target_comp` via `_used_in` back-references and returns
    `True` if `new_source` is found among the ancestors, meaning the
    replacement would create a circular reference chain.
    """
    if not hasattr(new_source, "layers"):
        return False
    visited: set[int] = set()
    stack = [target_comp]
    while stack:
        comp = stack.pop()
        if comp is new_source:
            return True
        comp_id = id(comp)
        if comp_id in visited:
            continue
        visited.add(comp_id)
        for ancestor in comp.used_in:
            stack.append(ancestor)
    return False


def _unregister_source_usage(
    source: AVItem, comp: CompItem, *, exclude: AVLayer | None = None
) -> None:
    """Remove `comp` from `source._used_in` if no other layer still references it.

    Args:
        source: The source item to potentially unregister.
        comp: The composition to remove from `source._used_in`.
        exclude: A layer to skip when scanning for other users (the caller
            itself, which is being removed or swapped out).
    """
    for layer in comp.av_layers:
        if layer is not exclude and layer._source_id == source.id:
            return
    source._used_in.discard(comp)


def _validate_collapse_transformation(value: bool, obj: AVLayer) -> None:
    if not obj.can_set_collapse_transformation:
        raise AttributeError(
            "'collapse_transformation' is read-only when"
            " 'can_set_collapse_transformation' is False."
        )


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

    adjustment_layer = ChunkField[bool]("_ldta", "adjustment_layer")
    """When `True`, the layer is an adjustment layer. Read / Write."""

    audio_enabled = ChunkField[bool]("_ldta", "audio_enabled")
    """When `True`, the layer's audio is enabled. This value corresponds
    to the audio toggle switch in the Timeline panel. Read / Write."""

    blending_mode = ChunkField.enum(BlendingMode, "_ldta", "blending_mode")
    """The blending mode of the layer. Read / Write."""

    collapse_transformation = ChunkField[bool](
        "_ldta",
        "collapse_transformation",
        validate=_validate_collapse_transformation,
    )
    """`True` if collapse transformation is on for this layer.
    Read / Write."""

    effects_active = ChunkField[bool]("_ldta", "effects_active")
    """`True` if the layer's effects are active, as indicated by the
    <f> icon next to it in the user interface. Read / Write."""

    environment_layer = ChunkField[bool](
        "_ldta", "environment_layer", post_set="_on_environment_layer_set"
    )
    """`True` if this is an environment layer in a Ray-traced 3D
    composition. Setting this to `True` automatically sets
    [three_d_layer][] to `True`. Read / Write."""

    frame_blending_type = ChunkField.enum(
        FrameBlendingType,
        "_ldta",
        "frame_blending_type",
    )
    """The type of frame blending for the layer. Read / Write."""

    guide_layer = ChunkField[bool]("_ldta", "guide_layer")
    """`True` if the layer is a guide layer. Read / Write."""

    motion_blur = ChunkField[bool]("_ldta", "motion_blur_flag")
    """`True` if motion blur is enabled for the layer. Read / Write."""

    preserve_transparency = ChunkField[bool]("_ldta", "preserve_transparency")
    """`True` if preserve transparency is enabled for the layer.
    Read / Write."""

    quality = ChunkField.enum(LayerQuality, "_ldta", "quality")
    """The layer's draft quality setting. Read / Write."""

    sampling_quality = ChunkField.enum(
        LayerSamplingQuality, "_ldta", "sampling_quality", min_version=12
    )
    """The layer's sampling method. Read / Write."""

    three_d_layer = ChunkField[bool](
        "_ldta", "three_d_layer", post_set="_on_three_d_layer_set"
    )
    """`True` if this layer is a 3D layer. Setting this to `True`
    automatically sets [environment_layer][] to `False`.
    Read / Write."""

    three_d_per_char = ChunkField[bool]("_ldta", "three_d_per_char")
    """`True` if this layer has the Enable Per-character 3D switch set,
    allowing its characters to be animated off the plane of the text
    layer. Applies only to text layers. Read / Write."""

    _source_id = ChunkField[int]("_ldta", "source_id")
    """The ID of the source item for this layer. 0 for a text layer. Read-only."""

    @classmethod
    def _new(  # type: ignore[override]
        cls,
        *,
        name: str,
        layer_id: int,
        duration: float,
        containing_comp: CompItem,
        source_id: int = 0,
        null_layer: bool = False,
        three_d_layer: bool = False,
        root_tdgp_extra: list[Any] | None = None,
        effect_param_defs: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> AVLayer:
        ae_major = containing_comp._project._head.ae_version_major
        ldta = LdtaChunk(
            layer_id=layer_id,
            quality=2,
            source_id=source_id,
            label=1,
            blending_mode=2,
            layer_type=LayerType.AV,
            matte_layer_id=0 if ae_major >= 23 else None,
            layer_name=name[:31] if len(name) > 31 else name,
        )
        ldta.out_point = duration
        ldta.null_layer = null_layer
        ldta.three_d_layer = three_d_layer
        ldta._reserved_3c = 1
        return cast(
            "AVLayer",
            super()._new(
                ldta=ldta,
                name=name,
                containing_comp=containing_comp,
                root_tdgp_extra=root_tdgp_extra,
                effect_param_defs=effect_param_defs,
            ),
        )

    @property
    def track_matte_type(self) -> TrackMatteType:
        """Specifies the way the track matte is applied.

        Setting `TrackMatteType.NO_TRACK_MATTE` removes the track matte
        for this layer and resets the matte layer reference.

        Note:
            This functionality was updated in After Effects 23.0.

        Warning:
            This is a legacy API. Consider using [set_track_matte][] and
            [remove_track_matte][] instead.

        Read / Write.
        """
        return TrackMatteType.from_binary(self._ldta.track_matte_type)

    @track_matte_type.setter
    def track_matte_type(self, value: TrackMatteType | int) -> None:
        validate_enum(TrackMatteType)(value)
        value = TrackMatteType(value)
        old_matte = self.track_matte_layer
        self._ldta.track_matte_type = value.to_binary()
        if (
            value == TrackMatteType.NO_TRACK_MATTE
            and self._ldta.matte_layer_id is not None
        ):
            self._ldta.matte_layer_id = 0
            if old_matte is not None:
                self._re_enable_matte(old_matte)

    def _on_environment_layer_set(self) -> None:
        if self._ldta.environment_layer:
            self._ldta.three_d_layer = True

    def _on_three_d_layer_set(self) -> None:
        if self._ldta.three_d_layer:
            self._ldta.environment_layer = False

    @property
    def _matte_layer_id(self) -> int:
        """The ID of the layer used as a track matte for this layer.

        `0` when no track matte is applied.
        Conditional in the binary (AE >= 23 only).
        """
        # matte_layer_id is conditional (only in AE >= 23)
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
        if source.duration <= 0:
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
        raw_in_point = self._ldta.in_point
        raw = float(self.start_time + raw_in_point * self._stretch_factor)
        if not self._should_clamp_times():
            return raw
        return max(raw, self.start_time)

    @in_point.setter
    def in_point(self, value: float) -> None:
        validate_number(value)
        self._set_raw_in_point(value)

    @property
    def out_point(self) -> float:
        """The "out" point of the layer, expressed in composition time
        (seconds). Clamped to `start_time + source.duration * stretch` for
        non-still footage layers without time remapping. Read / Write.
        """
        raw_out_point = self._ldta.out_point
        raw = float(self.start_time + raw_out_point * self._stretch_factor)
        if not self._should_clamp_times():
            return raw
        assert self.source is not None  # _should_clamp_times guards
        source_duration = self.source.duration
        max_out = float(self.start_time + source_duration * self._stretch_factor)
        return min(raw, max_out)

    @out_point.setter
    def out_point(self, value: float) -> None:
        validate_number(value)
        self._set_raw_out_point(value)

    @property
    def frame_blending(self) -> bool:
        """`True` if frame blending is enabled for this layer. Read-only."""
        return self.frame_blending_type != FrameBlendingType.NO_FRAME_BLEND

    @property
    def source(self) -> AVItem | None:
        """The source item for this layer. `None` for a text layer. Read-only."""
        from ..items.av_item import AVItem

        try:
            return self._source
        except AttributeError:
            if self._source_id == 0:
                self._source: AVItem | None = None
                return None
            else:
                result = self.containing_comp._project.items.get(self._source_id)
                if result is not None:
                    self._source = cast(AVItem, result)
                    return self._source
                return None

    @property
    def has_video(self) -> bool:
        """`True` if the layer has a video component. An `AVLayer` has video
        when its [source][] has video, or when the layer has no external source
        (text and shape layers always render video). Read-only.
        """
        source = self.source
        if source is None:
            return True
        return bool(source.has_video)

    @property
    def has_audio(self) -> bool:
        """`True` if the layer has an audio component. Read-only."""
        source = self.source
        if source is None:
            return False
        return bool(source.has_audio)

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
        validate_number(time)

        if not self.has_audio:
            return False

        if not self.audio_enabled:
            return False

        any_solo = any(
            getattr(layer, "has_audio", False)
            for layer in self.containing_comp.solo_layers
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
        if self.source is None:
            return False
        return self.source.duration > 0

    @property
    def time_remap_enabled(self) -> bool:
        """`True` if time remapping is enabled for this layer. Read / Write."""
        try:
            prop = self["ADBE Time Remapping"]
        except KeyError:
            return False
        if not isinstance(prop, Property):
            return False
        return bool(prop._animated)

    @time_remap_enabled.setter
    def time_remap_enabled(self, value: bool) -> None:
        if not self.can_set_time_remap_enabled:
            raise AttributeError(
                "'time_remap_enabled' is read-only when"
                " 'can_set_time_remap_enabled' is False."
            )
        prop = self["ADBE Time Remapping"]
        if isinstance(prop, Property):
            prop._animated = bool(value)

    @property
    def width(self) -> int:
        """The width of the layer in pixels.

        Returns the source item's width if available, otherwise falls back
        to the containing composition's width (matches ExtendScript behavior
        for source-less layers like text and shape layers). Read-only.
        """
        if self.source is not None:
            return self.source.width
        return self.containing_comp.width

    @property
    def height(self) -> int:
        """The height of the layer in pixels.

        Returns the source item's height if available, otherwise falls back
        to the containing composition's height (matches ExtendScript behavior
        for source-less layers like text and shape layers). Read-only.
        """
        if self.source is not None:
            return self.source.height
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
        # AE 23+: explicit ID-based references
        if any(
            layer._matte_layer_id == self.id for layer in self.containing_comp.av_layers
        ):
            return True
        # Pre-2023 positional fallback: layer below has has_track_matte
        layers = self.containing_comp.layers
        idx = self.index
        if idx + 1 < len(layers):
            below = layers[idx + 1]
            if (
                isinstance(below, AVLayer)
                and below._matte_layer_id == 0
                and below.has_track_matte
            ):
                return True
        return False

    @property
    def track_matte_layer(self) -> AVLayer | None:
        """The track matte layer for this layer. Returns `None` if this layer has no
        track matte layer. Read-only."""
        # AE 23+: explicit ID-based lookup
        if self._matte_layer_id != 0:
            layer = self.containing_comp.layers_by_id.get(self._matte_layer_id)
            if isinstance(layer, AVLayer):
                return layer
            return None
        # Pre-2023 positional fallback: matte is the layer directly above
        if self.has_track_matte:
            idx = self.index
            if idx > 0:
                layers = self.containing_comp.layers
                above = layers[idx - 1]
                if isinstance(above, AVLayer):
                    return above
        return None

    @property
    def auto_name(self) -> str:
        """Fall back to source name, then empty string."""
        if self.source is not None:
            return self.source.name
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

    # ------------------------------------------------------------------
    # Mutation methods
    # ------------------------------------------------------------------

    def _re_enable_matte(self, matte: AVLayer) -> None:
        """Re-enable `matte` if no other layer in the comp uses it."""
        for layer in self.containing_comp.av_layers:
            if layer is not self and layer._matte_layer_id == matte.id:
                return
        matte.enabled = True

    @requires_version(23)
    def set_track_matte(
        self,
        track_matte_layer: AVLayer | None,
        track_matte_type: TrackMatteType | int,
    ) -> None:
        """Sets the track matte layer and type for this layer.
        Passing in `None` to `track_matte_layer` parameter removes
        the track matte. See [remove_track_matte] for another way
        of removing track matte.

        Note:
            Requires AE 23.0+ file format.

        Args:
            track_matte_layer: The layer to use as a track matte,
                or `None` to remove the track matte.
            track_matte_type: The [TrackMatteType][] to apply.
                Passing `NO_TRACK_MATTE` with a non-`None` layer
                is a no-op.

        Raises:
            AttributeError: If the file predates AE 23.0.
            ValueError: If `track_matte_layer` belongs to a
                different composition.
        """
        validate_enum(TrackMatteType)(track_matte_type)
        track_matte_type = TrackMatteType(track_matte_type)
        if track_matte_layer is not None and not isinstance(track_matte_layer, AVLayer):
            raise ValueError("track_matte_layer must be an AVLayer or None.")
        if (
            track_matte_layer is not None
            and track_matte_type == TrackMatteType.NO_TRACK_MATTE
        ):
            return

        if (
            track_matte_layer is not None
            and track_matte_layer.containing_comp is not self.containing_comp
        ):
            raise ValueError("track_matte_layer must belong to the same composition.")

        # Re-enable old matte if it is being replaced
        old_matte = self.track_matte_layer
        if old_matte is not None and old_matte is not track_matte_layer:
            self._re_enable_matte(old_matte)

        self._ldta.track_matte_type = track_matte_type.to_binary()

        if track_matte_layer is not None:
            self._ldta.matte_layer_id = track_matte_layer.id
            track_matte_layer.enabled = False
        else:
            self._ldta.matte_layer_id = 0

    @requires_version(23)
    def remove_track_matte(self) -> None:
        """Remove the track matte layer reference.

        The [track_matte_type][] value is preserved. To also reset
        it, assign `TrackMatteType.NO_TRACK_MATTE` separately.

        Note:
            Requires AE 23.0+ file format.

        Raises:
            AttributeError: If the file predates AE 23.0.
        """

        old_matte = self.track_matte_layer
        self._ldta.matte_layer_id = 0

        if old_matte is not None:
            self._re_enable_matte(old_matte)

    def replace_source(self, new_source: AVItem, fix_expressions: bool = False) -> None:
        """Replace the source item for this layer.

        Warning:
            Contrary to ExtendScript, if this method is performed
            on a null layer, the layer's `null_layer` attribute
            changes to `False`, making the layer visible
            in comp viewer and renders.

        Args:
            new_source: The new source [AVItem][].
            fix_expressions: Update expressions that reference the
                old source name. Not yet implemented.

        Raises:
            NotImplementedError: If `fix_expressions` is `True`.
            ValueError: If the layer has no source (e.g. shape or
                text layers), if `new_source` is not in the project,
                if `new_source` would create a composition cycle, or
                if the layer is a 3D model layer.
        """
        if fix_expressions:
            raise NotImplementedError("fix_expressions is not yet supported.")

        if self.source is None:
            raise ValueError("layer does not have a source")

        # 3D model layers cannot have their source
        # replaced - AE silently ignores the call but we raise.
        if self._ldta.layer_type == 5:
            raise ValueError("replace_source is not supported on 3D model layers")

        if not isinstance(new_source, AVItem):
            raise ValueError("new_source must be an AVItem.")

        comp = self.containing_comp
        project = comp._project
        if new_source.id not in project.items:
            raise ValueError(
                f"Item {new_source.name!r} (id={new_source.id}) is not in the project."
            )

        if _would_create_cycle(comp, new_source):
            raise ValueError(
                f"Item {new_source.name!r} (id={new_source.id}) "
                "can't be used as a source because it would create "
                "a composition cycle."
            )

        old_source = self.source
        if old_source is not None and hasattr(old_source, "_used_in"):
            _unregister_source_usage(old_source, comp, exclude=self)

        self._source_id = new_source.id
        self._source = new_source

        new_source._used_in.add(comp)

        if self.null_layer:
            self._ldta.null_layer = False
