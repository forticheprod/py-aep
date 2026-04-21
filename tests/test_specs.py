"""Validate _PropSpec and _GroupSpec entries for internal consistency.

These tests catch typos, wrong PropertyValueType, incorrect dimensions, and
other silent data errors in the spec tables used for property synthesis.
"""

from __future__ import annotations

import pytest

from py_aep.data.match_names import MATCH_NAME_TO_AUTO_NAME
from py_aep.enums import PropertyValueType
from py_aep.models.properties.specs import (
    _ADV_BLEND_SPECS,
    _AUDIO_SPECS,
    _BEVEL_EMBOSS_SPECS,
    _BLEND_OPTIONS_SPECS,
    _CAMERA_SPECS,
    _COLOR_MAX,
    _COLOR_MIN,
    _COLOR_OVERLAY_SPECS,
    _COMPOSITING_OPTIONS_SPECS,
    _DROP_SHADOW_SPECS,
    _EXTRUSION_SPECS,
    _GRADIENT_OVERLAY_SPECS,
    _GROUP_CHILD_SPECS,
    _INNER_GLOW_SPECS,
    _INNER_SHADOW_SPECS,
    _LAYER_STYLE_CHILD_SPECS,
    _LIGHT_SPECS,
    _MASK_ATOM_SPECS,
    _MATERIAL_SPECS,
    _OUTER_GLOW_SPECS,
    _PATTERN_OVERLAY_SPECS,
    _PLANE_SPECS,
    _SATIN_SPECS,
    _SOURCE_OPTIONS_SPECS,
    _STROKE_SPECS,
    _TEXT_MORE_OPTIONS_SPECS,
    _TEXT_PATH_OPTIONS_SPECS,
    _TOP_LEVEL_SPECS,
    _TRANSFORM_SPECS,
    _VECTOR_ELLIPSE_SPECS,
    _VECTOR_FILL_SPECS,
    _VECTOR_GROUP_SPECS,
    _VECTOR_MATERIALS_SPECS,
    _VECTOR_RECT_SPECS,
    _VECTOR_REPEATER_SPECS,
    _VECTOR_REPEATER_TRANSFORM_SPECS,
    _VECTOR_STAR_SPECS,
    _VECTOR_STROKE_DASHES_SPECS,
    _VECTOR_STROKE_SPECS,
    _VECTOR_STROKE_TAPER_SPECS,
    _VECTOR_STROKE_WAVE_SPECS,
    _VECTOR_TRANSFORM_SPECS,
    _GroupSpec,
    _PropSpec,
)

# ---------------------------------------------------------------------------
# Collect all spec lists into a flat sequence of (list_name, spec) pairs
# for parametrized testing.
# ---------------------------------------------------------------------------

_NAMED_SPEC_LISTS: list[tuple[str, list[_PropSpec | _GroupSpec]]] = [
    ("MATERIAL", _MATERIAL_SPECS),
    ("EXTRUSION", _EXTRUSION_SPECS),
    ("PLANE", _PLANE_SPECS),
    ("AUDIO", _AUDIO_SPECS),
    ("SOURCE_OPTIONS", _SOURCE_OPTIONS_SPECS),
    ("COMPOSITING_OPTIONS", _COMPOSITING_OPTIONS_SPECS),
    ("MASK_ATOM", _MASK_ATOM_SPECS),
    ("LIGHT", _LIGHT_SPECS),
    ("CAMERA", _CAMERA_SPECS),
    ("TEXT_PATH_OPTIONS", _TEXT_PATH_OPTIONS_SPECS),
    ("TEXT_MORE_OPTIONS", _TEXT_MORE_OPTIONS_SPECS),
    ("VECTOR_STAR", _VECTOR_STAR_SPECS),
    ("VECTOR_FILL", _VECTOR_FILL_SPECS),
    ("VECTOR_STROKE", _VECTOR_STROKE_SPECS),
    ("VECTOR_STROKE_DASHES", _VECTOR_STROKE_DASHES_SPECS),
    ("VECTOR_STROKE_TAPER", _VECTOR_STROKE_TAPER_SPECS),
    ("VECTOR_STROKE_WAVE", _VECTOR_STROKE_WAVE_SPECS),
    ("VECTOR_GROUP", _VECTOR_GROUP_SPECS),
    ("VECTOR_TRANSFORM", _VECTOR_TRANSFORM_SPECS),
    ("VECTOR_MATERIALS", _VECTOR_MATERIALS_SPECS),
    ("VECTOR_ELLIPSE", _VECTOR_ELLIPSE_SPECS),
    ("VECTOR_RECT", _VECTOR_RECT_SPECS),
    ("VECTOR_REPEATER_TRANSFORM", _VECTOR_REPEATER_TRANSFORM_SPECS),
    ("VECTOR_REPEATER", _VECTOR_REPEATER_SPECS),
    ("BLEND_OPTIONS", _BLEND_OPTIONS_SPECS),
    ("ADV_BLEND", _ADV_BLEND_SPECS),
    ("DROP_SHADOW", _DROP_SHADOW_SPECS),
    ("INNER_SHADOW", _INNER_SHADOW_SPECS),
    ("OUTER_GLOW", _OUTER_GLOW_SPECS),
    ("INNER_GLOW", _INNER_GLOW_SPECS),
    ("BEVEL_EMBOSS", _BEVEL_EMBOSS_SPECS),
    ("SATIN", _SATIN_SPECS),
    ("COLOR_OVERLAY", _COLOR_OVERLAY_SPECS),
    ("GRADIENT_OVERLAY", _GRADIENT_OVERLAY_SPECS),
    ("PATTERN_OVERLAY", _PATTERN_OVERLAY_SPECS),
    ("STROKE", _STROKE_SPECS),
    ("TRANSFORM", _TRANSFORM_SPECS),
    ("TOP_LEVEL", _TOP_LEVEL_SPECS),
]

