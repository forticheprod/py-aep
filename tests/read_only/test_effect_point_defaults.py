"""Effect point defaults, read from PF_PointDef's dephault (AE 2026).

`effect_point_defaults.aep` holds three 800x600 comps:

- `edited_above` / `edited_below`: a Gradient Ramp whose End of Ramp and
  Ramp Shape were edited on a 400x300 solid, and an untouched one on a
  400x600 solid, in both stacking orders - the later instance of the effect
  borrows the other's definitions, whose last values are the other's.
- `points`: an untouched Lens Flare on a 200x100 solid (Flare Center 40/40
  percent) and 3D Point Control on a 300x200 solid (50/50/0).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from conftest import get_comp, get_comp_from_json_by_name, load_expected, parse_project

from py_aep.enums import PropertyControlType
from py_aep.models.properties.property import Property

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "property"
SAMPLE = "effect_point_defaults"

_CASES = [
    ("edited_above", "ramp edited"),
    ("edited_above", "ramp untouched"),
    ("edited_below", "ramp edited"),
    ("edited_below", "ramp untouched"),
    ("points", "flare untouched"),
    ("points", "point3d untouched"),
]


def _effect_props(comp_name: str, layer_name: str) -> list[Property]:
    comp = get_comp(parse_project(SAMPLES_DIR / f"{SAMPLE}.aep"), comp_name)
    layer = next(ly for ly in comp.layers if ly.name == layer_name)
    assert layer.effects is not None
    return [p for p in layer.effects[0].properties if isinstance(p, Property)]


def _expected_props(comp_name: str, layer_name: str) -> dict[str, dict[str, Any]]:
    comp = get_comp_from_json_by_name(load_expected(SAMPLES_DIR, SAMPLE), comp_name)
    layer = next(ly for ly in comp["layers"] if ly["name"] == layer_name)
    parade = next(
        p for p in layer["properties"] if p["matchName"] == "ADBE Effect Parade"
    )
    return {p["matchName"]: p for p in parade["properties"][0]["properties"]}


@pytest.mark.parametrize(("comp_name", "layer_name"), _CASES)
def test_points_and_popups_match_json(comp_name: str, layer_name: str) -> None:
    expected = _expected_props(comp_name, layer_name)
    checked = 0
    for prop in _effect_props(comp_name, layer_name):
        if prop._property_control_type not in (
            PropertyControlType.TWO_D,
            PropertyControlType.THREE_D,
            PropertyControlType.ENUM,
        ):
            continue
        prop_json = expected[prop.match_name]
        assert prop.value == pytest.approx(prop_json["value"]), prop.name
        assert prop.is_modified == prop_json["isModified"], prop.name
        checked += 1
    assert checked


@pytest.mark.parametrize(
    ("comp_name", "layer_name", "match_name", "default"),
    [
        # 50/100 percent of the edited ramp's own 400x300 layer, not the
        # untouched one's.
        ("edited_above", "ramp edited", "ADBE Ramp-0003", [200.0, 300.0]),
        ("edited_below", "ramp edited", "ADBE Ramp-0003", [200.0, 300.0]),
        ("edited_above", "ramp untouched", "ADBE Ramp-0003", [200.0, 600.0]),
        # 40 percent exactly: the last value read 39.9994.
        ("points", "flare untouched", "ADBE Lens Flare-0001", [80.0, 40.0]),
        ("points", "point3d untouched", "ADBE Point3D Control-0001", [150, 100, 0]),
    ],
)
def test_point_default_is_a_percentage_of_the_layer(
    comp_name: str, layer_name: str, match_name: str, default: list[float]
) -> None:
    prop = next(
        p for p in _effect_props(comp_name, layer_name) if p.match_name == match_name
    )
    assert prop.default_value == pytest.approx(default, abs=1e-9)


@pytest.mark.parametrize(
    ("layer_name", "center"),
    [("normal", [100.0, 50.0]), ("adjustment", [960.0, 540.0])],
)
def test_adjustment_layer_point_is_a_percentage_of_the_comp(
    layer_name: str, center: list[float]
) -> None:
    """`effect_point_adjustment.aep`: a Transform effect whose Anchor Point
    and Position AE 2026 set to 30,40 and 10,20 by script on two 200x100
    solids of a 1920x1080 comp, one of them an adjustment layer. AE stores
    the adjustment layer's points against the comp, and centres their
    defaults on it."""
    comp = get_comp(
        parse_project(SAMPLES_DIR / "effect_point_adjustment.aep"), "coverage"
    )
    layer = next(ly for ly in comp.layers if ly.name == layer_name)
    assert layer.effects is not None
    transform = layer.effects.property("ADBE Geometry2")
    for match_name, value in (
        ("ADBE Geometry2-0001", [30.0, 40.0]),
        ("ADBE Geometry2-0002", [10.0, 20.0]),
    ):
        prop = transform.property(match_name)
        assert prop.value == pytest.approx(value), match_name
        assert prop.default_value == pytest.approx(center), match_name
