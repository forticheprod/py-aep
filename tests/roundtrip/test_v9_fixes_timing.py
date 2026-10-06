"""Composition timing, markers and render-queue writes (v9 fuzz fixes).

The expected values are After Effects 2026 measurements (headless probes on
the same writes) unless a comment says otherwise.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from helpers import parse_project_fresh, project_bytes

import py_aep
from py_aep import MarkerValue
from py_aep.enums import RQItemStatus, TimeSpanSource

if TYPE_CHECKING:
    from py_aep import Project
    from py_aep.models.items.composition import CompItem

SAMPLES = Path(__file__).parent.parent.parent / "samples"


def _new_comp(
    rate: float = 24.0, duration: float = 10.0, platform: str | None = None
) -> tuple[Project, CompItem]:
    project = py_aep.new(platform=platform).project
    return project, project.root_folder.add_comp("c", 640, 360, 1.0, duration, rate)


def _reparse(project: Project, tmp_path: Path, name: str = "out.aep") -> Project:
    out = tmp_path / name
    project.save(out)
    return parse_project_fresh(out)


class TestFrameNumbers:
    @pytest.mark.parametrize("rate", [29.97, 59.94])
    def test_frames_read_back_at_ntsc_rates(self, rate: float, tmp_path: Path) -> None:
        project, comp = _new_comp(rate, 3600.0)
        comp.frame_time = 246
        comp.display_start_frame = 1221
        comp.work_area_start_frame = 10000
        for c in (comp, _reparse(project, tmp_path).compositions[0]):
            assert c.frame_time == 246
            assert c.display_start_frame == 1221
            assert c.work_area_start_frame == 10000

    def test_negative_times_match_extendscript_json(self) -> None:
        # frameTime from the ExtendScript export of this AE-saved sample.
        project = parse_project_fresh(
            SAMPLES / "bugs" / "29.97_fps_time_scale_3.125.aep"
        )
        frame_times = {c.id: c.frame_time for c in project.compositions}
        assert frame_times[11516] == -1244
        assert frame_times[155] == -1221


class TestFrameRateChangeRetimesCompMarkers:
    def test_unread_comp_markers_keep_their_seconds(self, tmp_path: Path) -> None:
        project, comp = _new_comp()
        comp.marker_property.set_value_at_time(3.0, MarkerValue("m"))
        fresh = _reparse(project, tmp_path, "a.aep").compositions[0]
        fresh.frame_rate = 25  # the markers have not been read since parse
        again = _reparse(fresh._project, tmp_path, "b.aep").compositions[0]
        for c in (fresh, again):
            assert [k.time for k in c.marker_property.keyframes] == [3.0]
            assert c.marker_property._tdb4._time_base == 25600

    def test_duplicate_markers_keep_their_seconds(self) -> None:
        project, comp = _new_comp()
        comp.marker_property.set_value_at_time(3.0, MarkerValue("m"))
        dup = comp.duplicate()
        dup.frame_rate = 25
        assert [k.time for k in dup.marker_property.keyframes] == [3.0]


class TestDurationKeepsTimesInside:
    """AE 2026 `comp.duration = d` on a 10 s 24 fps comp."""

    def test_pinned_end_past_new_end(self) -> None:
        _, comp = _new_comp()
        comp.work_area_start = 5
        comp.work_area_duration = 3
        comp.duration = 7
        assert (comp.work_area_start, comp.work_area_duration) == (5.0, 2.0)
        assert comp._cdta.work_area_end_dividend == 0xFFFFFFFF

    @pytest.mark.parametrize("pinned", [True, False])
    def test_start_past_new_end_moves_to_last_frame(self, pinned: bool) -> None:
        _, comp = _new_comp()
        comp.work_area_start = 5
        if pinned:
            comp.work_area_duration = 3
        comp.duration = 4
        assert comp.work_area_start == pytest.approx(95 / 24)
        assert comp.work_area_duration == pytest.approx(1 / 24)

    @pytest.mark.parametrize("time", [9.0, 5.0])
    def test_time_moves_to_last_frame(self, time: float) -> None:
        _, comp = _new_comp()
        comp.time = time
        comp.duration = 4 if time == 9.0 else 5
        assert comp.time == pytest.approx(comp.duration - 1 / 24)

    def test_end_at_new_end_runs_to_end(self) -> None:
        _, comp = _new_comp()
        comp.work_area_start = 2
        comp.work_area_duration = 3
        comp.duration = 5
        assert (comp.work_area_start, comp.work_area_duration) == (2.0, 3.0)
        assert comp._cdta.work_area_end_dividend == 0xFFFFFFFF

    def test_time_restored_over_timebase(self) -> None:
        _, comp = _new_comp()
        comp.duration = 20
        assert comp._cdta.time_divisor == comp._cdta.internal_timebase


class TestFrameRateChangeKeepsTimesInside:
    def test_work_area_start_on_the_end(self) -> None:
        _, comp = _new_comp()
        comp.work_area_start = 9.9
        comp.frame_rate = 1
        assert (comp.work_area_start, comp.work_area_duration) == (9.0, 1.0)

    def test_work_area_start_rounding_to_the_end(self) -> None:
        _, comp = _new_comp()
        comp.frame_rate = 99
        comp.duration = 1
        comp.work_area_start = 98 / 99
        comp.frame_rate = 1
        assert (comp.work_area_start, comp.work_area_duration) == (0.0, 1.0)

    def test_time_and_pinned_end_on_the_end(self) -> None:
        _, comp = _new_comp()
        comp.work_area_start = 1
        comp.work_area_duration = 239 / 24 - 1
        comp.time = 239 / 24
        comp.frame_rate = 1
        assert comp.time == 9.0
        assert comp._cdta.work_area_end_dividend == 0xFFFFFFFF


class TestDecimalRates:
    @pytest.mark.parametrize(
        ("rate", "duration"),
        [
            (23.98, 10.0083402835696),
            (29.98, 10.0066711140761),
            (7.3, 10.0),
            (44.1, 10.0),
            (99.99, 10.00100010001),
        ],
    )
    def test_add_comp_duration(self, rate: float, duration: float) -> None:
        _, comp = _new_comp(rate)
        assert comp.duration == pytest.approx(duration, abs=1e-9)

    def test_rate_change_keeps_keyframe_seconds(self, tmp_path: Path) -> None:
        project, comp = _new_comp()
        layer = comp.add_solid([1.0, 0.0, 0.0], "s", 64, 64)
        opacity = layer.property("ADBE Transform Group").property("ADBE Opacity")
        opacity.set_value_at_time(1.0, 0.0)
        opacity.set_value_at_time(5.5, 100.0)
        comp.frame_rate = 7.3
        again = _reparse(project, tmp_path).compositions[0]
        times = [
            k.time
            for k in again.layers[0]
            .property("ADBE Transform Group")
            .property("ADBE Opacity")
            .keyframes
        ]
        assert times == pytest.approx([1.0, 5.5], abs=1e-9)
        assert again.duration == pytest.approx(10.0)


class TestRateRoundingSaves:
    def test_comp_rate(self, tmp_path: Path) -> None:
        project, comp = _new_comp()
        comp.frame_rate = 23.99999999
        assert _reparse(project, tmp_path).compositions[0].frame_rate == 24.0

    def test_use_this_frame_rate(self, tmp_path: Path) -> None:
        project, comp = _new_comp()
        project.render_queue.add(comp).settings["Use this frame rate"] = 29.9999999
        rqi = _reparse(project, tmp_path).render_queue.items[0]
        assert rqi.settings["Use this frame rate"] == 30.0


class TestNewItemOutputPath:
    def test_file_template_on_added_item(self, tmp_path: Path) -> None:
        # A Windows path: on a macOS project (the default off Windows) it
        # would be stored as `/out/...`.
        project, comp = _new_comp(platform="windows")
        rqi = project.render_queue.add(comp)
        assert rqi.status == RQItemStatus.NEEDS_OUTPUT
        template = "C:\\out\\[compName]_[#####].[fileExtension]"
        rqi.output_modules[0].file_template = template
        again = _reparse(project, tmp_path).render_queue.items[0]
        for item in (rqi, again):
            assert item.output_modules[0].file_template == template
            assert item.output_modules[0].file == "C:\\out\\c_[#####].tif"
            assert item.status == RQItemStatus.QUEUED
            assert item._ldat.render_checked
            # AE ignores an output path record without this bit.
            assert item.output_modules[0]._om_ldat.has_output_file


class TestTimeSpanWrites:
    @pytest.mark.parametrize("bad", [float("inf"), float("nan"), 1e300, 2.0**31])
    def test_rejected_duration_mutates_nothing(self, bad: float) -> None:
        project = parse_project_fresh(
            SAMPLES / "models" / "renderqueue" / "skip_frames.aep"
        )
        rqi = project.render_queue.items[0]
        before = project_bytes(project)
        with pytest.raises(ValueError):
            rqi.time_span_duration = bad
        assert project_bytes(project) == before

    def test_string_rejected(self) -> None:
        project, comp = _new_comp()
        rqi = project.render_queue.add(comp)
        with pytest.raises(TypeError):
            rqi.time_span_start = "1"  # type: ignore[assignment]

    @pytest.mark.parametrize(
        ("work_area", "steps", "expected"),
        [
            (None, [("start", 1.03)], (1.03, 8.97)),
            (None, [("duration", 2.51), ("start", 1.03)], (1.03, 2.51)),
            (None, [("start", 1), ("duration", 5), ("start", 3)], (3.0, 5.0)),
            ((2, 3), [("start", 2.5)], (2.5, 2.5)),
            (None, [("start", 9)], (9.0, 1.0)),
            (None, [("duration", 2.51), ("start", 9)], (9.0, 2.51)),
            (None, [("start", 2), ("start", 1)], (1.0, 8.0)),
        ],
    )
    def test_start_keeps_end_then_duration(
        self,
        work_area: tuple[float, float] | None,
        steps: list[tuple[str, float]],
        expected: tuple[float, float],
    ) -> None:
        # AE 2026: the first start write from the work area / comp keeps the
        # end, a start write on a CUSTOM span keeps the duration.
        project, comp = _new_comp()
        if work_area is not None:
            comp.work_area_start, comp.work_area_duration = work_area
        rqi = project.render_queue.add(comp)
        for field, value in steps:
            setattr(rqi, "time_span_" + field, value)
        assert rqi.settings["Time Span"] == TimeSpanSource.CUSTOM
        assert (rqi.time_span_start, rqi.time_span_duration) == pytest.approx(expected)


class TestBounds:
    def test_comp_frame_rate_up_to_999(self) -> None:
        project, comp = _new_comp()
        comp.frame_rate = 999
        assert comp.frame_rate == 999
        assert (
            project.root_folder.add_comp("x", 64, 64, 1.0, 10.0, 120).frame_rate == 120
        )
        with pytest.raises(ValueError):
            comp.frame_rate = 999.5

    @pytest.mark.parametrize(
        ("rate", "lowest", "highest"),
        [(24, -259200, 2072160), (29.97, -323676, 2587609), (23.976, -258940, 2070087)],
    )
    def test_display_start_bounds(self, rate: float, lowest: int, highest: int) -> None:
        # AE 2026 bisected: frames from -10800 s to 86340 s; displayStartTime
        # itself goes to 86400 s.
        _, comp = _new_comp(rate)
        comp.display_start_time = 86400
        comp.display_start_frame = lowest
        comp.display_start_frame = highest
        assert comp.display_start_frame == highest
        with pytest.raises(ValueError):
            comp.display_start_frame = highest + 1
        with pytest.raises(ValueError):
            comp.display_start_frame = lowest - 1


class TestNullNaming:
    def test_numbered_across_the_project(self) -> None:
        # AE 2026: nulls take the next "Null N" over every project item
        # (solids, comps, folders), whatever comp they are added to.
        project = py_aep.new().project
        a = project.root_folder.add_comp("A", 64, 64, 1.0, 10.0, 24)
        b = project.root_folder.add_comp("B", 64, 64, 1.0, 10.0, 24)
        assert [a.add_null().name, b.add_null().name] == ["Null 1", "Null 2"]
        project.root_folder.add_folder("Null 20")
        assert a.add_null().name == "Null 21"


class TestRenderQueueItemIds:
    def test_added_and_duplicated_items_get_new_ids(self, tmp_path: Path) -> None:
        project, comp = _new_comp()
        rq = project.render_queue
        first, second = rq.add(comp), rq.add(comp)
        dup = first.duplicate()
        assert [first._ldat.item_id, second._ldat.item_id, dup._ldat.item_id] == [
            2,
            3,
            4,
        ]
        assert sorted(
            i._ldat.item_id for i in _reparse(project, tmp_path).render_queue.items
        ) == [2, 3, 4]

    def test_next_id_follows_the_highest(self) -> None:
        project = parse_project_fresh(
            SAMPLES / "models" / "renderqueue" / "2_rqitems.aep"
        )
        rq = project.render_queue
        rq.items[0]._ldat.item_id, rq.items[1]._ldat.item_id = 9, 3
        assert rq.add(project.compositions[0])._ldat.item_id == 10
        assert rq.items[0].duplicate()._ldat.item_id == 11


class TestSettingsWritten:
    def test_set_by_settings_writes_only(self) -> None:
        project, comp = _new_comp()
        rq = project.render_queue
        item = rq.add(comp)
        item.skip_frames = 1
        item.time_span_start = 1
        assert item._ldat.settings_written == 0
        item.settings["Quality"] = item.settings["Quality"]
        assert item._ldat.settings_written == 1


class TestDuplicateTime:
    def test_duplicate_starts_at_time_zero(self) -> None:
        _, comp = _new_comp()
        comp.time = 2.5
        dup = comp.duplicate()
        assert comp.time == 2.5
        assert dup.time == 0.0


class TestRatesWithMoreDecimals:
    @pytest.mark.parametrize(
        ("rate", "duration"),
        [
            (3.3333, 9.9009900990099),
            (12.3456, 9.96274096873481),
            (39.0625, 10.00947187876),
            (1.001, 9.99000999000999),
            (99.123, 9.99767965053519),
            (78.125, 9.9968),
        ],
    )
    def test_new_comp_duration(self, rate: float, duration: float) -> None:
        # AE 2026 addComp(..., 10 s, rate): the duration snaps on the grid
        # of the rate read to the thousandth (3.333 fps: 8000 units a frame).
        _, comp = _new_comp(rate)
        assert comp.duration == pytest.approx(duration, abs=1e-9)


_SVG_NS = 'xmlns="http://www.w3.org/2000/svg"'


class TestTinySvgCanvas:
    @pytest.mark.parametrize(
        ("attrs", "size"),
        [
            ('viewBox="0 0 3 100"', (3, 100)),
            ('viewBox="0 0 1 1"', (1, 1)),
            ('width="2" height="5"', (2, 5)),
        ],
    )
    def test_imports_comp_below_add_comp_floor(
        self, tmp_path: Path, attrs: str, size: tuple[int, int]
    ) -> None:
        # AE 2026 imports these as 3x100, 1x1 and 2x5 comps (1 frame, 30 fps,
        # one shape layer), although its addComp refuses under 4 px.
        svg = tmp_path / "tiny.svg"
        svg.write_text(
            f"<svg {_SVG_NS} {attrs}><rect width='1' height='1'/></svg>",
            encoding="utf-8",
        )
        project = py_aep.new().project
        opts = py_aep.ImportOptions(svg)
        opts.import_as = py_aep.ImportAsType.COMP_CROPPED_LAYERS
        comp = project.import_file(opts)
        again = next(
            c for c in _reparse(project, tmp_path).compositions if c.name == "tiny.svg"
        )
        for c in (comp, again):
            assert (c.width, c.height) == size
            assert len(c.layers) == 1
            assert c.frame_rate == 30.0

    def test_add_comp_keeps_its_floor(self) -> None:
        # AE 2026 addComp: "Value 3 out of range 4 to 30000".
        project = py_aep.new().project
        with pytest.raises(ValueError, match="must be >= 4"):
            project.root_folder.add_comp("x", 3, 100, 1.0, 1.0, 30.0)


_KEY_TIMES = [4.0, 2.0, 0.5, 1.3, 7.25]


def _stretched_layer(
    comp: CompItem, stretch: float, start: float, times: list[float] = _KEY_TIMES
) -> Any:
    """A solid set up like the AE probe: stretch, then start, then keys."""
    layer = comp.add_solid([0.5, 0.5, 0.5], "L", 10, 10, 1.0, 10.0)
    layer.stretch = stretch
    layer.start_time = start
    for i, t in enumerate(times):
        layer.transform.opacity.set_value_at_time(t, 10.0 * (i + 1))
    return layer


def _ticks(layer: Any) -> list[int]:
    return sorted(kf.time_units for kf in layer.transform.opacity.keyframes)


def _start_ratio(layer: Any) -> tuple[int, int]:
    return layer._ldta.start_time_dividend, layer._ldta.start_time_divisor


class TestStretchedLayerKeyTimes:
    # Key times and stored ticks AE 2026 reported / saved for the same
    # setValueAtTime calls on a new layer (stretch, then startTime 1.3).
    @pytest.mark.parametrize(
        ("rate", "start_ratio", "ticks", "times"),
        [
            (
                24.0,
                (47923, 36864),
                [-146240, -66368, -17216, -12, 19648],
                [
                    7.25001540798611,
                    4.00001540798611,
                    2.00001540798611,
                    1.29998285590278,
                    0.50001540798611,
                ],
            ),
            (
                29.97,
                (46753, 35964),
                [-142669, -64747, -16795, -12, 19169],
                [
                    7.24998659770882,
                    3.99998659770882,
                    1.99998659770882,
                    1.29999493938383,
                    0.49998659770882,
                ],
            ),
        ],
    )
    def test_reversed_layer_with_start_matches_ae(
        self,
        rate: float,
        start_ratio: tuple[int, int],
        ticks: list[int],
        times: list[float],
        tmp_path: Path,
    ) -> None:
        project, comp = _new_comp(rate)
        layer = _stretched_layer(comp, -150.0, 1.3)
        again = _reparse(project, tmp_path).compositions[0].layers[0]
        for lyr in (layer, again):
            assert _start_ratio(lyr) == start_ratio
            assert _ticks(lyr) == ticks
            got = [kf.time for kf in lyr.transform.opacity.keyframes]
            assert got == pytest.approx(times, abs=1e-12)

    @pytest.mark.parametrize(
        ("stretch", "key_time"),
        [(500.0, 4.0), (9900.0, 4.00015625), (-500.0, 3.99998263888889)],
    )
    def test_timebase_is_capped(
        self, stretch: float, key_time: float, tmp_path: Path
    ) -> None:
        # 24 fps x 5 would be 122880: AE counts these layers' ticks against
        # 115200, and reads a key it set at 4.0 back at these times.
        project, comp = _new_comp(24.0)
        layer = _stretched_layer(comp, stretch, 1.3, [4.0])
        again = _reparse(project, tmp_path).compositions[0].layers[0]
        for lyr in (layer, again):
            prop = lyr.transform.opacity
            assert prop._tdb4._time_base == 115200
            assert _start_ratio(lyr) == (149760, 115200)
            assert prop.keyframes[0].time == pytest.approx(key_time, abs=1e-12)

    def test_key_lands_where_ae_evaluates_the_time(self) -> None:
        # 77.777 fps, 100 %: 0.5 s is 38888.5 comp ticks; AE snaps it up
        # and keys tick -62221 (the nearest tick to the exact layer time is
        # a tie, which round-half-even sent to -62222).
        _project, comp = _new_comp(77.777)
        assert _ticks(_stretched_layer(comp, 100.0, 1.3)) == [
            -62221,
            0,
            54444,
            209998,
            462773,
        ]
        # -50 %: AE keyed 124416 at 0.5 s, one tick off the nearest.
        assert _ticks(_stretched_layer(comp, -50.0, 1.3)) == [
            -925572,
            -420022,
            -108914,
            -26,
            124416,
        ]


class TestLayerStartTime:
    @pytest.mark.parametrize(
        ("rate", "stretch", "start", "ratio"),
        [
            (24.0, 100.0, 1.3, (31949, 24576)),
            (24.0, 150.0, 1.3, (47923, 36864)),
            (24.0, -200.0, 0.7, (34406, 49152)),
            (24.0, -50.0, 1.3, (31949, 24576)),
            (24.0, 100.0, -1.3, (-31949, 24576)),
            (25.0, 150.0, 1.3, (49920, 38400)),
            (29.97, 100.0, 1.3, (31169, 23976)),
            (24.0, 300.0, 10800.0, (796262400, 73728)),
        ],
    )
    def test_snaps_to_layer_ticks(
        self,
        rate: float,
        stretch: float,
        start: float,
        ratio: tuple[int, int],
        tmp_path: Path,
    ) -> None:
        project, comp = _new_comp(rate)
        layer = comp.add_solid([0.5, 0.5, 0.5], "L", 10, 10, 1.0, 10.0)
        layer.stretch = stretch
        layer.start_time = start
        again = _reparse(project, tmp_path).compositions[0].layers[0]
        for lyr in (layer, again):
            assert _start_ratio(lyr) == ratio
            assert lyr.start_time == ratio[0] / ratio[1]

    @pytest.mark.parametrize(
        ("stretch", "ticks", "expected"),
        [
            (100.0, 0.5, 1),
            (100.0, 1.5, 2),
            (100.0, 2.5, 3),
            (100.0, -0.5, 0),
            (100.0, -1.5, -1),
            (100.0, -2.5, -2),
            (200.0, 0.5, 1),
            (200.0, 2.5, 3),
            (200.0, -2.5, -2),
        ],
    )
    def test_tie_rounds_up(self, stretch: float, ticks: float, expected: int) -> None:
        # 32 fps: 32768 ticks a second (65536 at 200 %), so these are exact.
        _project, comp = _new_comp(32.0)
        layer = comp.add_solid([0.5, 0.5, 0.5], "L", 10, 10, 1.0, 10.0)
        layer.stretch = stretch
        base = layer.transform.opacity._layer_timebase
        layer.start_time = ticks / base
        assert layer._ldta.start_time_dividend == expected

    def test_stretch_change_keeps_the_stored_start(self) -> None:
        _project, comp = _new_comp(24.0)
        layer = comp.add_solid([0.5, 0.5, 0.5], "L", 10, 10, 1.0, 10.0)
        layer.start_time = 1.3
        layer.stretch = 150.0
        assert _start_ratio(layer) == (31949, 24576)
        layer.stretch = 100.0
        layer.start_time = 1.3
        layer.stretch = -150.0
        assert _start_ratio(layer) == (31949, 24576)

    def test_start_past_the_field_is_rejected(self) -> None:
        # At 115200 ticks a second the signed 32-bit start holds 18641 s.
        _project, comp = _new_comp(24.0)
        layer = comp.add_solid([0.5, 0.5, 0.5], "L", 10, 10, 1.0, 10.0)
        layer.stretch = 500.0
        layer.start_time = 18641.0
        before = _start_ratio(layer)
        with pytest.raises(ValueError, match="must be <="):
            layer.start_time = 18642.0
        with pytest.raises(ValueError, match="must be >="):
            layer.start_time = -18642.0
        assert _start_ratio(layer) == before


class TestRetimeRoundsHalfUp:
    def test_stretch_change(self) -> None:
        # Keys at ticks 15, -13, -15, 13 (24 fps, 100 %); AE 2026 at 150 %.
        _project, comp = _new_comp(24.0)
        layer = _stretched_layer(
            comp, 100.0, 0.0, [u / 24576 for u in (15, -13, -15, 13)]
        )
        layer.stretch = 150.0
        assert _ticks(layer) == [-22, -19, 20, 23]

    def test_frame_rate_change(self) -> None:
        # 24 -> 25 fps scales ticks by 25 / 24, ties up; a 500 % layer sits
        # at the 115200 cap at both rates, so its ticks stay (AE 2026).
        _project, comp = _new_comp(24.0)
        times = [u / 24576 for u in (12, 60, -36, -84, 24576)]
        plain = _stretched_layer(comp, 100.0, 0.0, times)
        capped = _stretched_layer(comp, 100.0, 0.0, times)
        capped.stretch = 500.0
        assert _ticks(capped) == [-394, -169, 56, 281, 115200]
        comp.frame_rate = 25.0
        assert _ticks(plain) == [-87, -37, 13, 63, 25600]
        assert _ticks(capped) == [-394, -169, 56, 281, 115200]


def _stretch_ratio(layer: Any) -> tuple[int, int]:
    return layer._ldta.stretch_dividend, layer._ldta.stretch_divisor


class TestStretchStorage:
    def test_float32_ratio_survives_a_roundtrip(self, tmp_path: Path) -> None:
        project, comp = _new_comp(24.0)
        layer = comp.add_solid([0.5, 0.5, 0.5], "L", 10, 10, 1.0, 10.0)
        layer.stretch = 133.33
        again = _reparse(project, tmp_path).compositions[0].layers[0]
        for lyr in (layer, again):
            assert _stretch_ratio(lyr) == (11184531, 8388608)
            assert lyr.stretch == 11184531 * 100 / 8388608

    def test_near_tie_key_matches_ae(self) -> None:
        # 133.33 % at 77.777 fps: with the stretch stored as 13333 / 10000 the
        # key set at 4.0 s landed one tick short of AE's 209996.
        _project, comp = _new_comp(77.777)
        layer = _stretched_layer(comp, 133.33, 1.3)
        assert _start_ratio(layer) == (134809, 103699)
        assert _ticks(layer) == [-62221, 0, 54443, 209996, 462768]
        got = sorted(kf.time for kf in layer.transform.opacity.keyframes)
        assert got == pytest.approx(
            [
                0.50000232458115,
                1.30000289298836,
                1.99999856948853,
                4.00000667572021,
                7.24999856948853,
            ],
            abs=1e-6,
        )

    @pytest.mark.parametrize(
        ("percent", "ratio"),
        [
            (0.5, (655, 65536)),
            (0.0001, (655, 65536)),
            (0.0, (655, 65536)),
            (-0.5, (-655, 65536)),
        ],
    )
    def test_under_one_percent(self, percent: float, ratio: tuple[int, int]) -> None:
        # AE 2026 sets them all to 655 / 65536, read back as 0.99945068359375.
        _project, comp = _new_comp(24.0)
        layer = comp.add_solid([0.5, 0.5, 0.5], "L", 10, 10, 1.0, 10.0)
        layer.stretch = percent
        assert _stretch_ratio(layer) == ratio
        assert abs(layer.stretch) == 0.99945068359375

    def test_bound_is_the_field_width(self, tmp_path: Path) -> None:
        # AE refuses 10000 % from a script but opens a file holding 1e6 %.
        project, comp = _new_comp(24.0)
        layer = comp.add_solid([0.5, 0.5, 0.5], "L", 10, 10, 1.0, 10.0)
        layer.stretch = 1e6
        assert _stretch_ratio(layer) == (10000, 1)
        layer.stretch = 2147483520 * 100.0
        assert _stretch_ratio(layer) == (2147483520, 1)
        with pytest.raises(ValueError, match="must be <="):
            layer.stretch = 2147483600 * 100.0
        with pytest.raises(ValueError, match="must be >="):
            layer.stretch = -2147483600 * 100.0
        assert _stretch_ratio(layer) == (2147483520, 1)
        _reparse(project, tmp_path)


class TestFrameGridPastTheCap:
    # AE 2026 addComp(..., 3.3 s, rate), then duration = 1.0001,
    # time = 0.5041, workAreaStart = 0.2004, workAreaDuration = 0.5,
    # displayStartTime = 0.1234, and keys set at 0.5041 and 0.25 s.
    @pytest.mark.parametrize(
        ("rate", "grid", "expected"),
        [
            (
                120.001,
                (60000, 500),
                {
                    "dur0": 3.3,
                    "dur": 1.0,
                    "time": 0.5,
                    "was": 0.2,
                    "wad": 0.5,
                    "dsf": 15,
                    "keys": [0.25, 0.5041],
                },
            ),
            (
                333.333,
                (83333, 250),
                {
                    "dur0": 3.3000132000528,
                    "dur": 0.99900399601598,
                    "time": 0.50400201600806,
                    "was": 0.20100080400322,
                    "wad": 0.50100200400802,
                    "dsf": 42,
                    "keys": [0.249996999988, 0.50409801639207],
                },
            ),
            (
                750.001,
                (93750, 125),
                {
                    "dur0": 3.3,
                    "dur": 1.0,
                    "time": 0.504,
                    "was": 0.2,
                    "wad": 0.5,
                    "dsf": 93,
                    "keys": [0.25000533333333, 0.504096],
                },
            ),
            (
                998.999,
                (62437, 62),
                # AE's duration setter counts this grid's frames differently
                # (999 frames for 1.0001 s); not compared.
                {
                    "dur0": 3.2997421400772,
                    "time": 0.50444448003588,
                    "was": 0.20058619088041,
                    "wad": 0.50047247625607,
                    "dsf": 125,
                    "keys": [0.24999599596393, 0.50409212486186],
                },
            ),
        ],
    )
    def test_comp_times_match_ae(
        self, rate: float, grid: tuple[int, int], expected: dict, tmp_path: Path
    ) -> None:
        project, comp = _new_comp(rate, duration=3.3)
        cdta = comp._cdta
        assert (cdta.internal_timebase, round(cdta.time_scale * 256)) == grid
        got: dict = {"dur0": comp.duration}
        comp.duration = 1.0001
        got["dur"] = comp.duration
        comp.time = 0.5041
        got["time"] = comp.time
        comp.work_area_start = 0.2004
        got["was"] = comp.work_area_start
        comp.work_area_duration = 0.5
        got["wad"] = comp.work_area_duration
        comp.display_start_time = 0.1234
        got["dsf"] = comp.display_start_frame
        layer = comp.add_solid([0.5, 0.5, 0.5], "k", 10, 10, 1.0, 1.0)
        layer.transform.opacity.set_value_at_time(0.5041, 10.0)
        layer.transform.opacity.set_value_at_time(0.25, 20.0)
        got["keys"] = [kf.time for kf in layer.transform.opacity.keyframes]
        for key, value in expected.items():
            assert got[key] == pytest.approx(value, abs=1e-11), key
        again = _reparse(project, tmp_path).compositions[0]
        assert again.time == comp.time
        assert again.work_area_start == comp.work_area_start


class TestReversedInOutPoints:
    # AE 2026: 10 s null, stretch then startTime; inPoint / outPoint read.
    @pytest.mark.parametrize(
        ("stretch", "start", "in_point", "out_point"),
        [
            (-150.0, 1.3, 1.29949457465278, -13.7005054253472),
            (-150.0, -0.7, -0.70050542534722, -15.7005054253472),
            (-100.0, 1.3, 1.2996748046875, -8.7003251953125),
            (-50.0, -0.7, -0.70015852864583, -5.70015852864583),
            (-200.0, 1.3, 1.29934147135417, -18.7006585286458),
            (150.0, 1.3, 1.29999457465278, 16.2999945746528),
        ],
    )
    def test_defaults_match_ae(
        self,
        stretch: float,
        start: float,
        in_point: float,
        out_point: float,
        tmp_path: Path,
    ) -> None:
        project, comp = _new_comp(24.0, duration=30.0)
        layer = comp.add_null(10.0)
        layer.stretch = stretch
        layer.start_time = start
        again = _reparse(project, tmp_path).compositions[0].layers[0]
        for lyr in (layer, again):
            assert lyr.in_point == pytest.approx(in_point, abs=1e-11)
            assert lyr.out_point == pytest.approx(out_point, abs=1e-11)

    def test_writes_read_back(self) -> None:
        # AE 2026, -150 % from 1.3 s: inPoint = 1 then outPoint = -3 read
        # back as written.
        _project, comp = _new_comp(24.0, duration=30.0)
        layer = comp.add_null(10.0)
        layer.stretch = -150.0
        layer.start_time = 1.3
        layer.in_point = 1.0
        layer.out_point = -3.0
        assert layer.in_point == pytest.approx(1.0, abs=1e-9)
        assert layer.out_point == pytest.approx(-3.0, abs=1e-9)

    @pytest.mark.parametrize(
        ("stretch", "which", "value", "expected"),
        [
            (100.0, "in", 2.5 / 24576, 3 / 24576),
            (100.0, "in", -1.5 / 24576, -1 / 24576),
            (100.0, "out", 3 + 2.5 / 24576, 3 + 3 / 24576),
            (150.0, "in", 1 / 36864, 1 / 36864),
            (150.0, "in", 0.5 / 24576, 1 / 36864),
            (-100.0, "in", -2.5 / 24576, -2 / 24576),
            (-150.0, "in", -1 / 36864, -1 / 36864),
        ],
    )
    def test_writes_snap_to_layer_ticks(
        self, stretch: float, which: str, value: float, expected: float
    ) -> None:
        # The times AE 2026 read back for the same writes at 24 fps.
        _project, comp = _new_comp(24.0, duration=30.0)
        layer = comp.add_solid([0.5, 0.5, 0.5], "L", 10, 10, 1.0, 30.0)
        layer.stretch = stretch
        setattr(layer, which + "_point", value)
        assert getattr(layer, which + "_point") == pytest.approx(expected, abs=1e-12)

    def test_ae_sample_matches_extendscript(self) -> None:
        # layer_timing.json: the -100 % layer reads in -0.000333333333,
        # out -60.000333333333.
        project = py_aep.parse(
            SAMPLES / "models" / "layer" / "layer_timing.aep"
        ).project
        reversed_layers = [
            lyr for c in project.compositions for lyr in c.layers if lyr.stretch < 0
        ]
        assert reversed_layers
        for lyr in reversed_layers:
            assert lyr.in_point == pytest.approx(-1 / 3000, abs=1e-12)
            assert lyr.out_point == pytest.approx(-60 - 1 / 3000, abs=1e-12)
