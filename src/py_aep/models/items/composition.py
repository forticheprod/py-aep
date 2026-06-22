from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, cast

from ...ae_version import requires_version
from ...binary.chunk import Chunk, DeferredListChunk, ListChunk
from ...binary.comp_skeleton import (
    build_cps2,
    build_item_view_chunks,
    build_layer_view_block,
    build_new_comp_item,
)
from ...binary.composition_chunks import CdtaChunk
from ...binary.item_chunks import IdtaChunk
from ...binary.layer_chunks import (
    _LDTA_SOURCE_ID_END,
    _LDTA_SOURCE_ID_OFFSET,
    LdtaChunk,
)
from ...binary.misc_chunks import PguiChunk, PrinChunk
from ...binary.mutations import build_ovg2, build_source_alternate_extras
from ...binary.property_chunks import (
    TDSN_SENTINEL,
    CdatChunk,
    Tdb4Chunk,
    TdmnChunk,
    TdsbChunk,
    TdsnChunk,
)
from ...binary.scalar_chunks import F8Chunk, U1Chunk, U4Chunk, Utf8Chunk
from ...binary.utils import (
    ChunkNotFoundError,
    block_slice,
    filter_by_list_type,
    find_by_list_type,
    find_by_type,
    index_by_identity,
)
from ...enums import LineOrientation
from ...parsers.essential_graphics import parse_essential_graphics
from ...synthesis.specs import _CAMERA_LIGHT_TRANSFORM_SKIP, _OMITTED_EMPTY_GROUPS
from ..descriptors import ChunkField
from ..layers.av_layer import AVLayer
from ..layers.camera_layer import CameraLayer
from ..layers.light_layer import LightLayer
from ..layers.shape_layer import ShapeLayer
from ..layers.text_layer import TextLayer
from ..layers.three_d_model_layer import ThreeDModelLayer
from ..naming import auto_name
from ..properties.property import Property
from ..properties.property_group import PropertyGroup
from ..sources.file import FileSource
from ..sources.placeholder import PlaceholderSource
from ..sources.solid import SolidSource
from ..text.text_document import TextDocument
from ..validators import (
    _validate_number,
    validate_duration,
    validate_footage_dimension,
    validate_frame_rate,
    validate_name,
    validate_one_of,
    validate_pixel_aspect,
    validate_rgb_color,
    validate_sequence,
    validate_string,
    validate_vector2,
)
from .av_item import AVItem
from .footage import FootageItem

if TYPE_CHECKING:
    from typing import Iterator

    from ...binary.item_chunks import CmtaChunk
    from ..essential_graphics import EssentialGraphicsController
    from ..layers.layer import Layer
    from ..project import Project
    from ..properties.marker import MarkerValue
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


_LAYER_BOUNDARY_TYPES = frozenset({"Layr", "DLay", "SLay", "CLay", "SecL", "CIFO"})


_validate_renderer = validate_one_of(list(_RENDERER_EXTENDSCRIPT_TO_BINARY.keys()))


