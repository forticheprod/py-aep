"""Tests for ViewOptions model parsing using samples from models/view/.

These tests verify that py_aep correctly reads viewer panel settings
(channels, exposure, zoom, fast preview, toggle flags, etc.) from the
`fips` chunks in the binary AEP format.

The viewer panel data is accessed via `project.active_viewer`, which
represents the focused Composition/Layer/Footage panel. Each panel has
one or more `View` objects containing `ViewOptions`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from conftest import parse_app

from py_aep import (
    ChannelType,
    FastPreviewType,
    ViewerType,
    ViewOptions,
)

if TYPE_CHECKING:
    pass
SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "view"


def _get_active_view_options(aep_path: Path) -> ViewOptions:
    """Parse a project and return the ViewOptions of the active viewer's first view."""
    app = parse_app(aep_path)
    assert app.active_viewer is not None
    assert app.active_viewer.type == ViewerType.VIEWER_COMPOSITION
    assert len(app.active_viewer.views) >= 1
    return app.active_viewer.views[0].options


class TestViewOptionsChannels:
    """Tests for ViewOptions.channels attribute."""

    def test_channels_rgb(self) -> None:
        """Test RGB channel display mode (default)."""
        opts = _get_active_view_options(SAMPLES_DIR / "channels_rgb.aep")
        assert opts.channels == ChannelType.CHANNEL_RGB

    def test_channels_alpha(self) -> None:
        """Test Alpha channel display mode."""
        opts = _get_active_view_options(SAMPLES_DIR / "channels_alpha.aep")
        assert opts.channels == ChannelType.CHANNEL_ALPHA


class TestViewOptionsCheckerboards:
    """Tests for ViewOptions.checkerboards (transparency grid) attribute."""

    def test_transparency_grid_on(self) -> None:
        """Test transparency grid enabled."""
        opts = _get_active_view_options(SAMPLES_DIR / "transparency_grid_on.aep")
        assert opts.checkerboards is True

    def test_transparency_grid_off(self) -> None:
        """Test transparency grid disabled."""
        opts = _get_active_view_options(SAMPLES_DIR / "transparency_grid_off.aep")
        assert opts.checkerboards is False


class TestViewOptionsExposure:
    """Tests for ViewOptions.exposure attribute."""

    def test_exposure_zero(self) -> None:
        """Test exposure of 0.0 (no adjustment)."""
        opts = _get_active_view_options(SAMPLES_DIR / "exposure_0.0.aep")
        assert opts.exposure == 0.0

    def test_exposure_min(self) -> None:
        """Test minimum exposure of -40.0."""
        opts = _get_active_view_options(SAMPLES_DIR / "exposure_-40.0.aep")
        assert opts.exposure == -40.0


class TestViewOptionsFastPreview:
    """Tests for ViewOptions.fast_preview attribute."""

    def test_fast_preview_off(self) -> None:
        """Test fast preview off."""
        opts = _get_active_view_options(SAMPLES_DIR / "fast_preview_off.aep")
        assert opts.fast_preview == FastPreviewType.FP_OFF

    def test_fast_preview_wireframe(self) -> None:
        """Test wireframe fast preview mode."""
        opts = _get_active_view_options(SAMPLES_DIR / "fast_preview_wireframe.aep")
        assert opts.fast_preview == FastPreviewType.FP_WIREFRAME


class TestViewOptionsGrid:
    """Tests for ViewOptions.grid attribute."""

    def test_grid_on(self) -> None:
        """Test grid overlay enabled."""
        opts = _get_active_view_options(SAMPLES_DIR / "grid_on.aep")
        assert opts.grid is True

    def test_grid_off(self) -> None:
        """Test grid overlay disabled."""
        opts = _get_active_view_options(SAMPLES_DIR / "grid_off.aep")
        assert opts.grid is False


class TestViewOptionsGuidesVisibility:
    """Tests for ViewOptions.guides_visibility attribute."""

    def test_guides_on(self) -> None:
        """Test guides visible."""
        opts = _get_active_view_options(SAMPLES_DIR / "guides_on.aep")
        assert opts.guides_visibility is True

    def test_guides_off(self) -> None:
        """Test guides hidden."""
        opts = _get_active_view_options(SAMPLES_DIR / "guides_off.aep")
        assert opts.guides_visibility is False


class TestViewOptionsMaskAndShapePath:
    """Tests for ViewOptions.mask_and_shape_path attribute."""

    def test_mask_and_shape_path_on(self) -> None:
        """Test mask and shape path visibility enabled."""
        opts = _get_active_view_options(SAMPLES_DIR / "mask_and_shape_path_on.aep")
        assert opts.mask_and_shape_path is True

    def test_mask_and_shape_path_off(self) -> None:
        """Test mask and shape path visibility disabled."""
        opts = _get_active_view_options(SAMPLES_DIR / "mask_and_shape_path_off.aep")
        assert opts.mask_and_shape_path is False


class TestViewOptionsProportionalGrid:
    """Tests for ViewOptions.proportional_grid attribute."""

    def test_proportional_grid_on(self) -> None:
        """Test proportional grid enabled."""
        opts = _get_active_view_options(SAMPLES_DIR / "proportional_grid_on.aep")
        assert opts.proportional_grid is True

    def test_proportional_grid_off(self) -> None:
        """Test proportional grid disabled."""
        opts = _get_active_view_options(SAMPLES_DIR / "proportional_grid_off.aep")
        assert opts.proportional_grid is False


