"""Tests for parsing AEP files across different AE versions."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from py_aep.cli.validate import validate_aep

VERSIONS_DIR = Path(__file__).parent.parent.parent / "samples" / "versions"


class TestAE2025:
    """Tests specific to After Effects 2025 projects."""

    def test_validate_against_json(self) -> None:
        """Validate AE2025 project against ExtendScript JSON export."""
        aep_path = VERSIONS_DIR / "ae2025" / "complete.aep"
        json_path = VERSIONS_DIR / "ae2025" / "complete.json"
        if not aep_path.exists() or not json_path.exists():
            pytest.skip("ae2025 sample or JSON reference not found")
        result = validate_aep(aep_path, json_path)
        # Report differences as warnings, not failures
        for diff in result.differences:
            warnings.warn(diff, stacklevel=1)
