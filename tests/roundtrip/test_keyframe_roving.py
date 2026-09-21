"""Tests for roving keyframe re-timing on spatial properties.

`keyframe_roving.aep` was saved by After Effects with keyframes 1 and 2 of a
four-keyframe Position path set to "Rove Across Time", so the times it holds
for them are the times AE computed. Re-deriving them has to land on the same
values.

Mutation tests parse a fresh (uncached) copy so changes do not leak between
tests, and the persistence class additionally asserts results survive a
save / re-parse round-trip.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import parse_project_fresh

from py_aep.models import Layer, Project, Property

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "property"


def _position(sample: str) -> Property:
    project = parse_project_fresh(SAMPLES_DIR / sample)
    layer: Layer = project.compositions[0].layers[0]
    prop = layer.transform.property("ADBE Position")
    assert prop is not None
    return prop


def _position_from(project: Project) -> Property:
    layer: Layer = project.compositions[0].layers[0]
    prop = layer.transform.property("ADBE Position")
    assert prop is not None
    return prop


def _times(prop: Property) -> list[int]:
    """Stored (sub-frame) keyframe times, which `frame_time` would round."""
    return [kf._ldat_item.time_units for kf in prop.keyframes]


class TestRoundtripRovingRetimesToAEValues:
    """The re-timing model reproduces what AE saved."""

    def test_recompute_is_idempotent(self) -> None:
        prop = _position("keyframe_roving.aep")
        assert [kf.roving for kf in prop.keyframes] == [False, True, True, False]
        expected = _times(prop)
        prop._redistribute_roving_keyframes()
        assert _times(prop) == expected

    def test_rederived_from_clobbered_times(self) -> None:
        prop = _position("keyframe_roving.aep")
        expected = _times(prop)
        for index in (1, 2):
            prop.keyframes[index]._ldat_item.time_units = 1234 * index
        # Touching one member re-times the whole run it belongs to.
        prop.keyframes[1].roving = True
        assert _times(prop) == expected

    def test_bounding_keyframes_keep_their_times(self) -> None:
        prop = _position("keyframe_roving.aep")
        first, last = _times(prop)[0], _times(prop)[-1]
        prop.keyframes[2].roving = True
        assert _times(prop)[0] == first
        assert _times(prop)[-1] == last

    def test_times_stay_ordered(self) -> None:
        prop = _position("keyframe_roving.aep")
        prop.keyframes[0].value = [0.0, 0.0, 0.0]
        times = _times(prop)
        assert times == sorted(times)
        assert len(set(times)) == len(times)


class TestRoundtripRovingFollowsBoundingEase:
    """The bounding keyframes' ease shapes the run, not just arc length.

    `keyframe_roving.aep` has three equal-length path segments and no ease
    (influence 0), so AE spread its run evenly. Adding a symmetric
    ease-in-out has to pull both roving keyframes toward the middle of the
    span: the motion starts slow, so covering the first third of the path
    now takes more than a third of the time.
    """

    def test_ease_in_out_pulls_the_run_inward(self) -> None:
        prop = _position("keyframe_roving.aep")
        span = _times(prop)[-1]
        assert _times(prop)[1:3] == [span // 3, span * 2 // 3]

        prop.keyframes[0].out_temporal_ease[0].influence = 100.0 / 3.0
        prop.keyframes[-1].in_temporal_ease[0].influence = 100.0 / 3.0
        prop.keyframes[1].roving = True

        eased = _times(prop)
        assert eased[1] > span // 3
        assert eased[2] < span * 2 // 3
        # Symmetric ease on a symmetric path stays symmetric.
        assert abs((eased[1] - 0) - (span - eased[2])) <= 1


class TestRoundtripRovingBoundaryGuard:
    """The outermost keyframes bound every run and cannot rove themselves."""

    @pytest.mark.parametrize("index", [0, -1])
    def test_first_and_last_cannot_rove(self, index: int) -> None:
        prop = _position("keyframe_roving.aep")
        with pytest.raises(ValueError, match="cannot rove"):
            prop.keyframes[index].roving = True

    def test_middle_keyframe_is_allowed(self) -> None:
        prop = _position("keyframe_roving.aep")
        prop.keyframes[1].roving = True
        assert prop.keyframes[1].roving is True


class TestRoundtripRovingTriggers:
    """A bounding keyframe's time or value re-times the run it bounds."""

    def test_frame_time_retimes_the_run(self) -> None:
        prop = _position("keyframe_roving.aep")
        before = _times(prop)
        # Stretching the span the run sits in spreads the run over it.
        prop.keyframes[3].frame_time = 300
        after = _times(prop)
        assert after[1] > before[1]
        assert after[2] > before[2]
        assert after[0] == before[0]
        assert prop.keyframes[3].frame_time == 300

    def test_roved_times_are_not_whole_frames(self) -> None:
        prop = _position("keyframe_roving.aep")
        prop.keyframes[3].frame_time = 199
        units_per_frame = prop.keyframes[0]._time_scale * 256.0
        # A whole-frame-only implementation could not produce a remainder.
        assert any(time % units_per_frame != 0 for time in _times(prop)[1:3]), (
            "roved times should not all land on frame boundaries"
        )

    def test_value_retimes_the_run(self) -> None:
        prop = _position("keyframe_roving.aep")
        before = _times(prop)
        # Lengthening the first path segment pushes the roving keyframes later.
        prop.keyframes[0].value = [-400.0, 150.0, 0.0]
        after = _times(prop)
        assert after[1] > before[1]
        assert after[2] > before[2]
        assert after[0] == before[0]
        assert after[3] == before[3]

    def test_spatial_tangent_retimes_the_run(self) -> None:
        prop = _position("keyframe_roving.aep")
        before = _times(prop)
        # Adding a curve to the first segment changes the arc length,
        # which shifts where the roving keyframes land.
        prop.keyframes[0].out_spatial_tangent = [100.0, 0.0, 0.0]
        after = _times(prop)
        assert after[1:3] != before[1:3]
        assert after[0] == before[0]
        assert after[3] == before[3]

    def test_clearing_roving_pins_that_keyframe(self) -> None:
        prop = _position("keyframe_roving.aep")
        pinned = _times(prop)[2]
        prop.keyframes[2].roving = False
        assert prop.keyframes[2].roving is False
        assert _times(prop)[2] == pinned


