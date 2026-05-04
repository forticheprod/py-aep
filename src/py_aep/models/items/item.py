from __future__ import annotations

import typing

from py_aep.enums import Label

from ...binary.scalar_chunks import Utf8Chunk
from ..descriptors import ChunkField
from ..transforms import strip_null

if typing.TYPE_CHECKING:
    from ...binary.chunk import ListChunk
    from ...binary.item_chunks import IdtaChunk
    from ..guide import Guide
    from ..project import Project
    from .folder import FolderItem


class Item:
    """
    The `Item` object represents an item that can appear in the Project panel.

    Info:
        `Item` is the base class for [AVItem][] object and for [FolderItem][]
        object, which are in turn the base classes for various other item
        types, so `Item` attributes and methods are available when working with
        all of these item types.

    See: https://ae-scripting.docsforadobe.dev/item/item/
    """

    label = ChunkField.enum(
        Label,
        "_idta",
        "label",
        default=Label.NONE,
    )
    """The label color. Colors are represented by their number (0 for None,
    or 1 to 16 for one of the preset colors in the Labels preferences).
    Read / Write."""

    id = ChunkField[int]("_idta", "item_id", read_only=True, default=0)
    """The item unique identifier. Read-only."""

    name = ChunkField[str](
        "_name_utf8",
        "value",
        transform=strip_null,
    )
    """The name of the item, as shown in the Project panel.
    Read / Write."""

    def __init__(
        self,
        *,
        _idta: IdtaChunk | None,
        _name_utf8: Utf8Chunk | None,
        _cmta: Utf8Chunk | None,
        _item_list: ListChunk | None,
        project: Project,
        parent_folder: FolderItem | None,
        type_name: str,
    ) -> None:
        self._idta = _idta
        self._name_utf8 = _name_utf8
        self._cmta = _cmta
        self._item_list = _item_list
        self._project = project
        self._parent_folder = parent_folder
        self._selected = False
        self._type_name = type_name
        self._guides: list[Guide] = []

    @property
    def comment(self) -> str:
        """The item comment. Read / Write."""
        if self._cmta is None:
            return ""
        return strip_null(self._cmta.value)

    @comment.setter
    def comment(self, value: str) -> None:
        if self._cmta is not None:
            self._cmta.value = value
        elif self._item_list is not None:
            chunk = Utf8Chunk(chunk_type="cmta", value=value)
            self._item_list.chunks.append(chunk)
            self._cmta = chunk

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Item):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    @property
    def parent_folder(self) -> FolderItem | None:
        """The parent folder of this item. `None` for the root folder.
        Read-only."""
        return self._parent_folder

    @property
    def selected(self) -> bool:
        """When `True`, this item is selected. Read-only.

        Note:
            Item selection is not stored in the `.aep` binary format; it is a
            runtime-only state. Parsed projects always report `False`.
        """
        return self._selected

    @property
    def type_name(self) -> str:
        """A user-readable name for the item type ("Folder", "Footage" or
        "Composition"). These names are application locale-dependent, meaning
        that they are different depending on the application's UI language.
        Read-only."""
        return self._type_name

    @property
    def guides(self) -> list[Guide]:
        """The item's ruler guides. Each guide has an orientation
        and a pixel position. Read-only."""
        return self._guides

    @property
    def is_folder(self) -> bool:
        """`True` if the item is a folder."""
        return self.type_name == "Folder"

    @property
    def is_composition(self) -> bool:
        """`True` if the item is a composition."""
        return self.type_name == "Composition"

    @property
    def is_footage(self) -> bool:
        """`True` if the item is a footage."""
        return self.type_name == "Footage"
