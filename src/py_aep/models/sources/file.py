from __future__ import annotations

import io
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, cast

from ...binary.footage_chunks import (
    OptiChunk,
    PsdOptiChunk,
    SspcChunk,
    build_ai_layer_opti_data,
    build_generic_opti_data,
    build_psd_layer_opti_data,
    build_psd_opti_data,
    build_rhdr_opti_data,
    build_text_opti_data,
    build_tiff_opti_data,
)
from ...binary.misc_chunks import EmpdChunk
from ...binary.mutations import build_pin_list
from ...binary.scalar_chunks import Utf8Chunk
from ...binary.utils import (
    UNDEFINED_FRAME,
    ChunkNotFoundError,
    build_als2_list,
    filter_by_type,
    find_by_list_type,
    find_by_type,
    find_chunks_before,
    index_by_identity,
    parse_alas_data,
)
from ...data.file_formats import (
    AI_COMP_EXTENSIONS,
    FORMAT_3D_MODEL_SCENE,
    PSD_COMP_EXTENSIONS,
    FileFormat,
    get_file_format,
)
from ...resolvers.ai_layers import read_ai_color_info, read_ai_color_profile
from ...resolvers.media_probe import probe_media
from ...resolvers.psd_styles import has_enabled_styles
from ...resolvers.source_layers import resolve_ai_layer, resolve_psd_layer
from ..validators import validate_file_exists
from .footage import FootageSource

if TYPE_CHECKING:
    import os

    from ...binary.chunk import Chunk, ListChunk
    from ...binary.scalar_chunks import U1Chunk
    from ...resolvers.media_probe import MediaInfo
    from ...resolvers.psd_layers import PsdLayer


def _reject_styled_layer_size(path: Path, leaf: PsdLayer) -> None:
    """Refuse merge-mode Layer Size dimensions for a layer with styles.

    Merging styles expands the rasterized content box (shadow/glow extents),
    and the expanded box - which AE derives with its style renderer - sets
    the footage dimensions here. py_aep cannot compute it; see
    `docs/limitations.md`.
    """
    if has_enabled_styles(leaf):
        raise NotImplementedError(
            f"layer {leaf.name!r} of {path.name} has layer styles: merging "
            'them expands the rasterized bounds, so layer_dimensions="layer" '
            'is not representable; import at "document" size or pass '
            'layer_styles="ignore"'
        )


def _opti_data(fmt: FileFormat, info: MediaInfo, *, sequence: bool) -> bytes:
    """Select the `opti` asset-info body for a file source.

    Rules verified against AE 2026:

    - TIFF (still or sequence): always needs the 602-byte `TIF ` header;
      an empty or generic header crashes AE for TIFF regardless of whether
      it is a still or a sequence.
    - PSD: AE writes an empty opti for both stills and sequences; our code
      generates a `PsdOptiChunk` with typed fields whose `write()` produces
      the 602-byte header, which AE accepts on re-open.
    - PNG/EXR singles: empty opti is fine (AE re-reads the located file).
    - PNG/EXR sequences and all audio/video formats: need the 58-byte
      generic header so AE recognises the item as a sequence or media file
      rather than missing footage.
    - HDR (Radiance): needs the 30-byte format-specific `RHDR` header;
      dimensions live in `sspc`, not the opti.
    - AI/EPS/PDF: need the 596-byte `TEXT` header with width/height
      embedded as big-endian u16.
    """
    if fmt.opti == "tiff":
        return build_tiff_opti_data(info.width, info.height)
    if fmt.opti == "psd":
        return build_psd_opti_data(
            info.width, info.height, info.bit_depth, info.layer_count
        )
    if fmt.opti == "hdr":
        return build_rhdr_opti_data()
    if fmt.opti == "text":
        return build_text_opti_data(info.width, info.height)
    if fmt.opti == "empty" and not sequence:
        return b""
    return build_generic_opti_data(fmt.source_format)


