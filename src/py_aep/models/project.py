from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ..binary.chunk import ListChunk, write_aep
from ..binary.scalar_chunks import Utf8Chunk
from ..binary.utils import (
    filter_by_type,
    find_by_list_type,
    toggle_flag_chunk,
)
from ..enums import (
    BitsPerChannel,
    ColorManagementSystem,
    FeetFramesFilmType,
    FootageTimecodeDisplayStartType,
    FramesCountType,
    GpuAccelType,
    LutInterpolationMethod,
    TimeDisplayType,
)
from .descriptors import ChunkField
from .items.composition import CompItem
from .items.folder import FolderItem
from .items.footage import FootageItem
from .validators import validate_number, validate_one_of
from .version import requires_version

if TYPE_CHECKING:
    from typing import ClassVar, Iterator

    from ..binary.chunk import Chunk
    from ..binary.item_chunks import HeadChunk, NhedChunk, NnhdChunk
    from ..binary.misc_chunks import DwgaChunk
    from ..binary.scalar_chunks import F8Chunk, U1Chunk
    from .items.item import Item
    from .layers.layer import Layer
    from .renderqueue.render_queue import RenderQueue


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
        validate=validate_number(min=1, max=999, integer=True),
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
        "_acer", "value", transform=bool, reverse=int
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
    )
    """The GPU acceleration type for the project. None if not
    recognised. Read / Write."""

    # ChunkField needs a chunk_attr that resolves to an object holding the
    # target field.  _xmp lives directly on Project, so we alias _aep = self
    # in __init__ so the descriptor chain is: getattr(self, "_aep") -> self,
    # then getattr(self, "_xmp") -> the raw XMP string.
    xmp_packet = ChunkField[ET.Element](
        "_aep",
        "_xmp",
        transform=ET.fromstring,
        reverse=lambda el: ET.tostring(el, encoding="unicode"),
    )
    """The XMP packet for the project, containing metadata.
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
        self._used_in_linked = False
        self._max_item_id = -1  # lazily computed on first allocation
        self._max_layer_id = -1  # lazily computed on first allocation

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
    def expression_engine(self, value: str) -> None:
        if value not in ("extendscript", "javascript-1.0"):
            raise ValueError(
                f"expression_engine must be 'extendscript' or 'javascript-1.0', "
                f"got {value!r}"
            )
        if self._exen_utf8 is not None:
            self._exen_utf8.value = value
        else:
            utf8 = Utf8Chunk(chunk_type="Utf8", value=value)
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
        "None"). Read-only.

        The binary chunk stores both the profile name and its full ICC
        profile data (base64-encoded).  Changing the name alone would
        leave stale ICC data, producing a file that After Effects may
        reject or silently revert.  Generating the ICC data would
        require the Adobe ICC profile files installed on disk, which
        cannot be assumed.
        """
        if self._ws_utf8 is not None:
            data = json.loads(self._ws_utf8.value)
            return str(data.get("baseColorProfile", {}).get("colorProfileName", "None"))
        if not any(c.chunk_type == "pcms" for c in self._root_chunks):
            return "sRGB IEC61966-2.1"
        return "None"

    @property
    def display_color_space(self) -> str:
        """The name of the display color space used for the project (e.g.,
        "ACES/sRGB"). Only relevant when color_management_system is OCIO.
        "None" when not set. Read-only.

        The binary chunk stores both the profile name and embedded ICC
        or OCIO color-space data (base64-encoded).  Changing the name
        alone would leave stale profile data.  See [working_space][] for
        details.

        Note:
            Not exposed in ExtendScript
        """
        if self._dcs_utf8 is not None:
            data = json.loads(self._dcs_utf8.value)
            return str(data.get("baseColorProfile", {}).get("colorProfileName", "None"))
        return "None"

    @property
    def color_management_system(self) -> ColorManagementSystem:
        """The color management system used by the project (Adobe or OCIO).
        Available in CC 2024 and later. Read / Write."""
        settings = self._get_cms_settings()
        return ColorManagementSystem(int(settings["colorManagementSystem"]))

    @color_management_system.setter
    @requires_version(24)
    def color_management_system(self, value: ColorManagementSystem | int) -> None:
        if not isinstance(value, (ColorManagementSystem, int)):
            raise TypeError(f"expected a ColorManagementSystem member, got {value!r}")
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
        if not isinstance(value, (LutInterpolationMethod, int)):
            raise TypeError(f"expected a LutInterpolationMethod member, got {value!r}")
        self._update_cms_setting("lutInterpolationMethod", int(value))

    @property
    def ocio_configuration_file(self) -> str:
        """The OCIO configuration file for the project. Only relevant when
        color_management_system is OCIO. Read / Write."""
        settings = self._get_cms_settings()
        return str(settings["ocioConfigurationFile"])

    @ocio_configuration_file.setter
    @requires_version(24)
    def ocio_configuration_file(self, value: str) -> None:
        if isinstance(value, os.PathLike):
            value = str(value)
        if not isinstance(value, str):
            raise TypeError(
                f"ocio_configuration_file must be a string or Path, got {value!r}"
            )
        self._update_cms_setting("ocioConfigurationFile", value)

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

    def save(self, path: os.PathLike[str]) -> None:
        """
        Save the project to a new .aep file at the given path.

        Warning:
            This is highly experimental for now.
        """
        path_obj = Path(path)
        if path_obj.exists():
            raise FileExistsError(
                f"The file '{path}' already exists. As writing is still experimental, "
                "overwriting is not allowed for now. Please choose a different path or "
                "delete the existing file."
            )

        path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(path_obj, "wb") as f:
            write_aep(f, self._rifx, self._xmp)
        self._file = str(path)

    def _allocate_item_id(self) -> int:
        """Return the next unique item ID and update the counter.

        ID 0 is reserved for the root folder, so the minimum returned
        value is 1.
        """
        if self._max_item_id == -1:
            self._max_item_id = max(self._items.keys(), default=0)
        self._max_item_id += 1
        return self._max_item_id

    def _allocate_layer_id(self) -> int:
        """Return the next unique layer ID and update the counter."""
        if self._max_layer_id == -1:
            self._max_layer_id = max(
                (lyr.id for comp in self.compositions for lyr in comp.layers),
                default=0,
            )
        self._max_layer_id += 1
        return self._max_layer_id

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
            chunk = Utf8Chunk(chunk_type="Utf8", value=json.dumps(data))
            self._rifx.chunks.append(chunk)
            self._cms_utf8 = chunk


def _get_effect_names(root_chunks: list[Chunk]) -> list[str]:
    """Get the list of effect names used in the project."""
    pefl_chunk = find_by_list_type(chunks=root_chunks, list_type="Pefl")
    pjef_chunks = filter_by_type(chunks=pefl_chunk.chunks, chunk_type="pjef")
    return [cast("Utf8Chunk", chunk).value for chunk in pjef_chunks]
