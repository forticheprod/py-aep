"""Tests for ViewOptions model parsing using samples from models/view/.

These tests verify that py_aep correctly reads viewer panel settings
(channels, exposure, zoom, fast preview, toggle flags, etc.) from the
`fips` chunks in the binary AEP format.

The viewer panel data is accessed via `project.active_viewer`, which
represents the focused Composition/Layer/Footage panel. Each panel has
one or more `View` objects containing `ViewOptions`.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from conftest import parse_app

from py_aep import (
    ChannelType,
    FastPreviewType,
    ViewerType,
    ViewOptions,
)
from py_aep import parse as parse_aep
from py_aep.binary.misc_chunks import FipsChunk

if TYPE_CHECKING:
    from py_aep import Application

SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "models" / "view"


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


class TestViewActive:
    """Tests for View.active and View.set_active()."""

    def test_first_view_active_by_default(self) -> None:
        """The first view should be active by default."""
        app = parse_app(SAMPLES_DIR / "roi_base.aep")
        assert app.active_viewer is not None
        assert app.active_viewer.views[0].active is True

    def test_set_active_changes_index(self) -> None:
        """set_active() should update the viewer's active_view_index."""
        app = parse_app(SAMPLES_DIR / "roi_left_viewer.aep")
        assert app.active_viewer is not None
        viewer = app.active_viewer
        assert len(viewer.views) == 2
        assert viewer.active_view_index == 0
        assert viewer.views[0].active is True
        assert viewer.views[1].active is False

        viewer.views[1].set_active()
        assert viewer.active_view_index == 1
        assert viewer.views[0].active is False
        assert viewer.views[1].active is True

    def test_active_view_index_setter_validation(self) -> None:
        """Setting an invalid active_view_index should raise ValueError."""
        app = parse_app(SAMPLES_DIR / "roi_base.aep")
        assert app.active_viewer is not None
        viewer = app.active_viewer
        with pytest.raises(ValueError):
            viewer.active_view_index = 99


def _get_active_app_and_options(aep_path: Path) -> tuple[Application, ViewOptions]:
    """Parse a non-cached app and return (app, active view options)."""
    app = parse_aep(aep_path)
    assert app.active_viewer is not None
    assert len(app.active_viewer.views) >= 1
    return app, app.active_viewer.views[0].options


def _roundtrip_options(app: Application, tmp_path: Path) -> ViewOptions:
    """Save the project, re-parse, and return the active view options."""
    out = tmp_path / "modified.aep"
    app.project.save(out)
    app2 = parse_aep(out)
    assert app2.active_viewer is not None
    assert len(app2.active_viewer.views) >= 1
    return app2.active_viewer.views[0].options


