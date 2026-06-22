"""Tests for Layer model parsing."""

from __future__ import annotations

from pathlib import Path

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"
BUGS_DIR = Path(__file__).parent.parent.parent / "samples" / "bugs"
VERSIONS_DIR = Path(__file__).parent.parent.parent / "samples" / "versions"


class TestAutoName:
    """Tests for auto_name helper."""

    def test_trailing_number(self) -> None:
        from py_aep.models.naming import auto_name

        assert auto_name("Light 1", set()) == "Light 1"
        assert auto_name("Layer 99", set()) == "Layer 1"
        assert auto_name("abc3", set()) == "abc1"

    def test_no_trailing_number(self) -> None:
        from py_aep.models.naming import auto_name

        assert auto_name("MyLayer", set()) == "MyLayer 1"
        assert auto_name("Solid", set()) == "Solid 1"
        assert auto_name("Solid", {"Solid"}) == "Solid 2"

    def test_only_number(self) -> None:
        from py_aep.models.naming import auto_name

        assert auto_name("42", set()) == "1"

    def test_skips_existing_names(self) -> None:
        from py_aep.models.naming import auto_name

        existing = {"layer1", "layer2", "layer3"}
        assert auto_name("layer1", existing) == "layer4"

    def test_skips_existing_no_trailing_number(self) -> None:
        from py_aep.models.naming import auto_name

        existing = {"Solid", "Solid 2", "Solid 3"}
        assert auto_name("Solid", existing) == "Solid 4"
        assert auto_name("Solid 1", existing) == "Solid 4"

    def test_uses_max_suffix(self) -> None:
        from py_aep.models.naming import auto_name

        existing = {"Comp 1", "Comp 4"}
        assert auto_name("Comp 1", existing) == "Comp 5"

    def test_gap_not_filled(self) -> None:
        from py_aep.models.naming import auto_name

        existing = {"Layer 1", "Layer 5"}
        assert auto_name("Layer 1", existing) == "Layer 6"
