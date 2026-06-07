from __future__ import annotations

from typing import TYPE_CHECKING

from ...enums import ViewerType
from ..descriptors import ChunkField
from ..validators import _validate_number

if TYPE_CHECKING:
    from ...binary.scalar_chunks import AsciiChunk, U1Chunk
    from .view import View


class Viewer:
    """
    The `Viewer` object represents a Composition, Layer, or Footage panel.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        viewer = app.active_viewer
        print(viewer.type)
        ```

    See: https://ae-scripting.docsforadobe.dev/other/viewer/
    """

    type = ChunkField.enum(
        ViewerType,
        "_fitt",
        "value",
        transform=ViewerType.from_string,
        read_only=True,
    )
    """
    The content in the viewer panel. Read-only.
    """

    def __init__(
        self,
        *,
        _fitt: AsciiChunk,
        _foac: U1Chunk,
        _fiac: U1Chunk,
    ) -> None:
        self._fitt = _fitt
        self._foac = _foac
        self._fiac = _fiac
        self._views: list[View] = []
        self._active_view_index: int = 0

    @property
    def views(self) -> list[View]:
        """All of the [View][] objects associated with this viewer.
        Read-only."""
        return self._views

    @property
    def active_view_index(self) -> int:
        """The index of the active view in the viewer's `views` list.
        Read / Write.

        Note: The active locked view index is not persisted in the binary
        format. It defaults to 0 (first view). Set it manually or call
        `View.set_active()` to change which view is active."""
        return self._active_view_index

    @active_view_index.setter
    def active_view_index(self, value: int) -> None:
        # With no views the index is moot; clamp the upper bound to 0 so the
        # bound stays valid (an empty views list would otherwise give max=-1,
        # rejecting every value including 0).
        max_index = len(self._views) - 1 if self._views else 0
        _validate_number(min=0, max=max_index, integer=True)(value)
        self._active_view_index = value

    @property
    def active(self) -> bool:
        """When `True`, indicates if the viewer panel is active.
        Read-only."""
        return bool(self._foac and self._foac.value and self._fiac and self._fiac.value)
