from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .view_options import ViewOptions
    from .viewer import Viewer


class View:
    """
    The `View` object represents a specific view.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        view = app.active_viewer.views[0]
        print(view.options)
        ```

    See: https://ae-scripting.docsforadobe.dev/other/view/
    """

    def __init__(
        self,
        *,
        _viewer: Viewer,
        options: ViewOptions,
    ) -> None:
        self._viewer = _viewer
        self._options = options

    @property
    def active(self) -> bool:
        """When `True`, indicates if the view is the active view in its
        viewer. Read-only.

        Note: The active locked view index is not persisted in the binary
        format. It defaults to 0 (first view) and can be changed via
        `set_active()` or by setting `viewer.active_view_index`."""
        return self._viewer.active_view_index == self._viewer.views.index(self)

    def set_active(self) -> None:
        """Make this the active view in its viewer.

        This sets the parent viewer's `active_view_index` to this view's
        index. If the viewer is associated with a composition, this also
        affects which view's ROI is used for output module effective
        dimensions."""
        self._viewer.active_view_index = self._viewer.views.index(self)

    @property
    def options(self) -> ViewOptions:
        """Options object for this View. Read-only."""
        return self._options
