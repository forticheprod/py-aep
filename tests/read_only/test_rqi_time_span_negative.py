"""Signed decode of render-queue time-span fields.

`samples/models/renderqueue/time_span_negative.aep` was produced by AE 2026
scripting (which accepts degenerate spans): item 0 has `timeSpanStart = -5`
(end kept at 10 -> duration 15), item 1 has start 110 with the end kept at
10 (duration -100). AE stores the negative values as two's-complement
dividends; decoding them as unsigned read -5s as ~139805s.
"""

from __future__ import annotations

from pathlib import Path

from helpers import parse_project

SAMPLE = (
    Path(__file__).parent.parent.parent
    / "samples"
    / "models"
    / "renderqueue"
    / "time_span_negative.aep"
)


class TestNegativeTimeSpanDecode:
    def test_negative_start_decodes_signed(self) -> None:
        project = parse_project(SAMPLE)
        rqi = project.render_queue.items[0]
        assert rqi.time_span_start == -5.0
        assert rqi.time_span_duration == 15.0

    def test_negative_duration_decodes_signed(self) -> None:
        project = parse_project(SAMPLE)
        rqi = project.render_queue.items[1]
        assert rqi.time_span_start == 110.0
        assert rqi.time_span_duration == -100.0
