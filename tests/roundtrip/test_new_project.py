"""Tests for py_aep.new() - creating an empty project from scratch."""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import project_bytes

import py_aep
from py_aep.binary.utils import find_by_type, recursive_find
from py_aep.enums import BitsPerChannel, GpuAccelType

EMPTIER = (
    Path(__file__).parent.parent.parent
    / "samples"
    / "models"
    / "project"
    / "emptier.aep"
)
VERSIONS = Path(__file__).parent.parent.parent / "samples" / "versions"


class TestNewEmpty:
    def test_structure(self) -> None:
        app = py_aep.new()
        proj = app.project
        assert app.version == "26.0x67"
        assert app.build_number == 67
        assert proj.num_items == 1  # only the root folder
        assert proj.root_folder.name == "root"
        assert list(proj.items) == [0]
        assert proj._head.next_item_id == 1
        assert proj.revision == 1

    def test_settings_defaults(self) -> None:
        proj = py_aep.new().project
        assert proj.bits_per_channel is BitsPerChannel.EIGHT
        assert proj.audio_sample_rate == 48000.0
        assert proj.expression_engine == "javascript-1.0"

    def test_empty_render_queue(self) -> None:
        rq = py_aep.new().project.render_queue
        assert rq is not None
        assert len(rq.items) == 0

    def test_no_xmp_trailer(self) -> None:
        # XMP is optional; new() omits it (AE regenerates it on open).
        assert py_aep.new().project._xmp == ""

    def test_xmp_packet_none(self) -> None:
        # An empty/blank _xmp must read back as None, not raise ParseError.
        assert py_aep.new().project.xmp_packet is None

    def test_set_xmp_packet_none(self) -> None:
        # Clearing the packet (assigning None) must not crash and must read
        # back as None: the getter and setter are symmetric on the empty case.
        project = py_aep.new().project
        project.xmp_packet = None
        assert project.xmp_packet is None

    def test_to_dict_no_crash(self) -> None:
        # aep-validate walks every attribute (incl. xmp_packet) via to_dict;
        # it must not crash on a new()-based project with no XMP packet.
        from py_aep.cli.validate import to_dict

        result = to_dict(py_aep.new().project)
        assert result["xmp_packet"] is None

    @pytest.mark.parametrize(
        ("platform", "gpu", "os_code", "nnhd_byte", "code_page"),
        [
            # AE's own File > New on Windows (emptier.aep): CUDA, AE 26
            # writes the UTF-8 code page.
            ("windows", GpuAccelType.CUDA, 12, 0x00, "fde9"),
            ("macos", GpuAccelType.METAL, 14, 0x08, "0100"),
        ],
    )
    def test_platform_stamps(
        self,
        platform: str,
        gpu: GpuAccelType,
        os_code: int,
        nnhd_byte: int,
        code_page: str,
    ) -> None:
        project = py_aep.new("26.0x67", platform=platform).project
        assert project._platform == platform
        assert project.gpu_accel_type == gpu
        assert project._head.ae_version_os == os_code
        assert project._nnhd._saving_platform == nnhd_byte
        assert project._nnhd._system_code_page.to_bytes(2, "big").hex() == code_page

    def test_windows_stamps_match_ae_new_project(self) -> None:
        ae = py_aep.parse(EMPTIER).project
        ours = py_aep.new(ae._head.version, platform="windows").project
        assert ours.gpu_accel_type == ae.gpu_accel_type == GpuAccelType.CUDA
        assert ours._head.ae_version_os == ae._head.ae_version_os
        assert ours._nnhd._saving_platform == ae._nnhd._saving_platform
        assert ours._nnhd._system_code_page == ae._nnhd._system_code_page

    def test_pre_26_windows_code_page(self) -> None:
        # Windows AE up to 25 writes code page 1252 (every AE 15-25 sample).
        project = py_aep.new("25.6x101", platform="windows").project
        assert project._nnhd._system_code_page == 1252


