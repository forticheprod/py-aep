from __future__ import annotations

from typing import TYPE_CHECKING

from ...binary.chunk import ListChunk
from ...binary.mutations import build_pin_list
from ...binary.scalar_chunks import Utf8Chunk
from ...binary.utils import index_by_identity
from ..descriptors import ChunkField
from ..naming import auto_name
from ..preferences import default_sequence_fps
from ..validators import validate_bool
from .item import Item

if TYPE_CHECKING:
    import os

    from ...binary.item_chunks import CmtaChunk, IdtaChunk
    from ..project import Project
    from ..sources.file import FileSource
    from ..sources.placeholder import PlaceholderSource
    from ..sources.solid import SolidSource
    from ..viewer.viewer import Viewer
    from .composition import CompItem
    from .folder import FolderItem


def _validate_use_proxy(value: bool, obj: AVItem) -> None:
    validate_bool(value)
    if obj.proxy_source is None and value:
        raise AttributeError(
            "Cannot set use_proxy to True when there is no proxy source."
        )


def _sync_proxy_active(obj: AVItem) -> None:
    assert obj._idta is not None
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

    use_proxy = ChunkField.bool(
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
        if proxy_source is not None:
            proxy_source._project = project
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
    def footage_missing(self) -> bool:
        """When `True`, the AVItem is a placeholder, or represents footage
        with a source file that could not be found when the project was last
        saved. Read-only.

        Always `False` for a [CompItem][]; a
        [FootageItem][py_aep.models.items.footage.FootageItem] reports the
        state of its `main_source` (see the `FootageItem` override).
        """
        return False

    @property
    def is_media_replacement_compatible(self) -> bool:
        """`True` if the item can be used as an alternate source when setting
        [Property.alternate_source][py_aep.models.properties.property.Property.alternate_source].
        Read-only.

        A [CompItem][] or a [FootageItem][py_aep.models.items.footage.FootageItem]
        with a video component can be used as an alternate source; see the
        `FootageItem` override for footage restrictions.
        """
        return self.has_video

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

    @property
    def _proxy_pin_index(self) -> int:
        """Index of the proxy `LIST:Pin` within `_pin_chunks`.

        Footage items carry a main-source pin at index 0 and the proxy at
        index 1; composition items have no main-source pin, so the proxy
        lives at index 0. Overridden by [CompItem][].
        """
        return 1

    def set_proxy_to_none(self) -> None:
        """Remove the proxy source from this item."""
        if self._proxy_source:
            proxy_pin = self._pin_chunks[self._proxy_pin_index]
            del self._item_list.chunks[
                index_by_identity(self._item_list.chunks, proxy_pin)
            ]
            del self._pin_chunks[self._proxy_pin_index]
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
            solid_name = SolidSource._color_name(color[0], color[1], color[2])
            name = auto_name(solid_name, existing)
        elif name == "":
            name = "????"

        source = SolidSource._new(name, color, width, height, pixel_aspect)
        self._set_proxy(source)

    def set_proxy(self, file: str | os.PathLike[str]) -> None:
        """Sets a file as the proxy of this AVItem.

        Loads the specified file into a new `FileSource` object, sets this as the value
        of the `proxy_source` attribute, and sets `use_proxy` to true.

        It does not preserve the interpretation parameters, instead using the user
        preferences.

        This differs from setting a `FootageItem`'s `main_source`, but both actions are
        performed as in the user interface.

        Note:
            Unlike ExtendScript, if the specified file has an unlabeled alpha channel,
            this method does not estimate the alpha interpretation.

        Args:
            file: Path to the proxy source file.

        Raises:
            ValueError: If the extension is not a supported footage format.
            NotImplementedError: If After Effects requires a format-specific
                `opti` header not implemented for this format.
        """
        from ..sources.file import FileSource

        self._set_proxy(FileSource._from_file(file))

    def set_proxy_with_sequence(
        self, file: str | os.PathLike[str], force_alphabetical: bool = False
    ) -> None:
        """Sets a sequence of files as the proxy of this `AVItem`, with the option of
        forcing alphabetical order. Loads the specified file sequence into a new
        `FileSource` object, sets this as the value of the `proxy_source` attribute, and
        sets `use_proxy` to true.

        It does not preserve the interpretation parameters, instead using the user
        preferences.

        Note:
            Unlike ExtendScript, if the specified file has an unlabeled alpha channel,
            this method does not estimate the alpha interpretation.

        Args:
            file: Path to a representative frame; sibling frames in the same
                folder are gathered into the sequence.
            force_alphabetical: Order frames alphabetically rather than
                numerically.

        Raises:
            ValueError: If the extension is not a supported footage format.
            NotImplementedError: If After Effects requires a format-specific
                `opti` header not implemented for this format.
        """
        from ..sources.file import FileSource

        self._set_proxy(
            FileSource._from_file(
                file,
                sequence=True,
                force_alphabetical=force_alphabetical,
                default_sequence_fps=default_sequence_fps(self._project._preferences),
            )
        )

    @staticmethod
    def _pin_for_source(
        source: FileSource | SolidSource | PlaceholderSource,
    ) -> ListChunk:
        """Return the `LIST:Pin` for a footage source.

        A `FileSource` already carries its complete Pin (with the Als2 path
        and any sequence prefix/ext); solid/placeholder sources are built
        from sspc+opti.
        """
        from ..sources.file import FileSource
        from ..sources.solid import SolidSource

        if isinstance(source, FileSource):
            return source._pin
        return build_pin_list(
            source._sspc,
            source._opti,
            is_solid=isinstance(source, SolidSource),
        )

    def _replace_pin(self, pin_index: int, new_pin: ListChunk) -> None:
        """Replace or append a LIST:Pin chunk at the given index."""
        if pin_index < len(self._pin_chunks):
            old_pin = self._pin_chunks[pin_index]
            idx = index_by_identity(self._item_list.chunks, old_pin)
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
        self._replace_pin(self._proxy_pin_index, self._pin_for_source(source))
        self._proxy_source = source
        source._project = self._project
        self.use_proxy = True
