from __future__ import annotations

from typing import TYPE_CHECKING

from ..descriptors import ChunkField
from .item import Item

if TYPE_CHECKING:
    from ...binary.chunk import ListChunk
    from ...binary.item_chunks import IdtaChunk
    from ...binary.scalar_chunks import CmtaChunk, Utf8Chunk
    from ..project import Project
    from ..sources.file import FileSource
    from ..sources.placeholder import PlaceholderSource
    from ..sources.solid import SolidSource
    from ..viewer.viewer import Viewer
    from .composition import CompItem
    from .folder import FolderItem


def _validate_use_proxy(value: bool, obj: AVItem) -> None:
    if obj.proxy_source is None and value:
        raise AttributeError(
            "Cannot set use_proxy to True when there is no proxy source."
        )

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

    duration: float
    """The duration of the item in seconds. Still footages have a duration of 0. Read-only."""

    frame_duration: int
    """The duration of the item in frames. Still footages have a duration of 0. Read-only."""

    frame_rate: float
    """The frame rate of the item in frames-per-second. Read-only."""

    height: int
    """The height of the item in pixels. Read-only."""

    pixel_aspect: float
    """The pixel aspect ratio of the item (1.0 is square). Read-only."""

    width: int
    """The width of the item in pixels. Read-only."""

    use_proxy = ChunkField[bool]("_idta", "use_proxy", validate=_validate_use_proxy)
    """When `True`, a proxy is used for the item. Read / Write.

    It is set to `True` by all the `set_proxy` methods, and to `False` by
    the `set_proxy_to_none()` method.
    """

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
        type_name: str,
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
            type_name=type_name,
        )
        self._proxy_source = proxy_source
        self._used_in: set[CompItem] = set()
        self._viewer: Viewer | None = None

    @property
    def proxy_source(
        self,
    ) -> FileSource | SolidSource | PlaceholderSource | None:
        """The [FootageSource][] being used as a proxy. Read-only.

        To change it, call any of the `AVItem` methods that change the proxy
        source: `set_proxy()`, `set_proxy_with_sequence()`,
        `set_proxy_with_solid()`, or `set_proxy_with_placeholder()`.
        """
        return self._proxy_source

    @property
    def has_audio(self) -> bool:
        """When `True`, the AVItem has an audio component.

        In a [CompItem][], the value is linked to the composition.
        In a [FootageItem][py_aep.models.items.footage.FootageItem],
        the value is linked to the `main_source` or `proxy_source` object.
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
        error to set this value for a [FootageItem][] whose `main_source` or
        `proxy_source` is still."""
        return 0.0

    @property
    def frame_time(self) -> int:
        """The current time of the item when it is being previewed directly
        from the Project panel. This value is a number of frames."""
        return 0

    @property
    def used_in(self) -> list[CompItem]:
        """All the compositions that use this AVItem."""
        self._project._ensure_used_in_linked()
        return list(self._used_in)
