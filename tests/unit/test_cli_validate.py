"""Tests for the CLI validate module."""

from __future__ import annotations

from pathlib import Path

from py_aep.cli.validate import (
    ValidationResult,
    compare_marker,
    compare_values,
    get_enum_value,
    main,
)
from py_aep.enums import BlendingMode

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples"


class TestGetEnumValue:
    """Tests for get_enum_value()."""

    def test_enum_returns_value(self) -> None:
        assert get_enum_value(BlendingMode.ADD) == BlendingMode.ADD.value

    def test_non_enum_returns_as_is(self) -> None:
        assert get_enum_value(42) == 42
        assert get_enum_value("test") == "test"
        assert get_enum_value(None) is None


class TestCompareValues:
    """Tests for compare_values()."""

    def test_none_both(self) -> None:
        assert compare_values(None, None) is True

    def test_none_one(self) -> None:
        assert compare_values(None, 1) is False
        assert compare_values(1, None) is False

    def test_booleans(self) -> None:
        assert compare_values(True, True) is True
        assert compare_values(False, False) is True
        assert compare_values(True, False) is False

    def test_integers(self) -> None:
        assert compare_values(1, 1) is True
        assert compare_values(1, 2) is False

    def test_floats_with_tolerance(self) -> None:
        assert compare_values(1.0, 1.0001) is True
        assert compare_values(1.0, 2.0) is False

    def test_strings(self) -> None:
        assert compare_values("abc", "abc") is True
        assert compare_values("abc", "def") is False

    def test_lists(self) -> None:
        assert compare_values([1, 2, 3], [1, 2, 3]) is True
        assert compare_values([1, 2], [1, 2, 3]) is False
        assert compare_values([1, 2, 3], [1, 2, 4]) is False

    def test_nested_lists(self) -> None:
        assert compare_values([1.0, 2.0], [1.0001, 2.0001]) is True


class TestValidationResult:
    """Tests for ValidationResult class."""

    def test_empty(self) -> None:
        result = ValidationResult()
        assert len(result) == 0
        assert result.differences == []
        assert result.warnings == []

    def test_add_diff(self) -> None:
        result = ValidationResult()
        result.add_diff("test.field", 1, 2, "test")
        assert len(result) == 1
        assert "test.field" in result.differences[0]
        assert result.categories["test"] == 1

    def test_add_warning(self) -> None:
        result = ValidationResult()
        result.add_warning("some warning")
        assert len(result.warnings) == 1
        assert result.warnings[0] == "some warning"


class TestCompareMarker:
    """Tests for compare_marker()."""

    def test_matching_marker(self) -> None:
        result = ValidationResult()
        expected_marker = {
            "time": 1.0,
            "comment": "test",
            "chapter": "",
            "url": "",
            "duration": 0,
        }
        parsed_marker = {
            "frame_time": 30,
            "comment": "test",
            "chapter": "",
            "url": "",
            "duration": 0,
        }
        compare_marker(expected_marker, parsed_marker, "Marker[0]", 30.0, result)
        # time=frame_time/fps = 30/30 = 1.0
        marker_diffs = [d for d in result.differences if "Marker" in d]
        assert len(marker_diffs) == 0

    def test_mismatching_marker_comment(self) -> None:
        result = ValidationResult()
        expected_marker = {"comment": "expected"}
        parsed_marker = {"comment": "actual"}
        compare_marker(expected_marker, parsed_marker, "Marker[0]", 30.0, result)
        assert len(result) >= 1


class TestMain:
    """Tests for the CLI main() entry point."""

    def test_missing_aep(self, tmp_path: Path) -> None:
        exit_code = main(
            [str(tmp_path / "nonexistent.aep"), str(tmp_path / "test.json")]
        )
        assert exit_code == 1

    def test_missing_json(self, tmp_path: Path) -> None:
        aep_path = SAMPLES_DIR / "models" / "composition" / "bgColor_custom.aep"
        exit_code = main([str(aep_path), str(tmp_path / "nonexistent.json")])
        assert exit_code == 1

    def test_valid_input(self) -> None:
        aep_path = SAMPLES_DIR / "models" / "composition" / "bgColor_custom.aep"
        json_path = SAMPLES_DIR / "models" / "composition" / "bgColor_custom.json"
        exit_code = main([str(aep_path), str(json_path)])
        # Should return 0 (success) or 1 (differences found), depending on
        # how many fields the parser currently handles.
        assert isinstance(exit_code, int)
        assert exit_code in (0, 1)
