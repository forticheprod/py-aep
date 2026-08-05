from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, List, Mapping, cast

from ...ae_version import requires_version
from ...binary.chunk import Chunk, DeferredListChunk, ListChunk
from ...binary.comp_skeleton import (
    build_cps2,
    build_item_view_chunks,
    build_layer_view_block,
    build_new_comp_item,
)
from ...binary.composition_chunks import CdtaChunk
from ...binary.item_chunks import IdtaChunk, IideChunk
from ...binary.layer_chunks import (
    _LDTA_SOURCE_ID_END,
    _LDTA_SOURCE_ID_OFFSET,
    LdtaChunk,
)
from ...binary.misc_chunks import _PRDA_VARIANTS, PguiChunk, PrdaChunk, PrinChunk
from ...binary.mutations import (
    build_checkbox_cctl,
    build_color_cctl,
    build_media_cctl,
    build_ovg2,
    build_slider_cctl,
    build_source_alternate_extras,
    build_text_cctl,
    clone_chunk_tree,
    rewrite_owner_tdpi,
)
from ...binary.property_chunks import (
    TDSN_SENTINEL,
    CdatChunk,
    Tdb4Chunk,
    TdmnChunk,
    TdsbChunk,
    TdsnChunk,
)
from ...binary.scalar_chunks import F8Chunk, S4Chunk, U1Chunk, U4Chunk, Utf8Chunk
from ...binary.utils import (
    ChunkNotFoundError,
    block_slice,
    filter_by_list_type,
    filter_by_type,
    find_by_list_type,
    find_by_type,
    index_by_identity,
    recursive_find,
)
from ...enums import Label, LayerType, LineOrientation, ParametricMeshType, PREFType
from ...parsers.essential_graphics import parse_essential_graphics
from ...resolvers.motion_graphics import (
    CONTROLLER_CHECKBOX,
    CONTROLLER_COLOR,
    CONTROLLER_SLIDER,
    can_add_layer,
    font_caps_json,
    media_controller_path,
    property_controller_plan,
)
from ...synthesis.property import _CAMERA_LIGHT_TRANSFORM_SKIP, _OMITTED_EMPTY_GROUPS
from ..descriptors import ChunkField
from ..essential_graphics import EssentialGraphicsController, SourcePropertyRef
from ..layers.av_layer import AVLayer, _unregister_source_usage
from ..layers.camera_layer import CameraLayer
from ..layers.light_layer import LightLayer
from ..layers.parametric_mesh_layer import ParametricMeshLayer
from ..layers.shape_layer import ShapeLayer
from ..layers.text_layer import TextLayer
from ..layers.three_d_model_layer import ThreeDModelLayer
from ..naming import auto_name
from ..preferences import (
    apply_text_style_prefs,
    default_still_out_point,
    default_synthetic_out_point,
    label_index,
)
from ..properties.property import Property
from ..properties.property_group import PropertyGroup
from ..sources.file import FileSource
from ..sources.placeholder import PlaceholderSource
from ..sources.solid import SolidSource
from ..text.text_document import TextDocument
from ..validators import (
    _validate_number,
    validate_box_size,
    validate_duration,
    validate_footage_dimension,
    validate_frame_rate,
    validate_name,
    validate_one_of,
    validate_pixel_aspect,
    validate_rgb_color,
    validate_sequence,
    validate_string,
    validate_text,
    validate_vector2,
)
from .av_item import AVItem
from .footage import FootageItem

if TYPE_CHECKING:
    from typing import Callable, Iterator

    from ...binary.item_chunks import CmtaChunk
    from ...resolvers.motion_graphics import PathNode, PropertyControllerPlan
    from ..layers.layer import Layer
    from ..project import Project
    from ..properties.marker import MarkerValue
    from .folder import FolderItem
    from .renderer_options import RendererOptions

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

