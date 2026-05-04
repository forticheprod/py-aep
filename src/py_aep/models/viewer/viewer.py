from __future__ import annotations

import typing

from ...enums import ViewerType
from ..descriptors import ChunkField

if typing.TYPE_CHECKING:
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

    type = ChunkField[ViewerType](
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
        if self._views and not 0 <= value < len(self._views):
            msg = (
                f"active_view_index must be between 0 and "
                f"{len(self._views) - 1}, got {value}"
            )
            raise IndexError(msg)
        self._active_view_index = value

    @property
    def active(self) -> bool:
        """When `True`, indicates if the viewer panel is active.
        Read-only."""
        return bool(
            self._foac and self._foac.value and self._fiac and self._fiac.value
        )
