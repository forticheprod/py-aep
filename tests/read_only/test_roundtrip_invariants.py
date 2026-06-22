"""Migration invariant tests.

Regression suite designed to survive the Kaitai-to-struct migration.
All tests use the PUBLIC model API only - no Kaitai types, no chunk
internals. If any test here breaks during migration, the migration
has a bug.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from conftest import get_first_layer, get_layer

from py_aep import parse as parse_aep

if TYPE_CHECKING:
    from py_aep.models.layers.layer import Layer
    from py_aep.models.properties.property import Property
SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples"
PROPERTY_DIR = SAMPLES_DIR / "models" / "property"
LAYER_DIR = SAMPLES_DIR / "models" / "layer"
COMPOSITION_DIR = SAMPLES_DIR / "models" / "composition"
EG_DIR = SAMPLES_DIR / "models" / "essential_graphics"
VERSIONS_DIR = SAMPLES_DIR / "versions"
BUGS_DIR = SAMPLES_DIR / "bugs"
ROUNDTRIP_SAMPLES = [
    # Version coverage - conditional fields across AE eras
    VERSIONS_DIR / "ae2018" / "complete.aep",
    VERSIONS_DIR / "ae2022" / "complete.aep",
    VERSIONS_DIR / "ae2023" / "complete.aep",
    VERSIONS_DIR / "ae2024" / "complete.aep",
    VERSIONS_DIR / "ae2025" / "complete.aep",
    VERSIONS_DIR / "ae2026" / "complete.aep",
    # Feature coverage - unique binary patterns
    PROPERTY_DIR / "effects.aep",
    PROPERTY_DIR / "2_gaussian.aep",
    PROPERTY_DIR / "keyframe_spatial.aep",
    PROPERTY_DIR / "keyframe_spatial_bezier_3D.aep",
    PROPERTY_DIR / "keyframe_1D.aep",
    PROPERTY_DIR / "shape_basic.aep",
    PROPERTY_DIR / "mask_add.aep",
    EG_DIR / "multiple_controllers.aep",
    COMPOSITION_DIR / "bgColor_custom.aep",
    # Edge cases
    BUGS_DIR / "29.97_fps_time_scale_3.125.aep",
    BUGS_DIR / "windows-1250_decoding_error.aep",
    BUGS_DIR / "outputmodule_path.aep",
]


def _find_property(layer: Layer, match_name: str) -> Property | None:
    """Find a property by match_name anywhere in the layer's property tree."""
    from py_aep.models.properties.property import Property
    from py_aep.models.properties.property_group import PropertyGroup

    def _search(group: PropertyGroup) -> Property | None:
        for prop in group.properties:
            if isinstance(prop, Property) and prop.match_name == match_name:
                return prop
            if isinstance(prop, PropertyGroup):
                result = _search(prop)
                if result is not None:
                    return result
        return None

    for group in layer.properties:
        if isinstance(group, Property) and group.match_name == match_name:
            return group
        if isinstance(group, PropertyGroup):
            result = _search(group)
            if result is not None:
                return result
    return None


def _find_synthesized_effect_prop(
    layer: Layer, effect_index: int, match_name: str
) -> Property:
    """Find a synthesized effect property by match name."""
    from py_aep.models.properties.property import Property
    from py_aep.models.properties.property_group import PropertyGroup

    effect = layer.effects.properties[effect_index]
    assert isinstance(effect, PropertyGroup)
    for prop in effect.properties:
        if isinstance(prop, Property) and prop.match_name == match_name:
            return prop
    raise AssertionError(f"Property {match_name!r} not found in effect")


