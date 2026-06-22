"""Tests for gradient color property parsing."""

from __future__ import annotations

import pytest

from py_aep import parse
from py_aep.models.properties.gradient import (
    Gradient,
)

SAMPLE = "samples/models/property/gradient.aep"
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
        "ADBE Vector Grad Scale",
        "ADBE Vector Grad Rotation",
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
        "ADBE Vector Grad Scale",
        "ADBE Vector Grad Rotation",
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