class TestNewVersion:
    def test_version_stamped(self) -> None:
        app = py_aep.new("25.6x101")
        assert app.version == "25.6x101"
        assert app.build_number == 101

    def test_svap_build_number(self) -> None:
        # svap's last byte tracks the AE build number.
        app = py_aep.new("25.6x101")
        svap = find_by_type(chunks=app.project._rifx.chunks, chunk_type="svap")
        assert svap.build_number == 101  # type: ignore[attr-defined]

    def test_invalid_version_rejected(self) -> None:
        with pytest.raises(ValueError):
            py_aep.new("not-a-version")

    @pytest.mark.parametrize(
        ("version", "present", "absent"),
        [
            # version-gated chunks: ExEn (AE16+), mrid/pcms/PwCs (AE22+),
            # pdvc (AE23+). Boundaries from samples/versions + emptier_2018.
            ("26.0x67", {"ExEn", "mrid", "pcms", "PwCs", "pdvc"}, set()),
            ("23.0x1", {"ExEn", "mrid", "pcms", "PwCs", "pdvc"}, set()),
            ("22.0x1", {"ExEn", "mrid", "pcms", "PwCs"}, {"pdvc"}),
            ("16.0x1", {"ExEn"}, {"mrid", "pcms", "PwCs", "pdvc"}),
            ("15.1x69", set(), {"ExEn", "mrid", "pcms", "PwCs", "pdvc"}),
        ],
    )
    def test_version_gated_chunks(
        self, version: str, present: set[str], absent: set[str]
    ) -> None:
        chunks = py_aep.new(version).project._rifx.chunks
        types = {getattr(c, "list_type", "") or c.chunk_type for c in chunks}
        assert present <= types
        assert not (absent & types)

    def test_gated_down_reparses(self, tmp_path: Path) -> None:
        # A gated-down skeleton (no ExEn/CMS) must still round-trip.
        path = tmp_path / "old.aep"
        py_aep.new("15.1x69").project.save(path)
        proj = py_aep.parse(path).project
        assert proj.num_items == 1
        assert proj.expression_engine == "extendscript"  # ExEn absent -> default

    @pytest.mark.parametrize(
        ("version", "stamp"),
        [
            ("26.0x67", (97, 2)),
            ("25.0x1", (96, 9)),
            ("24.0x1", (95, 6)),
            ("23.0x1", (94, 9)),
            ("22.0x1", (93, 43)),
            ("18.0x1", (93, 29)),
            ("17.0x1", (93, 22)),
            ("16.0x1", (93, 5)),
            ("15.1x69", (92, 14)),
        ],
    )
    def test_format_version_per_release(
        self, version: str, stamp: tuple[int, int]
    ) -> None:
        # AE gates opening on the format version and reads a file with the
        # rules of its (format, minor) pair, so new(version) stamps the pair
        # After Effects writes for that release.
        head = py_aep.new(version).project._head
        assert (head.file_format_version, head._format_subversion) == stamp

    @pytest.mark.parametrize("year", ["ae2018", "ae2023", "ae2024", "ae2025", "ae2026"])
    def test_format_version_matches_after_effects_samples(self, year: str) -> None:
        sample = py_aep.parse(VERSIONS / year / "complete.aep")
        head = py_aep.new(sample.version).project._head
        saved = sample.project._head
        assert (head.file_format_version, head._format_subversion) == (
            saved.file_format_version,
            saved._format_subversion,
        )

    @pytest.mark.parametrize(
        ("version", "has_mrid"), [("17.0x1", True), ("16.0x1", False)]
    )
    def test_mrid_from_ae_17(self, version: str, has_mrid: bool) -> None:
        chunks = py_aep.new(version).project._rifx.chunks
        assert any(c.chunk_type == "mrid" for c in chunks) is has_mrid

    @pytest.mark.parametrize(
        ("source", "ldta_size"),
        [("new 22", 160), ("ae2022 sample", 160), ("new 23", 164)],
    )
    def test_new_comp_layer_records_fit_the_release(
        self, source: str, ldta_size: int, tmp_path: Path
    ) -> None:
        # AE 22 writes 160-byte layer records (samples/versions/ae2022); the
        # matte-layer field that makes them 164 arrived with AE 23. AE refuses
        # a 22-format file holding the longer record ("chunk in file too big").
        if source == "ae2022 sample":
            app = py_aep.parse(VERSIONS / "ae2022" / "complete.aep")
        else:
            app = py_aep.new(source.split()[1] + ".0x1")
        comp = app.project.root_folder.add_comp("Depth", 320, 240, 1.0, 2.0, 25.0)
        comp.add_solid([1.0, 0.0, 0.0], "Red", 320, 240)
        path = tmp_path / "comp.aep"
        app.project.save(path)
        reread = py_aep.parse(path).project
        new_comp = next(c for c in reread.compositions if c.name == "Depth")
        records = recursive_find(new_comp._item_list.chunks, chunk_type="ldta")
        assert {len(record.tobytes()) for record in records} == {ldta_size}

    def test_layer_copied_across_comps_keeps_a_22_record(self, tmp_path: Path) -> None:
        app = py_aep.parse(VERSIONS / "ae2022" / "complete.aep")
        source = app.project.root_folder.add_comp("Source", 320, 240, 1.0, 2.0, 25.0)
        target = app.project.root_folder.add_comp("Target", 320, 240, 1.0, 2.0, 25.0)
        source.add_solid([1.0, 0.0, 0.0], "Red", 320, 240).copy_to_comp(target)
        path = tmp_path / "copy.aep"
        app.project.save(path)
        reread = py_aep.parse(path).project
        copied = next(c for c in reread.compositions if c.name == "Target").layers[0]
        assert len(copied._ldta.tobytes()) == 160


