from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, cast

from ...binary.chunk import Chunk, DeferredListChunk, ListChunk
from ...binary.composition_chunks import CdtaChunk
from ...binary.layer_chunks import _LDTA_SOURCE_ID_END, _LDTA_SOURCE_ID_OFFSET
from ...binary.misc_chunks import PrinChunk
from ...binary.scalar_chunks import CsctChunk, U4Chunk, Utf8Chunk
from ...binary.utils import (
    ChunkNotFoundError,
    filter_by_list_type,
    find_by_list_type,
    find_by_type,
)
from ..descriptors import ChunkField, ComputedField
from ..layers.av_layer import AVLayer
from ..layers.camera_layer import CameraLayer
from ..layers.light_layer import LightLayer
from ..layers.shape_layer import ShapeLayer
from ..layers.text_layer import TextLayer
from ..layers.three_d_model_layer import ThreeDModelLayer
from ..reverses import (
    denormalize_values,
    reverse_frame_ticks,
    unpack_values,
)
from ..sources.file import FileSource
from ..sources.placeholder import PlaceholderSource
from ..sources.solid import SolidSource
from ..transforms import (
    normalize_values,
    pack_values,
)
from ..validators import (
    validate_number,
    validate_sequence,
)
from .av_item import AVItem
from .footage import FootageItem

if TYPE_CHECKING:
    from typing import Iterator

    from ...binary.item_chunks import IdtaChunk
    from ...binary.layer_chunks import LdtaChunk
    from ...binary.scalar_chunks import CmtaChunk, U1Chunk
    from ..essential_graphics import EssentialGraphicsController
    from ..layers.layer import Layer
    from ..project import Project
    from ..properties.marker import MarkerValue
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


_reverse_display_start_frame = reverse_frame_ticks("display_start_time")
_reverse_frame_duration = reverse_frame_ticks("duration")
_reverse_work_area_start_frame = reverse_frame_ticks("work_area_start")


def _compute_bg_color(body: CdtaChunk) -> list[float]:
    return normalize_values(
        cast(
            "list[int]",
            pack_values(body, "bg_color_r", "bg_color_g", "bg_color_b"),
        )
    )


def _reverse_bg_color(value: list[float], _body: CdtaChunk) -> dict[str, Any]:
    return unpack_values("bg_color_r", "bg_color_g", "bg_color_b")(
        denormalize_values(value), _body
    )


def _compute_resolution_factor(body: CdtaChunk) -> list[int]:
    return cast(
        "list[int]",
        pack_values(body, "resolution_factor_h", "resolution_factor_v"),
    )


def _reverse_resolution_factor(value: list[int], _body: CdtaChunk) -> dict[str, Any]:
    return unpack_values("resolution_factor_h", "resolution_factor_v")(
        value, _body
    )


def _compute_work_area_duration(body: CdtaChunk) -> float:
    if body.work_area_end_dividend == 0xFFFFFFFF:
        return body.duration - body.work_area_start
    return body.work_area_end_dividend / body.work_area_end_divisor - body.work_area_start


def _compute_frame_duration(body: CdtaChunk) -> int:
    return int(body.duration * body.frame_rate)


def _compute_display_start_frame(body: CdtaChunk) -> int:
    return int(body.display_start_time * body.frame_rate)


def _compute_frame_time(body: CdtaChunk) -> int:
    return int(body.time_seconds * body.frame_rate)


def _compute_work_area_start_frame(body: CdtaChunk) -> int:
    return int(body.work_area_start * body.frame_rate)


def _compute_work_area_duration_frame(body: CdtaChunk) -> int:
    return int(_compute_work_area_duration(body) * body.frame_rate)


def _reverse_work_area_duration(value: float, body: CdtaChunk) -> dict[str, int]:
    """Reverse work area duration: sets work_area_end = work_area_start + value."""
    _DIVISOR = 10000
    return {
        "work_area_end_dividend": round((body.work_area_start + value) * _DIVISOR),
        "work_area_end_divisor": _DIVISOR,
    }


