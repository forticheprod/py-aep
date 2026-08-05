"""Tests for CompItem.renderer_options (3D renderer options)."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep import RayTracedRendererOptions
from py_aep import parse as parse_aep
from py_aep.enums import EnvironmentLightShadowResolution, ShadowMapResolution

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models"
COMPOSITION_DIR = SAMPLES_DIR / "composition"


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


class TestRendererOptionsReads:
    def test_classic_defaults(self) -> None:
        comp = parse_aep(
            COMPOSITION_DIR / "renderer_classic_3d.aep"
        ).project.compositions[0]
        opts = comp.renderer_options

        assert opts.shadow_map_resolution is ShadowMapResolution.COMP_SIZE
        assert opts["Shadow Map Resolution"] is ShadowMapResolution.COMP_SIZE

    def test_advanced_defaults(self) -> None:
        comp = parse_aep(
            COMPOSITION_DIR / "renderer_advanced_3d.aep"
        ).project.compositions[0]
        opts = comp.renderer_options

        assert opts.quality == 8
        assert opts.resolution is EnvironmentLightShadowResolution.FULL
        assert opts.smoothness == 3
        # Comp-relative: stored 1.0 / 0.0 render as comp width and centre.
        assert opts.casting_box_size == pytest.approx(comp.width)
        assert opts.casting_box_center == pytest.approx(
            [comp.width / 2, comp.height / 2, 0.0]
        )

    def test_cinema_4d_defaults(self) -> None:
        comp = parse_aep(
            COMPOSITION_DIR / "renderer_cinema_4d.aep"
        ).project.compositions[0]

        assert comp.renderer_options.quality == 25

    def test_is_a_mapping(self) -> None:
        """renderer_options returns a Mapping."""
        comp = parse_aep(
            COMPOSITION_DIR / "renderer_cinema_4d.aep"
        ).project.compositions[0]
        opts = comp.renderer_options

        assert dict(opts) == {"Quality": 25}
        assert list(opts.keys()) == ["Quality"]
        assert opts == {"Quality": 25}

    def test_ray_traced_is_read_only(self) -> None:
        """AE 26.3 cannot author this renderer, so we do not let anyone edit it."""
        comp = parse_aep(
            COMPOSITION_DIR / "renderer_ray_traced.aep"
        ).project.compositions[0]
        opts = comp.renderer_options

        assert isinstance(opts, RayTracedRendererOptions)
        assert dict(opts) == {}
        with pytest.raises(KeyError):
            opts["Quality"] = 1
        with pytest.raises(AttributeError):
            opts.quality = 1


class TestRendererOptionsNonDefaults:
    """Values set by hand in After Effects 26.3, on 1920x1080 comps."""

    def test_classic_non_default(self) -> None:
        comp = parse_aep(
            COMPOSITION_DIR / "renderer_options_classic_3d.aep"
        ).project.compositions[0]

        assert comp.renderer_options.shadow_map_resolution is ShadowMapResolution.RES_750

    def test_cinema_4d_non_default(self) -> None:
        comp = parse_aep(
            COMPOSITION_DIR / "renderer_options_cinema_4d.aep"
        ).project.compositions[0]

        assert comp.renderer_options.quality == 44

    def test_advanced_non_default(self) -> None:
        comp = parse_aep(
            COMPOSITION_DIR / "renderer_options_advanced_3d.aep"
        ).project.compositions[0]

        assert comp.renderer_options.quality == 61
        assert comp.renderer_options.resolution is EnvironmentLightShadowResolution.DOUBLE
        assert comp.renderer_options.smoothness == 6
        assert comp.renderer_options.casting_box_size == pytest.approx(600.0)
        assert comp.renderer_options.casting_box_center == pytest.approx(
            [400.0, 600.0, -100.0]
        )
