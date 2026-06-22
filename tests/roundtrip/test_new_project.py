"""Tests for py_aep.new() - creating an empty project from scratch."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

import py_aep
from py_aep.binary.chunk import write_aep
from py_aep.binary.utils import find_by_list_type, find_by_type
from py_aep.enums import BitsPerChannel


def _serialize(app: py_aep.Application) -> bytes:
    buf = io.BytesIO()
    write_aep(buf, app.project._rifx, app.project._xmp)
    return buf.getvalue()


def _gpu_uuid(app: py_aep.Application) -> str:
    gpug = find_by_list_type(chunks=app.project._rifx.chunks, list_type="gpuG")
    return find_by_type(chunks=gpug.chunks, chunk_type="Utf8").value  # type: ignore[attr-defined]


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

    def test_fresh_gpu_uuid(self) -> None:
        # Each new project gets its own gpuG id rather than a baked one.
        assert _gpu_uuid(py_aep.new()) != _gpu_uuid(py_aep.new())


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
        ("version", "format_version"),
        [
            ("26.0x67", 26 + 71),
            ("25.0x1", 25 + 71),
            ("24.0x1", 24 + 71),
            ("23.0x1", 23 + 71),
            ("22.0x1", 22 + 71),
        ],
    )
    def test_format_version_deduced(self, version: str, format_version: int) -> None:
        # AE gates opening on head.file_format_version (= major + 71), so
        # new(old_version) must stamp that version's format byte.
        head = find_by_type(
            chunks=py_aep.new(version).project._rifx.chunks, chunk_type="head"
        )
        assert head.file_format_version == format_version  # type: ignore[attr-defined]


class TestNewRoundTrip:
    def test_byte_stable(self, tmp_path: Path) -> None:
        app = py_aep.new()
        original = _serialize(app)
        path = tmp_path / "empty.aep"
        app.project.save(path)
        reparsed = py_aep.parse(path)
        assert _serialize(reparsed) == original

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
