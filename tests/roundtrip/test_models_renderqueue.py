"""Tests for RenderQueue model parsing."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest
from helpers import get_rqi

from py_aep import parse as parse_aep
from py_aep.binary.chunk import ListChunk, read_aep, write_aep
from py_aep.binary.render_chunks import (
    ROUT_ITEMS_PER_RQ_ITEM,
    OutputModuleSettingsItem,
    RenderSettingsItem,
)
from py_aep.binary.utils import find_by_list_type
from py_aep.enums import (
    FieldRender,
    FrameRateSetting,
    LogType,
    MotionBlurSetting,
    PostRenderAction,
    RenderQuality,
    ResizeQuality,
    RQItemStatus,
    TimeSpanSource,
)
from py_aep.enums.mappings import profile_id_for_name
from py_aep.models.renderqueue.render_queue_item import RenderQueueItem

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "renderqueue"
OM_SAMPLES_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "output_module"
)
BUGS_DIR = Path(__file__).parent.parent.parent / "samples" / "bugs"
AE_PREFS_DIR = os.getenv("AE_PREFS_DIR")
OCS_SAMPLES_DIR = (
    Path(__file__).parent.parent.parent
    / "samples"
    / "models"
    / "output_module"
    / "output_color_space"
)


def _assert_rout_consistent(app: object) -> None:
    """The Rout chunk holds a fixed block of items per RQ item.

    AE writes `ROUT_ITEMS_PER_RQ_ITEM` Rout entries per render queue item and
    the `count` field must match the number of entries. Parse/remove/duplicate
    must keep this invariant (otherwise AE reports "missing data in file").
    """
    rq = app.project.render_queue  # type: ignore[attr-defined]
    rout = rq._rout
    expected = len(rq.items) * ROUT_ITEMS_PER_RQ_ITEM
    assert len(rout.items) == expected, (
        f"expected {expected} Rout items for {len(rq.items)} RQ items, "
        f"got {len(rout.items)}"
    )
    assert rout.count == len(rout.items), (
        f"Rout.count={rout.count} != len(items)={len(rout.items)}"
    )


class TestRoundtripLogType:
    """Roundtrip tests for RenderQueueItem.log_type."""

    def test_modify_log_type(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.log_type = LogType.ERRORS_AND_PER_FRAME_INFO

        out = tmp_path / "modified_log_type.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.log_type == LogType.ERRORS_AND_PER_FRAME_INFO

    def test_log_type_validation_rejects_invalid(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(ValueError, match="Invalid value"):
            rqi.log_type = 9999


class TestRoundtripQueueItemNotify:
    """Roundtrip tests for RenderQueueItem.queue_item_notify."""

    def test_modify_queue_item_notify(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        original = rqi.queue_item_notify
        rqi.queue_item_notify = not original

        out = tmp_path / "modified_notify.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.queue_item_notify is (not original)


class TestRoundtripStatus:
    """Roundtrip tests for RenderQueueItem.status."""

    def test_set_status_directly(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.status = RQItemStatus.UNQUEUED

        out = tmp_path / "modified_status.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.status == RQItemStatus.UNQUEUED

    def test_modify_status_via_render(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.render = False

        out = tmp_path / "modified_status.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.status == RQItemStatus.UNQUEUED
        assert rqi2.render is False

    def test_status_resets_start_time_and_elapsed(self, tmp_path: Path) -> None:
        """Setting render resets start_time and elapsed_seconds
        for QUEUED/UNQUEUED statuses."""
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        # Prime with non-zero values via underlying chunk body
        rqi._ldat.start_time = 1000000
        rqi._ldat.elapsed_seconds = 42

        rqi.status = RQItemStatus.QUEUED
        assert rqi.start_time is None
        assert rqi.elapsed_seconds == 0

        out = tmp_path / "status_reset.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.start_time is None
        assert rqi2.elapsed_seconds == 0
        assert rqi2.status == RQItemStatus.QUEUED


class TestRoundtripRender:
    """Roundtrip tests for RenderQueueItem.render setter."""

    def test_set_render_false(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.render = False

        out = tmp_path / "render_false.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.render is False
        assert rqi2.status == RQItemStatus.UNQUEUED

    def test_set_render_true(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.render = False
        rqi.render = True

        out = tmp_path / "render_true.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.render is True
        assert rqi2.status == RQItemStatus.QUEUED


class TestRoundtripName:
    """Roundtrip tests for RenderQueueItem.name (template name)."""

    def test_modify_name(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.name = "Custom Template"

        out = tmp_path / "modified_name.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.name == "Custom Template"


class TestRoundtripTimeSpan:
    """Roundtrip tests for time span frame fields."""

    def test_modify_time_span_start_frame(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.time_span_start_frame = 10

        out = tmp_path / "modified_ts_start.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.time_span_start_frame == 10

    def test_modify_time_span_duration_frames(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.time_span_duration_frames = 48

        out = tmp_path / "modified_ts_dur.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.time_span_duration_frames == 48


class TestRoundtripStartTime:
    """Tests for RenderQueueItem.start_time (read-only)."""

    def test_start_time_is_read_only(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(AttributeError, match="read-only"):
            rqi.start_time = datetime(2025, 6, 15, 12, 0, 0)

    def test_start_time_default_is_none(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        assert rqi.start_time is None


class TestReadOnlyFields:
    """Tests that read-only fields raise on write."""

    def test_elapsed_seconds_is_read_only(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(AttributeError, match="read-only"):
            rqi.elapsed_seconds = 999


class TestSetSetting:
    """Tests for setting RenderQueueItem.settings."""

    def test_set_enum_value(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.settings["Quality"] = RenderQuality.DRAFT

        out = tmp_path / "quality_enum.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Quality"] == RenderQuality.DRAFT

    def test_set_int_value(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.settings["Quality"] = 1  # DRAFT

        out = tmp_path / "quality_int.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Quality"] == RenderQuality.DRAFT

    def test_set_string_value(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.settings["Motion Blur"] = "On for Checked Layers"

        out = tmp_path / "mblur_str.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Motion Blur"] == MotionBlurSetting.ON_FOR_CHECKED_LAYERS

    def test_set_resolution(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.settings["Resolution"] = [2, 2]

        out = tmp_path / "resolution.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Resolution"] == [2, 2]

    def test_set_skip_existing_files(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.settings["Skip Existing Files"] = True

        out = tmp_path / "skip_existing.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Skip Existing Files"] is True

    def test_set_frame_rate(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.settings["Use this frame rate"] = 30.0

        out = tmp_path / "frame_rate.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Use this frame rate"] == pytest.approx(30.0)

    def test_unknown_key_raises(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(KeyError, match="Unknown setting"):
            rqi.settings["Nonexistent"] = 42

    def test_read_only_key_raises(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(AttributeError, match="read-only"):
            rqi.settings["Use comp's frame rate"] = 30.0

    def test_invalid_enum_int_raises(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(ValueError, match="Invalid int value"):
            rqi.settings["Quality"] = 9999

    def test_invalid_enum_str_raises(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(ValueError, match="Invalid string"):
            rqi.settings["Quality"] = "SuperHD"

    def test_invalid_type_raises(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(TypeError, match="Expected"):
            rqi.settings["Quality"] = [1, 2, 3]


class TestRoundtripComment:
    """Roundtrip tests for the comment property."""

    def test_modify_existing_comment(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "comment_aaaaa.aep").project
        rqi = project.render_queue.items[0]
        assert rqi.comment == "aaaaa"
        rqi.comment = "new comment"

        out = tmp_path / "comment_modified.aep"
        project.save(out)
        rqi2 = parse_aep(out).project.render_queue.items[0]
        assert rqi2.comment == "new comment"

    def test_create_comment_from_none(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "2_rqitems.aep").project
        items = project.render_queue.items
        assert len(items) == 2
        for rqi in items:
            assert rqi._rcom_utf8 is None
            assert rqi.comment == ""

        items[0].comment = "first comment"
        items[1].comment = "second comment"

        out = tmp_path / "comment_created.aep"
        project.save(out)
        items2 = parse_aep(out).project.render_queue.items
        assert items2[0].comment == "first comment"
        assert items2[1].comment == "second comment"


class TestRoundtripOutputModuleIncludeSourceXmp:
    """Roundtrip tests for OutputModule.include_source_xmp."""

    def test_modify_include_source_xmp(self, tmp_path: Path) -> None:
        project = parse_aep(OM_SAMPLES_DIR / "om_misc.aep").project
        rqi = get_rqi(project, "include_source_xmp_data_on")
        om = rqi.output_modules[0]
        assert om.include_source_xmp is True
        om.include_source_xmp = False

        out = tmp_path / "xmp_off.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "include_source_xmp_data_on")
        om2 = rqi2.output_modules[0]
        assert om2.include_source_xmp is False

    def test_enable_include_source_xmp(self, tmp_path: Path) -> None:
        project = parse_aep(OM_SAMPLES_DIR / "include_source_xmp_data_off.aep").project
        om = project.render_queue.items[0].output_modules[0]
        assert om.include_source_xmp is False
        om.include_source_xmp = True

        out = tmp_path / "xmp_on.aep"
        project.save(out)
        om2 = parse_aep(out).project.render_queue.items[0].output_modules[0]
        assert om2.include_source_xmp is True


class TestRoundtripOutputModulePostRenderAction:
    """Roundtrip tests for OutputModule.post_render_action."""

    def test_modify_post_render_action(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        om = rqi.output_modules[0]
        om.post_render_action = PostRenderAction.IMPORT

        out = tmp_path / "pra_import.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        om2 = rqi2.output_modules[0]
        assert om2.post_render_action == PostRenderAction.IMPORT

    def test_post_render_action_validation_rejects_invalid(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        om = rqi.output_modules[0]
        with pytest.raises(ValueError, match="Invalid value"):
            om.post_render_action = 9999


class TestRoundtripFileTemplate:
    """Roundtrip tests for OutputModule.file_template property."""

    def test_file_template_read(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        om = rqi.output_modules[0]
        assert om.file_template  # should be non-empty

    def test_file_template_roundtrip(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        om = rqi.output_modules[0]
        original = om.file_template
        assert original  # non-empty

        # Replace the filename portion with a custom template
        sep = "\\" if "\\" in original else "/"
        last_sep = original.rfind(sep)
        new_template = original[: last_sep + 1] + "custom_output.[fileExtension]"
        om.file_template = new_template

        out = tmp_path / "ft_roundtrip.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        om2 = rqi2.output_modules[0]
        assert om2.file_template == new_template


class TestRoundtripSkipFrames:
    """Roundtrip tests for RenderQueueItem.skip_frames setter."""

    def test_set_skip_frames(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "skip_frames.aep").project
        rqi = get_rqi(project, "skip_frames_0")
        assert rqi.skip_frames == 0
        rqi.skip_frames = 1

        out = tmp_path / "skip1.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "skip_frames_0")
        assert rqi2.skip_frames == 1

    def test_set_skip_frames_back_to_0(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "skip_frames.aep").project
        rqi = get_rqi(project, "skip_frames_1")
        assert rqi.skip_frames == 1
        rqi.skip_frames = 0

        out = tmp_path / "skip0.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "skip_frames_1")
        assert rqi2.skip_frames == 0


class TestRoundtripTimeSpanStart:
    """Roundtrip tests for RenderQueueItem.time_span_start setter."""

    def test_set_time_span_start(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "time_span.aep").project
        rqi = get_rqi(project, "time_span_custom_start_1s23f")
        rqi.time_span_start = 2.0

        out = tmp_path / "ts_start.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "time_span_custom_start_1s23f")
        assert rqi2.time_span_start == pytest.approx(2.0, abs=0.04)

    def test_set_time_span_start_switches_to_custom(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "time_span.aep").project
        rqi = get_rqi(project, "time_span_length_of_comp")
        rqi.time_span_start = 1.0

        out = tmp_path / "ts_custom.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "time_span_length_of_comp")
        assert rqi2.time_span_start == pytest.approx(1.0, abs=0.04)


class TestRoundtripTimeSpanDuration:
    """Roundtrip tests for RenderQueueItem.time_span_duration setter."""

    def test_set_time_span_duration(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "time_span.aep").project
        rqi = get_rqi(project, "time_span_custom_24s13f")
        rqi.time_span_duration = 5.0

        out = tmp_path / "ts_dur.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "time_span_custom_24s13f")
        assert rqi2.time_span_duration == pytest.approx(5.0, abs=0.04)


class TestRoundtripTimeSpanEnd:
    """Roundtrip tests for time_span_end and time_span_end_frame setters."""

    def test_set_time_span_end(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "time_span.aep").project
        rqi = get_rqi(project, "time_span_custom_start_1s23f")
        start = rqi.time_span_start
        rqi.time_span_end = start + 3.0

        out = tmp_path / "ts_end.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "time_span_custom_start_1s23f")
        assert rqi2.time_span_duration == pytest.approx(3.0, abs=0.04)
        assert rqi2.time_span_end == pytest.approx(start + 3.0, abs=0.04)

    def test_set_time_span_end_frame(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.time_span_start_frame = 5
        rqi.time_span_end_frame = 30

        out = tmp_path / "ts_end_frame.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.time_span_start_frame == 5
        assert rqi2.time_span_duration_frames == 25
        assert rqi2.time_span_end_frame == 30


class TestRoundtripSettingsResolution:
    """Roundtrip tests for Resolution via SettingsView dict access."""

    def test_asymmetric_resolution(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.settings["Resolution"] = [7, 3]

        out = tmp_path / "res_asymmetric.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Resolution"] == [7, 3]

    def test_resolution_full_to_custom_roundtrip(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "resolution.aep").project
        rqi = get_rqi(project, "resolution_custom_7x3")
        assert rqi.settings["Resolution"] == [7, 3]

        rqi.settings["Resolution"] = [1, 1]
        out = tmp_path / "res_full.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "resolution_custom_7x3")
        assert rqi2.settings["Resolution"] == [1, 1]

        # And back to a different custom value
        rqi2.settings["Resolution"] = [8, 3]
        out2 = tmp_path / "res_custom_again.aep"
        rqi2._project.save(out2)
        rqi3 = get_rqi(parse_aep(out2).project, "resolution_custom_7x3")
        assert rqi3.settings["Resolution"] == [8, 3]


class TestRoundtripSettingsFrameRate:
    """Roundtrip tests for Use this frame rate (integer+fractional split)."""

    def test_fractional_frame_rate_29_97(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.settings["Frame Rate"] = FrameRateSetting.USE_THIS_FRAME_RATE
        rqi.settings["Use this frame rate"] = 29.97

        out = tmp_path / "fr_29_97.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Frame Rate"] == FrameRateSetting.USE_THIS_FRAME_RATE
        assert rqi2.settings["Use this frame rate"] == pytest.approx(29.97, abs=0.01)

    def test_integer_frame_rate_24(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "frame_rate.aep").project
        rqi = get_rqi(project, "frame_rate_24")
        assert rqi.settings["Use this frame rate"] == pytest.approx(24.0)

        rqi.settings["Use this frame rate"] = 60.0
        out = tmp_path / "fr_60.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "frame_rate_24")
        assert rqi2.settings["Use this frame rate"] == pytest.approx(60.0)

    def test_existing_fractional_roundtrip(self, tmp_path: Path) -> None:
        """Parse and save 29.97 without modification preserves the value."""
        project = parse_aep(SAMPLES_DIR / "frame_rate.aep").project
        rqi = get_rqi(project, "frame_rate_29_97")
        original = rqi.settings["Use this frame rate"]
        assert original == pytest.approx(29.97, abs=0.01)

        out = tmp_path / "fr_29_97_unchanged.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "frame_rate_29_97")
        assert rqi2.settings["Use this frame rate"] == pytest.approx(
            original, abs=0.001
        )


class TestRoundtripSettingsMultiWrite:
    """Roundtrip tests for multiple settings writes with save/reparse."""

    def test_multiple_settings(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")

        rqi.settings["Quality"] = RenderQuality.DRAFT
        rqi.settings["Resolution"] = [3, 3]
        rqi.settings["Motion Blur"] = MotionBlurSetting.ON_FOR_CHECKED_LAYERS
        rqi.settings["Field Render"] = FieldRender.UPPER_FIELD_FIRST

        out = tmp_path / "batch_multi.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Quality"] == RenderQuality.DRAFT
        assert rqi2.settings["Resolution"] == [3, 3]
        assert rqi2.settings["Motion Blur"] == MotionBlurSetting.ON_FOR_CHECKED_LAYERS
        assert rqi2.settings["Field Render"] == FieldRender.UPPER_FIELD_FIRST

    def test_frame_rate_pair(self, tmp_path: Path) -> None:
        """Set the frame rate toggle and value together."""
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")

        rqi.settings["Frame Rate"] = FrameRateSetting.USE_THIS_FRAME_RATE
        rqi.settings["Use this frame rate"] = 23.976

        out = tmp_path / "batch_fr.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Frame Rate"] == FrameRateSetting.USE_THIS_FRAME_RATE
        assert rqi2.settings["Use this frame rate"] == pytest.approx(23.976, abs=0.01)


class TestRoundtripSettingsBulkAssign:
    """Roundtrip tests for bulk settings assignment via .settings setter."""

    def test_assign_settings_dict(self, tmp_path: Path) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.settings = {
            "Quality": RenderQuality.WIREFRAME,
            "Resolution": [4, 4],
            "Skip Existing Files": True,
        }

        out = tmp_path / "bulk_assign.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Quality"] == RenderQuality.WIREFRAME
        assert rqi2.settings["Resolution"] == [4, 4]
        assert rqi2.settings["Skip Existing Files"] is True

    def test_assign_from_another_rqi(self, tmp_path: Path) -> None:
        """Copy settings from one RQI to another via .settings setter."""
        project = parse_aep(SAMPLES_DIR / "2_rqitems.aep").project
        items = project.render_queue.items
        assert len(items) == 2

        items[0].settings["Quality"] = RenderQuality.DRAFT
        items[0].settings["Resolution"] = [2, 2]
        copied_settings = dict(items[0].settings)
        assert "Use comp's frame rate" in copied_settings
        copied_settings.pop("Use comp's frame rate")
        items[1].settings = copied_settings

        out = tmp_path / "copy_settings.aep"
        project.save(out)
        items2 = parse_aep(out).project.render_queue.items
        assert items2[1].settings["Quality"] == RenderQuality.DRAFT
        assert items2[1].settings["Resolution"] == [2, 2]

    def test_assign_settings_with_read_only_key_raises(self) -> None:
        """Bulk assignment should surface read-only setting errors."""
        project = parse_aep(SAMPLES_DIR / "2_rqitems.aep").project
        items = project.render_queue.items
        assert len(items) == 2

        with pytest.raises(AttributeError, match="read-only"):
            items[1].settings = items[0].settings


class TestRoundtripSettingsReadOnly:
    """Tests that read-only settings raise on dict-style write."""

    def test_time_span_start_writable(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        # Time Span Start is now writable - verify no error
        rqi.settings["Time Span Start"] = 1.0

    def test_time_span_duration_writable(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        # Time Span Duration is now writable - verify no error
        rqi.settings["Time Span Duration"] = 5.0

    def test_comps_frame_rate_read_only(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(AttributeError, match="read-only"):
            rqi.settings["Use comp's frame rate"] = 30.0

    def test_unknown_key_via_dict_raises(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        with pytest.raises(KeyError):
            rqi.settings["Nonexistent"]
        with pytest.raises(KeyError, match="Unknown setting"):
            rqi.settings["Nonexistent"] = 42


class TestRoundtripOutputModuleResize:
    """Roundtrip tests for OutputModule Resize to (2-field getter/setter)."""

    def test_set_resize_to(self, tmp_path: Path) -> None:
        project = parse_aep(OM_SAMPLES_DIR / "resize_custom_960x540.aep").project
        om = project.render_queue.items[0].output_modules[0]
        assert om.settings["Resize to"] == [960, 540]

        om.settings["Resize to"] = [1280, 720]
        out = tmp_path / "resize_720p.aep"
        project.save(out)
        om2 = parse_aep(out).project.render_queue.items[0].output_modules[0]
        assert om2.settings["Resize to"] == [1280, 720]

    def test_resize_roundtrip_back(self, tmp_path: Path) -> None:
        project = parse_aep(OM_SAMPLES_DIR / "resize_custom_960x540.aep").project
        om = project.render_queue.items[0].output_modules[0]
        om.settings["Resize to"] = [3840, 2160]

        out = tmp_path / "resize_4k.aep"
        project.save(out)
        om2 = parse_aep(out).project.render_queue.items[0].output_modules[0]
        assert om2.settings["Resize to"] == [3840, 2160]

        om2.settings["Resize to"] = [640, 480]
        out2 = tmp_path / "resize_vga.aep"
        om2._project.save(out2)
        om3 = parse_aep(out2).project.render_queue.items[0].output_modules[0]
        assert om3.settings["Resize to"] == [640, 480]


class TestRoundtripOutputModuleCrop:
    """Roundtrip tests for OutputModule crop settings."""

    def test_set_all_crop_values(self, tmp_path: Path) -> None:
        project = parse_aep(OM_SAMPLES_DIR / "om_crop.aep").project
        rqi = get_rqi(project, "crop_checked")
        om = rqi.output_modules[0]

        om.settings["Crop Top"] = 20
        om.settings["Crop Left"] = 30
        om.settings["Crop Bottom"] = 40
        om.settings["Crop Right"] = 50

        out = tmp_path / "crop_all.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "crop_checked")
        om2 = rqi2.output_modules[0]
        assert om2.settings["Crop Top"] == 20
        assert om2.settings["Crop Left"] == 30
        assert om2.settings["Crop Bottom"] == 40
        assert om2.settings["Crop Right"] == 50

    def test_toggle_crop_and_set_values(self, tmp_path: Path) -> None:
        project = parse_aep(OM_SAMPLES_DIR / "crop_unchecked.aep").project
        om = project.render_queue.items[0].output_modules[0]
        assert om.settings["Crop"] is False

        om.settings["Crop"] = True
        om.settings["Crop Top"] = 10
        om.settings["Crop Bottom"] = 10

        out = tmp_path / "crop_enabled.aep"
        project.save(out)
        om2 = parse_aep(out).project.render_queue.items[0].output_modules[0]
        assert om2.settings["Crop"] is True
        assert om2.settings["Crop Top"] == 10
        assert om2.settings["Crop Bottom"] == 10


class TestRoundtripOutputModuleSettings:
    """Roundtrip tests for various OutputModule settings via dict access."""

    def test_set_resize_quality(self, tmp_path: Path) -> None:
        project = parse_aep(OM_SAMPLES_DIR / "om_resize.aep").project
        rqi = get_rqi(project, "resize_quality_low")
        om = rqi.output_modules[0]
        assert om.settings["Resize Quality"] == ResizeQuality.LOW

        om.settings["Resize Quality"] = ResizeQuality.HIGH
        out = tmp_path / "rq_high.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "resize_quality_low")
        om2 = rqi2.output_modules[0]
        assert om2.settings["Resize Quality"] == ResizeQuality.HIGH

    def test_read_only_om_settings(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        om = rqi.output_modules[0]
        with pytest.raises(AttributeError, match="read-only"):
            om.settings["Output File Info"] = {}
        with pytest.raises(AttributeError, match="read-only"):
            om.settings["Output Color Space"] = "sRGB"

    def test_om_settings_contain_required_keys(self) -> None:
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        om = rqi.output_modules[0]
        settings = om.settings
        assert "Channels" in settings
        assert "Depth" in settings
        assert "Crop" in settings
        assert "Resize" in settings
        assert "Format" in settings
        assert "Output File Info" in settings

    def test_time_span_via_settings(self, tmp_path: Path) -> None:
        """Time Span key in RQI settings roundtrips correctly."""
        project = parse_aep(SAMPLES_DIR / "render_settings.aep").project
        rqi = get_rqi(project, "base")
        rqi.settings["Time Span"] = TimeSpanSource.WORK_AREA_ONLY

        out = tmp_path / "ts_work_area.aep"
        project.save(out)
        rqi2 = get_rqi(parse_aep(out).project, "base")
        assert rqi2.settings["Time Span"] == TimeSpanSource.WORK_AREA_ONLY


class TestRoutChunkIntegrity:
    """Regression tests: the Rout chunk stays consistent across mutations.

    These guard the 5-items-per-RQ-item invariant; len(items)-only checks
    miss a corrupt Rout chunk because the item count comes from the render
    settings ldat, not from Rout.
    """

    def test_parse_associates_per_item_block(self) -> None:
        # Each RQ item owns its own contiguous, non-shared Rout block.
        app = parse_aep(SAMPLES_DIR / "2_rqitems.aep")
        rq = app.project.render_queue
        _assert_rout_consistent(app)
        block0 = rq.items[0]._rout_items
        block1 = rq.items[1]._rout_items
        assert len(block0) == ROUT_ITEMS_PER_RQ_ITEM
        assert len(block1) == ROUT_ITEMS_PER_RQ_ITEM
        assert not any(a is b for a in block0 for b in block1)

    def test_remove_keeps_rout_consistent(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "2_rqitems.aep")
        app.project.render_queue.items[0].remove()
        _assert_rout_consistent(app)
        out = tmp_path / "out.aep"
        app.project.save(out)
        _assert_rout_consistent(parse_aep(out))

    def test_duplicate_keeps_rout_consistent(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "base.aep")
        app.project.render_queue.items[0].duplicate()
        _assert_rout_consistent(app)
        out = tmp_path / "out.aep"
        app.project.save(out)
        _assert_rout_consistent(parse_aep(out))


class TestRQItemRemove:
    """Tests for RenderQueueItem.remove()."""

    def test_remove_first_item(self, tmp_path: Path) -> None:
        """Removing the first RQ item leaves one item, roundtrips."""
        app = parse_aep(SAMPLES_DIR / "2_rqitems.aep")
        rq = app.project.render_queue
        assert len(rq.items) == 2
        _comp0 = rq.items[0].comp
        comp1 = rq.items[1].comp

        rq.items[0].remove()
        assert len(rq.items) == 1
        assert rq.items[0].comp is comp1

        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        assert len(app2.project.render_queue.items) == 1

    def test_remove_second_item(self, tmp_path: Path) -> None:
        """Removing the second RQ item leaves one item, roundtrips."""
        app = parse_aep(SAMPLES_DIR / "2_rqitems.aep")
        rq = app.project.render_queue
        comp0 = rq.items[0].comp

        rq.items[1].remove()
        assert len(rq.items) == 1
        assert rq.items[0].comp is comp0

        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        assert len(app2.project.render_queue.items) == 1

    def test_remove_all_items(self, tmp_path: Path) -> None:
        """Removing all items empties the render queue, roundtrips."""
        app = parse_aep(SAMPLES_DIR / "2_rqitems.aep")
        rq = app.project.render_queue
        assert rq._arsi.queue_nonempty == 1

        rq.items[1].remove()
        rq.items[0].remove()
        assert len(rq.items) == 0
        # Emptying the queue clears the ARsi non-empty marker AE set.
        assert rq._arsi.queue_nonempty == 0

        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        rq2 = app2.project.render_queue
        assert len(rq2.items) == 0
        assert rq2._arsi.queue_nonempty == 0

    def test_remove_item_with_comment(self, tmp_path: Path) -> None:
        """Removing an item with a comment works correctly."""
        app = parse_aep(SAMPLES_DIR / "comment_aaaaa.aep")
        rq = app.project.render_queue
        assert len(rq.items) == 1
        assert rq.items[0].comment == "aaaaa"

        rq.items[0].remove()
        assert len(rq.items) == 0

        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        assert len(app2.project.render_queue.items) == 0


class TestRQItemDuplicate:
    """Tests for RenderQueueItem.duplicate()."""

    def test_duplicate_basic(self, tmp_path: Path) -> None:
        """Duplicating an item increases count by one, roundtrips."""
        app = parse_aep(SAMPLES_DIR / "base.aep")
        rq = app.project.render_queue
        orig_count = len(rq.items)
        orig_comp = rq.items[0].comp

        new_item = rq.items[0].duplicate()
        assert len(rq.items) == orig_count + 1
        assert new_item.comp is orig_comp
        assert new_item is rq.items[1]

        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        assert len(app2.project.render_queue.items) == orig_count + 1

    def test_duplicate_preserves_output_modules(self, tmp_path: Path) -> None:
        """Duplicated item has the same number of output modules."""
        app = parse_aep(SAMPLES_DIR / "base.aep")
        rq = app.project.render_queue
        orig_om_count = len(rq.items[0].output_modules)

        new_item = rq.items[0].duplicate()
        assert len(new_item.output_modules) == orig_om_count

        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        assert len(app2.project.render_queue.items[1].output_modules) == orig_om_count

    def test_duplicate_from_two_items(self, tmp_path: Path) -> None:
        """Duplicating from a file with 2 items produces 3 items, roundtrips."""
        app = parse_aep(SAMPLES_DIR / "2_rqitems.aep")
        rq = app.project.render_queue
        assert len(rq.items) == 2

        rq.items[0].duplicate()
        assert len(rq.items) == 3

        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        assert len(app2.project.render_queue.items) == 3

    def test_duplicate_then_remove(self, tmp_path: Path) -> None:
        """Duplicate then remove the original leaves the duplicate."""
        app = parse_aep(SAMPLES_DIR / "base.aep")
        rq = app.project.render_queue

        new_item = rq.items[0].duplicate()
        rq.items[0].remove()
        assert len(rq.items) == 1
        assert rq.items[0] is new_item

        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        assert len(app2.project.render_queue.items) == 1


@pytest.mark.skipif(not AE_PREFS_DIR, reason="AE_PREFS_DIR env var not set")
class TestRQAdd:
    """Tests for RenderQueue.add()."""

    def test_add_to_existing(self, tmp_path: Path) -> None:
        """Adding a comp to RQ with existing items increases count."""
        app = parse_aep(SAMPLES_DIR / "base.aep", ae_preferences_dir=AE_PREFS_DIR)
        rq = app.project.render_queue
        comp = rq.items[0].comp
        orig_count = len(rq.items)

        new_item = rq.add(comp)
        assert len(rq.items) == orig_count + 1
        assert new_item.comp is comp
        assert len(new_item.output_modules) == 1

        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        assert len(app2.project.render_queue.items) == orig_count + 1

    def test_add_returns_rqitem(self) -> None:
        """add() returns a RenderQueueItem."""
        app = parse_aep(SAMPLES_DIR / "base.aep", ae_preferences_dir=AE_PREFS_DIR)
        rq = app.project.render_queue
        comp = rq.items[0].comp
        new_item = rq.add(comp)
        assert isinstance(new_item, RenderQueueItem)

    def test_add_after_remove_all(self, tmp_path: Path) -> None:
        """Adding to an emptied queue works and roundtrips."""
        app = parse_aep(SAMPLES_DIR / "base.aep", ae_preferences_dir=AE_PREFS_DIR)
        rq = app.project.render_queue
        comp = rq.items[0].comp

        rq.items[0].remove()
        assert len(rq.items) == 0

        rq.add(comp)
        assert len(rq.items) == 1

        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        assert len(app2.project.render_queue.items) == 1


class TestRQAddWithoutPreferences:
    """RenderQueue.add() builds a valid TIFF image-sequence item with no prefs.

    These run in CI (no AE_PREFS_DIR needed): add() no longer raises or warns
    without ae_preferences_dir - it builds a fresh "TIFF Sequence with Alpha"
    output module whose chunks match what After Effects writes for a freshly
    added item.
    """

    def test_add_without_prefs_builds_tiff_item(self) -> None:
        app = parse_aep(SAMPLES_DIR / "custom.aep")  # no ae_preferences_dir
        rq = app.project.render_queue
        comp = app.project.compositions[0]
        orig = rq.num_items

        rqi = rq.add(comp)

        assert rq.num_items == orig + 1
        assert rqi.name == "Best Settings"
        # Fresh item has no output file set yet -> NEEDS_OUTPUT, like AE.
        assert rqi.status == RQItemStatus.NEEDS_OUTPUT
        assert rqi.num_output_modules == 1
        assert rqi.output_modules[0].name == "TIFF Sequence with Alpha"

    def test_fresh_om_structure_matches_ae(self) -> None:
        # AE's freshly added OM has no Als2 alias; its LOm is Roou, Ropt,
        # hdrm, Utf8x3. The Ropt is the 602-byte TIFF format options.
        import io

        from py_aep.binary.render_chunks import TiffRoptChunk

        app = parse_aep(SAMPLES_DIR / "custom.aep")
        rqi = app.project.render_queue.add(app.project.compositions[0])
        lom_types = [
            getattr(c, "list_type", None) or c.chunk_type for c in rqi._lom.chunks
        ]
        assert "Als2" not in lom_types
        assert lom_types == ["Roou", "Ropt", "hdrm", "Utf8", "Utf8", "Utf8"]
        ropt = next(c for c in rqi._lom.chunks if c.chunk_type == "Ropt")
        assert isinstance(ropt, TiffRoptChunk)
        buf = io.BytesIO()
        ropt.write(buf)
        assert len(buf.getvalue()) == 602

    def test_add_without_prefs_roundtrips(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "custom.aep")
        rq = app.project.render_queue
        comp = app.project.compositions[0]
        orig = rq.num_items

        rq.add(comp)

        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        rq2 = app2.project.render_queue
        assert rq2.num_items == orig + 1
        assert rq2.items[-1].output_modules[0].name == "TIFF Sequence with Alpha"

    def test_add_to_empty_queue_roundtrips(self, tmp_path: Path) -> None:
        # A project whose render queue starts empty: the settings 'list' has
        # only an lhd3 and a synthetic (unwritten) ldat. add() materializes
        # the ldat so the new settings get written.
        app = parse_aep(SAMPLES_DIR / "empty.aep")
        rq = app.project.render_queue
        assert rq.num_items == 0
        comp = app.project.compositions[0]

        rq.add(comp)
        assert rq.num_items == 1

        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        rq2 = app2.project.render_queue
        assert rq2.num_items == 1
        assert rq2.items[0].output_modules[0].name == "TIFF Sequence with Alpha"

    def test_empty_queue_unchanged_roundtrip_is_byte_identical(
        self, tmp_path: Path
    ) -> None:
        # The synthetic ldat attached by the parser must be skipped on write,
        # so parsing then saving an untouched empty queue is byte-identical.
        src = SAMPLES_DIR / "empty.aep"
        app = parse_aep(src)
        assert app.project.render_queue.num_items == 0

        out = tmp_path / "roundtrip.aep"
        app.project.save(out)
        assert out.read_bytes() == src.read_bytes()

    def test_add_to_empty_queue_reparse_links_comp(self, tmp_path: Path) -> None:
        # Regression: adding to a queue-less project, saving, then reparsing
        # must yield exactly one item linked to the original comp. (See
        # project memory "renderqueue-add-known-bug".)
        app = parse_aep(SAMPLES_DIR / "empty.aep")
        rq = app.project.render_queue
        assert rq.num_items == 0
        comp = app.project.compositions[0]

        rq.add(comp)

        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        rq2 = app2.project.render_queue
        assert rq2.num_items == 1
        assert rq2.items[0].comp.name == comp.name
        assert rq2.items[0].comp.id == comp.id

    def test_image_sequence_chunk_defaults(self) -> None:
        # Field defaults reproduce AE's fresh "TIFF Sequence with Alpha" item
        # (values captured from After Effects 26). The reserved-region values
        # are the bytes AE writes; without them AE reports "missing data".
        from py_aep.binary.render_chunks import (
            RouuChunk,
        )

        rouu = RouuChunk()
        assert rouu.format_id == "TIF "
        assert rouu.depth == 32
        assert rouu.audio_disabled_hi == 255
        assert rouu.audio_channels == 0
        # The full image-sequence body is 154 bytes (114 typed + 40 trailing).
        assert len(rouu.tobytes()) == 154

        rs = RenderSettingsItem()
        assert rs._reserved_00 == b"\x00\x01\x00\x00\x00\x00\x00"
        assert rs._reserved_06 == b"\x00\x03\x00\x00"
        assert rs._reserved_39 == b"\xff\xff\xff\xff\x00\xb4" + b"\x00" * 8
        assert rs._reserved_45 == b"\x00\x00\x00\x02\xff\xff"
        assert rs._remaining == b"\x00" * 19 + b"\x02\x00\x00\x00\x0f" + b"\x00" * 16

        om = OutputModuleSettingsItem()
        assert om.convert_to_linear_light == 2
        assert om.output_color_space_working == 1
        assert om.channels == 1

    def test_tiff_ropt_default_is_602_bytes(self) -> None:
        # A default TiffRoptChunk reproduces AE's exact 602-byte TIFF Ropt
        # (the markers, incl. 0x025A = 602, are split across _pad + chunk_size).
        import io

        from py_aep.binary.render_chunks import TiffRoptChunk

        buf = io.BytesIO()
        TiffRoptChunk().write(buf)
        data = buf.getvalue()
        assert len(data) == 602
        assert data[:4] == b"TIF "
        assert TiffRoptChunk().chunk_size == 602

    def test_ropt_variant_defaults_are_valid_chunks(self) -> None:
        # Each variant's field defaults reproduce AE's real Ropt for that
        # format: correct full length, format code, and a construct -> parse
        # round-trip back to the same variant and bytes.
        from py_aep.binary.render_chunks import (
            CineonRoptChunk,
            JpegRoptChunk,
            OpenExrRoptChunk,
            PngRoptChunk,
            RoptChunk,
            TargaRoptChunk,
        )

        cases = [
            (CineonRoptChunk, b"sDPX", 48),
            (JpegRoptChunk, b"JPEG", 58),
            (OpenExrRoptChunk, b"oEXR", 78),
            (PngRoptChunk, b"png!", 322),
            (TargaRoptChunk, b"TPIC", 84),
        ]
        for cls, code, size in cases:
            data = cls().tobytes()
            assert len(data) == size, code
            assert data[:4] == code
            # RoptChunk dispatch re-parses the bytes to the same variant + bytes
            parsed = RoptChunk.frombytes(data, chunk_type="Ropt")
            assert isinstance(parsed, cls), code
            assert parsed.tobytes() == data, code

    def test_arsi_chunk_named_fields(self) -> None:
        # The ARsi state chunk parses to a typed ArsiChunk (fixed 1872 bytes)
        # whose queue_nonempty flag (offset 3) tracks whether the queue has
        # items.
        from py_aep.binary.render_chunks import ArsiChunk
        from py_aep.binary.utils import recursive_find

        app = parse_aep(SAMPLES_DIR / "field_render.aep")
        rq = app.project.render_queue
        arsi = recursive_find(rq._lrdr.chunks, chunk_type="ARsi")[0]
        assert isinstance(arsi, ArsiChunk)
        assert len(arsi.tobytes()) == 1872
        assert arsi.queue_nonempty == (1 if rq.num_items else 0)

    def test_parse_id_hex_section_is_bounded(self) -> None:
        # The section parser must decode AE's hex/ASCII encoding and never
        # leak continuation lines across section boundaries.
        from py_aep.parsers.templates import _parse_id_hex_section

        text = (
            '["Output File Info Preference Section v28"]\n'
            '\t"Output File Info ID # 0" = "AB"00"CD"\\\n'
            '\t\t01"EF"\n'
            '["Output File Options Preference Section v28"]\n'
            '\t"Output File Options ID # 0" = "XY"FF\n'
        )
        info = _parse_id_hex_section(
            text, "Output File Info Preference Section", "Output File Info"
        )
        opts = _parse_id_hex_section(
            text, "Output File Options Preference Section", "Output File Options"
        )
        # Info entry stops at the section boundary (no Options bytes leak in).
        assert info[0] == b"AB\x00CD\x01EF"
        assert opts[0] == b"XY\xff"


class TestOMRemove:
    """Tests for OutputModule.remove()."""

    def test_remove_last_om_raises(self) -> None:
        """Cannot remove the only output module."""
        app = parse_aep(SAMPLES_DIR / "base.aep")
        rq = app.project.render_queue
        rqi = rq.items[0]
        assert len(rqi.output_modules) == 1

        with pytest.raises(RuntimeError):
            rqi.output_modules[0].remove()


@pytest.mark.skipif(not AE_PREFS_DIR, reason="AE_PREFS_DIR env var not set")
class TestRenderQueueAdd:
    """Tests for RenderQueue.add()."""

    def test_add_returns_rq_item(self) -> None:
        """RenderQueue.add() returns a RenderQueueItem."""
        app = parse_aep(SAMPLES_DIR / "custom.aep", ae_preferences_dir=AE_PREFS_DIR)
        rq = app.project.render_queue
        comp = app.project.compositions[0]
        rqi = rq.add(comp)
        assert isinstance(rqi, RenderQueueItem)

    def test_add_increments_num_items(self) -> None:
        """Adding a comp increases num_items by 1."""
        app = parse_aep(SAMPLES_DIR / "custom.aep", ae_preferences_dir=AE_PREFS_DIR)
        rq = app.project.render_queue
        comp = app.project.compositions[0]
        n = rq.num_items
        rq.add(comp)
        assert rq.num_items == n + 1

    def test_add_sets_comp_reference(self) -> None:
        """The new RQ item references the correct comp."""
        app = parse_aep(SAMPLES_DIR / "custom.aep", ae_preferences_dir=AE_PREFS_DIR)
        rq = app.project.render_queue
        comp = app.project.compositions[0]
        rqi = rq.add(comp)
        assert rqi.comp is comp

    def test_add_default_status_needs_output(self) -> None:
        """New item has NEEDS_OUTPUT status (no output file path set yet)."""
        app = parse_aep(SAMPLES_DIR / "custom.aep", ae_preferences_dir=AE_PREFS_DIR)
        rq = app.project.render_queue
        comp = app.project.compositions[0]
        rqi = rq.add(comp)
        assert rqi.status == RQItemStatus.NEEDS_OUTPUT

    def test_add_default_time_span(self) -> None:
        """New item has WORK_AREA_ONLY time span source (matches AE add())."""
        app = parse_aep(SAMPLES_DIR / "custom.aep", ae_preferences_dir=AE_PREFS_DIR)
        rq = app.project.render_queue
        comp = app.project.compositions[0]
        rqi = rq.add(comp)
        assert rqi._ldat.time_span_source == int(TimeSpanSource.WORK_AREA_ONLY)

    def test_add_has_one_output_module(self) -> None:
        """New item has exactly 1 output module."""
        app = parse_aep(SAMPLES_DIR / "custom.aep", ae_preferences_dir=AE_PREFS_DIR)
        rq = app.project.render_queue
        comp = app.project.compositions[0]
        rqi = rq.add(comp)
        assert len(rqi.output_modules) == 1

    def test_add_to_empty_queue(self) -> None:
        """Adding to an empty render queue works."""
        app = parse_aep(SAMPLES_DIR / "empty.aep", ae_preferences_dir=AE_PREFS_DIR)
        rq = app.project.render_queue
        assert rq.num_items == 0
        comp = app.project.compositions[0]
        rqi = rq.add(comp)
        assert rq.num_items == 1
        assert rqi.comp is comp

    def test_add_to_existing_queue(self) -> None:
        """Adding to a queue that already has items works."""
        app = parse_aep(SAMPLES_DIR / "custom.aep", ae_preferences_dir=AE_PREFS_DIR)
        rq = app.project.render_queue
        n = rq.num_items
        comp = app.project.compositions[0]
        rqi = rq.add(comp)
        assert rq.num_items == n + 1
        assert rq.items[-1] is rqi

    def test_add_roundtrip(self, tmp_path: Path) -> None:
        """Save + reparse preserves the new RQ item."""
        app = parse_aep(SAMPLES_DIR / "custom.aep", ae_preferences_dir=AE_PREFS_DIR)
        rq = app.project.render_queue
        comp = app.project.compositions[0]
        rq.add(comp)

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        rq2 = app2.project.render_queue
        assert rq2.num_items == 2
        assert rq2.items[-1].comp.name == comp.name

    def test_add_then_remove(self) -> None:
        """Add then remove leaves RQ in original state."""
        app = parse_aep(SAMPLES_DIR / "custom.aep", ae_preferences_dir=AE_PREFS_DIR)
        rq = app.project.render_queue
        original_count = rq.num_items
        comp = app.project.compositions[0]
        rqi = rq.add(comp)
        assert rq.num_items == original_count + 1
        rqi.remove()
        assert rq.num_items == original_count


class TestOMRemoveIdenticalModules:
    """Removing one of two byte-identical output modules hits the right block."""

    def test_remove_second_of_identical_modules(self, tmp_path: Path) -> None:
        # numOutputModules_2 has two structurally-equal H.264 modules; with a
        # value-based lookup remove() would delete the first module's chunks.
        app = parse_aep(OM_SAMPLES_DIR / "numOutputModules_2.aep")
        rqi = app.project.render_queue.items[0]
        om0, om1 = rqi.output_modules
        # Distinguish the two modules by a per-module Roou value.
        om0._roou.starting_number = 7
        om1._roou.starting_number = 99

        om1.remove()
        assert len(rqi.output_modules) == 1
        # The surviving module is module 0, with its chunks intact.
        assert rqi.output_modules[0] is om0
        assert rqi.output_modules[0]._roou.starting_number == 7

        out = tmp_path / "out.aep"
        app.project.save(out)
        rqi2 = parse_aep(out).project.render_queue.items[0]
        assert len(rqi2.output_modules) == 1
        assert rqi2.output_modules[0]._roou.starting_number == 7


@pytest.mark.skipif(not AE_PREFS_DIR, reason="AE_PREFS_DIR env var not set")
class TestOMApplyTemplate:
    """apply_template targets only the module it is called on."""

    def test_apply_template_leaves_sibling_untouched(self) -> None:
        # Applying a template to module 1 must not rewrite module 0's Ropt
        # (the shared LOm list holds both modules' chunks back to back).
        app = parse_aep(
            OM_SAMPLES_DIR / "numOutputModules_2.aep",
            ae_preferences_dir=AE_PREFS_DIR,
        )
        rqi = app.project.render_queue.items[0]
        om0, om1 = rqi.output_modules
        om0_ropt_before = om0.format_options._body.tobytes()
        om0_format_before = om0._roou.format_id

        om1.apply_template("TIFF Sequence with Alpha")

        # Module 1 switched to TIFF; module 0 still H.264 with the same Ropt.
        assert om1._roou.format_id == "TIF "
        assert om0._roou.format_id == om0_format_before
        assert om0.format_options._body.tobytes() == om0_ropt_before

    def test_apply_template_refreshes_format_options(self, tmp_path: Path) -> None:
        # After apply_template the format_options must wrap the NEW Ropt, so
        # an edit through it serializes (the old chunk was detached/unwritten).
        app = parse_aep(
            OM_SAMPLES_DIR / "numOutputModules_2.aep",
            ae_preferences_dir=AE_PREFS_DIR,
        )
        rqi = app.project.render_queue.items[0]
        om1 = rqi.output_modules[1]
        om1.apply_template("TIFF Sequence with Alpha")

        fo = om1.format_options
        assert type(fo).__name__ == "TiffFormatOptions"
        new_value = not fo.lzw_compression
        fo.lzw_compression = new_value

        out = tmp_path / "out.aep"
        app.project.save(out)
        rqi2 = parse_aep(
            out, ae_preferences_dir=AE_PREFS_DIR
        ).project.render_queue.items[0]
        assert rqi2.output_modules[1].format_options.lzw_compression == new_value


class TestRQItemDuplicateStatus:
    """duplicate() resets a finished item's status to QUEUED."""

    @pytest.mark.parametrize(
        "done_status", [RQItemStatus.DONE, RQItemStatus.ERR_STOPPED]
    )
    def test_duplicate_resets_finished_status(self, done_status: RQItemStatus) -> None:
        app = parse_aep(SAMPLES_DIR / "base.aep")
        rqi = app.project.render_queue.items[0]
        # status stores the raw binary value, so set it via to_binary().
        rqi._ldat.status = done_status.to_binary()

        dup = rqi.duplicate()

        assert RQItemStatus.from_binary(dup._ldat.status) == RQItemStatus.QUEUED


