"""Tests for MarkerValue model parsing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from helpers import (
    get_comp,
    parse_project_fresh,
)

from py_aep import MarkerValue, Project
from py_aep import parse as parse_aep
from py_aep.enums import Label

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "marker"


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


class TestRoundtripMarkerComment:
    """Roundtrip tests for MarkerValue.comment."""

    def test_modify_comment(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "comment")
        original = marker.comment
        assert original != ""

        marker.comment = "modified comment"
        out = tmp_path / "modified_comment.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project_fresh(out), "comment")
        assert marker2.comment == "modified comment"


class TestRoundtripMarkerDuration:
    """Roundtrip tests for MarkerValue.duration and frame_duration."""

    def test_modify_frame_duration(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "duration_5")
        original_fd = marker.frame_duration

        marker.frame_duration = original_fd + 10
        out = tmp_path / "modified_frame_duration.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project_fresh(out), "duration_5")
        assert marker2.frame_duration == original_fd + 10

    def test_modify_duration(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "duration_5")

        marker.duration = 10.0
        out = tmp_path / "modified_duration.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project_fresh(out), "duration_5")
        assert math.isclose(marker2.duration, 10.0, abs_tol=0.01)


class TestValidateMarkerFrameDuration:
    """Validation tests for MarkerValue.frame_duration."""

    def test_frame_duration_rejects_negative(self) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "duration_5")
        with pytest.raises(ValueError, match="must be >= 0"):
            marker.frame_duration = -1

    def test_frame_duration_rejects_float(self) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "duration_5")
        with pytest.raises(TypeError, match="expected an integer"):
            marker.frame_duration = 1.5


class TestRoundtripMarkerLabel:
    """Roundtrip tests for MarkerValue.label."""

    def test_modify_label(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "label_3")
        assert marker.label == Label.AQUA

        marker.label = Label.RED
        out = tmp_path / "modified_label.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project_fresh(out), "label_3")
        assert marker2.label == Label.RED


class TestRoundtripMarkerNavigation:
    """Roundtrip tests for MarkerValue.navigation."""

    def test_modify_navigation(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "comment")
        original = marker.navigation

        marker.navigation = not original
        out = tmp_path / "modified_navigation.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project_fresh(out), "comment")
        assert marker2.navigation == (not original)
        assert marker2.event_cue_point == original


class TestRoundtripMarkerProtectedRegion:
    """Roundtrip tests for MarkerValue.protected_region."""

    def test_modify_protected_region(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "protectedRegion_true")
        assert marker.protected_region is True

        marker.protected_region = False
        out = tmp_path / "modified_protected_region.aep"
        project.save(out)
        marker2 = get_first_comp_marker(
            parse_project_fresh(out), "protectedRegion_true"
        )
        assert marker2.protected_region is False


class TestRoundtripMarkerChapter:
    """Roundtrip tests for MarkerValue.chapter."""

    def test_modify_chapter(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "chapter")
        assert marker.chapter != ""

        marker.chapter = "modified chapter"
        out = tmp_path / "modified_chapter.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project_fresh(out), "chapter")
        assert marker2.chapter == "modified chapter"


class TestRoundtripMarkerUrl:
    """Roundtrip tests for MarkerValue.url."""

    def test_modify_url(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "url")
        assert marker.url != ""

        marker.url = "https://example.com/modified"
        out = tmp_path / "modified_url.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project_fresh(out), "url")
        assert marker2.url == "https://example.com/modified"


class TestRoundtripMarkerFrameTarget:
    """Roundtrip tests for MarkerValue.frame_target."""

    def test_modify_frame_target(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "frameTarget")
        assert marker.frame_target != ""

        marker.frame_target = "_blank"
        out = tmp_path / "modified_frame_target.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project_fresh(out), "frameTarget")
        assert marker2.frame_target == "_blank"


class TestRoundtripMarkerCuePointName:
    """Roundtrip tests for MarkerValue.cue_point_name."""

    def test_modify_cue_point_name(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "comp_marker.aep")
        marker = get_first_comp_marker(project, "cuePointName")
        assert marker.cue_point_name != ""

        marker.cue_point_name = "modified_cue"
        out = tmp_path / "modified_cue_point_name.aep"
        project.save(out)
        marker2 = get_first_comp_marker(parse_project_fresh(out), "cuePointName")
        assert marker2.cue_point_name == "modified_cue"


class TestMarkerParams:
    """Tests for MarkerValue cue-point params."""

    def test_constructor_params(self) -> None:
        marker = MarkerValue(comment="c", params={"k1": "v1", "k2": "v2"})
        assert marker.params == {"k1": "v1", "k2": "v2"}

    def test_constructor_params_default_empty(self) -> None:
        assert MarkerValue().params == {}

    def test_constructor_params_invalid(self) -> None:
        with pytest.raises(ValueError, match="string key-value pairs"):
            MarkerValue(params={"k": 1})  # type: ignore[dict-item]

    def test_constructor_params_roundtrip(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "layer_marker.aep")
        comp = get_comp(project, "layer_multiple_markers")
        mp = comp.layers[0]["ADBE Marker"]
        mp.set_value_at_time(
            mp.keyframes[-1].time + 1.0,
            MarkerValue(comment="with params", params={"k1": "v1", "k2": "v2"}),
        )
        out = tmp_path / "marker_params.aep"
        project.save(out)
        comp2 = get_comp(parse_project_fresh(out), "layer_multiple_markers")
        mp2 = comp2.layers[0]["ADBE Marker"]
        marker2 = next(
            k.value for k in mp2.keyframes if k.value.comment == "with params"
        )
        assert marker2.params == {"k1": "v1", "k2": "v2"}
        # AE ignores params unless NmHd carries the pair count.
        assert marker2._nmhd.num_params == 2

    def test_params_grow_and_shrink_on_parsed_marker(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "layer_marker.aep")
        marker = get_first_layer_marker(project, "layer_multiple_markers")
        assert marker.params == {}

        marker.params = {"k1": "v1", "k2": "v2"}
        out = tmp_path / "marker_params_grow.aep"
        project.save(out)
        project2 = parse_project_fresh(out)
        marker2 = get_first_layer_marker(project2, "layer_multiple_markers")
        assert marker2.params == {"k1": "v1", "k2": "v2"}
        # AE ignores params unless NmHd carries the pair count.
        assert marker2._nmhd.num_params == 2

        marker2.params = {"k1": "x"}
        out2 = tmp_path / "marker_params_shrink.aep"
        project2.save(out2)
        project3 = parse_project_fresh(out2)
        marker3 = get_first_layer_marker(project3, "layer_multiple_markers")
        assert marker3.params == {"k1": "x"}
        assert marker3._nmhd.num_params == 1

        marker3.params = {}
        out3 = tmp_path / "marker_params_clear.aep"
        project3.save(out3)
        marker4 = get_first_layer_marker(
            parse_project_fresh(out3), "layer_multiple_markers"
        )
        assert marker4.params == {}
        assert marker4._nmhd.num_params == 0

    def test_params_set_after_keyframe_binding(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "layer_marker.aep")
        comp = get_comp(project, "layer_multiple_markers")
        mp = comp.layers[0]["ADBE Marker"]
        mp.set_value_at_time(mp.keyframes[-1].time + 1.0, MarkerValue(comment="late"))
        bound = next(k.value for k in mp.keyframes if k.value.comment == "late")
        bound.params = {"a": "1", "b": "2"}
        out = tmp_path / "marker_params_late.aep"
        project.save(out)
        comp2 = get_comp(parse_project_fresh(out), "layer_multiple_markers")
        mp2 = comp2.layers[0]["ADBE Marker"]
        marker2 = next(k.value for k in mp2.keyframes if k.value.comment == "late")
        assert marker2.params == {"a": "1", "b": "2"}

    def test_params_set_on_unbound_marker(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "layer_marker.aep")
        comp = get_comp(project, "layer_multiple_markers")
        mp = comp.layers[0]["ADBE Marker"]
        marker = MarkerValue(comment="unbound")
        marker.params = {"p": "q"}
        assert marker.params == {"p": "q"}
        mp.set_value_at_time(mp.keyframes[-1].time + 1.0, marker)
        out = tmp_path / "marker_params_unbound.aep"
        project.save(out)
        comp2 = get_comp(parse_project_fresh(out), "layer_multiple_markers")
        mp2 = comp2.layers[0]["ADBE Marker"]
        marker2 = next(k.value for k in mp2.keyframes if k.value.comment == "unbound")
        assert marker2.params == {"p": "q"}


class TestMarkerLazyParseRoundtrip:
    """Regression: comp markers parse lazily on first access; that
    access must not alter the saved bytes."""

    def test_access_then_save_is_byte_identical(self, tmp_path: Path) -> None:
        src = (SAMPLES_DIR / "comp_marker.aep").read_bytes()
        # Parse fresh: the conftest parse_project_fresh cache returns projects
        # other tests may have mutated.
        project = parse_aep(SAMPLES_DIR / "comp_marker.aep").project
        for comp in project.compositions:
            _ = comp.markers
        out = tmp_path / "out.aep"
        project.save(out)
        assert out.read_bytes() == src
