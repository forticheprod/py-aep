from __future__ import annotations

import json
import os
import uuid
import warnings
import xml.etree.ElementTree as ET
from itertools import count
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ..ae_version import requires_version
from ..binary.chunk import Chunk, ListChunk, write_aep
from ..binary.footage_chunks import (
    build_ai_layer_opti_data,
    build_psd_flattened_opti_data,
    build_psd_layer_opti_data,
    build_text_opti_data,
)
from ..binary.item_chunks import (
    HeadChunk,
    NhedChunk,
    NnhdChunk,
    TimeDisplayPrefItem,
)
from ..binary.misc_chunks import DwgaChunk
from ..binary.project_chunks import (
    CpidChunk,
    FdtaChunk,
    SvapChunk,
    WsnmChunk,
    WsnsChunk,
)
from ..binary.scalar_chunks import F8Chunk, U1Chunk, U2Chunk, U4Chunk, Utf8Chunk
from ..binary.utils import (
    ChunkNotFoundError,
    filter_by_type,
    find_by_list_type,
    find_by_type,
    index_by_identity,
    recursive_find,
    toggle_flag_chunk,
)
from ..color.envelope import (
    build_icc_envelope,
    build_ocio_display_envelope,
    envelope_profile_name,
)
from ..color.icc import IccProfileLibrary
from ..color.ocio import (
    list_config_color_spaces,
    ocio_color_profile_envelope,
    require_ocio_config,
    resolve_ocio_config,
)
from ..data.file_formats import (
    AI_COMP_EXTENSIONS,
    EPS_COMP_EXTENSIONS,
    PSD_COMP_EXTENSIONS,
)
from ..enums import (
    BitsPerChannel,
    ColorManagementSystem,
    FeetFramesFilmType,
    FootageTimecodeDisplayStartType,
    FramesCountType,
    GpuAccelType,
    ImportAsType,
    LutInterpolationMethod,
    PREFType,
    TimeDisplayType,
)
from ..enums.mappings import adobe_color_profile_names
from ..resolvers.ai_layers import (
    read_ai_color_info,
    read_ai_layers,
)
from ..resolvers.media_probe import probe_media
from ..resolvers.psd_layers import (
    FlattenedPsdError,
    PsdGroup,
    PsdLayer,
    read_psd_layers,
)
from ..resolvers.psd_paths import parse_vector_mask
from ..resolvers.psd_styles import (
    has_enabled_styles,
    parse_layer_styles,
    read_global_light,
)
from ..synthesis.layer import LayerGroupSpec, LayerSpec
from ..synthesis.property import (
    _ADV_BLEND_SPECS,
    _BLEND_OPTIONS_SPECS,
    _LAYER_STYLE_CHILD_SPECS,
    _STYLE_ANGLE_SUFFIXES,
    _STYLE_ENUM_SUFFIXES,
    _STYLE_HINT_BOUNDS,
    _STYLE_HINT_BOUNDS_EXCEPTIONS,
    PropSpec,
)
from .descriptors import ChunkField
from .import_options import ImportOptions
from .items.composition import CompItem
from .items.folder import FolderItem
from .items.footage import FootageItem
from .items.item import Item
from .preferences import (
    Preferences,
    default_sequence_fps,
    psd_comp_layer_styles,
    psd_footage_dimensions,
    psd_footage_layer_styles,
)
from .properties.gradient import Gradient
from .properties.property import Property, _values_equal
from .properties.property_group import PropertyGroup
from .properties.shape import Shape
from .renderqueue.render_queue import RenderQueue
from .sources.file import PSD_LAYER_STYLES_C8, FileSource
from .text.ranges import _replace_layer_font
from .validators import (
    _validate_number,
    validate_bool,
    validate_enum,
    validate_font_name,
    validate_one_of,
    validate_path,
    validate_path_does_not_exist,
    validate_path_exists,
    validate_string,
    validate_u2,
)

if TYPE_CHECKING:
    from typing import ClassVar, Iterator

    from ..binary.layer_chunks import LdtaChunk
    from ..binary.render_chunks import RenderSettingsItem
    from ..parsers.templates import OutputModuleTemplate
    from ..resolvers.media_probe import MediaInfo
    from ..resolvers.psd_styles import PsdLayerStyles
    from .items.av_item import AVItem
    from .layers.av_layer import AVLayer
    from .layers.layer import Layer
    from .properties.mask_property_group import MaskPropertyGroup
    from .text.font_object import FontObject
    from .text.text_document import TextDocument


_validate_expression_engine = validate_one_of(("extendscript", "javascript-1.0"))


def _font_post_script_name(font: FontObject | str) -> str:
    """The PostScript name of a `replace_font` argument."""
    if isinstance(font, str):
        validate_font_name(font)
        return font
    name = getattr(font, "post_script_name", None)
    if not isinstance(name, str) or not name:
        raise TypeError("expected a FontObject or a PostScript name string")
    return name


# AE's default new-composition import timing for a layered file: a 30-second
# duration rounded to whole frames at 29.97 fps. This is AE's built-in
# factory default, not a preference: verified by deleting every AE pref
# file and cold-starting AE (regenerated factory prefs, "Composition
# Settings7" empty) - a layered PSD still imported at 29.97 fps / 30 s.
_LAYERED_COMP_FRAME_RATE = 29.97
_LAYERED_COMP_DURATION_SECONDS = 30.0


