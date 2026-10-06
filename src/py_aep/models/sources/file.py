from __future__ import annotations

import io
import os
import re
import warnings
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, NamedTuple, cast

from ...binary.footage_chunks import (
    OptiChunk,
    PsdOptiChunk,
    SspcChunk,
    TextOptiChunk,
    build_ai_document_opti_data,
    build_ai_layer_opti_data,
    build_craw_opti_data,
    build_dpx_opti_data,
    build_exr_opti_data,
    build_generic_opti_data,
    build_psd_layer_opti_data,
    build_psd_opti_data,
    build_rhdr_opti_data,
    build_text_opti_data,
    build_tiff_opti_data,
)
from ...binary.misc_chunks import EmpdChunk
from ...binary.mutations import ColorProfileRecord, build_pin_list
from ...binary.scalar_chunks import Utf8Chunk
from ...binary.utils import (
    UNDEFINED_FRAME,
    ChunkNotFoundError,
    build_als2_list,
    build_stvc_list,
    filter_by_type,
    find_by_list_type,
    find_by_type,
    find_chunks_before,
    index_by_identity,
    parse_alas_data,
)
from ...color.envelope import build_icc_envelope
from ...color.icc import (
    ColorProfileNotFoundError,
    default_icc_library,
    icc_profile_description,
    icc_profile_id,
)
from ...color.ocio import ocio_input_envelope, resolve_ocio_config
from ...data.file_formats import (
    AI_COMP_EXTENSIONS,
    FORMAT_3D_MODEL_SCENE,
    PSD_COMP_EXTENSIONS,
    FileFormat,
    get_file_format,
    platform_source_format,
)
from ...enums import ColorManagementSystem, LinearLightMode
from ...resolvers.ai_bounds import (
    EMPTY_BOX,
    footage_size,
    read_ai_icc_profile,
    read_ai_layer_bounds,
)
from ...resolvers.ai_layers import UnsupportedAiLayersError, read_ai_layer_ocgs
from ...resolvers.media_probe import (
    pixel_buffer_size,
    probe_media,
    psd_layer_channels,
    psd_layer_depth,
)
from ...resolvers.platform_paths import platform_path
from ...resolvers.psd_bounds import psd_layer_box
from ...resolvers.psd_styles import read_global_light
from ...resolvers.source_layers import (
    layer_index_for_stored,
    resolve_ai_layer,
    resolve_psd_layer,
)
from ..validators import validate_bool, validate_file_exists
from .footage import _UNASSIGNED_PROFILE, FootageSource, _store_frames_over_rate

if TYPE_CHECKING:
    from ...binary.chunk import Chunk, ListChunk
    from ...binary.scalar_chunks import U1Chunk
    from ...resolvers.media_probe import MediaInfo
    from ...resolvers.psd_layers import PsdLayer
    from ..items.footage import FootageItem
    from ..project import Project


def _opti_data(
    fmt: FileFormat,
    info: MediaInfo,
    path: Path,
    *,
    sequence: bool,
    data: bytes | None = None,
) -> bytes:
    """Select the `opti` asset-info body for a file source (`path`, or a
    sequence's first frame; `data` is its content, if already read).

    Rules verified against AE 2026:

    - TIFF (still or sequence): always needs the 602-byte `TIF ` header;
      an empty or generic header crashes AE for TIFF regardless of whether
      it is a still or a sequence.
    - PSD: the 602-byte `8BPS` header of the merged document.
    - TIFF and PSD record the image as AE reads it: channel count, bit
      depth, colour mode and layer count.
    - EXR (still or sequence): the 9750-byte `oEXR` header AE writes
      (`build_exr_opti_data`). AE opens an EXR with an empty or generic opti,
      but renders a data window that differs from the display window
      misplaced, and crashed rendering one larger than the display window.
    - FBX singles: empty opti is fine (AE re-reads the located file).
    - Sequences and all audio/video formats: need the 58-byte generic
      header so AE recognises the item as a sequence or media file rather
      than missing footage.
    - PNG (still or sequence): needs the 58-byte generic header; AE opens
      a PNG still with an empty opti but crashes as soon as it renders it.
    - HDR (Radiance): needs the 30-byte format-specific `RHDR` header;
      dimensions live in `sspc`, not the opti.
    - Camera Raw (CRW): the 30-byte `Craw` header AE writes for a raw file
      without develop settings; an empty opti crashes AE.
    - AI/EPS/PDF: need the 596-byte `TEXT` header with width/height
      embedded as big-endian u16; an Illustrator/PDF document adds its
      layer count, page count and page-size tail, an EPS file does not.
    """
    if fmt.opti == "tiff":
        return build_tiff_opti_data(
            info.width,
            info.height,
            info.bit_depth,
            info.pixel_channels,
            info.color_mode,
            info.layer_count,
        )
    if fmt.opti == "psd":
        return build_psd_opti_data(
            info.width,
            info.height,
            info.bit_depth,
            info.pixel_channels,
            info.color_mode,
            info.layer_count,
        )
    if fmt.opti == "hdr":
        return build_rhdr_opti_data()
    if fmt.opti == "craw":
        return build_craw_opti_data()
    if fmt.opti == "dpx":
        return build_dpx_opti_data()
    if fmt.opti == "text":
        if path.suffix.lower() in AI_COMP_EXTENSIONS:
            return build_ai_document_opti_data(
                info.width, info.height, _ai_layer_count(path, data)
            )
        return build_text_opti_data(info.width, info.height)
    if fmt.opti == "exr":
        return build_exr_opti_data(info.compression, info.channel_names)
    if fmt.opti == "empty" and not sequence:
        return b""
    return build_generic_opti_data(fmt.source_format, sequence=sequence)


def _ai_layer_count(path: Path, data: bytes | None = None) -> int:
    """How many layers an Illustrator/PDF document has, as AE records it for
    the whole document: 0 for one without layers (pdf.pdf, ai_no_pdf.ai in
    footage_depth.aep). A document whose layers cannot be read (malformed or
    truncated PDF objects) counts 0 as well: the count only annotates the
    footage, which imports without it."""
    try:
        return len(read_ai_layer_ocgs(path, data))
    except UnsupportedAiLayersError:
        return 0


def _still_data_size(fmt: FileFormat, info: MediaInfo, path: Path) -> int:
    """The source data size AE caches in `sspc` for a single file.

    The file's size on disk (AE 2026, macOS and Windows), except for merged
    PSD footage and TIFF stills, whose decoded pixel buffer AE caches
    instead: `w * h * channels * bytes per channel` (`MediaInfo.pixel_channels`;
    choose_layer_merged / flattened_rgb_comp / footage_depth.aep fixtures).
    """
    if fmt.opti not in ("psd", "tiff"):
        return path.stat().st_size
    return pixel_buffer_size(
        info.width, info.height, info.pixel_channels, info.bit_depth
    )


class PsdLayerFootage(NamedTuple):
    """What After Effects records for the footage of one Photoshop layer."""

    box: tuple[int, int, int, int]
    """The content box `(left, top, right, bottom)` in canvas pixels."""

    opti_data: bytes
    data_size: int
    has_alpha: bool
    depth: int


def psd_layer_footage(
    info: MediaInfo, layer: PsdLayer, layer_styles: str, global_angle: float
) -> PsdLayerFootage:
    """The content box, `opti`, cached data size, alpha and depth AE
    records for `layer`'s footage - the same on a layered import and on a
    single-layer import or replace (`resolvers.psd_bounds.psd_layer_box`,
    `build_psd_layer_opti_data`, AE 2026 fixtures).

    Args:
        info: The probed document.
        layer: The Photoshop layer.
        layer_styles: The Layer Options choice: `"merge"`, `"editable"`
            or `"ignore"`.
        global_angle: The document's global light angle.
    """
    box = psd_layer_box(layer, info.width, info.height, layer_styles, global_angle)
    left, top, right, bottom = box
    layer_channels = psd_layer_channels(info, layer.has_transparency)
    opti_data = build_psd_layer_opti_data(
        info.width,
        info.height,
        info.bit_depth,
        info.layer_count,
        layer.record_index,
        layer.layer_id,
        layer.name,
        box,
        layer.is_adjustment,
        has_vector_mask=layer.vector_mask is not None,
        channels=info.pixel_channels,
        color_mode=info.color_mode,
        layer_channels=layer_channels,
    )
    data_size = pixel_buffer_size(
        max(right - left, 0), max(bottom - top, 0), layer_channels, info.bit_depth
    )
    return PsdLayerFootage(
        box,
        opti_data,
        data_size,
        layer.has_transparency,
        psd_layer_depth(info, layer.has_transparency),
    )


