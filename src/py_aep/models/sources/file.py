from __future__ import annotations

import io
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, cast

from ...binary.footage_chunks import (
    OptiChunk,
    PsdOptiChunk,
    SspcChunk,
    build_generic_opti_data,
    build_psd_opti_data,
    build_rhdr_opti_data,
    build_text_opti_data,
    build_tiff_opti_data,
)
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
    parse_alas_data,
)
from ...data.file_formats import FileFormat, get_file_format
from ...resolvers.ai_layers import read_ai_color_profile
from ...resolvers.media_probe import probe_media
from ..validators import validate_path_exists
from .footage import FootageSource

if TYPE_CHECKING:
    import os

    from ...binary.chunk import Chunk, ListChunk
    from ...binary.scalar_chunks import U1Chunk
    from ...resolvers.media_probe import MediaInfo


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
          the PSD file. `0xFFFF` means merged/flattened.
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
            self._file = str(
                PurePosixPath(alas_data.get("fullpath", "")) / self._file_names[0]
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
                    self._file = str(PurePosixPath(self._file) / first_frame)

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
                cropped to its content box (`COMP_CROPPED_LAYERS`).
        """
        is_sequence = sequence_prefix is not None
        path = Path(file)

        if not has_alpha:
            alpha_raw = 3
        elif alpha_premultiplied:
            alpha_raw = 1
        else:
            alpha_raw = 0

        sspc = SspcChunk(
            source_format_type=source_format,
            width=width,
            height=height,
            alpha_mode_raw=alpha_raw,
            footage_missing_at_save=False,
            is_synthetic_a=0,
            is_synthetic_b=0,
            is_synthetic_c=0,
        )
        sspc.native_frame_rate = frame_rate
        sspc.duration = duration
        sspc.pixel_aspect = pixel_aspect
        sspc.audio_sample_rate = audio_sample_rate
        # AE 2026 writes this reserved template for every file footage source
        # (solids/placeholders leave it all-zero). Byte 0xC7 (index 3) is 1 when
        # the footage spans the full source frame, 0 for a layer cropped to its
        # content box (COMP_CROPPED_LAYERS); byte 0xC9 is a constant 2.
        sspc._reserved_c4 = (
            b"\x00\x00\x00" + (b"\x01" if full_frame else b"\x00") + b"\x00\x02"
        )
        if is_sequence:
            sspc.start_frame = start_frame
            sspc.end_frame = end_frame
            sspc.frame_padding = frame_padding
            # AE tags image sequences with these flags; without them it
            # treats the folder reference as missing footage on open.
            # (Values reverse-engineered from AE 2026 sequence imports.)
            sspc._reserved_a8 = b"\x00\x00\x00\x02"
            sspc._reserved_b8 = b"\x01\x00\x01\x01"
            sspc._reserved_6f = b"\x00\x00\x00\x00\x08"

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

        Raises:
            ValueError: If the extension is not a supported footage format.
            NotImplementedError: If After Effects requires a format-specific
                `opti` header that is not implemented yet, or header probing
                is unavailable for the format.
        """
        validate_path_exists(file)
        path = Path(file)
        fmt = get_file_format(path.suffix)
        if fmt.opti == "unsupported":
            raise NotImplementedError(
                f"footage import does not yet support {path.suffix}: After "
                "Effects requires a format-specific opti header that has not "
                "been reverse-engineered yet."
            )
        if sequence:
            return cls._build_sequence(path, fmt, force_alphabetical)
        info = probe_media(path)
        opti_data = _opti_data(fmt, info, sequence=False)
        # AI/EPS/PDF carry an embedded ICC profile AE records in CLRS.
        profile_name = read_ai_color_profile(path) if fmt.opti == "text" else None
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
        )

    @classmethod
    def _build_sequence(
        cls,
        file: Path,
        fmt: FileFormat,
        force_alphabetical: bool,
    ) -> FileSource:
        """Build a sequence `FileSource` by scanning sibling frames."""
        stem = file.stem
        m = re.search(r"(\d+)$", stem)
        if m is None:
            raise ValueError(
                f"Sequence import requires a numbered filename, got {file.name!r}"
            )
        prefix = stem[: m.start()]
        ext = file.suffix
        padding = len(m.group(1))

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

        frames.sort(key=lambda fr: fr[1] if force_alphabetical else fr[0])

        info = probe_media(file)
        frame_rate = info.frame_rate or 30.0
        duration = len(frames) / frame_rate

        return cls._new(
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
            start_frame=frames[0][0],
            end_frame=frames[-1][0],
            frame_padding=padding,
            opti_data=_opti_data(fmt, info, sequence=True),
        )

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

    def _resolve_name(self, raw_name: str) -> str:
        """Resolve the display name for a file-type footage item.

        AE stores the full file path in the Utf8 chunk but displays only
        the filename. Builds sequence names (e.g. `render.[0001-0700].exr`)
        when appropriate.
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
                psd_group = getattr(self._opti, "psd_group_name", "")
                if psd_group:
                    item_name = f"{psd_group}/{basename}"
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
