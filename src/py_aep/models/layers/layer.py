from __future__ import annotations

import typing
from typing import Any, List, cast

from py_aep.enums import AutoOrientType, Label

from ...kaitai.descriptors import ChunkField
from ...kaitai.reverses import reverse_ratio
from ...kaitai.transforms import strip_null
from ...kaitai.utils import create_chunk, propagate_check
from ..properties.marker import MarkerValue
from ..properties.property import Property
from ..properties.property_group import PropertyGroup

if typing.TYPE_CHECKING:
    from ...kaitai import Aep
    from ..items.composition import CompItem


_reverse_start_time = reverse_ratio("start_time")
_reverse_in_point = reverse_ratio("in_point")
_reverse_out_point = reverse_ratio("out_point")


def _reverse_auto_orient(value: AutoOrientType, _body: Any) -> dict[str, int]:
    """Decompose AutoOrientType into individual ldta bit flags."""
    return {
        "auto_orient_along_path": int(value == AutoOrientType.ALONG_PATH),
        "camera_or_poi_auto_orient": int(
            value == AutoOrientType.CAMERA_OR_POINT_OF_INTEREST
        ),
        "characters_toward_camera": int(
            value == AutoOrientType.CHARACTERS_TOWARD_CAMERA
        ),
        "three_d_per_char": int(value == AutoOrientType.CHARACTERS_TOWARD_CAMERA),
    }


def _reverse_stretch(value: float, _body: Any) -> dict[str, int]:
    """Decompose stretch (percentage) into dividend/divisor."""
    _TIME_DIVISOR = 10000
    if value == 0:
        return {"stretch_dividend": 0, "stretch_divisor": 0}
    return {
        "stretch_dividend": round(value * _TIME_DIVISOR / 100.0),
        "stretch_divisor": _TIME_DIVISOR,
    }


