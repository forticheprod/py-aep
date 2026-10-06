"""Regression tests for the v9 fuzz findings on new projects, versions,
working space and saving.

After Effects 2026 (26.0x67) evidence: `py_aep.new()` projects stamped with a
major that was never an AE release opened as "missing data in file"
(21.0x1), "internal verification failure" (0.0x0), or with every mask,
effect and shape-element name read as "Utf8" (12, 13, 14, 19 and 20).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import project_bytes

import py_aep
from py_aep import parse


class TestVersionValidation:
    @pytest.mark.parametrize(
        "version",
        [
            "15.1x69",
            "16.0x1",
            "17.0x1",
            "18.0x1",
            "22.6x60",
            "23.0x1",
            "24.0x1",
            "25.6x101",
            "26.0x67",
            "26.15x255",
        ],
    )
    def test_releases_accepted(self, version: str) -> None:
        assert py_aep.new(version).version == version

    @pytest.mark.parametrize(
        "version",
        [
            "0.0x0",
            "12.0x1",
            "14.0x1",
            "19.0x1",
            "20.0x1",
            "21.0x1",
            "27.0x1",
            "185.0x1",
            "256.0x1",
        ],
    )
    def test_unknown_major_rejected(self, version: str) -> None:
        with pytest.raises(ValueError):
            py_aep.new(version)

    @pytest.mark.parametrize("version", ["26.16x1", "26.0x256", "26.99x1"])
    def test_field_overflow_rejected(self, version: str) -> None:
        # The head chunk holds the minor in 4 bits and the build in 8: these
        # used to wrap to 26.0x1, 26.0x0 and 26.3x1.
        with pytest.raises(ValueError):
            py_aep.new(version)

    @pytest.mark.parametrize("version", [26, None, "26.0", " 26.0x67"])
    def test_malformed_rejected(self, version: object) -> None:
        with pytest.raises((TypeError, ValueError)):
            py_aep.new(version)  # type: ignore[arg-type]

    @pytest.mark.parametrize("version", ["21.0x1", "26.16x3", "300.0x1"])
    def test_setter_rejects_without_mutation(self, version: str) -> None:
        app = py_aep.new()
        before = project_bytes(app.project)
        with pytest.raises(ValueError):
            app.version = version
        assert project_bytes(app.project) == before
        assert app.version == "26.0x67"

    @pytest.mark.parametrize(
        ("source", "target"),
        # AE 2026 opened each of these relabelled projects unchanged.
        [
            ("15.1x2", "16.0x1"),
            ("16.0x1", "15.1x2"),
            ("17.0x1", "18.0x1"),
            ("18.0x1", "22.6x60"),
            ("22.6x60", "18.0x1"),
            ("23.0x1", "26.0x67"),
            ("26.0x67", "23.0x1"),
        ],
    )
    def test_relabel_within_a_layout(self, source: str, target: str) -> None:
        app = py_aep.new(source)
        app.version = target
        assert app.version == target

    @pytest.mark.parametrize(
        ("source", "target"),
        # AE 2026: "chunk in file too big" (26 as 22), "file is damaged" or no
        # answer (22 as 23), no answer (16 as 22).
        [
            ("26.0x67", "22.6x60"),
            ("22.6x60", "23.0x1"),
            ("16.0x1", "22.6x60"),
            ("26.0x67", "15.1x2"),
            ("18.0x1", "26.0x67"),
        ],
    )
    def test_relabel_across_a_layout_rejected(self, source: str, target: str) -> None:
        app = py_aep.new(source)
        before = project_bytes(app.project)
        with pytest.raises(ValueError):
            app.version = target
        assert project_bytes(app.project) == before

    @pytest.mark.parametrize("build", [256, -1, "67"])
    def test_build_number_range(self, build: object) -> None:
        app = py_aep.new()
        with pytest.raises((TypeError, ValueError)):
            app.build_number = build  # type: ignore[assignment]
        assert app.build_number == 67


class TestWorkingSpaceNone:
    def test_none_round_trips(self, tmp_path: Path) -> None:
        # AE 2026 accepts workingSpace = "None": `PwCs` keeps `{}` and `cpid`
        # is all 0xFF, as in a new project.
        app = py_aep.new()
        before = project_bytes(app.project)
        app.project.working_space = app.project.working_space
        assert app.project.working_space == "None"
        assert project_bytes(app.project) == before

    def test_none_after_a_profile(self, tmp_path: Path) -> None:
        app = py_aep.new()
        cpid = app.project._cpid.data
        utf8 = app.project._ws_utf8
        app.project._ws_utf8 = app.project._rewrite_color_profile(
            "PwCs", '{"baseColorProfile":{"colorProfileName":"X"}}'
        )
        app.project._cpid.data = b"\x01" * 16
        app.project.working_space = "None"
        assert app.project.working_space == "None"
        assert app.project._cpid.data == cpid == b"\xff" * 16
        assert app.project._ws_utf8 is not None and app.project._ws_utf8.value == "{}"
        assert utf8 is None
        path = tmp_path / "ws.aep"
        app.project.save(path)
        assert parse(path).project.working_space == "None"


class TestSaveTempFile:
    def test_unrelated_tmp_file_survives(self, tmp_path: Path) -> None:
        keep = tmp_path / "out.aep.tmp"
        keep.write_bytes(b"user data")
        py_aep.new().project.save(tmp_path / "out.aep")
        assert keep.read_bytes() == b"user data"
        assert parse(tmp_path / "out.aep").version == "26.0x67"
        assert sorted(p.name for p in tmp_path.iterdir()) == ["out.aep", "out.aep.tmp"]
