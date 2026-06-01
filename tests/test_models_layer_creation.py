"""Tests for CompItem layer creation methods."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from py_aep import parse as parse_aep
from py_aep.models.layers.av_layer import AVLayer
from py_aep.models.layers.camera_layer import CameraLayer
from py_aep.models.layers.light_layer import LightLayer
from py_aep.models.layers.shape_layer import ShapeLayer
from py_aep.models.layers.text_layer import TextLayer
from py_aep.models.properties.property import Property

SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "models"

# Use comp_misc.aep which has a 0-layer comp named "comment" (100x100, 1s)
EMPTY_COMP_AEP = SAMPLES_DIR / "composition" / "comp_misc.aep"


# ---------------------------------------------------------------------------
# add_null
# ---------------------------------------------------------------------------


class TestAddNull:
    def test_returns_av_layer(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_null()
        assert isinstance(layer, AVLayer)

    def test_null_layer_flag(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_null()
        assert layer.null_layer is True

    def test_auto_name(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        n1 = comp.add_null()
        n2 = comp.add_null()
        assert n1.name == "Null 1"
        assert n2.name == "Null 2"

    def test_added_at_top(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        n1 = comp.add_null()
        n2 = comp.add_null()
        assert comp.layers[0] is n2
        assert comp.layers[1] is n1

    def test_layer_count(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        assert len(comp.layers) == 0
        comp.add_null()
        assert len(comp.layers) == 1

    def test_duration_defaults_to_comp(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_null()
        assert layer.out_point == pytest.approx(comp.duration)

    def test_custom_duration(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_null(duration=0.5)
        assert layer.out_point == pytest.approx(0.5)

    def test_has_source(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_null()
        assert layer.source is not None
        assert layer.source.name == "Null 1"

    def test_unique_ids_across_layers(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        n1 = comp.add_null()
        n2 = comp.add_null()
        assert n1.id != n2.id

    def test_transform_exists(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_null()
        assert layer.transform is not None
        assert layer.transform.property("ADBE Position") is not None
        assert layer.transform.property("ADBE Opacity") is not None

    def test_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_null()
        layer_id = layer.id

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = app2.project.compositions[0]

        assert len(comp2.layers) == 1
        lyr2 = comp2.layers[0]
        assert lyr2.id == layer_id
        assert lyr2.null_layer is True
        assert lyr2.name == "Null 1"


# ---------------------------------------------------------------------------
# add_shape
# ---------------------------------------------------------------------------


class TestAddShape:
    def test_returns_shape_layer(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_shape()
        assert isinstance(layer, ShapeLayer)

    def test_auto_name(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        s1 = comp.add_shape()
        s2 = comp.add_shape()
        assert s1.name == "Shape Layer 1"
        assert s2.name == "Shape Layer 2"

    def test_added_at_top(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        s1 = comp.add_shape()
        s2 = comp.add_shape()
        assert comp.layers[0] is s2
        assert comp.layers[1] is s1

    def test_transform_exists(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_shape()
        assert layer.transform is not None

    def test_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_shape()
        layer_id = layer.id

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = app2.project.compositions[0]

        assert len(comp2.layers) == 1
        lyr2 = comp2.layers[0]
        assert lyr2.id == layer_id
        assert isinstance(lyr2, ShapeLayer)
        assert lyr2.name == "Shape Layer 1"


# ---------------------------------------------------------------------------
# add_camera
# ---------------------------------------------------------------------------


class TestAddCamera:
    def test_returns_camera_layer(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_camera("MyCam", [50, 50])
        assert isinstance(layer, CameraLayer)

    def test_auto_name(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        c1 = comp.add_camera()
        c2 = comp.add_camera()
        assert c1.name == "Camera 1"
        assert c2.name == "Camera 2"

    def test_center_point_sets_position(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        cam = comp.add_camera("Cam", [100, 200])
        pos = cast("Property", cam.transform["ADBE Position"])
        assert pos.value[2] == pytest.approx(-138.8887, rel=1e-3)

    def test_center_point_sets_anchor(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        cam = comp.add_camera("Cam", [100, 200])
        anchor = cast("Property", cam.transform["ADBE Anchor Point"])
        assert anchor.value[0] == pytest.approx(100.0)
        assert anchor.value[1] == pytest.approx(200.0)

    def test_default_center_point(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        cam = comp.add_camera("Cam")
        anchor = cast("Property", cam.transform["ADBE Anchor Point"])
        assert anchor.value[0] == pytest.approx(comp.width / 2)
        assert anchor.value[1] == pytest.approx(comp.height / 2)

    def test_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        cam = comp.add_camera("TestCam", [50, 50])
        cam_id = cam.id

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = app2.project.compositions[0]

        assert len(comp2.layers) == 1
        lyr2 = comp2.layers[0]
        assert lyr2.id == cam_id
        assert isinstance(lyr2, CameraLayer)
        assert lyr2.name == "TestCam"


# ---------------------------------------------------------------------------
# add_light
# ---------------------------------------------------------------------------


class TestAddLight:
    def test_returns_light_layer(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_light("MyLight", [50, 50])
        assert isinstance(layer, LightLayer)

    def test_auto_name(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        l1 = comp.add_light()
        l2 = comp.add_light()
        assert l1.name == "Light 1"
        assert l2.name == "Light 2"

    def test_center_point_sets_position(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        light = comp.add_light("L", [300, 400])
        pos = cast("Property", light.transform["ADBE Position"])
        assert pos.value[2] == pytest.approx(-69.4444, rel=1e-3)

    def test_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        light = comp.add_light("TestLight", [50, 50])
        light_id = light.id

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = app2.project.compositions[0]

        assert len(comp2.layers) == 1
        lyr2 = comp2.layers[0]
        assert lyr2.id == light_id
        assert isinstance(lyr2, LightLayer)
        assert lyr2.name == "TestLight"


# ---------------------------------------------------------------------------
# add_solid
# ---------------------------------------------------------------------------


class TestAddSolid:
    def test_returns_av_layer(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_solid([1.0, 0.0, 0.0], "RedSolid")
        assert isinstance(layer, AVLayer)

    def test_name(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_solid([0.0, 1.0, 0.0], "GreenSolid")
        assert layer.name == "GreenSolid"

    def test_dimensions_default_to_comp(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_solid([0.0, 0.0, 1.0], "BlueSolid")
        assert layer.width == comp.width
        assert layer.height == comp.height

    def test_custom_dimensions(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_solid([1.0, 1.0, 0.0], "YellowSolid", 640, 480)
        assert layer.width == 640
        assert layer.height == 480

    def test_source_color(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_solid([1.0, 0.5, 0.0], "OrangeSolid")
        from py_aep.models.sources.solid import SolidSource

        assert isinstance(layer.source.main_source, SolidSource)
        color = layer.source.main_source.color
        assert color[0] == pytest.approx(1.0)
        assert color[1] == pytest.approx(0.5)
        assert color[2] == pytest.approx(0.0)

    def test_invalid_color_raises(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        with pytest.raises(ValueError):
            comp.add_solid([2.0, 0.0, 0.0], "BadColor")

    def test_solid_in_solids_folder(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_solid([0.0, 0.0, 0.0], "BlackSolid")
        solids_folder = None
        for item in app.project.root_folder.items:
            if item.name == "Solids":
                solids_folder = item
                break
        assert solids_folder is not None
        assert layer.source in solids_folder.items

    def test_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_solid([1.0, 0.0, 0.0], "RedSolid", 200, 200)
        layer_id = layer.id

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = app2.project.compositions[0]

        assert len(comp2.layers) == 1
        lyr2 = comp2.layers[0]
        assert lyr2.id == layer_id
        assert isinstance(lyr2, AVLayer)
        assert lyr2.name == "RedSolid"
        assert lyr2.width == 200
        assert lyr2.height == 200


# ---------------------------------------------------------------------------
# add (generic item)
# ---------------------------------------------------------------------------


class TestAddItem:
    def test_add_comp_as_layer(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        other_comp = app.project.compositions[1]
        layer = comp.add(other_comp)
        assert isinstance(layer, AVLayer)
        assert layer.source is other_comp

    def test_add_invalid_item_raises(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        with pytest.raises(ValueError):
            comp.add(app.project.root_folder)  # type: ignore[arg-type]

    def test_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        other_comp = app.project.compositions[1]
        layer = comp.add(other_comp)
        layer_id = layer.id

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = app2.project.compositions[0]

        assert len(comp2.layers) == 1
        lyr2 = comp2.layers[0]
        assert lyr2.id == layer_id
        assert isinstance(lyr2, AVLayer)


# ---------------------------------------------------------------------------
# Mixed creation
# ---------------------------------------------------------------------------


class TestMixedLayerCreation:
    def test_multiple_types_in_one_comp(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]

        null = comp.add_null()
        solid = comp.add_solid([1.0, 0.0, 0.0], "Red", 100, 100)
        cam = comp.add_camera("Cam", [50, 50])
        light = comp.add_light("Light", [50, 50])
        shape = comp.add_shape()

        assert len(comp.layers) == 5
        # Newest at top
        assert comp.layers[0] is shape
        assert comp.layers[1] is light
        assert comp.layers[2] is cam
        assert comp.layers[3] is solid
        assert comp.layers[4] is null

    def test_unique_ids(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layers = [
            comp.add_null(),
            comp.add_solid([0.0, 0.0, 0.0], "Black", 100, 100),
            comp.add_camera("Cam", [50, 50]),
            comp.add_light("Light", [50, 50]),
            comp.add_shape(),
        ]
        ids = [lyr.id for lyr in layers]
        assert len(set(ids)) == len(ids)

    def test_multiple_types_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]

        null = comp.add_null()
        solid = comp.add_solid([1.0, 0.0, 0.0], "Red", 100, 100)
        cam = comp.add_camera("Cam", [50, 50])
        light = comp.add_light("Light", [50, 50])
        shape = comp.add_shape()

        ids = [shape.id, light.id, cam.id, solid.id, null.id]

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = app2.project.compositions[0]

        assert len(comp2.layers) == 5
        roundtrip_ids = [lyr.id for lyr in comp2.layers]
        assert roundtrip_ids == ids

    def test_add_to_comp_with_existing_layers(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "layer" / "layer_misc.aep")
        comp = app.project.compositions[0]
        original_count = len(comp.layers)
        assert original_count == 1

        new_layer = comp.add_null()
        assert len(comp.layers) == 2
        assert comp.layers[0] is new_layer

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = app2.project.compositions[0]
        assert len(comp2.layers) == 2
        assert comp2.layers[0].null_layer is True


# ---------------------------------------------------------------------------
# add_text
# ---------------------------------------------------------------------------


class TestAddText:
    def test_returns_text_layer(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_text("Hello")
        assert isinstance(layer, TextLayer)

    def test_text_content(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_text("Hello World")
        st = layer.text.property("ADBE Text Document")
        assert isinstance(st, Property)
        assert st.value is not None
        assert st.value.text == "Hello World"

    def test_auto_name_when_empty(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        t1 = comp.add_text()
        t2 = comp.add_text()
        assert t1.name == "Text 1"
        assert t2.name == "Text 2"

    def test_name_from_text(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_text("My Title")
        assert layer.name == "My Title"

    def test_default_font_size(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_text("Test")
        st = layer.text.property("ADBE Text Document")
        assert st.value.font_size == pytest.approx(36.0)

    def test_custom_font_size(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_text("Big Text", font_size=72.0)
        st = layer.text.property("ADBE Text Document")
        assert st.value.font_size == pytest.approx(72.0)

    def test_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_text("Hello World")
        layer_id = layer.id

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = app2.project.compositions[0]

        assert len(comp2.layers) == 1
        lyr2 = comp2.layers[0]
        assert lyr2.id == layer_id
        assert isinstance(lyr2, TextLayer)
        st = lyr2.text.property("ADBE Text Document")
        assert st.value.text == "Hello World"

    def test_roundtrip_custom_font_size(self, tmp_path: Path) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        comp.add_text("Sized", font_size=48.0)

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = app2.project.compositions[0]

        st = comp2.layers[0].text.property("ADBE Text Document")
        assert st.value.font_size == pytest.approx(48.0)


# ---------------------------------------------------------------------------
# add_box_text
# ---------------------------------------------------------------------------


class TestAddBoxText:
    def test_returns_text_layer(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_box_text([400, 200], "Box")
        assert isinstance(layer, TextLayer)

    def test_text_content(self) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_box_text([400, 200], "Paragraph Text")
        st = layer.text.property("ADBE Text Document")
        assert st.value.text == "Paragraph Text"

    def test_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(EMPTY_COMP_AEP)
        comp = app.project.compositions[0]
        layer = comp.add_box_text([400, 200], "Box Text")
        layer_id = layer.id

        app.project.save(tmp_path / "out.aep")
        app2 = parse_aep(tmp_path / "out.aep")
        comp2 = app2.project.compositions[0]

        assert len(comp2.layers) == 1
        lyr2 = comp2.layers[0]
        assert lyr2.id == layer_id
        assert isinstance(lyr2, TextLayer)
        st = lyr2.text.property("ADBE Text Document")
        assert st.value.text == "Box Text"