class Project:
    """
    The `Project` object represents an After Effects project. Attributes
    provide access to specific objects within the project, such as imported
    files or footage and compositions, and also to project settings such as the
    timecode base.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        project = app.project
        print(project.file)
        for item in project:
            ...
        ```

    See: https://ae-scripting.docsforadobe.dev/general/project/
    """

    bits_per_channel = ChunkField.enum(
        BitsPerChannel,
        "_nnhd",
        "bits_per_channel",
        post_set=lambda obj: obj._sync_nhed_field("bits_per_channel"),
    )
    """The color depth of the current project, either 8, 16, or 32 bits.
    Read / Write."""

    feet_frames_film_type = ChunkField.enum(
        FeetFramesFilmType,
        "_nnhd",
        "feet_frames_film_type",
        post_set=lambda obj: obj._sync_nhed_field("_display_byte"),
    )
    """The film type for feet+frames timecode display, either MM16 (16mm) or
    MM35 (35mm). Read / Write."""

    footage_timecode_display_start_type = ChunkField.enum(
        FootageTimecodeDisplayStartType,
        "_nnhd",
        "footage_timecode_display_start_type",
        post_set=lambda obj: obj._sync_nhed_field(
            "footage_timecode_display_start_type"
        ),
    )
    """The Footage Start Time setting in the Project Settings dialog box,
    which is enabled when Timecode is selected as the time display style.
    Read / Write."""

    _timecode_default_base = ChunkField[int](
        "_nnhd",
        "timecode_default_base",
        validate=_validate_number(min=1, max=999, integer=True),
    )
    """The Default Base value in the Time Display Style section of
    the Project Settings dialog, under Timecode. Read/Write."""

    frames_count_type = ChunkField.enum(
        FramesCountType,
        "_nnhd",
        "frames_count_type",
        post_set=lambda obj: obj._sync_nhed_field("frames_count_type"),
    )
    """The Frame Count menu setting in the Project Settings dialog box.
    Read / Write."""

    display_start_frame = ChunkField[int](
        "_nnhd",
        "display_start_frame",
        validate=validate_one_of((0, 1)),
        post_set=lambda obj: obj._sync_nhed_field("frames_count_type"),
    )
    """The start frame number for the project display (0 or 1). An alternate
    way of setting the Frame Count menu setting. Read / Write."""

    frames_use_feet_frames = ChunkField.bool(
        "_nnhd",
        "frames_use_feet_frames",
        post_set=lambda obj: obj._sync_nhed_field("_feet_byte"),
    )
    """When `True`, the Frames field in the UI is displayed as
    feet+frames. Read / Write."""

    time_display_type = ChunkField.enum(
        TimeDisplayType,
        "_nnhd",
        "time_display_type",
        post_set=lambda obj: obj._sync_nhed_field("_display_byte"),
    )
    """The time display style, corresponding to the Time Display Style
    section in the Project Settings dialog box. Read / Write."""

    transparency_grid_thumbnails = ChunkField.bool(
        "_nnhd",
        "transparency_grid_thumbnails",
        post_set=lambda obj: obj._sync_nhed_field("transparency_grid_thumbnails"),
    )
    """When `True`, thumbnail views use the transparency checkerboard
    pattern. Read / Write."""

    revision = ChunkField[int]("_head", "file_revision", validate=validate_u2)
    """The current revision of the project. Every user action increases the
    revision number by one. A new project starts at revision 1. Read / Write.

    Note:
        This attribute is read-only in ExtendScript.
    """

    compensate_for_scene_referred_profiles = ChunkField.bool(
        "_acer",
        "value",
        transform=bool,
        reverse=int,
        min_version=16,
    )
    """When True, After Effects compensates for scene-referred profiles when
    rendering."""

    audio_sample_rate = ChunkField[float](
        "_adfr",
        "value",
        validate=validate_one_of((22050, 32000, 44100, 48000, 96000)),
    )
    """The project audio sample rate in Hz.

    Allowed values: 22050, 32000, 44100, 48000, 96000.

    Note:
        Not exposed in ExtendScript"""

    working_gamma = ChunkField[float](
        "_dwga",
        "working_gamma",
        validate=validate_one_of((2.2, 2.4)),
    )
    """The gamma value used for the working color space, either 2.2 or 2.4.
    Read / Write."""

    gpu_accel_type = ChunkField.enum(
        GpuAccelType,
        "_gpug_utf8",
        "value",
        min_version=13,
    )
    """The GPU acceleration type for the project. None if not
    recognised. Read / Write."""

    # ChunkField needs a chunk_attr that resolves to an object holding the
    # target field.  _xmp lives directly on Project, so we alias _aep = self
    # in __init__ so the descriptor chain is: getattr(self, "_aep") -> self,
    # then getattr(self, "_xmp") -> the raw XMP string.
    xmp_packet = ChunkField["ET.Element | None"](
        "_aep",
        "_xmp",
        transform=lambda s: ET.fromstring(s) if s and s.strip() else None,
        reverse=lambda el: (
            ET.tostring(el, encoding="unicode") if el is not None else ""
        ),
    )
    """The XMP packet for the project, containing metadata. `None` when the
    project has no XMP packet (e.g. projects created via `py_aep.new()`).
    Read / Write."""

    def __init__(
        self,
        *,
        _nhed: NhedChunk,
        _nnhd: NnhdChunk,
        _head: HeadChunk,
        _acer: U1Chunk,
        _adfr: F8Chunk,
        _dwga: DwgaChunk,
        _gpug_utf8: Utf8Chunk,
        _exen_utf8: Utf8Chunk | None,
        _cms_utf8: Utf8Chunk | None,
        _ws_utf8: Utf8Chunk | None,
        _dcs_utf8: Utf8Chunk | None,
        _rifx: ListChunk,
        _xmp: str,
        file: str,
        items: dict[int, Item],
        render_queue: RenderQueue | None,
        ae_preferences_dir: Path | None = None,
    ) -> None:
        # Chunk body references for descriptors
        self._nhed = _nhed
        self._nnhd = _nnhd
        self._head = _head
        self._acer = _acer
        self._adfr = _adfr
        self._dwga = _dwga
        self._gpug_utf8 = _gpug_utf8
        self._exen_utf8 = _exen_utf8
        self._cms_utf8 = _cms_utf8
        self._ws_utf8 = _ws_utf8
        self._dcs_utf8 = _dcs_utf8
        self._rifx = _rifx
        self._xmp = _xmp
        self._aep = self

        # Read-only attributes
        self._file = file
        self._items = items
        self._render_queue = render_queue
        self._active_item: Item | None = None
        self._effect_param_defs: dict[str, dict[str, dict[str, Any]]] = {}
        self._effect_definitions_cache: list[tuple[str, str, ListChunk]] | None = None
        self._used_in_linked = False

        self._id_counter_reconciled = False  # lazily done on first allocation
        self._ae_preferences_dir = ae_preferences_dir
        self._preferences = Preferences(ae_preferences_dir)
        # ICC profile discovery for Adobe-CMS working-space writes. `None`
        # dirs = auto-discover the standard Adobe Color directories.
        self._icc_profile_dirs: list[Path] | None = None
        self._icc_library: IccProfileLibrary | None = None
        self._render_templates_cache: list[RenderSettingsItem] | None = None
        self._output_templates_cache: list[OutputModuleTemplate] | None = None
        self._default_render_template_index: int | None = None

    # Color-management settings JSON AE 2026 writes for a new project.
    # Inherited from the empty-project ground truth; callers can override
    # via color_management_system / lut_interpolation_method / etc.
    _NEW_PROJECT_CMS_JSON: ClassVar[str] = '{"lutInterpolationMethod":1}'

    def _effect_definitions(self) -> list[tuple[str, str, ListChunk]]:
        """`LIST:EfdG` effect definitions, walked once and cached.

        EfdG is read-only after parse (adding an installed effect clones
        its sspc template into the layer rather than editing EfdG), so the
        walk is computed lazily on first lookup and reused across adds.
        """
        if self._effect_definitions_cache is None:
            from ..parsers.effect import effect_definition_entries  # noqa: PLC0415

            self._effect_definitions_cache = effect_definition_entries(
                self._rifx.chunks
            )
        return self._effect_definitions_cache

    @classmethod
    def _apply_project_settings_prefs(
        cls,
        preferences: Preferences,
        nhed: NhedChunk,
        nnhd: NnhdChunk,
    ) -> None:
        """Apply the last-used Project Settings preferences to a new project.

        AE persists the Project Settings dialog into the machine-specific
        "Project Pref Section" (color depth plus a 16-byte time-display
        blob mirroring the `nnhd` settings cluster) and File > New
        inherits them. Missing or malformed values leave the AE-factory
        chunk defaults untouched.
        """
        depth = preferences.get_pref_as_number(
            "Project Pref Section", "Project Settings Depth", default=0
        )
        if depth in (1, 2):  # 0 = 8 bpc = the chunk default
            nhed.bits_per_channel = int(depth)
            nnhd.bits_per_channel = int(depth)
        blob = preferences._get_bytes(
            "Project Pref Section",
            "Project Settings Time Display Format",
            PREFType.PREF_Type_MACHINE_SPECIFIC,
        )
        if blob is None or len(blob) != 16:
            return
        item = TimeDisplayPrefItem.frombytes(blob)
        assert isinstance(item, TimeDisplayPrefItem)
        for chunk in (nhed, nnhd):
            chunk.time_display_type = item.display_byte & 0x7F
            chunk.feet_frames_film_type = bool(item.display_byte & 0x80)
            chunk.footage_timecode_display_start_type = (
                item.footage_timecode_display_start_type
            )
            chunk.frames_use_feet_frames = bool(item.feet_byte & 0x01)
            chunk.timecode_default_base = item.timecode_default_base
            chunk.frames_count_type = item.frames_count_type

    @classmethod
    def _new(cls, version: str, ae_preferences_dir: Path | None = None) -> Project:
        """Build a new, empty project (mirrors AE's File > New Project).

        Constructs the minimal root chunk skeleton AE accepts - the large
        workspace blobs AE regenerates on open (`LSIf/AFsi`, `PTRE/ftwd`)
        are omitted - stamps `version` into the head chunk, and wires the
        model the same way `parse_project` does. `ae_preferences_dir` is
        stored for render-queue template lookup. See [Application][] and
        `py_aep.new`.
        """
        preferences = Preferences(ae_preferences_dir)
        head = HeadChunk()
        # HeadChunk defaults the OS / release / reserved bits AE always writes
        # for a saved Windows release build (see _version_word); the .version
        # setter stamps the version bits while preserving them.
        head.version = version
        # AE refuses to open a file whose file_format_version exceeds its
        # own; deriving it from the requested version lets new(old_version)
        # open in that AE (validated AE 2022-2026).
        head.sync_file_format_version()
        major = head.ae_version_major
        svap = SvapChunk(build_number=head.ae_build_number)
        nhed = NhedChunk()
        nnhd = NnhdChunk()
        cls._apply_project_settings_prefs(preferences, nhed, nnhd)
        acer = U1Chunk(chunk_type="acer", value=1)
        adfr = F8Chunk(chunk_type="adfr", value=48000.0)
        dwga = DwgaChunk(working_gamma_selector=1)
        gpug_utf8 = Utf8Chunk(value=str(uuid.uuid4()))
        fold = ListChunk(list_type="Fold", chunks=[FdtaChunk()])
        # AE stamps the "New Project Solids Folder" preference into the
        # root sfnm chunk at File > New; the stored name is used from
        # then on (see _solids_folder_name).
        solids_name = preferences.get_pref_as_string(
            "Template Project",
            "New Project Solids Folder",
            PREFType.PREF_Type_MACHINE_INDEPENDENT,
            default="Solids",
        )

        # Root chunks in AE's order. Several are version-gated: AE adds them
        # in later releases, and a fresh project from an older AE omits them
        # (boundaries from samples/versions + emptier_2018.aep). The big
        # workspace blobs AE regenerates on open are omitted entirely.
        cms_utf8: Utf8Chunk | None = None
        exen_utf8: Utf8Chunk | None = None
        root_chunks: list[Chunk] = [
            svap,
            head,
            nhed,
            nnhd,
            adfr,
            ListChunk(list_type="Pefl"),
            U1Chunk(chunk_type="qtlg"),
            ListChunk(list_type="gpuG", chunks=[gpug_utf8]),
            ListChunk(
                list_type="sfnm",
                chunks=[
                    Utf8Chunk(value=solids_name or "Solids"),
                    U4Chunk(chunk_type="sfid"),
                ],
            ),
        ]
        if major >= 22:
            root_chunks.append(U4Chunk(chunk_type="mrid"))
        root_chunks += [acer, ListChunk(list_type="CPPl"), CpidChunk(), dwga]
        if major >= 22:  # color management (pcms/PwCs) added in AE 22
            cms_utf8 = Utf8Chunk(value=cls._NEW_PROJECT_CMS_JSON)
            root_chunks += [
                U1Chunk(chunk_type="pcms", value=1),
                cms_utf8,
                U1Chunk(chunk_type="PwCs", value=1),
                Utf8Chunk(value="{}"),
            ]
        if major >= 23:  # pdvc added in AE 23
            root_chunks += [U1Chunk(chunk_type="pdvc", value=1), Utf8Chunk(value="{}")]
        if major >= 16:  # JS expression engine (LIST:ExEn) added in AE 16
            exen_utf8 = Utf8Chunk(value="javascript-1.0")
            root_chunks.append(ListChunk(list_type="ExEn", chunks=[exen_utf8]))
        root_chunks += [
            fold,
            # Workspace name ("Default"): wsns is the wsnm byte length, wsnm is
            # the name (UTF-16-LE), then a UTF-8 copy. WsnsChunk/WsnmChunk bake
            # the "Default" workspace as their defaults.
            WsnsChunk(),
            WsnmChunk(),
            Utf8Chunk(value="Default"),
            U4Chunk(chunk_type="fcid"),
            U2Chunk(chunk_type="oacc"),
        ]
        rifx = ListChunk(chunk_type="RIFX", list_type="Egg!", chunks=root_chunks)

        project = cls(
            _nhed=nhed,
            _nnhd=nnhd,
            _head=head,
            _acer=acer,
            _adfr=adfr,
            _dwga=dwga,
            _gpug_utf8=gpug_utf8,
            _exen_utf8=exen_utf8,
            _cms_utf8=cms_utf8,
            _ws_utf8=None,
            _dcs_utf8=None,
            _rifx=rifx,
            _xmp="",
            file="",
            items={},
            render_queue=None,
            ae_preferences_dir=ae_preferences_dir,
        )

        # Root folder (mirrors parse_folder(is_root=True): no idta/name, the
        # Fold chunk list is its own children container).
        root_folder = FolderItem(
            _idta=None,
            _name_utf8=None,
            _cmta=None,
            _item_list=fold,
            _gide=None,
            _children_container=fold.chunks,
            project=project,
            parent_folder=None,
        )
        root_folder.__dict__["name"] = "root"
        project.items[0] = root_folder
        project._active_item = root_folder

        # Empty render queue (LIST:LRdr appended after the loose root chunks,
        # matching AE's ordering).
        render_queue = RenderQueue._new(project)
        rifx.chunks.append(render_queue._lrdr)
        project._render_queue = render_queue

        return project

    def __repr__(self) -> str:
        return f"Project(file={self._file!r})"

    def __iter__(self) -> Iterator[Item]:
        """Return an iterator over the project's items."""
        return iter(self.items.values())

    def _ensure_used_in_linked(self) -> None:
        """Populate `AVItem._used_in` sets on first access.

        Deferred until the first `used_in` read or mutation that
        needs the back-references for correctness (e.g. cycle detection).
        """
        if self._used_in_linked:
            return
        self._used_in_linked = True
        for composition in self.compositions:
            for source_id in composition._source_ids_for_linking():
                source = self.items.get(source_id)
                if source is not None and hasattr(source, "_used_in"):
                    source._used_in.add(composition)

    @property
    def file(self) -> str:
        """The full path to the project file. Read-only."""
        return self._file

    @property
    def items(self) -> dict[int, Item]:
        """All the items in the project. Read-only."""
        return self._items

    @property
    def render_queue(self) -> RenderQueue | None:
        """The Render Queue of the project. Read-only."""
        return self._render_queue

    @property
    def active_item(self) -> Item | None:
        """The item that is currently active and is to be acted upon, or
        `None` if no item is currently selected or if multiple items are
        selected. Read-only."""
        return self._active_item

    @property
    def root_folder(self) -> FolderItem:
        """The root folder. This is a virtual folder that contains all items
        in the Project panel, but not items contained inside other folders in
        the Project panel. Read-only."""
        return cast("FolderItem", self._items[0])

    @property
    def _root_chunks(self) -> list[Chunk]:
        return self._rifx.chunks

    def _sync_nhed_field(self, field_name: str) -> None:
        setattr(self._nhed, field_name, getattr(self._nnhd, field_name))

    @property
    def linear_blending(self) -> bool:
        """When True, linear blending is used for the project. When False,
        the standard blending mode is used. Read / Write."""
        return any(c.chunk_type == "lnrb" for c in self._root_chunks)

    @linear_blending.setter
    def linear_blending(self, value: bool) -> None:
        validate_bool(value)
        # AE keeps `lnrb` in a fixed slot right after `cpid` (before `lnrp` /
        # `dwga`); appending it at the tail makes AE report "missing data".
        toggle_flag_chunk(self._rifx, "lnrb", value, after_types=("cpid",))

    @property
    def linearize_working_space(self) -> bool:
        """When True, the working color space is linearized for blending
        operations. Read / Write."""
        return any(c.chunk_type == "lnrp" for c in self._root_chunks)

    @linearize_working_space.setter
    @requires_version(16)
    def linearize_working_space(self, value: bool) -> None:
        validate_bool(value)
        # `lnrp` sits immediately after `lnrb` (or after `cpid` when linear
        # blending is off), before `dwga`.
        toggle_flag_chunk(self._rifx, "lnrp", value, after_types=("lnrb", "cpid"))

    @property
    def expression_engine(self) -> str:
        """The Expressions Engine setting in the Project Settings dialog box
        ("extendscript" or "javascript-1.0"). Read / Write."""
        if self._exen_utf8 is not None:
            return self._exen_utf8.value
        return "extendscript"

    @expression_engine.setter
    @requires_version(16)
    def expression_engine(self, value: str) -> None:
        _validate_expression_engine(value)
        if self._exen_utf8 is not None:
            self._exen_utf8.value = value
        else:
            utf8 = Utf8Chunk(value=value)
            exen = ListChunk(list_type="ExEn", chunks=[utf8])
            self._rifx.chunks.append(exen)
            self._exen_utf8 = utf8

    @property
    def effect_names(self) -> list[str]:
        """The names of all effects used in the project. Read-only."""
        return _get_effect_names(self._root_chunks)

    @property
    def working_space(self) -> str:
        """The name of the working color space (e.g., "sRGB IEC61966-2.1",
        "ACEScg", "None"). Read / Write.

        In OCIO mode, assigning any color space, role, alias, or
        `display/view` pair of [ocio_configuration_file][] rewrites the
        embedded profile JSON (AE identifies it by name, no ICC data). The
        config must be resolvable, because the envelope AE writes depends on
        which of those kinds the name is; `ValueError` is raised if it cannot
        be located or the name is not in it.

        In Adobe CMS mode, the matching ICC profile is discovered on disk (see
        [icc_profile_dirs][]) and embedded; `ColorProfileNotFoundError` is
        raised if it is not installed.
        """
        if self._ws_utf8 is not None:
            return envelope_profile_name(self._ws_utf8.value)
        if not any(c.chunk_type == "pcms" for c in self._root_chunks):
            return "sRGB IEC61966-2.1"
        return "None"

    @working_space.setter
    def working_space(self, value: str) -> None:
        validate_string(value)
        if self.color_management_system == ColorManagementSystem.OCIO:
            envelope = self._ocio_envelope(value)
        else:
            # bytes_for already raises ColorProfileNotFoundError for an
            # unknown Adobe profile name, so no separate name check is needed.
            envelope = build_icc_envelope(value, self._icc_lib().bytes_for(value))
        self._ws_utf8 = self._rewrite_color_profile("PwCs", envelope)

    def _ocio_envelope(self, name: str) -> str:
        """Build the OCIO color-profile envelope AE writes for `name`.

        `ocio_color_profile_envelope` raises for a name the config does not
        contain, so no separate membership check is needed.
        """
        config = require_ocio_config(
            self.ocio_configuration_file,
            f"build the color-profile envelope for {name!r}",
        )
        return ocio_color_profile_envelope(config, name)

    @property
    def icc_profile_dirs(self) -> list[Path] | None:
        """Directories scanned to resolve ICC profiles when writing an
        Adobe-CMS working space. `None` (default) auto-discovers the standard
        Adobe Color directories. Assign a list of folders containing `.icc`/
        `.icm` files to override (e.g. for a non-default install or CI)."""
        return self._icc_profile_dirs

    @icc_profile_dirs.setter
    def icc_profile_dirs(self, value: list[Path] | None) -> None:
        if value is not None:
            if not isinstance(value, (list, tuple)):
                raise TypeError(
                    "icc_profile_dirs must be a list of directories or None, "
                    f"got {type(value).__name__}"
                )
            for p in value:
                validate_path_exists(p)
            value = [Path(p) for p in value]
        self._icc_profile_dirs = value
        self._icc_library = None  # rebuild on next use

    def _icc_lib(self) -> IccProfileLibrary:
        if self._icc_library is None:
            self._icc_library = IccProfileLibrary(self._icc_profile_dirs)
        return self._icc_library

    @property
    def display_color_space(self) -> str:
        """The name of the display color space used for the project (e.g.,
        "ACES/sRGB"). Only relevant when color_management_system is OCIO.
        "None" when not set. Read / Write.

        Assign a `(display, view)` tuple or a `"display/view"` string. Writable
        only in OCIO mode (the chunk stores an OCIO display + view by name). In
        Adobe CMS mode the display uses the operating system's monitor profile,
        which is not stored in the project (the `pdvc` chunk is an empty `{}`,
        unlike `PwCs`/`working_space` which embeds the full ICC), so assigning
        raises [NotImplementedError][].

        Note:
            Not exposed in ExtendScript
        """
        if self._dcs_utf8 is not None:
            return envelope_profile_name(self._dcs_utf8.value)
        return "None"

    @display_color_space.setter
    def display_color_space(self, value: tuple[str, str] | str) -> None:
        if self.color_management_system != ColorManagementSystem.OCIO:
            raise NotImplementedError(
                "display_color_space is only settable in OCIO mode. In Adobe "
                "CMS the display uses the operating system's monitor profile, "
                "which is not stored in the project."
            )
        if isinstance(value, str):
            display, sep, view = value.rpartition("/")
            if not sep:
                raise ValueError(
                    "display_color_space string must be 'display/view'; got "
                    f"{value!r}. Pass a (display, view) tuple to disambiguate."
                )
        elif isinstance(value, tuple) and len(value) == 2:
            display, view = value
        else:
            raise TypeError(
                "display_color_space expects a 'display/view' string or a "
                f"(display, view) tuple, got {type(value).__name__}"
            )
        validate_string(display)
        validate_string(view)
        envelope = build_ocio_display_envelope(display, view)
        self._dcs_utf8 = self._rewrite_color_profile("pdvc", envelope)

    def _rewrite_color_profile(self, marker: str, envelope: str) -> Utf8Chunk:
        """Rewrite the `Utf8` color-profile chunk that follows `marker`.

        `marker` is the flag chunk (`PwCs` working space, `pdvc` display space)
        that AE writes immediately before the profile-JSON `Utf8`. The chunk
        pair exists in every project AE saved in OCIO mode (the `Utf8` is `{}`
        when unset), so this rewrites in place.

        Raises:
            ValueError: If the marker chunk is absent - color management is not
                initialized in this project (a brand-new project, or one from a
                pre-2022 After Effects, has no color-profile chunk to rewrite).
        """
        root = self._root_chunks
        for i, chunk in enumerate(root):
            if chunk.chunk_type == marker:
                if i + 1 < len(root) and root[i + 1].chunk_type == "Utf8":
                    utf8 = cast("Utf8Chunk", root[i + 1])
                    utf8.value = envelope
                    return utf8
                break
        raise ValueError(
            f"No '{marker}' color-profile chunk to write: color management is "
            "not initialized in this project. The project must be saved by "
            "After Effects (2022+) with color management enabled before its "
            "working/display color space can be set."
        )

    @property
    def color_management_system(self) -> ColorManagementSystem:
        """The color management system used by the project (Adobe or OCIO).
        Available in CC 2024 and later. Read / Write."""
        settings = self._get_cms_settings()
        return ColorManagementSystem(int(settings["colorManagementSystem"]))

    @color_management_system.setter
    @requires_version(24)
    def color_management_system(self, value: ColorManagementSystem | int) -> None:
        validate_enum(ColorManagementSystem)(value)
        self._update_cms_setting("colorManagementSystem", int(value))

    @property
    def lut_interpolation_method(self) -> LutInterpolationMethod:
        """The LUT interpolation method for the project (Trilinear or
        Tetrahedral). Read / Write."""
        settings = self._get_cms_settings()
        return LutInterpolationMethod(int(settings["lutInterpolationMethod"]))

    @lut_interpolation_method.setter
    @requires_version(24)
    def lut_interpolation_method(self, value: LutInterpolationMethod | int) -> None:
        validate_enum(LutInterpolationMethod)(value)
        self._update_cms_setting("lutInterpolationMethod", int(value))

    @property
    def ocio_configuration_file(self) -> str:
        """The OCIO configuration file for the project. Only relevant when
        color_management_system is OCIO. Read / Write."""
        settings = self._get_cms_settings()
        return str(settings["ocioConfigurationFile"])

    @ocio_configuration_file.setter
    @requires_version(24)
    def ocio_configuration_file(self, value: str | os.PathLike[str]) -> None:
        validate_path(value)
        self._update_cms_setting("ocioConfigurationFile", str(value))

    def list_color_profiles(self) -> list[str]:
        """Return the color-space names assignable in the current CMS mode.

        These are the names valid for [working_space][] (and, in Adobe mode,
        [media_color_space][
        py_aep.models.sources.footage.FootageSource.media_color_space] and the
        output color space).

        - Adobe CMS: the catalogued Adobe ICC profile names.
        - OCIO: the active color spaces of [ocio_configuration_file][] (a `.ocio`
          path or a built-in name like `"ACES 1.2"`). Returns `[]` if the config
          cannot be located or read.
        """
        if self.color_management_system == ColorManagementSystem.OCIO:
            config_path = resolve_ocio_config(self.ocio_configuration_file)
            if config_path is None:
                return []
            return list_config_color_spaces(config_path)
        return adobe_color_profile_names()

    @property
    def project_name(self) -> str:
        """The name of the project, derived from the file name."""
        return Path(self.file).name

    @property
    def num_items(self) -> int:
        """
        Return the number of items in the project.

        Note:
            Equivalent to `len(project.items)`
        """
        return len(self.items)

    def layer_by_id(self, layer_id: int) -> Layer:
        """Get a layer by its unique ID."""
        for comp in self.compositions:
            try:
                return comp.layers_by_id[layer_id]
            except KeyError:
                continue
        raise KeyError(f"Layer with ID {layer_id} not found")

    @property
    def compositions(self) -> list[CompItem]:
        """All the compositions in the project."""
        return [item for item in self.items.values() if isinstance(item, CompItem)]

    @property
    def folders(self) -> list[FolderItem]:
        """All the folders in the project."""
        return [item for item in self.items.values() if isinstance(item, FolderItem)]

    @property
    def footages(self) -> list[FootageItem]:
        """All the footages in the project."""
        return [item for item in self.items.values() if isinstance(item, FootageItem)]

    def import_placeholder(
        self,
        name: str | None,
        width: int,
        height: int,
        frame_rate: float,
        duration: float,
    ) -> FootageItem:
        """Import a placeholder footage item into the project root folder.

        Args:
            name: The placeholder name. Pass `None` to use
                `Missing Name`. An empty string becomes `Placeholder`.
            width: Width in pixels (4-30000).
            height: Height in pixels (4-30000).
            frame_rate: Frame rate in fps (1.0-99.0).
            duration: Duration in seconds (> 0, <= 10800).

        Returns:
            The newly created [FootageItem][].
        """
        from .sources.placeholder import PlaceholderSource

        if name is None:
            name = "Missing Name"
        elif name == "":
            name = "Placeholder"

        source = PlaceholderSource._new(name, width, height, frame_rate, duration)
        item = FootageItem._new(
            source,
            project=self,
            parent_folder=self.root_folder,
        )

        # Insert into root folder's chunk tree and register
        container = self.root_folder._children_container
        container.append(item._item_list)
        container.extend(item._view_data)
        self.items[item.id] = item
        self.root_folder.items.append(item)
        return item

    def import_file(self, options: ImportOptions) -> FootageItem | CompItem:
        """Imports the file specified in the specified ImportOptions object, using the
        specified options. Same as the File > Import File command.

        For `ImportAsType.FOOTAGE`, creates and returns a new FootageItem.
        For `ImportAsType.COMP` on a layered Illustrator/PDF (`.ai`, `.pdf`) or
        Photoshop (`.psd`, `.psb`) file, creates a composition with one footage
        layer per source layer (each referencing the same file) and returns
        that [CompItem][]. For `ImportAsType.COMP_CROPPED_LAYERS` on an SVG,
        converts the vector artwork into a new composition holding a single
        shape layer and returns that [CompItem][] (unlike ExtendScript, where
        `importFile` returns `null` for an SVG).

        Args:
            options: The import settings. `ImportAsType.FOOTAGE`, `COMP`
                (layered `.ai`/`.pdf`/`.psd`/`.psb`), and (for SVG)
                `COMP_CROPPED_LAYERS` are supported. With
                `ImportOptions.layer_index` set (py_aep extension mirroring
                the "Choose Layer" option of AE's import dialog), a FOOTAGE
                import of a layered file references that single layer
                instead of the merged/whole document; see also
                `ImportOptions.layer_dimensions` and `py_aep.list_layers`.

        Returns:
            The newly created [FootageItem][] or [CompItem][].

        Raises:
            ValueError: If `import_as` is unsupported for the file, or the
                file extension is not a supported format.
            NotImplementedError: If media-header probing is not implemented
                for the file's format.
            UnsupportedSVGError: If the SVG uses features py_aep cannot
                import.
            UnsupportedAiLayersError: If a layered `.ai`/`.pdf` import is
                requested but the file exposes no PDF Optional Content Groups
                (e.g. saved without PDF compatibility).
            UnsupportedPsdLayersError: If a `.psd`/`.psb` COMP import is
                requested but the file is not a valid Photoshop document.
        """
        if not isinstance(options, ImportOptions):
            raise ValueError(f"Expected ImportOptions, got {type(options).__name__}")

        if options.layer_index is not None:
            if options.import_as != ImportAsType.FOOTAGE:
                raise ValueError(
                    "layer_index applies to ImportAsType.FOOTAGE only; COMP "
                    "imports include every layer"
                )
            if options.sequence:
                raise ValueError("layer_index cannot be combined with sequence")
        elif options.layer_dimensions is not None:
            raise ValueError("layer_dimensions requires layer_index")

        suffix = options.file.suffix.lower()
        if options.layer_styles is not None:
            if suffix not in PSD_COMP_EXTENSIONS:
                raise ValueError(
                    "layer_styles applies to Photoshop (.psd/.psb) imports only"
                )
            if options.import_as == ImportAsType.FOOTAGE:
                if options.layer_index is None:
                    raise ValueError(
                        "layer_styles requires layer_index for a FOOTAGE "
                        'import: a "Merged Layers" whole-document import '
                        "always flattens the styles into the composite"
                    )
                if options.layer_styles == "editable":
                    raise ValueError(
                        "editable layer styles require a COMP import; a "
                        'FOOTAGE import offers "merge" or "ignore"'
                    )
            elif options.layer_styles == "ignore":
                raise ValueError(
                    'a COMP import offers "editable" or "merge" layer '
                    "styles (AE's dialog has no Ignore option there)"
                )
        if options.import_as == ImportAsType.COMP_CROPPED_LAYERS:
            if suffix == ".svg":
                return self._import_svg_cropped(options.file)
            if suffix in PSD_COMP_EXTENSIONS:
                return self._import_psd_layered(
                    options.file,
                    cropped=True,
                    layer_styles=self._resolve_comp_layer_styles(options),
                )
            raise ValueError(
                "import_file supports COMP_CROPPED_LAYERS for SVG and layered "
                f".psd/.psb; {suffix} cropped import is not implemented yet"
            )
        if options.import_as == ImportAsType.COMP:
            if suffix in AI_COMP_EXTENSIONS:
                return self._import_ai_layered(options.file)
            if suffix in EPS_COMP_EXTENSIONS:
                return self._import_eps_comp(options.file)
            if suffix in PSD_COMP_EXTENSIONS:
                return self._import_psd_layered(
                    options.file,
                    layer_styles=self._resolve_comp_layer_styles(options),
                )
            raise ValueError(f"import_file does not support COMP import for {suffix!r}")
        if options.import_as == ImportAsType.PROJECT:
            raise ValueError(
                "import_file does not support PROJECT import (importing an "
                ".aep/.aet, or an AE project embedded in a .mov/.m4a)"
            )
        if options.import_as != ImportAsType.FOOTAGE:
            raise ValueError(
                "import_file supports ImportAsType.FOOTAGE, COMP (layered "
                f".ai/.pdf/.psd/.psb), and COMP_CROPPED_LAYERS (SVG, .psd/.psb), "
                f"got {options.import_as.name}"
            )

        if options.layer_index is not None:
            # Fill unset PSD layer-import choices from the machine's sticky
            # import-dialog preferences, as AE's own importFile does. These
            # prefs are PSD-only: an AI/PDF layer import keeps None (its
            # downstream default), since a PSD "layer" dimension would wrongly
            # trip _from_layer's Layer-Size NotImplementedError for AI/PDF.
            dimensions = options.layer_dimensions
            styles = options.layer_styles
            if suffix in PSD_COMP_EXTENSIONS:
                if styles is None:
                    styles = psd_footage_layer_styles(self._preferences)
                if dimensions is None:
                    dimensions = psd_footage_dimensions(self._preferences)
            source = FileSource._from_layer(
                options.file,
                options.layer_index,
                dimensions=dimensions,
                layer_styles=styles,
            )
        else:
            source = FileSource._from_file(
                options.file,
                sequence=options.sequence,
                force_alphabetical=options.force_alphabetical,
                default_sequence_fps=default_sequence_fps(self._preferences),
                range_start=options.range_start if options.sequence else 0,
                range_end=options.range_end if options.sequence else 0,
            )

        item = FootageItem._new(source, project=self, parent_folder=self.root_folder)
        container = self.root_folder._children_container
        container.append(item._item_list)
        container.extend(item._view_data)
        self.items[item.id] = item
        self.root_folder.items.append(item)
        return item

    def _resolve_comp_layer_styles(self, options: ImportOptions) -> str | None:
        """The COMP-import Layer Options value: the user's explicit choice, or
        the machine's sticky PSD-comp import preference. `None` (no preference,
        or no preferences directory) keeps AE's `editable` dialog default."""
        if options.layer_styles is not None:
            return options.layer_styles
        return psd_comp_layer_styles(self._preferences)

    def _import_svg_cropped(self, file: Path) -> CompItem:
        """Import an SVG as a cropped comp (one shape layer of its art)."""
        from ..svg import read_svg
        from ..svg.build import build_shape_layer_contents

        doc = read_svg(file)
        width = max(1, int(doc.width))
        height = max(1, int(doc.height))
        # AE creates a 1-frame, 30 fps comp named after the file.
        # (add_comp front-inserts the comp to match AE's import ordering.)
        comp = self.root_folder.add_comp(
            file.name, width, height, 1.0, 1.0 / 30.0, 30.0
        )
        layer = comp.add_shape()
        layer.name = file.name
        # Vertices are baked in absolute viewBox coordinates, so an identity
        # layer transform (anchor and position at the origin) maps shape
        # local space 1:1 onto the comp. (AE centres the layer instead, but
        # it stores the shape-layer anchor scaled by comp size, which
        # py_aep does not model; the origin avoids that and renders the
        # same.)
        transform = layer.transform
        cast("Property", transform["ADBE Anchor Point"]).value = [0.0, 0.0, 0.0]
        cast("Property", transform["ADBE Position"]).value = [0.0, 0.0, 0.0]
        contents = cast("PropertyGroup", layer.property("ADBE Root Vectors Group"))
        build_shape_layer_contents(contents, doc.drawables)
        return comp

    def _new_layered_comp(
        self, parent_folder: FolderItem, name: str, width: int, height: int
    ) -> CompItem:
        """Create an import composition (full canvas, AE's default timing)."""
        frames = round(_LAYERED_COMP_DURATION_SECONDS * _LAYERED_COMP_FRAME_RATE)
        comp = parent_folder.add_comp(
            name,
            width,
            height,
            1.0,
            frames / _LAYERED_COMP_FRAME_RATE,
            _LAYERED_COMP_FRAME_RATE,
        )
        # AE gives a layered-import comp shutter phase -90 (unlike a
        # script-created comp, which AE leaves at 0 - as add_comp's skeleton
        # does); so set it only here, on the import path.
        comp.shutter_phase = -90
        return comp

    def _import_layered_comp(
        self,
        file: Path,
        source_format: str,
        layer_specs: list[LayerSpec | LayerGroupSpec],
        info: MediaInfo,
        embedded_profile_name: str | None = None,
    ) -> CompItem:
        """Build the composition shared by every layered-file import.

        Mirrors AE's File > Import as Composition: a `<stem> Layers` folder
        holding one footage item per leaf layer (each referencing the same file
        with its layer selected in the opti) and one nested composition per
        layer group, plus a composition with one layer per top-level spec,
        stacked in document order (the last layer on top, matching AE).

        Args:
            file: The source file every per-layer footage item references.
            source_format: The `sspc` source-format code (`TEXT`, `8BPS`, ...).
            layer_specs: Top-level [LayerSpec][]/[LayerGroupSpec][] nodes, in
                document order (bottom layer first).
            info: The probed media info for `file` (canvas size, alpha, ...).
            embedded_profile_name: Optional ICC profile name for the sources.
        """
        folder = self.root_folder.add_folder(f"{file.stem} Layers")
        comp = self._new_layered_comp(
            self.root_folder, file.stem, info.width, info.height
        )
        self._add_layered_specs(
            comp, folder, layer_specs, file, source_format, info, embedded_profile_name
        )
        # AE stores the `<stem> Layers` folder's Sfdr in the Project-panel
        # alphabetical order, not the document order the items are built in
        # (verified against the grouped_layers / layer_bounds AE fixtures).
        folder._sort_children_by_name()
        # AE places the `<stem> Layers` folder immediately after the comp (before
        # the project's pre-existing items); add_folder appended it, so move it
        # into position to match AE's Fold ordering.
        container = self.root_folder._children_container
        container.pop(index_by_identity(container, folder._item_list))
        comp_idx = index_by_identity(container, comp._item_list)
        container.insert(comp_idx + 1 + len(comp._view_data), folder._item_list)
        return comp

    def _add_layered_specs(
        self,
        comp: CompItem,
        folder: FolderItem,
        specs: list[LayerSpec | LayerGroupSpec],
        file: Path,
        source_format: str,
        info: MediaInfo,
        embedded_profile_name: str | None,
    ) -> None:
        """Add one layer per spec to `comp` (groups become nested comps).

        Leaf footage items and nested group comps both live in `folder`,
        matching AE's flat `<stem> Layers` folder.
        """
        for spec in specs:
            if isinstance(spec, LayerGroupSpec):
                nested = self._new_layered_comp(
                    folder,
                    spec.comp_name if spec.comp_name is not None else spec.name,
                    info.width,
                    info.height,
                )
                self._add_layered_specs(
                    nested,
                    folder,
                    spec.children,
                    file,
                    source_format,
                    info,
                    embedded_profile_name,
                )
                # AE imports a PSD group as a collapsed precomp and leaves the
                # layer name empty (it inherits the nested comp's name), so
                # `name_set` stays off - matching avoids both deltas. A
                # clipping-run precomp instead bakes the base layer's name
                # (still with `name_set` off) and stays uncollapsed.
                group_layer = cast("AVLayer", comp.add(nested))
                if spec.collapsed:
                    group_layer.collapse_transformation = True
                if spec.layer_name is not None:
                    group_layer.name = spec.layer_name
                    group_layer._ldta.name_set = False
                _serialize_import_layer_styles(group_layer, None, file.name)
                continue
            source = FileSource._new(
                file,
                source_format=source_format,
                width=spec.width,
                height=spec.height,
                duration=0.0,
                frame_rate=0.0,
                pixel_aspect=info.pixel_aspect,
                has_alpha=info.has_alpha,
                opti_data=spec.opti_data,
                embedded_profile_name=embedded_profile_name,
                full_frame=spec.full_frame,
                layer_name=spec.name if spec.layer_index is not None else "",
                layer_id=spec.layer_id,
                layer_index=spec.layer_index,
                data_size=spec.data_size,
                reserved_c8=spec.reserved_c8,
            )
            footage = FootageItem._new(source, project=self, parent_folder=folder)
            folder._children_container.append(footage._item_list)
            folder._children_container.extend(footage._view_data)
            self.items[footage.id] = footage
            folder.items.append(footage)
            layer = comp.add(footage)
            layer.name = spec.name
            if spec.transform is not None:
                (anchor_x, anchor_y), (position_x, position_y) = spec.transform
                transform = layer.transform
                cast("Property", transform["ADBE Anchor Point"]).value = [
                    anchor_x,
                    anchor_y,
                    0.0,
                ]
                cast("Property", transform["ADBE Position"]).value = [
                    position_x,
                    position_y,
                    0.0,
                ]
            if spec.is_adjustment:
                cast("AVLayer", layer).adjustment_layer = True
            if spec.preserve_transparency:
                cast("AVLayer", layer).preserve_transparency = True
            if spec.masks:
                # A PSD vector-mask/shape-layer path: AE creates one mask
                # per subpath (psd_vector_mask* fixtures).
                parade = cast("PropertyGroup", layer.property("ADBE Mask Parade"))
                for shape in spec.masks:
                    mask = cast(
                        "MaskPropertyGroup", parade.add_property("ADBE Mask Atom")
                    )
                    cast("Property", mask.property("ADBE Mask Shape")).value = shape
            _serialize_import_layer_styles(layer, spec.styles, file.name)

    def _import_ai_layered(self, file: Path) -> CompItem:
        """Import a layered Illustrator/PDF file as a composition."""
        # Read once: the probe, the ICC scan and the layer scan all consume
        # the same bytes.
        data = file.read_bytes()
        info = probe_media(file, data)
        color_space, profile_name = read_ai_color_info(file, data)
        specs: list[LayerSpec | LayerGroupSpec] = [
            LayerSpec(
                name,
                build_ai_layer_opti_data(info.width, info.height, name, color_space),
                info.width,
                info.height,
                layer_index=index,
                data_size=len(data),
            )
            for index, name in enumerate(read_ai_layers(file, data))
        ]
        return self._import_layered_comp(file, "TEXT", specs, info, profile_name)

    def _import_eps_comp(self, file: Path) -> CompItem:
        """Import an EPS as a single-layer composition.

        EPS is single-stream PostScript with no Optional Content Groups (the
        layer mechanism `read_ai_layers` relies on for `.ai`/`.pdf`), so AE
        rasterizes it to one full-canvas layer. Verified against AE 2026:
        importing `eps.eps` yields a 1-layer comp whose footage carries the
        bare `TEXT` opti (no per-layer name/index/bbox - those stay zero,
        unlike a real AI layer), byte-matched against an AE-resaved import.

        EPS carries no embedded ICC profile (`read_ai_color_info` needs a PDF
        object structure EPS lacks), so the footage is left untagged. AE instead
        tags such footage with the project working space (sRGB by default); that
        is a general color-management-on-import default py_aep does not yet apply
        to any no-embedded-profile import, not an EPS-specific gap.
        """
        info = probe_media(file)
        spec = LayerSpec(
            file.name,
            build_text_opti_data(info.width, info.height),
            info.width,
            info.height,
        )
        return self._import_layered_comp(file, "TEXT", [spec], info, None)

    def _import_psd_layered(
        self,
        file: Path,
        cropped: bool = False,
        layer_styles: str | None = None,
    ) -> CompItem:
        """Import a layered Photoshop file (`.psd`/`.psb`) as a composition.

        Layer groups become nested compositions (recursively); adjustment
        layers are flagged. With `cropped`, each leaf layer is cropped to its
        content box (`COMP_CROPPED_LAYERS`); otherwise the full canvas is kept
        (`COMP`). `layer_styles` is the dialog's Layer Options choice
        (`"editable"`, the default, or `"merge"`; see
        `ImportOptions.layer_styles`).

        A flattened file (no layer records) is imported as a one-layer
        composition of the merged still, matching AE 2026: a `<stem> Layers`
        folder holding one footage item that references the file, and a comp
        with a single full-canvas layer named after the file.
        """
        info = probe_media(file)
        try:
            nodes = read_psd_layers(file)
        except FlattenedPsdError:
            spec = LayerSpec(
                file.name,
                build_psd_flattened_opti_data(
                    info.width, info.height, info.bit_depth, info.channels
                ),
                info.width,
                info.height,
                # AE marks the flattened merged-still layer as not spanning a
                # full frame and caches its actual channel count (both from
                # the flattened_rgb_comp.aep fixture).
                full_frame=False,
                data_size=(
                    info.width * info.height * info.channels * (info.bit_depth // 8)
                ),
            )
            return self._import_layered_comp(file, "8BPS", [spec], info)
        resolved_styles = "editable" if layer_styles is None else layer_styles
        specs = self._psd_layer_specs(
            nodes,
            file,
            info.width,
            info.height,
            info.bit_depth,
            info.layer_count,
            cropped,
            resolved_styles,
            # The global light is a document constant; read it once here
            # rather than per recursion level (one file scan per group).
            read_global_light(file) if resolved_styles == "editable" else None,
        )
        return self._import_layered_comp(file, "8BPS", specs, info)

    def _psd_layer_specs(
        self,
        nodes: list[Any],
        file: Path,
        canvas_w: int,
        canvas_h: int,
        bit_depth: int,
        layer_count: int,
        cropped: bool,
        layer_styles: str,
        global_light: tuple[float, float] | None,
        clip_counter: Iterator[int] | None = None,
        group_clipping: bool = True,
    ) -> list[LayerSpec | LayerGroupSpec]:
        """Convert a PSD layer tree into import specs (recursively).

        `clip_counter` numbers the clipping-run precomps document-wide
        (AE names them `"<stem> (n)"`); `group_clipping=False` disables
        run detection while building a run's own children.
        """
        if clip_counter is None:
            clip_counter = count(1)
        reserved_c8 = PSD_LAYER_STYLES_C8[layer_styles]
        specs: list[LayerSpec | LayerGroupSpec] = []
        index = 0
        while index < len(nodes):
            node = nodes[index]
            index += 1
            if isinstance(node, PsdGroup):
                if has_enabled_styles(node):
                    # Photoshop allows styles on a group; applying them to
                    # the nested-comp layer is not supported yet.
                    warnings.warn(
                        f"{file.name}: styles on layer group {node.name!r} "
                        "were ignored - importing group layer styles is "
                        "not supported",
                        stacklevel=2,
                    )
                specs.append(
                    LayerGroupSpec(
                        node.name,
                        self._psd_layer_specs(
                            node.children,
                            file,
                            canvas_w,
                            canvas_h,
                            bit_depth,
                            layer_count,
                            cropped,
                            layer_styles,
                            global_light,
                            clip_counter,
                        ),
                    )
                )
                continue
            if group_clipping and not node.clipped:
                # A clipping run (this base + the clipped layers above it)
                # is auto-precomposed by AE: nested comp "<stem> (n)", the
                # base's name baked on the uncollapsed parent layer, and
                # preserve-transparency on the clipped members
                # (psd_clipping_mask fixture).
                run = [node]
                while (
                    index < len(nodes)
                    and isinstance(nodes[index], PsdLayer)
                    and nodes[index].clipped
                ):
                    run.append(nodes[index])
                    index += 1
                if len(run) > 1:
                    specs.append(
                        LayerGroupSpec(
                            node.name,
                            self._psd_layer_specs(
                                run,
                                file,
                                canvas_w,
                                canvas_h,
                                bit_depth,
                                layer_count,
                                cropped,
                                layer_styles,
                                global_light,
                                clip_counter,
                                group_clipping=False,
                            ),
                            comp_name=f"{file.stem} ({next(clip_counter)})",
                            layer_name=node.name,
                            collapsed=False,
                        )
                    )
                    continue
            if cropped and layer_styles == "merge" and has_enabled_styles(node):
                # Merging styles expands the rasterized content box, which
                # sets the cropped footage size and the layer transform here.
                # AE derives the expansion with its style renderer; py_aep
                # cannot (see docs/limitations.md).
                raise NotImplementedError(
                    f"layer {node.name!r} of {file.name} has layer styles: "
                    "merging them expands the rasterized bounds, so a "
                    "COMP_CROPPED_LAYERS import cannot size its layers; "
                    'import as COMP or pass layer_styles="editable"'
                )
            styles = (
                parse_layer_styles(node, global_light)
                if global_light is not None
                else None
            )
            opti_data = build_psd_layer_opti_data(
                canvas_w,
                canvas_h,
                bit_depth,
                layer_count,
                node.record_index,
                node.layer_id,
                node.name,
                node.bounds,
                node.is_adjustment,
            )
            left, top, right, bottom = node.bounds
            data_size = (
                max(right - left, 0) * max(bottom - top, 0) * 4 * (bit_depth // 8)
            )
            masks: tuple[Shape, ...] = ()
            if node.vector_mask is not None:
                masks = tuple(parse_vector_mask(node.vector_mask, canvas_w, canvas_h))
            if cropped:
                # An empty layer (degenerate content box) is kept at FULL
                # CANVAS size, centered - not cropped to 1x1 (probed AE 2026:
                # psd_clipping_mask "Layer 1" and grouped_layers "hue/sat adj"
                # both bounds (0,0,0,0) -> full-canvas, centered).
                if right <= left or bottom <= top:
                    box = (0, 0, canvas_w, canvas_h)
                else:
                    box = (left, top, right, bottom)
                b_left, b_top, b_right, b_bottom = box
                crop_w = b_right - b_left
                crop_h = b_bottom - b_top
                # Anchor at the cropped footage centre; position the layer so the
                # content sits where it was in the document (AE 2026 verified).
                transform = (
                    (crop_w / 2, crop_h / 2),
                    ((b_left + b_right) / 2, (b_top + b_bottom) / 2),
                )
                # Mask vertices are canvas coordinates; a cropped layer's
                # source origin is the content box.
                masks = tuple(
                    Shape(
                        vertices=[[x - b_left, y - b_top] for x, y in shape.vertices],
                        in_tangents=shape.in_tangents,
                        out_tangents=shape.out_tangents,
                        closed=shape.closed,
                    )
                    for shape in masks
                )
                specs.append(
                    LayerSpec(
                        node.name,
                        opti_data,
                        crop_w,
                        crop_h,
                        transform,
                        full_frame=False,
                        is_adjustment=node.is_adjustment,
                        layer_id=node.layer_id,
                        layer_index=node.record_index,
                        # Empty layers have no pixels: data_size stays 0 (from
                        # the real bounds), even though the layer is full-canvas.
                        data_size=data_size,
                        reserved_c8=reserved_c8,
                        styles=styles,
                        masks=masks,
                        preserve_transparency=not group_clipping and node.clipped,
                    )
                )
            else:
                specs.append(
                    LayerSpec(
                        node.name,
                        opti_data,
                        canvas_w,
                        canvas_h,
                        is_adjustment=node.is_adjustment,
                        layer_id=node.layer_id,
                        layer_index=node.record_index,
                        data_size=data_size,
                        reserved_c8=reserved_c8,
                        styles=styles,
                        masks=masks,
                        preserve_transparency=not group_clipping and node.clipped,
                    )
                )
        return specs

    def _iter_text_source_properties(self) -> Iterator[tuple[Layer, Property]]:
        """Yield `(layer, source_text)` for every text layer in the project."""
        for comp in self.compositions:
            for layer in comp.layers:
                group = layer.text
                if group is None:
                    continue
                source_text = group["ADBE Text Document"]
                if isinstance(source_text, Property):
                    yield layer, source_text

    @property
    def used_fonts(self) -> list[dict[str, Any]]:
        """Returns an Array of Objects containing references to used fonts
        and the Text Layers and times on which they appear in the current
        Project. Read-only.

        Each entry is `{"font": FontObject, "used_at": [...]}`, where every
        `used_at` record is `{"layer_id": int, "layer_time": float}` - one
        per source-text keyframe whose document references that font (a
        single record at time 0 for an unanimated document). A document
        with several fonts contributes one record per distinct font.
        Entries are sorted by PostScript name, matching After Effects.

        Note:
            `layer_time` is in LAYER time, not composition time - After
            Effects names it `layerTimeD` because `Source Text`'s
            `value_at_time` expects layer time, unlike other properties.
        """
        records: dict[
            tuple[str, str | None, tuple[float, ...] | None],
            tuple[FontObject, list[dict[str, float]]],
        ] = {}
        for layer, source_text in self._iter_text_source_properties():
            if source_text.keyframes:
                entries = [
                    (cast("TextDocument", kf.value), kf.time - layer.start_time)
                    for kf in source_text.keyframes
                ]
            else:
                entries = [(cast("TextDocument", source_text.value), 0.0)]
            for doc, layer_time in entries:
                if doc is None:
                    continue
                for font in doc._used_font_objects():
                    vector = font.design_vector
                    key = (
                        font.post_script_name,
                        font.version,
                        tuple(vector) if vector is not None else None,
                    )
                    record = records.get(key)
                    if record is None:
                        record = (font, [])
                        records[key] = record
                    record[1].append({"layer_id": layer.id, "layer_time": layer_time})
        return [
            {"font": font, "used_at": used_at}
            for _key, (font, used_at) in sorted(
                records.items(), key=lambda item: item[0][0]
            )
        ]

    def replace_font(
        self,
        from_font: FontObject | str,
        to_font: FontObject | str,
        no_font_locking: bool = False,
    ) -> bool:
        """Replace all usages of `from_font` with `to_font`.

        A complete and precise replacement, even on text documents with
        mixed styling: the character ranges `from_font` was applied to are
        preserved, and every source-text keyframe of every text layer is
        covered. This operation is not undoable.

        Each font may be given as a [FontObject][] (e.g. from
        [used_fonts][Project.used_fonts]) or as a PostScript name.

        Args:
            from_font: Font to be replaced.
            to_font: Font to replace it with.
            no_font_locking: Accepted for ExtendScript parity and ignored.
                After Effects uses it to suppress the fallback font it
                picks when `to_font` lacks glyphs for the text; that
                fallback is a runtime font-engine decision py_aep does not
                make, so py_aep always performs the direct replacement
                (i.e. it behaves as if this were `True`).

        Returns:
            `True` if at least one layer was changed.
        """
        validate_bool(no_font_locking)
        from_name = _font_post_script_name(from_font)
        to_name = _font_post_script_name(to_font)
        if from_name == to_name:
            return False

        changed = False
        for _layer, source_text in self._iter_text_source_properties():
            docs = [cast("TextDocument", kf.value) for kf in source_text.keyframes]
            if not docs:
                docs = [cast("TextDocument", source_text.value)]
            docs = [doc for doc in docs if doc is not None]
            if docs and _replace_layer_font(docs, from_name, to_name):
                changed = True
        return changed

    def auto_fix_expressions(self, old_text: str, new_text: str) -> None:
        """Automatically replaces text found in broken expressions in the
        project, if the new text causes the expression to evaluate without
        errors.

        py_aep cannot evaluate expressions, and After Effects' actual gate
        (is the expression currently erroring) is runtime state that is not
        stored in the project file. Instead, py_aep replaces the quoted
        forms `"old_text"` and `'old_text'` in EVERY enabled expression of
        the project. Divergence from After Effects (probed AE 2026): an
        expression that evaluates cleanly but contains the quoted text is
        rewritten here, while After Effects leaves it untouched. Matching
        After Effects: disabled expressions are never modified, both quote
        styles are fixed, and quoted occurrences inside comments of a
        rewritten expression are replaced too.

        Args:
            old_text: The text to replace.
            new_text: The new text.
        """
        validate_string(old_text)
        validate_string(new_text)
        if not old_text:
            return
        old_double = f'"{old_text}"'
        new_double = f'"{new_text}"'
        old_single = f"'{old_text}'"
        new_single = f"'{new_text}'"

        def walk(group: PropertyGroup) -> Iterator[Property]:
            for child in group:
                if isinstance(child, PropertyGroup):
                    yield from walk(child)
                elif isinstance(child, Property):
                    yield child

        for comp in self.compositions:
            for layer in comp.layers:
                for prop in walk(layer):
                    expression = prop.expression
                    if not expression or not prop.expression_enabled:
                        continue
                    fixed = expression.replace(old_double, new_double).replace(
                        old_single, new_single
                    )
                    if fixed != expression:
                        prop.expression = fixed

    def remove_unused_footage(self) -> int:
        """Remove footage items that are not used in any composition.

        Same as the File > Remove Unused Footage command.

        Returns:
            The total number of footage items removed.
        """
        removed = 0
        for footage in self.footages:
            if not footage.used_in:
                footage.remove()
                removed += 1
        return removed

    def reduce_project(self, items_to_keep: list[Item]) -> int:
        """Remove all items except those specified and the items they use.

        Same as the File > Reduce Project command. For each kept composition,
        the items it uses (and their dependencies, recursively) are also kept.
        The folders containing kept items are kept as well.

        Args:
            items_to_keep: The items to keep in the project.

        Returns:
            The total number of items removed.
        """
        if not all(isinstance(item, Item) for item in items_to_keep):
            raise ValueError("All items_to_keep must be Item instances")
        keep_ids: set[int] = {0}
        queue = list(items_to_keep)
        while queue:
            item = queue.pop()
            if item.id in keep_ids:
                continue
            keep_ids.add(item.id)
            parent = item.parent_folder
            while parent is not None and parent.id not in keep_ids:
                keep_ids.add(parent.id)
                parent = parent.parent_folder
            if isinstance(item, CompItem):
                for source_id in item._source_ids_for_linking():
                    source = self.items.get(source_id)
                    if source is not None:
                        queue.append(source)
        removed = 0
        for item_id in list(self.items):
            if item_id in keep_ids or item_id not in self.items:
                continue
            self.items[item_id].remove()
            removed += 1
        return removed

    def consolidate_footage(self) -> int:
        """Merge duplicate footage items that share the same source.

        Same as the File > Consolidate All Footage command. Footage items
        whose sources are identical (same file and interpretation, or same
        solid characteristics) are merged: layers referencing a duplicate are
        retargeted to the kept item, and the duplicate is removed.

        Returns:
            The total number of footage items removed.
        """
        groups: dict[object, list[FootageItem]] = {}
        for footage in self.footages:
            key = footage._consolidation_key()
            if key is None:
                continue
            groups.setdefault(key, []).append(footage)
        removed = 0
        for duplicates in groups.values():
            if len(duplicates) < 2:
                continue
            kept = duplicates[0]
            for dup in duplicates[1:]:
                for comp in dup.used_in:
                    for layer in comp.av_layers:
                        if layer._source_id == dup.id:
                            layer._source_id = kept.id
                            # Refresh the layer's cached source so a prior
                            # `layer.source` access doesn't keep returning
                            # the removed duplicate.
                            layer._source = kept
                            kept._used_in.add(comp)
                dup.remove()
                removed += 1
        return removed

    def save(self, path: os.PathLike[str]) -> None:
        """
        Save the project to a new .aep file at the given path.

        Warning:
            This is highly experimental for now.

        Raises:
            FileExistsError: If `path` already exists; overwriting is not
                allowed while saving is experimental.
        """
        validate_path_does_not_exist(path)
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        # Write to a sibling temp file then rename, so a serialization
        # error can never leave a truncated .aep at the target path.
        tmp_path = path_obj.with_name(path_obj.name + ".tmp")
        try:
            with tmp_path.open("wb") as f:
                write_aep(f, self._rifx, self._xmp)
        except BaseException:
            if tmp_path.exists():  # missing_ok needs Python 3.8
                tmp_path.unlink()
            raise
        os.replace(tmp_path, path_obj)
        self._file = str(path)

    def _require_prefs_dir(self, label: str) -> Path:
        """Return the AE preferences directory or raise if none was given."""
        if self._ae_preferences_dir is None:
            raise ValueError(
                "No 'ae_preferences_dir' provided to parse(); "
                f"{label} templates are required for adding items "
                "to the render queue. Pass ae_preferences_dir pointing to "
                "the AE preferences directory (e.g. "
                "C:/Users/<user>/AppData/Roaming/Adobe/After Effects/26.0)"
            )
        return self._ae_preferences_dir

    def _get_render_templates(self) -> list[RenderSettingsItem]:
        """Lazily parse render settings templates from AE preferences.

        Raises:
            ValueError: If no preferences directory was provided to
                `parse()`. Render settings templates are required for
                adding items to the render queue.
        """
        if self._render_templates_cache is not None:
            return self._render_templates_cache

        from ..parsers.templates import parse_render_templates

        prefs_dir = self._require_prefs_dir("render settings")
        templates, default_index = parse_render_templates(prefs_dir)
        self._default_render_template_index = default_index

        self._render_templates_cache = templates
        return templates

    def _get_output_templates(self) -> list[OutputModuleTemplate]:
        """Lazily parse output module templates from AE preferences.

        Returns a list of [OutputModuleTemplate][] objects.

        Raises:
            ValueError: If no preferences directory was provided to
                `parse()`. Output module templates are required for
                adding items to the render queue.
        """
        if self._output_templates_cache is not None:
            return self._output_templates_cache

        from ..parsers.templates import parse_output_templates

        prefs_dir = self._require_prefs_dir("output module")
        templates, _ = parse_output_templates(prefs_dir)

        self._output_templates_cache = templates
        return self._output_templates_cache

    def _allocate_id(self) -> int:
        """Return the next unique id for a new item or layer.

        After Effects draws item ids AND layer ids (including viewer
        pseudo-layers in DLay/SLay/CLay/SecL lists) from one project-wide
        counter persisted in `head.next_item_id`, and TRUSTS that counter
        on open without rescanning - probed in AE 2026: opening a file
        whose counter sits below the live ids makes AE itself mint
        duplicate layer ids. So there is a single allocator, reconciled
        once against every live id, then
        strictly counter-driven. ID 0 is reserved for the root folder.
        """
        if not self._id_counter_reconciled:
            max_layer_id = max(
                (
                    cast("LdtaChunk", ldta).layer_id
                    for comp in self.compositions
                    for ldta in recursive_find(
                        comp._item_list.chunks, chunk_type="ldta"
                    )
                ),
                default=0,
            )
            max_item_id = max(self.items.keys(), default=0)
            floor = max(max_layer_id, max_item_id) + 1
            if self._head.next_item_id < floor:
                self._head.next_item_id = floor
            self._id_counter_reconciled = True
        new_id = self._head.next_item_id
        self._head.next_item_id = new_id + 1
        return new_id

    @property
    def _solids_folder_name(self) -> str:
        """The solids folder name stored in the project's root `sfnm` chunk.

        AE stamps the "New Project Solids Folder" preference into `sfnm`
        when the project is created and uses the stored name from then on.
        """
        try:
            sfnm = find_by_list_type(chunks=self._rifx.chunks, list_type="sfnm")
            name = find_by_type(chunks=sfnm.chunks, chunk_type="Utf8").value  # type: ignore[attr-defined]
        except ChunkNotFoundError:
            return "Solids"
        return name or "Solids"

    @property
    def _solids_folder(self) -> FolderItem:
        """Return the Solids folder, creating one if it doesn't exist."""
        name = self._solids_folder_name
        for folder in self.root_folder.folders:
            if folder.name == name:
                return folder
        return self.root_folder.add_folder(name)

    _CMS_DEFAULTS: ClassVar[dict[str, int | str]] = {
        "colorManagementSystem": 0,
        "lutInterpolationMethod": 0,
        "ocioConfigurationFile": "",
    }

    def _get_cms_settings(self) -> dict[str, int | str]:
        """Return the color profile settings dict."""
        if self._cms_utf8 is not None:
            cms_data: dict[str, int | str] = json.loads(self._cms_utf8.value)
            return {**self._CMS_DEFAULTS, **cms_data}
        return dict(self._CMS_DEFAULTS)

    def _update_cms_setting(self, key: str, value: int | str) -> None:
        """Update a single key in the CMS settings JSON chunk."""
        if self._cms_utf8 is not None:
            data = json.loads(self._cms_utf8.value)
            data[key] = value
            self._cms_utf8.value = json.dumps(data)
        else:
            data = dict(self._CMS_DEFAULTS)
            data[key] = value
            chunk = Utf8Chunk(value=json.dumps(data))
            self._rifx.chunks.append(chunk)
            self._cms_utf8 = chunk


def _get_effect_names(root_chunks: list[Chunk]) -> list[str]:
    """Get the list of effect names used in the project."""
    pefl_chunk = find_by_list_type(chunks=root_chunks, list_type="Pefl")
    pjef_chunks = filter_by_type(chunks=pefl_chunk.chunks, chunk_type="pjef")
    return [cast("Utf8Chunk", chunk).value for chunk in pjef_chunks]


# tdb4 canon AE writes on materialized Layer Styles leaves, keyed by leaf
# suffix or full match name: (value_hint_type, value_hint_flag, cvot_flags,
# type_flags, property_category, pad2a, vector), None leaving the
# materialized value. Byte-diffed from the psd_layer_styles*.aep fixtures;
# stamped after the value write because the static-state tdb4 templates run
# there. The enum/angle/scalar classification is derived from the synthesis
# canon tables so the two mechanisms cannot drift; "gradient" is
# scalar-stamped here although `_style_leaf_canon` leaves the spec
# uncanonized, the 2D point rows come from the psd_styles_offset_phase
# fixture, and the blend-options leaves are keyed by full match name.
_STYLE_TDB4_ENUM: Any = (0x0001, None, 0x04, 0x04, 0x04, None, None, False)
_STYLE_TDB4_SCALAR: Any = (0xFFFF, None, None, None, None, None, None, False)
_STYLE_TDB4_ANGLE: Any = (0xFFFF, 0xFF, 0xFF, 0x04, 0x06, None, None, False)
_STYLE_TDB4_TOGGLE: Any = (0xFFFF, None, 0x04, 0x04, 0x04, None, None, False)
_STYLE_TDB4_POINT: Any = (0xFFFF, 0xFF, 0xFF, 0x04, 0x06, 3, False, True)

# The spatial-block epsilon AE writes on the 2D point style leaves (exact
# double 0x3D9B7CDFD9D7BDBC, both leaves and layers of the
# psd_styles_offset_phase fixture; ordinary spatial properties carry 1e-4).
_STYLE_POINT_EPSILON = float.fromhex("0x1.b7cdfd9d7bdbcp-38")
_STYLE_TDB4_CANON: dict[str, Any] = {
    **dict.fromkeys(_STYLE_ENUM_SUFFIXES, _STYLE_TDB4_ENUM),
    **dict.fromkeys(_STYLE_ANGLE_SUFFIXES, _STYLE_TDB4_ANGLE),
    **dict.fromkeys(_STYLE_HINT_BOUNDS, _STYLE_TDB4_SCALAR),
    **{
        name.rsplit("/", 1)[-1]: _STYLE_TDB4_SCALAR
        for name in _STYLE_HINT_BOUNDS_EXCEPTIONS
    },
    "gradient": _STYLE_TDB4_SCALAR,
    "offset": _STYLE_TDB4_POINT,
    "phase": _STYLE_TDB4_POINT,
    "ADBE Global Angle2": (0x0002, None, None, None, None, None, None, False),
    "ADBE Global Altitude2": (0x0002, None, None, None, None, None, None, False),
    "ADBE Layer Fill Opacity2": (0xFFFF, None, None, 0x04, 0x08, None, None, False),
    "ADBE R Channel Blend": _STYLE_TDB4_TOGGLE,
    "ADBE G Channel Blend": _STYLE_TDB4_TOGGLE,
    "ADBE B Channel Blend": _STYLE_TDB4_TOGGLE,
    "ADBE Blend Interior": _STYLE_TDB4_TOGGLE,
}


def _stamp_style_tdb4(
    leaf: Property, match_name: str, timebase: int, point_aspect: float
) -> None:
    """Apply the AE tdb4 canon to a just-written Layer Styles leaf."""
    tdb4 = leaf._tdb4
    if tdb4 is None:
        return
    canon = _STYLE_TDB4_CANON.get(match_name) or _STYLE_TDB4_CANON.get(
        match_name.rsplit("/", 1)[-1]
    )
    if canon is None:
        return
    hint, hint_flag, cvot, type_flags, category, pad2a, vector, spatial = canon
    if hint is not None:
        tdb4._value_hint_type = hint
    if hint_flag is not None:
        tdb4._value_hint_flag = hint_flag
    if cvot is not None:
        tdb4._cvot_flags = cvot
    if type_flags is not None:
        tdb4._type_flags = type_flags
    if category is not None:
        tdb4._property_category = category
    if pad2a is not None:
        tdb4._pad2a = pad2a
    if vector is not None:
        tdb4.vector = vector
    if spatial:
        # AE fills the spatial block on the 2D point leaves: marker + flags
        # 0x0F, its point epsilon, and the LAYER's display aspect
        # (source_width * PAR / source_height; 1.28 in the fixture).
        tdb4._spatial_marker = True
        tdb4._spatial_static_flags = 0x0F
        tdb4._unknown_float_0 = _STYLE_POINT_EPSILON
        tdb4.pixel_aspect = point_aspect
    tdb4._time_base = timebase


# AE default values per Layer Styles leaf match name. Editable imports
# write a parameter leaf only when its value differs from these (AE 2026);
# the synthesis tables are the byte-verified source, and only the Layer
# Styles + Blend Options tables can carry keys the resolver emits.
_STYLE_SPEC_DEFAULTS: dict[str, Any] = {
    spec.match_name: spec.value
    for spec_list in _LAYER_STYLE_CHILD_SPECS.values()
    for spec in spec_list
    if spec.value is not None
}
_STYLE_SPEC_DEFAULTS.update(
    {
        spec.match_name: spec.value
        for spec in (*_BLEND_OPTIONS_SPECS, *_ADV_BLEND_SPECS)
        if isinstance(spec, PropSpec) and spec.value is not None
    }
)


def _style_leaf_map(group: PropertyGroup) -> dict[str, Property]:
    """Map of match name -> leaf under `group`, first-in-tree-order."""
    leaves: dict[str, Property] = {}
    for child in group.properties:
        if isinstance(child, PropertyGroup):
            for name, leaf in _style_leaf_map(child).items():
                leaves.setdefault(name, leaf)
        elif child.match_name not in leaves:
            leaves[child.match_name] = cast("Property", child)
    return leaves


def _serialize_import_layer_styles(
    layer: Layer, styles: PsdLayerStyles | None, source_name: str
) -> None:
    """Serialize a comp layer's `ADBE Layer Styles` subtree like AE's imports.

    AE writes the container, Blend Options (with its Advanced group) and the
    ten style groups as real chunks on EVERY layer a layered-file import
    creates (all modes, all formats - the `psd_layer_styles*`, `psd_comp`,
    `ai_comp` and `grouped_layers_comp` fixtures). With `styles`, the present
    styles are enabled and their non-default parameter values written; the
    `tdsb` enable bytes follow AE exactly (styled: container/Blend Options
    0x01, enabled style 0x01, absent style 0x02; plain skeleton: 0x03 and
    0x02 - functional bits, fixture-pinned).
    """
    container = cast("PropertyGroup", layer["ADBE Layer Styles"])
    # AE enables the container + Blend Options chain when any style is
    # enabled OR the layer carries blend-options data (a Photoshop Fill
    # slider away from 100% enables the chain with zero styles - the
    # psd_fill_opacity fixture).
    styled = styles is not None and bool(styles.enabled or styles.blend_options)
    container_flags = 1 if styled else 3
    container._ensure_materialized()
    assert container._tdsb is not None
    container._tdsb._enable_flags = container_flags
    # The synthesis pass stamped derived `enabled` overrides while every
    # group was still synthetic-disabled; refresh them to the written state
    # (ExtendScript semantics: container/Blend Options = any style enabled).
    container.__dict__["enabled"] = styled
    for child in container.properties:
        if not isinstance(child, PropertyGroup):
            continue
        child._ensure_materialized()
        assert child._tdsb is not None
        if child.match_name == "ADBE Blend Options Group":
            child._tdsb._enable_flags = container_flags
            child.__dict__["enabled"] = styled
            for sub in child.properties:
                if isinstance(sub, PropertyGroup):
                    sub._ensure_materialized()
                    assert sub._tdsb is not None
                    # AE writes the Advanced Blending subgroup enabled on
                    # EVERY import, plain skeletons included (pinned by the
                    # psd_fill_opacity/psd_layer_styles/ai_comp fixtures).
                    sub._tdsb._enable_flags = 1
        else:
            prefix = child.match_name.split("/")[0]
            if styles is not None and prefix in styles.enabled:
                flags = 1
            elif styles is not None and prefix in styles.disabled:
                # Present-but-unchecked style: parameters imported, distinct
                # enable byte 0x00 (psd_fill_opacity fixture).
                flags = 0
            else:
                flags = 2
            child._tdsb._enable_flags = flags
            child.__dict__.pop("enabled", None)
    if styles is None:
        return
    for prefix in styles.dropped:
        warnings.warn(
            f"{source_name}: layer {layer.name!r} style {prefix!r} was "
            "imported as disabled - After Effects drops styles with "
            "multiple instances or unrepresentable content, and py_aep "
            "matches its output",
            stacklevel=2,
        )
    if not styles.values:
        return
    timebase = layer.containing_comp._cdta.internal_timebase
    source = cast("AVItem", layer.source)
    point_aspect = source.width * source.pixel_aspect / source.height
    leaves = _style_leaf_map(container)
    for match_name, value in styles.values.items():
        if _values_equal(value, _STYLE_SPEC_DEFAULTS.get(match_name)):
            continue
        leaf = leaves.get(match_name)
        if leaf is None:
            continue
        leaf.value = value
        if isinstance(value, Gradient) and leaf._tdb4 is not None:
            # AE's style gradient tdb4 is vector-typed (the NO_VALUE-seeded
            # spec builds a bare one).
            leaf._tdb4.vector = True
        _stamp_style_tdb4(leaf, match_name, timebase, point_aspect)
