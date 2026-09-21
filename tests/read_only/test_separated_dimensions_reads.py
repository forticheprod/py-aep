"""Reads on a dimension-separated Position must match ExtendScript.

While `dimensionsSeparated` is on, AE drives the layer from the X / Y / Z
followers and resets the leader's own stored value to the comp-centre
default, so reading that value reports the default rather than the position.
Expressibility moves the same way: the leader refuses an expression and the
followers accept one.

Every expectation is taken from the matching `.json` ExtendScript export.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import get_layer_from_json, load_expected, parse_project

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "property"


def _expected_transform(sample: str) -> dict[str, dict]:
    """`{matchName: property dict}` for the first layer's transform group."""
    layer = get_layer_from_json(load_expected(SAMPLES_DIR, sample))
    for group in layer.get("properties") or []:
        if group.get("matchName") == "ADBE Transform Group":
            return {
                child["matchName"]: child for child in group.get("properties") or []
            }
    raise AssertionError(f"no transform group in {sample}.json")


@pytest.mark.parametrize(
    "sample",
    ["transform_unseparated", "transform_separated", "keyframe_separated_dimensions"],
)
def test_position_reads_match_extendscript(sample: str) -> None:
    expected = _expected_transform(sample)
    layer = parse_project(SAMPLES_DIR / f"{sample}.aep").compositions[0].layers[0]

    for match_name in (
        "ADBE Position",
        "ADBE Position_0",
        "ADBE Position_1",
        "ADBE Position_2",
    ):
        prop = layer.transform[match_name]
        wanted = expected[match_name]
        assert prop.value == pytest.approx(wanted["value"]), match_name
        assert prop.can_set_expression is wanted["canSetExpression"], match_name


def test_separated_leader_composes_from_its_followers() -> None:
    """The stored leader value is the comp centre (100, 100 on this 200x200
    comp); AE reports the followers' composite, [0, 200, 0]."""
    comp = parse_project(
        SAMPLES_DIR / "keyframe_separated_dimensions.aep"
    ).compositions[0]
    position = comp.layers[0].transform["ADBE Position"]
    assert position.dimensions_separated is True

    stored = position._read_cdat_raw()
    assert stored == pytest.approx([comp.width / 2, comp.height / 2, 0.0])
    assert position.value == pytest.approx([0.0, 200.0, 0.0])


def test_expressibility_moves_to_the_followers_when_separated() -> None:
    layer = (
        parse_project(SAMPLES_DIR / "transform_separated.aep").compositions[0].layers[0]
    )
    position = layer.transform["ADBE Position"]
    assert position.dimensions_separated is True

    assert position.can_set_expression is False
    assert layer.transform["ADBE Position_0"].can_set_expression is True
    assert layer.transform["ADBE Position_1"].can_set_expression is True
    # Z stays unexpressionable on a 2D layer.
    assert layer.transform["ADBE Position_2"].can_set_expression is False


def test_unseparated_keeps_expressibility_on_the_leader() -> None:
    layer = (
        parse_project(SAMPLES_DIR / "transform_unseparated.aep")
        .compositions[0]
        .layers[0]
    )
    assert layer.transform["ADBE Position"].can_set_expression is True
    for dimension in range(3):
        follower = layer.transform[f"ADBE Position_{dimension}"]
        assert follower.can_set_expression is False
