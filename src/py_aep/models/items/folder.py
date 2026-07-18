from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from ...binary.chunk import ListChunk
from ...binary.item_chunks import IdpcChunk, IdtaChunk, IideChunk
from ...binary.misc_chunks import SfdtChunk
from ...binary.scalar_chunks import Utf8Chunk
from ..naming import auto_name
from ..preferences import label_index
from ..validators import validate_name, validate_string
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
        validate_string(name)
        new_id = project._allocate_id()

        iide = IideChunk(value=new_id)
        idpc = IdpcChunk()
        # AE labels new folders with the "Folder Label Index 2" preference
        # (factory 2, probed in AE 2026).
        idta = IdtaChunk(
            item_type=1,
            item_id=new_id,
            label=label_index(project._preferences, "Folder Label Index 2", 2),
        )
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

        # AE places a newly created/imported comp (its Item plus view-data
        # chunks) at the FRONT of the folder - right after the root folder's
        # `fdta` header, or at index 0 in a subfolder's Sfdr (verified in AE
        # 2026 for both script addComp and SVG import). Match that ordering.
        block = [comp._item_list, *comp._view_data]
        container = self._children_container
        insert_at = 1 if container and container[0].chunk_type == "fdta" else 0
        container[insert_at:insert_at] = block

        # Register in project and parent
        self._project.items[comp.id] = comp
        self.items.insert(0, comp)
        return comp

    def add_comp_from_preset(
        self,
        name: str | None,
        preset: str,
        duration: float,
    ) -> CompItem:
        """Create a new composition from a New Composition preset
        (py_aep extension, not in ExtendScript).

        Width, height, pixel aspect and frame rate resolve from the named
        preset in the AE preferences (see
        [composition_presets][py_aep.models.preferences.Preferences.composition_presets]);
        presets carry no duration, so it must be given.

        Args:
            name: The name of the new composition. Pass `None` to
                auto-generate a name (`Comp 1`, `Comp 2`, ...).
            preset: Preset name; matched exactly first, then as a unique
                case-insensitive substring (full names contain bullet
                separators, e.g. `HD . 1920x1080 . 25 fps`, so a
                fragment like `"1920x1080 . 25"` works).
            duration: The duration in seconds.

        Returns:
            The newly created [CompItem][].

        Raises:
            ValueError: If no preferences directory was provided, or the
                preset name does not resolve to exactly one preset.
        """
        validate_name(preset)
        presets = self._project._preferences.composition_presets()
        if not presets:
            raise ValueError(
                "no composition presets available; pass 'ae_preferences_dir' "
                "to parse()/new() to read them from the AE preferences"
            )
        matches = [p for p in presets if p.name == preset]
        if not matches:
            needle = preset.lower()
            matches = [p for p in presets if needle in p.name.lower()]
        if len(matches) != 1:
            available = ", ".join(repr(p.name) for p in presets)
            raise ValueError(
                f"preset {preset!r} matched {len(matches)} presets; "
                f"available: {available}"
            )
        found = matches[0]
        return self.add_comp(
            name,
            found.width,
            found.height,
            found.pixel_aspect,
            duration,
            found.frame_rate,
        )

    def _sort_children_by_name(self) -> None:
        """Reorder this folder's items case-insensitive alphabetically by name.

        After Effects stores the `Sfdr` of an imported `<stem> Layers` folder
        in the Project-panel alphabetical display order (verified against the
        AE 2026 `grouped_layers`/`layer_bounds` fixtures, whose stored order
        matches the alphabetical sort, not the document/creation order
        py_aep builds the items in). This rebuilds both the model `items`
        list and the backing `Sfdr` chunk blocks to match. Used only by the
        layered-import path; it does not affect `add_comp`/`add_folder`.
        """
        header, blocks = self._child_chunk_blocks()
        blocks.sort(key=lambda b: b[0].name.lower())
        self._children_container[:] = header + [
            c for _, chunks in blocks for c in chunks
        ]
        self.items.sort(key=lambda item: item.name.lower())

    def _child_chunk_blocks(
        self,
    ) -> tuple[list[Chunk], list[tuple[Item, list[Chunk]]]]:
        """Partition `_children_container` into a leading header and one
        chunk block per child item (the item's chunk list plus any
        trailing non-item chunks, e.g. view data)."""
        by_item_list = {id(item._item_list): item for item in self.items}
        header: list[Chunk] = []
        blocks: list[tuple[Item, list[Chunk]]] = []
        for chunk in self._children_container:
            item = by_item_list.get(id(chunk))
            if item is not None:
                blocks.append((item, [chunk]))
            elif blocks:
                blocks[-1][1].append(chunk)
            else:
                header.append(chunk)
        return header, blocks

    def _reposition_child_sorted(self, item: Item) -> None:
        """Move one child to its case-insensitive alphabetical position
        among the current siblings.

        AE stores folder children in Project-panel display order and
        inserts a precompose result comp at that position. Unlike
        `_sort_children_by_name` this moves only `item`, leaving the
        other children's stored order untouched.
        """
        header, blocks = self._child_chunk_blocks()
        moved = next(b for b in blocks if b[0] is item)
        blocks.remove(moved)
        key = item.name.lower()
        pos = next(
            (i for i, b in enumerate(blocks) if b[0].name.lower() > key),
            len(blocks),
        )
        blocks.insert(pos, moved)
        self._children_container[:] = header + [
            c for _, chunks in blocks for c in chunks
        ]
        self.items[:] = [b[0] for b in blocks]
