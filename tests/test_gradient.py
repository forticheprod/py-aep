"""Tests for gradient color property parsing."""

from __future__ import annotations

import pytest

from py_aep import parse
from py_aep.models.properties.gradient import (
    Gradient,
    GradientAlphaStop,
    GradientColorStop,
)
from py_aep.parsers.gradient import parse_gradient_xml

SAMPLE = "samples/models/property/gradient.aep"


class _FakeUtf8:
    """Minimal stand-in for Utf8Chunk in parser unit tests."""

    def __init__(self, value: str) -> None:
        self.value = value


# --- XML parser unit tests ---


SAMPLE_XML = """\
<prop.map version="4">
  <prop.list>
    <prop.pair>
      <key>Gradient Color Data</key>
      <prop.list>
        <prop.pair>
          <key>Color Stops</key>
          <prop.list>
            <prop.pair>
              <key>Stops List</key>
              <prop.list>
                <prop.pair>
                  <key>Stop-0</key>
                  <prop.list>
                    <prop.pair>
                      <key>Stops Color</key>
                      <array>
                        <float>0</float>
                        <float>0.5</float>
                        <float>1</float>
                        <float>0</float>
                        <float>0</float>
                        <float>1</float>
                      </array>
                    </prop.pair>
                  </prop.list>
                </prop.pair>
                <prop.pair>
                  <key>Stop-1</key>
                  <prop.list>
                    <prop.pair>
                      <key>Stops Color</key>
                      <array>
                        <float>1</float>
                        <float>0.5</float>
                        <float>0</float>
                        <float>0</float>
                        <float>0</float>
                        <float>1</float>
                      </array>
                    </prop.pair>
                  </prop.list>
                </prop.pair>
              </prop.list>
            </prop.pair>
          </prop.list>
        </prop.pair>
        <prop.pair>
          <key>Alpha Stops</key>
          <prop.list>
            <prop.pair>
              <key>Stops List</key>
              <prop.list>
                <prop.pair>
                  <key>Stop-0</key>
                  <prop.list>
                    <prop.pair>
                      <key>Stops Alpha</key>
                      <array>
                        <float>0</float>
                        <float>0.5</float>
                        <float>1</float>
                      </array>
                    </prop.pair>
                  </prop.list>
                </prop.pair>
                <prop.pair>
                  <key>Stop-1</key>
                  <prop.list>
                    <prop.pair>
                      <key>Stops Alpha</key>
                      <array>
                        <float>1</float>
                        <float>0.5</float>
                        <float>1</float>
                      </array>
                    </prop.pair>
                  </prop.list>
                </prop.pair>
              </prop.list>
            </prop.pair>
          </prop.list>
        </prop.pair>
      </prop.list>
    </prop.pair>
    <prop.pair>
      <key>Gradient Colors</key>
      <string>1.0</string>
    </prop.pair>
  </prop.list>
</prop.map>
"""


def test_parse_gradient_xml_color_stops() -> None:
    result = parse_gradient_xml(_FakeUtf8(SAMPLE_XML))  # type: ignore[arg-type]
    assert result is not None
    assert len(result.color_stops) == 2
    assert result.color_stops[0] == GradientColorStop(
        offset=0.0, midpoint=0.5, color=(1.0, 0.0, 0.0)
    )
    assert result.color_stops[1] == GradientColorStop(
        offset=1.0, midpoint=0.5, color=(0.0, 0.0, 0.0)
    )


def test_parse_gradient_xml_alpha_stops() -> None:
    result = parse_gradient_xml(_FakeUtf8(SAMPLE_XML))  # type: ignore[arg-type]
    assert result is not None
    assert len(result.alpha_stops) == 2
    assert result.alpha_stops[0] == GradientAlphaStop(
        offset=0.0, midpoint=0.5, alpha=1.0
    )
    assert result.alpha_stops[1] == GradientAlphaStop(
        offset=1.0, midpoint=0.5, alpha=1.0
    )


def test_parse_gradient_xml_version() -> None:
    result = parse_gradient_xml(_FakeUtf8(SAMPLE_XML))  # type: ignore[arg-type]
    assert result is not None
    assert result.version == "1.0"


def test_parse_gradient_xml_empty() -> None:
    assert parse_gradient_xml(_FakeUtf8("")) is None  # type: ignore[arg-type]