class TestRoundtripRovingNonSpatial:
    """AE rejects roving on a non-spatial property with a ValueError."""

    def test_scale_rejects_roving(self) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "keyframe_bezier_ease_scale.aep")
        prop = project.compositions[0].layers[0].transform.property("ADBE Scale")
        assert prop is not None
        assert prop.is_spatial is False
        with pytest.raises(ValueError, match="spatial"):
            prop.keyframes[1].roving = True

    def test_opacity_rejects_roving(self) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "keyframe_bounce_pattern.aep")
        prop = project.compositions[0].layers[0].transform.property("ADBE Opacity")
        assert prop is not None
        assert prop.is_spatial is False
        with pytest.raises(ValueError, match="spatial"):
            prop.keyframes[3].roving = True


class TestRoundtripRovingPersistence:
    """A re-timed roved keyframe survives `Project.save()` -> re-parse.

    `_redistribute_roving_keyframes` writes straight to `_ldat_item.time_units`
    (`Keyframe.frame_time` would quantise a sub-frame roved tick to a whole
    frame, per its own docstring), so this is the check that the raw value
    actually round-trips through the binary writer, not just through the
    in-memory model - `test_roved_times_are_not_whole_frames` above only
    proves the value is sub-frame, not that it survives a save.
    """

    def test_roved_tick_is_bit_identical_after_save_reparse(
        self, tmp_path: Path
    ) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "keyframe_roving.aep")
        prop = _position_from(project)
        # Re-derive from a clobbered time, like
        # test_rederived_from_clobbered_times, so the saved value is
        # provably the model's own answer and not just the untouched byte
        # AE originally wrote.
        prop.keyframes[1]._ldat_item.time_units = 4321
        prop.keyframes[1].roving = True
        in_memory = _times(prop)

        out = tmp_path / "keyframe_roving_saved.aep"
        project.save(out)

        reparsed = parse_project_fresh(out)
        on_disk = _times(_position_from(reparsed))

        assert on_disk == in_memory, (
            "save/reparse did not preserve the re-derived roved ticks "
            f"exactly: in-memory {in_memory}, on disk {on_disk}"
        )

    def test_non_spatial_roving_flag_survives_save_reparse(
        self, tmp_path: Path
    ) -> None:
        project = parse_project_fresh(SAMPLES_DIR / "keyframe_bounce_pattern.aep")
        prop = project.compositions[0].layers[0].transform.property("ADBE Opacity")
        assert prop is not None
        before_times = [kf._ldat_item.time_units for kf in prop.keyframes]

        prop.keyframes[3]._ldat_item.roving = True

        out = tmp_path / "keyframe_bounce_pattern_saved.aep"
        project.save(out)

        reparsed = parse_project_fresh(out)
        reparsed_prop = (
            reparsed.compositions[0].layers[0].transform.property("ADBE Opacity")
        )
        assert reparsed_prop is not None
        assert reparsed_prop.keyframes[3].roving is True
        assert [
            kf._ldat_item.time_units for kf in reparsed_prop.keyframes
        ] == before_times


