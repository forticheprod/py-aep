from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from ...binary.chunk import Chunk, ListChunk
from ...binary.ldat_chunks import (
    LHD3_BLOCK_SINGLE,
    LdatChunk,
    Lhd3Chunk,
    set_lhd3_count,
)
from ...binary.mutations import build_rq_settings_list
from ...binary.project_chunks import RhedChunk
from ...binary.render_chunks import ArsiChunk, RoutChunk

if TYPE_CHECKING:
    from ..items.composition import CompItem
    from ..project import Project
    from .render_queue_item import RenderQueueItem


def _ensure_materialized(chunk: Chunk) -> None:
    """Clear the `synthetic` flag on a chunk and its container subtree.

    `parse_render_queue` leaves a synthesized render-queue scaffold (a missing
    `LRdr`, settings `LIST:list`, or empty-queue `ldat`) marked `synthetic` so
    `write_aep` skips it and an untouched queue-less file round-trips
    byte-identically. The first `add()` calls this to materialize the whole
    subtree so the populated queue is serialized. A no-op for a normal AE file
    whose `LRdr` is already fully present and non-synthetic.
    """
    chunk.synthetic = False
    children = getattr(chunk, "chunks", None)
    if children is not None:
        for child in children:
            _ensure_materialized(child)


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

    @classmethod
    def _new(cls, parent: Project) -> RenderQueue:
        """Build an empty render queue with its backing `LIST:LRdr` tree.

        Mirrors the empty-queue scaffold AE writes and `parse_render_queue`
        yields: `Rhed` + empty `Rout` + a settings `LIST:list` (lhd3 plus a
        synthetic ldat) + empty `LItm` + `LSIf[ARsi]`. The settings ldat is
        synthetic so it is skipped by `write_aep()` until the first `add()`.
        """
        rhed = RhedChunk()
        rout = RoutChunk()
        settings, rs_lhd3, rs_ldat = build_rq_settings_list()
        litm = ListChunk(list_type="LItm")
        arsi = ArsiChunk()
        lrdr = ListChunk(
            list_type="LRdr",
            chunks=[
                rhed,
                rout,
                settings,
                litm,
                ListChunk(list_type="LSIf", chunks=[arsi]),
            ],
        )
        return cls(
            _lrdr=lrdr,
            _rs_lhd3=rs_lhd3,
            _rs_ldat=rs_ldat,
            _rout=rout,
            _litm=litm,
            _arsi=arsi,
            parent=parent,
            items=[],
        )

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
        rqi = RenderQueueItem._new(comp, parent=self)

        # Materialize any synthesized scaffold the parser left synthetic (an
        # empty-queue ldat, or - for a queue-less file - the whole LRdr tree),
        # so the populated queue is actually written. No-op for a normal file.
        _ensure_materialized(self._lrdr)

        # Append render settings to LRdr's ldat and keep the lhd3 capacity
        # counters in sync with the new item count - AE keeps _count_b /
        # _counter_a / _counter_b equal to `count` for this list and rejects
        # the file ("Invalid read length") when they go stale.
        self._rs_ldat.items.append(rqi._ldat)
        set_lhd3_count(self._rs_lhd3, self._rs_lhd3.count + 1, LHD3_BLOCK_SINGLE)

        # Append Rout items (5 per RQ item) and update header
        for ri in rqi._rout_items:
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