class TestSynthesizedPropertyInvisibility:
    """Synthesized (ProxyBody-backed) properties must not affect saved bytes."""

    def test_effect_properties_invisible(self, tmp_path: Path) -> None:
        """Synthesized effect properties exist in model but not in output."""
        aep_path = PROPERTY_DIR / "2_gaussian.aep"
        original_bytes = aep_path.read_bytes()

        app = parse_aep(aep_path)
        layer = get_first_layer(app.project)

        # Verify synthesized properties exist in the model
        blur = _find_synthesized_effect_prop(layer, 0, "ADBE Gaussian Blur 2-0001")
        assert blur is not None
        assert blur.value is not None

        # Save WITHOUT mutating anything
        out = tmp_path / "untouched.aep"
        app.project.save(out)
        assert out.read_bytes() == original_bytes

    def test_top_level_groups_invisible(self, tmp_path: Path) -> None:
        """Synthesized top-level groups (Effects, Masks) don't affect output."""
        aep_path = PROPERTY_DIR / "keyframe_1D.aep"
        original_bytes = aep_path.read_bytes()

        app = parse_aep(aep_path)
        layer = get_first_layer(app.project)

        # Verify synthesized groups exist in the property tree
        match_names = [p.match_name for p in layer.properties]
        assert "ADBE Effect Parade" in match_names
        assert "ADBE Mask Parade" in match_names

        # Save without mutation
        out = tmp_path / "untouched.aep"
        app.project.save(out)
        assert out.read_bytes() == original_bytes


class TestParameterizedBodyRoundtrip:
    """Verify that specific binary patterns (LE cdat, spatial ldat, tdum/tduM)
    survive parse > model access > save without corruption."""

    def test_le_cdat_orientation(self, tmp_path: Path) -> None:
        """LE cdat inside LIST:otst survives round-trip."""
        aep_path = LAYER_DIR / "orientation_with_keyframes.aep"
        original_bytes = aep_path.read_bytes()

        app = parse_aep(aep_path)
        layer = get_first_layer(app.project)
        orientation = _find_property(layer, "ADBE Orientation")
        assert orientation is not None
        assert len(orientation.keyframes) > 0

        out = tmp_path / "roundtrip.aep"
        app.project.save(out)
        assert out.read_bytes() == original_bytes

    def test_spatial_2d_ldat(self, tmp_path: Path) -> None:
        """2D spatial ldat with tangent arrays survives round-trip."""
        aep_path = PROPERTY_DIR / "keyframe_spatial.aep"
        original_bytes = aep_path.read_bytes()

        app = parse_aep(aep_path)
        layer = get_layer(app.project, "keyframe_spatial_bezier_arc")
        position = _find_property(layer, "ADBE Position")
        assert position is not None
        assert position.is_spatial is True
        assert len(position.keyframes) > 0

        out = tmp_path / "roundtrip.aep"
        app.project.save(out)
        assert out.read_bytes() == original_bytes

    def test_spatial_3d_ldat(self, tmp_path: Path) -> None:
        """3D spatial ldat (promoted via tdb4.is_spatial) survives round-trip."""
        aep_path = PROPERTY_DIR / "keyframe_spatial_bezier_3D.aep"
        original_bytes = aep_path.read_bytes()

        app = parse_aep(aep_path)
        layer = get_first_layer(app.project)
        position = _find_property(layer, "ADBE Position")
        assert position is not None
        assert position.is_spatial is True
        assert len(position.keyframes) > 0

        out = tmp_path / "roundtrip.aep"
        app.project.save(out)
        assert out.read_bytes() == original_bytes

    def test_tdum_with_effects(self, tmp_path: Path) -> None:
        """tdum/tduM min/max chunks with multiple value types survive round-trip."""
        aep_path = PROPERTY_DIR / "effects.aep"
        original_bytes = aep_path.read_bytes()

        app = parse_aep(aep_path)
        layer = get_first_layer(app.project)
        # Verify effects parsed
        assert layer.effects is not None
        assert len(layer.effects.properties) > 0

        out = tmp_path / "roundtrip.aep"
        app.project.save(out)
        assert out.read_bytes() == original_bytes

    def test_nonspatial_1d_ldat(self, tmp_path: Path) -> None:
        """Non-spatial 1D keyframes - simplest ldat pattern."""
        aep_path = PROPERTY_DIR / "keyframe_1D.aep"
        original_bytes = aep_path.read_bytes()

        app = parse_aep(aep_path)
        layer = get_first_layer(app.project)
        opacity = _find_property(layer, "ADBE Opacity")
        assert opacity is not None
        assert len(opacity.keyframes) > 0
        assert opacity.is_spatial is False

        out = tmp_path / "roundtrip.aep"
        app.project.save(out)
        assert out.read_bytes() == original_bytes
