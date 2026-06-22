"""Tests for gradient color property parsing."""

from __future__ import annotations

from py_aep.models.properties.gradient import (
    Gradient,
    GradientAlphaStop,
    GradientColorStop,
)
from py_aep.parsers.gradient import parse_gradient_xml


class _FakeUtf8:
    """Minimal stand-in for Utf8Chunk in parser unit tests."""

    def __init__(self, value: str) -> None:
        self.value = value


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


def test_default_gradient_matches_ae_bytes() -> None:
    """Gradient() serializes to AE's default gradient XML, byte for byte."""
    assert Gradient()._utf8.value == DEFAULT_AE_GRADIENT_XML


def test_gradient_stops_serialized_in_lexicographic_key_order() -> None:
    """AE serializes gradient stops with keys in lexicographic order
    (Stop-0, Stop-1, Stop-10, ..., Stop-2, ...), not numeric, for >9
    stops. The values must stay paired with their (numeric) stop index."""
    color_stops = [
        GradientColorStop(i / 11.0, 0.5, (i / 11.0, 0.0, 0.0)) for i in range(12)
    ]
    grad = Gradient(color_stops)
    xml = grad._utf8.value
    keys = [
        ln[len("<key>Stop-") : -len("</key>")]
        for ln in xml.splitlines()
        if ln.startswith("<key>Stop-")
    ]
    # XML emits 2 default alpha stops first, then the 12 color stops;
    # check the color block's key ordering.
    color_keys = keys[-12:]
    assert color_keys == sorted(color_keys)  # lexicographic, not numeric
    assert color_keys[:4] == ["0", "1", "10", "11"]
    assert color_keys[-1] == "9"
