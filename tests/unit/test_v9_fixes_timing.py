"""Composition timebase, frame numbers and 16.16 rate fields (v9 fuzz fixes).

Expected values are After Effects 2026 measurements: the internal timebase
AE stored for compositions made with `addComp` at each rate, and the
`displayStartFrame` / `frameTime` AE reported for stored comp times.
"""

from __future__ import annotations

import struct
from fractions import Fraction

import pytest

from py_aep.binary.composition_chunks import CdtaChunk, frame_grid, layer_timebase
from py_aep.binary.footage_chunks import SspcChunk
from py_aep.binary.layer_chunks import LdtaChunk
from py_aep.binary.render_chunks import RenderSettingsItem, RouuChunk
from py_aep.models.items.composition import _frame_number

# rate -> (internal timebase, timebase units per frame), AE 2026 addComp.
_AE_TIMEBASES = {
    1: (32768, 32768),
    7.3: (37376, 5120),
    8.33: (26656, 3200),
    12.3456: (24692, 2000),
    19.5: (39936, 2048),
    23.976: (23976, 1000),
    23.98: (38368, 1600),
    24: (24576, 1024),
    29.97: (23976, 800),
    29.98: (23984, 800),
    37: (37888, 1024),
    39.0625: (39063, 1000),
    44.1: (28224, 640),
    59.94: (23976, 400),
    66.666: (33333, 500),
    77: (39424, 512),
    78.125: (20000, 256),
    99.123: (99123, 1000),
    99.99: (39996, 400),
    119.88: (23976, 200),
    120.5: (30848, 256),
    3.3333: (26664, 8000),
    998.5: (31952, 32),
    999: (31968, 32),
    # Past 115200 at k = 0: units per frame halved, timebase rounded down.
    112.501: (112501, 1000),
    115.199: (115199, 1000),
    115.201: (57600, 500),
    116.001: (58000, 500),
    118.001: (59000, 500),
    119.999: (59999, 500),
    120.001: (60000, 500),
    120.003: (60001, 500),
    120.005: (24001, 200),
    121.003: (60501, 500),
    250.003: (62500, 250),
    333.333: (83333, 250),
    500.001: (62500, 125),
    750.001: (93750, 125),
    998.999: (62437, 62),
}


class TestTimebaseRule:
    @pytest.mark.parametrize("rate", sorted(_AE_TIMEBASES))
    def test_timebase_matches_after_effects(self, rate: float) -> None:
        timebase, units_per_frame = _AE_TIMEBASES[rate]
        assert frame_grid(rate) == (timebase, units_per_frame)
        cdta = CdtaChunk()
        cdta.frame_rate = rate
        assert cdta.internal_timebase == timebase
        assert cdta.time_scale * 256 == units_per_frame


def _f32_ratio(value: float) -> tuple[int, int]:
    """The float32 time ratio AE stores for `displayStartTime = value`."""
    frac = Fraction(struct.unpack(">f", struct.pack(">f", value))[0])
    return frac.numerator, frac.denominator


def _cdta(rate: float) -> CdtaChunk:
    cdta = CdtaChunk()
    cdta.frame_rate = rate
    return cdta


class TestFrameNumber:
    """`displayStartFrame` / `frameTime` as AE 2026 reports them."""

    @pytest.mark.parametrize(
        ("rate", "frames"),
        [(29.97, 246), (29.97, 1221), (29.97, 107892), (59.94, 246), (29.97, -1244)],
    )
    def test_whole_frames_in_timebase_units(self, rate: float, frames: int) -> None:
        # The frames AE's displayStartFrame setter stores (units / timebase).
        timebase, units_per_frame = frame_grid(rate)
        assert _frame_number(_cdta(rate), frames * units_per_frame, timebase) == frames

    @pytest.mark.parametrize(
        ("rate", "seconds", "expected"),
        [
            (24, 1 / 24, 2),  # stored 0.0416666679: a hair past frame 1
            (24, 12.00001 / 24, 13),
            (24, 0.51, 13),
            (24, -0.51, -13),
            (24, 1531 / 24, 1532),
            (29.97, 52 / 29.97, 52),
            (29.97, 1221 / 29.97, 1221),
            (29.97, -41.5081748415082, -1244),
            (59.94, 1221 / 29.97, 2442),
            (7.3, 13 / 7.3, 14),
        ],
    )
    def test_float32_display_starts(
        self, rate: float, seconds: float, expected: int
    ) -> None:
        cdta = _cdta(rate)
        assert _frame_number(cdta, *_f32_ratio(seconds)) == expected


