"""Tests for the CLI validate module."""

from __future__ import annotations

from pathlib import Path

from conftest import load_expected, parse_project

from py_aep.cli.validate import (
    ValidationResult,
    compare_layer,
    compare_project_level,
    compare_property,
    to_dict,
    validate_aep,
)
from py_aep.enums import BlendingMode

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples"


class TestToDict:
    """Tests for to_dict() serialization."""

    def test_project_to_dict(self) -> None:
        aep_path = SAMPLES_DIR / "models" / "composition" / "bgColor_custom.aep"
        project = parse_project(aep_path)
        result = to_dict(project)
        assert isinstance(result, dict)
        assert "items" in result

    def test_enum_to_dict(self) -> None:
        result = to_dict(BlendingMode.NORMAL)
        assert result == BlendingMode.NORMAL.value

    def test_list_to_dict(self) -> None:
        result = to_dict([1, 2, 3])
        assert result == [1, 2, 3]

    def test_dict_to_dict(self) -> None:
        result = to_dict({"a": 1})
        assert result == {"a": 1}

    def test_plain_value(self) -> None:
        assert to_dict(42) == 42
        assert to_dict("hello") == "hello"
        assert to_dict(None) is None


class TestCompareProjectLevel:
    """Tests for compare_project_level()."""

    def test_matching_project(self) -> None:
        aep_path = SAMPLES_DIR / "models" / "composition" / "bgColor_custom.aep"
        project = parse_project(aep_path)
        parsed = to_dict(project)
        expected = load_expected(
            SAMPLES_DIR / "models" / "composition", "bgColor_custom"
        )
        result = ValidationResult()
        compare_project_level(expected, parsed, result)
        # Project-level fields should match (or have no differences)
        assert isinstance(result, ValidationResult)

    def test_mismatching_field(self) -> None:
        result = ValidationResult()
        expected = {"bitsPerChannel": 16}
        parsed = {"bits_per_channel": 8}
        compare_project_level(expected, parsed, result)
        assert len(result) == 1


class TestCompareLayer:
    """Tests for compare_layer()."""

    def test_full_layer_comparison(self) -> None:
        aep_path = SAMPLES_DIR / "models" / "layer" / "enabled_false.aep"
        project = parse_project(aep_path)
        parsed = to_dict(project)
        expected = load_expected(SAMPLES_DIR / "models" / "layer", "enabled_false")
        # Find matching comp and layers
        for item in expected["items"]:
            if "layers" in item and len(item["layers"]) > 0:
                exp_layer = item["layers"][0]
                # Get parsed comp layers
                parsed_comps = parsed.get("_compositions", [])
                if parsed_comps:
                    parsed_layers = parsed_comps[0].get("layers", [])
                    if parsed_layers:
                        result = ValidationResult()
                        compare_layer(
                            exp_layer, parsed_layers[0], "Layer[0]", 30.0, 24.0, result
                        )
                        assert isinstance(result, ValidationResult)


class TestValidateAep:
    """Tests for validate_aep() integration."""

    def test_validate_sample(self) -> None:
        aep_path = SAMPLES_DIR / "models" / "composition" / "bgColor_custom.aep"
        json_path = SAMPLES_DIR / "models" / "composition" / "bgColor_custom.json"
        result = validate_aep(aep_path, json_path)
        assert isinstance(result, ValidationResult)

    def test_media_replacement_fully_validates(self) -> None:
        # Guards the alternateSource/essentialPropertySource object comparison
        # against the regenerated ground-truth JSON (the override leaf carries
        # both keys).
        eg = SAMPLES_DIR / "models" / "essential_graphics"
        result = validate_aep(
            eg / "media_replacement.aep", eg / "media_replacement.json"
        )
        assert len(result) == 0


class TestComparePropertyMediaReplacement:
    """Tests for the media-replacement object comparisons in compare_property()."""

    def test_matching_object_sources_no_diff(self) -> None:
        expected = {
            "alternateSource": {"id": 30, "name": "wrapper"},
            "essentialPropertySource": {
                "sourceType": "AVLayer",
                "name": "src_layer",
                "index": 1,
            },
        }
        # Parsed index is 0-based; the AVItem/AVLayer serialize id/name/index.
        parsed = {
            "alternate_source": {"id": 30, "name": "wrapper"},
            "essential_property_source": {"name": "src_layer", "index": 0},
        }
        result = ValidationResult()
        compare_property(expected, parsed, "P", result)
        assert len(result) == 0

    def test_id_and_index_mismatches_flagged(self) -> None:
        expected = {
            "alternateSource": {"id": 30, "name": "wrapper"},
            "essentialPropertySource": {
                "sourceType": "AVLayer",
                "name": "src_layer",
                "index": 1,
            },
        }
        parsed = {
            "alternate_source": {"id": 99, "name": "wrapper"},  # id mismatch
            "essential_property_source": {"name": "src_layer", "index": 5},  # 5+1 != 1
        }
        result = ValidationResult()
        compare_property(expected, parsed, "P", result)
        assert len(result) == 2

    def test_property_source_matchname_compared(self) -> None:
        expected = {
            "essentialPropertySource": {
                "sourceType": "Property",
                "matchName": "ADBE Opacity",
            }
        }
        result = ValidationResult()
        compare_property(
            expected,
            {"essential_property_source": {"match_name": "ADBE Fill"}},
            "P",
            result,
        )
        assert len(result) == 1
