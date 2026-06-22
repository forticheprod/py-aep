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