def _reverse_work_area_duration_frame(value: int, body: CdtaChunk) -> dict[str, int]:
    """Reverse work area duration in frames: converts to seconds then sets end."""
    _DIVISOR = 10000
    duration_seconds = value / body.frame_rate
    return {
        "work_area_end_dividend": round(
            (body.work_area_start + duration_seconds) * _DIVISOR
        ),
        "work_area_end_divisor": _DIVISOR,
    }


_LAYER_BOUNDARY_TYPES = frozenset(
    {"Layr", "DLay", "SLay", "CLay", "SecL", "CIFO"}
)


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

    bg_color = ComputedField[List[float]](
        "_cdta",
        compute=_compute_bg_color,
        reverse=_reverse_bg_color,
        validate=validate_sequence(length=3, min=0.0, max=1.0),
    )
    """The background color of the composition. The three array values specify
    the red, green, and blue components of the color. Read / Write."""

    draft3d = ChunkField[bool]("_cdta", "draft3d")
    """When `True`, Draft 3D mode is enabled for the composition.
    Read / Write.

    Warning:
        Deprecated in After Effects 2024 in favor of the new Draft 3D mode."""

    frame_blending = ChunkField[bool]("_cdta", "frame_blending")
    """When `True`, frame blending is enabled for this Composition. Corresponds
    to the value of the Frame Blending button in the Composition panel.
    Read / Write."""

    hide_shy_layers = ChunkField[bool]("_cdta", "hide_shy_layers")
    """When `True`, only layers with `shy` set to `False` are shown in the
    Timeline panel. When `False`, all layers are visible, including those
    whose `shy` value is `True`. Corresponds to the value of the Hide All
    Shy Layers button in the Composition panel. Read / Write."""

    motion_blur = ChunkField[bool]("_cdta", "motion_blur")
    """When `True`, motion blur is enabled for the composition. Corresponds
    to the value of the Motion Blur button in the Composition panel.
    Read / Write."""

    preserve_nested_frame_rate = ChunkField[bool]("_cdta", "preserve_nested_frame_rate")
    """When `True`, the frame rate of nested compositions is preserved in
    the current composition. Corresponds to the value of the "Preserve frame
    rate when nested or in render queue" option in the Advanced tab of the
    Composition Settings dialog box. Read / Write."""

    preserve_nested_resolution = ChunkField[bool]("_cdta", "preserve_nested_resolution")
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

    resolution_factor = ComputedField[List[int]](
        "_cdta",
        compute=_compute_resolution_factor,
        reverse=_reverse_resolution_factor,
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
        "_cdta", "frame_rate", validate=validate_number(min=1.0, max=999.0)
    )
    """The frame rate of the item in frames-per-second. Read / Write."""

    duration = ChunkField[float](
        "_cdta", "duration", validate=validate_number(min=0.0, max=10800.0)
    )
    """The duration of the item in seconds. Read / Write."""

    frame_duration = ComputedField[int](
        "_cdta",
        compute=_compute_frame_duration,
        reverse=_reverse_frame_duration,
        validate=validate_number(
            min=1,
            max=lambda self: int(self.duration * self.frame_rate),
            integer=True,
        ),
    )
    """The duration of the item in frames. Read / Write."""

    pixel_aspect = ChunkField[float](
        "_cdta", "pixel_aspect", validate=validate_number(min=0.01, max=100.0)
    )
    """The pixel aspect ratio of the item (1.0 is square). Read / Write."""

    time_scale = ChunkField[float]("_cdta", "time_scale", read_only=True)
    """The time scale, used as a divisor for keyframe time values. Read-only."""

    display_start_time = ChunkField[float](
        "_cdta",
        "display_start_time",
        validate=validate_number(min=-10800.0, max=86339.0),
    )
    """The time set as the beginning of the composition, in seconds. This
    is the equivalent of the Start Timecode or Start Frame setting in the
    Composition Settings dialog box. Read / Write."""

    display_start_frame = ComputedField[int](
        "_cdta",
        compute=_compute_display_start_frame,
        reverse=_reverse_display_start_frame,
        validate=validate_number(
            min=lambda self: int(-10800.0 * self.frame_rate),
            max=lambda self: int(86339.0 * self.frame_rate),
            integer=True,
        ),
    )
    """The frame value of the beginning of the composition. Read / Write."""

    work_area_start = ChunkField[float](
        "_cdta",
        "work_area_start",
        validate=validate_number(
            min=0.0,
            max=lambda self: self.duration - 1 / self.frame_rate,
        ),
    )
    """The work area start time relative to composition start.
    Read / Write."""

    work_area_start_frame = ComputedField[int](
        "_cdta",
        compute=_compute_work_area_start_frame,
        reverse=_reverse_work_area_start_frame,
        validate=validate_number(
            min=0,
            max=lambda self: self.frame_duration - 1,
            integer=True,
        ),
    )
    """The work area start frame relative to composition start.
    Read / Write."""

    work_area_duration = ComputedField[float](
        "_cdta",
        compute=_compute_work_area_duration,
        reverse=_reverse_work_area_duration,
        validate=validate_number(
            min=lambda self: 1 / self.frame_rate,
            max=lambda self: self.duration - self.work_area_start,
        ),
    )
    """The work area duration in seconds. Read / Write."""

    work_area_duration_frame = ComputedField[int](
        "_cdta",
        compute=_compute_work_area_duration_frame,
        reverse=_reverse_work_area_duration_frame,
        validate=validate_number(
            min=1,
            max=lambda self: self.frame_duration - self.work_area_start_frame,
            integer=True,
        ),
    )
    """The work area duration in frames. Read / Write."""

    time = ChunkField[float](
        "_cdta",
        "time_seconds",
        validate=validate_number(
            min=lambda self: self.display_start_time,
            max=lambda self: (
                self.display_start_time + self.duration - 1 / self.frame_rate
            ),
        ),
    )
    """The current time of the item when it is being previewed directly from
    the Project panel. This value is a number of seconds. It is an error to set
    this value for a [FootageItem][] whose `main_source` is still
    (`item.main_source.is_still is True`). Read / Write."""

    frame_time = ComputedField[int](
        "_cdta",
        compute=_compute_frame_time,
        reverse=reverse_frame_ticks("time"),
        validate=validate_number(
            min=lambda self: self.display_start_frame,
            max=lambda self: self.display_start_frame + self.frame_duration - 1,
            integer=True,
        ),
    )
    """The current time of the item when it is being previewed directly from
    the Project panel. This value is a number of frames. Read / Write."""

    drop_frame = ChunkField[bool](
        "_cdrp", "value", transform=bool, reverse=int, default=False
    )
    """When `True`, timecode is displayed in drop-frame format. Only
    applicable when `frameRate` is 29.97 or 59.94. Read / Write."""

    def __init__(
        self,
        *,
        _child_chunks: list[Chunk],
        _cmta: CmtaChunk | None,
        _idta: IdtaChunk,
        _item_list: ListChunk,
        _gide: ListChunk | None,
        _name_utf8: Utf8Chunk,
        project: Project,
        parent_folder: FolderItem,
        effect_param_defs: dict[str, dict[str, dict[str, Any]]],
        proxy_source: FileSource | SolidSource | PlaceholderSource | None,
    ) -> None:
        # Skip AVItem's extra params - they're all descriptor-backed on
        # CompItem and read directly from the cdta chunk body.
        super().__init__(
            _idta=_idta,
            _name_utf8=_name_utf8,
            _cmta=_cmta,
            _item_list=_item_list,
            _gide=_gide,
            project=project,
            parent_folder=parent_folder,
            type_name="Composition",
            proxy_source=proxy_source,
        )

        self._layers: list[Layer] = []
        self._layers_by_id: dict[int, Layer] | None = None
        self._type_cache: dict[str, list[Any]] | None = None
        self.__layer_id_to_index: dict[int, int] | None = None

        self._cdta = cast(
            "CdtaChunk",
            find_by_type(chunks=_child_chunks, chunk_type="cdta"),
        )
        try:
            self._cdrp: U1Chunk | None = cast(
                "U1Chunk",
                find_by_type(chunks=_child_chunks, chunk_type="cdrp"),
            )
        except ChunkNotFoundError:
            self._cdrp = None
        prin_list = find_by_list_type(chunks=_child_chunks, list_type="PRin")
        self._prin = cast(
            "PrinChunk",
            find_by_type(chunks=prin_list.chunks, chunk_type="prin"),
        )

        # Layer deferral: collect layer chunks and source IDs now, parse
        # the actual Layer objects on first access via _ensure_layers_loaded.
        layer_chunks = filter_by_list_type(
            chunks=_child_chunks, list_type="Layr",
        )
        if layer_chunks:
            self._deferred_layers: (
                tuple[
                    list[ListChunk],
                    dict[str, dict[str, dict[str, Any]]],
                ]
                | None
            ) = (layer_chunks, effect_param_defs)
            self._layers_loaded = False
        else:
            self._deferred_layers = None
            self._layers_loaded = True

        # Deferred markers + Essential Graphics parsing.
        self._deferred_child_chunks: list[Chunk] | None = _child_chunks
        self._marker_property: Property | None = None
        self._eg_template_name_utf8: Utf8Chunk | None = None
        self._eg_controllers: list[EssentialGraphicsController] = []

    def __iter__(self) -> Iterator[Layer]:
        """Return an iterator over the composition's layers."""
        return iter(self.layers)

    def _source_ids_for_linking(self) -> set[int]:
        """Return source IDs for `_used_in` linking without forcing layer parse."""
        deferred = self._deferred_layers
        if deferred is not None:
            source_ids: set[int] = set()
            for lc in deferred[0]:
                if isinstance(lc, DeferredListChunk) and lc._parsed_chunks is None:
                    raw = lc._raw_body
                    if len(raw) >= _LDTA_SOURCE_ID_END and raw[:4] == b"ldta":
                        sid = int.from_bytes(
                            raw[_LDTA_SOURCE_ID_OFFSET:_LDTA_SOURCE_ID_END], "big",
                        )
                        if sid != 0:
                            source_ids.add(sid)
                else:
                    try:
                        ldta = cast(
                            "LdtaChunk",
                            find_by_type(chunks=lc.chunks, chunk_type="ldta"),
                        )
                    except ChunkNotFoundError:
                        continue
                    if ldta.source_id != 0:
                        source_ids.add(ldta.source_id)
            return source_ids

        return {
            layer._source_id
            for layer in self._layers
            if isinstance(layer, AVLayer) and layer._source_id != 0
        }

    def _ensure_layers_loaded(self) -> None:
        """Parse deferred `LIST:Layr` chunks on first layer access."""
        if self._layers_loaded:
            return

        deferred = self._deferred_layers
        assert deferred is not None

        # Clear deferred state first to avoid duplicate work if any nested
        # access re-enters this method.
        layer_chunks, deferred_effect_param_defs = deferred
        self._deferred_layers = None

        # Deferred import avoids model<->parser import cycles.
        from ...parsers.layer import parse_layer

        effect_param_defs: dict[str, dict[str, dict[str, Any]]]
        if deferred_effect_param_defs:
            effect_param_defs = deferred_effect_param_defs
        elif self._project is not None:
            effect_param_defs = self._project._effect_param_defs
        else:
            effect_param_defs = {}

        parsed_layers: list[Layer] = []
        for layer_chunk in layer_chunks:
            parsed_layers.append(
                parse_layer(
                    layer_chunk=layer_chunk,
                    composition=self,
                    effect_param_defs=effect_param_defs,
                )
            )

        self._layers = parsed_layers

        self._layers_loaded = True
        self._invalidate_layer_cache()

    def _ensure_comp_parsed(self) -> None:
        """Parse markers and Essential Graphics on first access."""
        if self._deferred_child_chunks is None:
            return

        child_chunks = self._deferred_child_chunks
        self._deferred_child_chunks = None

        # Deferred imports: both parsers import from models.
        from ...parsers.composition import _get_markers  # noqa: PLC0415
        from ...parsers.essential_graphics import (  # noqa: PLC0415
            parse_essential_graphics,
        )

        self._marker_property = _get_markers(
            child_chunks=child_chunks, composition=self,
        )
        eg_result = parse_essential_graphics(child_chunks)
        if eg_result is not None:
            self._eg_template_name_utf8 = eg_result[0]
            self._eg_controllers = list(eg_result[1])

    def _build_type_cache(self) -> dict[str, list[Any]]:

        av: list[AVLayer] = []
        text: list[TextLayer] = []
        shape: list[ShapeLayer] = []
        camera: list[CameraLayer] = []
        light: list[LightLayer] = []
        three_d_model: list[ThreeDModelLayer] = []
        by_id: dict[int, Layer] = {}
        for layer in self.layers:
            by_id[layer.id] = layer
            if isinstance(layer, AVLayer):
                av.append(layer)
                if isinstance(layer, TextLayer):
                    text.append(layer)
                elif isinstance(layer, ShapeLayer):
                    shape.append(layer)
                elif isinstance(layer, ThreeDModelLayer):
                    three_d_model.append(layer)
            elif isinstance(layer, CameraLayer):
                camera.append(layer)
            elif isinstance(layer, LightLayer):
                light.append(layer)
        self._layers_by_id = by_id
        cache: dict[str, list[Any]] = {
            "av": av,
            "text": text,
            "shape": shape,
            "camera": camera,
            "light": light,
            "three_d_model": three_d_model,
        }
        self._type_cache = cache
        return cache

    def _invalidate_layer_cache(self) -> None:
        """Reset layer caches after structural mutations."""
        self._type_cache = None
        self._layers_by_id = None
        self.__layer_id_to_index = None

    def _layer_block_slice(self, layer: Layer) -> tuple[int, int]:
        """Return `(start, end)` indices of a layer's chunk block in
        `_item_list.chunks`.

        The block runs from the layer's `LIST:Layr` to the next boundary
        chunk (another `LIST:Layr`, a view block, or a footer chunk).
        """
        chunks = self._item_list.chunks
        # Identity scan - attrs __eq__ on ListChunk is structural, so two layers
        # with identical content would fool .index() into returning the wrong position.
        start = next(i for i, c in enumerate(chunks) if c is layer._layer_list)
        for end in range(start + 1, len(chunks)):
            c = chunks[end]
            if isinstance(c, ListChunk) and c.list_type in _LAYER_BOUNDARY_TYPES:
                return start, end
        return start, len(chunks)

    def _find_first_layer_position(self) -> int:
        """Find the insertion point for the first layer in the chunk list."""
        for i, chunk in enumerate(self._item_list.chunks):
            if isinstance(chunk, ListChunk) and chunk.list_type in (
                "DLay", "SLay", "CLay", "SecL", "CIFO",
            ):
                return i
        return len(self._item_list.chunks)

    @property
    def layers(self) -> list[Layer]:
        """All the [Layer][] objects for layers in this composition.
        Read-only."""
        self._ensure_layers_loaded()
        return self._layers

    @property
    def layers_by_id(self) -> dict[int, Layer]:
        """Map of layer ID to layer, for O(1) lookup by sibling layers."""
        if self._layers_by_id is None:
            self._layers_by_id = {layer.id: layer for layer in self.layers}
        return self._layers_by_id

    @property
    def _layer_id_to_index(self) -> dict[int, int]:
        """Map of layer ID to 0-based index."""
        if self.__layer_id_to_index is None:
            self.__layer_id_to_index = {
                layer.id: idx for idx, layer in enumerate(self.layers)
            }
        return self.__layer_id_to_index

    @property
    def marker_property(self) -> Property | None:
        """The composition's marker property. Read-only."""
        self._ensure_comp_parsed()
        return self._marker_property

    @property
    def motion_graphics_template_name(self) -> str | None:
        """The name property in the Essential Graphics panel for the
        composition. The name in the Essential Graphics panel is used
        for the file name of an exported Motion Graphics template.
        Read / Write."""
        self._ensure_comp_parsed()
        if self._eg_template_name_utf8 is None:
            return None
        return self._eg_template_name_utf8.value

    @motion_graphics_template_name.setter
    def motion_graphics_template_name(self, value: str) -> None:
        self._ensure_comp_parsed()
        if self._eg_template_name_utf8 is not None:
            self._eg_template_name_utf8.value = value
        else:
            utf8_chunk = Utf8Chunk(chunk_type="Utf8", value=value)
            cps2 = ListChunk(
                chunk_type="LIST",
                list_type="CpS2",
                chunks=[
                    CsctChunk(),
                    utf8_chunk,
                    Utf8Chunk(chunk_type="Utf8", value="en_US"),
                ],
            )
            cif3 = ListChunk(
                chunk_type="LIST",
                list_type="CIF3",
                chunks=[
                    cps2,
                    U4Chunk(chunk_type="CcCt"),
                ],
            )
            self._item_list.chunks.append(cif3)
            self._eg_template_name_utf8 = utf8_chunk

    @property
    def essential_graphics_controllers(self) -> list[EssentialGraphicsController]:
        """The Essential Graphics controllers for this composition.
        Read-only."""
        self._ensure_comp_parsed()
        return self._eg_controllers

    @property
    def motion_graphics_template_controller_count(self) -> int:
        """The number of properties in the Essential Graphics panel
        for the composition. Read-only."""
        return len(self.essential_graphics_controllers)

    @property
    def motion_graphics_template_controller_names(self) -> list[str]:
        """The names of all properties in the Essential Graphics panel.
        Read-only."""
        return [ctrl.name for ctrl in self.essential_graphics_controllers]

    def get_motion_graphics_template_controller_name(self, index: int) -> str:
        """Get the name of a single property in the Essential Graphics
        panel.

        Warning:
            Uses 0-based indexing, unlike the ExtendScript API which is
            1-based.

        Args:
            index: The 0-based index of the EGP property.
        """
        return self.essential_graphics_controllers[index].name

    def set_motion_graphics_controller_name(self, index: int, name: str) -> None:
        """Set the name of a single property in the Essential Graphics
        panel.

        Warning:
            Uses 0-based indexing, unlike the ExtendScript API which is
            1-based.

        Args:
            index: The 0-based index of the EGP property.
            name: The new name for the EGP property.
        """
        self.essential_graphics_controllers[index].name = name

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
            "list[MarkerValue]",
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
        cache = self._type_cache if self._type_cache is not None else self._build_type_cache()
        return cache["av"]

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
        cache = self._type_cache if self._type_cache is not None else self._build_type_cache()
        return cache["text"]

    @property
    def shape_layers(self) -> list[ShapeLayer]:
        """A list of the shape layers in this composition."""
        cache = self._type_cache if self._type_cache is not None else self._build_type_cache()
        return cache["shape"]

    @property
    def camera_layers(self) -> list[CameraLayer]:
        """A list of the camera layers in this composition."""
        cache = self._type_cache if self._type_cache is not None else self._build_type_cache()
        return cache["camera"]

    @property
    def light_layers(self) -> list[LightLayer]:
        """A list of the light layers in this composition."""
        cache = self._type_cache if self._type_cache is not None else self._build_type_cache()
        return cache["light"]

    @property
    def three_d_model_layers(self) -> list[ThreeDModelLayer]:
        """A list of the 3D model layers in this composition."""
        cache = self._type_cache if self._type_cache is not None else self._build_type_cache()
        return cache["three_d_model"]

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

