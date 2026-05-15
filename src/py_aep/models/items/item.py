from __future__ import annotations

from typing import TYPE_CHECKING, cast

from py_aep.enums import Label

from ...binary.chunk import ListChunk
from ...binary.ldat_chunks import GdtaChunk, LdatChunk, LdatItemType, Lhd3Chunk
from ...binary.scalar_chunks import CmtaChunk, Utf8Chunk
from ...binary.utils import (
    ChunkNotFoundError,
    find_by_list_type,
    find_by_type,
)
from ..descriptors import ChunkField
from ..guide import Guide
from ..validators import validate_string

if TYPE_CHECKING:
    from ...binary.item_chunks import IdtaChunk
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
        validate=validate_string(allow_empty=False),
    )
    """The name of the item, as shown in the Project panel.
    Read / Write."""

    def __init__(
        self,
        *,
        _idta: IdtaChunk | None,
        _name_utf8: Utf8Chunk | None,
        _cmta: CmtaChunk | None,
        _item_list: ListChunk,
        _gide: ListChunk | None = None,
        project: Project,
        parent_folder: FolderItem | None,
        type_name: str,
    ) -> None:
        self._idta = _idta
        self._name_utf8 = _name_utf8
        self._cmta = _cmta
        self._item_list = _item_list
        self._gide = _gide
        self._project = project
        self._parent_folder = parent_folder
        self._type_name = type_name
        self._guides: list[Guide] = []

        if self._gide is None:
            self._inner: ListChunk | None = None
            self._lhd3: Lhd3Chunk | None = None
            self._ldat: LdatChunk | None = None
        else:
            self._inner = find_by_list_type(chunks=self._gide.chunks, list_type="list")
            self._lhd3 = cast("Lhd3Chunk", find_by_type(chunks=self._inner.chunks, chunk_type="lhd3"))
            try:
                self._ldat = cast("LdatChunk", find_by_type(chunks=self._inner.chunks, chunk_type="ldat"))
            except ChunkNotFoundError:
                self._ldat = None

    @property
    def comment(self) -> str:
        """The item comment. Read / Write."""
        if self._cmta is None:
            return ""
        return self._cmta.value

    @comment.setter
    def comment(self, value: str) -> None:
        if self._cmta is not None:
            self._cmta.value = value
        else:
            chunk = CmtaChunk(chunk_type="cmta")
            chunk.value = value
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
        return False

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

    def add_guide(self, orientation_type: int, position: int) -> int:
        """Adds a new guide to the item.

        Any `orientation_type` value other than 0 (horizontal) or 1 (vertical)
        defaults to horizontal.

        Args:
            orientation_type: 0 for horizontal, 1 for vertical.
            position: The pixel position of the guide.

        Returns:
            The index of the new guide.
        """
        self._ensure_guides_container()
        assert self._lhd3 is not None
        assert self._ldat is not None
        guide = Guide._new(orientation_type, position)
        self._guides.append(guide)
        self._ldat.items.append(guide._guide_item)
        self._lhd3.count += 1
        return self._lhd3.count - 1

    def remove_guide(self, guide_index: int) -> None:
        """Removes an existing guide by index.

        Args:
            guide_index: The 0-based index of the guide to remove.

        Raises:
            IndexError: If `guide_index` is out of range.
        """
        if not self._guides:
            raise IndexError("No guides to remove")
        if not 0 <= guide_index < len(self._guides):
            raise IndexError(
                f"Guide index {guide_index} out of range "
                f"[0, {len(self._guides) - 1}]"
            )
        assert self._lhd3 is not None
        assert self._ldat is not None
        del self._ldat.items[guide_index]
        del self._guides[guide_index]
        self._lhd3.count -= 1
        if self._lhd3.count == 0:
            self._remove_guides_container()

    def _ensure_guides_container(self) -> None:
        """Create the guides container if needed."""
        if self._ldat is not None:
            return
        self._ldat = LdatChunk(
            chunk_type="ldat",
            items=[],
            item_type=LdatItemType.gide,
            item_size=16,
        )
        if self._lhd3 is None:
            self._lhd3 = Lhd3Chunk(
                chunk_type="lhd3",
                count=0,
                item_size=16,
                item_type_raw=2,
            )
            self._inner = ListChunk(
                chunk_type="LIST",
                list_type="list",
                chunks=[self._lhd3, self._ldat],
            )
            self._gide = ListChunk(
                chunk_type="LIST",
                list_type="Gide",
                chunks=[GdtaChunk(), self._inner],
            )
            self._item_list.chunks.append(self._gide)
        else:
            assert self._inner is not None
            self._inner.chunks.append(self._ldat)

    def _remove_guides_container(self) -> None:
        """Removes the guides container."""
        if self._gide is None:
            return
        self._item_list.chunks.remove(self._gide)
        self._gide = None
        self._lhd3 = None
        self._ldat = None
        self._inner = None
