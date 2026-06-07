from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from ...binary.chunk import ListChunk
from ...binary.ldat_chunks import LdatChunk, Lhd3Chunk
from ...binary.utils import find_by_list_type

if TYPE_CHECKING:
    from ...binary.render_chunks import ArsiChunk, RoutChunk
    from ..items.composition import CompItem
    from ..project import Project
    from .render_queue_item import RenderQueueItem


class RenderQueue:
    """
    The `RenderQueue` object represents the render automation process, the data
    and functionality that is available through the Render Queue panel of a
    particular After Effects project. Attributes provide access to items in
    the render queue and their render status.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        render_queue = app.project.render_queue
        for rq_item in render_queue:
            ...
        ```

    See: https://ae-scripting.docsforadobe.dev/renderqueue/renderqueue/
    """

    def __init__(
        self,
        *,
        _lrdr: ListChunk,
        _rs_lhd3: Lhd3Chunk,
        _rs_ldat: LdatChunk,
        _rout: RoutChunk,
        _litm: ListChunk,
        _arsi: ArsiChunk,
        parent: Project,
        items: list[RenderQueueItem],
    ) -> None:
        self._lrdr = _lrdr
        self._rs_lhd3 = _rs_lhd3
        self._rs_ldat = _rs_ldat
        self._rout = _rout
        self._litm = _litm
        self._arsi = _arsi
        self._items = items
        self._parent = parent

    def __iter__(self) -> Iterator[RenderQueueItem]:
        return iter(self.items)

    @property
    def items(self) -> list[RenderQueueItem]:
        """A collection of all items in the render queue. Read-only."""
        return self._items

    @property
    def parent(self) -> Project:
        """The [Project][] containing this render queue. Read-only."""
        return self._parent

    @property
    def num_items(self) -> int:
        """The number of items in the render queue. Read-only.

        Note:
            Equivalent to `len(render_queue.items)`
        """
        return len(self.items)

    def add(self, comp: CompItem) -> RenderQueueItem:
        """Add a composition to the render queue.

        Creates a new [RenderQueueItem][] with default render settings and
        a single default output module.

        Args:
            comp: The [CompItem][] to render.

        Returns:
            The newly created [RenderQueueItem][].
        """
        # Imported here to avoid a circular dependency at module load time.
        from ..items.composition import CompItem
        from .render_queue_item import RenderQueueItem

        if not isinstance(comp, CompItem):
            raise TypeError("comp must be a CompItem")

        # Create the new RQ item with all backing chunks
        rqi, rs_item, rout_items = RenderQueueItem._new(comp, parent=self)

        # When the render queue started empty, the settings 'list' holds only
        # an lhd3 and the parser created the ldat lazily (not in the tree).
        # Attach it on first add so the new settings actually get written.
        rs_list = find_by_list_type(chunks=self._lrdr.chunks, list_type="list")
        if not any(c.chunk_type == "ldat" for c in rs_list.chunks):
            rs_list.chunks.append(self._rs_ldat)

        # Append render settings to LRdr's ldat. Only `count` tracks the
        # item count; AE keeps count_b/counter_a/counter_b at their seeded
        # value of 1 regardless of item count (verified against real files
        # and duplicate(), which bumps only `count`).
        self._rs_ldat.items.append(rs_item)
        self._rs_lhd3.count += 1

        # Append Rout items (5 per RQ item) and update header
        for ri in rout_items:
            self._rout.items.append(ri)
        self._rout.count = len(self._rout.items)

        # Insert OM metadata and OM container into LItm
        self._litm.chunks.append(rqi._list_chunk)
        self._litm.chunks.append(rqi._lom)

        # AE flips two bytes in the LRdr "LSIf/ARsi" state chunk once the
        # render queue is non-empty; without this AE reports "missing data
        # in file" when opening the result. RenderQueueItem.remove clears the
        # non-empty flag again when the last item is removed.
        self._arsi.queue_nonempty = 1
        self._arsi.active_slot_state = 0x73

        # Register in model list
        self._items.append(rqi)

        return rqi