class TestFrameGridFollowsTheRate:
    def test_stored_timebase_disagreeing_with_the_rate(self) -> None:
        # Old py_aep files stored a 24 fps comp on the 29.97 grid (23976 /
        # time scale 3.125); AE derives the grid from the rate on open and
        # reported displayStartFrame 120 for a 5 s start there.
        cdta = _cdta(24)
        cdta.internal_timebase = 23976
        cdta.time_scale_integer, cdta.time_scale_fractional = 3, 32
        assert _frame_number(cdta, 5 * 23976, 23976) == 120


class TestFixedPointRates:
    """A rate whose 16.16 fraction rounds up to 65536 carries into the
    integer part instead of overflowing the u2 (save used to raise)."""

    def test_cdta(self) -> None:
        cdta = CdtaChunk()
        cdta.frame_rate = 23.99999999
        assert (cdta.frame_rate_integer, cdta.frame_rate_fractional) == (24, 0)
        assert len(cdta.tobytes()) == len(CdtaChunk().tobytes())

    def test_render_settings(self) -> None:
        item = RenderSettingsItem()
        item.frame_rate = 29.9999999
        assert (item.frame_rate_integer, item.frame_rate_fractional) == (30, 0)

    def test_output_module(self) -> None:
        roou = RouuChunk()
        roou.frame_rate = 1.99999999
        assert (roou.frame_rate_integer, roou.frame_rate_fractional) == (2, 0)

    def test_footage_rates(self) -> None:
        sspc = SspcChunk()
        sspc.native_frame_rate = 23.99999999
        sspc.conform_frame_rate = 29.9999999
        assert sspc.native_frame_rate == 24.0
        assert sspc.conform_frame_rate == 30.0
        assert sspc.display_frame_rate == 30.0
        assert sspc.tobytes()


class TestSignedWorkAreaStart:
    def test_negative_start_reads_signed(self) -> None:
        # AE 2026 stores -1 frame (-1024/24576) for a zero-length comp.
        cdta = CdtaChunk()
        cdta.work_area_start_dividend = -1024
        cdta.work_area_start_divisor = 24576
        again = CdtaChunk.frombytes(cdta.tobytes())
        assert isinstance(again, CdtaChunk)
        assert again.work_area_start == pytest.approx(-1 / 24)


class TestLayerTimebase:
    # (comp timebase, stretch / 100) -> the tdb4 time base AE 2026 stored.
    @pytest.mark.parametrize(
        ("comp_timebase", "stretch", "expected"),
        [
            (24576, 1.0, 24576),
            (24576, 0.5, 24576),
            (77777, -1.0, 77777),
            (24576, 1.5, 36864),
            (24576, -1.5, 36864),
            (23976, 1.5, 35964),
            (24576, 1.3333, 32767),
            (32768, 1.3333, 43689),
            (30720, 1.16, 35635),
            # 16.16 stretch: the exact 1.16 would give 114982.
            (99123, 1.16, 114983),
            (77777, 1.48, 115109),
            # Capped at 115200.
            (24576, 4.5, 110592),
            (24576, 5.0, 115200),
            (24576, -5.0, 115200),
            (24576, 99.0, 115200),
            (77777, 1.5, 115200),
            (30720, 4.0, 115200),
        ],
    )
    def test_matches_ae(
        self, comp_timebase: int, stretch: float, expected: int
    ) -> None:
        assert layer_timebase(comp_timebase, stretch) == expected


class TestStretchEncoding:
    # The ldta ratio AE 2026 stored for `layer.stretch = percent`.
    @pytest.mark.parametrize(
        ("percent", "ratio"),
        [
            (133.33, (11184531, 8388608)),
            (33.333, (11184699, 33554432)),
            (1.0, (5368709, 536870912)),
            (9900.0, (99, 1)),
            (-9900.0, (-99, 1)),
            (-150.0, (-3, 2)),
            (100.0, (1, 1)),
        ],
    )
    def test_float32_ratio(self, percent: float, ratio: tuple[int, int]) -> None:
        ldta = LdtaChunk()
        ldta.stretch = percent
        assert (ldta.stretch_dividend, ldta.stretch_divisor) == ratio
