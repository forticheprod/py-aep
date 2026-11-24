"""A stored keyframe influence above 100 percent stays readable.

AE 2026, on a project storing 104.626 on boundary and interior keys of an
Opacity property: `keyInTemporalEase` / `keyOutTemporalEase` report 104.626
as stored on every side, a resave keeps the bytes, `new KeyframeEase` and the
`influence` attribute refuse any value outside 0.1 to 100, and handing the
reported ease objects back to `setTemporalEaseAtKey` writes 100.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import parse_project_fresh

from py_aep import parse as parse_aep
from py_aep.models.properties.keyframe_ease import KeyframeEase
from py_aep.models.properties.property import Property

SAMPLES = Path(__file__).parent.parent.parent / "samples" / "models" / "property"
RAW_INFLUENCE = 1.04626


def _animated_opacity(path: Path) -> Property:
    return next(
        g
        for layer in parse_aep(path).project.compositions[0].layers
        for g in layer.transform.properties
        if g.keyframes
    )


@pytest.fixture
def over_100(tmp_path: Path) -> Property:
    """The three-key Opacity sample with 104.626 percent stored on the first
    key's out side, both sides of the middle key and the last key's in side,
    read back from disk."""
    project = parse_project_fresh(SAMPLES / "keyframe_bezier_nonzero_speed.aep")
    prop = next(
        g
        for layer in project.compositions[0].layers
        for g in layer.transform.properties
        if g.keyframes
    )
    first, middle, last = prop.keyframes
    first._ldat_item.kf_data.out_influence[0] = RAW_INFLUENCE
    middle._ldat_item.kf_data.in_influence[0] = RAW_INFLUENCE
    middle._ldat_item.kf_data.out_influence[0] = RAW_INFLUENCE
    last._ldat_item.kf_data.in_influence[0] = RAW_INFLUENCE
    out = tmp_path / "over_100.aep"
    project.save(out)
    return _animated_opacity(out)


def test_reads_as_stored_on_every_side(over_100: Property) -> None:
    first, middle, last = over_100.keyframes
    assert first.out_temporal_ease[0].influence == pytest.approx(104.626)
    assert middle.in_temporal_ease[0].influence == pytest.approx(104.626)
    assert middle.out_temporal_ease[0].influence == pytest.approx(104.626)
    assert last.in_temporal_ease[0].influence == pytest.approx(104.626)
    # The untouched boundary sides still read their stored 33.
    assert first.in_temporal_ease[0].influence == pytest.approx(33.0)
    assert last.out_temporal_ease[0].influence == pytest.approx(33.0)


def test_writing_a_read_ease_back_clamps_to_100(over_100: Property) -> None:
    middle = over_100.keyframes[1]
    middle.in_temporal_ease = middle.in_temporal_ease
    assert middle.in_temporal_ease[0].influence == pytest.approx(100.0)
    assert middle.in_temporal_ease[0].speed == pytest.approx(15.0)
    assert middle.out_temporal_ease[0].influence == pytest.approx(104.626)


def test_user_values_keep_the_range() -> None:
    with pytest.raises(ValueError):
        KeyframeEase(speed=0.0, influence=104.626)
    ease = KeyframeEase(speed=0.0, influence=50.0)
    with pytest.raises(ValueError):
        ease.influence = 104.626


def test_add_key_beside_a_stored_over_100(over_100: Property) -> None:
    over_100.add_key(1.5)
    influences = [
        ease.influence
        for key in over_100.keyframes
        for ease in (*key.in_temporal_ease, *key.out_temporal_ease)
    ]
    assert len(influences) == 8
    assert max(influences) <= 104.626 + 1e-9