class TestRoundtripChannels:
    """Roundtrip tests for ViewOptions.channels."""

    def test_modify_channels(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(SAMPLES_DIR / "channels_rgb.aep")
        assert opts.channels == ChannelType.CHANNEL_RGB

        opts.channels = ChannelType.CHANNEL_ALPHA
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.channels == ChannelType.CHANNEL_ALPHA


class TestRoundtripCheckerboards:
    """Roundtrip tests for ViewOptions.checkerboards."""

    def test_toggle_checkerboards(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(
            SAMPLES_DIR / "transparency_grid_off.aep"
        )
        assert opts.checkerboards is False

        opts.checkerboards = True
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.checkerboards is True


class TestRoundtripDraft3d:
    """Roundtrip tests for ViewOptions.draft3d."""

    def test_toggle_draft3d(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(SAMPLES_DIR / "draft3d_false.aep")
        assert opts.draft3d is False

        opts.draft3d = True
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.draft3d is True


class TestRoundtripExposure:
    """Roundtrip tests for ViewOptions.exposure."""

    def test_modify_exposure(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(SAMPLES_DIR / "exposure_0.0.aep")
        assert opts.exposure == 0.0

        opts.exposure = 5.5
        opts2 = _roundtrip_options(app, tmp_path)
        assert math.isclose(opts2.exposure, 5.5, abs_tol=0.01)

    def test_exposure_validation_rejects_too_high(self) -> None:
        _, opts = _get_active_app_and_options(SAMPLES_DIR / "exposure_0.0.aep")
        with pytest.raises(ValueError, match="must be <= 40.0"):
            opts.exposure = 41.0

    def test_exposure_validation_rejects_too_low(self) -> None:
        _, opts = _get_active_app_and_options(SAMPLES_DIR / "exposure_0.0.aep")
        with pytest.raises(ValueError, match="must be >= -40.0"):
            opts.exposure = -41.0


class TestRoundtripFastPreview:
    """Roundtrip tests for ViewOptions.fast_preview."""

    def test_modify_fast_preview_to_wireframe(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(SAMPLES_DIR / "fast_preview_off.aep")
        assert opts.fast_preview == FastPreviewType.FP_OFF

        opts.fast_preview = FastPreviewType.FP_WIREFRAME
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.fast_preview == FastPreviewType.FP_WIREFRAME

    def test_modify_fast_preview_to_adaptive(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(SAMPLES_DIR / "fast_preview_off.aep")
        opts.fast_preview = FastPreviewType.FP_ADAPTIVE_RESOLUTION
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.fast_preview == FastPreviewType.FP_ADAPTIVE_RESOLUTION

    def test_modify_fast_preview_to_off(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(
            SAMPLES_DIR / "fast_preview_wireframe.aep"
        )
        assert opts.fast_preview == FastPreviewType.FP_WIREFRAME

        opts.fast_preview = FastPreviewType.FP_OFF
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.fast_preview == FastPreviewType.FP_OFF

    def test_modify_fast_preview_to_draft(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(SAMPLES_DIR / "fast_preview_off.aep")
        opts.fast_preview = FastPreviewType.FP_DRAFT
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.fast_preview == FastPreviewType.FP_DRAFT

    def test_modify_fast_preview_to_fast_draft(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(SAMPLES_DIR / "fast_preview_off.aep")
        opts.fast_preview = FastPreviewType.FP_FAST_DRAFT
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.fast_preview == FastPreviewType.FP_FAST_DRAFT


class TestRoundtripGrid:
    """Roundtrip tests for ViewOptions.grid."""

    def test_toggle_grid(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(SAMPLES_DIR / "grid_off.aep")
        assert opts.grid is False

        opts.grid = True
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.grid is True


class TestRoundtripGuidesLocked:
    """Roundtrip tests for ViewOptions.guides_locked."""

    def test_toggle_guides_locked(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(SAMPLES_DIR / "lock_guides_off.aep")
        assert opts.guides_locked is False

        opts.guides_locked = True
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.guides_locked is True


class TestRoundtripGuidesSnap:
    """Roundtrip tests for ViewOptions.guides_snap."""

    def test_toggle_guides_snap(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(SAMPLES_DIR / "snap_to_guides_off.aep")
        assert opts.guides_snap is False

        opts.guides_snap = True
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.guides_snap is True


class TestRoundtripGuidesVisibility:
    """Roundtrip tests for ViewOptions.guides_visibility."""

    def test_toggle_guides_visibility(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(SAMPLES_DIR / "guides_off.aep")
        assert opts.guides_visibility is False

        opts.guides_visibility = True
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.guides_visibility is True


class TestRoundtripMaskAndShapePath:
    """Roundtrip tests for ViewOptions.mask_and_shape_path."""

    def test_toggle_mask_and_shape_path(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(
            SAMPLES_DIR / "mask_and_shape_path_off.aep"
        )
        assert opts.mask_and_shape_path is False

        opts.mask_and_shape_path = True
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.mask_and_shape_path is True


class TestRoundtripProportionalGrid:
    """Roundtrip tests for ViewOptions.proportional_grid."""

    def test_toggle_proportional_grid(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(
            SAMPLES_DIR / "proportional_grid_off.aep"
        )
        assert opts.proportional_grid is False

        opts.proportional_grid = True
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.proportional_grid is True


class TestRoundtripRegionOfInterest:
    """Roundtrip tests for ViewOptions.region_of_interest."""

    def test_toggle_region_of_interest(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(SAMPLES_DIR / "roi_off.aep")
        assert opts.region_of_interest is False

        opts.region_of_interest = True
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.region_of_interest is True


class TestRoundtripRulers:
    """Roundtrip tests for ViewOptions.rulers."""

    def test_toggle_rulers(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(SAMPLES_DIR / "rulers_off.aep")
        assert opts.rulers is False

        opts.rulers = True
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.rulers is True


class TestRoundtripTitleActionSafe:
    """Roundtrip tests for ViewOptions.title_action_safe."""

    def test_toggle_title_action_safe(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(
            SAMPLES_DIR / "title_action_safe_off.aep"
        )
        assert opts.title_action_safe is False

        opts.title_action_safe = True
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.title_action_safe is True


class TestRoundtripUseDisplayColorManagement:
    """Roundtrip tests for ViewOptions.use_display_color_management."""

    def test_toggle_display_color_management(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(
            SAMPLES_DIR / "channels_use_display_color_management_off.aep"
        )
        assert opts.use_display_color_management is False

        opts.use_display_color_management = True
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.use_display_color_management is True


class TestRoundtripZoom:
    """Roundtrip tests for ViewOptions.zoom."""

    def test_modify_zoom(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(SAMPLES_DIR / "zoom_100.aep")
        assert opts.zoom == 1.0

        opts.zoom = 0.5
        opts2 = _roundtrip_options(app, tmp_path)
        assert math.isclose(opts2.zoom, 0.5, rel_tol=0.001)

    def test_zoom_validation_rejects_too_high(self) -> None:
        _, opts = _get_active_app_and_options(SAMPLES_DIR / "zoom_100.aep")
        with pytest.raises(ValueError, match="must be <= 16.0"):
            opts.zoom = 17.0

    def test_zoom_validation_rejects_too_low(self) -> None:
        _, opts = _get_active_app_and_options(SAMPLES_DIR / "zoom_100.aep")
        with pytest.raises(ValueError, match="must be >= 0.01"):
            opts.zoom = 0.0


class TestRoundtripRoi:
    """Roundtrip tests for ViewOptions ROI coordinates."""

    def test_modify_roi_coordinates(self, tmp_path: Path) -> None:
        app, opts = _get_active_app_and_options(SAMPLES_DIR / "roi_base.aep")
        assert opts.roi_top == 111

        opts.roi_top = 50
        opts.roi_left = 60
        opts.roi_bottom = 400
        opts.roi_right = 450
        opts2 = _roundtrip_options(app, tmp_path)
        assert opts2.roi_top == 50
        assert opts2.roi_left == 60
        assert opts2.roi_bottom == 400
        assert opts2.roi_right == 450


class TestRoiValidation:
    """Tests for ROI coordinate validation."""

    def test_roi_top_rejects_negative(self) -> None:
        opts = _get_active_view_options(SAMPLES_DIR / "roi_base.aep")
        with pytest.raises(ValueError, match="must be >= 0"):
            opts.roi_top = -1

    def test_roi_left_rejects_negative(self) -> None:
        opts = _get_active_view_options(SAMPLES_DIR / "roi_base.aep")
        with pytest.raises(ValueError, match="must be >= 0"):
            opts.roi_left = -1

    def test_roi_top_rejects_above_bottom(self) -> None:
        opts = _get_active_view_options(SAMPLES_DIR / "roi_base.aep")
        # roi_bottom is 339, so roi_top must be <= 338
        with pytest.raises(ValueError, match="must be <= 338"):
            opts.roi_top = 339

    def test_roi_left_rejects_above_right(self) -> None:
        opts = _get_active_view_options(SAMPLES_DIR / "roi_base.aep")
        # roi_right is 366, so roi_left must be <= 365
        with pytest.raises(ValueError, match="must be <= 365"):
            opts.roi_left = 366

    def test_roi_bottom_rejects_below_top(self) -> None:
        opts = _get_active_view_options(SAMPLES_DIR / "roi_base.aep")
        # roi_top is 111, so roi_bottom must be >= 112
        with pytest.raises(ValueError, match="must be >= 112"):
            opts.roi_bottom = 111

    def test_roi_right_rejects_below_left(self) -> None:
        opts = _get_active_view_options(SAMPLES_DIR / "roi_base.aep")
        # roi_left is 123, so roi_right must be >= 124
        with pytest.raises(ValueError, match="must be >= 124"):
            opts.roi_right = 123

    def test_roi_bottom_rejects_above_comp_height(self) -> None:
        opts = _get_active_view_options(SAMPLES_DIR / "roi_base.aep")
        # Comp height is 500
        with pytest.raises(ValueError, match="must be <= 500"):
            opts.roi_bottom = 501

    def test_roi_right_rejects_above_comp_width(self) -> None:
        opts = _get_active_view_options(SAMPLES_DIR / "roi_base.aep")
        # Comp width is 500
        with pytest.raises(ValueError, match="must be <= 500"):
            opts.roi_right = 501

    def test_roi_rejects_float(self) -> None:
        opts = _get_active_view_options(SAMPLES_DIR / "roi_base.aep")
        with pytest.raises(TypeError, match="an integer"):
            opts.roi_top = 50.5  # type: ignore[assignment]

    def test_roi_accepts_valid_values(self) -> None:
        # Must parse a fresh (uncached) copy: this test writes valid ROI
        # values, and parse_app is lru_cached for the session, so mutating
        # the shared roi_base.aep app would corrupt the read-only ROI tests
        # (e.g. test_roi_base) when they land on the same xdist worker.
        _, opts = _get_active_app_and_options(SAMPLES_DIR / "roi_base.aep")
        opts.roi_top = 0
        opts.roi_left = 0
        opts.roi_bottom = 500
        opts.roi_right = 500
        assert opts.roi_top == 0
        assert opts.roi_left == 0
        assert opts.roi_bottom == 500
        assert opts.roi_right == 500


class TestViewOptionsWithoutItem:
    """Version-gated fields work when the viewer's item is no AVItem.

    parsers/view.py creates `ViewOptions(_item=None)` for such viewers;
    the `min_version` gate must be skipped (write allowed) when no AE
    version can be determined, instead of raising TypeError.
    """

    def test_set_and_read_gated_fields_with_item_none(self) -> None:
        opts = ViewOptions(_fips=FipsChunk(), _item=None)

        opts.rulers = True
        assert opts.rulers is True
        opts.guides_locked = True
        assert opts.guides_locked is True
        opts.guides_snap = True
        assert opts.guides_snap is True
        opts.guides_visibility = True
        assert opts.guides_visibility is True

    def test_gated_enum_field_with_item_none(self) -> None:
        opts = ViewOptions(_fips=FipsChunk(), _item=None)

        opts.fast_preview = FastPreviewType.FP_WIREFRAME
        assert opts.fast_preview == FastPreviewType.FP_WIREFRAME