class TestViewOptionsRulers:
    """Tests for ViewOptions.rulers attribute."""

    def test_rulers_on(self) -> None:
        """Test rulers displayed."""
        opts = _get_active_view_options(SAMPLES_DIR / "rulers_on.aep")
        assert opts.rulers is True

    def test_rulers_off(self) -> None:
        """Test rulers hidden."""
        opts = _get_active_view_options(SAMPLES_DIR / "rulers_off.aep")
        assert opts.rulers is False


class TestViewOptionsTitleActionSafe:
    """Tests for ViewOptions.title_action_safe attribute."""

    def test_title_action_safe_on(self) -> None:
        """Test title/action safe guides displayed."""
        opts = _get_active_view_options(SAMPLES_DIR / "title_action_safe_on.aep")
        assert opts.title_action_safe is True

    def test_title_action_safe_off(self) -> None:
        """Test title/action safe guides hidden."""
        opts = _get_active_view_options(SAMPLES_DIR / "title_action_safe_off.aep")
        assert opts.title_action_safe is False


class TestViewOptionsUseDisplayColorManagement:
    """Tests for ViewOptions.use_display_color_management attribute."""

    def test_display_color_management_on(self) -> None:
        """Test display color management enabled (default)."""
        opts = _get_active_view_options(SAMPLES_DIR / "channels_rgb.aep")
        assert opts.use_display_color_management is True

    def test_display_color_management_off(self) -> None:
        """Test display color management disabled."""
        opts = _get_active_view_options(
            SAMPLES_DIR / "channels_use_display_color_management_off.aep"
        )
        assert opts.use_display_color_management is False


class TestViewOptionsZoom:
    """Tests for ViewOptions.zoom attribute."""

    def test_zoom_25(self) -> None:
        """Test 25% zoom level."""
        opts = _get_active_view_options(SAMPLES_DIR / "zoom_25.aep")
        assert opts.zoom == 0.25

    def test_zoom_100(self) -> None:
        """Test 100% zoom level."""
        opts = _get_active_view_options(SAMPLES_DIR / "zoom_100.aep")
        assert opts.zoom == 1.0


class TestViewOptionsRoi:
    """Tests for ViewOptions ROI coordinate attributes."""

    def test_roi_base(self) -> None:
        opts = _get_active_view_options(SAMPLES_DIR / "roi_base.aep")
        assert opts.roi_top == 111
        assert opts.roi_left == 123
        assert opts.roi_bottom == 339
        assert opts.roi_right == 366

    def test_roi_right_extended(self) -> None:
        opts = _get_active_view_options(SAMPLES_DIR / "roi_right.aep")
        assert opts.roi_top == 111
        assert opts.roi_left == 123
        assert opts.roi_bottom == 339
        assert opts.roi_right == 438

    def test_roi_left_extended(self) -> None:
        opts = _get_active_view_options(SAMPLES_DIR / "roi_left.aep")
        assert opts.roi_top == 111
        assert opts.roi_left == 60
        assert opts.roi_bottom == 339
        assert opts.roi_right == 366

    def test_roi_down_extended(self) -> None:
        opts = _get_active_view_options(SAMPLES_DIR / "roi_down.aep")
        assert opts.roi_top == 111
        assert opts.roi_left == 123
        assert opts.roi_bottom == 393
        assert opts.roi_right == 366

    def test_roi_full(self) -> None:
        opts = _get_active_view_options(SAMPLES_DIR / "roi_full.aep")
        assert opts.roi_top == 9
        assert opts.roi_left == 6
        assert opts.roi_bottom == 498
        assert opts.roi_right == 495

    def test_roi_on_zeroed(self) -> None:
        """ROI enabled but coordinates are all zero."""
        opts = _get_active_view_options(SAMPLES_DIR / "roi_on.aep")
        assert opts.region_of_interest is True
        assert opts.roi_top == 0
        assert opts.roi_left == 0
        assert opts.roi_bottom == 0
        assert opts.roi_right == 0

    def test_roi_off_zeroed(self) -> None:
        """ROI disabled, coordinates are all zero."""
        opts = _get_active_view_options(SAMPLES_DIR / "roi_off.aep")
        assert opts.region_of_interest is False
        assert opts.roi_top == 0
        assert opts.roi_left == 0
        assert opts.roi_bottom == 0
        assert opts.roi_right == 0


class TestViewOptionsGuidesSnap:
    """Tests for ViewOptions.guidesSnap attribute."""

    def test_snap_to_guides_on(self) -> None:
        """Test snap to guides enabled."""
        opts = _get_active_view_options(SAMPLES_DIR / "snap_to_guides_on.aep")
        assert opts.guides_snap is True

    def test_snap_to_guides_off(self) -> None:
        """Test snap to guides disabled."""
        opts = _get_active_view_options(SAMPLES_DIR / "snap_to_guides_off.aep")
        assert opts.guides_snap is False


class TestViewOptionsGuidesLocked:
    """Tests for ViewOptions.guidesLocked attribute."""

    def test_lock_guides_on(self) -> None:
        """Test lock guides enabled."""
        opts = _get_active_view_options(SAMPLES_DIR / "lock_guides_on.aep")
        assert opts.guides_locked is True

    def test_lock_guides_off(self) -> None:
        """Test lock guides disabled."""
        opts = _get_active_view_options(SAMPLES_DIR / "lock_guides_off.aep")
        assert opts.guides_locked is False
