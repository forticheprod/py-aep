"""Tests for OCIO config color-space enumeration.

The active-colorspace counts were verified set-equal to PyOpenColorIO (AE's OCIO
backend): samples/assets/config.ocio -> 22, AE's bundled ACES 1.2 -> 353.
"""

from __future__ import annotations

from pathlib import Path

from py_aep.color.ocio import (
    list_config_color_spaces,
    resolve_ocio_config,
)

CONFIG = Path(__file__).parent.parent.parent / "samples" / "assets" / "config.ocio"


class TestListConfigColorSpaces:
    def test_active_color_spaces(self) -> None:
        names = list_config_color_spaces(CONFIG)
        assert len(names) == 22  # == PyOpenColorIO getColorSpaceNames()
        # colorspaces + display_colorspaces are included
        assert "ACEScg" in names
        assert "ACEScct" in names
        assert "Raw" in names
        assert "sRGB - Display" in names
        assert "Linear Rec.709 (sRGB)" in names

    def test_inactive_color_spaces_excluded(self) -> None:
        names = list_config_color_spaces(CONFIG)
        # config.ocio lists these two in inactive_colorspaces.
        assert "CIE XYZ-D65 - Display-referred" not in names
        assert "CIE XYZ-D65 - Scene-referred" not in names

    def test_custom_ocio_tags_do_not_break_parsing(self) -> None:
        # The config is full of `!<ColorSpace>`/`!<View>`/`!<Rule>` tags; a
        # successful non-empty parse proves the tag-ignoring loader works.
        assert list_config_color_spaces(CONFIG)

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert list_config_color_spaces(tmp_path / "nope.ocio") == []


class TestResolveOcioConfig:
    def test_existing_path(self) -> None:
        assert resolve_ocio_config(str(CONFIG)) == CONFIG

    def test_empty_returns_none(self) -> None:
        assert resolve_ocio_config("") is None

    def test_unknown_name_returns_none(self) -> None:
        assert resolve_ocio_config("Not A Real Config Name") is None
