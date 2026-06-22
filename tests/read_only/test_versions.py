"""Tests for parsing AEP files across different AE versions."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import parse_project

from py_aep import Project

VERSIONS_DIR = Path(__file__).parent.parent.parent / "samples" / "versions"


class TestVersionCompatibility:
    """Cross-version compatibility checks."""

    @pytest.mark.parametrize(
        "version",
        ["ae2018", "ae2022", "ae2023", "ae2024", "ae2025", "ae2026"],
    )
    def test_all_versions_parseable(self, version: str) -> None:
        aep_path = VERSIONS_DIR / version / "complete.aep"
        if not aep_path.exists():
            pytest.skip(f"{version} sample not found")
        project = parse_project(aep_path)
        assert isinstance(project, Project)
        assert len(project.compositions) >= 1