def _alpha_mode_raw(has_alpha: bool, premultiplied: bool) -> int:
    """The `sspc` alpha byte AE stores: 3 = no alpha, 1 = premultiplied,
    0 = straight."""
    if not has_alpha:
        return 3
    return 1 if premultiplied else 0


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

        # Resolve undefined start/end frames from StVc filenames.
        # The frame number is the last digit group in each filename
        # (e.g. "render.0101.exr" > 101).
        if _sspc.start_frame == UNDEFINED_FRAME and self._file_names:
            first_match = re.search(r"(\d+)\D*$", self._file_names[0])
            if first_match is not None:
                _sspc.start_frame = int(first_match.group(1))
        if _sspc.end_frame == UNDEFINED_FRAME and self._file_names:
            last_match = re.search(r"(\d+)\D*$", self._file_names[-1])
            if last_match is not None:
                _sspc.end_frame = int(last_match.group(1))

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
        alpha_premultiplied: bool = False,
        audio_sample_rate: float = 0.0,
        sequence_prefix: str | None = None,
        sequence_ext: str | None = None,
        start_frame: int = 0,
        end_frame: int = 0,
        frame_padding: int = 0,
        opti_data: bytes = b"",
        embedded_profile_name: str | None = None,
        full_frame: bool = True,
        layer_name: str = "",
        layer_id: int | None = None,
        layer_index: int | None = None,
        data_size: int = 0,
        reserved_c8: bytes | None = None,
    ) -> FileSource:
        """Create a new file footage source with backing chunks.

        AE caches all of this metadata in `sspc` and does not re-read the
        media on open, so the caller must supply correct values (see
        `resolvers.media_probe`). The `opti` asset-info chunk is left empty;
        AE locates the file via the `alas` path.

        Args:
            file: Path to the source file (single), or to a representative
                frame (sequence; the containing folder is stored).
            source_format: 4-char `sspc` source-format code (see
                `data/file_formats.py`).
            width: Pixel width (0 for audio-only media).
            height: Pixel height (0 for audio-only media).
            duration: Duration in seconds (0 for a still image).
            frame_rate: Native frame rate in fps (0 for stills/audio).
            pixel_aspect: Pixel aspect ratio.
            has_alpha: Whether the footage has an alpha channel.
            alpha_premultiplied: When `has_alpha`, select PREMULTIPLIED
                rather than the STRAIGHT default.
            audio_sample_rate: Audio sample rate in Hz (0 = no audio).
            sequence_prefix: Filename text before the frame number. When not
                `None`, the source is an image sequence.
            sequence_ext: Filename extension including the dot (sequence only).
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
        """
        is_sequence = sequence_prefix is not None
        path = Path(file)

        if reserved_c8 is None:
            # AE 2026 writes byte 0xC9 = 0x02 for raster/media file footage but
            # 0x00 for TEXT (AI/EPS/PDF); solids/placeholders keep the all-zero
            # default. Verified across the AE-resaved import fixtures. Layer-
            # bound and merged-PSD sources override this (chosen PSD layer =
            # 0x01, chosen AI layer = 0x02, merged PSD = 0x03; from the
            # choose_layer_*.aep fixtures).
            reserved_c8 = b"\x00\x00" if source_format == "TEXT" else b"\x00\x02"
        sspc = SspcChunk(
            source_format_type=source_format,
            width=width,
            height=height,
            alpha_mode_raw=_alpha_mode_raw(has_alpha, alpha_premultiplied),
            footage_missing_at_save=False,
            is_synthetic_a=0,
            is_synthetic_b=0,
            is_synthetic_c=0,
            full_frame=full_frame,
            reserved_c8=reserved_c8,
            data_size=data_size,
        )
        if layer_id is not None:
            sspc.layer_id = layer_id
        if layer_index is not None:
            sspc.layer_index = layer_index
        sspc.native_frame_rate = frame_rate
        sspc.duration = duration
        sspc.pixel_aspect = pixel_aspect
        sspc.audio_sample_rate = audio_sample_rate
        if source_format == FORMAT_3D_MODEL_SCENE:
            # AE 2026 sets the premultiplied-alpha flag for an imported FBX
            # scene even though `alpha_mode_raw` stays 0 (the 3D scene renders
            # against a premultiplied black background). Measured against an
            # AE-resaved crystal.fbx; every other format leaves the bit clear.
            sspc.premultiplied = True
        if is_sequence:
            sspc.start_frame = start_frame
            sspc.end_frame = end_frame
            sspc.frame_padding = frame_padding
            # AE tags image sequences with these flags; without them it
            # treats the folder reference as missing footage on open.
            # (Values reverse-engineered from AE 2026 sequence imports.)
            sspc._reserved_a8 = b"\x00\x00\x00\x02"
            sspc._reserved_b8 = b"\x01"
            sspc._reserved_ba = b"\x01\x01"
            sspc._reserved_6f = b"\x00\x00\x00\x00\x08"
            # Sequence-specific sspc fields AE writes and does NOT recompute
            # on open (proven necessary by an AE open+resave diff: AE
            # preserves py's value rather than normalizing it). full_frame is
            # False for a sequence, the 0xC8 kind bytes are 0x0000 (not the
            # 0x0002 raster-media default), and byte 5 of the field-separation
            # block is 0x01. The other sequence-import diffs (duration
            # divisor reduction, _reserved_3e, the _reserved_74 filesystem
            # fingerprint, and the cached data_size) are cosmetic: AE
            # recomputes them on open, so py leaves them at their defaults.
            sspc.full_frame = False
            sspc._reserved_c8 = b"\x00\x00"
            sspc._reserved_4a = b"\x00\x00\x00\x00\x00\x01\x00\x00\x00"

        # Route through variant dispatch so a recognized asset type (e.g.
        # 8BPS -> PsdOptiChunk) is stored as its typed subclass and exposes
        # file_attributes immediately, not just after a save/reparse.
        if opti_data:
            opti = OptiChunk.read(
                io.BytesIO(opti_data), len(opti_data), chunk_type="opti"
            )
        else:
            opti = OptiChunk(chunk_type="opti")

        fullpath = str(path.parent) if is_sequence else str(path)
        path_chunks: list[Chunk] = [
            build_als2_list(fullpath, target_is_folder=is_sequence)
        ]
        if is_sequence:
            path_chunks.append(Utf8Chunk(value=sequence_prefix or ""))
            path_chunks.append(Utf8Chunk(value=sequence_ext or ""))

        pin = build_pin_list(
            sspc,
            opti,
            path_chunks=path_chunks,
            embedded_profile_name=embedded_profile_name,
            layer_name=layer_name,
        )
        clrs = find_by_list_type(chunks=pin.chunks, list_type="CLRS")
        linl = cast("U1Chunk", find_by_type(chunks=clrs.chunks, chunk_type="linl"))

        return cls(_pin=pin, _sspc=sspc, _opti=opti, _linl=linl, _clrs=clrs)

    @classmethod
    def _from_file(
        cls,
        file: str | os.PathLike[str],
        *,
        sequence: bool = False,
        force_alphabetical: bool = False,
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
            default_sequence_fps: Frame rate for formats with no native
                rate (AE's "Import Options Default Sequence FPS"
                preference; AE's factory value is 30).
            range_start: First frame number of the sequence clipping range
                (see `ImportOptions.range_start`). 0 with `range_end` 0
                imports every frame.
            range_end: Last frame number of the clipping range, inclusive.

        Raises:
            ValueError: If the extension is not a supported footage format,
                or the frame range is invalid.
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
        if sequence:
            return cls._build_sequence(
                path,
                fmt,
                force_alphabetical,
                default_sequence_fps,
                range_start=range_start,
                range_end=range_end,
            )
        info = probe_media(path)
        opti_data = _opti_data(fmt, info, sequence=False)
        # AI/EPS/PDF carry an embedded ICC profile AE records in CLRS.
        profile_name = read_ai_color_profile(path) if fmt.opti == "text" else None
        if fmt.opti == "psd":
            # Merged PSD footage: AE writes kind 0x0003 and the canvas
            # pixel-buffer size - RGBA when the composite has alpha, the
            # actual channel count otherwise (choose_layer_merged /
            # replace_from_merged / flattened_rgb_comp AE 2026 fixtures;
            # the byte scale beyond 8 bpc is extrapolated).
            channels_eff = 4 if info.has_alpha else info.channels
            reserved_c8: bytes | None = b"\x00\x03"
            data_size = info.width * info.height * channels_eff * (info.bit_depth // 8)
        else:
            reserved_c8 = None
            data_size = 0
        return cls._new(
            path,
            source_format=fmt.source_format,
            width=info.width,
            height=info.height,
            duration=info.duration,
            frame_rate=info.frame_rate,
            pixel_aspect=info.pixel_aspect,
            has_alpha=info.has_alpha,
            alpha_premultiplied=fmt.alpha_premultiplied,
            audio_sample_rate=info.audio_sample_rate,
            opti_data=opti_data,
            embedded_profile_name=profile_name,
            data_size=data_size,
            reserved_c8=reserved_c8,
        )

    @classmethod
    def _from_layer(
        cls,
        file: str | os.PathLike[str],
        layer_index: int,
        *,
        dimensions: str | None = None,
        layer_styles: str | None = None,
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
                canvas; `"layer"` to the layer's content box (PSD only:
                computing an AI/PDF layer's artwork bounds would require
                rendering the PDF content).
            layer_styles: PSD only - the Layer Options choice recorded in
                the `sspc` kind byte: `"merge"` (default), `"ignore"`, or
                `"editable"` (reachable only via replace's CURRENT_VALUE
                pass-through). Callers validate; ignored for AI/PDF.

        Raises:
            ValueError: If the file is not a layered format, or `layer_index`
                is out of range.
            NotImplementedError: For `dimensions="layer"` on an AI/PDF file,
                or for merge-mode dimensions="layer" on a styled PSD layer
                (the style-expanded content box is not derivable; see
                `docs/limitations.md`).
        """
        validate_file_exists(file)
        path = Path(file)
        suffix = path.suffix.lower()
        if suffix in PSD_COMP_EXTENSIONS:
            info = probe_media(path)
            fmt = get_file_format(suffix)
            leaf = resolve_psd_layer(path, layer_index)
            left, top, right, bottom = leaf.bounds
            content_w = max(right - left, 0)
            content_h = max(bottom - top, 0)
            styles = "merge" if layer_styles is None else layer_styles
            if dimensions == "layer" and styles == "merge":
                _reject_styled_layer_size(path, leaf)
            if dimensions == "layer":
                width, height = content_w, content_h
            else:
                width, height = info.width, info.height
            opti_data = build_psd_layer_opti_data(
                info.width,
                info.height,
                info.bit_depth,
                info.layer_count,
                leaf.record_index,
                leaf.layer_id,
                leaf.name,
                leaf.bounds,
                leaf.is_adjustment,
            )
            return cls._new(
                path,
                source_format=fmt.source_format,
                width=width,
                height=height,
                duration=info.duration,
                frame_rate=info.frame_rate,
                pixel_aspect=info.pixel_aspect,
                has_alpha=info.has_alpha,
                alpha_premultiplied=fmt.alpha_premultiplied,
                audio_sample_rate=info.audio_sample_rate,
                opti_data=opti_data,
                full_frame=dimensions != "layer",
                layer_name=leaf.name,
                layer_id=leaf.layer_id,
                layer_index=leaf.record_index,
                data_size=content_w * content_h * 4 * (info.bit_depth // 8),
                reserved_c8=PSD_LAYER_STYLES_C8[styles],
            )
        if suffix in AI_COMP_EXTENSIONS:
            if dimensions == "layer":
                raise NotImplementedError(
                    "Layer Size dimensions for an AI/PDF layer require the "
                    "layer's artwork bounds, which py_aep cannot compute; "
                    "use 'document' (note: AE's own dialog defaults to "
                    "Layer Size for AI/PDF)."
                )
            data = path.read_bytes()
            info = probe_media(path, data)
            fmt = get_file_format(suffix)
            index, layer_name = resolve_ai_layer(path, layer_index, data)
            color_space, profile_name = read_ai_color_info(path, data)
            opti_data = build_ai_layer_opti_data(
                info.width, info.height, layer_name, color_space
            )
            return cls._new(
                path,
                source_format=fmt.source_format,
                width=info.width,
                height=info.height,
                duration=info.duration,
                frame_rate=info.frame_rate,
                pixel_aspect=info.pixel_aspect,
                has_alpha=info.has_alpha,
                alpha_premultiplied=fmt.alpha_premultiplied,
                audio_sample_rate=info.audio_sample_rate,
                opti_data=opti_data,
                embedded_profile_name=profile_name,
                layer_name=layer_name,
                layer_index=index,
                data_size=len(data),
                reserved_c8=b"\x00\x02",
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
        """
        stem = file.stem
        m = re.search(r"(\d+)$", stem)
        if m is None:
            raise ValueError(
                f"Sequence import requires a numbered filename, got {file.name!r}"
            )
        prefix = stem[: m.start()]
        ext = file.suffix
        padding = len(m.group(1))

        has_range = range_start > 0 or range_end > 0
        if has_range and range_end == 0:
            # AE errors at import time ("Found no matches for the selected
            # file name") when a start is set without an end.
            raise ValueError("a sequence range start requires a range end")
        if has_range and range_end < range_start:
            raise ValueError("Range end cannot be less than range start")

        frame_re = re.compile(re.escape(prefix) + r"(\d+)$")
        frames: list[tuple[int, str]] = []
        for sibling in file.parent.iterdir():
            if sibling.suffix.lower() != ext.lower():
                continue
            sm = frame_re.match(sibling.stem)
            if sm is not None:
                frames.append((int(sm.group(1)), sibling.name))
        if not frames:
            frames = [(int(m.group(1)), file.name)]

        if has_range:
            frames = [fr for fr in frames if range_start <= fr[0] <= range_end]
            if not frames:
                raise ValueError(
                    f"no sequence frames numbered within [{range_start}, {range_end}]"
                )

        frames.sort(key=lambda fr: fr[1] if force_alphabetical else fr[0])

        info = probe_media(file.parent / frames[0][1])
        frame_rate = info.frame_rate or default_frame_rate
        if has_range:
            start_frame = range_start
            end_frame = range_end
        else:
            start_frame = frames[0][0]
            end_frame = frames[-1][0]
        if force_alphabetical:
            duration = len(frames) / frame_rate
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
            alpha_premultiplied=fmt.alpha_premultiplied,
            audio_sample_rate=0.0,
            sequence_prefix=prefix,
            sequence_ext=ext,
            start_frame=start_frame,
            end_frame=end_frame,
            frame_padding=padding,
            opti_data=_opti_data(fmt, info, sequence=True),
        )
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
        is never changed.

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
                a file, or if its extension is not a supported footage
                format.
            NotImplementedError: If the format needs a format-specific
                `opti` header that is not implemented.
        """
        owner = None
        if self._project is not None:
            for item in self._project.items.values():
                if getattr(item, "_main_source", None) is self:
                    owner = item
                    break

        validate_file_exists(self._file)
        path = Path(self._file)
        fmt = get_file_format(path.suffix)
        if fmt.opti == "unsupported":
            raise NotImplementedError(
                f"footage reload does not support {path.suffix}: After "
                "Effects requires a format-specific opti header that has "
                "not been reverse-engineered yet."
            )

        sspc = self._sspc
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
                range_start, range_end = sspc.start_frame, sspc.end_frame
            else:
                range_start, range_end = 0, 0
            fresh = FileSource._build_sequence(
                path,
                fmt,
                False,
                sspc.native_frame_rate or 30.0,
                range_start=range_start,
                range_end=range_end,
            )
            fresh_sspc = fresh._sspc
            sspc.width = fresh_sspc.width
            sspc.height = fresh_sspc.height
            sspc.alpha_mode_raw = fresh_sspc.alpha_mode_raw
            sspc.start_frame = fresh_sspc.start_frame
            sspc.end_frame = fresh_sspc.end_frame
            sspc.frame_padding = fresh_sspc.frame_padding
            sspc.native_frame_rate = fresh_sspc.native_frame_rate
            sspc.duration = fresh_sspc.duration
            self._swap_opti(fresh._opti)
        else:
            info = probe_media(path)
            sspc.width = info.width
            sspc.height = info.height
            sspc.alpha_mode_raw = _alpha_mode_raw(
                info.has_alpha, fmt.alpha_premultiplied
            )
            sspc.native_frame_rate = info.frame_rate
            sspc.duration = info.duration
            sspc.pixel_aspect = info.pixel_aspect
            sspc.audio_sample_rate = info.audio_sample_rate
            # AE refreshes the cached source size to the file's byte size
            # (probed: 3614 -> 223874 across the reload fixture pair).
            sspc.data_size = path.stat().st_size
            opti_data = _opti_data(fmt, info, sequence=False)
            if opti_data:
                new_opti = OptiChunk.read(
                    io.BytesIO(opti_data), len(opti_data), chunk_type="opti"
                )
            else:
                new_opti = OptiChunk(chunk_type="opti")
            self._swap_opti(new_opti)
            # Only AI/EPS/PDF carry a re-readable embedded profile. Other
            # formats keep the record they already have: AE writes `empd`
            # for PNG/MOV/MPEG too, and a reload that only re-reads the
            # same pixels must not erase it.
            if fmt.opti == "text":
                self._update_embedded_profile(read_ai_color_profile(path))

        idta = getattr(owner, "_idta", None)
        if idta is not None:
            idta._flags_17 = self._idta_flags17()

    def _swap_opti(self, new_opti: OptiChunk) -> None:
        """Replace the pin's `opti` chunk (and this source's reference)."""
        index = index_by_identity(self._pin.chunks, self._opti)
        self._pin.chunks[index] = new_opti
        self._opti = new_opti

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
        # AI/EPS/PDF: raw TEXT opti with a per-layer-reference flag at 0x3D
        # and the NUL-terminated layer name at 0x44.
        data = self._opti.data
        if len(data) > 0x44 and data[:4] == b"TEXT" and data[0x3D] == 1:
            return data[0x44:].split(b"\x00", 1)[0].decode("utf-8", "replace")
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

        AE stores the full file path in the Utf8 chunk but displays only
        the filename. Builds sequence names (e.g. `render.[0001-0700].exr`)
        when appropriate, and `layername/filename` for layer-bound sources.
        """
        # Strip to basename so the item name matches AE's UI.
        item_name = raw_name
        if item_name and ("/" in item_name or "\\" in item_name):
            item_name = ""

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
        chunk inside the Pin LIST.
        """
        start_frame = self._sspc.start_frame
        end_frame = self._sspc.end_frame
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
