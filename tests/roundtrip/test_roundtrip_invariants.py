"""Migration invariant tests.

Regression suite designed to survive the Kaitai-to-struct migration.
All tests use the PUBLIC model API only - no Kaitai types, no chunk
internals. If any test here breaks during migration, the migration
has a bug.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from helpers import get_first_layer

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


class TestByteIdentityRoundtrip:
    """Parse > save > compare bytes for diverse sample files."""

    @pytest.mark.parametrize(
        "aep_path",
        ROUNDTRIP_SAMPLES,
        ids=lambda p: p.relative_to(SAMPLES_DIR).as_posix().replace("/", "__"),
    )
    def test_roundtrip(self, aep_path: Path, tmp_path: Path) -> None:
        original_bytes = aep_path.read_bytes()

        app = parse_aep(aep_path)
        out = tmp_path / "roundtrip.aep"
        app.project.save(out)
        roundtrip_bytes = out.read_bytes()

        assert roundtrip_bytes == original_bytes


class TestMaterializationLifecycle:
    """Writing to synthesized properties triggers materialization that
    survives save/re-parse."""

    def test_materialize_on_value_write(self, tmp_path: Path) -> None:
        """Setting value materializes the property into the chunk tree."""
        app = parse_aep(PROPERTY_DIR / "2_gaussian.aep")
        layer = get_first_layer(app.project)
        blur = _find_synthesized_effect_prop(layer, 0, "ADBE Gaussian Blur 2-0001")

        blur.value = 42.0

        out = tmp_path / "materialized.aep"
        app.project.save(out)

        app2 = parse_aep(out)
        layer2 = get_first_layer(app2.project)
        blur2 = _find_synthesized_effect_prop(layer2, 0, "ADBE Gaussian Blur 2-0001")
        assert blur2.value == 42.0

    def test_enabled_read_only_on_effect_param(self) -> None:
        """Effect-parameter `enabled` is read-only (AE `canSetEnabled` is
        False), so the write is rejected and the property is left untouched."""
        app = parse_aep(PROPERTY_DIR / "2_gaussian.aep")
        layer = get_first_layer(app.project)
        blur = _find_synthesized_effect_prop(layer, 0, "ADBE Gaussian Blur 2-0001")
        assert blur.enabled is True
        assert blur.can_set_enabled is False

        with pytest.raises(AttributeError):
            blur.enabled = False

        assert blur.enabled is True

    def test_materialize_on_name_write(self, tmp_path: Path) -> None:
        """Setting name materializes the property into the chunk tree."""
        app = parse_aep(PROPERTY_DIR / "2_gaussian.aep")
        layer = get_first_layer(app.project)
        blur = _find_synthesized_effect_prop(layer, 0, "ADBE Gaussian Blur 2-0001")

        blur.name = "Custom Blur Name"

        out = tmp_path / "materialized.aep"
        app.project.save(out)

        app2 = parse_aep(out)
        layer2 = get_first_layer(app2.project)
        blur2 = _find_synthesized_effect_prop(layer2, 0, "ADBE Gaussian Blur 2-0001")
        assert blur2.name == "Custom Blur Name"


class TestParseTimeWriteGuard:
    """ChunkField.__set__ must block writes when materialization is suppressed,
    while __dict__ bypass must still work."""

    def test_write_blocked_during_suppress(self) -> None:
        """ChunkField raises RuntimeError when materialization is suppressed."""
        from py_aep.models.descriptors import _suppress_materialization

        app = parse_aep(PROPERTY_DIR / "keyframe_1D.aep")
        layer = get_first_layer(app.project)
        opacity = _find_property(layer, "ADBE Opacity")
        assert opacity is not None

        with _suppress_materialization():
            with pytest.raises(RuntimeError, match="Cannot write"):
                opacity.enabled = False

    def test_dict_bypass_allowed_during_suppress(self) -> None:
        """__dict__ writes bypass ChunkField guard during suppression."""
        from py_aep.models.descriptors import _suppress_materialization

        app = parse_aep(PROPERTY_DIR / "keyframe_1D.aep")
        layer = get_first_layer(app.project)
        opacity = _find_property(layer, "ADBE Opacity")
        assert opacity is not None

        with _suppress_materialization():
            opacity.__dict__["enabled"] = False
            assert opacity.__dict__["enabled"] is False