class TestCompRemoveWithRenderQueue:
    """Removing a comp also removes its render-queue items (chunks and all)."""

    def test_remove_comp_clears_its_rq_item(self, tmp_path: Path) -> None:
        # numItems_2 renders two distinct comps; the active item is neither,
        # so removing one rendered comp leaves a parseable project.
        app = parse_aep(SAMPLES_DIR / "numItems_2.aep")
        rq = app.project.render_queue
        assert len(rq.items) == 2
        comp0 = rq.items[0].comp
        comp1 = rq.items[1].comp
        assert comp0 is not comp1

        comp0.remove()

        assert len(rq.items) == 1
        assert rq.items[0].comp is comp1
        # Chunk-level bookkeeping stays in sync (no orphaned settings entry).
        assert rq._rs_lhd3.count == 1
        assert rq._rout.count == ROUT_ITEMS_PER_RQ_ITEM

        out = tmp_path / "out.aep"
        app.project.save(out)
        rq2 = parse_aep(out).project.render_queue
        assert len(rq2.items) == 1
        assert rq2._rs_lhd3.count == 1

    def test_remove_comp_keeps_remaining_item_removable(self, tmp_path: Path) -> None:
        # After comp.remove(), the rs_ldat index bookkeeping must still line up
        # so a later rqi.remove() deletes the correct settings entry.
        app = parse_aep(SAMPLES_DIR / "numItems_2.aep")
        app.project.render_queue.items[0].comp.remove()

        out = tmp_path / "out.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        rq2 = app2.project.render_queue
        assert len(rq2.items) == 1

        rq2.items[0].remove()
        assert len(rq2.items) == 0
        assert rq2._rs_lhd3.count == 0
        assert rq2._rout.count == 0