def test_parse_gradient_xml_invalid() -> None:
    assert parse_gradient_xml(_FakeUtf8("<not valid/>")) is None  # type: ignore[arg-type]


# --- Integration tests with sample .aep ---


@pytest.fixture()
def gradient_comp():
    app = parse(SAMPLE)
    return next(v for v in app.project.items.values() if hasattr(v, "layers"))


def test_g_fill_gradient_colors(gradient_comp) -> None:
    layer = gradient_comp.layers[0]
    contents = layer.property("ADBE Root Vectors Group")
    gfill = contents.property("ADBE Vector Graphic - G-Fill")
    colors = gfill.property("ADBE Vector Grad Colors")

    assert colors.match_name == "ADBE Vector Grad Colors"
    assert colors.name == "Colors"

    gd = colors.value
    assert isinstance(gd, Gradient)
    assert len(gd.color_stops) == 2
    assert len(gd.alpha_stops) == 2
    # Non-default values set in the sample
    assert gd.color_stops[0].offset == pytest.approx(0.065, abs=0.001)
    assert gd.alpha_stops[0].alpha == pytest.approx(0.83, abs=0.01)


def test_g_stroke_gradient_colors(gradient_comp) -> None:
    layer = gradient_comp.layers[0]
    contents = layer.property("ADBE Root Vectors Group")
    gstroke = contents.property("ADBE Vector Graphic - G-Stroke")
    colors = gstroke.property("ADBE Vector Grad Colors")

    gd = colors.value
    assert isinstance(gd, Gradient)
    assert len(gd.color_stops) >= 2


def test_g_fill_synthesized_properties(gradient_comp) -> None:
    """G-Fill has all expected properties from synthesis specs."""
    layer = gradient_comp.layers[0]
    contents = layer.property("ADBE Root Vectors Group")
    gfill = contents.property("ADBE Vector Graphic - G-Fill")

    expected_match_names = [
        "ADBE Vector Blend Mode",
        "ADBE Vector Composite Order",
        "ADBE Vector Fill Rule",
        "ADBE Vector Grad Type",
        "ADBE Vector Grad Start Pt",
        "ADBE Vector Grad End Pt",
        "ADBE Vector Grad HiLite Length",
        "ADBE Vector Grad HiLite Angle",
        "ADBE Vector Grad Colors",
        "ADBE Vector Fill Opacity",
    ]
    actual = [p.match_name for p in gfill.properties]
    assert actual == expected_match_names


def test_g_stroke_synthesized_properties(gradient_comp) -> None:
    """G-Stroke has all expected properties from synthesis specs."""
    layer = gradient_comp.layers[0]
    contents = layer.property("ADBE Root Vectors Group")
    gstroke = contents.property("ADBE Vector Graphic - G-Stroke")

    expected_match_names = [
        "ADBE Vector Blend Mode",
        "ADBE Vector Composite Order",
        "ADBE Vector Grad Type",
        "ADBE Vector Grad Start Pt",
        "ADBE Vector Grad End Pt",
        "ADBE Vector Grad HiLite Length",
        "ADBE Vector Grad HiLite Angle",
        "ADBE Vector Grad Colors",
        "ADBE Vector Stroke Opacity",
        "ADBE Vector Stroke Width",
        "ADBE Vector Stroke Line Cap",
        "ADBE Vector Stroke Line Join",
        "ADBE Vector Stroke Miter Limit",
        "ADBE Vector Stroke Dashes",
        "ADBE Vector Stroke Taper",
        "ADBE Vector Stroke Wave",
    ]
    actual = [p.match_name for p in gstroke.properties]
    assert actual == expected_match_names


# --- Serialization and roundtrip tests ---


def test_serialize_gradient_xml_roundtrip() -> None:
    """serialize > parse produces identical gradient data."""
    original = Gradient(
        color_stops=[
            GradientColorStop(0.0, 0.5, color=(1.0, 0.0, 0.0)),
            GradientColorStop(1.0, 0.5, color=(0.0, 0.0, 1.0)),
        ],
        alpha_stops=[
            GradientAlphaStop(0.0, 0.5, 1.0),
            GradientAlphaStop(1.0, 0.5, 0.5),
        ],
        version="1.0",
    )
    result = parse_gradient_xml(_FakeUtf8(original._utf8.value))  # type: ignore[arg-type]
    assert result == original


