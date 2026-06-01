from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from ...binary.chunk import ListChunk
from ...binary.item_chunks import IdpcChunk, IdtaChunk, IideChunk
from ...binary.misc_chunks import SfdtChunk
from ...binary.scalar_chunks import Utf8Chunk
from ..naming import auto_name
from .composition import CompItem
from .footage import FootageItem
from .item import Item

if TYPE_CHECKING:
    from ...binary.chunk import Chunk
    from ...binary.item_chunks import CmtaChunk
    from ..project import Project
    from ..viewer.viewer import Viewer


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

    _auto_name: str = "Untitled"

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
        _children_container: list[Chunk],
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
        self._children_container = _children_container
        self._viewers: list[Viewer] = []

    def __iter__(self) -> Iterator[Item]:
        """Return an iterator over the folder items."""
        return iter(self.items)

    @property
    def compositions(self) -> list[CompItem]:
        """All the compositions in the project."""
        return [item for item in self.items if isinstance(item, CompItem)]

    @property
    def folders(self) -> list[FolderItem]:
        """All the folders in the project."""
        return [item for item in self.items if isinstance(item, FolderItem)]

    @property
    def footages(self) -> list[FootageItem]:
        """All the footages in the project."""
        return [item for item in self.items if isinstance(item, FootageItem)]

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
        name_utf8 = Utf8Chunk(value=name)
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
            _children_container=sfdr.chunks,
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

    def add_folder(self, name: str | None = None) -> FolderItem:
        """Create a new folder inside this folder.

        Args:
            name: The name of the new folder. Pass `None` to auto-generate
                a name (`Untitled 1`, `Untitled 2`, ...).
                An empty string is allowed.

        Returns:
            The newly created [FolderItem][].
        """
        if name is None:
            existing = {item.name for item in self._project.items.values()}
            name = auto_name(FolderItem._auto_name, existing)

        folder = FolderItem._new(
            name,
            project=self._project,
            parent_folder=self,
        )

        # Insert into parent container
        self._children_container.append(folder._item_list)

        # Register in project and parent
        self._project.items[folder.id] = folder
        self.items.append(folder)
        return folder

    def add_comp(
        self,
        name: str | None,
        width: int,
        height: int,
        pixel_aspect: float,
        duration: float,
        frame_rate: float,
    ) -> CompItem:
        """Create a new composition inside this folder.

        Args:
            name: The name of the new composition. Pass `None` to
                auto-generate a name (`Comp 1`, `Comp 2`, ...).
                An empty string is allowed.
            width: The width of the composition in pixels.
            height: The height of the composition in pixels.
            pixel_aspect: The pixel aspect ratio (1.0 for square pixels).
            duration: The duration in seconds.
            frame_rate: The frame rate in frames per second.

        Returns:
            The newly created [CompItem][].
        """
        from .composition import CompItem

        if name is None:
            existing = {item.name for item in self._project.items.values()}
            name = auto_name(CompItem._auto_name, existing)

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
        self._children_container.append(comp._item_list)
        self._children_container.extend(comp._view_data)

        # Register in project and parent
        self._project.items[comp.id] = comp
        self.items.append(comp)
        return comp
