"""Tests for Property.value_at_time() interpolation against ExtendScript ground truth.

Ground truth comes from `export_value_at_time.jsx` which evaluates
`prop.valueAtTime(frame * comp.frameDuration)` in After Effects and stores
the result alongside the frame number and full-precision evaluation time.

Spatial properties (position, 2D/3D) exhibit a systematic ±0.015 deviation
from pure mathematical interpolation because After Effects processes spatial
values through an internal arc-length reparameterisation pipeline that
introduces small numerical artifacts - even for perfectly straight paths.
See :doc:`/limitations` for details.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import get_first_layer, load_expected, parse_project

from py_aep import Property

SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "models" / "property"
VAT_DIR = SAMPLES_DIR / "value_at_time"

# Maps matchName -> function to find the property from a parsed layer
_FINDERS: dict[str, object] = {
    "ADBE Opacity": lambda ly: ly.transform.property("ADBE Opacity"),
    "ADBE Position": lambda ly: ly.transform.property("ADBE Position"),
    "ADBE Position_0": lambda ly: ly.transform.property("ADBE Position_0"),
    "ADBE Scale": lambda ly: ly.transform.property("ADBE Scale"),
    "ADBE Rotate Z": lambda ly: ly.transform.property("ADBE Rotate Z"),
}


def _load_vat(base_name: str) -> tuple[str, list[dict]]:
    """Load value_at_time JSON and return (matchName, frames)."""
    data = load_expected(VAT_DIR, f"{base_name}_value_at_time")
    prop = data["comps"][0]["layers"][0]["properties"][0]
    return prop["matchName"], prop["frames"]


def _get_prop(base_name: str) -> Property:
    """Parse .aep and return the target property."""
    aep = SAMPLES_DIR / f"{base_name}.aep"
    layer = get_first_layer(parse_project(aep))
    (
        match_name,
        _,
    ) = _load_vat(base_name)
    finder = _FINDERS.get(match_name)
    assert finder is not None, f"No finder for {match_name}"
    prop = finder(layer)
    assert prop is not None, f"Property {match_name} not found"
    return prop


def _max_error(prop: Property, frames: list[dict]) -> float:
    """Compute maximum abs error across all frames."""
    max_err = 0.0
    for f in frames:
        got = prop.value_at_time(f["time"])
        expected = f["value"]
        if isinstance(expected, list) and isinstance(got, list):
            err = max(abs(g - e) for g, e in zip(got, expected))
        elif isinstance(expected, (int, float)) and isinstance(got, (int, float)):
            err = abs(float(got) - float(expected))
        else:
            err = float("inf")
        max_err = max(max_err, err)
    return max_err


# -- Tolerance groups -------------------------------------------------------
# Non-spatial samples: max error < 0.001 (exact when time matches AE).
# Spatial samples: max error < 0.015 (AE's internal spatial pipeline
# introduces ±0.011 systematic artifacts, even for straight LINEAR paths).
_NON_SPATIAL_SAMPLES = [
    "keyframe_bezier_asymmetric_ease_1D",
    "keyframe_bezier_ease_in_out_1D",
    "keyframe_bezier_ease_scale",
    "keyframe_bezier_extreme_ease_1D",
    "keyframe_bezier_multi_ease_1D",
    "keyframe_bezier_nonzero_speed",
    "keyframe_bounce_pattern",
    "keyframe_comp_boundaries",
    "keyframe_extrapolation",
    "keyframe_flat_value",
    "keyframe_hold_2D_position",
    "keyframe_HOLD",
    "keyframe_mixed_interpolation",
    "keyframe_separated_dimensions",
    "keyframe_single",
    "keyframe_temporal_auto_bezier",
    "keyframe_temporal_continuous",
    "property_1D_opacity",
    "property_rotation",
    "property_scale",
]

_SPATIAL_SAMPLES = [
    "keyframe_bezier_ease_2D_position",
    "keyframe_BEZIER",
    "keyframe_linear_2D_position",
    "keyframe_LINEAR",
    "keyframe_roving",
    "keyframe_spatial_auto_bezier",
    "keyframe_spatial_bezier_3D",
    "keyframe_spatial_bezier_arc",
    "keyframe_spatial_bezier_s_curve",
    "keyframe_spatial_continuous",
    "property_2D_position",
    "property_3D_position",
]


class TestValueAtTimeNonSpatial:
    """Non-spatial samples: error < 0.001."""

    @pytest.mark.parametrize("sample", _NON_SPATIAL_SAMPLES)
    def test_value_at_time(self, sample: str) -> None:
        prop = _get_prop(sample)
        _, frames = _load_vat(sample)
        max_err = _max_error(prop, frames)
        assert max_err < 0.001, f"{sample}: max error {max_err:.6f}"


class TestValueAtTimeSpatial:
    """Spatial samples: error < 0.015 (AE spatial noise floor)."""

    @pytest.mark.parametrize("sample", _SPATIAL_SAMPLES)
    def test_value_at_time(self, sample: str) -> None:
        prop = _get_prop(sample)
        _, frames = _load_vat(sample)
        max_err = _max_error(prop, frames)
        assert max_err < 0.015, f"{sample}: max error {max_err:.6f}"


class TestValueAtTimeAPI:
    """Tests for value_at_time API behavior."""

    def test_pre_expression_false_raises(self) -> None:
        """pre_expression=False raises NotImplementedError."""
        prop = _get_prop("property_1D_opacity")
        with pytest.raises(NotImplementedError):
            prop.value_at_time(0.0, pre_expression=False)

    def test_static_value(self) -> None:
        """Static (non-animated) property returns its value at any time."""
        prop = _get_prop("property_1D_opacity")
        _, frames = _load_vat("property_1D_opacity")
        for f in frames[:5]:
            result = prop.value_at_time(f["time"])
            expected = f["value"]
            if isinstance(expected, (int, float)):
                assert abs(float(result) - float(expected)) < 0.001
            elif isinstance(expected, list):
                for g, e in zip(result, expected):
                    assert abs(g - e) < 0.001
