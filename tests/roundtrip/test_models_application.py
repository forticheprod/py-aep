"""Tests for Application model."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep import parse as parse_aep

SAMPLE = (
    Path(__file__).resolve().parent.parent.parent
    / "samples"
    / "versions"
    / "ae2025"
    / "complete.aep"
)


class TestBuildName:
    """build_name is an alias for version."""

    def test_build_name_equals_version(self) -> None:
        app = parse_aep(SAMPLE)
        assert app.build_name == app.version

    def test_set_build_name_updates_version(self) -> None:
        app = parse_aep(SAMPLE)
        app.build_name = "25.0x100"
        assert app.version == "25.0x100"

    def test_set_version_updates_build_name(self) -> None:
        app = parse_aep(SAMPLE)
        app.version = "24.3x50"
        assert app.build_name == "24.3x50"


class TestVersionUpdatesFormatGate:
    """Setting version also updates the file-format open gate."""

    def test_version_setter_syncs_format_version(self) -> None:
        app = parse_aep(SAMPLE)  # AE 2025 -> format 96.9
        head = app._head
        assert (head.file_format_version, head._format_subversion) == (96, 9)
        app.version = "24.0x1"
        assert (head.file_format_version, head._format_subversion) == (95, 6)
        app.version = "26.0x67"
        assert (head.file_format_version, head._format_subversion) == (97, 2)

    def test_build_name_setter_syncs_format_version(self) -> None:
        app = parse_aep(SAMPLE)
        app.build_name = "23.0x1"
        head = app._head
        assert (head.file_format_version, head._format_subversion) == (94, 9)

    def test_unknown_release_rejected(self) -> None:
        # No After Effects release 20 or 27 to take a stamp from; a derived
        # one makes AE 2026 misread or reject the file.
        app = parse_aep(SAMPLE)
        for version in ("20.0x1", "27.0x1"):
            with pytest.raises(ValueError):
                app.version = version
        head = app._head
        assert (head.file_format_version, head._format_subversion) == (96, 9)

    def test_relabel_across_the_layer_record_change_rejected(self) -> None:
        # AE 2026 refuses an AE 2026 project relabelled 22 ("chunk in file
        # too big"): AE 23 lengthened the layer record.
        app = parse_aep(SAMPLE)
        with pytest.raises(ValueError):
            app.version = "22.0x1"
        assert app.version == "25.6x101"


class TestRoundtripBuildName:
    """Roundtrip tests for build_name (alias for version)."""

    def test_roundtrip_build_name(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLE)
        original = app.build_name

        app.build_name = "24.1x42"
        assert app.build_name == "24.1x42"

        out = tmp_path / "modified.aep"
        app.project.save(out)
        app2 = parse_aep(out)

        assert app2.build_name == "24.1x42"
        assert app2.version == "24.1x42"
        assert app2.build_name != original