# The gradient XML AE 2026 writes for a fresh, never-edited gradient
# (white > black, full alpha). Ground truth for Gradient() serialization.
DEFAULT_AE_GRADIENT_XML = (
    "<?xml version='1.0'?>\n"
    "<prop.map version='4'>\n"
    "<prop.list>\n"
    "<prop.pair>\n"
    "<key>Gradient Color Data</key>\n"
    "<prop.list>\n"
    "<prop.pair>\n"
    "<key>Alpha Stops</key>\n"
    "<prop.list>\n"
    "<prop.pair>\n"
    "<key>Stops List</key>\n"
    "<prop.list>\n"
    "<prop.pair>\n"
    "<key>Stop-0</key>\n"
    "<prop.list>\n"
    "<prop.pair>\n"
    "<key>Stops Alpha</key>\n"
    "<array>\n"
    "<array.type><float/></array.type>\n"
    "<float>0</float>\n"
    "<float>0.5</float>\n"
    "<float>1</float>\n"
    "</array>\n"
    "</prop.pair>\n"
    "</prop.list>\n"
    "</prop.pair>\n"
    "<prop.pair>\n"
    "<key>Stop-1</key>\n"
    "<prop.list>\n"
    "<prop.pair>\n"
    "<key>Stops Alpha</key>\n"
    "<array>\n"
    "<array.type><float/></array.type>\n"
    "<float>1</float>\n"
    "<float>0.5</float>\n"
    "<float>1</float>\n"
    "</array>\n"
    "</prop.pair>\n"
    "</prop.list>\n"
    "</prop.pair>\n"
    "</prop.list>\n"
    "</prop.pair>\n"
    "<prop.pair>\n"
    "<key>Stops Size</key>\n"
    "<int type='unsigned' size='32'>2</int>\n"
    "</prop.pair>\n"
    "</prop.list>\n"
    "</prop.pair>\n"
    "<prop.pair>\n"
    "<key>Color Stops</key>\n"
    "<prop.list>\n"
    "<prop.pair>\n"
    "<key>Stops List</key>\n"
    "<prop.list>\n"
    "<prop.pair>\n"
    "<key>Stop-0</key>\n"
    "<prop.list>\n"
    "<prop.pair>\n"
    "<key>Stops Color</key>\n"
    "<array>\n"
    "<array.type><float/></array.type>\n"
    "<float>0</float>\n"
    "<float>0.5</float>\n"
    "<float>1</float>\n"
    "<float>1</float>\n"
    "<float>1</float>\n"
    "<float>1</float>\n"
    "</array>\n"
    "</prop.pair>\n"
    "</prop.list>\n"
    "</prop.pair>\n"
    "<prop.pair>\n"
    "<key>Stop-1</key>\n"
    "<prop.list>\n"
    "<prop.pair>\n"
    "<key>Stops Color</key>\n"
    "<array>\n"
    "<array.type><float/></array.type>\n"
    "<float>1</float>\n"
    "<float>0.5</float>\n"
    "<float>0</float>\n"
    "<float>0</float>\n"
    "<float>0</float>\n"
    "<float>1</float>\n"
    "</array>\n"
    "</prop.pair>\n"
    "</prop.list>\n"
    "</prop.pair>\n"
    "</prop.list>\n"
    "</prop.pair>\n"
    "<prop.pair>\n"
    "<key>Stops Size</key>\n"
    "<int type='unsigned' size='32'>2</int>\n"
    "</prop.pair>\n"
    "</prop.list>\n"
    "</prop.pair>\n"
    "</prop.list>\n"
    "</prop.pair>\n"
    "<prop.pair>\n"
    "<key>Gradient Colors</key>\n"
    "<string>1.0</string>\n"
    "</prop.pair>\n"
    "</prop.list>\n"
    "</prop.map>\n"
)


def test_default_gradient_matches_ae_bytes() -> None:
    """Gradient() serializes to AE's default gradient XML, byte for byte."""
    assert Gradient()._utf8.value == DEFAULT_AE_GRADIENT_XML


def test_reserialize_matches_ae_bytes(gradient_comp) -> None:
    """Re-serializing a parsed (AE-written) gradient reproduces its bytes."""
    layer = gradient_comp.layers[0]
    contents = layer.property("ADBE Root Vectors Group")
    gfill = contents.property("ADBE Vector Graphic - G-Fill")
    colors = gfill.property("ADBE Vector Grad Colors")
    gradient = colors.value
    assert isinstance(gradient, Gradient)

    original = gradient._utf8.value
    gradient._serialize()
    assert gradient._utf8.value == original


