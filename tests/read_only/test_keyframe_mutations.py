"""Tests for keyframe mutation: add_key, remove_key, set_value(s)_at_time(s),
Shape creation from scratch, and numeric keyframe value persistence.

Mutation tests parse a fresh (uncached) copy so changes do not leak between
tests, and assert results survive a save / re-parse round-trip.
"""

from __future__ import annotations

from pathlib import Path

from py_aep import Application
from py_aep import parse as parse_aep
from py_aep.models.properties.property import Property

SAMPLES = Path(__file__).parent.parent.parent / "samples" / "models" / "property"
SAMPLES_ROOT = Path(__file__).parent.parent.parent / "samples"


def _fresh(name: str) -> Application:
    return parse_aep(str(SAMPLES / name))


def _prop(
    app: Application, match_name: str, *, comp: int = 0, layer: int = 0
) -> Property:
    lay = app.project.compositions[comp].layers[layer]
    return next(p for p in lay.transform if p.match_name == match_name)


class TestNearestKeyIndex:
    def test_returns_temporally_nearest(self) -> None:
        # Regression: nearest_key_index compared frame_time (frames) against
        # the time argument (seconds); at any fps != 1 querying near a late
        # keyframe wrongly returned the first keyframe. Querying at each
        # keyframe's own time must return that keyframe's index.
        app = _fresh("keyframe_HOLD.aep")
        op = _prop(app, "ADBE Opacity")
        assert len(op.keyframes) >= 2
        for i, kf in enumerate(op.keyframes):
            assert op.nearest_key_index(kf.time) == i