def _materialize_layer(layer: Layer) -> None:
    """Materialize properties for a newly created layer.

    Walks the full property tree and:
    1. Materializes all PropertyGroup shells (not children), except the
       empty groups AE itself omits (trackers / masks / effects / shape
       contents).
    2. Materializes only Property items whose tdb4 has a non-zero
       time-base field, matching the property set AE writes for a new
       layer. Camera and light layers use a fixed two-node transform
       set instead. Other properties stay synthetic.
    3. Inserts the loose skeleton chunks AE writes around specific
       groups (`OvG2` for Layer Overrides, `blsv`/`blsi` for the
       Source Alternate entry).

    Group end markers are already present in each tdgp (added during
    synthesis) and get flipped to non-synthetic by _ensure_materialized().
    """
    cam_light = layer.match_name in ("ADBE Camera Layer", "ADBE Light Layer")

    def _materialize_prop(prop: Property, in_transform: bool) -> None:
        if cam_light and in_transform:
            if prop.match_name not in _CAMERA_LIGHT_TRANSFORM_SKIP:
                prop._ensure_materialized()
        elif prop._tdb4.has_time_base:
            prop._ensure_materialized()

    def _materialize_tree(group: PropertyGroup) -> None:
        group._ensure_materialized()
        in_transform = group.match_name == "ADBE Transform Group"
        for child in group.properties:
            if isinstance(child, PropertyGroup):
                if child.match_name in _OMITTED_EMPTY_GROUPS and not child.properties:
                    continue
                _materialize_tree(child)
            elif isinstance(child, Property):
                _materialize_prop(child, in_transform)

    for top in layer.properties:
        if isinstance(top, PropertyGroup):
            if top.match_name in _OMITTED_EMPTY_GROUPS and not top.properties:
                continue
            _materialize_tree(top)
        elif isinstance(top, Property):
            _materialize_prop(top, False)

    _insert_layer_skeleton_extras(layer)