# Add spec lists from the registry dicts.
for _key, _specs in _GROUP_CHILD_SPECS.items():
    _NAMED_SPEC_LISTS.append((f"GROUP_CHILD[{_key}]", list(_specs)))
for _key, _specs in _LAYER_STYLE_CHILD_SPECS.items():
    _NAMED_SPEC_LISTS.append((f"LAYER_STYLE[{_key}]", list(_specs)))

# Flat list of all _PropSpec entries with readable IDs.
_ALL_PROP_SPECS: list[tuple[str, _PropSpec]] = [
    (f"{list_name}/{spec.match_name}", spec)
    for list_name, specs in _NAMED_SPEC_LISTS
    for spec in specs
    if isinstance(spec, _PropSpec)
]

# Flat list of all specs (both types) with readable IDs.
_ALL_SPECS: list[tuple[str, _PropSpec | _GroupSpec]] = [
    (f"{list_name}/{spec.match_name}", spec)
    for list_name, specs in _NAMED_SPEC_LISTS
    for spec in specs
]

# Expected dimensions for each PropertyValueType.
_PVT_EXPECTED_DIMENSIONS: dict[PropertyValueType, int | None] = {
    PropertyValueType.COLOR: 4,
    PropertyValueType.ThreeD_SPATIAL: 3,
    PropertyValueType.ThreeD: 3,
    PropertyValueType.TwoD_SPATIAL: 2,
    PropertyValueType.TwoD: 2,
    PropertyValueType.MARKER: 0,
}

