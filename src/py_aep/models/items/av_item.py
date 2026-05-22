from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ...binary.chunk import Chunk, ListChunk
from ...binary.misc_chunks import (
    ApidChunk,
    DcuiChunk,
    DropChunk,
    EmbpChunk,
    EpidChunk,
    HdrmChunk,
    IpwsChunk,
    LinlChunk,
    McspChunk,
    OcspChunk,
    PrgbChunk,
    StrtChunk,
)
from ...binary.scalar_chunks import U1Chunk, U2Chunk, U4Chunk, Utf8Chunk
from ...resolvers.solid import solid_color_name
from ..descriptors import ChunkField
from ..naming import auto_name
from .item import Item

if TYPE_CHECKING:
    from ...binary.item_chunks import CmtaChunk, IdtaChunk
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


def _sync_proxy_active(obj: AVItem) -> None:
    obj._idta._proxy_active = int(obj._idta.use_proxy)


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

    use_proxy = ChunkField[bool](
        "_idta",
        "use_proxy",
        validate=_validate_use_proxy,
        post_set=_sync_proxy_active,
    )
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
        _pin_chunks: list[ListChunk],
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
        self._pin_chunks = _pin_chunks
        self._proxy_source = proxy_source
        self._used_in: set[CompItem] = set()
        self._viewer: Viewer | None = None

    def remove(self) -> None:
        """Remove this AV item, its referencing layers, and viewer."""
        item_id = self.id
        for comp in self.used_in:
            for layer in list(comp.av_layers):
                if layer._source_id == item_id:
                    layer.remove()
        if self._viewer is not None:
            assert self._parent_folder is not None
            self._parent_folder._viewers.remove(self._viewer)
            self._viewer = None
        super().remove()

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

    def set_proxy_to_none(self) -> None:
        """Remove the proxy source from this item."""
        if self._proxy_source:
            self._item_list.chunks.remove(self._pin_chunks[1])
            del self._pin_chunks[1]
            self._proxy_source = None
        self.use_proxy = False

    def set_proxy_with_placeholder(
        self,
        name: str | None,
        width: int,
        height: int,
        frame_rate: float,
        duration: float,
    ) -> None:
        """Set a placeholder as the proxy source.

        Args:
            name: The placeholder name. `None` becomes `Missing Name`.
                An empty string becomes `Placeholder`.
            width: Width in pixels (4-30000).
            height: Height in pixels (4-30000).
            frame_rate: Frame rate in fps (1.0-99.0).
            duration: Duration in seconds (> 0, <= 10800).
        """
        from ..sources.placeholder import PlaceholderSource

        if name is None:
            name = "Missing Name"
        elif name == "":
            name = "Placeholder"

        source = PlaceholderSource._new(name, width, height, frame_rate, duration)
        self._set_proxy(source)

    def set_proxy_with_solid(
        self,
        color: list[float],
        name: str | None,
        width: int,
        height: int,
        pixel_aspect: float = 1.0,
    ) -> None:
        """Set a solid as the proxy source.

        Args:
            color: Solid color as [R, G, B] in 0.0-1.0 range.
            name: The solid name. Pass `None` to auto-generate
                a name from the color (e.g. `Red Solid 1`).
                An empty string becomes `????`.
            width: Width in pixels (1-30000).
            height: Height in pixels (1-30000).
            pixel_aspect: Pixel aspect ratio (0.01-100.0).
        """
        from ..sources.solid import SolidSource

        if name is None:
            existing = {item.name for item in self._project.items.values()}
            solid_name = solid_color_name(color[0], color[1], color[2])
            name = auto_name(solid_name, existing)
        elif name == "":
            name = "????"

        source = SolidSource._new(color, name, width, height, pixel_aspect)
        self._set_proxy(source)

    @staticmethod
    def _build_view_data() -> list[Chunk]:
        """Build the view data chunks AE expects after LIST:Item."""
        return [
            U4Chunk(chunk_type="fvdv", value=3),
            U1Chunk(chunk_type="fiop"),
            U4Chunk(chunk_type="ftts"),
            U1Chunk(chunk_type="foac"),
            U1Chunk(chunk_type="fiac"),
            U2Chunk(chunk_type="fipc"),
            U4Chunk(chunk_type="fifl"),
        ]

    @staticmethod
    def _build_pin_list(
        sspc: Chunk,
        opti: Chunk,
        *,
        is_solid: bool = False,
    ) -> ListChunk:
        """Build a complete `LIST:Pin` with required companion chunks."""
        pgui = Chunk(chunk_type="pgui", data=uuid.uuid4().bytes)

        clrs_chunks: list[Chunk] = [
            EpidChunk(),
            ApidChunk(),
            LinlChunk(),
            EmbpChunk(),
            IpwsChunk(),
        ]
        if is_solid:
            clrs_chunks.append(DcuiChunk())
            clrs_chunks.append(PrgbChunk())
        clrs_chunks.extend([
            McspChunk(),
            Utf8Chunk(),
            OcspChunk(),
            Utf8Chunk(),
            HdrmChunk(),
            Utf8Chunk(value="{}"),
        ])
        clrs = ListChunk(list_type="CLRS", chunks=clrs_chunks)

        mnfo = ListChunk(
            list_type="mnfo",
            chunks=[StrtChunk(), DropChunk()],
        )

        return ListChunk(
            list_type="Pin ",
            chunks=[
                sspc,
                Utf8Chunk(),
                opti,
                pgui,
                clrs,
                mnfo,
                Utf8Chunk(),
            ],
        )

    def _replace_pin(self, pin_index: int, new_pin: ListChunk) -> None:
        """Replace or append a LIST:Pin chunk at the given index."""
        if pin_index < len(self._pin_chunks):
            old_pin = self._pin_chunks[pin_index]
            idx = self._item_list.chunks.index(old_pin)
            self._item_list.chunks[idx] = new_pin
            self._pin_chunks[pin_index] = new_pin
        else:
            self._item_list.chunks.append(new_pin)
            self._pin_chunks.append(new_pin)

    def _set_proxy(
        self,
        source: FileSource | SolidSource | PlaceholderSource,
    ) -> None:
        """Set a proxy LIST:Pin chunk (add or replace)."""
        from ..sources.solid import SolidSource as _SolidSource

        new_pin = AVItem._build_pin_list(
            source._sspc,
            source._opti,
            is_solid=isinstance(source, _SolidSource),
        )
        self._replace_pin(1, new_pin)
        self._proxy_source = source
        self.use_proxy = True