class Layer(PropertyGroup):
    """
    The `Layer` object provides access to layers within compositions.

    Info:
        `Layer` is a subclass of [PropertyGroup][], which is a subclass of
        [PropertyBase][py_aep.models.properties.property_base.PropertyBase]. All
        methods and attributes of [PropertyGroup][], in addition to those listed below,
        are available when working with `Layer` objects.

    Info:
        `Layer` is the base class for [CameraLayer][] object, [LightLayer][]
        object and [AVLayer][] object, so `Layer` attributes and methods are
        available when working with all layer types.

    See: https://ae-scripting.docsforadobe.dev/layer/layer/
    """

    # Maps ldta layer_type.name to ExtendScript match name.
    _LAYER_MATCH_NAMES: dict[str, str] = {
        "avlayer": "ADBE AV Layer",
        "shape": "ADBE Vector Layer",
        "text": "ADBE Text Layer",
        "camera": "ADBE Camera Layer",
        "light": "ADBE Light Layer",
        "three_d_model": "ADBE 3D Model Layer",
    }

    # Maps ldta layer_type.name to ExtendScript layerType string.
    _LAYER_TYPE_NAMES: dict[str, str] = {
        "avlayer": "AVLayer",
        "shape": "Layer",
        "text": "Layer",
        "camera": "CameraLayer",
        "light": "LightLayer",
        "three_d_model": "Layer",
    }

    enabled = ChunkField.bool("_ldta", "enabled")
    """When `True`, the layer is enabled. Overrides `PropertyBase.enabled`
    to read from the ldta chunk. Read / Write."""

    id = ChunkField[int]("_ldta", "layer_id", read_only=True)
    """Unique and persistent identification number used internally to
    identify a Layer between sessions. Read-only."""

    label = ChunkField.enum(Label, "_ldta", "label")
    """The label color. Colors are represented by their number (0 for None,
    or 1 to 16 for one of the preset colors in the Labels preferences).
    Read / Write."""

    locked = ChunkField.bool("_ldta", "locked")
    """When `True`, the layer is locked. This corresponds to the lock toggle
    in the Layer panel. Read / Write."""

    null_layer = ChunkField.bool("_ldta", "null_layer", read_only=True)
    """When `True`, the layer was created as a null object. Read-only."""

    _parent_id = ChunkField[int]("_ldta", "parent_id")
    """The ID of the layer's parent layer. `0` if the layer has no parent."""

    shy = ChunkField.bool("_ldta", "shy")
    """When `True`, the layer is "shy", meaning that it is hidden in the
    Layer panel if the composition's "Hide all shy layers" option is
    toggled on. Read / Write."""

    solo = ChunkField.bool("_ldta", "solo")
    """When `True`, the layer is soloed. Read / Write."""

    start_time = ChunkField[float](
        "_ldta",
        "start_time",
        reverse_instance_field=_reverse_start_time,
    )
    """The start time of the layer, expressed in composition time (seconds).
    Read / Write."""

    stretch = ChunkField[float](
        "_ldta",
        "stretch",
        reverse_instance_field=_reverse_stretch,
    )
    """The layer's time stretch, expressed as a percentage. A value of 100
    means no stretch. Values between 0 and 1 are set to 1, and values
    between -1 and 0 (not including 0) are set to -1. Read / Write."""

    auto_orient = ChunkField.enum(
        AutoOrientType,
        "_ldta",
        "auto_orient_type",
        reverse_instance_field=_reverse_auto_orient,
    )
    """The type of automatic orientation to perform for the layer.
    Read / Write."""

    # Use identity-based equality to avoid comparing all fields recursively,
    # which could produce unexpected results or hit circular references.
    __eq__ = object.__eq__
    __hash__ = object.__hash__

    def __init__(
        self,
        *,
        _ldta: Aep.LdtaBody,
        _cmta: Aep.Utf8Body | None,
        _name_utf8: Aep.Utf8Body,
        containing_comp: CompItem,
        properties: list[Property | PropertyGroup],
    ) -> None:
        self._ldta = _ldta
        self._cmta = _cmta
        self._otln_entry: Aep.OtlnEntry | None = None

        layer_type_name = _ldta.layer_type.name
        match_name = self._LAYER_MATCH_NAMES.get(layer_type_name, "ADBE AV Layer")

        super().__init__(
            _tdsb=None,
            _name_utf8=_name_utf8,
            match_name=match_name,
            auto_name="",
            property_depth=0,
            properties=properties,
        )

        self._containing_comp = containing_comp

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"enabled={self.enabled!r}, "
            f"match_name={self.match_name!r}, "
            f"name={self.name!r})"
        )

    @property  # type: ignore[override]
    def selected(self) -> bool:
        """When `True`, the layer is selected in the timeline. Read / Write."""
        if self._otln_entry is not None:
            return bool(self._otln_entry.selected)
        return bool(self.__dict__.get("_selected", False))

    @selected.setter
    def selected(self, value: bool) -> None:
        if self._otln_entry is not None:
            self._otln_entry.selected = int(value)
            propagate_check(self._otln_entry)
        else:
            self._selected = value

    @property
    def comment(self) -> str:
        """A descriptive comment for the layer. Read / Write."""
        if self._cmta is None:
            return ""
        return strip_null(self._cmta.contents)

    @comment.setter
    def comment(self, value: str) -> None:
        if self._cmta is None:
            container = self._ldta._parent._parent
            chunk = create_chunk(container, "cmta", "Utf8Body", contents=value)
            self._cmta = chunk.body
        else:
            self._cmta.contents = value
            propagate_check(self._cmta)

    @property
    def containing_comp(self) -> CompItem:
        """The composition that contains this layer. Read-only."""
        return self._containing_comp

    @property
    def layer_type(self) -> str:
        """The type of layer. Matches ExtendScript `layerType` values:
        `"AVLayer"`, `"LightLayer"`, `"CameraLayer"`, or `"Layer"`.
        Read-only."""
        return self._LAYER_TYPE_NAMES.get(self._ldta.layer_type.name, "AVLayer")

    @property
    def time(self) -> float:
        """The current time of the layer, expressed in composition time
        (seconds). Read-only."""
        return self._containing_comp.time

    @property
    def frame_time(self) -> int:
        """The current time of the layer, expressed in composition time
        (frames). Read-only."""
        return self._containing_comp.frame_time

    @property
    def _stretch_factor(self) -> float:
        stretch = self.stretch
        return stretch / 100.0 if stretch != 0.0 else 1.0

    @property
    def in_point(self) -> float:
        """The "in" point of the layer, expressed in composition time
        (seconds). Read / Write."""
        return float(self.start_time + self._ldta.in_point * self._stretch_factor)

    @in_point.setter
    def in_point(self, value: float) -> None:
        self._set_raw_in_point(value)

    @property
    def out_point(self) -> float:
        """The "out" point of the layer, expressed in composition time
        (seconds). Read / Write."""
        return float(self.start_time + self._ldta.out_point * self._stretch_factor)

    @out_point.setter
    def out_point(self, value: float) -> None:
        self._set_raw_out_point(value)

    @property
    def frame_in_point(self) -> int:
        """The "in" point of the layer, expressed in composition time
        (frames). Read / Write."""
        return round(self.in_point * self.containing_comp.frame_rate)

    @frame_in_point.setter
    def frame_in_point(self, value: int) -> None:
        self.in_point = value / self.containing_comp.frame_rate

    @property
    def frame_out_point(self) -> int:
        """The "out" point of the layer, expressed in composition time
        (frames). Read / Write."""
        return round(self.out_point * self.containing_comp.frame_rate)

    @frame_out_point.setter
    def frame_out_point(self, value: int) -> None:
        self.out_point = value / self.containing_comp.frame_rate

    @property
    def frame_start_time(self) -> int:
        """The start time of the layer, expressed in composition time
        (frames). Read / Write."""
        return round(self.start_time * self.containing_comp.frame_rate)

    @frame_start_time.setter
    def frame_start_time(self, value: int) -> None:
        self.start_time = value / self.containing_comp.frame_rate

    @property
    def index(self) -> int:
        """The 0-based index position of the layer in its containing comp.

        Warning:
            Unlike ExtendScript (1-based), this uses Python's 0-based
            convention so that `comp.layers[layer.index]` works directly.
        """
        return self.containing_comp.layers.index(self)

    @property
    def has_video(self) -> bool:
        """`True` if the layer has a video switch in the Timeline panel.

        Always `False` for [CameraLayer][] and [LightLayer][] objects.
        """
        return False

    @property
    def adjustment_layer(self) -> bool:
        """`True` if the layer is an adjustment layer.

        Always `False` for [CameraLayer][] and [LightLayer][] objects.
        Overridden in [AVLayer][] to read from the binary chunk.
        """
        return False

    @property
    def environment_layer(self) -> bool:
        """`True` if the layer is an environment layer.

        Always `False` for [CameraLayer][] and [LightLayer][] objects.
        Overridden in [AVLayer][] to read from the binary chunk.
        """
        return False

    @property
    def active(self) -> bool:
        """
        When `True`, the layer is active at the current time.

        Overrides [PropertyBase.active][] to evaluate
        [active_at_time][] at [time][].
        """
        return self.active_at_time(self.time)

    @property
    def marker(self) -> Property | None:
        """The layer's marker property.

        A [Property][py_aep.models.properties.property.Property] with
        `match_name="ADBE Marker"` whose keyframes hold marker values.
        `None` when the layer has no markers.
        """
        try:
            prop = self["ADBE Marker"]
        except KeyError:
            return None
        return cast(Property, prop)

    @property
    def markers(self) -> list[MarkerValue]:
        """A flat list of [MarkerValue][] objects for this layer.

        Shortcut for accessing marker data without navigating the property
        tree. Returns an empty list when the layer has no markers.

        Example:
            ```python
            for marker in layer.markers:
                print(marker.comment)
            ```
        """
        if self.marker is None:
            return []
        return cast(
            List[MarkerValue],  # Cannot use `list` for Py3.7
            [kf.value for kf in self.marker.keyframes],
        )

    @property
    def transform(self) -> PropertyGroup:
        """
        Contains a layer's transform properties.

        This is the Transform `PropertyGroup` (match name
        `ADBE Transform Group`). Individual transform properties (Position,
        Scale, Rotation, etc.) are accessible via
        [properties][PropertyGroup.properties].
        """
        group = self["ADBE Transform Group"]
        assert isinstance(group, PropertyGroup)
        return group

    @property
    def effects(self) -> PropertyGroup | None:
        """
        Contains a layer's effects.

        This is the Effects `PropertyGroup` (match name `ADBE Effect Parade`).
        Each child in [properties][PropertyGroup.properties] is itself a
        [PropertyGroup][] representing one effect. `None` when the layer has no
        effects.
        """
        try:
            group = self["ADBE Effect Parade"]
        except KeyError:
            return None
        if not isinstance(group, PropertyGroup) or not group.properties:
            return None
        return group

    @property
    def masks(self) -> PropertyGroup | None:
        """
        Contains a layer's masks.

        This is the Masks `PropertyGroup` (match name `ADBE Mask Parade`).
        Each child in [properties][PropertyGroup.properties] is itself a
        [PropertyGroup][] representing one mask. `None` when the layer has no
        masks.
        """
        try:
            group = self["ADBE Mask Parade"]
        except KeyError:
            return None
        if not isinstance(group, PropertyGroup) or not group.properties:
            return None
        return group

    @property
    def text(self) -> PropertyGroup | None:
        """Contains a layer's text properties (if any)."""
        try:
            group = self["ADBE Text Properties"]
        except KeyError:
            return None
        if isinstance(group, PropertyGroup):
            return group
        return None

    @property
    def parent(self) -> Layer | None:
        """The parent layer for layer parenting. `None` if no parent."""
        if self._parent_id == 0:
            return None
        return self.containing_comp.layers_by_id.get(self._parent_id)

    @parent.setter
    def parent(self, value: Layer | None) -> None:
        self._parent_id = value.id if value is not None else 0

    def active_at_time(self, time: float) -> bool:
        """Return whether the layer is active at the given time.

        For this method to return `True`, three conditions must be met:

        1. The layer must be `enabled`.
        2. No other layer in the [containing_comp][] may be soloed unless
           this layer is also [solo][].
        3. *time* must fall between [in_point][] (inclusive) and
           [out_point][] (exclusive).

        Args:
            time: The time in seconds.
        """
        if not self.enabled:
            return False

        any_solo = any(layer.solo for layer in self.containing_comp.layers)
        if any_solo and not self.solo:
            return False

        if time < self.in_point or time >= self.out_point:
            return False

        return True

    def _set_raw_in_point(self, value: float) -> None:
        """Write a new in_point (comp time) to the binary chunk."""
        layer_relative = (value - self.start_time) / self._stretch_factor
        for field, v in _reverse_in_point(layer_relative, self._ldta).items():
            setattr(self._ldta, field, v)
        try:
            self._ldta._invalidate_in_point()
        except AttributeError:
            pass
        propagate_check(self._ldta)

    def _set_raw_out_point(self, value: float) -> None:
        """Write a new out_point (comp time) to the binary chunk."""
        layer_relative = (value - self.start_time) / self._stretch_factor
        for field, v in _reverse_out_point(layer_relative, self._ldta).items():
            setattr(self._ldta, field, v)
        try:
            self._ldta._invalidate_out_point()
        except AttributeError:
            pass
        propagate_check(self._ldta)
