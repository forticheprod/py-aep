"""Read-only tests for variable-font support (AE 2026 fixtures)."""

from __future__ import annotations

from pathlib import Path

from helpers import get_comp, parse_project

from py_aep.enums import VariableFontSpacing

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"


def _vf_layer(name: str):
    project = parse_project(SAMPLES_DIR / name)
    return get_comp(project, "vf").layers[0]


def _animator_props(layer):
    animators = layer["ADBE Text Properties"]["ADBE Text Animators"]
    return animators.properties[0]["ADBE Text Animator Properties"]


class TestFontObjectVariable:
    def test_design_vector_default_instance(self) -> None:
        font = _vf_layer("variable_font_static.aep").text.source_text.value.font_object
        assert font.design_vector == [400.0, 100.0]
        assert font.has_design_axes is True
        assert font.family_prefix == "Bahnschrift"

    def test_design_vector_named_instance(self) -> None:
        font = _vf_layer(
            "variable_font_instance.aep"
        ).text.source_text.value.font_object
        assert font.post_script_name == "Bahnschrift-BoldSemiCondensed"
        assert font.design_vector == [700.0, 87.5]
        assert font.family_prefix == "Bahnschrift"

    def test_non_variable_font(self) -> None:
        project = parse_project(SAMPLES_DIR / "threeDPerChar_on.aep")
        font = project.compositions[0].layers[0].text.source_text.value.font_object
        assert font.design_vector is None
        assert font.has_design_axes is False
        assert font.family_prefix is None


class TestVariableFontAxisProperty:
    def test_static_axis(self) -> None:
        props = _animator_props(_vf_layer("variable_font_axis_static.aep"))
        axis = props["ADBE Text VF Axis 1"]
        assert axis.value == 700.0
        assert axis.axis_tag == "wght"
        assert axis.name == "Font Axis Weight"
        assert axis.min_value == 300.0
        assert axis.max_value == 700.0

    def test_animated_axis_scalar_keyframes(self) -> None:
        props = _animator_props(_vf_layer("variable_font_axis_animated.aep"))
        wght = props["ADBE Text VF Axis 1"]
        assert [kf.value for kf in wght.keyframes] == [300.0, 700.0]
        assert wght.axis_tag == "wght"
        wdth = props["ADBE Text VF Axis 2"]
        assert wdth.value == 80.0
        assert wdth.axis_tag == "wdth"
        assert wdth.name == "Font Axis Width"

    def test_unused_slot(self) -> None:
        props = _animator_props(_vf_layer("variable_font_axis_animated.aep"))
        slot = props["ADBE Text VF Axis 3"]
        assert slot.axis_tag is None
        assert slot.name == ""

    def test_axis_tag_none_for_regular_property(self) -> None:
        layer = _vf_layer("variable_font_axis_static.aep")
        opacity = layer.transform.property("ADBE Opacity")
        assert opacity.axis_tag is None


class TestVariableFontSpacing:
    def test_spacing_value_enum(self) -> None:
        layer = _vf_layer("variable_font_spacing.aep")
        prop = layer["ADBE Text Properties"]["ADBE Text More Options"][
            "ADBE Text Variable Font Spacing"
        ]
        assert prop.name == "Variable Font Spacing"
        assert VariableFontSpacing(prop.value) == VariableFontSpacing.PER_CHARACTER

    def test_spacing_default(self) -> None:
        layer = _vf_layer("variable_font_axis_static.aep")
        prop = layer["ADBE Text Properties"]["ADBE Text More Options"][
            "ADBE Text Variable Font Spacing"
        ]
        assert VariableFontSpacing(prop.value) == VariableFontSpacing.ADAPTIVE


class TestValueText:
    def test_value_text_none_without_dropdown_parameters(self) -> None:
        layer = _vf_layer("variable_font_axis_static.aep")
        opacity = layer.transform.property("ADBE Opacity")
        assert opacity.value_text is None
