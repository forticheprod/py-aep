from __future__ import annotations

from typing import TYPE_CHECKING, cast

from py_aep.enums import Label

from ...ae_version import requires_version
from ...binary.chunk import ListChunk
from ...binary.item_chunks import CmtaChunk
from ...binary.ldat_chunks import (
    LHD3_BLOCK_GUIDES,
    LdatChunk,
    LdatItemType,
    Lhd3Chunk,
    set_lhd3_count,
)
from ...binary.mutations import build_gide_list
from ...binary.scalar_chunks import Utf8Chunk
from ...binary.utils import (
    ChunkNotFoundError,
    block_slice,
    find_by_list_type,
    find_by_type,
    index_by_identity,
)
from ..descriptors import ChunkField
from ..guide import Guide
from ..validators import validate_name, validate_string

if TYPE_CHECKING:
    from ...binary.chunk import Chunk
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
        validate=validate_name,
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
            self._lhd3 = cast(
                "Lhd3Chunk", find_by_type(chunks=self._inner.chunks, chunk_type="lhd3")
            )
            try:
                self._ldat = cast(
                    "LdatChunk",
                    find_by_type(chunks=self._inner.chunks, chunk_type="ldat"),
                )
            except ChunkNotFoundError:
                self._ldat = None

    @property
    def dynamic_link_guid(self) -> str:
        """A unique and persistent identification number used for the
        dynamic link, in form of `00000000-0000-0000-0000-000000000000`.
        Read-only.
        """
        return f"{self.id:08x}-0000-0000-0000-000000000000"

    @property
    def comment(self) -> str:
        """The item comment. Read / Write."""
        if self._cmta is None:
            return ""
        return self._cmta.value

    @comment.setter
    def comment(self, value: str) -> None:
        validate_string(value)
        if self._cmta is not None:
            self._cmta.value = value
        elif value:
            chunk = CmtaChunk()
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
        Read / Write.

        Setting this moves the item into another folder. The item's binary
        chunk block is relocated from the old folder's container to the end
        of the new folder's container, and both folders' `items` lists are
        updated.

        Raises:
            ValueError: If this is the root folder, or if moving a folder
                into itself or one of its own descendants.
            TypeError: If the value is not a [FolderItem][].
        """
        return self._parent_folder

    @parent_folder.setter
    def parent_folder(self, value: FolderItem) -> None:
        from .folder import FolderItem

        old_parent = self._parent_folder
        if old_parent is None:
            raise ValueError("Cannot move the root folder")
        if not isinstance(value, FolderItem):
            raise TypeError("parent_folder must be a FolderItem")
        if value is old_parent:
            return
        # A folder cannot become its own descendant. Walking up from the
        # target also covers value is self and value under the root.
        ancestor: FolderItem | None = value
        while ancestor is not None:
            if ancestor is self:
                raise ValueError("a folder cannot be moved inside itself")
            ancestor = ancestor._parent_folder

        block = self._remove_from_parent_chunks()
        value._children_container.extend(block)

        old_parent.items.remove(self)
        value.items.append(self)

        # Relocate the item's open-panel viewer (AVItem only).
        viewer = getattr(self, "_viewer", None)
        if viewer is not None:
            old_parent._viewers.remove(viewer)
            value._viewers.append(viewer)

        self._parent_folder = value

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

    @requires_version(16)
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
        set_lhd3_count(self._lhd3, len(self._ldat.items), LHD3_BLOCK_GUIDES)
        return self._lhd3.count - 1

    @requires_version(16)
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
                f"Guide index {guide_index} out of range [0, {len(self._guides) - 1}]"
            )
        assert self._lhd3 is not None
        assert self._ldat is not None
        del self._ldat.items[guide_index]
        del self._guides[guide_index]
        set_lhd3_count(self._lhd3, len(self._ldat.items), LHD3_BLOCK_GUIDES)
        if self._lhd3.count == 0:
            self._empty_guides_container()

    @requires_version(16)
    def remove_all_guides(self) -> None:
        """Remove all guides from the item.

        Equivalent to calling `remove_guide` for each guide. A no-op
        when the item has no guides.
        """
        while self._guides:
            self.remove_guide(len(self._guides) - 1)

    def _ensure_guides_container(self) -> None:
        """Create the guides container if needed."""
        if self._ldat is not None:
            return
        self._ldat = LdatChunk(
            items=[],
            item_type=LdatItemType.gide,
            item_size=16,
        )
        if self._lhd3 is None:
            self._gide, self._lhd3, self._inner = build_gide_list()
            self._inner.chunks.append(self._ldat)
            self._item_list.chunks.append(self._gide)
        else:
            assert self._inner is not None
            self._inner.chunks.append(self._ldat)

    def _empty_guides_container(self) -> None:
        """Empty the guides container, keeping the (now childless) `LIST:Gide`.

        After Effects always writes a `LIST:Gide` for an item even with zero
        guides (its `lhd3` has `count=0` and no `ldat` child); deleting the
        container entirely leaves the project in a state AE opens but cannot
        re-save. So we drop only the `ldat` and keep `gide`/`lhd3`/`inner`.
        """
        if self._gide is None:
            return
        if self._ldat is not None and self._inner is not None:
            del self._inner.chunks[index_by_identity(self._inner.chunks, self._ldat)]
        self._ldat = None

    def remove(self) -> None:
        """Remove this item from the project.

        Subclasses add their own cleanup before calling `super().remove()`:

        - [FolderItem][] removes children recursively.
        - [AVItem][] removes layers that reference this item as their source
          and cleans up viewer references.
        - [CompItem][] removes render-queue items targeting this composition.

        Raises:
            ValueError: If this is the root folder.
        """
        # Remove from parent folder's binary chunks
        self._remove_from_parent_chunks()

        # Remove from model collections
        assert self._parent_folder is not None
        self._parent_folder.items.remove(self)
        del self._project.items[self.id]

    #: list_types that mark the start of the next item block.
    _ITEM_BOUNDARY_LIST_TYPES: frozenset[str] = frozenset({"Item"})

    def _remove_from_parent_chunks(self) -> list[Chunk]:
        """Detach this item's LIST:Item and trailing view-data chunks.

        Returns the removed block so callers can relocate it (e.g. the
        `parent_folder` setter); `remove()` discards it.
        """
        parent = self._parent_folder
        assert parent is not None
        container = parent._children_container
        start, end = block_slice(
            container,
            self._item_list,
            self._ITEM_BOUNDARY_LIST_TYPES,
        )
        block = container[start:end]
        del container[start:end]
        return block
