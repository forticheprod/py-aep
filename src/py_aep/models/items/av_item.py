from __future__ import annotations

import typing

from .item import Item

if typing.TYPE_CHECKING:
    from ...binary.chunk import Chunk, ListChunk
    from ..descriptors import ChunkField
    from ..project import Project
    from ..viewer.viewer import Viewer
    from .composition import CompItem
    from .folder import FolderItem


class AVItem(Item):
    """
    The `AVItem` object provides access to attributes and methods of
    audio/visual files imported into After Effects.

    Info:
        `AVItem` is a subclass of [Item][]. All methods and attributes of [Item][]
        are available when working with `AVItem`.

    Info:
        `AVItem` is the base class for both [CompItem][] and [FootageItem][], so
        `AVItem` attributes and methods are also available when working with
        [CompItem][] and [FootageItem][] objects. See [CompItem][] object and
        [FootageItem][] object.

    See: https://ae-scripting.docsforadobe.dev/item/avitem/
    """

    duration: ChunkField[float]
    """The duration of the item in seconds. Still footages have a duration of 0. Read-only."""

    frame_duration: ChunkField[int]
    """The duration of the item in frames. Still footages have a duration of 0. Read-only."""

    frame_rate: ChunkField[float]
    """The frame rate of the item in frames-per-second. Read-only."""

    height: ChunkField[int]
    """The height of the item in pixels. Read-only."""

    pixel_aspect: ChunkField[float]
    """The pixel aspect ratio of the item (1.0 is square). Read-only."""

    width: ChunkField[int]
    """The width of the item in pixels. Read-only."""

    def __init__(
        self,
        *,
        _idta: Chunk | None,
        _name_utf8: Chunk,
        _cmta: Chunk | None,
        _item_list: ListChunk | None = None,
        project: Project,
        parent_folder: FolderItem | None,
        type_name: str,
    ) -> None:
        super().__init__(
            _idta=_idta,
            _name_utf8=_name_utf8,
            _cmta=_cmta,
            _item_list=_item_list,
            project=project,
            parent_folder=parent_folder,
            type_name=type_name,
        )
        self._used_in: set[CompItem] = set()
        self._viewer: Viewer | None = None

    @property
    def has_audio(self) -> bool:
        """When `True`, the AVItem has an audio component.

        In a [CompItem][], the value is linked to the composition.
        In a [FootageItem][py_aep.models.items.footage.FootageItem],
        the value is linked to the `main_source` object.
        """
        return False

    @property
    def has_video(self) -> bool:
        """`True` if the item has a video component.

        An AVItem has video when it has non-zero dimensions (`width > 0`
        and `height > 0`). In a [CompItem][], the value is always `True`.
        In a [FootageItem][py_aep.models.items.footage.FootageItem],
        the value depends on the footage source (e.g. audio-only files
        return `False`).
        """
        return self.width > 0 and self.height > 0

    @property
    def time(self) -> float:
        """The current time of the item when it is being previewed directly
        from the Project panel. This value is a number of seconds. It is an
        error to set this value for a [FootageItem][] whose `main_source`
        is still (`item.main_source.is_still is True`)."""
        return 0.0

    @property
    def frame_time(self) -> int:
        """The current time of the item when it is being previewed directly
        from the Project panel. This value is a number of frames."""
        return 0

    @property
    def used_in(self) -> list[CompItem]:
        """All the compositions that use this AVItem."""
        return list(self._used_in)
