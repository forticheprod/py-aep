from __future__ import annotations

from pathlib import PureWindowsPath
from typing import TYPE_CHECKING, cast

from ...binary.footage_chunks import (
    PlaceholderOptiChunk,
    SoliOptiChunk,
)
from ...binary.utils import (
    UNDEFINED_FRAME,
    ChunkNotFoundError,
    find_chunks_before,
)
from ..descriptors import ChunkField, ComputedField
from ..sources.file import FileSource
from ..sources.footage import (
    _compute_conform_frame_rate,
    _compute_display_frame_rate,
)
from ..sources.solid import SolidSource
from ..transforms import compute_fractional, compute_ratio
from .av_item import AVItem

if TYPE_CHECKING:
    from ...binary.chunk import ListChunk
    from ...binary.footage_chunks import (
        OptiChunk,
        SspcChunk,
    )
    from ...binary.item_chunks import IdtaChunk
    from ...binary.scalar_chunks import CmtaChunk, Utf8Chunk
    from ..project import Project
    from ..sources.placeholder import PlaceholderSource
    from .folder import FolderItem


def _compute_fi_duration(body: SspcChunk) -> float:
    """Total duration in seconds (with conform and loop)."""
    source_duration = body.duration_dividend / body.duration_divisor
    conform = _compute_conform_frame_rate(body)
    if conform != 0:
        native = compute_fractional(
            body, "native_frame_rate_integer", "native_frame_rate_fractional",
        )
        conform_factor = native / conform
    else:
        conform_factor = 1.0
    return source_duration * conform_factor * body.loop


def _compute_fi_frame_duration(body: SspcChunk) -> int:
    return int(_compute_fi_duration(body) * _compute_display_frame_rate(body))


def _compute_fi_pixel_aspect(body: SspcChunk) -> float:
    return compute_ratio(body, "pixel_ratio_dividend", "pixel_ratio_divisor")


def _compute_fi_has_audio(body: SspcChunk) -> bool:
    return body.audio_sample_rate > 0


class FootageItem(AVItem):
    """
    The `FootageItem` object represents a footage item imported into a project,
    which appears in the Project panel.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        footage = app.project.footages[0]
        print(footage.main_source)
        ```

    Info:
        `FootageItem` is a subclass of [AVItem][] object, which is a subclass of
        [Item][] object. All methods and attributes of [AVItem][] and [Item][] are
        available when working with `FootageItem`.

    See: https://ae-scripting.docsforadobe.dev/item/footageitem/
    """

    width = ChunkField[int]("_sspc", "width", read_only=True)
    """The width of the item in pixels. Read-only."""

    height = ChunkField[int]("_sspc", "height", read_only=True)
    """The height of the item in pixels. Read-only."""

    duration = ComputedField[float]("_sspc", compute=_compute_fi_duration)
    """The duration of the item in seconds. Still footages have a duration
    of 0. Read-only."""

    frame_rate = ComputedField[float]("_sspc", compute=_compute_display_frame_rate)
    """The frame rate of the item in frames-per-second. Read-only."""

    frame_duration = ComputedField[int]("_sspc", compute=_compute_fi_frame_duration)
    """The duration of the item in frames. Still footages have a duration
    of 0. Read-only."""

    pixel_aspect = ComputedField[float]("_sspc", compute=_compute_fi_pixel_aspect)
    """The pixel aspect ratio of the item (1.0 is square). Read-only."""

    footage_missing = ChunkField[bool](
        "_sspc",
        "footage_missing_at_save",
        read_only=True,
    )
    """When `True`, the AVItem is a placeholder, or represents footage with a
    source file that could not be found when the project was last saved.

    In this case, the path of the missing source file is in the
    `missing_footage_path` attribute of the footage item's source-file object.
    See [FootageItem.main_source][] and
    [FileSource.missing_footage_path][py_aep.models.sources.file.FileSource.missing_footage_path].
    Read-only."""

    has_audio = ComputedField[bool]("_sspc", compute=_compute_fi_has_audio)
    """When `True`, the footage has an audio component. Read-only."""

    start_frame = ChunkField[int]("_sspc", "start_frame", read_only=True)
    """The footage start frame. Read-only."""

    end_frame = ChunkField[int]("_sspc", "end_frame", read_only=True)
    """The footage end frame. Read-only."""

    def __init__(
        self,
        *,
        _idta: IdtaChunk,
        _name_utf8: Utf8Chunk,
        _cmta: CmtaChunk | None,
        _item_list: ListChunk,
        _gide: ListChunk | None,
        _sspc: SspcChunk,
        _opti: OptiChunk,
        project: Project,
        parent_folder: FolderItem,
        main_source: FileSource | SolidSource | PlaceholderSource,
        proxy_source: FileSource | SolidSource | PlaceholderSource | None,
    ) -> None:
        super().__init__(
            _idta=_idta,
            _name_utf8=_name_utf8,
            _cmta=_cmta,
            _item_list=_item_list,
            _gide=_gide,
            project=project,
            parent_folder=parent_folder,
            type_name="Footage",
            proxy_source=proxy_source,
        )
        self._sspc = _sspc
        self._opti = _opti
        self._main_source = main_source
        # Store resolved display name in __dict__ so the ChunkField
        # getter returns it without mutating the binary Utf8 chunk.
        self.__dict__["name"] = self._resolve_name(_name_utf8.value)

    @property
    def main_source(self) -> FileSource | SolidSource | PlaceholderSource:
        """The footage source. Read-only."""
        return self._main_source

    @property
    def asset_type(self) -> str:
        """The footage type (placeholder, solid, file). Read-only."""
        if isinstance(self._main_source, SolidSource):
            return "solid"
        if isinstance(self._main_source, FileSource):
            return "file"
        return "placeholder"

    @property
    def file(self) -> str | None:
        """The footage file path if its source is a [FileSource][], else `None`."""
        if hasattr(self._main_source, "file"):
            return self._main_source.file
        return None

    def _resolve_name(self, raw_name: str) -> str:
        """Derive the display name for this footage item.

        Placeholder and solid names come directly from the opti chunk.
        File footage names are derived from the file path, with special
        handling for image sequences and PSD groups.
        """
        if isinstance(self._main_source, SolidSource):
            return str(cast("SoliOptiChunk", self._opti).solid_name)
        if not isinstance(self._main_source, FileSource):
            # Placeholder
            return cast("PlaceholderOptiChunk", self._opti).placeholder_name
        return self._resolve_file_name(raw_name)

    def _resolve_file_name(self, raw_name: str) -> str:
        """Resolve the display name for a file-type footage item.

        AE stores the full file path in the Utf8 chunk but displays only
        the filename. Builds sequence names (e.g. `render.[0001-0700].exr`)
        when appropriate.
        """
        file_source = cast("FileSource", self._main_source)

        # Strip to basename so the item name matches AE's UI.
        item_name = raw_name
        if item_name and ("/" in item_name or "\\" in item_name):
            item_name = ""

        if not item_name:
            if self.duration != 0 and file_source.target_is_folder:
                item_name = self._build_sequence_name()
            if not item_name:
                # PureWindowsPath handles both / and \ separators,
                # unlike PurePosixPath which only splits on /.
                basename = PureWindowsPath(file_source.file).name
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

        file_source = cast("FileSource", self._main_source)
        try:
            utf8_before_opti = find_chunks_before(
                chunks=file_source._pin.chunks,
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