class TestRenderQueueMissingScaffolding:
    """An LRdr lacking Rout/LItm/LSIf still parses as an empty queue.

    Regression: parse_render_queue required those chunks unconditionally,
    so a legacy/minimal file failed the entire parse() with
    ChunkNotFoundError instead of yielding an empty RenderQueue.
    """

    @staticmethod
    def _strip_scaffolding(tmp_path: Path) -> Path:
        src = SAMPLES_DIR / "empty.aep"
        with src.open("rb") as f:
            rifx, xmp = read_aep(f)
        lrdr = find_by_list_type(chunks=rifx.chunks, list_type="LRdr")
        lrdr.chunks = [
            c
            for c in lrdr.chunks
            if c.chunk_type != "Rout"
            and not (isinstance(c, ListChunk) and c.list_type in ("LItm", "LSIf"))
        ]
        out = tmp_path / "stripped.aep"
        with out.open("wb") as f:
            write_aep(f, rifx, xmp)
        return out

    def test_parse_yields_empty_queue(self, tmp_path: Path) -> None:
        stripped = self._strip_scaffolding(tmp_path)
        app = parse_aep(stripped)
        rq = app.project.render_queue
        assert rq.num_items == 0
        assert list(rq) == []

    def test_untouched_roundtrip_is_byte_identical(self, tmp_path: Path) -> None:
        # The synthetic placeholder chunks must be skipped on write.
        stripped = self._strip_scaffolding(tmp_path)
        app = parse_aep(stripped)
        out = tmp_path / "roundtrip.aep"
        app.project.save(out)
        assert out.read_bytes() == stripped.read_bytes()


