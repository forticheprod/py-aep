from __future__ import annotations

from typing import TYPE_CHECKING

from ...enums import ChannelType, FastPreviewType
from ..descriptors import ChunkField
from ..validators import _validate_number

if TYPE_CHECKING:
    from ...binary.misc_chunks import FipsChunk
    from ..items.av_item import AVItem


class ViewOptions:
    """
    The `ViewOptions` object represents the options for a given [View][] object.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        options = app.active_viewer.views[0].options
        print(options.zoom)
        ```

    See: https://ae-scripting.docsforadobe.dev/other/viewoptions/
    """

    channels = ChunkField.enum(
        ChannelType,
        "_fips",
        "channels",
    )
    """
    The state of the Channels menu. Read / Write.
    """

    checkerboards = ChunkField.bool(
        "_fips",
        "checkerboards",
    )
    """
    When `True`, checkerboards (transparency grid) is enabled in the current view.
    Read / Write.
    """

    draft3d = ChunkField.bool(
        "_fips",
        "draft3d",
    )
    """
    When `True`, Draft 3D mode is enabled for the Composition panel. This
    corresponds to the value of the Draft 3D button in the Composition panel.
    Read / Write.
    """

    exposure = ChunkField[float](
        "_fips",
        "exposure",
        validate=_validate_number(min=-40.0, max=40.0),
    )
    """
    The exposure value for the current view. Read / Write.
    """

    grid = ChunkField.bool(
        "_fips",
        "grid",
    )
    """When `True`, the grid overlay is visible in the view. Read / Write."""

    guides_locked = ChunkField.bool(
        "_fips",
        "guides_locked",
        min_version=16,
    )
    """When `True`, indicates guides are locked in the view. Read / Write."""

    guides_snap = ChunkField.bool(
        "_fips",
        "guides_snap",
        min_version=16,
    )
    """When `True`, indicates layers snap to guides when dragged in the view.
    Read / Write."""

    guides_visibility = ChunkField.bool(
        "_fips",
        "guides_visibility",
        min_version=16,
    )
    """
    When `True`, indicates guides are visible in the view. Read / Write.
    """

    mask_and_shape_path = ChunkField.bool(
        "_fips",
        "mask_and_shape_path",
    )
    """When `True`, indicates mask and shape paths are visible in the view.
    Read / Write."""

    proportional_grid = ChunkField.bool(
        "_fips",
        "proportional_grid",
    )
    """When `True`, indicates the proportional grid overlay is visible in the
    view. Read / Write."""

    region_of_interest = ChunkField.bool(
        "_fips",
        "region_of_interest",
    )
    """
    When `True`, the region of interest (ROI) selection is active in the view.
    Read / Write.
    """

    roi_top = ChunkField[int](
        "_fips",
        "roi_top",
        validate=_validate_number(
            min=0,
            max=lambda self: self.roi_bottom - 1,
            integer=True,
        ),
    )
    """Top coordinate of the region of interest in pixels. Read / Write."""

    roi_left = ChunkField[int](
        "_fips",
        "roi_left",
        validate=_validate_number(
            min=0,
            max=lambda self: self.roi_right - 1,
            integer=True,
        ),
    )
    """Left coordinate of the region of interest in pixels. Read / Write."""

    roi_bottom = ChunkField[int](
        "_fips",
        "roi_bottom",
        validate=_validate_number(
            min=lambda self: self.roi_top + 1,
            max=lambda self: self._item.height if self._item else None,
            integer=True,
        ),
    )
    """Bottom coordinate of the region of interest in pixels. Read / Write."""

    roi_right = ChunkField[int](
        "_fips",
        "roi_right",
        validate=_validate_number(
            min=lambda self: self.roi_left + 1,
            max=lambda self: self._item.width if self._item else None,
            integer=True,
        ),
    )
    """Right coordinate of the region of interest in pixels. Read / Write."""

    rulers = ChunkField.bool(
        "_fips",
        "rulers",
        min_version=16,
    )
    """When `True`, indicates rulers are shown in the view. Read / Write."""

    title_action_safe = ChunkField.bool(
        "_fips",
        "title_action_safe",
    )
    """
    When `True`, indicates title/action safe margin guides are visible in the
    view. Read / Write.
    """

    use_display_color_management = ChunkField.bool(
        "_fips",
        "use_display_color_management",
    )
    """
    When `True`, indicates display color management is enabled for the view.
    Read / Write.
    """

    zoom = ChunkField[float](
        "_fips",
        "zoom",
        validate=_validate_number(min=0.01, max=16.0),
    )
    """
    The current zoom value for the view, as a normalized percentage between 1%
    (0.01) and 1600% (16). Read / Write.
    """

    fast_preview = ChunkField.enum(
        FastPreviewType,
        "_fips",
        "fast_preview_type",
        min_version=12,
    )
    """The state of the Fast Previews menu. Read / Write."""

    def __init__(
        self,
        *,
        _fips: FipsChunk,
        _item: AVItem | None = None,
    ) -> None:
        self._fips = _fips
        self._item = _item
