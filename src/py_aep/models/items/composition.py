from __future__ import annotations

import typing
from typing import Any, List, cast

from ...kaitai.descriptors import ChunkField
from ...kaitai.reverses import (
    denormalize_values,
    reverse_fractional,
    reverse_frame_ticks,
    reverse_ratio,
)
from ...kaitai.transforms import normalize_values
from ...kaitai.utils import create_chunk, propagate_check
from ..layers.av_layer import AVLayer
from ..layers.camera_layer import CameraLayer
from ..layers.light_layer import LightLayer
from ..layers.shape_layer import ShapeLayer
from ..layers.text_layer import TextLayer
from ..layers.three_d_model_layer import ThreeDModelLayer
from ..properties.marker import MarkerValue
from ..sources.file import FileSource
from ..sources.placeholder import PlaceholderSource
from ..sources.solid import SolidSource
from ..validators import (
    validate_number,
    validate_sequence,
)
from .av_item import AVItem
from .footage import FootageItem

if typing.TYPE_CHECKING:
    from ...kaitai import Aep
    from ..essential_graphics import EssentialGraphicsController
    from ..layers.layer import Layer
    from ..project import Project
    from ..properties.property import Property
    from .folder import FolderItem

# The binary prin chunk stores internal plugin match_names (e.g. ADBE Escher)
# but ExtendScript exposes different module names (e.g. ADBE Advanced 3d).
_RENDERER_BINARY_TO_EXTENDSCRIPT: dict[str, str] = {
    "ADBE Escher": "ADBE Advanced 3d",
    "ADBE Calder": "ADBE Calder",
    "ADBE Ernst": "ADBE Ernst",
    "ADBE Picasso": "ADBE Picasso",
}

_RENDERER_EXTENDSCRIPT_TO_BINARY: dict[str, str] = {
    v: k for k, v in _RENDERER_BINARY_TO_EXTENDSCRIPT.items()
}


_reverse_frame_rate = reverse_fractional("frame_rate_integer", "frame_rate_fractional")
_reverse_pixel_aspect = reverse_ratio("pixel_ratio")
_reverse_display_start_time = reverse_ratio("display_start_time")
_reverse_display_start_frame = reverse_frame_ticks("display_start_time")
_reverse_duration = reverse_ratio("duration")
_reverse_frame_duration = reverse_frame_ticks("duration")
_reverse_work_area_start = reverse_ratio("work_area_start")
_reverse_work_area_start_frame = reverse_frame_ticks("work_area_start")


def _reverse_work_area_duration(value: float, body: Any) -> dict[str, int]:
    """Reverse work area duration: sets work_area_end = work_area_start + value."""
    _DIVISOR = 10000
    work_start = body.work_area_start_dividend / body.work_area_start_divisor
    return {
        "work_area_end_dividend": round((work_start + value) * _DIVISOR),
        "work_area_end_divisor": _DIVISOR,
    }


def _reverse_work_area_duration_frame(value: int, body: Any) -> dict[str, int]:
    """Reverse work area duration in frames: converts to seconds then sets end."""
    _DIVISOR = 10000
    work_start = body.work_area_start_dividend / body.work_area_start_divisor
    duration_seconds = value / body.frame_rate
    return {
        "work_area_end_dividend": round((work_start + duration_seconds) * _DIVISOR),
        "work_area_end_divisor": _DIVISOR,
    }


