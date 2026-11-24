"""Tests for a camera or light Position at its default (AE 2026 ground truth).

After Effects leaves a camera or light Position that sits at its default out
of the file. A camera's default is `[w/2, h/2, -zoom]`, `zoom` its own Zoom at
the layer's time 0; a light's is `[w/2 + 0.03 z, h/2 - 0.03 z, -z/4]`, `z`
the comp's default camera zoom. The X / Y / Z separation followers default to
the leader's components, so separating a Position left at its default reads
all three unmodified.

`camera_default_position.aep`: each 1440x810 comp holds a two-node camera
whose Zoom was set to 1000 (the comp's default is 2000) and whose Position
was then set to [720, 405, -1000], which AE drops, except in `moved`
([720, 405, -2600]). `zoom_keyed` keys the Zoom from 1000 to 3000 afterwards
and `zoom_1000_separated` separates the dropped Position.

`light_default_position.aep`: one comp per size and pixel aspect, each holding
every light type reset to its default Position (Layer > Transform > Reset),
plus a Point light whose default Position was then separated. A scripted
`addLight` does not place a light there, so the reset is what pins it. The
layer named `Environment` is an Ambient light (its ExtendScript JSON reports
`lightType` Ambient); `light_source_default.aep` holds an Environment one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import get_comp, get_comp_from_json_by_name, load_expected, parse_project

from py_aep.models.layers import Layer
from py_aep.models.properties.property import Property
from py_aep.resolvers.transform import default_camera_zoom

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"
VIEW_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "view"

_POSITION_MATCH_NAMES = (
    "ADBE Position",
    "ADBE Position_0",
    "ADBE Position_1",
    "ADBE Position_2",
)

_CAMERA_COMPS = ["moved", "zoom_1000", "zoom_1000_separated", "zoom_keyed"]
_LIGHT_COMPS = [
    "1920x1080",
    "1440x1620",
    "2880x810",
    "810x1440",
    "1920x1080_par2",
    "1440x810_par05",
]
_LIGHT_LAYERS = [
    "Point",
    "Spot",
    "Parallel",
    "Ambient",
    "Environment",
    "Point Separated",
]


def _layer(sample: str, comp_name: str, layer_name: str) -> Layer:
    comp = get_comp(parse_project(SAMPLES_DIR / f"{sample}.aep"), comp_name)
    return next(layer for layer in comp.layers if layer.name == layer_name)


def _position(layer: Layer, match_name: str = "ADBE Position") -> Property:
    prop = layer.transform[match_name]
    assert isinstance(prop, Property)
    return prop


def _expected_transform(sample: str, comp_name: str, layer_name: str) -> dict:
    expected = load_expected(SAMPLES_DIR, sample)
    comp_json = get_comp_from_json_by_name(expected, comp_name)
    layer_json = next(ly for ly in comp_json["layers"] if ly["name"] == layer_name)
    group = next(
        p for p in layer_json["properties"] if p["matchName"] == "ADBE Transform Group"
    )
    return {p["matchName"]: p for p in group["properties"]}


def _assert_matches_json(sample: str, comp_name: str, layer_name: str) -> None:
    layer = _layer(sample, comp_name, layer_name)
    expected = _expected_transform(sample, comp_name, layer_name)
    for match_name in _POSITION_MATCH_NAMES:
        prop = _position(layer, match_name)
        prop_json = expected[match_name]
        assert prop.value == pytest.approx(prop_json["value"]), match_name
        assert prop.is_modified == prop_json["isModified"], match_name
    leader_json = expected["ADBE Position"]
    assert _position(layer).dimensions_separated == leader_json["dimensionsSeparated"]


class TestCameraDefaultPosition:
    @pytest.mark.parametrize("comp_name", _CAMERA_COMPS)
    def test_position_and_followers_match_json(self, comp_name: str) -> None:
        _assert_matches_json("camera_default_position", comp_name, "Camera")

    @pytest.mark.parametrize(
        "comp_name", ["zoom_1000", "zoom_keyed", "zoom_1000_separated"]
    )
    def test_default_follows_zoom(self, comp_name: str) -> None:
        # AE places a dropped Position from the camera's Zoom at time 0, not
        # the comp's default zoom (-2000), also once the Zoom is keyed.
        camera = _layer("camera_default_position", comp_name, "Camera")
        assert _position(camera).default_value == pytest.approx([720.0, 405.0, -1000.0])

    def test_separated_followers_default_to_leader(self) -> None:
        camera = _layer("camera_default_position", "zoom_1000_separated", "Camera")
        defaults = [
            _position(camera, f"ADBE Position_{dim}").default_value for dim in range(3)
        ]
        assert defaults == pytest.approx([720.0, 405.0, -1000.0])

    def test_moved_off_default(self) -> None:
        camera = _layer("camera_default_position", "moved", "Camera")
        position = _position(camera)
        assert position.default_value == pytest.approx([720.0, 405.0, -1000.0])

    def test_camera_with_default_zoom(self) -> None:
        # Zoom and Position are both absent here; the 1920x107 comp's 10:11
        # pixel aspect makes the default zoom 2424.24 rather than 2666.67.
        # ExtendScript: [960, 53.5, -2424.24242418], isModified false.
        comp = get_comp(parse_project(VIEW_DIR / "draft3d_false.aep"), "Comp 1")
        camera = next(layer for layer in comp.layers if layer.name == "Camera 1")
        position = _position(camera)
        assert position.value == pytest.approx([960.0, 53.5, -2424.24242418])
        assert not position.is_modified


class TestLightDefaultPosition:
    @pytest.mark.parametrize("layer_name", _LIGHT_LAYERS)
    @pytest.mark.parametrize("comp_name", _LIGHT_COMPS)
    def test_position_and_followers_match_json(
        self, comp_name: str, layer_name: str
    ) -> None:
        _assert_matches_json("light_default_position", comp_name, layer_name)

    @pytest.mark.parametrize("comp_name", _LIGHT_COMPS)
    def test_default_value(self, comp_name: str) -> None:
        light = _layer("light_default_position", comp_name, "Point")
        comp = light.containing_comp
        zoom = default_camera_zoom(comp.width, comp.pixel_aspect)
        expected = [
            comp.width / 2 + 0.03 * zoom,
            comp.height / 2 - 0.03 * zoom,
            -zoom / 4,
        ]
        assert _position(light).default_value == pytest.approx(expected)

    @pytest.mark.parametrize("comp_name", _LIGHT_COMPS)
    def test_separated_followers_default_to_leader(self, comp_name: str) -> None:
        light = _layer("light_default_position", comp_name, "Point Separated")
        defaults = [
            _position(light, f"ADBE Position_{dim}").default_value for dim in range(3)
        ]
        assert defaults == pytest.approx(_position(light).default_value)

    def test_environment_light_stored_at_default(self) -> None:
        # This light's Position is stored at its default rather than left out;
        # ExtendScript reports it unmodified all the same.
        comp = get_comp(
            parse_project(SAMPLES_DIR / "light_source_default.aep"), "crystal"
        )
        light = next(ly for ly in comp.layers if ly.name == "Environment Light 1")
        position = _position(light)
        assert position.default_value == pytest.approx([1040.0, 460.0, -2000.0 / 3])
        assert position.value == pytest.approx(position.default_value)
        assert not position.is_modified
