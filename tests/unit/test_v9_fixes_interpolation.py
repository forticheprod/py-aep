"""Unit regression tests for the v9 fuzz findings on keyframes and bounds."""

from __future__ import annotations

import struct
from io import BytesIO

import pytest

from py_aep.binary.property_chunks import TdumChunk
from py_aep.models.properties.keyframe import _timebase_units


@pytest.mark.parametrize(
    ("fps", "units"),
    [
        # AE 2026's frame grid: the rate to the thousandth as p/q, q * 2**k
        # units a frame (12.3456 fps -> 24692 units a second, 2000 a frame).
        (12.3456, 24692.0),
        (3.3333, 26664.0),
        (29.97, 23976.0),
        (24.0, 24576.0),
    ],
)
def test_timebase_units_follow_frame_grid(fps: float, units: float) -> None:
    assert _timebase_units(fps) == units


class TestIntegerFlaggedBounds:
    """An integer-flagged tdum/tduM AE writes holds a double (all 47652 in
    the sample corpus are 8 bytes); read as a u4 its high word turned 100.0
    into 1079574528."""

    def test_eight_byte_body_is_a_double(self) -> None:
        raw = struct.pack(">d", 100.0)
        chunk = TdumChunk.read(BytesIO(raw), 8, chunk_type="tduM", is_integer=True)
        assert chunk.values == [100.0]
        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == raw