_RENDERER_DISPLAY_NAMES: dict[str, str] = {
    "ADBE Escher": "Classic 3D",
    "ADBE Calder": "Advanced 3D",
    "ADBE Ernst": "Cinema 4D",
    "ADBE Picasso": "Ray-traced 3D",
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
        for child in group._properties:
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

    # AE writes the `ADBE Layer Source Alternate` leaf (with its blsv/blsi
    # skeleton) inside Source Options for every new layer. `_materialize_tree`
    # iterates raw `_properties` and so never triggers that group's deferred
    # child synthesis, so materialize the leaf explicitly here.
    for top in layer.properties:
        if (
            isinstance(top, PropertyGroup)
            and top.match_name == "ADBE Source Options Group"
        ):
            for child in top.properties:
                if child.match_name == "ADBE Layer Source Alternate" and isinstance(
                    child, Property
                ):
                    child._ensure_materialized()
            break

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


def _rewrite_eg_identity(
    cloned_item: ListChunk,
    old_comp_id: int,
    new_comp_id: int,
    id_map: dict[int, int],
) -> None:
    """Give a duplicated comp's Essential Graphics controllers a new identity.

    AE's duplicate mints a fresh uuid per controller - kept identical
    across the CIFO/CIF2/CIF3 containers, matched here by the OLD uuid
    since the legacy containers can be stale - and retargets `CCId` /
    `CLId` at the duplicate. Layer-side OvG2 override uuids are NOT
    touched: they reference controllers of other (source) comps.
    """
    uuid_map: dict[str, str] = {}
    for cif in cloned_item.chunks:
        if not isinstance(cif, ListChunk) or cif.list_type not in (
            "CIFO",
            "CIF2",
            "CIF3",
        ):
            continue
        for cctl in filter_by_list_type(chunks=cif.chunks, list_type="CCtl"):
            utf8s = filter_by_type(chunks=cctl.chunks, chunk_type="Utf8")
            if utf8s:
                uuid_utf8 = cast("Utf8Chunk", utf8s[0])
                if uuid_utf8.value not in uuid_map:
                    uuid_map[uuid_utf8.value] = str(uuid.uuid4())
                uuid_utf8.value = uuid_map[uuid_utf8.value]
            for chunk in cctl.chunks:
                # AE zeroes the controller's cached value/default in the
                # duplicate and re-derives them from the source property
                # (probed in AE 2026 on a slider controller).
                if chunk.chunk_type in ("CVal", "CDef") and chunk.data:
                    chunk.data = b"\x00" * len(chunk.data)
            try:
                cprp = find_by_list_type(chunks=cctl.chunks, list_type="CPrp")
            except ChunkNotFoundError:
                continue
            for chunk in cprp.chunks:
                if chunk.chunk_type == "CCId":
                    ccid = cast("U4Chunk", chunk)
                    if ccid.value == old_comp_id:
                        ccid.value = new_comp_id
                elif chunk.chunk_type == "CLId":
                    clid = cast("U4Chunk", chunk)
                    if clid.value in id_map:
                        clid.value = id_map[clid.value]


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

    draft3d = ChunkField.bool(
        "_cdta",
        "draft3d",
    )
    """When `True`, Draft 3D mode is enabled for the composition.
    Read / Write.

    Warning:
        Deprecated in After Effects 2024 in favor of the new Draft 3D mode."""

    frame_blending = ChunkField.bool(
        "_cdta",
        "frame_blending",
    )
    """When `True`, frame blending is enabled for this Composition. Corresponds
    to the value of the Frame Blending button in the Composition panel.
    Read / Write."""

    hide_shy_layers = ChunkField.bool(
        "_cdta",
        "hide_shy_layers",
    )
    """When `True`, only layers with `shy` set to `False` are shown in the
    Timeline panel. When `False`, all layers are visible, including those
    whose `shy` value is `True`. Corresponds to the value of the Hide All
    Shy Layers button in the Composition panel. Read / Write."""

    motion_blur = ChunkField.bool(
        "_cdta",
        "motion_blur",
    )
    """When `True`, motion blur is enabled for the composition. Corresponds
    to the value of the Motion Blur button in the Composition panel.
    Read / Write."""

    preserve_nested_frame_rate = ChunkField.bool(
        "_cdta",
        "preserve_nested_frame_rate",
    )
    """When `True`, the frame rate of nested compositions is preserved in
    the current composition. Corresponds to the value of the "Preserve frame
    rate when nested or in render queue" option in the Advanced tab of the
    Composition Settings dialog box. Read / Write."""

    preserve_nested_resolution = ChunkField.bool(
        "_cdta",
        "preserve_nested_resolution",
    )
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

    drop_frame = ChunkField.bool(
        "_cdrp",
        "value",
        transform=bool,
        reverse=int,
        default=False,
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

        new_id = project._allocate_id()

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
            allocate_layer_id=project._allocate_id,
            label=label_index(project._preferences, "Comp Label Index 2", 15),
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
        self.__type_cache: dict[str, list[Any]] | None = None
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
        self.prin_list = find_by_list_type(chunks=_child_chunks, list_type="PRin")
        self._prin = cast(
            "PrinChunk",
            find_by_type(chunks=self.prin_list.chunks, chunk_type="prin"),
        )
        self._prda = cast(
            "PrdaChunk",
            find_by_type(chunks=self.prin_list.chunks, chunk_type="prda"),
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

    def duplicate(self) -> CompItem:
        """Creates and returns a duplicate of this composition, which
        contains the same layers as the original.

        The duplicate is placed directly after the original in its folder and named with
        the next numeric suffix (`Comp` > `Comp 2`). Every layer id - including the
        viewer pseudo-layers - is freshly allocated, with parent, track
        matte and effect layer-references remapped to the new siblings.
        Essential Graphics controllers get fresh uuids with their comp and
        layer references retargeted at the duplicate. Layer sources
        (footage, precomps) and layer-side Essential Property override
        uuids stay shared with the original.

        Returns:
            The newly created [CompItem][].
        """
        # Circular: parsers.item -> parsers.composition -> models.
        from ...parsers.item import parse_item  # noqa: PLC0415

        project = self._project
        parent = self._parent_folder
        assert parent is not None
        container = parent._children_container

        # Clone the comp's whole block: LIST:Item + trailing view chunks.
        start, end = block_slice(
            container, self._item_list, self._ITEM_BOUNDARY_LIST_TYPES
        )
        cloned_block = [clone_chunk_tree(c) for c in container[start:end]]
        cloned_item = cast("ListChunk", cloned_block[0])

        old_comp_id = self.id
        new_comp_id = project._allocate_id()
        try:
            # Pre-2020 files have no iide; the id then lives only in idta.
            cast(
                "IideChunk", find_by_type(chunks=cloned_item.chunks, chunk_type="iide")
            ).value = new_comp_id
        except ChunkNotFoundError:
            pass
        cast(
            "IdtaChunk", find_by_type(chunks=cloned_item.chunks, chunk_type="idta")
        ).item_id = new_comp_id

        # Fresh ids for every ldta - real layers AND viewer pseudo-layers,
        # AE reallocates them all - then remap every intra-comp layer
        # reference. Ids not in the map (0 / stale) stay untouched, and
        # source_id is deliberately kept: footage and precomp sources are
        # shared with the original.
        ldta_chunks = [
            cast("LdtaChunk", c)
            for c in recursive_find(cloned_item.chunks, chunk_type="ldta")
        ]
        id_map: dict[int, int] = {}
        for ldta in ldta_chunks:
            id_map[ldta.layer_id] = project._allocate_id()
        for ldta in ldta_chunks:
            ldta.layer_id = id_map[ldta.layer_id]
            if ldta.parent_id in id_map:
                ldta.parent_id = id_map[ldta.parent_id]
            # matte_layer_id is absent (None) in pre-AE23 files.
            matte = ldta.matte_layer_id
            if matte is not None and matte in id_map:
                ldta.matte_layer_id = id_map[matte]
        # tdpi layer references: the effect owner (hidden -0000 param) and
        # effect layer parameters (e.g. Set Matte's source layer) - both
        # can only point at layers of this comp.
        for tdpi in recursive_find(cloned_item.chunks, chunk_type="tdpi"):
            value = cast("S4Chunk", tdpi).value
            if value in id_map:
                cast("S4Chunk", tdpi).value = id_map[value]

        _rewrite_eg_identity(cloned_item, old_comp_id, new_comp_id, id_map)

        # Name (the item block's first direct Utf8), numbered like AE.
        existing = {item.name for item in project.items.values()}
        cast(
            "Utf8Chunk", find_by_type(chunks=cloned_item.chunks, chunk_type="Utf8")
        ).value = auto_name(self.name, existing)

        # Insert right after the original's block, then build the model
        # through the normal parse path (registers it in project.items).
        container[end:end] = cloned_block
        new_comp = cast(
            "CompItem",
            parse_item(item_chunk=cloned_item, project=project, parent_folder=parent),
        )
        parent.items.insert(parent.items.index(self) + 1, new_comp)

        # Register the duplicate on its layer sources' used_in if linking
        # already ran (the lazy pass covers it otherwise).
        if project._used_in_linked:
            for source_id in new_comp._source_ids_for_linking():
                source = project.items.get(source_id)
                if source is not None and hasattr(source, "_used_in"):
                    source._used_in.add(new_comp)

        return new_comp

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
        parametric_mesh: list[ParametricMeshLayer] = []
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
                elif isinstance(layer, ParametricMeshLayer):
                    parametric_mesh.append(layer)
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
            "parametric_mesh": parametric_mesh,
        }
        self.__type_cache = cache
        return cache

    def _invalidate_layer_cache(self) -> None:
        """Reset layer caches after structural mutations."""
        self.__type_cache = None
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
    def _proxy_pin_index(self) -> int:
        """A composition has no main-source pin, so its proxy pin is at
        index 0 (footage items keep the main pin at 0 and the proxy at 1)."""
        return 0

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
        """The number of controllers in the Essential Graphics panel for the
        composition. Read-only.

        Note: for each type-10 Group controller, After Effects synthesizes a
        runtime-only "drop zone" controller it does not store in the file, so
        this count is one lower per group than ExtendScript's
        `motionGraphicsTemplateControllerCount`."""
        return len(self.motion_graphics_controllers)

    @property
    def motion_graphics_template_controller_names(self) -> list[str]:
        """The names of all controllers in the Essential Graphics panel.
        Read-only. Excludes the runtime-only Group "drop zone" controller AE
        synthesizes but does not store (see
        `motion_graphics_template_controller_count`)."""
        return [ctrl.name for ctrl in self.motion_graphics_controllers]

    def _cif_containers(self) -> list[ListChunk]:
        """The `CIFO`/`CIF2`/`CIF3` Essential Graphics containers of this comp,
        in file order (every comp AE or py_aep writes has all three)."""
        return [
            c
            for c in self._item_list.chunks
            if isinstance(c, ListChunk) and c.list_type in ("CIFO", "CIF2", "CIF3")
        ]

    def _build_property_cctl(
        self, plan: PropertyControllerPlan, prop: Property, name: str, uuid_str: str
    ) -> tuple[ListChunk, Utf8Chunk, U4Chunk]:
        """Assemble one `LIST:CCtl` for `prop` per the resolved `plan`.

        Called once per CIF container so each holds its own chunk objects.
        """
        comp_id = self.id
        layer_id = plan.layer._ldta.layer_id
        if plan.controller_type == CONTROLLER_SLIDER:
            # AE seeds the EGP slider range from the pard UI slider range
            # (Slider Control -> 0..100 despite its +/-1e6 valid range,
            # Brightness -> -150..150), falling back to the valid range for
            # pard-less properties (Transform > Opacity -> 0..100).
            min_v = prop._slider_min if prop._slider_min is not None else prop.min_value
            max_v = prop._slider_max if prop._slider_max is not None else prop.max_value
            return build_slider_cctl(
                name,
                uuid_str,
                float(cast("float", prop.value)),
                float(min_v) if min_v is not None else 0.0,
                float(max_v) if max_v is not None else 100.0,
                comp_id,
                layer_id,
                plan.path_json,
            )
        if plan.controller_type == CONTROLLER_CHECKBOX:
            return build_checkbox_cctl(
                name, uuid_str, bool(prop.value), comp_id, layer_id, plan.path_json
            )
        if plan.controller_type == CONTROLLER_COLOR:
            rgba = [float(c) for c in cast("list[float]", prop.value)]
            rgba = (rgba + [1.0, 1.0, 1.0, 1.0])[:4]
            return build_color_cctl(
                name, uuid_str, rgba, comp_id, layer_id, plan.path_json
            )
        text = prop.value.text if isinstance(prop.value, TextDocument) else ""
        return build_text_cctl(
            name,
            uuid_str,
            text,
            font_caps_json(prop),
            comp_id,
            layer_id,
            plan.path_json,
        )

    def _append_controller(
        self,
        build: Callable[[], tuple[ListChunk, Utf8Chunk, U4Chunk]],
    ) -> tuple[Utf8Chunk, U4Chunk] | None:
        """Append one freshly built `LIST:CCtl` per CIF container and bump
        each `CcCt` count (AE keeps the `CIFO`/`CIF2`/`CIF3` copies in sync).

        Returns the CIF3 copy's editable chunks `(name_utf8, ctyp)` for the
        controller model - the parser's preferred container - or `None` when
        the comp has no CIF containers (not produced by AE or py_aep).
        """
        containers = self._cif_containers()
        if not containers:
            return None
        model_name_utf8: Utf8Chunk | None = None
        model_ctyp: U4Chunk | None = None
        for cif in containers:
            cctl, name_utf8, ctyp = build()
            cif.chunks.append(cctl)
            ccct = cast("U4Chunk", find_by_type(chunks=cif.chunks, chunk_type="CcCt"))
            ccct.value += 1
            if cif.list_type == "CIF3" or model_name_utf8 is None:
                model_name_utf8, model_ctyp = name_utf8, ctyp
        return cast("Utf8Chunk", model_name_utf8), cast("U4Chunk", model_ctyp)

    def _register_controller(
        self,
        bound: tuple[Utf8Chunk, U4Chunk],
        uuid_str: str,
        nodes: list[PathNode],
        layer: Layer,
    ) -> None:
        """Append the model for a controller just written to the containers."""
        name_utf8, ctyp = bound
        self._eg_controllers.append(
            EssentialGraphicsController(
                _name_utf8=name_utf8,
                _ctyp=ctyp,
                uuid=uuid_str,
                source_property_path=[
                    SourcePropertyRef(
                        match_name=node.match_name, prop_index=node.prop_index
                    )
                    for node in nodes
                ],
                source_comp_id=self.id,
                source_layer_id=layer._ldta.layer_id,
            )
        )

    def _add_property_controller(self, prop: Property, name: str | None) -> bool:
        """Add `prop` to this comp's Essential Graphics panel.

        Returns `False` (adding nothing) when `prop` cannot be exposed - see
        `resolvers.motion_graphics`.
        """
        self._ensure_comp_parsed()
        plan = property_controller_plan(prop, self)
        if plan is None:
            return False
        display = name if name is not None else prop.name
        validate_name(display)
        uuid_str = str(uuid.uuid4())
        bound = self._append_controller(
            lambda: self._build_property_cctl(plan, prop, display, uuid_str)
        )
        if bound is None:
            return False
        self._register_controller(bound, uuid_str, plan.nodes, plan.layer)
        return True

    def _add_layer_controller(self, layer: AVLayer, name: str | None) -> bool:
        """Add `layer` to this comp's Essential Graphics panel as a Media
        Replacement (type 14) controller.

        Returns `False` (adding nothing) when the layer is not eligible -
        see `resolvers.motion_graphics.can_add_layer`.
        """
        self._ensure_comp_parsed()
        if not can_add_layer(layer, self):
            return False
        source = layer.source
        assert source is not None  # guaranteed by can_add_layer
        display = name if name is not None else layer.name
        validate_name(display)
        uuid_str = str(uuid.uuid4())
        timebase = self._cdta.internal_timebase
        nodes, path_json = media_controller_path()
        # AE names a per-controller thumbnail cache file it regenerates on
        # open; only the uuid-shaped name is stored in the project.
        thumbnail = f"{uuid.uuid4()}.png"
        bound = self._append_controller(
            lambda: build_media_cctl(
                display,
                uuid_str,
                source.width,
                source.height,
                round(layer.in_point * timebase),
                round(layer.out_point * timebase),
                timebase,
                thumbnail,
                self.id,
                layer._ldta.layer_id,
                path_json,
            )
        )
        if bound is None:
            return False
        self._register_controller(bound, uuid_str, nodes, layer)
        return True

    @property
    def renderers(self) -> list[str]:
        """The available rendering plug-in module names. Read-only."""
        return list(_RENDERER_EXTENDSCRIPT_TO_BINARY)

    @property
    def renderer(self) -> str:
        """The current rendering plug-in module to be used to render this
        composition, as set in the Advanced tab of the Composition Settings
        dialog box. Allowed values are the members of `renderers`.
        Read / Write.

        Changing the renderer replaces the stored options with the new
        renderer's defaults. Previous options are not preserved.
        Read `renderer_options` again after changing the renderer."""
        binary_name = str(self._prin.match_name)
        return _RENDERER_BINARY_TO_EXTENDSCRIPT.get(binary_name, binary_name)

    @renderer.setter
    def renderer(self, value: str) -> None:
        _validate_renderer(value)
        binary_name = _RENDERER_EXTENDSCRIPT_TO_BINARY[value]
        if binary_name == self._prin.match_name:
            # If comp is already set to the requested renderer,
            # preserve renderer options instead of replacing with defaults
            return
        # Otherwise update match name and display name
        self._prin.match_name = binary_name
        self._prin.display_name = _RENDERER_DISPLAY_NAMES[binary_name]
        # Create a fresh prda chunk using requested renderer's default settings
        new_prda = _PRDA_VARIANTS[binary_name][0]()
        # Replace the existing prda chunk
        prin_chunks = self.prin_list.chunks
        prin_chunks[index_by_identity(prin_chunks, self._prda)] = new_prda
        self._prda = new_prda

    @property
    def renderer_options(self) -> RendererOptions:
        """The active 3D renderer's options, as a mutable mapping.

        Keys are the labels the Render Options dialog uses, and the same
        object also exposes each option as a typed attribute.

        Example:
            ```python
            comp.renderer_options["Quality"] = 61
            comp.renderer_options.quality = 61
            ```

        The concrete type follows the composition's 3D renderer. Note
        that [renderer][] holds the ExtendScript module name, and the
        one for Classic 3D is (confusingly) `ADBE Advanced 3d`:

        - `ADBE Advanced 3d` (Classic 3D) - [ClassicRendererOptions][]
        - `ADBE Calder` (Advanced 3D) - [AdvancedRendererOptions][]
        - `ADBE Ernst` (Cinema 4D) - [Cinema4DRendererOptions][]
        - `ADBE Picasso` (Ray-traced 3D) - [RayTracedRendererOptions][]

        Read / Write.
        """
        from .renderer_options import renderer_options_for  # noqa: PLC0415

        return renderer_options_for(self._prda, self)

    @renderer_options.setter
    def renderer_options(self, value: Mapping[str, Any]) -> None:
        if not isinstance(value, Mapping):
            raise ValueError("renderer_options must be a mapping of key-value pairs")
        view = self.renderer_options
        for key, option in value.items():
            view[key] = option

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

    def remove_all_markers(self) -> None:
        """Remove all markers from this composition.

        A no-op when the composition has no markers.
        """
        if self.marker_property is not None:
            self.marker_property.remove_all_keys()

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
    def _type_cache(self) -> dict[str, list[Any]]:
        """Cached layer type lists for O(1) access."""
        return (
            self.__type_cache
            if self.__type_cache is not None
            else self._build_type_cache()
        )

    @property
    def av_layers(self) -> list[AVLayer]:
        """A list of all [AVLayer][] objects in this composition."""
        return self._type_cache["av"]

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
        return self._type_cache["text"]

    @property
    def shape_layers(self) -> list[ShapeLayer]:
        """A list of the shape layers in this composition."""
        return self._type_cache["shape"]

    @property
    def camera_layers(self) -> list[CameraLayer]:
        """A list of the camera layers in this composition."""
        return self._type_cache["camera"]

    @property
    def light_layers(self) -> list[LightLayer]:
        """A list of the light layers in this composition."""
        return self._type_cache["light"]

    @property
    def three_d_model_layers(self) -> list[ThreeDModelLayer]:
        """A list of the 3D model layers in this composition."""
        return self._type_cache["three_d_model"]

    @property
    def parametric_mesh_layers(self) -> list[ParametricMeshLayer]:
        """A list of the parametric mesh layers in this composition."""
        return self._type_cache["parametric_mesh"]

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

    def _synthetic_layer_duration(self) -> float:
        """Default span of a new sourceless layer (solid, null, text,
        shape, camera, light), from the "Pref_DEFAULT_SYNTHETIC_OUT_POINT"
        preference; comp duration for the factory `0/0` value."""
        pref = default_synthetic_out_point(self._project._preferences)
        return pref if pref is not None else self.duration

    def _still_layer_duration(self) -> float:
        """Default span of a new still-footage layer, from the
        "Pref_DEFAULT_STILL_OUT_POINT" preference; comp duration for the
        factory `0/0` value."""
        pref = default_still_out_point(self._project._preferences)
        return pref if pref is not None else self.duration

    def _insert_layer(self, layer: Layer) -> None:
        """Insert a fully-constructed layer at the top of the layer stack.

        Handles view block creation, chunk insertion, materialization,
        and layer list bookkeeping.
        """
        # AE anchors new layers at the comp's current time when the
        # "Create New Layers At Time Zero" preference is off: start = in
        # = time, out shifted by the same amount (probed in AE 2026 for
        # every scripted layer add). duplicate() bypasses this path and
        # keeps the source timing, matching AE.
        at_time_zero = self._project._preferences.get_pref_as_bool(
            "General Section",
            "Create New Layers At Time Zero",
            PREFType.PREF_Type_MACHINE_INDEPENDENT,
            default=True,
        )
        if not at_time_zero and self.time:
            layer.start_time = self.time

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
            duration: Layer duration in seconds. Defaults to the
                synthetic-layer default span (the
                "Pref_DEFAULT_SYNTHETIC_OUT_POINT" preference; composition
                duration by default). AE's `addNull` ignores this argument
                (probed in AE 2026); py_aep honors it, since it sets the
                layer out-point directly and the result is a valid AE file.

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
            layer_id=self._project._allocate_id(),
            source_id=footage.id,
            duration=(
                duration if duration is not None else self._synthetic_layer_duration()
            ),
            containing_comp=self,
            null_layer=True,
            label=label_index(self._project._preferences, "Null Label Index", 1),
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
            layer_id=self._project._allocate_id(),
            duration=self._synthetic_layer_duration(),
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
            layer_id=self._project._allocate_id(),
            duration=self._synthetic_layer_duration(),
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

        # AE's new-camera Camera Zoom equals the same computed zoom. Without
        # this the property keeps its 0.0 spec placeholder, which violates its
        # own >= 1 minimum and makes keyframing the zoom raise ValueError.
        camera_options = cast("PropertyGroup", layer["ADBE Camera Options Group"])
        zoom_prop = cast("Property", camera_options["ADBE Camera Zoom"])
        zoom_prop.value = zoom

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
            layer_id=self._project._allocate_id(),
            duration=self._synthetic_layer_duration(),
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

    def add_parametric_mesh(
        self,
        name: str | None = None,
        *,
        mesh_type: ParametricMeshType,
    ) -> ParametricMeshLayer:
        """Create a new parametric mesh layer at the top of the layer stack.

        Args:
            name: Layer name. Auto-generated if `None`.
            mesh_type: The type of parametric mesh (required, keyword-only).

        Returns:
            The newly created [ParametricMeshLayer][].
        """
        explicit_name = name is not None
        if name is None:
            existing = {lyr.name for lyr in self.layers}
            prefix = mesh_type.name.title()
            name = auto_name(f"{prefix} {ParametricMeshLayer._auto_name}", existing)

        layer = ParametricMeshLayer._new(
            name=name,
            layer_id=self._project._allocate_id(),
            duration=self._synthetic_layer_duration(),
            containing_comp=self,
            mesh_type=mesh_type,
            effect_param_defs=self._project._effect_param_defs,
        )
        # AE sets the ldta name bit when addParametricMesh receives an
        # explicit name (unlike other sourceless layers); UI-created mesh
        # layers with default names leave it clear.
        layer._ldta.name_set = explicit_name
        self._insert_layer(layer)
        return layer

    def add(
        self,
        item: AVItem,
        duration: float | None = None,
    ) -> AVLayer:
        """Add an existing footage or composition item as a new layer.

        Args:
            item: The [AVItem][] (footage or composition) to add.
            duration: Layer duration in seconds, for still footage.
                By default (probed in AE 2026) timed footage and nested
                comps span their source duration, and stills span the
                still-layer default (the "Pref_DEFAULT_STILL_OUT_POINT"
                preference; composition duration by default).

        Returns:
            The newly created [AVLayer][].
        """
        if not isinstance(item, AVItem):
            raise ValueError("item must be an AVItem (FootageItem or CompItem).")

        if duration is not None:
            validate_duration(duration)
            layer_duration = duration
        elif item.duration:
            layer_duration = item.duration
        else:
            layer_duration = self._still_layer_duration()

        # AE leaves the layer name empty for source-named layers, and the
        # new layer's label mirrors the item's label at add time (probed
        # in AE 2026, including user-recolored items).
        layer = AVLayer._new(
            name="",
            layer_id=self._project._allocate_id(),
            source_id=item.id,
            duration=layer_duration,
            containing_comp=self,
            label=int(item.label),
            effect_param_defs=self._project._effect_param_defs,
        )
        self._insert_layer(layer)

        self._project._ensure_used_in_linked()
        if hasattr(item, "_used_in"):
            item._used_in.add(self)

        return cast("AVLayer", layer)

    def precompose(
        self,
        layer_indices: list[int],
        name: str,
        move_all_attributes: bool = True,
    ) -> CompItem:
        """Create a new [CompItem][] and move the specified layers into it.

        The moved layers are replaced in this composition by a single new
        layer whose source is the new composition, placed at the topmost
        moved layer's index. The new composition inherits this composition's
        settings and is stored at the alphabetical position in this
        composition's folder.

        Parent and track-matte links follow AE's rules: links inside the
        moved set are kept; a stayer referencing a moved layer retargets
        to the replacement layer; a moved layer whose parent stays is
        unparented; a moved layer whose track matte stays gets a copy of
        the matte layer inside the new composition (the original stays
        untouched).

        When `move_all_attributes` is `False` (allowed for a single
        source-backed layer only), the selected layer stays in this
        composition with all its attributes and its source is swapped to
        the new composition, which is sized from the layer's source and
        contains one fresh layer referencing that source.

        Warning:
            References to moved `Layer` objects become stale (the layers
            are re-created inside the new composition), mirroring
            ExtendScript's reference invalidation.

        Args:
            layer_indices: 0-based indices of the layers to precompose
                (ExtendScript uses 1-based indices).
            name: The name of the new composition.
            move_all_attributes: `True` (default) to move all attributes
                into the new composition; `False` to leave them on the
                retained layer ("Leave all attributes" in the
                Pre-compose dialog).

        Returns:
            The newly created [CompItem][].

        Raises:
            ValueError: If `layer_indices` is empty or contains an
                out-of-range index, or if `move_all_attributes` is
                `False` with more than one index or with a layer that
                has no source.
        """
        validate_string(name)
        if not isinstance(layer_indices, (list, tuple)) or not layer_indices:
            raise ValueError("layer_indices must be a non-empty list.")
        check_index = _validate_number(integer=True, min=0, max=len(self.layers) - 1)
        for idx in layer_indices:
            check_index(idx)
        indices = sorted(set(layer_indices))
        if not move_all_attributes:
            if len(indices) != 1:
                raise ValueError(
                    "move_all_attributes=False requires exactly one layer index."
                )
            layer = self.layers[indices[0]]
            # 3D model layers cannot swap sources (replace_source raises);
            # check before mutating so a failure leaves the project intact.
            if (
                not isinstance(layer, AVLayer)
                or layer.source is None
                or layer._ldta.layer_type == LayerType.THREE_D_MODEL
            ):
                raise ValueError(
                    "move_all_attributes=False requires a layer with a "
                    "replaceable source."
                )
            return self._precompose_leave_attributes(layer, name)
        return self._precompose_move(indices, name)

    def _create_precomp_item(self, name: str, width: int, height: int) -> CompItem:
        """Create the precompose target composition.

        Built via `add_comp` for the skeleton, then this composition's
        settings are inherited by byte-copying its cdta (AE writes the
        new comp's cdta byte-identical to the parent's, with only
        width/height overridden in the leave-attributes path), and the
        item is stored at the alphabetical position AE uses.
        """
        folder = self.parent_folder
        assert folder is not None
        new_comp = folder.add_comp(
            name, width, height, self.pixel_aspect, self.duration, self.frame_rate
        )
        cloned = cast("CdtaChunk", clone_chunk_tree(self._cdta))
        cloned.width = width
        cloned.height = height
        cdta_idx = index_by_identity(new_comp._item_list.chunks, new_comp._cdta)
        new_comp._item_list.chunks[cdta_idx] = cloned
        new_comp._cdta = cloned
        folder._reposition_child_sorted(new_comp)
        return new_comp

    def _precompose_leave_attributes(self, layer: AVLayer, name: str) -> CompItem:
        """The `move_all_attributes=False` path: the retained layer only
        swaps its source to the new comp (sized from the layer's source),
        which holds one fresh layer referencing the original source."""
        source = layer.source
        assert source is not None
        new_comp = self._create_precomp_item(name, source.width, source.height)
        new_comp.add(source)
        layer.replace_source(new_comp)
        return new_comp

    def _precompose_move(self, indices: list[int], name: str) -> CompItem:
        """The `move_all_attributes=True` path: verbatim chunk-block moves
        with fresh layer ids."""
        # Circular: parsers.layer -> models.layers -> models.items
        from ...parsers.layer import parse_layer  # noqa: PLC0415

        project = self._project
        moved = [self.layers[i] for i in indices]
        top_index = indices[0]
        old_ids = {ly.id for ly in moved}
        repl_enabled = moved[0].enabled

        new_comp = self._create_precomp_item(name, self.width, self.height)

        # Detach the moved layers' chunk blocks (top-down keeps their
        # relative stacking order).
        blocks: list[list[Chunk]] = []
        for ly in moved:
            start, end = self._layer_block_slice(ly)
            blocks.append(self._item_list.chunks[start:end])
            del self._item_list.chunks[start:end]
            self._layers.remove(ly)
        self._invalidate_layer_cache()

        # AE reallocates layer ids on precompose; owner tdpi values inside
        # each layer's tdgp reference the owning layer id and must follow.
        id_map: dict[int, int] = {}
        for ly in moved:
            new_id = project._allocate_id()
            id_map[ly.id] = new_id
            ly._ldta.layer_id = new_id
            rewrite_owner_tdpi(ly._layer_list, new_id)

        # A moved layer whose track matte stays behind gets a verbatim
        # COPY of the matte layer directly below it in the new comp; the
        # original matte layer stays untouched in this comp (AE 2026).
        matte_map: dict[int, int] = {}
        final_blocks: list[list[Chunk]] = []
        for ly, block in zip(moved, blocks):
            final_blocks.append(block)
            matte_id = ly._ldta.matte_layer_id or 0
            if matte_id and matte_id not in id_map and matte_id not in matte_map:
                matte_layer = self.layers_by_id.get(matte_id)
                if matte_layer is not None:
                    m_start, m_end = self._layer_block_slice(matte_layer)
                    m_block = [
                        clone_chunk_tree(c)
                        for c in self._item_list.chunks[m_start:m_end]
                    ]
                    m_list = cast("ListChunk", m_block[0])
                    m_ldta = cast(
                        "LdtaChunk",
                        find_by_type(chunks=m_list.chunks, chunk_type="ldta"),
                    )
                    copy_id = project._allocate_id()
                    m_ldta.layer_id = copy_id
                    rewrite_owner_tdpi(m_list, copy_id)
                    # The clone's own references point at old-comp layer
                    # ids: follow a parent/matte that moved, drop one that
                    # stayed behind (it does not exist in the new comp).
                    if m_ldta.parent_id:
                        m_ldta.parent_id = id_map.get(m_ldta.parent_id, 0)
                    if m_ldta.matte_layer_id:
                        m_ldta.matte_layer_id = id_map.get(m_ldta.matte_layer_id, 0)
                    matte_map[matte_id] = copy_id
                    final_blocks.append(m_block)

        # Remap references inside the moved set: both ends moved -> new
        # id; parent stayed behind -> unparented; matte stayed behind ->
        # the copy created above.
        for ly in moved:
            ldta = ly._ldta
            if ldta.parent_id:
                ldta.parent_id = id_map.get(ldta.parent_id, 0)
            matte_id = ldta.matte_layer_id or 0
            if matte_id:
                ldta.matte_layer_id = id_map.get(matte_id) or matte_map.get(matte_id, 0)

        # Insert the blocks and re-parse each layer in the new comp's
        # context (the old Layer models go stale, like ExtendScript).
        new_comp._ensure_layers_loaded()
        insert_at = new_comp._find_first_layer_position()
        effect_defs = project._effect_param_defs
        for block in final_blocks:
            new_comp._item_list.chunks[insert_at:insert_at] = block
            insert_at += len(block)
            new_layer = parse_layer(cast("ListChunk", block[0]), new_comp, effect_defs)
            new_comp._layers.append(new_layer)
        new_comp._invalidate_layer_cache()

        # Source usage bookkeeping for the moved (and copied) layers.
        project._ensure_used_in_linked()
        for new_layer in new_comp._layers:
            source = getattr(new_layer, "source", None)
            if source is not None and hasattr(source, "_used_in"):
                _unregister_source_usage(source, self)
                source._used_in.add(new_comp)

        # Replacement layer at the topmost moved index. AE writes the
        # Sandstone label and inherits the topmost moved layer's video
        # switch (a matte layer moved alone keeps serving as matte, so
        # it stays off).
        repl = self.add(new_comp)
        if top_index > 0:
            repl.move_after(self.layers[top_index])
        repl.label = Label.SANDSTONE
        repl.enabled = repl_enabled

        # Stayers referencing a moved layer retarget to the replacement
        # layer (both parenting and track matte).
        repl_id = repl.id
        for ly in self.layers:
            if ly is repl:
                continue
            ldta = ly._ldta
            if ldta.parent_id in old_ids:
                ldta.parent_id = repl_id
            if ldta.matte_layer_id in old_ids:
                ldta.matte_layer_id = repl_id

        self._invalidate_layer_cache()
        return new_comp

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
            duration: Layer duration in seconds. Defaults to the
                synthetic-layer default span (the
                "Pref_DEFAULT_SYNTHETIC_OUT_POINT" preference; composition
                duration by default). AE's `addSolid` ignores this argument
                (probed in AE 2026); py_aep honors it, since it sets the
                layer out-point directly and the result is a valid AE file.

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
            layer_id=self._project._allocate_id(),
            source_id=footage.id,
            duration=(
                duration if duration is not None else self._synthetic_layer_duration()
            ),
            containing_comp=self,
            label=label_index(self._project._preferences, "Solid Label Index 2", 1),
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
        # AE applies the character-level "Text Style Sheet" preferences to
        # every new text layer (probed in AE 2026; the paragraph sheet is
        # not applied).
        apply_text_style_prefs(td, self._project._preferences)
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
        validate_text(text)
        if box:
            if box_size is None:
                box_size = [float(self.width), float(self.height)]
            else:
                validate_box_size(box_size)

        existing = {lyr.name for lyr in self.layers}
        text = text or auto_name(TextLayer._auto_name, existing)

        btds, btgu, td_mn = self._build_text_btds(
            text, box_size=box_size, line_orientation=line_orientation
        )

        layer = TextLayer._new(
            name=text,
            layer_id=self._project._allocate_id(),
            duration=self._synthetic_layer_duration(),
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
