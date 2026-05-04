from __future__ import annotations

import re
import typing
from pathlib import PurePosixPath
from typing import cast

from ...binary.footage_chunks import PsdOptiChunk
from ...binary.utils import (
    UNDEFINED_FRAME,
    ChunkNotFoundError,
    filter_by_type,
    find_by_list_type,
    find_chunks_before,
    parse_alas_data,
    str_value,
)
from ..transforms import strip_null
from .footage import FootageSource

if typing.TYPE_CHECKING:
    from ...binary.chunk import ListChunk
    from ...binary.footage_chunks import OptiChunk, SspcChunk
    from ...binary.scalar_chunks import U1Chunk


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
            utf8_chunks = filter_by_type(
                chunks=stvc_chunk.chunks, chunk_type="Utf8"
            )
            self._file_names = [str_value(chunk) for chunk in utf8_chunks]
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
                prefix = str_value(utf8_before_opti[-2])
                extension = str_value(utf8_before_opti[-1])
                if prefix or extension:
                    first_frame = (
                        f"{prefix}{_sspc.start_frame:0{_sspc.frame_padding}d}"
                        f"{extension}"
                    )
                    self._file = str(PurePosixPath(self._file) / first_frame)

        if getattr(_opti, "asset_type", "") == "8BPS":
            psd_opti = cast(PsdOptiChunk, _opti)
            self._file_attributes: dict[str, int | str] = {
                "psd_layer_index": psd_opti.psd_layer_index,
                "psd_group_name": strip_null(psd_opti.psd_group_name or ""),
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
