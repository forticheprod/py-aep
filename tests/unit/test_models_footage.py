"""Tests for FootageItem model parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep import parse as parse_aep

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "footage"


def _get_first_footage(aep_path: Path) -> object:
    """Parse an .aep and return the first footage item."""
    project = parse_aep(aep_path).project
    return project.footages[0]


class TestFootageReadOnly:
    """All FootageItem fields backed by source delegation are read-only."""

    def test_width_is_read_only(self) -> None:
        footage = _get_first_footage(SAMPLES_DIR / "solid_sizes.aep")
        with pytest.raises(AttributeError):
            footage.width = 100  # type: ignore[misc]

    def test_height_is_read_only(self) -> None:
        footage = _get_first_footage(SAMPLES_DIR / "solid_sizes.aep")
        with pytest.raises(AttributeError):
            footage.height = 100  # type: ignore[misc]

    def test_duration_is_read_only(self) -> None:
        footage = _get_first_footage(SAMPLES_DIR / "placeholder.aep")
        with pytest.raises(AttributeError):
            footage.duration = 5.0  # type: ignore[misc]

    def test_frame_rate_is_read_only(self) -> None:
        footage = _get_first_footage(SAMPLES_DIR / "footage_misc.aep")
        with pytest.raises(AttributeError):
            footage.frame_rate = 30.0  # type: ignore[misc]

    def test_frame_duration_is_read_only(self) -> None:
        footage = _get_first_footage(SAMPLES_DIR / "placeholder.aep")
        with pytest.raises(AttributeError):
            footage.frame_duration = 100  # type: ignore[misc]

    def test_pixel_aspect_is_read_only(self) -> None:
        footage = _get_first_footage(SAMPLES_DIR / "solid_sizes.aep")
        with pytest.raises(AttributeError):
            footage.pixel_aspect = 1.5  # type: ignore[misc]

    def test_footage_missing_is_read_only(self) -> None:
        footage = _get_first_footage(SAMPLES_DIR / "footage_missing.aep")
        with pytest.raises(AttributeError):
            footage.footage_missing = False  # type: ignore[misc]
