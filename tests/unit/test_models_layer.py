"""Tests for Layer model parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep import parse as parse_aep
from py_aep.models import Layer, Property

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"
BUGS_DIR = Path(__file__).parent.parent.parent / "samples" / "bugs"
VERSIONS_DIR = Path(__file__).parent.parent.parent / "samples" / "versions"
VIEW_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "view"


class TestAutoName:
    """Tests for auto_name helper."""

    def test_trailing_number(self) -> None:
        from py_aep.models.naming import auto_name

        assert auto_name("Light 1", set()) == "Light 1"
        assert auto_name("Layer 99", set()) == "Layer 1"
        assert auto_name("abc3", set()) == "abc1"

    def test_no_trailing_number(self) -> None:
        from py_aep.models.naming import auto_name

        assert auto_name("MyLayer", set()) == "MyLayer 1"
        assert auto_name("Solid", set()) == "Solid 1"
        assert auto_name("Solid", {"Solid"}) == "Solid 2"

    def test_only_number(self) -> None:
        from py_aep.models.naming import auto_name

        assert auto_name("42", set()) == "1"

    def test_skips_existing_names(self) -> None:
        from py_aep.models.naming import auto_name

        existing = {"layer1", "layer2", "layer3"}
        assert auto_name("layer1", existing) == "layer4"

    def test_skips_existing_no_trailing_number(self) -> None:
        from py_aep.models.naming import auto_name

        existing = {"Solid", "Solid 2", "Solid 3"}
        assert auto_name("Solid", existing) == "Solid 4"
        assert auto_name("Solid 1", existing) == "Solid 4"

    def test_uses_max_suffix(self) -> None:
        from py_aep.models.naming import auto_name

        existing = {"Comp 1", "Comp 4"}
        assert auto_name("Comp 1", existing) == "Comp 5"

    def test_gap_not_filled(self) -> None:
        from py_aep.models.naming import auto_name

        existing = {"Layer 1", "Layer 5"}
        assert auto_name("Layer 1", existing) == "Layer 6"


def _layer(path: Path, comp_name: str, layer_name: str) -> Layer:
    project = parse_aep(path).project
    comp = next(c for c in project.compositions if c.name == comp_name)
    return next(layer for layer in comp.layers if layer.name == layer_name)


def _position(layer: Layer) -> Property:
    position = layer.property("ADBE Transform Group").property("ADBE Position")
    assert isinstance(position, Property)
    return position


class TestCameraLightDefaultPosition:
    """A camera or light Position at its default, which AE leaves out of the file.

    `camera_default_position.aep` was built in AE 2026 and read back via
    ExtendScript. Each 1440x810 comp holds a camera whose Zoom was set to 1000
    (the comp's default is 2000) and whose Position was then set: to
    [720, 405, -1000] in `zoom_1000` and `zoom_keyed`, which AE drops from the
    file, and to [720, 405, -2600] in `moved`. `zoom_keyed` keys the Zoom from
    1000 to 3000 afterwards. AE places a dropped Position from the camera's
    Zoom at time 0, not the comp's default zoom.
    """

    @pytest.mark.parametrize("comp_name", ["zoom_1000", "zoom_keyed"])
    def test_camera_position_left_out_follows_zoom(self, comp_name: str) -> None:
        camera = _layer(
            SAMPLES_DIR / "camera_default_position.aep", comp_name, "Camera"
        )
        position = _position(camera)
        assert position.value == pytest.approx([720.0, 405.0, -1000.0])
        assert position.default_value == pytest.approx([720.0, 405.0, -1000.0])
        assert not position.is_modified

    def test_camera_position_moved_off_default(self) -> None:
        camera = _layer(SAMPLES_DIR / "camera_default_position.aep", "moved", "Camera")
        position = _position(camera)
        assert position.value == pytest.approx([720.0, 405.0, -2600.0])
        assert position.default_value == pytest.approx([720.0, 405.0, -1000.0])
        assert position.is_modified

    def test_camera_with_default_zoom(self) -> None:
        # Zoom and Position are both absent here; the 1920x107 comp's 10:11
        # pixel aspect makes the default zoom 2424.24 rather than 2666.67.
        # ExtendScript: [960, 53.5, -2424.24242418], isModified false.
        camera = _layer(VIEW_DIR / "draft3d_false.aep", "Comp 1", "Camera 1")
        position = _position(camera)
        assert position.value == pytest.approx([960.0, 53.5, -2424.24242418])
        assert not position.is_modified

    def test_light_default_position(self) -> None:
        # A light's default is up, right and in front of the comp centre at
        # fixed fractions of the comp's default camera zoom (2666.67 here).
        # ExtendScript reports this one, stored at the default, as unmodified.
        light = _layer(
            SAMPLES_DIR / "light_source_default.aep", "crystal", "Environment Light 1"
        )
        position = _position(light)
        assert position.default_value == pytest.approx([1040.0, 460.0, -2000.0 / 3])
        assert position.value == pytest.approx(position.default_value)
        assert not position.is_modified
