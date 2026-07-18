"""Tests for synthesized Camera Options defaults (AE 2026 ground truth).

An untouched camera stores no Camera Options chunks; py synthesizes them.
Zoom and Focus Distance default to `comp width / 0.72` (AE's 50mm lens),
Aperture to a width-independent constant, and AE 2026 exposes two options
(Focus Area Width, Near/Far Blur Level) that AE 25 did not. All values were
probed against AE 2026 (2026-07-14) at comp widths 1920/1280/640.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import parse_project

from py_aep.models.layers import CameraLayer
from py_aep.models.properties.property import Property

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"
CAMERAS_AEP = SAMPLES_DIR / "camera_rigs.aep"
TYPE_AEP = SAMPLES_DIR / "type.aep"


def _camera(comp_name: str) -> CameraLayer:
    project = parse_project(CAMERAS_AEP)
    comp = next(c for c in project.compositions if c.name == comp_name)
    cam = next(ly for ly in comp.layers if isinstance(ly, CameraLayer))
    return cam


class TestCameraOptionDefaults:
    def _opt(self, cam: CameraLayer, match_name: str) -> Property:
        prop = cam["ADBE Camera Options Group"][match_name]
        assert isinstance(prop, Property)
        return prop

    def test_zoom_and_focus_are_width_over_072(self) -> None:
        # CAM_ONE is a 1920-wide comp with an untouched camera.
        cam = _camera("CAM_ONE")
        expected = 1920 / 0.72
        zoom = self._opt(cam, "ADBE Camera Zoom")
        focus = self._opt(cam, "ADBE Camera Focus Distance")
        assert zoom.value == pytest.approx(expected)
        assert focus.value == pytest.approx(expected)
        # An untouched default is not "modified".
        assert zoom.is_modified is False
        assert focus.is_modified is False

    def test_aperture_is_constant(self) -> None:
        cam = _camera("CAM_ONE")
        aperture = self._opt(cam, "ADBE Camera Aperture")
        assert aperture.value == pytest.approx(25.3093363329584)
        assert aperture.is_modified is False

    def test_ae26_has_fifteen_options(self) -> None:
        cam = _camera("CAM_ONE")
        options = cam["ADBE Camera Options Group"].properties
        assert len(options) == 15
        names = [p.match_name for p in options]
        assert "ADBE Camera Focus Area Width" in names
        assert "ADBE Camera Split Blur Level" in names
        # Iris Shape follows the two 2026 additions.
        assert names.index("ADBE Iris Shape") == 7

    def test_new_option_metadata_matches_ae(self) -> None:
        cam = _camera("CAM_ONE")
        focus_area = self._opt(cam, "ADBE Camera Focus Area Width")
        assert focus_area.value == pytest.approx(0.0)
        assert focus_area.has_min is True
        assert focus_area.has_max is False
        assert focus_area.can_set_expression is False

        split_blur = self._opt(cam, "ADBE Camera Split Blur Level")
        assert list(split_blur.value) == pytest.approx([100.0, 100.0])
        assert split_blur.has_max is False
        assert split_blur.can_set_expression is False
        assert split_blur.units_text == "percent"

    def test_ae25_gate_keeps_thirteen_options(self) -> None:
        # type.aep is authored by AE 25, which predates the two 2026
        # additions; min_major=26 gating must keep it at 13 options.
        project = parse_project(TYPE_AEP)
        assert project._head.ae_version_major == 25
        cam = next(
            ly
            for c in project.compositions
            for ly in c.layers
            if isinstance(ly, CameraLayer)
        )
        options = cam["ADBE Camera Options Group"].properties
        assert len(options) == 13
        names = [p.match_name for p in options]
        assert "ADBE Camera Focus Area Width" not in names
        assert "ADBE Camera Split Blur Level" not in names


class TestCameraLightTransformMetadata:
    """Transform-property metadata that AE reports specially for camera and
    light layers (probed AE 2026; separate from the Camera Options group).

    - The Z Position separation follower reads isModified True on camera and
      light layers (always positioned in depth) but False on regular layers,
      even though the follower's stored value is a placeholder 0 while the
      leader is unseparated.
    - Point of Interest (the camera anchor point) is expressionable only on a
      two-node camera (orient towards POI); a one-node camera's POI is
      inactive and non-expressionable.
    """

    GEOMETRY_AEP = SAMPLES_DIR / "geometry_probe.aep"

    def _z_follower(self, layer) -> Property:
        prop = layer.transform["ADBE Position_2"]
        assert isinstance(prop, Property)
        # These probes assume the leader is NOT dimension-separated.
        leader = layer.transform["ADBE Position"]
        assert isinstance(leader, Property)
        assert leader.dimensions_separated is False
        return prop

    def test_camera_z_position_follower_is_modified(self) -> None:
        for comp_name in ("CAM_ONE", "CAM_TWO"):
            cam = _camera(comp_name)
            assert self._z_follower(cam).is_modified is True, comp_name

    def test_regular_layer_z_follower_not_modified(self) -> None:
        # Non-regression: a normal 3D layer keeps Z follower isModified False.
        project = parse_project(self.GEOMETRY_AEP)
        comp = next(c for c in project.compositions if c.name == "PROBE_MAIN")
        solid = next(ly for ly in comp.layers if ly.name == "solid_3d")
        assert self._z_follower(solid).is_modified is False

    def test_two_node_camera_poi_expressionable(self) -> None:
        cam = _camera("CAM_TWO")
        assert cam._ldta.poi_auto_orient is True
        poi = cam.transform["ADBE Anchor Point"]
        assert isinstance(poi, Property)
        assert poi.can_set_expression is True

    def test_one_node_camera_poi_not_expressionable(self) -> None:
        cam = _camera("CAM_ONE")
        assert cam._ldta.poi_auto_orient is False
        poi = cam.transform["ADBE Anchor Point"]
        assert isinstance(poi, Property)
        assert poi.can_set_expression is False
