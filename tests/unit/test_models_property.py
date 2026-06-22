"""Tests for Property model parsing with strengthened assertions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from py_aep.binary.chunk import ListChunk
from py_aep.binary.property_chunks import TdmnChunk, TdsnChunk
from py_aep.enums import (
    PropertyControlType,
)
from py_aep.parsers.property import parse_property_group

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "property"
BUGS_DIR = Path(__file__).parent.parent.parent / "samples" / "bugs"
LAYER_SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"
LAYER_SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"
VERSIONS_DIR = Path(__file__).parent.parent.parent / "samples" / "versions"
PROPERTY_SAMPLES_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "property"
)


class TestResolveEffectValue:
    """Tests for _resolve_effect_value pure helper."""

    @pytest.mark.parametrize(
        ("param_def", "control_type", "expected"),
        [
            pytest.param(
                {"property_control_type": PropertyControlType.ENUM, "default_value": 0},
                PropertyControlType.ENUM,
                (1, 1),
                id="enum_default_0_becomes_1",
            ),
            pytest.param(
                {"property_control_type": PropertyControlType.ENUM, "default_value": 2},
                PropertyControlType.ENUM,
                (3, 3),
                id="enum_default_2_becomes_3",
            ),
            pytest.param(
                {
                    "property_control_type": PropertyControlType.ENUM,
                    "default_value": 0,
                    "last_value": 5,
                },
                PropertyControlType.ENUM,
                (5, 5),
                id="enum_last_value_takes_precedence",
            ),
            pytest.param(
                {
                    "property_control_type": PropertyControlType.BOOLEAN,
                    "default_value": 1,
                },
                PropertyControlType.BOOLEAN,
                (1, 1),
                id="boolean_default_value",
            ),
            pytest.param(
                {
                    "property_control_type": PropertyControlType.BOOLEAN,
                    "last_value": 0,
                },
                PropertyControlType.BOOLEAN,
                (0, 0),
                id="boolean_falls_back_to_last_value",
            ),
            pytest.param(
                {
                    "property_control_type": PropertyControlType.SCALAR,
                    "last_value": 42.0,
                    "default_value": 10.0,
                },
                PropertyControlType.SCALAR,
                (42.0, 10.0),
                id="general_last_value_preferred",
            ),
            pytest.param(
                {
                    "property_control_type": PropertyControlType.SCALAR,
                    "default_value": 10.0,
                },
                PropertyControlType.SCALAR,
                (10.0, 10.0),
                id="general_falls_back_to_default",
            ),
            pytest.param(
                {"property_control_type": PropertyControlType.SCALAR},
                PropertyControlType.SCALAR,
                (None, None),
                id="general_no_values_returns_none",
            ),
            pytest.param(
                {
                    "property_control_type": PropertyControlType.SCALAR,
                    "last_value": 7.0,
                },
                PropertyControlType.SCALAR,
                (7.0, 7.0),
                id="general_default_falls_back_to_value",
            ),
        ],
    )
    def test_resolve_effect_value(
        self,
        param_def: dict[str, Any],
        control_type: PropertyControlType,
        expected: tuple[Any, Any],
    ) -> None:
        from py_aep.parsers.effect import _resolve_effect_value

        result = _resolve_effect_value("TEST-0001", param_def, control_type)
        assert result == expected


class TestTdsnWithoutUtf8:
    """A tdsn missing its Utf8 child degrades to the auto-name.

    Regression: `TdsnChunk.utf8` raised ValueError, escaping
    `parse_property_group`'s ChunkNotFoundError handler and failing
    the whole parse instead of falling back to the auto-name.
    """

    def test_property_group_falls_back_to_auto_name(self) -> None:
        tdgp = ListChunk(
            list_type="tdgp",
            chunks=[TdsnChunk(chunks=[])],  # no Utf8 child
        )
        group = parse_property_group(
            tdgp_chunk=tdgp,
            group_match_name="ADBE Transform Group",
            property_depth=1,
            effect_param_defs={},
            composition=cast(Any, None),
            tdmn=TdmnChunk(value="ADBE Transform Group"),
        )
        assert group._name_utf8 is None
        assert group.name == "Transform"