# SPATIAL pvt types that require is_spatial=True.
_SPATIAL_PVTS = frozenset(
    {
        PropertyValueType.TwoD_SPATIAL,
        PropertyValueType.ThreeD_SPATIAL,
    }
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPropSpecFieldConsistency:
    """Validate individual _PropSpec field invariants."""

    @pytest.mark.parametrize(
        "spec_id, spec",
        _ALL_PROP_SPECS,
        ids=[s[0] for s in _ALL_PROP_SPECS],
    )
    def test_pvt_dimensions_consistency(self, spec_id: str, spec: _PropSpec) -> None:
        expected = _PVT_EXPECTED_DIMENSIONS.get(spec.pvt)
        if expected is not None:
            assert spec.dimensions == expected, (
                "%s: pvt=%s requires dimensions=%d, got %d"  # noqa: UP031
                % (spec_id, spec.pvt.name, expected, spec.dimensions)
            )

    @pytest.mark.parametrize(
        "spec_id, spec",
        _ALL_PROP_SPECS,
        ids=[s[0] for s in _ALL_PROP_SPECS],
    )
    def test_color_flag_iff_color_pvt(self, spec_id: str, spec: _PropSpec) -> None:
        is_color_pvt = spec.pvt == PropertyValueType.COLOR
        assert spec.color == is_color_pvt, (
            f"{spec_id}: color={spec.color!r} but pvt={spec.pvt.name}"
        )

    @pytest.mark.parametrize(
        "spec_id, spec",
        _ALL_PROP_SPECS,
        ids=[s[0] for s in _ALL_PROP_SPECS],
    )
    def test_spatial_pvt_requires_is_spatial(
        self, spec_id: str, spec: _PropSpec
    ) -> None:
        if spec.pvt in _SPATIAL_PVTS:
            assert spec.is_spatial, (
                f"{spec_id}: pvt={spec.pvt.name} requires is_spatial=True"
            )

    @pytest.mark.parametrize(
        "spec_id, spec",
        _ALL_PROP_SPECS,
        ids=[s[0] for s in _ALL_PROP_SPECS],
    )
    def test_value_shape_matches_dimensions(
        self, spec_id: str, spec: _PropSpec
    ) -> None:
        if spec.value is None:
            return
        if spec.dimensions > 1:
            assert isinstance(spec.value, list), (
                f"{spec_id}: dimensions={spec.dimensions} but value is not a list"
            )
            assert len(spec.value) == spec.dimensions, (
                f"{spec_id}: dimensions={spec.dimensions} but value has {len(spec.value)} elements"
            )
        elif spec.dimensions <= 1:
            assert isinstance(spec.value, (int, float)), (
                f"{spec_id}: dimensions={spec.dimensions} but value is {type(spec.value).__name__}, expected scalar"
            )

    @pytest.mark.parametrize(
        "spec_id, spec",
        _ALL_PROP_SPECS,
        ids=[s[0] for s in _ALL_PROP_SPECS],
    )
    def test_color_specs_have_bounds(self, spec_id: str, spec: _PropSpec) -> None:
        if spec.pvt != PropertyValueType.COLOR:
            return
        assert spec.min_value == _COLOR_MIN, (
            f"{spec_id}: COLOR spec missing min_value=_COLOR_MIN"
        )
        assert spec.max_value == _COLOR_MAX, (
            f"{spec_id}: COLOR spec missing max_value=_COLOR_MAX"
        )

    @pytest.mark.parametrize(
        "spec_id, spec",
        _ALL_PROP_SPECS,
        ids=[s[0] for s in _ALL_PROP_SPECS],
    )
    def test_min_max_ordering(self, spec_id: str, spec: _PropSpec) -> None:
        if spec.min_value is not None and spec.max_value is not None:
            assert spec.min_value <= spec.max_value, (
                f"{spec_id}: min_value={spec.min_value!r} > max_value={spec.max_value!r}"
            )


class TestSpecStringFields:
    """Validate name and match_name are non-empty on all specs."""

    @pytest.mark.parametrize(
        "spec_id, spec",
        _ALL_SPECS,
        ids=[s[0] for s in _ALL_SPECS],
    )
    def test_non_empty_match_name(
        self, spec_id: str, spec: _PropSpec | _GroupSpec
    ) -> None:
        assert isinstance(spec.match_name, str) and spec.match_name

    @pytest.mark.parametrize(
        "spec_id, spec",
        _ALL_SPECS,
        ids=[s[0] for s in _ALL_SPECS],
    )
    def test_non_empty_auto_name(
        self, spec_id: str, spec: _PropSpec | _GroupSpec
    ) -> None:
        assert isinstance(spec.auto_name, str) and spec.auto_name


class TestSpecListUniqueness:
    """Validate no duplicate match_names within a single spec list."""

    @pytest.mark.parametrize(
        "list_name, specs",
        _NAMED_SPEC_LISTS,
        ids=[s[0] for s in _NAMED_SPEC_LISTS],
    )
    def test_unique_match_names(
        self,
        list_name: str,
        specs: list[_PropSpec | _GroupSpec],
    ) -> None:
        match_names = [s.match_name for s in specs]
        duplicates = [mn for mn in match_names if match_names.count(mn) > 1]
        assert not duplicates, (
            f"{list_name} has duplicate match_names: {sorted(set(duplicates))}"
        )


# Known intentional divergences: spec name differs from registry name.
# Specs use the short names shown in the AE timeline; the registry has the
# fully qualified ExtendScript names.
_KNOWN_DIVERGENCES: dict[str, str] = {
    # AE shows "Rotation" on 2D layers; registry has "Z Rotation".
    "ADBE Rotate Z": "Rotation",
    # Vector Transform properties: specs use short names, registry prefixes
    # with "Shape Group Transform".
    "ADBE Vector Anchor": "Anchor Point",
    "ADBE Vector Position": "Position",
    "ADBE Vector Scale": "Scale",
    "ADBE Vector Skew": "Skew",
    "ADBE Vector Skew Axis": "Skew Axis",
    "ADBE Vector Rotation": "Rotation",
    "ADBE Vector Group Opacity": "Opacity",
}

_REGISTRY_SPECS = [
    (sid, s)
    for sid, s in _ALL_SPECS
    if s.match_name in MATCH_NAME_TO_AUTO_NAME
    and s.match_name not in _KNOWN_DIVERGENCES
]


class TestSpecNamesMatchRegistry:
    """Cross-validate spec auto_names against MATCH_NAME_TO_AUTO_NAME."""

    @pytest.mark.parametrize(
        "spec_id, spec",
        _REGISTRY_SPECS,
        ids=[s[0] for s in _REGISTRY_SPECS],
    )
    def test_name_matches_registry(
        self, spec_id: str, spec: _PropSpec | _GroupSpec
    ) -> None:
        expected = MATCH_NAME_TO_AUTO_NAME[spec.match_name]
        assert spec.auto_name == expected, (
            f"{spec_id}: spec auto_name {spec.auto_name!r} != registry {expected!r}"
        )

    @pytest.mark.parametrize(
        "match_name, expected_spec_name",
        list(_KNOWN_DIVERGENCES.items()),
        ids=list(_KNOWN_DIVERGENCES.keys()),
    )
    def test_known_divergences_are_still_divergent(
        self, match_name: str, expected_spec_name: str
    ) -> None:
        """Guard that allowlisted divergences haven't been fixed without
        removing the allowlist entry."""
        registry_name = MATCH_NAME_TO_AUTO_NAME.get(match_name)
        assert registry_name is not None, (
            f"allowlisted match_name {match_name!r} no longer in registry"
        )
        assert registry_name != expected_spec_name, (
            f"divergence for {match_name!r} has been resolved - remove from allowlist"
        )
