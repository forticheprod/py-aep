"""Tests for Application model."""

from __future__ import annotations

from pathlib import Path

from py_aep import parse as parse_aep

SAMPLE = (
    Path(__file__).resolve().parent.parent
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


class TestRoundtripBuildName:
    """Roundtrip tests for build_name (alias for version)."""

    def test_roundtrip_build_name(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLE)
        original = app.build_name

        app.build_name = "20.1x42"
        assert app.build_name == "20.1x42"

        out = tmp_path / "modified.aep"
        app.project.save(out)
        app2 = parse_aep(out)

        assert app2.build_name == "20.1x42"
        assert app2.version == "20.1x42"
        assert app2.build_name != original
