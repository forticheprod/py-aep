"""Write-side validation of RenderQueueItem / OutputModule values.

Ground truth probed in AE 2026 scripting:
- `skipFrames` raises out of range 0..99.
- Resolution components raise outside 0..99; `[0, 0]` is legal ("Current
  Settings").
- `timeSpanStart` keeps the span END fixed (duration recomputed);
  `timeSpanDuration` keeps the start and enforces a one-frame minimum.
  AE accepts degenerate spans (negative start, end before start) and
  silently renders garbage, so py_aep validates those instead.
- Boolean settings/attributes are strict-bool in py_aep: AE's binary layer
  would silently coerce truthy values (`"no"` -> True).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import parse_project_fresh

SAMPLE = (
    Path(__file__).parent.parent.parent
    / "samples"
    / "models"
    / "output_module"
    / "file.aep"
)


def _rqi(project):  # noqa: ANN001, ANN202
    return project.render_queue.items[0]


class TestStrictBools:
    def test_rqi_bool_settings_reject_non_bool(self) -> None:
        rqi = _rqi(parse_project_fresh(SAMPLE))
        with pytest.raises(TypeError):
            rqi.settings["Skip Existing Files"] = "no"
        with pytest.raises(TypeError):
            rqi.render = 1
        rqi.settings["Skip Existing Files"] = True
        assert rqi.settings["Skip Existing Files"] is True

    def test_om_bool_settings_reject_non_bool(self) -> None:
        rqi = _rqi(parse_project_fresh(SAMPLE))
        om = rqi.output_modules[0]
        for key in (
            "Crop",
            "Resize",
            "Lock Aspect Ratio",
            "Include Project Link",
            "Preserve RGB",
            "Use Comp Frame Number",
            "Use Region of Interest",
            "Include Source XMP Metadata",
            "Video Output",
        ):
            with pytest.raises(TypeError):
                om.settings[key] = "no"
        om.settings["Preserve RGB"] = True
        assert om.settings["Preserve RGB"] is True


class TestSkipFramesBounds:
    def test_ae_range_0_to_99(self) -> None:
        rqi = _rqi(parse_project_fresh(SAMPLE))
        rqi.skip_frames = 0
        with pytest.raises(ValueError):
            rqi.skip_frames = 100
        with pytest.raises(ValueError):
            rqi.skip_frames = -1


class TestResolutionBounds:
    def test_zero_is_current_settings(self) -> None:
        rqi = _rqi(parse_project_fresh(SAMPLE))
        rqi.settings["Resolution"] = [0, 0]
        assert rqi.settings["Resolution"] == [0, 0]

    def test_components_0_to_99(self) -> None:
        rqi = _rqi(parse_project_fresh(SAMPLE))
        rqi.settings["Resolution"] = [99, 99]
        with pytest.raises(ValueError):
            rqi.settings["Resolution"] = [100, 100]
        with pytest.raises(ValueError):
            rqi.settings["Resolution"] = [-2, -2]


class TestTimeSpanSemantics:
    def test_start_keeps_end(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLE)
        rqi = _rqi(project)
        end = rqi.time_span_start + rqi.time_span_duration
        new_start = end / 2
        rqi.time_span_start = new_start
        assert rqi.time_span_start == pytest.approx(new_start)
        assert rqi.time_span_start + rqi.time_span_duration == pytest.approx(end)

        out = tmp_path / "span.aep"
        project.save(out)
        rqi2 = _rqi(parse_project_fresh(out))
        assert rqi2.time_span_start == pytest.approx(new_start)
        assert rqi2.time_span_start + rqi2.time_span_duration == pytest.approx(end)

    def test_duration_keeps_start(self) -> None:
        rqi = _rqi(parse_project_fresh(SAMPLE))
        rqi.time_span_start = 0.5
        start = rqi.time_span_start
        rqi.time_span_duration = 1.0
        assert rqi.time_span_start == pytest.approx(start)
        assert rqi.time_span_duration == pytest.approx(1.0)

    def test_degenerate_spans_rejected(self) -> None:
        rqi = _rqi(parse_project_fresh(SAMPLE))
        end = rqi.time_span_start + rqi.time_span_duration
        with pytest.raises(ValueError):
            rqi.time_span_start = -5
        with pytest.raises(ValueError):
            rqi.time_span_start = end + 1  # would leave a negative duration
        one_frame = 1.0 / rqi.comp.frame_rate
        with pytest.raises(ValueError):
            rqi.time_span_duration = one_frame / 2  # below AE's one-frame bound
        rqi.time_span_duration = one_frame  # exactly one frame is legal
