"""`Property.value_at_time` on the value kinds AE blends as one quantity.

Ground truth is the per-frame `valueAtTime` export of two AE 2026 probe
projects (`scripts/jsx/export_value_at_time.jsx`):

- `property_path_orientation_pin` - a mask path, a shape-layer path, an
  Orientation and a puppet pin, deliberately on layers SMALLER than the
  composition so a layer-vs-comp normalization error shows up.
- `property_path_orientation_ease` - the same kinds under asymmetric and
  mixed LINEAR/BEZIER eases, which pin down the progress curve.
- `property_vat_edge_cases` - path keyframe pairs holding different vertex
  counts, and Orientation eases carrying a non-zero speed.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from helpers import get_comp, load_expected, parse_project

from py_aep.models.properties.property import Property
from py_aep.models.properties.shape import Shape
from py_aep.resolvers.interpolation import (
    _subdivision_cuts,
    euler_to_quaternion,
    interpolate_shapes,
    slerp_orientation,
)

if TYPE_CHECKING:
    from py_aep.models.layers.layer import Layer

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "property"
VAT_DIR = SAMPLES_DIR / "value_at_time"

# Path vertices are stored as float32, so a blend of two of them cannot be
# closer than about 1e-5 of AE's double. An effect point additionally
# carries AE's own arc-length reparameterisation noise (see
# /limitations), which is a few 1e-4 on the measured fixture.
_TOLERANCE = {
    "ADBE Mask Shape": 1e-4,
    "ADBE Vector Shape": 1e-4,
    "ADBE Orientation": 1e-8,
    "ADBE FreePin3 PosPin Position": 1e-3,
    "ADBE Opacity": 1e-9,
}


def _find(layer: Layer, match_name: str) -> Property:
    """The single property under `layer` with this match name."""
    found = [p for p in layer._leaf_properties() if p.match_name == match_name]
    assert len(found) == 1, f"{match_name}: expected 1 match, got {len(found)}"
    return found[0]


def _flatten(value: object) -> list[float]:
    """Every number in a value, in a stable order."""
    if isinstance(value, Shape):
        numbers: list[float] = []
        for points in (value.vertices, value.in_tangents, value.out_tangents):
            for point in points:
                numbers.extend(point)
        return numbers
    if isinstance(value, dict):
        numbers = []
        for key in ("vertices", "inTangents", "outTangents"):
            for point in value[key]:
                numbers.extend(point)
        return numbers
    if isinstance(value, list):
        return [float(v) for v in value]
    assert isinstance(value, (int, float))
    return [float(value)]


def _assert_same_rotation(
    actual: list[float],
    expected: list[float],
    tolerance: float,
    layer_name: str,
    time: float,
) -> None:
    """Compare two Orientations as rotations, not as angle triples.

    At a Y of +/-90 degrees X and Z turn about the same axis, so only
    their sum is recoverable and the split between them is arbitrary. AE
    is not even self-consistent there: `sp_one_side` reads
    [37.5, 90, 37.5] one frame and [0, 90, 75] the next, the same
    rotation written two ways. Comparing the rotation itself is the
    assertion that means something; the angles are compared too wherever
    the chart is well conditioned.
    """
    q_actual = euler_to_quaternion(actual)
    q_expected = euler_to_quaternion(expected)
    dot = min(1.0, abs(sum(a * b for a, b in zip(q_actual, q_expected))))
    between = math.degrees(2.0 * math.acos(dot))
    assert between <= max(tolerance, 1e-3), (
        f"{layer_name} t={time}: {actual} is {between} degrees from {expected}"
    )
    if abs(abs(expected[1] % 360.0) - 90.0) > 0.01:
        for index, (a, b) in enumerate(zip(actual, expected)):
            assert abs(a - b) <= tolerance, (
                f"{layer_name} t={time} [{index}]: {a} != {b}"
            )


def _cases() -> list[tuple[str, str, str, str]]:
    """(base name, comp name, layer name, match name) per exported property."""
    out: list[tuple[str, str, str, str]] = []
    for base in (
        "property_path_orientation_pin",
        "property_path_orientation_ease",
        "property_vat_edge_cases",
    ):
        data = load_expected(VAT_DIR, f"{base}_value_at_time")
        for comp in data["comps"]:
            for layer in comp["layers"]:
                for prop in layer["properties"]:
                    out.append((base, comp["name"], layer["name"], prop["matchName"]))
    return out


def _expected_frames(
    base: str, comp_name: str, layer_name: str, match_name: str
) -> list[dict]:
    """The exported frames for one property, or fail loudly.

    Looked up rather than scanned for: a scan that falls off the end
    silently passes the case instead of reporting the missing fixture.
    """
    data = load_expected(VAT_DIR, f"{base}_value_at_time")
    comp_data = next(c for c in data["comps"] if c["name"] == comp_name)
    layers = [ly for ly in comp_data["layers"] if ly["name"] == layer_name]
    assert len(layers) == 1, (
        f"{base}/{comp_name}: expected 1 layer named {layer_name}, got {len(layers)}"
    )
    props = [p for p in layers[0]["properties"] if p["matchName"] == match_name]
    assert len(props) == 1, (
        f"{base}/{comp_name}/{layer_name}: expected 1 {match_name}, got {len(props)}"
    )
    frames: list[dict] = props[0]["frames"]
    assert frames, f"{base}/{comp_name}/{layer_name}/{match_name}: no frames exported"
    return frames


@pytest.mark.parametrize(("base", "comp_name", "layer_name", "match_name"), _cases())
def test_matches_extendscript(
    base: str, comp_name: str, layer_name: str, match_name: str
) -> None:
    frames = _expected_frames(base, comp_name, layer_name, match_name)
    project = parse_project(SAMPLES_DIR / f"{base}.aep")
    comp = get_comp(project, comp_name)
    matches = [layer for layer in comp.layers if layer.name == layer_name]
    assert len(matches) == 1, (
        f"{comp_name}: expected 1 layer named {layer_name}, got {len(matches)}"
    )
    prop = _find(matches[0], match_name)
    tolerance = _TOLERANCE[match_name]

    for frame in frames:
        got = prop.value_at_time(frame["time"])
        expected = _flatten(frame["value"])
        actual = _flatten(got)
        assert len(actual) == len(expected), (
            f"{match_name} t={frame['time']}: "
            f"{len(actual)} values, expected {len(expected)}"
        )
        if match_name == "ADBE Orientation":
            _assert_same_rotation(
                actual, expected, tolerance, layer_name, frame["time"]
            )
        else:
            for index, (a, b) in enumerate(zip(actual, expected)):
                assert abs(a - b) <= tolerance, (
                    f"{layer_name}.{match_name} t={frame['time']} [{index}]: {a} != {b}"
                )
        if isinstance(frame["value"], dict):
            assert isinstance(got, Shape)
            assert got.closed == frame["value"]["closed"]


class TestValueSpaces:
    """The static read path, on the same layers-smaller-than-comp fixture."""

    @staticmethod
    def _probe_layer(name: str) -> Layer:
        project = parse_project(SAMPLES_DIR / "property_path_orientation_pin.aep")
        comp = get_comp(project, "vat_probe")
        return next(layer for layer in comp.layers if layer.name == name)

    def test_mask_shape_is_bound_to_its_layer_at_parse_time(self) -> None:
        # Reached through `_value` / `_ldat_item`, never through `.value`:
        # the binding is the parser's job, so a read must not be what
        # establishes it. `_parse_shape_shap` raises if a mask path is
        # parsed without its layer, which makes a missed parse site loud
        # rather than silently comp-scaled.
        layer = self._probe_layer("probe_solid")
        prop = _find(layer, "ADBE Mask Shape")
        assert prop._value is not None
        assert prop._value._layer is layer
        for keyframe in prop.keyframes:
            assert keyframe._value._layer is layer

    def test_mask_keyframes_are_in_layer_space(self) -> None:
        # The layer is 200x100 inside a 400x300 comp, so a Shape scaled by
        # the comp instead of the layer reads 2x / 3x too large.
        prop = _find(self._probe_layer("probe_solid"), "ADBE Mask Shape")
        first = prop.keyframes[0].value
        assert isinstance(first, Shape)
        for got, expected in zip(
            first.vertices, [[20, 20], [120, 20], [120, 80], [20, 80]]
        ):
            assert abs(got[0] - expected[0]) < 1e-4
            assert abs(got[1] - expected[1]) < 1e-4

    def test_puppet_pin_is_in_pixels(self) -> None:
        # AE reports the pin in layer pixels; the file holds it normalized
        # against the 200x100 layer.
        prop = _find(self._probe_layer("probe_puppet"), "ADBE FreePin3 PosPin Position")
        assert prop.units_text == "pixels"
        for got, expected in zip(prop.keyframes[0].value, [50.0, 25.0]):
            assert abs(got - expected) < 1e-6

    def test_orientation_keyframe_ease_reads_the_stored_influence(self) -> None:
        # The orientation ldat item has no value slot, so reading it as a
        # 1-D value item shifted every ease field by one double.
        project = parse_project(SAMPLES_DIR / "property_path_orientation_ease.aep")
        comp = get_comp(project, "vat_ease")
        layer = next(ly for ly in comp.layers if ly.name == "orient_asym")
        prop = _find(layer, "ADBE Orientation")
        out_ease = prop.keyframes[0].out_temporal_ease[0]
        in_ease = prop.keyframes[1].in_temporal_ease[0]
        assert (out_ease.speed, out_ease.influence) == (0.0, 90.0)
        assert (in_ease.speed, in_ease.influence) == (0.0, 20.0)

    def test_linear_orientation_ease_speed_is_one(self) -> None:
        # AE reports 1 for a LINEAR side of a value with no scalar
        # magnitude, not the euler-vector slope.
        prop = _find(self._probe_layer("probe_solid"), "ADBE Orientation")
        assert prop.keyframes[0].out_temporal_ease[0].speed == 1.0
        assert prop.keyframes[1].in_temporal_ease[0].speed == 1.0


class TestShapeInterpolationEdges:
    """Behaviour the AE fixtures do not cover."""

    @pytest.mark.parametrize(
        ("segments", "target", "expected"),
        [
            # AE bisects breadth-first: every segment once in path order,
            # then every half in that order. Read off AE 2026 across
            # sources of 2 to 5 segments and targets up to 12.
            (3, 3, [[], [], []]),
            (3, 4, [[0.5], [], []]),
            (3, 5, [[0.5], [0.5], []]),
            (3, 6, [[0.5], [0.5], [0.5]]),
            (3, 7, [[0.25, 0.5], [0.5], [0.5]]),
            (3, 8, [[0.25, 0.5, 0.75], [0.5], [0.5]]),
            (3, 9, [[0.25, 0.5, 0.75], [0.25, 0.5], [0.5]]),
            (3, 10, [[0.25, 0.5, 0.75], [0.25, 0.5, 0.75], [0.5]]),
            (4, 6, [[0.5], [0.5], [], []]),
            (4, 9, [[0.25, 0.5], [0.5], [0.5], [0.5]]),
            (5, 7, [[0.5], [0.5], [], [], []]),
        ],
    )
    def test_subdivision_is_breadth_first(
        self, segments: int, target: int, expected: list[list[float]]
    ) -> None:
        assert _subdivision_cuts(segments, target) == expected

    def test_vertex_count_mismatch_resamples_the_shorter_path(self) -> None:
        left = Shape([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]])
        right = Shape([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [-5.0, 5.0]])
        blended = interpolate_shapes(left, right, 0.0)
        assert blended is not None
        # At progress 0 the blend IS the resampled left path: the same
        # outline, two extra vertices, and still straight.
        assert blended.vertices == [
            [0.0, 0.0],
            [5.0, 0.0],
            [10.0, 0.0],
            [10.0, 5.0],
            [10.0, 10.0],
        ]
        assert blended.in_tangents == [[0.0, 0.0]] * 5
        assert blended.out_tangents == [[0.0, 0.0]] * 5

    def test_resampling_a_curve_preserves_its_shape(self) -> None:
        # One curved segment split in half: de Casteljau puts the new
        # vertex at the curve's midpoint and halves the outer handles.
        left = Shape(
            [[0.0, 0.0], [100.0, 0.0]],
            [[0.0, 0.0], [-40.0, 0.0]],
            [[40.0, 0.0], [0.0, 0.0]],
            closed=False,
        )
        right = Shape([[0.0, 0.0], [50.0, 0.0], [100.0, 0.0]], closed=False)
        blended = interpolate_shapes(left, right, 0.0)
        assert blended is not None
        assert blended.vertices == [[0.0, 0.0], [50.0, 0.0], [100.0, 0.0]]
        assert blended.out_tangents[0] == [20.0, 0.0]
        assert blended.in_tangents[2] == [-20.0, 0.0]

    def test_empty_shapes_hold_the_left_key(self) -> None:
        assert interpolate_shapes(Shape([]), Shape([]), 0.5) is None

    def test_closed_comes_from_the_left_key(self) -> None:
        left = Shape([[0.0, 0.0], [10.0, 0.0]], closed=False)
        right = Shape([[0.0, 0.0], [10.0, 0.0]], closed=True)
        blended = interpolate_shapes(left, right, 0.5)
        assert blended is not None
        assert blended.closed is False


class TestOrientationSlerp:
    """The quaternion path, independently of any sample."""

    def test_midpoint_is_not_a_per_axis_blend(self) -> None:
        got = slerp_orientation([0.0, 0.0, 0.0], [45.0, 90.0, 30.0], 0.5)
        # AE 2026; a per-axis blend would give [22.5, 45, 15].
        for a, b in zip(got, [22.083206323481, 42.8193869722279, 22.083206323481]):
            assert abs(a - b) < 1e-9

    def test_takes_the_short_way_round(self) -> None:
        # 10 -> 350 degrees is -20 degrees the short way, and AE reports the
        # result wrapped into [0, 360).
        got = slerp_orientation([0.0, 0.0, 10.0], [0.0, 0.0, 350.0], 0.5)
        assert abs(got[2] - 0.0) < 1e-9 or abs(got[2] - 360.0) < 1e-9

    def test_endpoints_round_trip(self) -> None:
        for angles in ([0.0, 0.0, 0.0], [10.0, 20.0, 30.0], [45.0, 80.0, 30.0]):
            start = slerp_orientation(angles, [1.0, 2.0, 3.0], 0.0)
            for a, b in zip(start, angles):
                assert abs(a - b) < 1e-9

    def test_gimbal_lock_keeps_the_rotation(self) -> None:
        # At Y = 90 degrees X and Z turn about the same axis, so only their
        # sum is recoverable: [45, 90, 30] comes back as [0, 90, 75], the
        # same rotation. All of it lands on Z because that is where AE puts
        # it - measured by reparenting a 3D layer onto the pole, which AE
        # writes back as [0, 270, g]. `interpolate_keyframes` returns a
        # keyframe's own value at its own time, so this never reshapes a
        # stored angle.
        got = slerp_orientation([45.0, 90.0, 30.0], [1.0, 2.0, 3.0], 0.0)
        assert [round(v, 9) for v in got] == [0.0, 90.0, 75.0]
        original = euler_to_quaternion([45.0, 90.0, 30.0])
        recovered = euler_to_quaternion(got)
        assert abs(abs(sum(a * b for a, b in zip(original, recovered))) - 1.0) < 1e-12
