"""Tests for AVLayer geometry methods against AE 2026 probe fixtures.

`geometry_probe.aep` / `camera_rigs.aep` were generated headlessly in
AE 2026 (2026-07-14) together with per-method ground-truth JSONs read back
via ExtendScript: `sourcePointToComp` / `compPointToSource` for seven layer
setups at two times, `calculateTransformFromPoints` for eleven point sets
(including mirrored and non-orthogonal ones), `sourceRectAtTime` for every
layer kind, and the point conversions under four camera rigs.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from conftest import parse_project

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"
GEOMETRY_AEP = SAMPLES_DIR / "geometry_probe.aep"
CAMERAS_AEP = SAMPLES_DIR / "camera_rigs.aep"

POINTS = [[0.0, 0.0], [100.0, 50.0], [960.0, 540.0]]
CAMERA_POINTS = [[0.0, 0.0], [100.0, 50.0], [200.0, 100.0]]


def _fixture(name: str) -> dict:
    with open(SAMPLES_DIR / name, encoding="utf-8") as fp:
        return json.load(fp)


def _probe_comp(project):
    return next(c for c in project.compositions if c.name == "PROBE_MAIN")


def _layer(comp, name: str):
    return next(ly for ly in comp.layers if ly.name == name)


class TestPointConversions:
    """sourcePointToComp / compPointToSource vs the AE probe values."""

    @pytest.mark.parametrize("time_key,time_val", [("time0", 0.0), ("time1.5", 1.5)])
    def test_all_layers_match_ae(self, time_key: str, time_val: float) -> None:
        expected = _fixture("geometry_points_probe.json")[time_key]
        comp = _probe_comp(parse_project(GEOMETRY_AEP))
        for layer_name, entry in expected.items():
            layer = _layer(comp, layer_name)
            for pi, pt in enumerate(POINTS):
                want = entry["s2c"][pi]
                if want["ok"]:
                    got = layer.source_point_to_comp(pt, time=time_val)
                    assert got == pytest.approx(want["value"], abs=5e-3), (
                        f"{layer_name} s2c {pt} @ {time_val}"
                    )
                want = entry["c2s"][pi]
                if want["ok"]:
                    got = layer.comp_point_to_source(pt, time=time_val)
                    assert got == pytest.approx(want["value"], abs=5e-3), (
                        f"{layer_name} c2s {pt} @ {time_val}"
                    )

    def test_default_time_is_comp_time(self) -> None:
        # The saved playhead of the fixture is 0, so the no-time call must
        # equal the explicit t=0 call (AE evaluates at the comp time).
        comp = _probe_comp(parse_project(GEOMETRY_AEP))
        assert comp.time == 0.0
        layer = _layer(comp, "solid_keyed")
        assert layer.source_point_to_comp([0.0, 0.0]) == pytest.approx(
            layer.source_point_to_comp([0.0, 0.0], time=0.0)
        )

    def test_roundtrip_inverse_2d(self) -> None:
        comp = _probe_comp(parse_project(GEOMETRY_AEP))
        layer = _layer(comp, "solid_xform")
        for pt in POINTS:
            comp_pt = layer.source_point_to_comp(pt, time=0.0)
            back = layer.comp_point_to_source(comp_pt, time=0.0)
            assert back == pytest.approx(pt, abs=1e-6)

    def test_invalid_point_raises(self) -> None:
        comp = _probe_comp(parse_project(GEOMETRY_AEP))
        layer = _layer(comp, "solid_default")
        with pytest.raises(ValueError):
            layer.source_point_to_comp([1.0, 2.0, 3.0])


class TestPointConversionsUnderCameras:
    """The four camera rigs: s2c is camera-independent, c2s is not."""

    @pytest.mark.parametrize(
        "comp_name,fixture_key",
        [
            ("CAM_ONE", "one_node"),
            ("CAM_TWO", "two_node"),
            ("CAM_KEYED", "keyed_zoom"),
            ("CAM_NONE", "no_camera"),
        ],
    )
    def test_rig_matches_ae(self, comp_name: str, fixture_key: str) -> None:
        expected = _fixture("camera_rigs_probe.json")[fixture_key]["conv"]
        project = parse_project(CAMERAS_AEP)
        comp = next(c for c in project.compositions if c.name == comp_name)
        layer = _layer(comp, "target3d")
        for time_key, entry in expected.items():
            time_val = float(time_key[1:])
            for pi, pt in enumerate(CAMERA_POINTS):
                want = entry["s2c"][pi]
                if want["ok"]:
                    got = layer.source_point_to_comp(pt, time=time_val)
                    assert got == pytest.approx(want["value"], abs=5e-3), (
                        f"{comp_name} s2c {pt} @ {time_val}"
                    )
                want = entry["c2s"][pi]
                if want["ok"]:
                    got = layer.comp_point_to_source(pt, time=time_val)
                    assert got == pytest.approx(want["value"], abs=5e-3), (
                        f"{comp_name} c2s {pt} @ {time_val}"
                    )


class TestCalculateTransformFromPoints:
    """All eleven AE-probed point sets, on 2D and 3D layers."""

    # (fixture group, key) -> (tl, tr, bl) inputs used in the probe run.
    _SQ = 141.4213562373095  # 200 * sin(45 deg)
    SETS = {
        "identity_bl": ([0, 0, 0], [200, 0, 0], [0, 100, 0]),
        "identity_br": ([0, 0, 0], [200, 0, 0], [200, 100, 0]),
        "translated": ([300, 200, 0], [500, 200, 0], [300, 300, 0]),
        "rot90": ([0, 0, 0], [0, 200, 0], [-100, 0, 0]),
        "scaled2x": ([0, 0, 0], [400, 0, 0], [0, 200, 0]),
        "tilt_y45": ([0, 0, 0], [_SQ, 0, -_SQ], [0, 100, 0]),
    }
    MIRROR_SETS = {
        "mirrorX": ([0, 0, 0], [-200, 0, 0], [0, 100, 0]),
        "mirrorY": ([0, 0, 0], [200, 0, 0], [0, -100, 0]),
        "mirrorBoth": ([0, 0, 0], [-200, 0, 0], [0, -100, 0]),
    }
    FOOTAGE_SETS = {
        "identity_srcdims": ([0, 0, 0], [640, 0, 0], [0, 346, 0]),
        "rect200x100": ([0, 0, 0], [200, 0, 0], [0, 100, 0]),
    }

    @staticmethod
    def _assert_matches(got: dict, want: dict) -> None:
        assert got["anchor_point"] == want["anchorPoint"]
        assert got["position"] == pytest.approx(want["position"], abs=1e-9)
        assert got["x_rotation"] == pytest.approx(want["xRotation"], abs=1e-4)
        assert got["y_rotation"] == pytest.approx(want["yRotation"], abs=1e-4)
        assert got["z_rotation"] == pytest.approx(want["zRotation"], abs=1e-4)
        assert got["scale"] == pytest.approx(want["scale"], abs=1e-4)

    @pytest.mark.parametrize("layer_key", ["layer2d", "layer3d"])
    def test_solid_point_sets(self, layer_key: str) -> None:
        expected = _fixture("geometry_ctfp_probe.json")[layer_key]
        comp = _probe_comp(parse_project(GEOMETRY_AEP))
        layer = _layer(comp, "solid_default" if layer_key == "layer2d" else "solid_3d")
        for key, (tl, tr, bl) in self.SETS.items():
            got = layer.calculate_transform_from_points(tl, tr, bl)
            self._assert_matches(got, expected[key]["value"])

    def test_mirrored_point_sets(self) -> None:
        expected = _fixture("geometry_ctfp_probe2.json")["solid"]
        comp = _probe_comp(parse_project(GEOMETRY_AEP))
        layer = _layer(comp, "solid_default")
        for key, (tl, tr, bl) in self.MIRROR_SETS.items():
            got = layer.calculate_transform_from_points(tl, tr, bl)
            self._assert_matches(got, expected[key]["value"])

    def test_source_dimension_divisor(self) -> None:
        # 640x346 footage: confirms the scale divisor is the SOURCE size.
        expected = _fixture("geometry_ctfp_probe2.json")["footage"]
        comp = _probe_comp(parse_project(GEOMETRY_AEP))
        layer = _layer(comp, "footage_layer")
        for key, (tl, tr, bl) in self.FOOTAGE_SETS.items():
            got = layer.calculate_transform_from_points(tl, tr, bl)
            self._assert_matches(got, expected[key]["value"])

    def test_degenerate_points_raise(self) -> None:
        comp = _probe_comp(parse_project(GEOMETRY_AEP))
        layer = _layer(comp, "solid_default")
        with pytest.raises(ValueError):
            layer.calculate_transform_from_points([0, 0, 0], [0, 0, 0], [0, 1, 0])
        with pytest.raises(ValueError):  # collinear
            layer.calculate_transform_from_points([0, 0, 0], [1, 0, 0], [2, 0, 0])


class TestSourceRectAtTime:
    """Slice 1: footage/solid/precomp rects; text/shape refuse."""

    def test_rects_match_ae(self) -> None:
        expected = _fixture("geometry_rects_probe.json")
        comp = _probe_comp(parse_project(GEOMETRY_AEP))
        for layer_name in (
            "solid_default",
            "solid_xform",
            "solid_parented",
            "solid_3d",
            "solid_keyed",
            "precomp_layer",
            "footage_layer",
        ):
            layer = _layer(comp, layer_name)
            for time_val in (0.0, 1.5, 2.5):
                for extents in (False, True):
                    suffix = "ext" if extents else "noext"
                    want = expected[layer_name][f"t{time_val:g}_{suffix}"]["value"]
                    got = layer.source_rect_at_time(time_val, extents)
                    assert got["top"] == pytest.approx(want["top"])
                    assert got["left"] == pytest.approx(want["left"])
                    assert got["width"] == pytest.approx(want["width"])
                    assert got["height"] == pytest.approx(want["height"])

    def test_text_and_shape_not_implemented(self) -> None:
        comp = _probe_comp(parse_project(GEOMETRY_AEP))
        with pytest.raises(NotImplementedError, match="text"):
            _layer(comp, "text_point").source_rect_at_time(0.0, False)
        with pytest.raises(NotImplementedError, match="shape"):
            _layer(comp, "shape_rect").source_rect_at_time(0.0, True)

    def test_invalid_args_raise(self) -> None:
        comp = _probe_comp(parse_project(GEOMETRY_AEP))
        layer = _layer(comp, "solid_default")
        with pytest.raises(TypeError):
            layer.source_rect_at_time([0.0], False)  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            layer.source_rect_at_time(0.0, "yes")  # type: ignore[arg-type]


class TestCalculateTransformFromPointsNumerics:
    """The returned transform must be finite whenever the inputs are.

    The method validates that its points are finite, and its result is
    documented as assignable to the transform properties - an `inf` scale is
    not. `_vec3_norm` computed `sqrt(x*x + y*y + z*z)`, whose intermediate
    square overflows to `inf` above ~1.34e154, so finite-but-huge points
    produced a non-finite scale.
    """

    @pytest.mark.parametrize("magnitude", [1e6, 1e100, 1e154, 1e200, 1e300])
    def test_huge_but_finite_points_give_a_finite_transform(
        self, magnitude: float
    ) -> None:
        layer = _layer(_probe_comp(parse_project(GEOMETRY_AEP)), "solid_default")
        got = layer.calculate_transform_from_points(
            [0.0, 0.0, 0.0], [magnitude, 0.0, 0.0], [0.0, magnitude, 0.0]
        )
        values = (
            list(got["anchor_point"])
            + list(got["position"])
            + list(got["scale"])
            + [got["x_rotation"], got["y_rotation"], got["z_rotation"]]
        )
        assert all(math.isfinite(v) for v in values), got

    def test_scale_is_proportional_at_huge_magnitudes(self) -> None:
        # 1e300 wide over a source `width` must scale to 1e300 / width * 100,
        # not saturate.
        layer = _layer(_probe_comp(parse_project(GEOMETRY_AEP)), "solid_default")
        got = layer.calculate_transform_from_points(
            [0.0, 0.0, 0.0], [1e300, 0.0, 0.0], [0.0, 1e300, 0.0]
        )
        assert got["scale"][0] == pytest.approx(1e300 / layer.width * 100.0)
        assert got["scale"][1] == pytest.approx(1e300 / layer.height * 100.0)
