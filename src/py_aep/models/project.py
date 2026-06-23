from __future__ import annotations

import json
import os
import uuid
import xml.etree.ElementTree as ET
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
from ..binary.item_chunks import HeadChunk, NhedChunk, NnhdChunk
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
    filter_by_type,
    find_by_list_type,
    index_by_identity,
    recursive_find,
    toggle_flag_chunk,
)
from ..color.envelope import (
    build_icc_envelope,
    build_ocio_colorspace_envelope,
    build_ocio_display_envelope,
)
from ..color.icc import IccProfileLibrary
from ..color.ocio import list_config_color_spaces, resolve_ocio_config
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
    TimeDisplayType,
)
from ..enums.mappings import adobe_color_profile_names
from ..resolvers.ai_layers import (
    read_ai_color_info,
    read_ai_layers,
)
from ..resolvers.media_probe import probe_media
from ..resolvers.psd_layers import FlattenedPsdError, PsdGroup, read_psd_layers
from ..synthesis.layer import LayerGroupSpec, LayerSpec
from .descriptors import ChunkField
from .import_options import ImportOptions
from .items.composition import CompItem
from .items.folder import FolderItem
from .items.footage import FootageItem
from .items.item import Item
from .renderqueue.render_queue import RenderQueue
from .sources.file import FileSource
from .validators import (
    _validate_number,
    validate_enum,
    validate_one_of,
    validate_path,
    validate_path_does_not_exist,
    validate_path_exists,
    validate_string,
)

if TYPE_CHECKING:
    from typing import ClassVar, Iterator

    from ..binary.layer_chunks import LdtaChunk
    from ..binary.render_chunks import RenderSettingsItem
    from ..parsers.templates import OutputModuleTemplate
    from ..resolvers.media_probe import MediaInfo
    from .layers.av_layer import AVLayer
    from .layers.layer import Layer
    from .properties.property import Property
    from .properties.property_group import PropertyGroup


_validate_expression_engine = validate_one_of(("extendscript", "javascript-1.0"))

