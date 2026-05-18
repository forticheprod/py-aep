from __future__ import annotations

from typing import TYPE_CHECKING

from ..sources.file import FileSource
from ..sources.placeholder import PlaceholderSource
from ..sources.solid import SolidSource
from .av_item import AVItem

if TYPE_CHECKING:
    from ...binary.chunk import ListChunk
    from ...binary.item_chunks import CmtaChunk, IdtaChunk
    from ...binary.scalar_chunks import Utf8Chunk
    from ..project import Project
    from .folder import FolderItem


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

    @property
    def width(self) -> int:  # type: ignore[override]
        """The width of the item in pixels. Read-only."""
        return self._main_source._width

    @property
    def height(self) -> int:  # type: ignore[override]
        """The height of the item in pixels. Read-only."""
        return self._main_source._height

    @property
    def duration(self) -> float:  # type: ignore[override]
        """The duration of the item in seconds. Still footages have a duration
        of 0. Read-only."""
        return self._main_source._duration

    @property
    def frame_rate(self) -> float:  # type: ignore[override]
        """The frame rate of the item in frames-per-second. Read-only."""
        return self._main_source.display_frame_rate

    @property
    def frame_duration(self) -> int:  # type: ignore[override]
        """The duration of the item in frames. Still footages have a duration
        of 0. Read-only."""
        return self._main_source._frame_duration

    @property
    def pixel_aspect(self) -> float:  # type: ignore[override]
        """The pixel aspect ratio of the item (1.0 is square). Read-only."""
        return self._main_source._pixel_aspect

    @property
    def footage_missing(self) -> bool:
        """When `True`, the AVItem is a placeholder, or represents footage with a
        source file that could not be found when the project was last saved.

        In this case, the path of the missing source file is in the
        `missing_footage_path` attribute of the footage item's source-file object.
        See [FootageItem.main_source][] and
        [FileSource.missing_footage_path][py_aep.models.sources.file.FileSource.missing_footage_path].
        Read-only."""
        return self._main_source._footage_missing

    @property
    def has_audio(self) -> bool:
        """When `True`, the footage has an audio component.

        When [use_proxy][py_aep.models.items.av_item.AVItem.use_proxy] is
        `True`, reflects the proxy source rather than the main source.
        Read-only.
        """
        if self.use_proxy and self._proxy_source is not None:
            return self._proxy_source._has_audio
        return self._main_source._has_audio

    @property
    def start_frame(self) -> int:
        """The footage start frame. Read-only."""
        return self._main_source._start_frame

    @property
    def end_frame(self) -> int:
        """The footage end frame. Read-only."""
        return self._main_source._end_frame

    def __init__(
        self,
        *,
        _idta: IdtaChunk,
        _name_utf8: Utf8Chunk,
        _cmta: CmtaChunk | None,
        _item_list: ListChunk,
        _gide: ListChunk | None,
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
        self._main_source = main_source
        # Store resolved display name in __dict__ so the ChunkField
        # getter returns it without mutating the binary Utf8 chunk.
        self.__dict__["name"] = main_source._resolve_name(_name_utf8.value)

    @property
    def main_source(self) -> FileSource | SolidSource | PlaceholderSource:
        """The footage source. Read-only."""
        return self._main_source

    @property
    def asset_type(self) -> str:
        """The footage type (placeholder, solid, file). Read-only."""
        if isinstance(self._main_source, SolidSource):
            return "solid"
        elif isinstance(self._main_source, FileSource):
            return "file"
        elif isinstance(self._main_source, PlaceholderSource):
            return "placeholder"
        else:
            raise TypeError(
                f"Unexpected source type for {self.name}: {type(self._main_source)}"
            )

    @property
    def file(self) -> str | None:
        """The footage file path if its source is a [FileSource][], else `None`."""
        if hasattr(self._main_source, "file"):
            return self._main_source.file
        return None
