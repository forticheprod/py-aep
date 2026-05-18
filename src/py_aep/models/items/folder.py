from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from ...binary.chunk import ListChunk
from ...binary.item_chunks import IdpcChunk, IdtaChunk, IideChunk
from ...binary.misc_chunks import SfdtChunk
from ...binary.scalar_chunks import Utf8Chunk
from ...binary.utils import (
    find_by_list_type,
)
from ..validators import validate_string
from .item import Item

if TYPE_CHECKING:
    from ...binary.chunk import Chunk
    from ...binary.item_chunks import CmtaChunk
    from ..items.composition import CompItem
    from ..project import Project
    from ..viewer.viewer import Viewer

_validate_name = validate_string(allow_empty=False)


class FolderItem(Item):
    """
    The `FolderItem` object corresponds to a folder in your Project panel. It
    can contain various types of items (footage, compositions, solids) as well
    as other folders.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        root = app.project.root_folder
        print(root.name)
        for item in root:
            ...
        ```

    See: https://ae-scripting.docsforadobe.dev/item/folderitem/
    """

    items: list[Item]
    """
    The items in this folder. Contains only the top-level items in the folder.
    Read-only.
    """

    def __init__(
        self,
        *,
        _idta: IdtaChunk | None,
        _name_utf8: Utf8Chunk | None,
        _cmta: CmtaChunk | None,
        _item_list: ListChunk,
        _gide: ListChunk | None,
        project: Project,
        parent_folder: FolderItem | None,
    ) -> None:
        super().__init__(
            _idta=_idta,
            _name_utf8=_name_utf8,
            _cmta=_cmta,
            _item_list=_item_list,
            _gide=_gide,
            project=project,
            parent_folder=parent_folder,
            type_name="Folder",
        )
        self.items: list[Item] = []
        self._viewers: list[Viewer] = []

    def __iter__(self) -> Iterator[Item]:
        """Return an iterator over the folder items."""
        return iter(self.items)

    def remove(self) -> None:
        """Remove this folder and all its children from the project."""
        if self._parent_folder is None:
            raise ValueError("Cannot remove the root folder")
        for child in list(self.items):
            child.remove()
        super().remove()

    @classmethod
    def _new(
        cls,
        name: str,
        *,
        project: Project,
        parent_folder: FolderItem,
    ) -> FolderItem:
        """Create a new empty folder with backing chunks.

        Args:
            name: The name of the new folder.
            project: The project that owns this folder.
            parent_folder: The folder that will contain this folder.
        """
        new_id = project._allocate_item_id()

        iide = IideChunk(value=new_id)
        idpc = IdpcChunk()
        idta = IdtaChunk(item_type=1, item_id=new_id)
        name_utf8 = Utf8Chunk(chunk_type="Utf8", value=name)
        sfdt = SfdtChunk()
        sfdr = ListChunk(list_type="Sfdr")

        item_list = ListChunk(
            list_type="Item",
            chunks=[iide, idpc, idta, name_utf8, sfdt, sfdr],
        )

        folder = cls(
            _idta=idta,
            _name_utf8=name_utf8,
            _cmta=None,
            _item_list=item_list,
            _gide=None,
            project=project,
            parent_folder=parent_folder,
        )
        return folder

    @property
    def num_items(self) -> int:
        """
        Return the number of items in the folder.

        Note:
            Equivalent to `len(folder.items)`
        """
        return len(self.items)

    def _get_children_container(self) -> list[Chunk]:
        """Return the chunk list where child items should be appended.

        For root folder (id 0): directly `_item_list.chunks`.
        For non-root folders: the `LIST:Sfdr` chunk inside `_item_list`.
        """
        if self._idta is None:
            # Root folder - children are directly in LIST:Fold.chunks
            return self._item_list.chunks
        sfdr = find_by_list_type(chunks=self._item_list.chunks, list_type="Sfdr")
        return sfdr.chunks

    def add_folder(self, name: str) -> FolderItem:
        """Create a new folder inside this folder.

        Args:
            name: The name of the new folder.

        Returns:
            The newly created [FolderItem][].
        """
        _validate_name(name, None)

        folder = FolderItem._new(
            name,
            project=self._project,
            parent_folder=self,
        )

        # Insert into parent container
        container = self._get_children_container()
        container.append(folder._item_list)

        # Register in project and parent
        self._project.items[folder.id] = folder
        self.items.append(folder)
        return folder

    def add_comp(
        self,
        name: str,
        width: int,
        height: int,
        pixel_aspect: float,
        duration: float,
        frame_rate: float,
    ) -> CompItem:
        """Create a new composition inside this folder.

        Args:
            name: The name of the new composition.
            width: The width of the composition in pixels.
            height: The height of the composition in pixels.
            pixel_aspect: The pixel aspect ratio (1.0 for square pixels).
            duration: The duration in seconds.
            frame_rate: The frame rate in frames per second.

        Returns:
            The newly created [CompItem][].
        """
        from .composition import CompItem

        _validate_name(name, None)

        comp = CompItem._new(
            name,
            width,
            height,
            pixel_aspect,
            duration,
            frame_rate,
            project=self._project,
            parent_folder=self,
        )

        # Insert into parent container with required view data chunks
        container = self._get_children_container()
        container.append(comp._item_list)
        container.extend(comp._view_data)

        # Register in project and parent
        self._project.items[comp.id] = comp
        self.items.append(comp)
        return comp
