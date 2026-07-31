"""Tests for CompItem.render_options (3D renderer options)."""

from __future__ import annotations

from py_aep.enums import EnvironmentLightShadowResolution, ShadowMapResolution


class TestRenderOptionEnums:
    def test_shadow_map_resolution_is_positional(self) -> None:
        """Index into AE's dropdown, confirmed at 0, 1 and 8."""
        assert ShadowMapResolution.COMP_SIZE == 0
        assert ShadowMapResolution.RES_250 == 1
        assert ShadowMapResolution.RES_4000 == 8
        assert len(ShadowMapResolution) == 9

    def test_shadow_map_resolution_labels(self) -> None:
        assert ShadowMapResolution.COMP_SIZE.label == "Comp Size"
        assert ShadowMapResolution.RES_750.label == "750"

    def test_environment_light_shadow_resolution(self) -> None:
        assert EnvironmentLightShadowResolution.HALF == 0
        assert EnvironmentLightShadowResolution.FULL == 1
        assert EnvironmentLightShadowResolution.DOUBLE == 2

    def test_environment_light_shadow_resolution_labels(self) -> None:
        assert EnvironmentLightShadowResolution.HALF.label == "Half (2MB)"
        assert EnvironmentLightShadowResolution.DOUBLE.label == "Double (128MB)"
