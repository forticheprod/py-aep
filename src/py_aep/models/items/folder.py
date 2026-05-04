from __future__ import annotations

import typing

from .item import Item

if typing.TYPE_CHECKING:
    from ...binary.chunk import ListChunk
    from ...binary.item_chunks import IdtaChunk
    from ...binary.scalar_chunks import Utf8Chunk
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
        _cmta: Utf8Chunk | None,
        _item_list: ListChunk | None = None,
        project: Project,
        parent_folder: FolderItem | None,
    ) -> None:
        super().__init__(
            _idta=_idta,
            _name_utf8=_name_utf8,
            _cmta=_cmta,
            _item_list=_item_list,
            project=project,
            parent_folder=parent_folder,
            type_name="Folder",
        )
        self.items: list[Item] = []
        self._viewers: list[Viewer] = []

    def __iter__(self) -> typing.Iterator[Item]:
        """Return an iterator over the folder items."""
        return iter(self.items)

    @property
    def num_items(self) -> int:
        """
        Return the number of items in the folder.

        Note:
            Equivalent to `len(folder.items)`
        """
        return len(self.items)