def _platform_media_info(
    info: MediaInfo, fmt: FileFormat, *, windows: bool
) -> MediaInfo:
    """`info` as After Effects on the target platform reads the file.

    AE 2026 on Windows stores `heic_alpha.heic` without alpha, whether it is
    imported by script or through the Import dialog; AE on macOS keeps the
    alpha channel (`format_options/heic` fixture).
    """
    if windows and fmt.source_format == "AIDE" and info.has_alpha:
        # The same channels without the alpha one (32 -> 24 on Windows).
        return info._replace(has_alpha=False, depth=info.depth // 4 * 3)
    return info


#: The profile AE falls back to for media that carries none of its own.
_DEFAULT_PROFILE = "sRGB IEC61966-2.1"

#: What AE assigns instead to video it decodes itself - an animated GIF, an
#: MPEG, a SWF or a WMV. A still or an image sequence of the same format
#: keeps the default, and QuickTime/MP4 name their space instead. STIL and
#: IMIO are BMP/GIF on Windows and macOS (see `GENERIC_STILL_FORMATS`).
_VIDEO_PROFILE = "Rec.709 Gamma 2.4"
_VIDEO_DECODED_FORMATS = frozenset({"STIL", "IMIO", "SWF ", "MPEO", "WMED"})

#: Formats whose importer embeds After Effects' own catalogued copy of the
#: profile rather than the file's bytes, and treats an untagged RGB file as
#: carrying sRGB (the Photoshop convention). The two copies differ only in
#: the advisory rendering-intent field, so the profile ID still matches.
#: An Illustrator/PDF file's RGB profile is recorded the same way (AE 2026,
#: complex.ai).
_CATALOGUED_PROFILE_FORMATS = frozenset({"TIF ", "8BPS"})

#: DPX and Cineon: AE records no profile at all and interprets the footage
#: in the working space (`ipws` 1; AE 2026 on Windows and the macOS
#: media_gap_formats.aep fixture).
_UNPROFILED_FORMATS = frozenset({"sDPX"})

#: The profile AE embeds for a Camera Raw file, which carries none: the
#: catalogued ProPhoto RGB Camera Raw develops into (AE 2026, crw.crw).
_CAMERA_RAW_PROFILES = {"Craw": "ProPhoto RGB"}

#: The profile AE records by name only (`empd`, no ICC data, interpreted in
#: the working space) for a TIFF or Photoshop image that carries none and is
#: not RGB, by Photoshop colour mode: grayscale, indexed, CMYK, Lab (AE 2026,
#: depth/*.psd and *.tif). A 32-bit float grayscale TIFF names the linear
#: one; a bitmap (1-bit) image is assigned sRGB like any untagged media.
_MODE_PROFILE_NAMES = {
    1: "Dot Gain 20%",
    2: "sRGB IEC61966-2.1",
    4: "U.S. Web Coated (SWOP) v2",
    9: "Lab D50",
}
_LINEAR_GRAY_PROFILE_NAME = "Linear Grayscale Profile"

#: Formats AE leaves without any profile record when the file carries none:
#: JPEG, and the QuickTime/MP4 containers, whose color space AE names
#: (`empd` + e.g. "Rec. 709") from data py_aep cannot read yet. The record
#: still counts as managed - AE fills the name in when it opens the project.
_UNRECORDED_PROFILE_FORMATS = frozenset({"ZPEG"})
_VIDEO_CONTAINER_FORMATS = frozenset({"MOoV", "XCEX"})

#: Formats AE imports with Interpret As Linear Light off rather than the
#: "on for 32-bpc files" default: the ones it decodes through its media
#: importers. An audio-only QuickTime and any image sequence keep the
#: default. The setting is inert below 32 bpc either way. HEIC (`AIDE`) is
#: one of them: off in every AE 2026 HEIC import (Windows and macOS).
_LINEAR_LIGHT_OFF_FORMATS = frozenset(
    {"ZPEG", "STIL", "IMIO", "SWF ", "MPEO", "WMED", "MOoV", "XCEX", "AIDE"}
)


def _catalogued_profile(name: str) -> bytes | None:
    """After Effects' own copy of the named profile, if it is installed."""
    try:
        return default_icc_library().bytes_for(name)
    except ColorProfileNotFoundError:
        return None


def _profile_record(blob: bytes) -> ColorProfileRecord:
    name = icc_profile_description(blob) or ""
    return ColorProfileRecord(icc_profile_id(blob), build_icc_envelope(name, blob))


def named_media_profile(source_format: str, info: MediaInfo) -> str | None:
    """The profile After Effects records by name only for a TIFF or Photoshop
    image whose colours are not RGB, or `None` when it records an ICC
    profile (or none) instead.

    A file tagged with a non-RGB profile names that profile; an untagged one
    names AE's default for its colour mode (`_MODE_PROFILE_NAMES`).
    """
    if source_format not in _CATALOGUED_PROFILE_FORMATS:
        return None
    if info.icc_profile is not None:
        if info.icc_profile[16:20] == b"RGB ":
            return None
        return icc_profile_description(info.icc_profile)
    if info.color_mode == 1 and info.bit_depth == 32:
        # Measured for a float TIFF only; a 32-bit grayscale PSD keeps the
        # RGB rule until it is measured.
        return _LINEAR_GRAY_PROFILE_NAME if source_format == "TIF " else None
    return _MODE_PROFILE_NAMES.get(info.color_mode)


def ai_document_profile(
    path: Path, data: bytes | None = None
) -> tuple[bytes | None, str | None]:
    """`(icc_profile, profile_name)` for an Illustrator/PDF/EPS file: the RGB
    profile its page draws with, recorded like a raster file's embedded one,
    or the name of a non-RGB one, which AE records by name only (AE 2026:
    complex.ai embeds sRGB, ai.ai names Coated FOGRA39)."""
    icc = read_ai_icc_profile(path, data)
    if icc is None:
        return None, None
    if icc[16:20] == b"RGB ":
        return icc, None
    return None, icc_profile_description(icc)


def _media_profile_records(
    icc_profile: bytes | None,
    source_format: str,
    has_video: bool,
    is_video: bool,
    embedded_profile_name: str | None,
    color_mode: int = 3,
) -> tuple[ColorProfileRecord | None, ColorProfileRecord | None]:
    """The `(embedded, assigned)` CLRS profile records for a source file.

    AE records the profile the file carries and assigns one to media that
    carries none, with the per-format exceptions in
    `_CATALOGUED_PROFILE_FORMATS`, `_UNRECORDED_PROFILE_FORMATS`,
    `_VIDEO_CONTAINER_FORMATS` and `_VIDEO_DECODED_FORMATS`. Measured across
    every format py_aep imports (AE 2026), plus untagged JPEG/TIFF/PSB
    variants.

    Args:
        icc_profile: The profile the media file embeds, if any (see
            [MediaInfo.icc_profile][py_aep.resolvers.media_probe.MediaInfo]).
        source_format: Its `sspc` 4-char format code.
        has_video: Whether the media has picture at all (audio-only
            QuickTime is recorded like any other audio file).
        is_video: Whether the picture is time-based rather than a still or
            an image sequence.
        embedded_profile_name: A named media color space, for the formats
            that carry one (`.ai` and friends, non-RGB TIFF/PSD).
        color_mode: The Photoshop colour mode the image reads as (see
            [MediaInfo.color_mode][py_aep.resolvers.media_probe.MediaInfo]);
            an untagged bitmap TIFF/PSD is assigned sRGB rather than taken
            as carrying it.
    """
    if embedded_profile_name is not None or source_format in _UNPROFILED_FORMATS:
        return None, None  # a named space, or none at all (DPX/Cineon)
    blob = icc_profile
    if blob is None and source_format in _CAMERA_RAW_PROFILES:
        blob = _catalogued_profile(_CAMERA_RAW_PROFILES[source_format])
    elif blob is None and source_format in _CATALOGUED_PROFILE_FORMATS and color_mode:
        blob = _catalogued_profile(_DEFAULT_PROFILE)
    elif blob is not None and source_format in _CATALOGUED_PROFILE_FORMATS | {"TEXT"}:
        catalogued = _catalogued_profile(icc_profile_description(blob) or "")
        if catalogued is not None and icc_profile_id(catalogued) == icc_profile_id(
            blob
        ):
            blob = catalogued
    if blob is not None:
        return _profile_record(blob), None
    if source_format in _UNRECORDED_PROFILE_FORMATS or (
        has_video and source_format in _VIDEO_CONTAINER_FORMATS
    ):
        return None, None
    name = (
        _VIDEO_PROFILE
        if is_video and source_format in _VIDEO_DECODED_FORMATS
        else _DEFAULT_PROFILE
    )
    assigned = _catalogued_profile(name)
    if assigned is None:
        # Nothing to assign without the profile's bytes; the record stays
        # empty so the import still works with no ICC store on the machine.
        return None, None
    return None, _profile_record(assigned)


def _alpha_mode_raw(has_alpha: bool, premultiplied: bool) -> int:
    """The `sspc` alpha byte AE stores: 3 = no alpha, 1 = premultiplied,
    0 = straight."""
    if not has_alpha:
        return 3
    return 1 if premultiplied else 0


def _sync_premultiplied(sspc: SspcChunk) -> None:
    """Set the `sspc` premultiplied flag bit AE writes with the alpha byte.

    AE resets the footage to straight alpha on open when the bit disagrees
    with a premultiplied alpha byte. An FBX scene is the exception: AE 2026
    sets the bit while the byte stays straight (the 3D scene renders against
    a premultiplied black background; measured against an AE-resaved
    crystal.fbx).
    """
    sspc.premultiplied = (
        sspc.alpha_mode_raw == 1 or sspc.source_format_type == FORMAT_3D_MODEL_SCENE
    )


# `sspc` kind bytes (0xC8-0xC9) for a PSD single-layer binding: byte 0xC9
# records the import dialog's Layer Options choice (psd_layer_styles.aep
# fixtures). "editable" is never a user-passable value on the footage
# paths - it only flows through `FootageItem.replace(CURRENT_VALUE)`
# preserving an editable-comp per-layer binding verbatim.
PSD_LAYER_STYLES_C8 = {
    "ignore": b"\x00\x00",
    "merge": b"\x00\x01",
    "editable": b"\x00\x02",
}
_C9_TO_LAYER_STYLES = {v[1]: k for k, v in PSD_LAYER_STYLES_C8.items()}

# A sequence frame number is at most the last 9 digits of the file stem; any
# digits before them belong to the prefix (AE 2026: f_99999999998.png and
# f_99999999999.png import as `f_99[999999998-999999999].png`).
_FRAME_NUMBER_RE = re.compile(r"(\d{1,9})$")

# AE reads the `sspc` width and height as signed 16-bit values: a py_aep file
# holding a 65535-px-wide PNG opens -1 px wide in AE 2026, and 65536 does not
# fit the field at all.
_MAX_FOOTAGE_SIZE = 32767


def check_footage_size(name: str, width: int, height: int) -> None:
    """Reject footage dimensions After Effects cannot store or read back.

    Raises:
        ValueError: If `width` or `height` is outside 0-32767 px.
    """
    if not (0 <= width <= _MAX_FOOTAGE_SIZE and 0 <= height <= _MAX_FOOTAGE_SIZE):
        raise ValueError(
            f"{name}: {width}x{height} px is outside the 0-{_MAX_FOOTAGE_SIZE} px "
            "After Effects footage can hold"
        )


def _join_sequence_frame(folder: str, frame_name: str) -> str:
    """Join a footage folder with an image-sequence frame filename using the
    folder's own separator, so the result matches AE's `fsName` (all `\\` for
    a Windows-authored project, all `/` for a POSIX one) rather than mixing
    the two. A backslash anywhere marks a Windows path; `PureWindowsPath` also
    splits any embedded `/`, while `PurePosixPath` leaves a native POSIX path
    intact (`PureWindowsPath` would rewrite its forward slashes to `\\`)."""
    if "\\" in folder:
        return str(PureWindowsPath(folder) / frame_name)
    return str(PurePosixPath(folder) / frame_name)


class FileSource(FootageSource):
    """
    The `FileSource` object describes footage that comes from a file.

    Example:
        ```python
        from py_aep import FileSource, parse

        app = parse("project.aep")
        footage = app.project.footages[0]
        if isinstance(footage.main_source, FileSource):
            print(footage.main_source.file)
        ```

    Info:
        `FileSource` is a subclass of [FootageSource][] object. All methods and
        attributes of [FootageSource][] are available when working with `FileSource`.

    See: https://ae-scripting.docsforadobe.dev/sources/filesource/
    """

    @property
    def file(self) -> str:
        """The full file path. Read-only."""
        return self._file

    @property
    def file_names(self) -> list[str]:
        """The filenames if the footage is an image sequence. Read-only."""
        return self._file_names

    @property
    def target_is_folder(self) -> bool:
        """`True` if the file is a folder, else `False`. Read-only."""
        return self._target_is_folder

    @property
    def _is_sequence(self) -> bool:  # type: ignore[override]  # property over property
        return self._target_is_folder

    @property
    def _is_alphabetical(self) -> bool:
        """Whether this is an image sequence listed by file name (imported
        with `force_alphabetical`) rather than numbered: AE leaves its frame
        numbers undefined and keeps the file names in the Pin's StVc list."""
        return (
            self._target_is_folder
            and self._sspc.start_frame == UNDEFINED_FRAME
            and bool(self._file_names)
        )

    def _join_project(self, project: Project) -> None:
        """Record the color space an OCIO-managed project assigns this new
        file (`color.ocio.ocio_input_envelope`).

        After Effects 2026 writes it for every file it imports under OCIO,
        beside any profile the file embeds, and marks the media color
        managed - an Illustrator file too. A source that already holds an
        OCIO space keeps it: a replace carries its predecessor's. Without the
        project's config at hand the Adobe-mode record built with the source
        stays. The records are first cut to the project's file version (see
        `FootageSource._join_project`).
        """
        super()._join_project(project)
        if (
            self._clrs is None
            or project.color_management_system != ColorManagementSystem.OCIO
        ):
            return
        profile = self._ocsp_profile()
        if profile is not None and profile.is_ocio:
            return
        config = resolve_ocio_config(project.ocio_configuration_file)
        envelope = None if config is None else ocio_input_envelope(config, self._file)
        if envelope is None:
            warnings.warn(
                f"OCIO configuration {project.ocio_configuration_file!r} not found "
                f"or without a default color space: {Path(self._file).name} keeps "
                "an Adobe color profile",
                stacklevel=3,
            )
            return
        ipws = cast(
            "U1Chunk", find_by_type(chunks=self._clrs.chunks, chunk_type="ipws")
        )
        ipws.value = 0
        find_by_type(
            chunks=self._clrs.chunks, chunk_type="apid"
        ).data = _UNASSIGNED_PROFILE
        self._write_ocsp(envelope)

    @property
    def _is_3d_model_scene(self) -> bool:
        """`True` for an imported 3D model scene (e.g. an `.fbx`)."""
        return self._sspc.source_format_type == FORMAT_3D_MODEL_SCENE

    @property
    def missing_footage_path(self) -> str:
        """The path of the missing source file when the footage was missing
        at the time the project was last saved, otherwise an empty string.
        Read-only."""
        if self._sspc.footage_missing_at_save:
            return self._file
        return ""

    @property
    def file_attributes(self) -> dict[str, int | str]:
        """
        Format-specific metadata extracted from the source file header stored
        in the project.

        For PSD (Photoshop) sources, the following keys are available:

        - `psd_layer_index` (`int`): Zero-based index of this layer within
          the PSD file. `0xFFFFFFFF` means merged/flattened.
        - `psd_group_name` (`str`): PSD group/folder that contains this
          layer (e.g. `"PAINT 02"`).
        - `psd_layer_count` (`int`): Total number of layers in the source
          PSD.
        - `psd_canvas_width` (`int`): Full PSD canvas width in pixels.
        - `psd_canvas_height` (`int`): Full PSD canvas height in pixels.
        - `psd_bit_depth` (`int`): Bit depth per channel (8, 16, 32).
        - `psd_channels` (`int`): Number of color channels (3 for RGB,
          4 for RGBA/CMYK).
        - `psd_layer_top` (`int`): Layer bounding-box top (pixels, can be
          negative if the layer extends above the canvas).
        - `psd_layer_left` (`int`): Layer bounding-box left.
        - `psd_layer_bottom` (`int`): Layer bounding-box bottom.
        - `psd_layer_right` (`int`): Layer bounding-box right.

        Read-only.
        """
        return self._file_attributes

    @property
    def _start_frame(self) -> int:  # type: ignore[override]  # ChunkField -> property
        """First frame of an image sequence.

        AE leaves the `sspc` field undefined for some sequences (every
        pre-2019 file in the fixtures); the number is then the last digit
        group of the first `StVc` filename (`render.0101.exr` > 101).
        Derived on read rather than written back, so a parse/save
        round-trip stays byte-identical.
        """
        return self._derived_frame(self._sspc.start_frame, 0)

    @property
    def _end_frame(self) -> int:  # type: ignore[override]  # ChunkField -> property
        """Last frame of an image sequence. See `_start_frame`."""
        return self._derived_frame(self._sspc.end_frame, -1)

    def _derived_frame(self, stored: int, index: int) -> int:
        if stored != UNDEFINED_FRAME or not self._file_names:
            return stored
        match = re.search(r"(\d+)\D*$", self._file_names[index])
        return int(match.group(1)) if match is not None else stored

    def __init__(
        self,
        *,
        _pin: ListChunk,
        _sspc: SspcChunk,
        _opti: OptiChunk,
        _linl: U1Chunk | None = None,
        _clrs: ListChunk | None = None,
    ) -> None:
        super().__init__(_sspc=_sspc, _linl=_linl, _clrs=_clrs)
        self._pin = _pin
        self._opti = _opti

        pin_chunks = _pin.chunks

        # Derive file_names from StVc LIST
        self._file_names: list[str]
        try:
            stvc_chunk = find_by_list_type(chunks=pin_chunks, list_type="StVc")
            utf8_chunks = filter_by_type(chunks=stvc_chunk.chunks, chunk_type="Utf8")
            self._file_names = [cast("Utf8Chunk", chunk).value for chunk in utf8_chunks]
        except ChunkNotFoundError:
            self._file_names = []

        # Derive file path and target_is_folder from Als2/alas JSON
        alas_data = parse_alas_data(pin_chunks)
        self._target_is_folder: bool = alas_data.get("target_is_folder", False)
        if self._file_names:
            self._file = _join_sequence_frame(
                alas_data.get("fullpath", ""), self._file_names[0]
            )
        else:
            self._file = alas_data.get("fullpath", "")

        # Old-format AE files lack the StVc LIST that stores per-frame
        # filenames for image sequences.  Construct the first-frame path
        # from the Utf8 prefix/extension chunks stored before opti.
        if (
            not self._file_names
            and _sspc.frame_padding > 0
            and _sspc.start_frame != UNDEFINED_FRAME
        ):
            try:
                utf8_before_opti = find_chunks_before(
                    chunks=pin_chunks,
                    chunk_type="Utf8",
                    before_type="opti",
                )
            except ChunkNotFoundError:
                utf8_before_opti = []
            if len(utf8_before_opti) >= 2:
                prefix = cast("Utf8Chunk", utf8_before_opti[-2]).value
                extension = cast("Utf8Chunk", utf8_before_opti[-1]).value
                if prefix or extension:
                    first_frame = (
                        f"{prefix}{_sspc.start_frame:0{_sspc.frame_padding}d}"
                        f"{extension}"
                    )
                    self._file = _join_sequence_frame(self._file, first_frame)

        if getattr(_opti, "asset_type", "") == "8BPS":
            psd_opti = cast("PsdOptiChunk", _opti)
            self._file_attributes: dict[str, int | str] = {
                "psd_layer_index": psd_opti.psd_layer_index,
                "psd_group_name": psd_opti.psd_group_name or "",
                "psd_layer_count": psd_opti.psd_layer_count,
                "psd_canvas_width": psd_opti.psd_canvas_width,
                "psd_canvas_height": psd_opti.psd_canvas_height,
                "psd_bit_depth": psd_opti.psd_bit_depth,
                "psd_channels": psd_opti.psd_channels,
                "psd_layer_top": psd_opti.psd_layer_top,
                "psd_layer_left": psd_opti.psd_layer_left,
                "psd_layer_bottom": psd_opti.psd_layer_bottom,
                "psd_layer_right": psd_opti.psd_layer_right,
            }
        else:
            self._file_attributes = {}

    @classmethod
    def _new(
        cls,
        file: str | os.PathLike[str],
        *,
        source_format: str,
        width: int,
        height: int,
        duration: float,
        frame_rate: float,
        pixel_aspect: float = 1.0,
        has_alpha: bool = False,
        depth: int = 0,
        media_flag: bool = False,
        alpha_premultiplied: bool = False,
        audio_sample_rate: float = 0.0,
        sequence_prefix: str | None = None,
        sequence_ext: str | None = None,
        sequence_files: list[str] | None = None,
        start_frame: int = 0,
        end_frame: int = 0,
        frame_padding: int = 0,
        opti_data: bytes = b"",
        embedded_profile_name: str | None = None,
        icc_profile: bytes | None = None,
        full_frame: bool = True,
        layer_name: str = "",
        layer_id: int | None = None,
        layer_index: int | None = None,
        data_size: int = 0,
        reserved_c8: bytes | None = None,
        color_mode: int = 3,
        windows: bool,
    ) -> FileSource:
        """Create a new file footage source with backing chunks.

        AE caches all of this metadata in `sspc` and does not re-read the
        media on open, so the caller must supply correct values (see
        `resolvers.media_probe`). The `opti` asset-info chunk is left empty;
        AE locates the file via the `alas` path.

        Args:
            file: Path to the source file (single), or to a representative
                frame (sequence; the containing folder is stored).
            windows: Store the path in the style of AE on Windows rather
                than macOS (see `resolvers.platform_paths.platform_path`).
            source_format: 4-char `sspc` source-format code (see
                `data/file_formats.py`).
            width: Pixel width (0 for audio-only media).
            height: Pixel height (0 for audio-only media).
            duration: Duration in seconds (0 for a still image).
            frame_rate: Native frame rate in fps (0 for stills/audio).
            pixel_aspect: Pixel aspect ratio.
            has_alpha: Whether the footage has an alpha channel.
            depth: Pixel depth AE caches for the footage (see
                [MediaInfo.depth][py_aep.resolvers.media_probe.MediaInfo]).
            media_flag: Mark the footage the way AE marks its media formats
                (`FileFormat.media_flag`): `sspc` 0x70 bit 3, and 0x9F bit 3
                for a single file.
            alpha_premultiplied: When `has_alpha`, select PREMULTIPLIED
                rather than the STRAIGHT default.
            audio_sample_rate: Audio sample rate in Hz (0 = no audio).
            sequence_prefix: Filename text before the frame number. When not
                `None`, the source is an image sequence.
            sequence_ext: Filename extension including the dot (sequence only).
            sequence_files: The frame file names of an alphabetical sequence,
                in order. When not `None`, the source is an image sequence
                listed by name rather than numbered, and `sequence_prefix`,
                `sequence_ext`, `start_frame`, `end_frame` and
                `frame_padding` are not used.
            start_frame: First frame number (sequence only).
            end_frame: Last frame number (sequence only).
            frame_padding: Zero-padded digit width of the frame number
                (sequence only).
            opti_data: Raw `opti` asset-info bytes. Empty is accepted by AE
                for single still images; sequences and audio need the
                generic header (see `build_generic_opti_data`).
            embedded_profile_name: Name of the source's embedded color
                profile, recorded in `LIST:CLRS` (matching AE). `None` for
                sources with no embedded profile.
            icc_profile: The ICC profile the media file embeds (see
                [MediaInfo.icc_profile][py_aep.resolvers.media_probe.MediaInfo]).
                `None` selects the profile AE assigns to media that carries
                none - see `_media_profile_records`.
            full_frame: When `True` (default, every standard import), the
                footage spans its full source frame. Set `False` for a layer
                cropped to its content box (`COMP_CROPPED_LAYERS`, or a
                chosen layer imported at Layer Size).
            layer_name: Name of the referenced layer when the source is a
                single layer of a layered file; stored in the Pin's `Utf8`
                slot after `sspc` (empty otherwise, matching AE).
            layer_id: Photoshop layer id for a layer-bound source; `None`
                keeps the `0xFFFFFFFF` unbound sentinel.
            layer_index: 0-based document index of the referenced layer;
                `None` keeps the `0xFFFFFFFF` unbound sentinel.
            data_size: Cached source data size for `sspc` byte 0xD0 (see
                `SspcChunk.data_size`); `0` lets AE re-derive it.
            reserved_c8: Override for the `sspc` 0xC8 kind bytes. `None`
                applies the whole-file rule (see below); layer-bound and
                merged-PSD sources pass AE's observed per-context value.
            color_mode: The Photoshop colour mode the image reads as (see
                `_media_profile_records`); 3 (RGB) by default.

        Raises:
            ValueError: If `width` or `height` is outside 0-32767 px.
        """
        check_footage_size(Path(file).name, width, height)
        is_sequence = sequence_prefix is not None or sequence_files is not None
        # AE locates footage only by an absolute path (a relative one opens
        # as missing), and its scripts' `new File()` resolves a relative path
        # against the current folder: resolve against the working directory.
        path = Path(os.path.abspath(file))

        if reserved_c8 is None:
            # AE 2026 writes byte 0xC9 = 0x02 for raster/media file footage but
            # 0x00 for the layers of an Illustrator/PDF composition import
            # (ai_comp.aep, complex_comp.aep); solids/placeholders keep the
            # all-zero default. Verified across the AE-resaved import
            # fixtures. Other sources override this (chosen PSD layer = 0x01,
            # chosen AI layer = 0x02, merged PSD = 0x03, a whole AI/EPS/PDF
            # file = 0x02; choose_layer_*.aep, footage_depth.aep).
            reserved_c8 = b"\x00\x00" if source_format == "TEXT" else b"\x00\x02"
        sspc = SspcChunk(
            source_format_type=source_format,
            width=width,
            height=height,
            alpha_mode_raw=_alpha_mode_raw(has_alpha, alpha_premultiplied),
            is_synthetic_a=0,
            is_synthetic_b=0,
            is_synthetic_c=0,
            full_frame=full_frame,
            reserved_c8=reserved_c8,
            data_size=data_size,
            depth=depth,
            reserved_40=b"\x01\x01",  # every file source (AE 2026)
        )
        _sync_premultiplied(sspc)
        if media_flag:
            sspc.media_format = True
            sspc.media_file = not is_sequence
        if layer_id is not None:
            sspc.layer_id = layer_id
        if layer_index is not None:
            sspc.layer_index = layer_index
        sspc.native_frame_rate = frame_rate
        sspc.duration = duration
        sspc.pixel_aspect = pixel_aspect
        sspc.audio_sample_rate = audio_sample_rate
        # AE stamps the source's last-modified time and re-reads the media
        # whenever it does not match, taking the dimensions from the format
        # plugin instead of the ones cached here. For an OpenEXR frame whose
        # data window differs from its display window that is a different
        # answer (the plugin reports the data window, AE's importer records
        # the display window), so an unstamped sequence silently changes size
        # when AE opens the project. AE stamps a sequence with its folder.
        sspc.from_file = True
        # Media that is not on this machine stays unstamped, which is the
        # "re-read me" state AE itself writes for missing footage.
        stamp_target = path.parent if is_sequence else path
        try:
            sspc.source_modified = int(stamp_target.stat().st_mtime)
        except OSError:
            pass
        if sequence_files is not None:
            # An alphabetical sequence lists its frames by name (in the Pin's
            # StVc list, below) instead of numbering them. AE 2026 writes the
            # frame numbers undefined, no padding, these flags and a set byte
            # 0x74.
            sspc.start_frame = sspc.end_frame = UNDEFINED_FRAME
            sspc._reserved_a8 = b"\x00\x00\x00\x01"
            sspc._reserved_b8 = b"\x00"
            sspc._reserved_ba = b"\x00\x00"
            sspc._source_stamp = b"\x01" + sspc._source_stamp[1:]
        elif is_sequence:
            sspc.start_frame = start_frame
            sspc.end_frame = end_frame
            sspc.frame_padding = frame_padding
            # AE tags image sequences with these flags; without them it
            # treats the folder reference as missing footage on open.
            # (Values reverse-engineered from AE 2026 sequence imports.)
            # Byte 0xB8 marks zero-padded frame numbers: 0 for p410.png
            # or s1.png ... s12.png, 1 for z_0410.png or frame_001.png.
            sspc._reserved_a8 = b"\x00\x00\x00\x02"
            zero_padded = len(str(start_frame)) < frame_padding
            sspc._reserved_b8 = b"\x01" if zero_padded else b"\x00"
            sspc._reserved_ba = b"\x01\x01"
        if is_sequence:
            _store_frames_over_rate(sspc, round(duration * frame_rate), frame_rate)

        # Route through variant dispatch so a recognized asset type (e.g.
        # 8BPS -> PsdOptiChunk) is stored as its typed subclass and exposes
        # file_attributes immediately, not just after a save/reparse.
        if opti_data:
            opti = OptiChunk.read(
                io.BytesIO(opti_data), len(opti_data), chunk_type="opti"
            )
        else:
            opti = OptiChunk(chunk_type="opti")

        fullpath = platform_path(
            str(path.parent) if is_sequence else str(path), windows=windows
        )
        path_chunks: list[Chunk] = [
            build_als2_list(fullpath, target_is_folder=is_sequence)
        ]
        if sequence_files is not None:
            path_chunks.append(build_stvc_list(sequence_files))
        elif is_sequence:
            path_chunks.append(Utf8Chunk(value=sequence_prefix or ""))
            path_chunks.append(Utf8Chunk(value=sequence_ext or ""))

        embedded, assigned = _media_profile_records(
            icc_profile,
            source_format,
            width > 0,
            width > 0 and duration > 0 and not is_sequence,
            embedded_profile_name,
            color_mode,
        )
        pin = build_pin_list(
            sspc,
            opti,
            path_chunks=path_chunks,
            embedded_profile_name=embedded_profile_name,
            embedded_profile=embedded,
            assigned_profile=assigned,
            # AE color-manages every file it imports; the ones whose space it
            # only names (a CMYK .ai, a grayscale TIFF...) or does not know
            # (DPX/Cineon) keep the working space, and so does a solid.
            color_managed=embedded_profile_name is None
            and source_format not in _UNPROFILED_FORMATS,
            layer_name=layer_name,
        )
        clrs = find_by_list_type(chunks=pin.chunks, list_type="CLRS")
        linl = cast("U1Chunk", find_by_type(chunks=clrs.chunks, chunk_type="linl"))
        if source_format in _LINEAR_LIGHT_OFF_FORMATS and width > 0 and not is_sequence:
            linl.value = int(LinearLightMode.OFF)

        return cls(_pin=pin, _sspc=sspc, _opti=opti, _linl=linl, _clrs=clrs)

    @classmethod
    def _from_file(
        cls,
        file: str | os.PathLike[str],
        *,
        sequence: bool = False,
        force_alphabetical: bool = False,
        windows: bool,
        default_sequence_fps: float = 30.0,
        range_start: int = 0,
        range_end: int = 0,
    ) -> FileSource:
        """Build a `FileSource` by probing a media file's header.

        Shared by `Project.import_file`, `FootageItem.replace*`, and
        `AVItem.set_proxy*`.

        Args:
            file: Path to the source file, or a representative frame for a
                sequence.
            sequence: When `True`, import as a numbered image sequence.
            force_alphabetical: For a sequence, order frames alphabetically
                rather than numerically.
            windows: Write what AE on Windows writes rather than AE on
                macOS: the BMP/GIF importer code, and no alpha for HEIC
                (see `Project._platform`).
            default_sequence_fps: Frame rate for formats with no native
                rate (AE's "Import Options Default Sequence FPS"
                preference; AE's factory value is 30).
            range_start: First frame number of the sequence clipping range
                (see `ImportOptions.range_start`). 0 with `range_end` 0
                imports every frame.
            range_end: Last frame number of the clipping range, inclusive.

        Raises:
            ValueError: If the extension is not a supported footage format
                (or, with `sequence`, one AE does not import as a sequence),
                if the frame range is invalid, or if the file has no track
                After Effects can decode (e.g. an AV1-only `.mp4`).
            NotImplementedError: If After Effects requires a format-specific
                `opti` header that is not implemented yet, or header probing
                is unavailable for the format.
        """
        validate_file_exists(file)
        path = Path(file)
        fmt = get_file_format(path.suffix)
        if fmt.opti == "unsupported":
            raise NotImplementedError(
                f"footage import does not yet support {path.suffix}: After "
                "Effects requires a format-specific opti header that has not "
                "been reverse-engineered yet."
            )
        if sequence and not fmt.sequence:
            raise ValueError(
                f"After Effects cannot import {path.suffix} files as an image "
                "sequence; import the file on its own."
            )
        if sequence:
            return cls._build_sequence(
                path,
                fmt,
                force_alphabetical,
                default_sequence_fps,
                windows=windows,
                range_start=range_start,
                range_end=range_end,
            )
        fmt = fmt._replace(source_format=platform_source_format(fmt, windows=windows))
        # An AI/EPS/PDF file is read once for its probe, layers and profile.
        data = path.read_bytes() if fmt.opti == "text" else None
        info = _platform_media_info(probe_media(path, data), fmt, windows=windows)
        opti_data = _opti_data(fmt, info, path, sequence=False, data=data)
        # The profile AE records in CLRS: an AI/EPS/PDF page's (embedded when
        # RGB, named otherwise), or the name of a non-RGB TIFF/PSD's.
        if fmt.opti == "text":
            icc, profile_name = ai_document_profile(path, data)
            info = info._replace(icc_profile=icc)
        else:
            profile_name = named_media_profile(fmt.source_format, info)
        # Merged PSD footage: AE writes kind 0x0003. An AI/EPS/PDF file
        # imported whole takes the file-footage 0x0002 (footage_depth.aep),
        # not the 0x0000 of an Illustrator composition's layers.
        reserved_c8 = {"psd": b"\x00\x03", "text": b"\x00\x02"}.get(fmt.opti)
        data_size = _still_data_size(fmt, info, path)
        return cls._new(
            path,
            source_format=fmt.source_format,
            width=info.width,
            height=info.height,
            duration=info.duration,
            frame_rate=info.frame_rate,
            icc_profile=info.icc_profile,
            pixel_aspect=info.pixel_aspect,
            has_alpha=info.has_alpha,
            depth=info.depth,
            media_flag=fmt.media_flag,
            alpha_premultiplied=fmt.alpha_premultiplied,
            audio_sample_rate=info.audio_sample_rate,
            opti_data=opti_data,
            embedded_profile_name=profile_name,
            data_size=data_size,
            reserved_c8=reserved_c8,
            color_mode=info.color_mode,
            windows=windows,
        )

    @classmethod
    def _from_layer(
        cls,
        file: str | os.PathLike[str],
        layer_index: int,
        *,
        dimensions: str | None = None,
        layer_styles: str | None = None,
        windows: bool,
    ) -> FileSource:
        """Build a `FileSource` referencing a single layer of a layered file.

        Mirrors the "Choose Layer" option of AE's import dialog for
        `.psd`/`.psb` (layer records) and `.ai`/`.pdf` (PDF Optional Content
        Groups). Shared by `Project.import_file` (`ImportOptions.layer_index`)
        and `FootageItem.replace`. Byte-verified against the AE 2026
        `choose_layer_*.aep` / `ai_choose_layer*.aep` fixtures.

        Args:
            file: Path to the layered source file.
            layer_index: The layer to reference, as its 0-based position in
                `resolvers.source_layers.list_layers` order (top first, leaf
                layers only).
            dimensions: `"document"` (default) sizes the footage to the full
                canvas; `"layer"` to the layer's content box - the PSD layer's
                (`resolvers.psd_bounds.psd_layer_box`), or the AI/PDF artwork
                box measured by `resolvers.ai_bounds.read_ai_layer_bounds`.
            layer_styles: PSD only - the Layer Options choice recorded in
                the `sspc` kind byte: `"merge"` (default), `"ignore"`, or
                `"editable"` (reachable only via replace's CURRENT_VALUE
                pass-through). Callers validate; ignored for AI/PDF.
            windows: Store the path in the style of AE on Windows rather
                than macOS (see `_new`).

        Raises:
            ValueError: If the file is not a layered format, or `layer_index`
                is out of range.
            NotImplementedError: For a merged PSD layer whose styles'
                rasterized bounds are not known (see
                `resolvers.psd_styles.merged_styles_bounds`).
            UnsupportedAiLayersError: For `dimensions="layer"` on an AI/PDF
                file whose page content py_aep cannot read.
        """
        validate_file_exists(file)
        path = Path(file)
        suffix = path.suffix.lower()
        if suffix in PSD_COMP_EXTENSIONS:
            info = probe_media(path)
            fmt = get_file_format(suffix)
            leaf = resolve_psd_layer(path, layer_index)
            styles = "merge" if layer_styles is None else layer_styles
            footage = psd_layer_footage(info, leaf, styles, read_global_light(path)[0])
            left, top, right, bottom = footage.box
            if dimensions == "layer" and right > left and bottom > top:
                width, height = right - left, bottom - top
            else:
                # Document Size - and a layer with no content box (an
                # adjustment or fully transparent layer), which keeps the
                # full canvas at Layer Size as in a cropped-comp import (AE
                # 2026 reads py's 0x0 footage back as the canvas).
                width, height = info.width, info.height
            return cls._new(
                path,
                source_format=fmt.source_format,
                width=width,
                height=height,
                duration=info.duration,
                frame_rate=info.frame_rate,
                icc_profile=info.icc_profile,
                pixel_aspect=info.pixel_aspect,
                has_alpha=footage.has_alpha,
                depth=footage.depth,
                alpha_premultiplied=fmt.alpha_premultiplied,
                audio_sample_rate=info.audio_sample_rate,
                opti_data=footage.opti_data,
                full_frame=dimensions != "layer",
                layer_name=leaf.name,
                layer_id=leaf.layer_id,
                layer_index=leaf.record_index,
                data_size=footage.data_size,
                reserved_c8=PSD_LAYER_STYLES_C8[styles],
                embedded_profile_name=named_media_profile(fmt.source_format, info),
                color_mode=info.color_mode,
                windows=windows,
            )
        if suffix in AI_COMP_EXTENSIONS:
            data = path.read_bytes()
            info = probe_media(path, data)
            fmt = get_file_format(suffix)
            ai_layers, index = resolve_ai_layer(path, layer_index, data)
            ai_layer = ai_layers[index]
            icc, profile_name = ai_document_profile(path, data)
            artwork_bounds = None
            width, height = info.width, info.height
            if dimensions == "layer":
                # The artwork box is the whole binding for a Layer Size
                # import: After Effects derives the footage pixel size from
                # it and does not recompute it on open.
                bounds = read_ai_layer_bounds(path, data)[index]
                artwork_bounds = EMPTY_BOX if bounds is None else bounds
                width, height = footage_size(bounds)
            opti_data = build_ai_layer_opti_data(
                info.width,
                info.height,
                ai_layer.name,
                len(ai_layers),
                artwork_bounds,
                ai_layer.visible,
            )
            return cls._new(
                path,
                source_format=fmt.source_format,
                width=width,
                height=height,
                duration=info.duration,
                frame_rate=info.frame_rate,
                icc_profile=icc,
                pixel_aspect=info.pixel_aspect,
                has_alpha=info.has_alpha,
                depth=info.depth,
                alpha_premultiplied=fmt.alpha_premultiplied,
                audio_sample_rate=info.audio_sample_rate,
                opti_data=opti_data,
                embedded_profile_name=profile_name,
                full_frame=dimensions != "layer",
                layer_name=ai_layer.name,
                layer_index=index,
                data_size=len(data),
                reserved_c8=b"\x00\x02",
                windows=windows,
            )
        raise ValueError(
            f"layer_index requires a layered .psd/.psb/.ai/.pdf file, got {suffix!r}"
        )

    @classmethod
    def _build_sequence(
        cls,
        file: Path,
        fmt: FileFormat,
        force_alphabetical: bool,
        default_frame_rate: float,
        *,
        windows: bool,
        range_start: int = 0,
        range_end: int = 0,
    ) -> FileSource:
        """Build a sequence `FileSource` by scanning sibling frames.

        With a frame range set, frames are filtered to numbers in
        `[range_start, range_end]` (inclusive) and the stored
        `start_frame`/`end_frame` bounds are the RANGE bounds even when
        files are missing inside or beyond it - AE treats absent frames as
        implied placeholders and encodes nothing else (verified against
        AE 2026 range-import fixtures, including interior gaps).

        `force_alphabetical` takes every file of the same type in the
        folder, numbered or not, in case-insensitive name order - AE 2026
        gathers `a_001.png`, `b.png`, `D.PNG`, `n_10.png`, `n_2.png` from a
        folder that also holds `x.jpg` and a subfolder.
        """
        validate_bool(force_alphabetical)
        if not 0 < default_frame_rate <= 999:
            # The "Import Options Default Sequence FPS" preference; outside
            # the conform-rate range it cannot time a sequence (0 divided
            # by zero below).
            raise ValueError(
                f"invalid default sequence frame rate {default_frame_rate!r}"
            )
        m = _FRAME_NUMBER_RE.search(file.stem)
        if m is None and not force_alphabetical:
            raise ValueError(
                f"Sequence import requires a numbered filename, got {file.name!r}"
            )

        has_range = range_start > 0 or range_end > 0
        if has_range and range_end == 0:
            # AE errors at import time ("Found no matches for the selected
            # file name") when a start is set without an end.
            raise ValueError("a sequence range start requires a range end")
        if has_range and range_end < range_start:
            raise ValueError("Range end cannot be less than range start")

        # BMP/GIF sequences take the target platform's importer code. AE
        # refuses the other one (see GENERIC_STILL_FORMATS).
        fmt = fmt._replace(source_format=platform_source_format(fmt, windows=windows))

        file_names: list[str] | None = None
        prefix: str | None = None
        ext: str | None = None
        if m is None or force_alphabetical:
            suffix = file.suffix.lower()
            # scandir's entries know their type, and the cheap name test runs
            # first: no stat per file of a large frame folder.
            with os.scandir(file.parent) as entries:
                file_names = sorted(
                    (
                        entry.name
                        for entry in entries
                        if os.path.splitext(entry.name)[1].lower() == suffix
                        and entry.is_file()
                    ),
                    key=str.lower,
                )
            first_frame = file_names[0]
            start_frame = end_frame = UNDEFINED_FRAME
            padding = 0
        else:
            prefix = file.stem[: m.start()]
            ext = file.suffix
            ext_key, prefix_key = ext.lower(), prefix.lower()
            # (number, name, digit count, own prefix)
            frames: list[tuple[int, str, int, str]] = []
            for sibling in file.parent.iterdir():
                if sibling.suffix.lower() != ext_key:
                    continue
                # Each file splits into its own prefix and frame number, and
                # the prefixes compare case-insensitively: AE 2026 (Windows)
                # gathers F_001.png and f_002.png into `F_[001-002].png`.
                stem = sibling.stem
                sm = _FRAME_NUMBER_RE.search(stem)
                if sm is not None and stem[: sm.start()].lower() == prefix_key:
                    frames.append(
                        (
                            int(sm.group(1)),
                            sibling.name,
                            len(sm.group(1)),
                            stem[: sm.start()],
                        )
                    )
            if not frames:
                frames = [(int(m.group(1)), file.name, len(m.group(1)), prefix)]

            if has_range:
                frames = [fr for fr in frames if range_start <= fr[0] <= range_end]
                if not frames:
                    raise ValueError(
                        f"no sequence frames numbered within [{range_start}, "
                        f"{range_end}]"
                    )

            frames.sort()
            # The padding is the first frame's digit count, whichever frame
            # was picked: AE 2026 names s1.png ... s12.png `s[1-12].png`
            # even from s12.png. The sequence is named after the first
            # frame's own prefix (the case can differ from the picked file's:
            # `F_[001-002].png`).
            _, first_frame, padding, prefix = frames[0]
            if has_range:
                start_frame = range_start
                end_frame = range_end
            else:
                start_frame = frames[0][0]
                end_frame = frames[-1][0]

        file_count = len(file_names) if file_names is not None else len(frames)
        first_path = file.parent / first_frame
        info = probe_media(first_path)
        frame_rate = info.frame_rate or default_frame_rate
        if info.duration:
            # A first frame with a timeline of its own (an animated GIF) sets
            # the sequence's rate and duration: AE 2026 imports two 14-frame
            # 10 fps GIFs as one 1.4 s sequence at 10 fps.
            duration = info.duration
        elif file_names is not None:
            duration = len(file_names) / frame_rate
        else:
            # Frame-number span, not file count: AE counts absent interior
            # frames as implied placeholders (probed: a 1-12 sequence with
            # frames 6-7 missing imports with a 12-frame duration).
            duration = (end_frame - start_frame + 1) / frame_rate

        source = cls._new(
            file,
            source_format=fmt.source_format,
            width=info.width,
            height=info.height,
            duration=duration,
            frame_rate=frame_rate,
            pixel_aspect=info.pixel_aspect,
            has_alpha=info.has_alpha,
            depth=info.depth,
            media_flag=fmt.media_flag,
            alpha_premultiplied=fmt.alpha_premultiplied,
            audio_sample_rate=0.0,
            icc_profile=info.icc_profile,
            sequence_prefix=prefix,
            sequence_ext=ext,
            sequence_files=file_names,
            start_frame=start_frame,
            end_frame=end_frame,
            frame_padding=padding,
            opti_data=_opti_data(fmt, info, first_path, sequence=True),
            # AE caches the first frame's size times the file count, however
            # large the others are (a 4928-byte first GIF in three files is
            # 14784), on macOS and Windows alike.
            data_size=file_count * first_path.stat().st_size,
            embedded_profile_name=named_media_profile(fmt.source_format, info),
            color_mode=info.color_mode,
            windows=windows,
        )
        source._rate_from_media = bool(info.duration)
        if has_range:
            source._sspc.frame_range_set = True
        return source

    def reload(self) -> None:
        """Reloads the asset from the file.

        Re-reads the media at the stored path and updates the cached
        source metadata in place - dimensions, alpha, frame rate,
        duration, pixel aspect, audio, cached data size, the format
        `opti` header and (for AI/EPS/PDF) the embedded color-profile
        record - like After Effects' File > Reload Footage (byte-validated
        against an AE 2026 reload of a still image whose file changed on
        disk). Image sequences re-scan their sibling frames; the item name
        is never changed. A source bound to one layer of a layered file
        re-measures that layer and keeps its binding, Document/Layer Size
        choice and Layer Options, as After Effects does.

        Note:
            ExtendScript restricts `reload()` to a `mainSource`; py_aep
            also allows it on a `proxySource`. Every chunk it refreshes
            (`sspc`, `opti`, `CLRS`) lives in the source's own `Pin`, so a
            proxy reload is self-contained. The owning item's `idta`
            footage-kind flags are only refreshed for a `mainSource` -
            they describe the main source's kind, and AE keeps them
            pointing at it while a proxy is attached.

        Raises:
            ValueError: If the stored path no longer exists or is no longer
                a file, if its extension is not a supported footage
                format, or if a layer-bound source's file no longer has a
                layer at the stored index.
            NotImplementedError: If the format needs a format-specific
                `opti` header that is not implemented.
        """
        owner = None
        if self._project is not None:
            for item in self._project.items.values():
                if getattr(item, "_main_source", None) is self:
                    owner = item
                    break

        # A path stored for the other platform is read where AE on this one
        # looks for it (`/Users/x` -> `C:\Users\x`).
        host_file = platform_path(self._file, windows=os.name == "nt")
        validate_file_exists(host_file)
        path = Path(host_file)
        fmt = get_file_format(path.suffix)
        if fmt.opti == "unsupported":
            raise NotImplementedError(
                f"footage reload does not support {path.suffix}: After "
                "Effects requires a format-specific opti header that has "
                "not been reverse-engineered yet."
            )

        sspc = self._sspc
        # AE keeps the source's importer across a reload: the rebuilt `opti`
        # names the stored code (a BMP imported on Windows stays `STIL`).
        fmt = fmt._replace(source_format=sspc.source_format_type)
        if self._target_is_folder:
            # Sequence: re-scan sibling frames. The stored native rate is
            # kept as the fallback for rate-less formats (reload does not
            # consult the import preferences).
            #
            # A user-set frame range must survive the re-scan: without it
            # the rebuild would widen the sequence to every sibling frame
            # while the marker still claimed a range. The range bounds are
            # the stored start/end frames.
            if sspc.frame_range_set:
                range_start, range_end = self._start_frame, self._end_frame
            else:
                range_start, range_end = 0, 0
            alphabetical = self._is_alphabetical
            fresh = FileSource._build_sequence(
                path,
                fmt,
                alphabetical,
                sspc.native_frame_rate or 30.0,
                windows=self._windows,
                range_start=range_start,
                range_end=range_end,
            )
            # The duration as frames over rate, unreduced, as the import writes
            # it (the float setter would store 3/30 as 1/10).
            self._adopt_measured(
                fresh,
                "start_frame",
                "end_frame",
                "frame_padding",
                "native_frame_rate",
                "duration_dividend",
                "duration_divisor",
            )
            if alphabetical:
                # An alphabetical sequence re-lists its folder by name.
                stvc = find_by_list_type(chunks=self._pin.chunks, list_type="StVc")
                index = index_by_identity(self._pin.chunks, stvc)
                self._pin.chunks[index] = find_by_list_type(
                    chunks=fresh._pin.chunks, list_type="StVc"
                )
                self._file_names = fresh._file_names
                self._file = fresh._file
        elif self.layer_name:
            # A single layer of a layered file: re-measure that layer, not the
            # merged document. AE 2026 keeps the binding, its Document/Layer
            # Size choice and its Layer Options across a reload (cropped PSD
            # and AI comp layers keep their names and sizes - ae1 probe). The
            # stored index is rebound the way `replace(..., CURRENT_VALUE)`
            # does, and everything is measured before anything is written.
            fresh = FileSource._from_layer(
                path,
                layer_index_for_stored(path, sspc.layer_index),
                dimensions=None if sspc.full_frame else "layer",
                layer_styles=self.layer_styles,
                windows=self._windows,
            )
            self._adopt_measured(fresh, "pixel_aspect", "layer_id")
        else:
            data = path.read_bytes() if fmt.opti == "text" else None
            info = _platform_media_info(
                probe_media(path, data), fmt, windows=self._windows
            )
            sspc.width = info.width
            sspc.height = info.height
            sspc.depth = info.depth
            sspc.alpha_mode_raw = _alpha_mode_raw(
                info.has_alpha, fmt.alpha_premultiplied
            )
            sspc.native_frame_rate = info.frame_rate
            sspc.duration = info.duration
            sspc.pixel_aspect = info.pixel_aspect
            sspc.audio_sample_rate = info.audio_sample_rate
            # AE refreshes the cached source size (probed on a PNG: the file
            # size, 3614 -> 223874 across the reload fixture pair).
            sspc.data_size = _still_data_size(fmt, info, path)
            opti_data = _opti_data(fmt, info, path, sequence=False, data=data)
            if opti_data:
                new_opti = OptiChunk.read(
                    io.BytesIO(opti_data), len(opti_data), chunk_type="opti"
                )
            else:
                new_opti = OptiChunk(chunk_type="opti")
            self._swap_opti(new_opti)
            # AE 2026 restamps the source with the file's current mtime on a
            # reload; a stale stamp makes it re-read the media at every open.
            sspc.source_modified = int(path.stat().st_mtime)
            # Only AI/EPS/PDF carry a re-readable embedded profile. Other
            # formats keep the record they already have: AE writes `empd`
            # for PNG/MOV/MPEG too, and a reload that only re-reads the
            # same pixels must not erase it.
            if fmt.opti == "text":
                self._update_embedded_profile(ai_document_profile(path, data)[1])
        _sync_premultiplied(sspc)

        idta = getattr(owner, "_idta", None)
        if idta is not None:
            idta._flags_17 = self._idta_flags17()
            # AE 2026 restamps the item with the reloaded file's mtime too.
            cast("FootageItem", owner)._sync_modified_time()

    def _swap_opti(self, new_opti: OptiChunk) -> None:
        """Replace the pin's `opti` chunk (and this source's reference)."""
        index = index_by_identity(self._pin.chunks, self._opti)
        self._pin.chunks[index] = new_opti
        self._opti = new_opti

    def _adopt_measured(self, fresh: FileSource, *fields: str) -> None:
        """Take a reloaded source's measurements from `fresh`, the same file
        measured again: its `opti`, and the `sspc` size, depth, alpha, data
        size and source stamp (the file's new mtime: AE 2026 restamps the
        source on reload), plus `fields`."""
        sspc, fresh_sspc = self._sspc, fresh._sspc
        for name in ("width", "height", "depth", "alpha_mode_raw", *fields):
            setattr(sspc, name, getattr(fresh_sspc, name))
        sspc.data_size = fresh_sspc.data_size
        sspc._source_stamp = fresh_sspc._source_stamp
        self._swap_opti(fresh._opti)

    def _update_embedded_profile(self, name: str | None) -> None:
        """Set, update or remove the CLRS embedded-profile record (`empd`
        flag + `Utf8` profile name, in AE's slot right after `apid`)."""
        if self._clrs is None:
            return
        chunks = self._clrs.chunks
        for index, chunk in enumerate(chunks):
            if chunk.chunk_type == "empd":
                if name is None:
                    del chunks[index : index + 2]
                else:
                    cast("Utf8Chunk", chunks[index + 1]).value = name
                return
        if name is not None:
            insert_at = next(
                (i + 1 for i, ch in enumerate(chunks) if ch.chunk_type == "apid"),
                0,
            )
            chunks.insert(insert_at, Utf8Chunk(value=name))
            chunks.insert(insert_at, EmpdChunk())

    def _idta_flags17(self) -> int:
        """Footage-kind flags for `IdtaChunk._flags_17`: bit 5 = has video,
        bit 4 = single still image, bit 2 = has audio. AE rejects an
        audio-only (0x0) file flagged as video, so this is set from the
        source's actual kind."""
        flags = 0
        if self._width > 0:
            flags |= 0x20
        if self.is_still:
            flags |= 0x10
        if self._has_audio:
            flags |= 0x04
        return flags

    @property
    def layer_name(self) -> str:
        """The referenced layer's name when this source is a single layer
        of a layered file (a chosen-layer import or a member of a layered
        comp import), or an empty string for merged/whole-file footage.
        Read-only.

        py_aep extension: ExtendScript exposes no layer-selection API.
        """
        psd_layer = getattr(self._opti, "psd_group_name", "")
        if psd_layer:
            return str(psd_layer)
        # AI/EPS/PDF: a `TEXT` opti carries the layer name as a typed
        # `TextOptiChunk` field (0x44). The name alone marks the binding -
        # the 0x3D byte next to it is the layer's visibility, and AE writes
        # it 0 for a hidden layer's (still layer-bound) footage.
        opti = self._opti
        if isinstance(opti, TextOptiChunk):
            return opti.text_layer_name
        return ""

    @property
    def layer_styles(self) -> str | None:
        """The layer-styles choice recorded for a Photoshop single-layer
        binding: `"editable"`, `"merge"` or `"ignore"` (see
        `ImportOptions.layer_styles`), or `None` when this source is not a
        PSD single-layer binding (merged/whole-document footage, other
        formats). Read-only.

        py_aep extension. `"editable"` appears on the per-layer footage of
        an Editable-Layer-Styles comp import; `FootageItem.replace` rejects
        it as an explicit argument (AE's footage dialog offers merge/ignore
        only) - `CURRENT_VALUE` is the way to preserve it. The byte encoding
        was pinned on AE 2026 output; on much older projects the reported
        value is whatever the byte says.
        """
        if self._sspc.source_format_type != "8BPS" or not self.layer_name:
            return None
        return _C9_TO_LAYER_STYLES.get(self._sspc._reserved_c8[1])

    def _resolve_name(self, raw_name: str) -> str:
        """Resolve the display name for a file-type footage item.

        AE writes the item-level Utf8 chunk only when the user renames the
        item, and then displays that name verbatim - including a name holding
        a `/`, and including the ` 2` suffix AE appends to disambiguate two
        imports of the same layer. An empty chunk means the name is derived
        from the source: a sequence pattern (e.g. `render.[0001-0700].exr`),
        `layername/filename` for a layer-bound source, else the filename.
        """
        item_name = raw_name

        if not item_name:
            if self._duration != 0 and self._target_is_folder:
                item_name = self._build_sequence_name()
            if not item_name:
                # PureWindowsPath handles both / and \ separators,
                # unlike PurePosixPath which only splits on /.
                basename = PureWindowsPath(self._file).name
                layer = self.layer_name
                if layer:
                    item_name = f"{layer}/{basename}"
                else:
                    item_name = basename

        return item_name

    def _build_sequence_name(self) -> str:
        """Build the display name for an image sequence.

        Returns the pattern `prefix[start_frame-end_frame]extension`,
        for example `render.[0001-0700].exr`. The prefix and extension are
        stored as two consecutive Utf8 chunks immediately before the opti
        chunk inside the Pin LIST. An alphabetical sequence is named after
        its folder instead, as AE 2026 does.
        """
        if self._is_alphabetical:
            return PureWindowsPath(self._file).parent.name
        start_frame = self._start_frame
        end_frame = self._end_frame
        if UNDEFINED_FRAME in (start_frame, end_frame):
            return ""

        try:
            utf8_before_opti = find_chunks_before(
                chunks=self._pin.chunks,
                chunk_type="Utf8",
                before_type="opti",
            )
        except ChunkNotFoundError:
            utf8_before_opti = []

        if len(utf8_before_opti) < 2:
            return ""

        prefix = cast("Utf8Chunk", utf8_before_opti[-2]).value
        extension = cast("Utf8Chunk", utf8_before_opti[-1]).value

        if not prefix and not extension:
            return ""

        frame_padding = self._sspc.frame_padding
        frame_range = f"[{start_frame:0{frame_padding}d}-{end_frame:0{frame_padding}d}]"
        return f"{prefix}{frame_range}{extension}"