class TestRenderQueueNoLRdr:
    """A project with NO top-level LRdr chunk parses as an empty queue, and
    add() then attaches a writable queue that survives a reparse.

    Regression: parse_render_queue required a top-level LRdr unconditionally
    (so a legacy/hand-built file lacking it failed parse() entirely), and a
    freshly-added queue was never attached to the root so it was lost on save.
    """

    @staticmethod
    def _strip_lrdr(tmp_path: Path) -> Path:
        src = SAMPLES_DIR / "empty.aep"
        with src.open("rb") as f:
            rifx, xmp = read_aep(f)
        rifx.chunks = [
            c
            for c in rifx.chunks
            if not (isinstance(c, ListChunk) and c.list_type == "LRdr")
        ]
        out = tmp_path / "no_lrdr.aep"
        with out.open("wb") as f:
            write_aep(f, rifx, xmp)
        return out

    def test_parse_yields_empty_queue(self, tmp_path: Path) -> None:
        app = parse_aep(self._strip_lrdr(tmp_path))
        rq = app.project.render_queue
        assert rq.num_items == 0
        assert list(rq) == []

    def test_untouched_roundtrip_is_byte_identical(self, tmp_path: Path) -> None:
        # The synthesized LRdr is synthetic, so write_aep skips it entirely.
        stripped = self._strip_lrdr(tmp_path)
        app = parse_aep(stripped)
        out = tmp_path / "roundtrip.aep"
        app.project.save(out)
        assert out.read_bytes() == stripped.read_bytes()

    def test_add_reparse_links_comp(self, tmp_path: Path) -> None:
        stripped = self._strip_lrdr(tmp_path)
        app = parse_aep(stripped)
        rq = app.project.render_queue
        comp = app.project.compositions[0]
        rq.add(comp)
        assert rq.num_items == 1

        out = tmp_path / "added.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        rq2 = app2.project.render_queue
        assert rq2.num_items == 1
        assert rq2.items[0].comp.id == comp.id


