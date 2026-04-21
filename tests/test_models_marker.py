"""Tests for MarkerValue model parsing."""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from conftest import (
    get_comp,
    get_comp_marker_from_json_by_name,
    get_layer_marker_from_json_by_comp,
    load_expected,
    parse_project,
)

from py_aep import Project
from py_aep.enums import Label

if TYPE_CHECKING:
    from py_aep import MarkerValue

SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "models" / "marker"


def get_first_comp_marker(
    project: Project, comp_name: str | None = None
) -> MarkerValue:
    """Get the first marker value from a composition."""
    if comp_name:
        comp = get_comp(project, comp_name)
    else:
        assert len(project.compositions) >= 1
        comp = project.compositions[0]
    assert len(comp.markers) >= 1
    return comp.markers[0]


def get_first_layer_marker(
    project: Project, comp_name: str | None = None
) -> MarkerValue:
    """Get the first marker value from the first layer of a composition."""
    if comp_name:
        comp = get_comp(project, comp_name)
    else:
        assert len(project.compositions) >= 1
        comp = project.compositions[0]
    assert len(comp.layers) >= 1
    layer = comp.layers[0]
    assert len(layer.markers) >= 1
    return layer.markers[0]


class TestCompMarkerLabel:
    """Tests for composition marker label."""

    def test_label_0(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_marker")
        marker_json = get_comp_marker_from_json_by_name(expected, "label_0")
        marker = get_first_comp_marker(
            parse_project(SAMPLES_DIR / "comp_marker.aep"), "label_0"
        )
        assert marker.label.value == marker_json["label"] == 0

    def test_label_3(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_marker")
        marker_json = get_comp_marker_from_json_by_name(expected, "label_3")
        marker = get_first_comp_marker(
            parse_project(SAMPLES_DIR / "comp_marker.aep"), "label_3"
        )
        assert marker.label.value == marker_json["label"] == 3

    def test_label_8(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_marker")
        marker_json = get_comp_marker_from_json_by_name(expected, "label_8")
        marker = get_first_comp_marker(
            parse_project(SAMPLES_DIR / "comp_marker.aep"), "label_8"
        )
        assert marker.label.value == marker_json["label"] == 8


class TestCompMarkerDuration:
    """Tests for composition marker duration."""

    def test_duration_5(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_marker")
        marker_json = get_comp_marker_from_json_by_name(expected, "duration_5")
        marker = get_first_comp_marker(
            parse_project(SAMPLES_DIR / "comp_marker.aep"), "duration_5"
        )
        assert marker_json["duration"] == 5
        assert math.isclose(marker.duration, marker_json["duration"])


class TestCompMarkerComment:
    """Tests for composition marker comment."""

    def test_comment(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_marker")
        marker_json = get_comp_marker_from_json_by_name(expected, "comment")
        marker = get_first_comp_marker(
            parse_project(SAMPLES_DIR / "comp_marker.aep"), "comment"
        )
        assert marker.comment == marker_json["comment"] == "Test comment"


class TestCompMarkerChapter:
    """Tests for composition marker chapter."""

    def test_chapter(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_marker")
        marker_json = get_comp_marker_from_json_by_name(expected, "chapter")
        marker = get_first_comp_marker(
            parse_project(SAMPLES_DIR / "comp_marker.aep"), "chapter"
        )
        assert marker.chapter == marker_json["chapter"] == "Chapter 1"


class TestCompMarkerUrl:
    """Tests for composition marker URL."""

    def test_url(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_marker")
        marker_json = get_comp_marker_from_json_by_name(expected, "url")
        marker = get_first_comp_marker(
            parse_project(SAMPLES_DIR / "comp_marker.aep"), "url"
        )
        assert marker.url == marker_json["url"] == "https://example.com"


class TestCompMarkerFrameTarget:
    """Tests for composition marker frame target."""

    def test_frameTarget(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_marker")
        marker_json = get_comp_marker_from_json_by_name(expected, "frameTarget")
        marker = get_first_comp_marker(
            parse_project(SAMPLES_DIR / "comp_marker.aep"), "frameTarget"
        )
        assert marker.frame_target == marker_json["frameTarget"] == "_blank"


class TestCompMarkerCuePoint:
    """Tests for composition marker cue point."""

    def test_cuePointName(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_marker")
        marker_json = get_comp_marker_from_json_by_name(expected, "cuePointName")
        marker = get_first_comp_marker(
            parse_project(SAMPLES_DIR / "comp_marker.aep"), "cuePointName"
        )
        assert marker.cue_point_name == marker_json["cuePointName"] == "cue_test"


class TestCompMarkerProtectedRegion:
    """Tests for composition marker protected region."""

    def test_protectedRegion_true(self) -> None:
        expected = load_expected(SAMPLES_DIR, "comp_marker")
        marker_json = get_comp_marker_from_json_by_name(
            expected, "protectedRegion_true"
        )
        marker = get_first_comp_marker(
            parse_project(SAMPLES_DIR / "comp_marker.aep"), "protectedRegion_true"
        )
        assert marker_json["protectedRegion"] is True
        assert marker.protected_region == marker_json["protectedRegion"]


class TestLayerMarker:
    """Tests for layer markers."""

    def test_layer_marker_comment(self) -> None:
        expected = load_expected(SAMPLES_DIR, "layer_marker")
        marker_json = get_layer_marker_from_json_by_comp(expected, "layer_comment")
        marker = get_first_layer_marker(
            parse_project(SAMPLES_DIR / "layer_marker.aep"), "layer_comment"
        )
        assert marker.comment == marker_json["comment"] == "Layer marker comment"

    def test_layer_marker_duration(self) -> None:
        expected = load_expected(SAMPLES_DIR, "layer_marker")
        marker_json = get_layer_marker_from_json_by_comp(expected, "layer_duration")
        marker = get_first_layer_marker(
            parse_project(SAMPLES_DIR / "layer_marker.aep"), "layer_duration"
        )
        assert marker_json["duration"] == 3
        assert math.isclose(marker.duration, marker_json["duration"])

    def test_layer_marker_cuePointName(self) -> None:
        expected = load_expected(SAMPLES_DIR, "layer_marker")
        marker_json = get_layer_marker_from_json_by_comp(expected, "layer_cuePointName")
        marker = get_first_layer_marker(
            parse_project(SAMPLES_DIR / "layer_marker.aep"), "layer_cuePointName"
        )
        assert marker.cue_point_name == marker_json["cuePointName"] == "layer_cue_1"

    def test_layer_marker_with_startTime(self) -> None:
        """Marker time is at comp time 5, layer startTime is 3."""
        expected = load_expected(SAMPLES_DIR, "layer_marker")
        marker_json = get_layer_marker_from_json_by_comp(
            expected, "layer_marker_with_startTime"
        )
        marker = get_first_layer_marker(
            parse_project(SAMPLES_DIR / "layer_marker.aep"),
            "layer_marker_with_startTime",
        )
        assert marker.comment == marker_json["comment"] == "marker at comp time 5"

    def test_layer_multiple_markers(self) -> None:
        """Three markers on one layer, parsed in correct order."""
        project = parse_project(SAMPLES_DIR / "layer_marker.aep")
        comp = get_comp(project, "layer_multiple_markers")
        layer = comp.layers[0]
        assert len(layer.markers) == 3
        assert layer.markers[0].comment == "first marker"
        assert layer.markers[1].comment == "second marker"
        assert layer.markers[2].comment == "Third"


class TestRoundtripMarkerComment:
    """Roundtrip tests for MarkerValue.comment."""

    def test_modify_comment(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "comment")
        original = marker.comment
        assert original != ""

        marker.comment = "modified comment"
        out = tmp_path / "modified_comment.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project(out), "comment")
        assert marker2.comment == "modified comment"


class TestRoundtripMarkerDuration:
    """Roundtrip tests for MarkerValue.duration and frame_duration."""

    def test_modify_frame_duration(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "duration_5")
        original_fd = marker.frame_duration

        marker.frame_duration = original_fd + 10
        out = tmp_path / "modified_frame_duration.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project(out), "duration_5")
        assert marker2.frame_duration == original_fd + 10

    def test_modify_duration(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "duration_5")

        marker.duration = 10.0
        out = tmp_path / "modified_duration.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project(out), "duration_5")
        assert math.isclose(marker2.duration, 10.0, abs_tol=0.01)


class TestValidateMarkerFrameDuration:
    """Validation tests for MarkerValue.frame_duration."""

    def test_frame_duration_rejects_negative(self) -> None:
        project = parse_project(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "duration_5")
        with pytest.raises(ValueError, match="must be >= 0"):
            marker.frame_duration = -1

    def test_frame_duration_rejects_float(self) -> None:
        project = parse_project(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "duration_5")
        with pytest.raises(TypeError, match="expected an integer"):
            marker.frame_duration = 1.5


class TestRoundtripMarkerLabel:
    """Roundtrip tests for MarkerValue.label."""

    def test_modify_label(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "label_3")
        assert marker.label == Label.AQUA

        marker.label = Label.RED
        out = tmp_path / "modified_label.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project(out), "label_3")
        assert marker2.label == Label.RED


class TestRoundtripMarkerNavigation:
    """Roundtrip tests for MarkerValue.navigation."""

    def test_modify_navigation(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "comment")
        original = marker.navigation

        marker.navigation = not original
        out = tmp_path / "modified_navigation.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project(out), "comment")
        assert marker2.navigation == (not original)
        assert marker2.event_cue_point == original


class TestRoundtripMarkerProtectedRegion:
    """Roundtrip tests for MarkerValue.protected_region."""

    def test_modify_protected_region(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "protectedRegion_true")
        assert marker.protected_region is True

        marker.protected_region = False
        out = tmp_path / "modified_protected_region.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project(out), "protectedRegion_true")
        assert marker2.protected_region is False


class TestRoundtripMarkerChapter:
    """Roundtrip tests for MarkerValue.chapter."""

    def test_modify_chapter(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "chapter")
        assert marker.chapter != ""

        marker.chapter = "modified chapter"
        out = tmp_path / "modified_chapter.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project(out), "chapter")
        assert marker2.chapter == "modified chapter"


class TestRoundtripMarkerUrl:
    """Roundtrip tests for MarkerValue.url."""

    def test_modify_url(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "url")
        assert marker.url != ""

        marker.url = "https://example.com/modified"
        out = tmp_path / "modified_url.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project(out), "url")
        assert marker2.url == "https://example.com/modified"


class TestRoundtripMarkerFrameTarget:
    """Roundtrip tests for MarkerValue.frame_target."""

    def test_modify_frame_target(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "frameTarget")
        assert marker.frame_target != ""

        marker.frame_target = "_blank"
        out = tmp_path / "modified_frame_target.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project(out), "frameTarget")
        assert marker2.frame_target == "_blank"


class TestRoundtripMarkerCuePointName:
    """Roundtrip tests for MarkerValue.cue_point_name."""

    def test_modify_cue_point_name(self, tmp_path: Path) -> None:
        project = parse_project(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "cuePointName")
        assert marker.cue_point_name != ""

        marker.cue_point_name = "modified_cue"
        out = tmp_path / "modified_cue_point_name.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project(out), "cuePointName")
        assert marker2.cue_point_name == "modified_cue"