class TestOrientationInert:
    """Orientation is spatial-valued but does not rove in AE (26.3x87):
    the menu accepts the command, the keyframe never moves. Unequal
    segments on purpose - equal spans would make re-timing a no-op and
    prove nothing."""

    def test_roved_orientation_keeps_its_time(self):
        project = parse_project_fresh(
            SAMPLES_DIR.parent / "layer" / "orientation_0_0_5.aep"
        )
        prop = None
        for layer in project.compositions[0].layers:
            candidate = layer.transform.property("ADBE Orientation")
            if candidate is not None:
                prop = candidate
                break
        assert prop is not None
        for time, z in [(0.0, 0.0), (0.5, 10.0), (1.0, 40.0)]:
            prop.set_value_at_time(time, [0.0, 0.0, z])
        keyframes = prop.keyframes
        keyframes[1]._ldat_item.roving = True
        before = [k._ldat_item.time_units for k in keyframes]
        prop._redistribute_roving_keyframes()
        assert [k._ldat_item.time_units for k in keyframes] == before
        assert keyframes[1].roving is True


class TestRoundtripRovingTimeIsDerived:
    """A roving keyframe has no time of its own.

    Every time write is followed by a redistribution that re-derives it from
    the path, so accepting one would silently discard the caller's value.
    """

    def test_setting_time_on_a_roving_keyframe_raises(self) -> None:
        prop = _position("keyframe_roving.aep")
        before = _times(prop)
        with pytest.raises(ValueError, match="derived from the spatial path"):
            prop.keyframes[1].time = 0.25
        assert _times(prop) == before

    def test_setting_frame_time_on_a_roving_keyframe_raises(self) -> None:
        prop = _position("keyframe_roving.aep")
        before = _times(prop)
        with pytest.raises(ValueError, match="derived from the spatial path"):
            prop.keyframes[1].frame_time = 6
        assert _times(prop) == before

    def test_an_anchor_still_moves_and_retimes_the_run(self) -> None:
        prop = _position("keyframe_roving.aep")
        before = _times(prop)
        prop.keyframes[-1].time = prop.keyframes[-1].time + 1.0
        after = _times(prop)
        assert after[-1] > before[-1]
        assert after[1:3] != before[1:3]

    def test_clearing_roving_makes_the_time_writable_again(self) -> None:
        prop = _position("keyframe_roving.aep")
        prop.keyframes[1].roving = False
        prop.keyframes[1].time = 0.25
        assert prop.keyframes[1].time == pytest.approx(0.25)


class TestRoundtripRovingEarlyOut:
    """Redistribution runs on every value, time and tangent write, so a
    property carrying no roving keyframe must be left completely alone."""

    def test_value_write_leaves_a_non_roving_run_untouched(self) -> None:
        prop = _position("keyframe_roving.aep")
        for kf in prop.keyframes:
            if kf.roving:
                kf.roving = False
        before = _times(prop)

        prop.keyframes[0].value = [-400.0, 150.0, 0.0]
        prop.keyframes[2].out_spatial_tangent = [80.0, 0.0, 0.0]

        assert _times(prop) == before

    def test_roving_run_still_retimes_after_the_early_out(self) -> None:
        prop = _position("keyframe_roving.aep")
        assert any(kf.roving for kf in prop.keyframes), "sample must carry a run"
        before = _times(prop)
        prop.keyframes[0].value = [-400.0, 150.0, 0.0]
        assert _times(prop) != before