class TestRoundtripOutputColorSpace:
    """Roundtrip tests for OutputModule.output_color_space."""

    SAMPLE = Path(__file__).parent.parent.parent / (
        "samples/models/renderqueue/render_settings.aep"
    )

    def test_set_adobe_profile(self, tmp_path: Path) -> None:
        project = parse_aep(self.SAMPLE).project
        om = project.render_queue.items[0].output_modules[0]
        name = "ARRI LogC3 Wide Color Gamut - EI 800"
        om.output_color_space = name

        out = tmp_path / "modified.aep"
        project.save(out)
        om2 = parse_aep(out).project.render_queue.items[0].output_modules[0]
        assert om2.output_color_space == name
        # output_profile_id is the catalogued ID (matches AE ground truth).
        assert om2._om_ldat.output_profile_id == profile_id_for_name(name)
        assert om2._om_ldat.output_color_space_working == 0

    def test_set_working_color_space(self, tmp_path: Path) -> None:
        project = parse_aep(self.SAMPLE).project
        om = project.render_queue.items[0].output_modules[0]
        om.output_color_space = "ARRI LogC3 Wide Color Gamut - EI 800"
        assert om._om_ldat.output_color_space_working == 0
        om.output_color_space = "Working Color Space"

        out = tmp_path / "modified.aep"
        project.save(out)
        project2 = parse_aep(out).project
        om2 = project2.render_queue.items[0].output_modules[0]
        assert om2._om_ldat.output_color_space_working == 1
        # "Working Color Space" resolves to the project's working space name.
        assert om2.output_color_space == project2.working_space

    def test_ocio_or_unknown_name_not_supported(self) -> None:
        project = parse_aep(self.SAMPLE).project
        om = project.render_queue.items[0].output_modules[0]
        with pytest.raises(NotImplementedError):
            om.output_color_space = "ACEScg"  # OCIO name, not a catalogued ICC