class CompItem(AVItem):
    """
    The `CompItem` object represents a composition, and allows you to
    manipulate and get information about it.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        comp = app.project.compositions[0]
        print(comp.frame_rate)
        for layer in comp:
            ...
        ```

    Info:
        [Item][] is the base class for [AVItem][] object and for [FolderItem][]
        object, which are in turn the base classes for various other item
        types, so [Item][] attributes and methods are available when working with
        all of these item types.

    See: https://ae-scripting.docsforadobe.dev/item/compitem/"""

    bg_color = ChunkField[List[float]](
        "_cdta",
        "bg_color",
        transform=normalize_values,
        reverse_seq_field=denormalize_values,
        validate=validate_sequence(length=3, min=0.0, max=1.0),
    )
    """The background color of the composition. The three array values specify
    the red, green, and blue components of the color. Read / Write."""

    draft3d = ChunkField.bool("_cdta", "draft3d")
    """When `True`, Draft 3D mode is enabled for the composition.
    Read / Write.

    Warning:
        Deprecated in After Effects 2024 in favor of the new Draft 3D mode."""

    frame_blending = ChunkField.bool("_cdta", "frame_blending")
    """When `True`, frame blending is enabled for this Composition. Corresponds
    to the value of the Frame Blending button in the Composition panel.
    Read / Write."""

    hide_shy_layers = ChunkField.bool("_cdta", "hide_shy_layers")
    """When `True`, only layers with `shy` set to `False` are shown in the
    Timeline panel. When `False`, all layers are visible, including those
    whose `shy` value is `True`. Corresponds to the value of the Hide All
    Shy Layers button in the Composition panel. Read / Write."""

    motion_blur = ChunkField.bool("_cdta", "motion_blur")
    """When `True`, motion blur is enabled for the composition. Corresponds
    to the value of the Motion Blur button in the Composition panel.
    Read / Write."""

    preserve_nested_frame_rate = ChunkField.bool("_cdta", "preserve_nested_frame_rate")
    """When `True`, the frame rate of nested compositions is preserved in
    the current composition. Corresponds to the value of the "Preserve frame
    rate when nested or in render queue" option in the Advanced tab of the
    Composition Settings dialog box. Read / Write."""

    preserve_nested_resolution = ChunkField.bool("_cdta", "preserve_nested_resolution")
    """When `True`, the resolution of nested compositions is preserved in
    the current composition. Corresponds to the value of the "Preserve
    Resolution When Nested" option in the Advanced tab of the Composition
    Settings dialog box. Read / Write."""

    width = ChunkField[int](
        "_cdta",
        "width",
        validate=validate_number(min=4, max=30000, integer=True),
    )
    """The width of the item in pixels. Read / Write."""

    height = ChunkField[int](
        "_cdta",
        "height",
        validate=validate_number(min=4, max=30000, integer=True),
    )
    """The height of the item in pixels. Read / Write."""

    shutter_angle = ChunkField[int](
        "_cdta",
        "shutter_angle",
        validate=validate_number(min=0, max=720, integer=True),
    )
    """The shutter angle setting for the composition. This corresponds to the
    Shutter Angle setting in the Advanced tab of the Composition Settings
    dialog box. Read / Write."""

    shutter_phase = ChunkField[int](
        "_cdta",
        "shutter_phase",
        validate=validate_number(min=-360, max=360, integer=True),
    )
    """The shutter phase setting for the composition. This corresponds to the
    Shutter Phase setting in the Advanced tab of the Composition Settings
    dialog box. Read / Write."""

    resolution_factor = ChunkField[List[int]](
        "_cdta",
        "resolution_factor",
        transform=list,
        validate=validate_sequence(length=2, min=1, max=99, integer=True),
    )
    """The x and y downsample resolution factors for rendering the
    composition. The two values in the array specify how many pixels to skip
    when sampling; the first number controls horizontal sampling, the second
    controls vertical sampling. Full resolution is [1, 1], half resolution
    is [2, 2], and quarter resolution is [4, 4]. The default is [1, 1].
    Read / Write."""

    motion_blur_adaptive_sample_limit = ChunkField[int](
        "_cdta",
        "motion_blur_adaptive_sample_limit",
        validate=validate_number(
            min=lambda self: self.motion_blur_samples_per_frame,
            max=256,
            integer=True,
        ),
    )
    """The maximum number of motion blur samples of 2D layer motion. This
    corresponds to the Adaptive Sample Limit setting in the Advanced tab of
    the Composition Settings dialog box. Must be >= `samples_per_frame`.
    Read / Write."""

    motion_blur_samples_per_frame = ChunkField[int](
        "_cdta",
        "motion_blur_samples_per_frame",
        validate=validate_number(min=2, max=64, integer=True),
    )
    """The minimum number of motion blur samples per frame for Classic 3D
    layers, shape layers, and certain effects. This corresponds to the
    Samples Per Frame setting in the Advanced tab of the Composition
    Settings dialog box. Read / Write."""

    frame_rate = ChunkField[float](
        "_cdta",
        "frame_rate",
        reverse_instance_field=_reverse_frame_rate,
        validate=validate_number(min=1.0, max=999.0),
        invalidates=[
            "display_start_frame",
            "frame_duration",
            "frame_time",
            "frame_work_area_end_absolute",
            "frame_work_area_start_absolute",
        ],
    )
    """The frame rate of the item in frames-per-second. Read / Write."""

    duration = ChunkField[float](
        "_cdta",
        "duration",
        reverse_instance_field=_reverse_duration,
        validate=validate_number(min=0.0, max=10800.0),
        invalidates=["frame_duration"],
    )
    """The duration of the item in seconds. Read / Write."""

    frame_duration = ChunkField[int](
        "_cdta",
        "frame_duration",
        transform=int,
        reverse_instance_field=_reverse_frame_duration,
        validate=validate_number(
            min=1,
            max=lambda self: int(self.duration * self.frame_rate),
            integer=True,
        ),
        invalidates=["duration"],
    )
    """The duration of the item in frames. Read / Write."""

    pixel_aspect = ChunkField[float](
        "_cdta",
        "pixel_aspect",
        reverse_instance_field=_reverse_pixel_aspect,
        validate=validate_number(min=0.01, max=100.0),
    )
    """The pixel aspect ratio of the item (1.0 is square). Read / Write."""

    time_scale = ChunkField[float]("_cdta", "time_scale", read_only=True)
    """The time scale, used as a divisor for keyframe time values. Read-only."""

    display_start_time = ChunkField[float](
        "_cdta",
        "display_start_time",
        reverse_instance_field=_reverse_display_start_time,
        validate=validate_number(min=-10800.0, max=86340.0),
        invalidates=[
            "display_start_frame",
            "frame_work_area_duration",
            "frame_work_area_end_absolute",
            "frame_work_area_start_absolute",
            "frame_work_area_start_relative",
            "work_area_duration",
            "work_area_end_absolute",
            "work_area_start_absolute",
            "work_area_start_relative",
        ],
    )
    """The time set as the beginning of the composition, in seconds. This
    is the equivalent of the Start Timecode or Start Frame setting in the
    Composition Settings dialog box. Read / Write."""

    display_start_frame = ChunkField[int](
        "_cdta",
        "display_start_frame",
        transform=int,
        reverse_instance_field=_reverse_display_start_frame,
        validate=validate_number(
            min=lambda self: int(-10800.0 * self.frame_rate),
            max=lambda self: int(86340.0 * self.frame_rate),
            integer=True,
        ),
        invalidates=[
            "display_start_time",
            "frame_work_area_duration",
            "frame_work_area_end_absolute",
            "frame_work_area_start_absolute",
            "frame_work_area_start_relative",
            "work_area_duration",
            "work_area_end_absolute",
            "work_area_start_absolute",
            "work_area_start_relative",
        ],
    )
    """The frame value of the beginning of the composition. Read / Write."""

    work_area_start = ChunkField[float](
        "_cdta",
        "work_area_start_relative",
        reverse_instance_field=_reverse_work_area_start,
        validate=validate_number(
            min=0.0,
            max=lambda self: self.duration - 1 / self.frame_rate,
        ),
        invalidates=[
            "frame_work_area_duration",
            "frame_work_area_start_absolute",
            "frame_work_area_start_relative",
            "work_area_duration",
            "work_area_start_absolute",
        ],
    )
    """The work area start time relative to composition start.
    Read / Write."""

    work_area_start_frame = ChunkField[int](
        "_cdta",
        "frame_work_area_start_relative",
        transform=int,
        reverse_instance_field=_reverse_work_area_start_frame,
        validate=validate_number(
            min=0,
            max=lambda self: self.frame_duration - 1,
            integer=True,
        ),
        invalidates=[
            "frame_work_area_duration",
            "frame_work_area_start_absolute",
            "work_area_duration",
            "work_area_start_absolute",
            "work_area_start_relative",
        ],
    )
    """The work area start frame relative to composition start.
    Read / Write."""

    work_area_duration = ChunkField[float](
        "_cdta",
        "work_area_duration",
        reverse_instance_field=_reverse_work_area_duration,
        validate=validate_number(
            min=lambda self: 1 / self.frame_rate,
            max=lambda self: self.duration - self.work_area_start,
        ),
        invalidates=[
            "frame_work_area_duration",
            "frame_work_area_end_absolute",
            "frame_work_area_start_relative",
            "work_area_end_absolute",
            "work_area_start_relative",
        ],
    )
    """The work area duration in seconds. Read / Write."""

    work_area_duration_frame = ChunkField[int](
        "_cdta",
        "frame_work_area_duration",
        transform=int,
        reverse_instance_field=_reverse_work_area_duration_frame,
        validate=validate_number(
            min=1,
            max=lambda self: self.frame_duration - self.work_area_start_frame,
            integer=True,
        ),
        invalidates=[
            "frame_work_area_end_absolute",
            "frame_work_area_start_relative",
            "work_area_duration",
            "work_area_end_absolute",
            "work_area_start_relative",
        ],
    )
    """The work area duration in frames. Read / Write."""

    time: float = ChunkField[float](  # type: ignore[assignment]
        "_cdta",
        "time",
        reverse_instance_field=reverse_ratio("time"),
        validate=validate_number(
            min=lambda self: self.display_start_time,
            max=lambda self: (
                self.display_start_time + self.duration - 1 / self.frame_rate
            ),
        ),
        invalidates=["time", "frame_time"],
    )
    """The current time of the item when it is being previewed directly from
    the Project panel. This value is a number of seconds. It is an error to set
    this value for a [FootageItem][] whose `main_source` is still
    (`item.main_source.is_still is True`). Read / Write."""

    frame_time: int = ChunkField[int](  # type: ignore[assignment]
        "_cdta",
        "frame_time",
        transform=int,
        reverse_instance_field=reverse_frame_ticks("time"),
        validate=validate_number(
            min=lambda self: self.display_start_frame,
            max=lambda self: self.display_start_frame + self.frame_duration - 1,
            integer=True,
        ),
        invalidates=["time", "frame_time"],
    )
    """The current time of the item when it is being previewed directly from
    the Project panel. This value is a number of frames. Read / Write."""

    drop_frame = ChunkField.bool("_cdrp", "drop_frame", default=False)
    """When `True`, timecode is displayed in drop-frame format. Only
    applicable when `frameRate` is 29.97 or 59.94. Read / Write."""

    def __init__(
        self,
        *,
        _cdrp: Aep.CdrpBody | None,
        _cdta: Aep.CdtaBody,
        _cmta: Aep.Utf8Body | None,
        _idta: Aep.IdtaBody | None,
        _item_list: Aep.ListBody | None = None,
        _name_utf8: Aep.Utf8Body,
        _prin: Aep.PrinBody,
        project: Project,
        parent_folder: FolderItem | None,
        marker_property: Property | None = None,
    ) -> None:
        self._cdta = _cdta
        self._cdrp = _cdrp
        self._prin = _prin

        # Skip AVItem's extra params - they're all descriptor-backed on
        # CompItem and read directly from the cdta chunk body.
        super().__init__(
            _idta=_idta,
            _name_utf8=_name_utf8,
            _cmta=_cmta,
            _item_list=_item_list,
            project=project,
            parent_folder=parent_folder,
            type_name="Composition",
        )

        self._layers: list[Layer] = []
        self._layers_by_id: dict[int, Layer] | None = None
        self._layer_id_to_index: dict[int, int] = {}
        self._marker_property = marker_property
        self._eg_template_name_utf8: Aep.Utf8Body | None = None
        self._eg_controllers: list[EssentialGraphicsController] = []

    def __iter__(self) -> typing.Iterator[Layer]:
        """Return an iterator over the composition's layers."""
        return iter(self.layers)

    @property
    def layers(self) -> list[Layer]:
        """All the [Layer][] objects for layers in this composition.
        Read-only."""
        return self._layers

    @property
    def layers_by_id(self) -> dict[int, Layer]:
        """Map of layer ID to layer, for O(1) lookup by sibling layers."""
        if self._layers_by_id is None:
            self._layers_by_id = {layer.id: layer for layer in self._layers}
        return self._layers_by_id

    @property
    def marker_property(self) -> Property | None:
        """The composition's marker property. Read-only."""
        return self._marker_property

    @property
    def motion_graphics_template_name(self) -> str | None:
        """The name property in the Essential Graphics panel for the
        composition. The name in the Essential Graphics panel is used
        for the file name of an exported Motion Graphics template.
        Read / Write."""
        if self._eg_template_name_utf8 is None:
            return None
        return self._eg_template_name_utf8.contents  # type: ignore[no-any-return]

    @motion_graphics_template_name.setter
    def motion_graphics_template_name(self, value: str) -> None:
        if self._eg_template_name_utf8 is not None:
            self._eg_template_name_utf8.contents = value
            propagate_check(self._eg_template_name_utf8)
        elif self._item_list is not None:
            cif3 = create_chunk(
                self._item_list,
                "LIST",
                "ListBody",
                list_type="CIF3",
                chunks=[],
            )
            cps2 = create_chunk(
                cif3.body,
                "LIST",
                "ListBody",
                list_type="CpS2",
                chunks=[],
            )
            create_chunk(cps2.body, "CsCt", "U4Body", value=0x01000000)
            utf8_chunk = create_chunk(cps2.body, "Utf8", "Utf8Body", contents=value)
            create_chunk(cps2.body, "Utf8", "Utf8Body", contents="en_US")
            create_chunk(cif3.body, "CcCt", "U4Body", value=0)
            self._eg_template_name_utf8 = utf8_chunk.body

    @property
    def motion_graphics_template_controller_count(self) -> int:
        """The number of properties in the Essential Graphics panel
        for the composition. Read-only."""
        return len(self._eg_controllers)

    @property
    def motion_graphics_template_controller_names(self) -> list[str]:
        """The names of all properties in the Essential Graphics panel.
        Read-only."""
        return [ctrl.name for ctrl in self._eg_controllers]

    def get_motion_graphics_template_controller_name(self, index: int) -> str:
        """Get the name of a single property in the Essential Graphics
        panel.

        Args:
            index: The 1-based index of the EGP property.
        """
        return self._eg_controllers[index - 1].name  # type: ignore[no-any-return]

    def set_motion_graphics_controller_name(self, index: int, name: str) -> None:
        """Set the name of a single property in the Essential Graphics
        panel.

        Args:
            index: The 1-based index of the EGP property.
            name: The new name for the EGP property.
        """
        self._eg_controllers[index - 1].name = name

    @property
    def renderers(self) -> list[str]:
        """The available rendering plug-in module names. Read-only."""
        return list(_RENDERER_EXTENDSCRIPT_TO_BINARY)

    @property
    def renderer(self) -> str:
        """The current rendering plug-in module to be used to render this
        composition, as set in the Advanced tab of the Composition Settings
        dialog box. Allowed values are the members of `renderers`.
        Read / Write."""
        binary_name = str(self._prin.match_name)
        return _RENDERER_BINARY_TO_EXTENDSCRIPT.get(binary_name, binary_name)

    @renderer.setter
    def renderer(self, value: str) -> None:
        if value not in _RENDERER_EXTENDSCRIPT_TO_BINARY:
            valid = ", ".join(_RENDERER_EXTENDSCRIPT_TO_BINARY)
            raise ValueError(f"Invalid renderer {value!r}. Valid values: {valid}")
        self._prin.match_name = _RENDERER_EXTENDSCRIPT_TO_BINARY[value]
        propagate_check(self._prin)

    @property
    def has_audio(self) -> bool:
        """When `True`, the composition has an audio component.

        A composition has audio when at least one of its layers has a
        source with audio.
        Read-only.
        """
        return any(layer.has_audio for layer in self.av_layers)

    @property
    def markers(self) -> list[MarkerValue]:
        """A flat list of [MarkerValue][] objects for this composition.

        Shortcut for accessing marker data without navigating the property
        tree.  Returns an empty list when the composition has no markers.

        Example:
            ```python
            for marker in comp.markers:
                print(marker.comment)
            ```
        """
        if self.marker_property is None:
            return []
        return cast(
            List[MarkerValue],  # Cannot use `list` for Py3.7`
            [kf.value for kf in self.marker_property.keyframes],
        )

    @property
    def num_layers(self) -> int:
        """The number of layers in the composition."""
        return len(self.layers)

    @property
    def active_camera(self) -> CameraLayer | None:
        """The front-most enabled camera layer, or `None`.

        Returns the first [CameraLayer][] that is active at the current
        composition time. The value is `None` when the composition
        contains no active camera layers.
        """
        for layer in self.camera_layers:
            if layer.active:
                return layer
        return None

    def layer(
        self,
        name: str | None = None,
        index: int | None = None,
        other_layer: Layer | None = None,
        rel_index: int | None = None,
    ) -> Layer:
        """
        Get a Layer object by name, index, or relative to another layer.

        Args:
            name: The name of the layer to return.
            index: The index position of the layer to return.
            other_layer: A Layer object to use as a reference for the relative
                index position of the layer to return.
            rel_index: The index position of the layer relative to the
                other_layer to return.
        """
        if name:
            for layer in self.layers:
                if layer.name == name:
                    return layer
            raise ValueError(f"Layer with name '{name}' not found")
        elif index is not None:
            return self.layers[index]
        elif other_layer and rel_index:
            return self.layers[self.layers.index(other_layer) + rel_index]
        raise ValueError(
            "Must specify one of name, index, or other_layer and rel_index"
        )

    @property
    def av_layers(self) -> list[AVLayer]:
        """A list of all [AVLayer][] objects in this composition."""
        return [layer for layer in self.layers if isinstance(layer, AVLayer)]

    @property
    def composition_layers(self) -> list[AVLayer]:
        """A list of the composition layers whose source are compositions."""
        return [layer for layer in self.av_layers if isinstance(layer.source, CompItem)]

    @property
    def footage_layers(self) -> list[AVLayer]:
        """A list of the composition layers whose source are footages."""
        return [
            layer for layer in self.av_layers if isinstance(layer.source, FootageItem)
        ]

    @property
    def file_layers(self) -> list[AVLayer]:
        """A list of the layers whose source are file footages."""
        return [
            layer
            for layer in self.footage_layers
            if isinstance(layer.source, FootageItem)
            and isinstance(layer.source.main_source, FileSource)
        ]

    @property
    def solid_layers(self) -> list[AVLayer]:
        """A list of the layers whose source are solids."""
        return [
            layer
            for layer in self.footage_layers
            if isinstance(layer.source, FootageItem)
            and isinstance(layer.source.main_source, SolidSource)
        ]

    @property
    def placeholder_layers(self) -> list[AVLayer]:
        """A list of the layers whose source are placeholders."""
        return [
            layer
            for layer in self.footage_layers
            if isinstance(layer.source, FootageItem)
            and isinstance(
                layer.source.main_source,
                PlaceholderSource,
            )
        ]

    @property
    def text_layers(self) -> list[TextLayer]:
        """A list of the text layers in this composition."""
        return [layer for layer in self.layers if isinstance(layer, TextLayer)]

    @property
    def shape_layers(self) -> list[ShapeLayer]:
        """A list of the shape layers in this composition."""
        return [layer for layer in self.layers if isinstance(layer, ShapeLayer)]

    @property
    def camera_layers(self) -> list[CameraLayer]:
        """A list of the camera layers in this composition."""
        return [layer for layer in self.layers if isinstance(layer, CameraLayer)]

    @property
    def light_layers(self) -> list[LightLayer]:
        """A list of the light layers in this composition."""
        return [layer for layer in self.layers if isinstance(layer, LightLayer)]

    @property
    def three_d_model_layers(self) -> list[ThreeDModelLayer]:
        """A list of the 3D model layers in this composition."""
        return [layer for layer in self.layers if isinstance(layer, ThreeDModelLayer)]

    @property
    def null_layers(self) -> list[Layer]:
        """A list of the null layers in this composition."""
        return [layer for layer in self.layers if layer.null_layer]

    @property
    def adjustment_layers(self) -> list[AVLayer]:
        """A list of the adjustment layers in this composition."""
        return [layer for layer in self.av_layers if layer.adjustment_layer]

    @property
    def three_d_layers(self) -> list[AVLayer]:
        """A list of the 3D layers in this composition."""
        return [layer for layer in self.av_layers if layer.three_d_layer]

    @property
    def guide_layers(self) -> list[AVLayer]:
        """A list of the guide layers in this composition."""
        return [layer for layer in self.av_layers if layer.guide_layer]

    @property
    def solo_layers(self) -> list[Layer]:
        """A list of the soloed layers in this composition."""
        return [layer for layer in self.layers if layer.solo]

    @property
    def selected_layers(self) -> list[Layer]:
        """The layers that are selected in the composition. Read-only."""
        return [layer for layer in self.layers if layer.selected]

    @property
    def selected_properties(self) -> list[Layer]:
        """All selected layers in this composition.

        Warning:
            This is not the same as ExtendScript's `selectedProperties`,
            which returns selected properties.
        Read-only."""
        return [layer for layer in self.layers if layer.selected]
