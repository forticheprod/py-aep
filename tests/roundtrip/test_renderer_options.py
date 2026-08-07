"""Mutation round-trips for CompItem.renderer_options."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep import parse as parse_aep
from py_aep.enums import EnvironmentLightShadowResolution, ShadowMapResolution

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models"
COMPOSITION_DIR = SAMPLES_DIR / "composition"


def _reparse(app, tmp_path: Path):
    out = tmp_path / "modified.aep"
    app.project.save(out)
    return parse_aep(out).project.compositions[0]


class TestRoundtripRendererOptions:
    def test_classic_shadow_map(self, tmp_path: Path) -> None:
        app = parse_aep(COMPOSITION_DIR / "renderer_classic_3d.aep")
        app.project.compositions[
            0
        ].renderer_options.shadow_map_resolution = ShadowMapResolution.RES_4000

        comp = _reparse(app, tmp_path)

        assert (
            comp.renderer_options.shadow_map_resolution is ShadowMapResolution.RES_4000
        )

    def test_cinema_4d_quality(self, tmp_path: Path) -> None:
        app = parse_aep(COMPOSITION_DIR / "renderer_cinema_4d.aep")
        app.project.compositions[0].renderer_options.quality = 99

        assert _reparse(app, tmp_path).renderer_options.quality == 99

    def test_advanced_scalars(self, tmp_path: Path) -> None:
        app = parse_aep(COMPOSITION_DIR / "renderer_advanced_3d.aep")
        opts = app.project.compositions[0].renderer_options
        opts.quality = 125
        opts.resolution = EnvironmentLightShadowResolution.HALF
        opts.smoothness = 20

        comp = _reparse(app, tmp_path)

        assert comp.renderer_options.quality == 125
        assert comp.renderer_options.resolution is EnvironmentLightShadowResolution.HALF
        assert comp.renderer_options.smoothness == 20

    def test_advanced_casting_box(self, tmp_path: Path) -> None:
        """Pixel values survive a save, to float32 precision.

        `approx` is required: the field holds a float64 in memory and narrows
        to float32 only when packed on save, so a value that crosses disk
        returns off by ~4e-5 px. A set-then-read without saving would compare
        exactly equal, which is the trap.
        """
        app = parse_aep(COMPOSITION_DIR / "renderer_advanced_3d.aep")
        opts = app.project.compositions[0].renderer_options
        opts.casting_box_size = 640.0
        opts.casting_box_center = [100.0, 200.0, -300.0]

        comp = _reparse(app, tmp_path)

        assert comp.renderer_options.casting_box_size == pytest.approx(640.0)
        assert comp.renderer_options.casting_box_center == pytest.approx(
            [100.0, 200.0, -300.0]
        )

    def test_mapping_write_round_trips(self, tmp_path: Path) -> None:
        app = parse_aep(COMPOSITION_DIR / "renderer_advanced_3d.aep")
        app.project.compositions[0].renderer_options["Quality"] = 42

        assert _reparse(app, tmp_path).renderer_options["Quality"] == 42

    def test_bulk_assignment(self, tmp_path: Path) -> None:
        app = parse_aep(COMPOSITION_DIR / "renderer_advanced_3d.aep")
        app.project.compositions[0].renderer_options = {"Quality": 7, "Smoothness": 2}

        comp = _reparse(app, tmp_path)

        assert comp.renderer_options.quality == 7
        assert comp.renderer_options.smoothness == 2


class TestRendererOptionsValidation:
    def test_quality_out_of_range(self) -> None:
        comp = parse_aep(
            COMPOSITION_DIR / "renderer_advanced_3d.aep"
        ).project.compositions[0]

        with pytest.raises(ValueError):
            comp.renderer_options.quality = 126

    def test_unknown_key(self) -> None:
        comp = parse_aep(
            COMPOSITION_DIR / "renderer_cinema_4d.aep"
        ).project.compositions[0]

        with pytest.raises(KeyError):
            comp.renderer_options["Nonexistent"] = 1

    def test_enum_rejects_out_of_range(self) -> None:
        """ChunkField.enum validates membership without a separate validator."""
        comp = parse_aep(
            COMPOSITION_DIR / "renderer_classic_3d.aep"
        ).project.compositions[0]

        with pytest.raises(ValueError):
            comp.renderer_options.shadow_map_resolution = 9

    @pytest.mark.parametrize("bad", [-1, 30001])
    def test_casting_box_size_out_of_range(self, bad: float) -> None:
        comp = parse_aep(
            COMPOSITION_DIR / "renderer_advanced_3d.aep"
        ).project.compositions[0]

        with pytest.raises(ValueError):
            comp.renderer_options.casting_box_size = bad

    @pytest.mark.parametrize(
        "bad", [[0.0, 0.0], [40000.0, 0.0, 0.0], [0.0, -40000.0, 0.0]]
    )
    def test_casting_box_center_rejected(self, bad: list[float]) -> None:
        comp = parse_aep(
            COMPOSITION_DIR / "renderer_advanced_3d.aep"
        ).project.compositions[0]

        with pytest.raises(ValueError):
            comp.renderer_options.casting_box_center = bad

    def test_smoothness_out_of_range(self) -> None:
        comp = parse_aep(
            COMPOSITION_DIR / "renderer_advanced_3d.aep"
        ).project.compositions[0]

        with pytest.raises(ValueError):
            comp.renderer_options.smoothness = 21