# AE's default new-composition import timing for a layered file: a 30-second
# duration rounded to whole frames at the default frame rate. These come from
# After Effects preferences (not the file), so they reproduce AE's factory
# default and may differ from a given install (the probe machine used 29.97).
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

    frames_use_feet_frames = ChunkField[bool](
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

    transparency_grid_thumbnails = ChunkField[bool](
        "_nnhd",
        "transparency_grid_thumbnails",
        post_set=lambda obj: obj._sync_nhed_field("transparency_grid_thumbnails"),
    )
    """When `True`, thumbnail views use the transparency checkerboard
    pattern. Read / Write."""

    revision = ChunkField[int]("_head", "file_revision")
    """The current revision of the project. Every user action increases the
    revision number by one. A new project starts at revision 1. Read / Write.

    Note:
        This attribute is read-only in ExtendScript.
    """

    compensate_for_scene_referred_profiles = ChunkField[bool](
        "_acer", "value", transform=bool, reverse=int, min_version=16
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

        self._max_layer_id = -1  # lazily computed on first allocation
        self._ae_preferences_dir = ae_preferences_dir
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
    def _new(cls, version: str, ae_preferences_dir: Path | None = None) -> Project:
        """Build a new, empty project (mirrors AE's File > New Project).

        Constructs the minimal root chunk skeleton AE accepts - the large
        workspace blobs AE regenerates on open (`LSIf/AFsi`, `PTRE/ftwd`)
        are omitted - stamps `version` into the head chunk, and wires the
        model the same way `parse_project` does. `ae_preferences_dir` is
        stored for render-queue template lookup. See [Application][] and
        `py_aep.new`.
        """
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
        acer = U1Chunk(chunk_type="acer", value=1)
        adfr = F8Chunk(chunk_type="adfr", value=48000.0)
        dwga = DwgaChunk(working_gamma_selector=1)
        gpug_utf8 = Utf8Chunk(value=str(uuid.uuid4()))
        fold = ListChunk(list_type="Fold", chunks=[FdtaChunk()])

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
                chunks=[Utf8Chunk(value="Solids"), U4Chunk(chunk_type="sfid")],
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
        toggle_flag_chunk(self._rifx, "lnrb", value)

    @property
    def linearize_working_space(self) -> bool:
        """When True, the working color space is linearized for blending
        operations. Read / Write."""
        return any(c.chunk_type == "lnrp" for c in self._root_chunks)

    @linearize_working_space.setter
    @requires_version(16)
    def linearize_working_space(self, value: bool) -> None:
        toggle_flag_chunk(self._rifx, "lnrp", value)

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

        In OCIO mode, assigning an OCIO color-space name rewrites the embedded
        profile JSON (AE identifies it by name, no ICC data). In Adobe CMS mode,
        the matching ICC profile is discovered on disk (see [icc_profile_dirs][])
        and embedded; `ColorProfileNotFoundError` is raised if it is not
        installed.
        """
        if self._ws_utf8 is not None:
            data = json.loads(self._ws_utf8.value)
            return str(data.get("baseColorProfile", {}).get("colorProfileName", "None"))
        if not any(c.chunk_type == "pcms" for c in self._root_chunks):
            return "sRGB IEC61966-2.1"
        return "None"

    @working_space.setter
    def working_space(self, value: str) -> None:
        validate_string(value)
        if self.color_management_system == ColorManagementSystem.OCIO:
            self._validate_ocio_color_space(value)
            envelope = build_ocio_colorspace_envelope(value)
        else:
            # bytes_for already raises ColorProfileNotFoundError for an
            # unknown Adobe profile name, so no separate name check is needed.
            envelope = build_icc_envelope(value, self._icc_lib().bytes_for(value))
        self._ws_utf8 = self._rewrite_color_profile("PwCs", envelope)

    def _validate_ocio_color_space(self, name: str) -> None:
        """Reject an OCIO color-space name absent from the active config.

        `list_color_profiles()` returns `[]` when the config cannot be located
        or read; in that case skip the check rather than block a name that
        cannot be verified.
        """
        available = self.list_color_profiles()
        if available and name not in available:
            raise ValueError(
                f"{name!r} is not an active color space in the current OCIO "
                f"configuration ({self.ocio_configuration_file!r}). Call "
                "Project.list_color_profiles() to see the valid names."
            )

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
            data = json.loads(self._dcs_utf8.value)
            return str(data.get("baseColorProfile", {}).get("colorProfileName", "None"))
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

        Mirrors ExtendScript `app.project.listColorProfiles()`: the names valid
        for [working_space][] (and, in Adobe mode, [media_color_space][
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
                `COMP_CROPPED_LAYERS` are supported.

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

        suffix = options.file.suffix.lower()
        if options.import_as == ImportAsType.COMP_CROPPED_LAYERS:
            if suffix == ".svg":
                return self._import_svg_cropped(options.file)
            if suffix in PSD_COMP_EXTENSIONS:
                return self._import_psd_layered(options.file, cropped=True)
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
                return self._import_psd_layered(options.file)
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

        source = FileSource._from_file(
            options.file,
            sequence=options.sequence,
            force_alphabetical=options.force_alphabetical,
        )

        item = FootageItem._new(source, project=self, parent_folder=self.root_folder)
        container = self.root_folder._children_container
        container.append(item._item_list)
        container.extend(item._view_data)
        self.items[item.id] = item
        self.root_folder.items.append(item)
        return item

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
                    folder, spec.name, info.width, info.height
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
                # `name_set` stays off - matching avoids both deltas.
                cast("AVLayer", comp.add(nested)).collapse_transformation = True
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

    def _import_ai_layered(self, file: Path) -> CompItem:
        """Import a layered Illustrator/PDF file as a composition."""
        info = probe_media(file)
        color_space, profile_name = read_ai_color_info(file)
        specs: list[LayerSpec | LayerGroupSpec] = [
            LayerSpec(
                name,
                build_ai_layer_opti_data(info.width, info.height, name, color_space),
                info.width,
                info.height,
            )
            for name in read_ai_layers(file)
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

    def _import_psd_layered(self, file: Path, cropped: bool = False) -> CompItem:
        """Import a layered Photoshop file (`.psd`/`.psb`) as a composition.

        Layer groups become nested compositions (recursively); adjustment
        layers are flagged. With `cropped`, each leaf layer is cropped to its
        content box (`COMP_CROPPED_LAYERS`); otherwise the full canvas is kept
        (`COMP`).

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
            )
            return self._import_layered_comp(file, "8BPS", [spec], info)
        specs = self._psd_layer_specs(
            nodes,
            info.width,
            info.height,
            info.bit_depth,
            info.layer_count,
            cropped,
        )
        return self._import_layered_comp(file, "8BPS", specs, info)

    def _psd_layer_specs(
        self,
        nodes: list[Any],
        canvas_w: int,
        canvas_h: int,
        bit_depth: int,
        layer_count: int,
        cropped: bool,
    ) -> list[LayerSpec | LayerGroupSpec]:
        """Convert a PSD layer tree into import specs (recursively)."""
        specs: list[LayerSpec | LayerGroupSpec] = []
        for node in nodes:
            if isinstance(node, PsdGroup):
                specs.append(
                    LayerGroupSpec(
                        node.name,
                        self._psd_layer_specs(
                            node.children,
                            canvas_w,
                            canvas_h,
                            bit_depth,
                            layer_count,
                            cropped,
                        ),
                    )
                )
                continue
            opti_data = build_psd_layer_opti_data(
                canvas_w,
                canvas_h,
                bit_depth,
                layer_count,
                node.record_index,
                node.layer_id,
                node.name,
                node.bounds,
            )
            if cropped:
                left, top, right, bottom = node.bounds
                # AE stores an empty layer as 1x1 (its content box is degenerate).
                crop_w = max(1, right - left)
                crop_h = max(1, bottom - top)
                # Anchor at the cropped footage centre; position the layer so the
                # content sits where it was in the document (AE 2026 verified).
                transform = (
                    (crop_w / 2, crop_h / 2),
                    ((left + right) / 2, (top + bottom) / 2),
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
                    )
                )
        return specs

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

    def _allocate_item_id(self) -> int:
        """Return the next unique item ID and update the counter.

        ID 0 is reserved for the root folder, so the minimum returned
        value is 1. Also updates the next-item-ID counter in the head chunk.
        """
        new_id = self._head.next_item_id
        self._head.next_item_id = new_id + 1
        return new_id

    def _allocate_layer_id(self) -> int:
        """Return the next unique layer ID and update the counter."""
        if self._max_layer_id == -1:
            # AE allocates viewer pseudo-layer IDs (DLay/SLay/CLay/SecL
            # lists) from the same project-wide counter as real layers, so
            # scan every ldta in each comp's item tree, not just LIST:Layr.
            self._max_layer_id = max(
                (
                    cast("LdtaChunk", ldta).layer_id
                    for comp in self.compositions
                    for ldta in recursive_find(
                        comp._item_list.chunks, chunk_type="ldta"
                    )
                ),
                default=0,
            )
        self._max_layer_id += 1
        return self._max_layer_id

    @property
    def _solids_folder(self) -> FolderItem:
        """Return the Solids folder, creating one if it doesn't exist."""
        for folder in self.root_folder.folders:
            if folder.name == "Solids":
                return folder
        return self.root_folder.add_folder("Solids")

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
