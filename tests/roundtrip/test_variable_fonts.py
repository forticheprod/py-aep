"""Roundtrip tests for variable-font mutations.

`add_variable_font_axis` reads the axis metadata from the installed font
file with fontTools; tests needing the Bahnschrift variable font skip
when it is not installed (e.g. non-Windows CI).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import get_comp

from py_aep import parse as parse_aep
from py_aep.svg.fonts import resolve_font_exact

SAMPLES = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"

_BAHNSCHRIFT = resolve_font_exact("Bahnschrift")

needs_bahnschrift = pytest.mark.skipif(
    _BAHNSCHRIFT is None, reason="Bahnschrift variable font not installed"
)


def _fresh_vf():
    app = parse_aep(str(SAMPLES / "variable_font_static.aep"))
    layer = get_comp(app.project, "vf").layers[0]
    animators = layer["ADBE Text Properties"]["ADBE Text Animators"]
    animator = animators.add_property("ADBE Text Animator")
    return app, animator["ADBE Text Animator Properties"]


class TestAddVariableFontAxis:
    @needs_bahnschrift
    def test_add_axis_roundtrip(self, tmp_path: Path) -> None:
        app, props = _fresh_vf()
        axis = props.add_variable_font_axis("wght")
        # Bounds, default value and display name come from the font file.
        assert axis.axis_tag == "wght"
        assert axis.name == "Font Axis Weight"
        assert axis.value == 400.0
        assert axis.min_value == 300.0
        assert axis.max_value == 700.0
        axis.value = 700.0

        out = tmp_path / "axis.aep"
        app.project.save(out)
        app2 = parse_aep(str(out))
        props2 = (
            get_comp(app2.project, "vf")
            .layers[0]["ADBE Text Properties"]["ADBE Text Animators"]
            .properties[0]["ADBE Text Animator Properties"]
        )
        axis2 = props2["ADBE Text VF Axis 1"]
        assert axis2.axis_tag == "wght"
        assert axis2.name == "Font Axis Weight"
        assert axis2.value == 700.0
        assert (axis2.min_value, axis2.max_value) == (300.0, 700.0)

    @needs_bahnschrift
    def test_add_axis_animated_roundtrip(self, tmp_path: Path) -> None:
        app, props = _fresh_vf()
        wght = props.add_variable_font_axis("wght")
        wght.set_value_at_time(0.0, 300.0)
        wght.set_value_at_time(2.0, 700.0)
        wdth = props.add_variable_font_axis("wdth")
        wdth.value = 80.0

        out = tmp_path / "axis_anim.aep"
        app.project.save(out)
        app2 = parse_aep(str(out))
        props2 = (
            get_comp(app2.project, "vf")
            .layers[0]["ADBE Text Properties"]["ADBE Text Animators"]
            .properties[0]["ADBE Text Animator Properties"]
        )
        wght2 = props2["ADBE Text VF Axis 1"]
        assert [kf.value for kf in wght2.keyframes] == [300.0, 700.0]
        assert wght2.axis_tag == "wght"
        wdth2 = props2["ADBE Text VF Axis 2"]
        assert wdth2.value == 80.0
        assert wdth2.axis_tag == "wdth"

    @needs_bahnschrift
    def test_remove_all_keys_restores_static(self, tmp_path: Path) -> None:
        app, props = _fresh_vf()
        wght = props.add_variable_font_axis("wght")
        wght.set_value_at_time(0.0, 300.0)
        wght.set_value_at_time(2.0, 700.0)
        wght.remove_all_keys()
        assert wght.keyframes == []
        assert wght.axis_tag == "wght"

        out = tmp_path / "deanimated.aep"
        app.project.save(out)
        app2 = parse_aep(str(out))
        props2 = (
            get_comp(app2.project, "vf")
            .layers[0]["ADBE Text Properties"]["ADBE Text Animators"]
            .properties[0]["ADBE Text Animator Properties"]
        )
        wght2 = props2["ADBE Text VF Axis 1"]
        assert wght2.keyframes == []
        assert wght2.axis_tag == "wght"
        assert wght2.value == 300.0

    @needs_bahnschrift
    def test_same_tag_returns_existing_slot(self) -> None:
        _, props = _fresh_vf()
        first = props.add_variable_font_axis("wght")
        again = props.add_variable_font_axis("wght")
        assert again is first

    @needs_bahnschrift
    def test_unknown_tag_raises(self) -> None:
        _, props = _fresh_vf()
        with pytest.raises(ValueError, match="no 'XXXX' axis"):
            props.add_variable_font_axis("XXXX")

    def test_bad_tag_length_raises(self) -> None:
        _, props = _fresh_vf()
        with pytest.raises(ValueError):
            props.add_variable_font_axis("weight")

    def test_wrong_group_raises(self) -> None:
        app = parse_aep(str(SAMPLES / "variable_font_static.aep"))
        layer = get_comp(app.project, "vf").layers[0]
        with pytest.raises(ValueError):
            layer.transform.add_variable_font_axis("wght")

    @needs_bahnschrift
    def test_setting_value_preserves_tag(self, tmp_path: Path) -> None:
        app, props = _fresh_vf()
        axis = props.add_variable_font_axis("wdth")
        axis.value = 90.0
        out = tmp_path / "tag_kept.aep"
        app.project.save(out)
        app2 = parse_aep(str(out))
        props2 = (
            get_comp(app2.project, "vf")
            .layers[0]["ADBE Text Properties"]["ADBE Text Animators"]
            .properties[0]["ADBE Text Animator Properties"]
        )
        axis2 = props2["ADBE Text VF Axis 1"]
        assert axis2.value == 90.0
        assert axis2.axis_tag == "wdth"


class TestValueTextDropdown:
    def test_value_text_for_custom_dropdown(self) -> None:
        app = parse_aep(str(SAMPLES.parent / "property" / "2_gaussian.aep"))
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        fx = layer.effects.add_property("ADBE Dropdown Control")
        menu = fx.property("Menu")
        assert menu.property_parameters == ["Item 1", "Item 2", "Item 3"]
        assert menu.value_text == "Item 1"
        menu.value = 3
        assert menu.value_text == "Item 3"