def test_gradient_value_write_through(gradient_comp) -> None:
    """Mutating a Gradient auto-serializes to the Utf8 chunk."""

    layer = gradient_comp.layers[0]
    contents = layer.property("ADBE Root Vectors Group")
    gfill = contents.property("ADBE Vector Graphic - G-Fill")
    colors = gfill.property("ADBE Vector Grad Colors")

    gradient = colors.value
    assert isinstance(gradient, Gradient)
    assert gradient._utf8 is not None

    # Mutate via descriptor - auto-serializes
    gradient.color_stops = [
        GradientColorStop(0.0, 0.5, color=(0.0, 1.0, 0.0)),
        GradientColorStop(0.5, 0.5, color=(1.0, 1.0, 0.0)),
        GradientColorStop(1.0, 0.5, color=(0.0, 0.0, 1.0)),
    ]
    gradient.alpha_stops = [
        GradientAlphaStop(0.0, 0.5, 1.0),
        GradientAlphaStop(1.0, 0.5, 1.0),
    ]

    # Re-read from the Utf8 chunk to confirm write-through
    reparsed = parse_gradient_xml(gradient._utf8)
    assert reparsed == gradient


def test_gradient_binary_roundtrip(tmp_path) -> None:
    """Modified gradient survives a full binary roundtrip."""
    app = parse(SAMPLE)
    comp = next(v for v in app.project.items.values() if hasattr(v, "layers"))
    layer = comp.layers[0]
    contents = layer.property("ADBE Root Vectors Group")
    gfill = contents.property("ADBE Vector Graphic - G-Fill")
    colors = gfill.property("ADBE Vector Grad Colors")

    gradient = colors.value
    assert isinstance(gradient, Gradient)

    gradient.color_stops = [
        GradientColorStop(0.0, 0.5, color=(0.25, 0.75, 0.5)),
        GradientColorStop(1.0, 0.5, color=(0.75, 0.25, 0.5)),
    ]
    gradient.alpha_stops = [
        GradientAlphaStop(0.0, 0.5, 0.8),
        GradientAlphaStop(1.0, 0.5, 0.2),
    ]

    # Save and re-parse
    out = tmp_path / "roundtrip.aep"
    app.project.save(out)

    app2 = parse(out)
    comp2 = next(v for v in app2.project.items.values() if hasattr(v, "layers"))
    layer2 = comp2.layers[0]
    contents2 = layer2.property("ADBE Root Vectors Group")
    gfill2 = contents2.property("ADBE Vector Graphic - G-Fill")
    colors2 = gfill2.property("ADBE Vector Grad Colors")
    assert isinstance(colors2.value, Gradient)
    assert len(colors2.value.color_stops) == 2
    assert colors2.value.color_stops[0].color[0] == pytest.approx(0.25)


def test_gradient_add_color_stop_serializes(gradient_comp) -> None:
    """Adding a stop via add_color_stop auto-serializes."""
    layer = gradient_comp.layers[0]
    contents = layer.property("ADBE Root Vectors Group")
    gfill = contents.property("ADBE Vector Graphic - G-Fill")
    colors = gfill.property("ADBE Vector Grad Colors")

    gradient = colors.value
    assert isinstance(gradient, Gradient)
    original_count = len(gradient.color_stops)

    gradient.add_color_stop(0.5, 0.5, (1.0, 1.0, 0.0))

    # Re-parse from utf8 to confirm serialization
    reparsed = parse_gradient_xml(gradient._utf8)
    assert reparsed is not None
    assert len(reparsed.color_stops) == original_count + 1


def test_gradient_remove_color_stop_serializes(gradient_comp) -> None:
    """Removing a stop via remove_color_stop auto-serializes."""
    layer = gradient_comp.layers[0]
    contents = layer.property("ADBE Root Vectors Group")
    gfill = contents.property("ADBE Vector Graphic - G-Fill")
    colors = gfill.property("ADBE Vector Grad Colors")

    gradient = colors.value
    assert isinstance(gradient, Gradient)
    original_count = len(gradient.color_stops)

    gradient.remove_color_stop(0)

    assert len(gradient.color_stops) == original_count - 1
    reparsed = parse_gradient_xml(gradient._utf8)
    assert reparsed is not None
    assert len(reparsed.color_stops) == original_count - 1