def _insert_layer_skeleton_extras(layer: Layer) -> None:
    """Insert the loose chunks AE writes inside a new layer's tdgp:
    `LIST:OvG2(CprC)` after the Layer Overrides tdmn and `blsv`/`blsi`
    after the Layer Source Alternate tdmn."""
    root = layer._tdgp
    if root is None:
        return

    def has_following(chunks: list[Chunk], i: int, kind: str) -> bool:
        nxt = chunks[i + 1] if i + 1 < len(chunks) else None
        return getattr(nxt, "list_type", getattr(nxt, "chunk_type", None)) == kind

    chunks = root.chunks
    for i, ch in enumerate(chunks):
        if (
            isinstance(ch, TdmnChunk)
            and ch.value == "ADBE Layer Overrides"
            and not has_following(chunks, i, "OvG2")
        ):
            chunks.insert(i + 1, build_ovg2())
            break
    for i, ch in enumerate(chunks):
        if (
            isinstance(ch, TdmnChunk)
            and ch.value == "ADBE Source Options Group"
            and i + 1 < len(chunks)
            and isinstance(chunks[i + 1], ListChunk)
            and cast("ListChunk", chunks[i + 1]).list_type == "tdgp"
        ):
            inner = cast("ListChunk", chunks[i + 1]).chunks
            for j, c in enumerate(inner):
                if (
                    isinstance(c, TdmnChunk)
                    and c.value == "ADBE Layer Source Alternate"
                    and not has_following(inner, j, "blsv")
                ):
                    inner[j + 1 : j + 1] = build_source_alternate_extras()
                    break
            break


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

    _auto_name: str = "Comp"

    bg_color = ChunkField[List[float]](
        "_cdta",
        "bg_color",
        validate=validate_rgb_color,
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

    width = ChunkField[int]("_cdta", "width", validate=validate_footage_dimension)
    """The width of the item in pixels. Read / Write."""

    height = ChunkField[int]("_cdta", "height", validate=validate_footage_dimension)
    """The height of the item in pixels. Read / Write."""

    shutter_angle = ChunkField[int](
        "_cdta",
        "shutter_angle",
        validate=_validate_number(min=0, max=720, integer=True),
    )
    """The shutter angle setting for the composition. This corresponds to the
    Shutter Angle setting in the Advanced tab of the Composition Settings
    dialog box. Read / Write."""

    shutter_phase = ChunkField[int](
        "_cdta",
        "shutter_phase",
        validate=_validate_number(min=-360, max=360, integer=True),
    )
    """The shutter phase setting for the composition. This corresponds to the
    Shutter Phase setting in the Advanced tab of the Composition Settings
    dialog box. Read / Write."""

    resolution_factor = ChunkField[List[int]](
        "_cdta",
        "resolution_factor",
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
        validate=_validate_number(
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
        validate=_validate_number(min=2, max=64, integer=True),
    )
    """The minimum number of motion blur samples per frame for Classic 3D
    layers, shape layers, and certain effects. This corresponds to the
    Samples Per Frame setting in the Advanced tab of the Composition
    Settings dialog box. Read / Write."""

    frame_rate = ChunkField[float]("_cdta", "frame_rate", validate=validate_frame_rate)
    """The frame rate of the item in frames-per-second. Read / Write."""

    duration = ChunkField[float]("_cdta", "duration", validate=validate_duration)
    """The duration of the item in seconds. Read / Write."""

    frame_duration = ChunkField[int](
        "_cdta",
        "frame_duration",
        validate=_validate_number(
            min=1,
            max=lambda self: int(self.duration * self.frame_rate),
            integer=True,
        ),
    )
    """The duration of the item in frames. Read / Write."""

    pixel_aspect = ChunkField[float](
        "_cdta", "pixel_aspect", validate=validate_pixel_aspect
    )
    """The pixel aspect ratio of the item (1.0 is square). Read / Write."""

    time_scale = ChunkField[float]("_cdta", "time_scale", read_only=True)
    """The time scale, used as a divisor for keyframe time values. Read-only."""

    display_start_time = ChunkField[float](
        "_cdta",
        "display_start_time",
        validate=_validate_number(min=-10800.0, max=86339.0),
    )
    """The time set as the beginning of the composition, in seconds. This
    is the equivalent of the Start Timecode or Start Frame setting in the
    Composition Settings dialog box. Read / Write."""

    display_start_frame = ChunkField[int](
        "_cdta",
        "display_start_frame",
        validate=_validate_number(
            min=lambda self: int(-10800.0 * self.frame_rate),
            max=lambda self: int(86339.0 * self.frame_rate),
            integer=True,
        ),
    )
    """The frame value of the beginning of the composition. Read / Write."""

    work_area_start = ChunkField[float](
        "_cdta",
        "work_area_start",
        validate=_validate_number(
            min=0.0,
            max=lambda self: self.duration - 1 / self.frame_rate,
        ),
    )
    """The work area start time relative to composition start.
    Read / Write."""

    work_area_start_frame = ChunkField[int](
        "_cdta",
        "work_area_start_frame",
        validate=_validate_number(
            min=0,
            max=lambda self: self.frame_duration - 1,
            integer=True,
        ),
    )
    """The work area start frame relative to composition start.
    Read / Write."""

    work_area_duration = ChunkField[float](
        "_cdta",
        "work_area_duration",
        validate=_validate_number(
            min=lambda self: 1 / self.frame_rate,
            max=lambda self: self.duration - self.work_area_start,
        ),
    )
    """The work area duration in seconds. Read / Write."""

    work_area_duration_frame = ChunkField[int](
        "_cdta",
        "work_area_duration_frame",
        validate=_validate_number(
            min=1,
            max=lambda self: self.frame_duration - self.work_area_start_frame,
            integer=True,
        ),
    )
    """The work area duration in frames. Read / Write."""

    time = ChunkField[float](
        "_cdta",
        "time_seconds",
        validate=_validate_number(
            min=lambda self: self.display_start_time,
            max=lambda self: (
                self.display_start_time + self.duration - 1 / self.frame_rate
            ),
        ),
    )
    """The current time of the item when it is being previewed directly from
    the Project panel. This value is a number of seconds. It is an error to set
    this value for a [FootageItem][] whose `main_source` is still. Read / Write."""

    frame_time = ChunkField[int](
        "_cdta",
        "frame_time",
        validate=_validate_number(
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

    @classmethod
    def _new(
        cls,
        name: str,
        width: int,
        height: int,
        pixel_aspect: float,
        duration: float,
        frame_rate: float,
        *,
        project: Project,
        parent_folder: FolderItem,
    ) -> CompItem:
        """Create a new empty composition.

        Args:
            name: The name of the new composition.
            width: The width in pixels.
            height: The height in pixels.
            pixel_aspect: The pixel aspect ratio (1.0 for square pixels).
            duration: The duration in seconds.
            frame_rate: The frame rate in frames per second.
            project: The project that owns this composition.
            parent_folder: The folder that will contain this composition.
        """
        validate_string(name)
        validate_footage_dimension(width)
        validate_footage_dimension(height)
        validate_pixel_aspect(pixel_aspect)
        validate_duration(duration)
        validate_frame_rate(frame_rate)

        new_id = project._allocate_item_id()

        # AE hard-crashes opening a comp item without the full view-state
        # skeleton (~180 chunks of viewer pseudo-layers and panel state),
        # so the whole item is built by the typed skeleton builder.
        item_list, idta, name_utf8, gide = build_new_comp_item(
            item_id=new_id,
            name=name,
            width=width,
            height=height,
            pixel_aspect=pixel_aspect,
            duration=duration,
            frame_rate=frame_rate,
            allocate_layer_id=project._allocate_layer_id,
        )

        # View data chunks that AE expects after every comp's LIST:Item
        fee = ListChunk(
            list_type="FEE ",
            chunks=[F8Chunk(chunk_type="ppSn")],
        )
        view_data: list[Chunk] = [fee, *build_item_view_chunks()]

        comp = cls(
            _child_chunks=item_list.chunks,
            _cmta=None,
            _idta=idta,
            _item_list=item_list,
            _gide=gide,
            _pin_chunks=[],
            _name_utf8=name_utf8,
            project=project,
            parent_folder=parent_folder,
            effect_param_defs=project._effect_param_defs,
            proxy_source=None,
        )
        comp._view_data = view_data
        return comp

    def __init__(
        self,
        *,
        _child_chunks: list[Chunk],
        _cmta: CmtaChunk | None,
        _idta: IdtaChunk,
        _item_list: ListChunk,
        _gide: ListChunk | None,
        _pin_chunks: list[ListChunk],
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
            _pin_chunks=_pin_chunks,
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
            chunks=_child_chunks,
            list_type="Layr",
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
        self._view_data: list[Chunk] = []

    def __iter__(self) -> Iterator[Layer]:
        """Return an iterator over the composition's layers."""
        return iter(self.layers)

    def remove(self) -> None:
        """Remove this composition, including any render-queue items targeting it."""
        rq = self._project.render_queue
        assert rq is not None
        comp_id = self.id
        for rqi in list(rq.items):
            if rqi.comp is self:
                # Full chunk-level removal keeps rs_ldat/Rout/LItm bookkeeping
                # in sync; a model-list drop alone would orphan its chunks.
                rqi.remove()
                continue
            for om in rqi.output_modules:
                if om._om_ldat.post_render_target_comp_id == comp_id:
                    om._om_ldat.post_render_target_comp_id = 0
        super().remove()

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
                            raw[_LDTA_SOURCE_ID_OFFSET:_LDTA_SOURCE_ID_END],
                            "big",
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

        from ...parsers.composition import _get_markers  # noqa: PLC0415

        self._marker_property = _get_markers(
            child_chunks=child_chunks,
            composition=self,
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
        return block_slice(
            self._item_list.chunks,
            layer._layer_list,
            _LAYER_BOUNDARY_TYPES,
        )

    def _find_first_layer_position(self) -> int:
        """Find the insertion point for the first layer in the chunk list."""
        for i, chunk in enumerate(self._item_list.chunks):
            if isinstance(chunk, ListChunk) and chunk.list_type in (
                "DLay",
                "SLay",
                "CLay",
                "SecL",
                "CIFO",
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
    @requires_version(15)
    def motion_graphics_template_name(self, value: str) -> None:
        validate_name(value)
        self._ensure_comp_parsed()
        if self._eg_template_name_utf8 is not None:
            self._eg_template_name_utf8.value = value
        else:
            cps2, utf8_chunk = build_cps2(value)
            cif3 = ListChunk(
                list_type="CIF3",
                chunks=[
                    cps2,
                    U4Chunk(chunk_type="CcCt"),
                ],
            )
            self._item_list.chunks.append(cif3)
            self._eg_template_name_utf8 = utf8_chunk

    @property
    def motion_graphics_controllers(self) -> list[EssentialGraphicsController]:
        """The Essential Graphics controllers for this composition.
        Read-only."""
        self._ensure_comp_parsed()
        return self._eg_controllers

    @property
    def motion_graphics_template_controller_count(self) -> int:
        """The number of properties in the Essential Graphics panel
        for the composition. Read-only."""
        return len(self.motion_graphics_controllers)

    @property
    def motion_graphics_template_controller_names(self) -> list[str]:
        """The names of all properties in the Essential Graphics panel.
        Read-only."""
        return [ctrl.name for ctrl in self.motion_graphics_controllers]

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
        _validate_renderer(value)
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
        cache = (
            self._type_cache
            if self._type_cache is not None
            else self._build_type_cache()
        )
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
        cache = (
            self._type_cache
            if self._type_cache is not None
            else self._build_type_cache()
        )
        return cache["text"]

    @property
    def shape_layers(self) -> list[ShapeLayer]:
        """A list of the shape layers in this composition."""
        cache = (
            self._type_cache
            if self._type_cache is not None
            else self._build_type_cache()
        )
        return cache["shape"]

    @property
    def camera_layers(self) -> list[CameraLayer]:
        """A list of the camera layers in this composition."""
        cache = (
            self._type_cache
            if self._type_cache is not None
            else self._build_type_cache()
        )
        return cache["camera"]

    @property
    def light_layers(self) -> list[LightLayer]:
        """A list of the light layers in this composition."""
        cache = (
            self._type_cache
            if self._type_cache is not None
            else self._build_type_cache()
        )
        return cache["light"]

    @property
    def three_d_model_layers(self) -> list[ThreeDModelLayer]:
        """A list of the 3D model layers in this composition."""
        cache = (
            self._type_cache
            if self._type_cache is not None
            else self._build_type_cache()
        )
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

    # -- Layer creation --------------------------------------------------------

    def _insert_layer(self, layer: Layer) -> None:
        """Insert a fully-constructed layer at the top of the layer stack.

        Handles view block creation, chunk insertion, materialization,
        and layer list bookkeeping.
        """
        view_block = build_layer_view_block()

        if self.layers:
            try:
                chunk_idx = index_by_identity(
                    self._item_list.chunks, self.layers[0]._layer_list
                )
            except ValueError:
                chunk_idx = self._find_first_layer_position()
        else:
            chunk_idx = self._find_first_layer_position()
        self._item_list.chunks[chunk_idx:chunk_idx] = [layer._layer_list, *view_block]

        _materialize_layer(layer)
        self._layers.insert(0, layer)
        self._invalidate_layer_cache()

    def add_null(self, duration: float | None = None) -> AVLayer:
        """Create a new null layer at the top of the layer stack.

        A null layer has no visual content and is commonly used as a parent
        for other layers. Its source is a small transparent solid created
        automatically.

        Args:
            duration: Layer duration in seconds. Defaults to the composition
                duration.

        Returns:
            The newly created [AVLayer][].
        """
        if duration is not None:
            validate_duration(duration)

        existing = {lyr.name for lyr in self.layers}
        name = auto_name("Null", existing)

        solid_source = SolidSource._new(name=name)
        solids_folder = self._project._solids_folder
        footage = FootageItem._new(
            source=solid_source,
            project=self._project,
            parent_folder=solids_folder,
        )
        solids_folder._children_container.append(footage._item_list)
        solids_folder._children_container.extend(footage._view_data)
        self._project.items[footage.id] = footage
        solids_folder.items.append(footage)

        # AE leaves the layer name empty for source-named layers (the
        # name resolves from the footage item).
        layer = AVLayer._new(
            name="",
            layer_id=self._project._allocate_layer_id(),
            source_id=footage.id,
            duration=duration if duration is not None else self.duration,
            containing_comp=self,
            null_layer=True,
            effect_param_defs=self._project._effect_param_defs,
        )
        self._insert_layer(layer)
        return cast("AVLayer", layer)

    def add_shape(self) -> ShapeLayer:
        """Create a new empty shape layer at the top of the layer stack.

        Returns:
            The newly created [ShapeLayer][].
        """
        existing = {lyr.name for lyr in self.layers}
        name = auto_name(ShapeLayer._auto_name, existing)

        layer = ShapeLayer._new(
            name=name,
            layer_id=self._project._allocate_layer_id(),
            duration=self.duration,
            containing_comp=self,
            effect_param_defs=self._project._effect_param_defs,
        )
        self._insert_layer(layer)
        return cast("ShapeLayer", layer)

    def add_camera(
        self,
        name: str | None = None,
        center_point: list[float] | None = None,
    ) -> CameraLayer:
        """Create a new camera layer at the top of the layer stack.

        Args:
            name: Layer name. Auto-generated if `None`.
            center_point: The `[x, y]` center point. Defaults to
                `[width/2, height/2]`.

        Returns:
            The newly created [CameraLayer][].
        """
        if name is None:
            existing = {lyr.name for lyr in self.layers}
            name = auto_name(CameraLayer._auto_name, existing)

        if center_point is None:
            center_point = [self.width / 2, self.height / 2]
        else:
            validate_vector2(center_point)

        layer = CameraLayer._new(
            name=name,
            layer_id=self._project._allocate_layer_id(),
            duration=self.duration,
            containing_comp=self,
            effect_param_defs=self._project._effect_param_defs,
        )
        self._insert_layer(layer)

        # AE rounds the zoom to 8 decimals before storing it.
        zoom = round(self.width * self.pixel_aspect / CameraLayer._zoom_dividend, 8)

        transform = layer.transform
        anchor_point = cast("Property", transform["ADBE Anchor Point"])
        anchor_point.value = [
            center_point[0],
            center_point[1],
            0.0,
        ]
        # ExtendScript reports a new two-node camera's position as
        # [0, 0, -zoom] (the point of interest carries the center).
        position = cast("Property", transform["ADBE Position"])
        position.value = [0.0, 0.0, -zoom]

        return layer

    def add_light(
        self,
        name: str | None = None,
        center_point: list[float] | None = None,
    ) -> LightLayer:
        """Create a new light layer at the top of the layer stack.

        Args:
            name: Layer name. Auto-generated if `None`.
            center_point: The `[x, y]` center point. Defaults to
                `[width/2, height/2]`.

        Returns:
            The newly created [LightLayer][].
        """
        if name is None:
            existing = {lyr.name for lyr in self.layers}
            name = auto_name(LightLayer._auto_name, existing)

        if center_point is None:
            center_point = [self.width / 2, self.height / 2]
        else:
            validate_vector2(center_point)

        layer = LightLayer._new(
            name=name,
            layer_id=self._project._allocate_layer_id(),
            duration=self.duration,
            containing_comp=self,
            light_type=1,
            effect_param_defs=self._project._effect_param_defs,
        )
        self._insert_layer(layer)

        # AE rounds the zoom to 8 decimals before storing it.
        zoom = round(self.width * self.pixel_aspect / LightLayer._zoom_dividend, 8)

        transform = layer.transform
        anchor_point = cast("Property", transform["ADBE Anchor Point"])
        anchor_point.value = [
            center_point[0],
            center_point[1],
            0.0,
        ]
        # Like cameras, lights report position [0, 0, -zoom/2] with the
        # point of interest at the center.
        position = cast("Property", transform["ADBE Position"])
        position.value = [0.0, 0.0, -zoom / 2]

        return layer

    def add(
        self,
        item: AVItem,
        duration: float | None = None,
    ) -> AVLayer:
        """Add an existing footage or composition item as a new layer.

        Args:
            item: The [AVItem][] (footage or composition) to add.
            duration: Layer duration in seconds. Defaults to the composition
                duration.

        Returns:
            The newly created [AVLayer][].
        """
        if not isinstance(item, AVItem):
            raise ValueError("item must be an AVItem (FootageItem or CompItem).")

        if duration is not None:
            validate_duration(duration)

        # AE leaves the layer name empty for source-named layers.
        layer = AVLayer._new(
            name="",
            layer_id=self._project._allocate_layer_id(),
            source_id=item.id,
            duration=duration if duration is not None else self.duration,
            containing_comp=self,
            effect_param_defs=self._project._effect_param_defs,
        )
        self._insert_layer(layer)

        self._project._ensure_used_in_linked()
        if hasattr(item, "_used_in"):
            item._used_in.add(self)

        return cast("AVLayer", layer)

    def add_solid(
        self,
        color: list[float],
        name: str | None = None,
        width: int | None = None,
        height: int | None = None,
        pixel_aspect: float = 1.0,
        duration: float | None = None,
    ) -> AVLayer:
        """Create a new solid layer at the top of the layer stack.

        Args:
            color: Solid color as `[R, G, B]` in 0.0--1.0 range.
            name: The solid and layer name. Pass `None` to auto-generate
                a name from the color (e.g. `Red Solid 1`).
            width: Solid width in pixels. Defaults to comp width.
            height: Solid height in pixels. Defaults to comp height.
            pixel_aspect: Pixel aspect ratio (default 1.0).
            duration: Layer duration in seconds. Defaults to comp duration.

        Returns:
            The newly created [AVLayer][].
        """
        # Validate before the auto-name subscripts the color, so malformed
        # input raises ValueError instead of TypeError/IndexError.
        validate_rgb_color(color)

        if name is None:
            existing = {item.name for item in self._project.items.values()}
            solid_name = SolidSource._color_name(color[0], color[1], color[2])
            name = auto_name(solid_name, existing)

        if width is None:
            width = self.width
        if height is None:
            height = self.height

        solid_source = SolidSource._new(
            name=name,
            color=color,
            width=width,
            height=height,
            pixel_aspect=pixel_aspect,
        )
        solids_folder = self._project._solids_folder
        footage = FootageItem._new(
            source=solid_source,
            project=self._project,
            parent_folder=solids_folder,
        )
        solids_folder._children_container.append(footage._item_list)
        solids_folder._children_container.extend(footage._view_data)
        self._project.items[footage.id] = footage
        solids_folder.items.append(footage)

        # AE leaves the layer name empty for source-named layers (the
        # name resolves from the solid footage item).
        layer = AVLayer._new(
            name="",
            layer_id=self._project._allocate_layer_id(),
            source_id=footage.id,
            duration=duration if duration is not None else self.duration,
            containing_comp=self,
            effect_param_defs=self._project._effect_param_defs,
        )
        self._insert_layer(layer)

        self._project._ensure_used_in_linked()
        if hasattr(footage, "_used_in"):
            footage._used_in.add(self)

        return cast("AVLayer", layer)

    def _build_text_btds(
        self,
        text: str,
        box_size: list[float] | None = None,
        line_orientation: LineOrientation | None = None,
    ) -> tuple[ListChunk, ListChunk, TdmnChunk]:
        """Build the binary btds/btdk structure for a text layer.

        Args:
            text: The text content.
            box_size: `[width, height]` for box text; `None` for point text.
            line_orientation: Text [LineOrientation][]; `None` for the
                default horizontal orientation.

        Returns:
            A `(LIST:btds, btgu, tdmn)` tuple to inject into the root tdgp.
        """
        td = TextDocument(text, box_size=box_size, line_orientation=line_orientation)
        btdk = td._btdk_body

        # Text-document tdbs carries an empty cdat with 4 trailing zero
        # bytes (matches what AE writes).
        cdat = CdatChunk(pad=b"\x00\x00\x00\x00")
        tdb4 = Tdb4Chunk(
            dimensions=1,
            time_base=self._cdta.internal_timebase,
            no_value_flags=1,
            type_flags=0x08,
            cvot_flags=0x04,
            value_hint_type=1,
        )
        tdbs = ListChunk(
            list_type="tdbs",
            chunks=[
                TdsbChunk(),
                TdsnChunk.new(TDSN_SENTINEL),
                tdb4,
                cdat,
            ],
        )
        btds = ListChunk(list_type="btds", chunks=[tdbs, btdk])
        btgu = ListChunk(
            list_type="btgu",
            chunks=[PguiChunk.new(), PguiChunk()],
        )
        tdmn = TdmnChunk(value="ADBE Text Document")
        return btds, btgu, tdmn

    def _add_text_layer(
        self,
        text: str,
        box: bool = False,
        box_size: list[float] | None = None,
        line_orientation: LineOrientation | None = None,
    ) -> TextLayer:
        validate_string(text)
        if box:
            if box_size is None:
                box_size = [float(self.width), float(self.height)]
            else:
                validate_vector2(box_size)

        existing = {lyr.name for lyr in self.layers}
        text = text or auto_name(TextLayer._auto_name, existing)

        btds, btgu, td_mn = self._build_text_btds(
            text, box_size=box_size, line_orientation=line_orientation
        )

        layer = TextLayer._new(
            name=text,
            layer_id=self._project._allocate_layer_id(),
            duration=self.duration,
            containing_comp=self,
            btds=btds,
            btgu=btgu,
            tdmn=td_mn,
            effect_param_defs=self._project._effect_param_defs,
        )
        self._insert_layer(layer)
        return cast("TextLayer", layer)

    def add_text(
        self,
        text: str = "",
    ) -> TextLayer:
        """Create a new point text layer at the top of the layer stack.

        Args:
            text: Initial text content.

        Returns:
            The newly created [TextLayer][].
        """
        return self._add_text_layer(text=text, box=False)

    def add_box_text(
        self,
        box_size: list[float] | None = None,
        text: str = "",
    ) -> TextLayer:
        """Create a new box (paragraph) text layer at the top of the layer stack.

        Args:
            box_size: `[width, height]` of the text box. If `None`, uses
                the composition dimensions.
            text: Initial text content.

        Returns:
            The newly created [TextLayer][].
        """
        return self._add_text_layer(text=text, box=True, box_size=box_size)

    @requires_version(24)
    def add_vertical_text(
        self,
        text: str = "",
    ) -> TextLayer:
        """Create a new vertical point text layer at the top of the stack.

        Vertical text flows top-to-bottom with lines stacking right-to-left,
        matching the Vertical Type Tool default.

        Args:
            text: Initial text content.

        Returns:
            The newly created [TextLayer][].
        """
        return self._add_text_layer(
            text=text,
            box=False,
            line_orientation=LineOrientation.VERTICAL_RIGHT_TO_LEFT,
        )

    @requires_version(24)
    def add_vertical_box_text(
        self,
        box_size: list[float] | None = None,
        text: str = "",
    ) -> TextLayer:
        """Create a new vertical box (paragraph) text layer at the top of the stack.

        Vertical text flows top-to-bottom with lines stacking right-to-left,
        matching the Vertical Type Tool default.

        Args:
            box_size: `[width, height]` of the text box. If `None`, uses
                the composition dimensions.
            text: Initial text content.

        Returns:
            The newly created [TextLayer][].
        """
        return self._add_text_layer(
            text=text,
            box=True,
            box_size=box_size,
            line_orientation=LineOrientation.VERTICAL_RIGHT_TO_LEFT,
        )
