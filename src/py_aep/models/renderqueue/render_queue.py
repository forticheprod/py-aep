from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
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

    def __init__(self, *, parent: Project, items: list[RenderQueueItem]) -> None:
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