class TestNewRoundTrip:
    def test_byte_stable(self, tmp_path: Path) -> None:
        app = py_aep.new()
        original = project_bytes(app.project)
        path = tmp_path / "empty.aep"
        app.project.save(path)
        reparsed = py_aep.parse(path)
        assert project_bytes(reparsed.project) == original

    def test_reparse_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.aep"
        py_aep.new().project.save(path)
        proj = py_aep.parse(path).project
        assert proj.num_items == 1
        assert proj.render_queue is not None


class TestNewMutations:
    def test_add_comp(self, tmp_path: Path) -> None:
        app = py_aep.new()
        app.project.root_folder.add_comp("Comp 1", 1920, 1080, 1.0, 10.0, 30.0)
        path = tmp_path / "comp.aep"
        app.project.save(path)
        proj = py_aep.parse(path).project
        assert [c.name for c in proj.compositions] == ["Comp 1"]
        comp = proj.compositions[0]
        assert (comp.width, comp.height) == (1920, 1080)

    def test_add_folder(self, tmp_path: Path) -> None:
        app = py_aep.new()
        app.project.root_folder.add_folder("Assets")
        path = tmp_path / "folder.aep"
        app.project.save(path)
        proj = py_aep.parse(path).project
        assert "Assets" in [f.name for f in proj.folders]

    def test_import_placeholder(self, tmp_path: Path) -> None:
        app = py_aep.new()
        app.project.import_placeholder("PH", 640, 480, 25.0, 5.0)
        path = tmp_path / "ph.aep"
        app.project.save(path)
        proj = py_aep.parse(path).project
        assert [f.name for f in proj.footages] == ["PH"]

    def test_ae_preferences_dir_threaded(self, tmp_path: Path) -> None:
        app = py_aep.new(ae_preferences_dir=tmp_path)
        assert app.project._ae_preferences_dir == tmp_path


def _ae_prefs_dir() -> Path | None:
    """Newest installed AE preferences directory, or None (for CI)."""
    base = Path.home() / "AppData" / "Roaming" / "Adobe" / "After Effects"
    if not base.is_dir():
        return None
    dirs = sorted(d for d in base.iterdir() if d.is_dir() and d.name[:1].isdigit())
    return dirs[-1] if dirs else None


class TestNewRenderQueue:
    def test_render_queue_add(self, tmp_path: Path) -> None:
        prefs = _ae_prefs_dir()
        if prefs is None:
            pytest.skip("no AE preferences dir (render templates unavailable)")
        app = py_aep.new(ae_preferences_dir=prefs)
        comp = app.project.root_folder.add_comp("Comp 1", 1920, 1080, 1.0, 10.0, 30.0)
        app.project.render_queue.add(comp)
        path = tmp_path / "rq.aep"
        app.project.save(path)
        proj = py_aep.parse(path, ae_preferences_dir=prefs).project
        assert len(proj.render_queue.items) == 1
        assert proj.render_queue.items[0].comp.name == "Comp 1"
