"""Auto-bezier tangent / ease accessors must agree with AE for real files.

`samples/versions/ae2018/complete.aep` is the regression fixture: its stored
tangents are stale on one keyframe and zero on another, while AE's own
ExtendScript reports chord/6 for all five. Reading the chunk back verbatim
produced seven `aep-validate` differences that nothing tracked.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import pytest
from helpers import load_expected

from py_aep import parse as parse_aep
from py_aep.models.properties.property import Property

VERSIONS_DIR = Path(__file__).parent.parent.parent / "samples" / "versions"


def _keyed(comp: Any) -> Iterator[tuple[str, Property]]:
    """Every keyframed property in `comp`, paired with its layer's name."""
    for layer in comp.layers:
        for prop in layer._leaf_properties():
            if prop.keyframes:
                yield layer.name, prop


def _json_properties(document: dict) -> Iterator[tuple[str, str, dict]]:
    def walk(prop: dict, out: list[dict]) -> None:
        if prop.get("numKeys"):
            out.append(prop)
        for child in prop.get("properties") or []:
            walk(child, out)

    for item in document.get("items", []):
        for layer in item.get("layers") or []:
            found: list[dict] = []
            for group in layer.get("properties") or []:
                walk(group, found)
            for prop in found:
                yield item.get("name", ""), layer.get("name", ""), prop


@pytest.mark.parametrize("version", ["ae2018", "ae2022", "ae2023", "ae2026"])
def test_auto_bezier_accessors_match_extendscript(version: str) -> None:
    """Every auto-bezier keyframe's tangents and ease must equal what AE
    reported for the same file."""
    aep = VERSIONS_DIR / version / "complete.aep"
    expected = load_expected(VERSIONS_DIR / version, "complete")
    app = parse_aep(aep)

    parsed: dict[tuple[str, str, str], Property] = {}
    for comp in app.project.compositions:
        for layer_name, prop in _keyed(comp):
            parsed[(comp.name, layer_name, prop.match_name)] = prop

    compared = 0
    for comp_name, layer_name, json_prop in _json_properties(expected):
        key = (comp_name, layer_name, json_prop["matchName"])
        prop = parsed.get(key)
        if prop is None:
            continue
        keys = json_prop.get("keyframes") or []
        if len(keys) != len(prop.keyframes):
            continue
        for json_key, keyframe in zip(keys, prop.keyframes):
            if json_key.get("spatialAutoBezier"):
                compared += 1
                assert keyframe.in_spatial_tangent == pytest.approx(
                    json_key["inSpatialTangent"], abs=0.001
                )
                assert keyframe.out_spatial_tangent == pytest.approx(
                    json_key["outSpatialTangent"], abs=0.001
                )
            if json_key.get("temporalAutoBezier"):
                compared += 1
                for ease, json_ease in zip(
                    keyframe.in_temporal_ease, json_key["inTemporalEase"]
                ):
                    assert ease.speed == pytest.approx(json_ease["speed"], abs=0.001)
                    assert ease.influence == pytest.approx(
                        json_ease["influence"], abs=0.001
                    )
                for ease, json_ease in zip(
                    keyframe.out_temporal_ease, json_key["outTemporalEase"]
                ):
                    assert ease.speed == pytest.approx(json_ease["speed"], abs=0.001)
                    assert ease.influence == pytest.approx(
                        json_ease["influence"], abs=0.001
                    )

    assert compared, f"{version} exercised no auto-bezier keyframe"
