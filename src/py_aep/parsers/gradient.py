"""Parser and serializer for After Effects gradient XML in GCky Utf8 chunks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from xml.etree.ElementTree import (
    Element,
    ParseError,
    fromstring,
)

from ..models.properties.gradient import (
    Gradient,
    GradientAlphaStop,
    GradientColorStop,
)

if TYPE_CHECKING:
    from ..binary.scalar_chunks import Utf8Chunk

logger = logging.getLogger(__name__)


def parse_gradient_xml(
    utf8: Utf8Chunk,
) -> Gradient | None:
    """Parse AE gradient XML into a `Gradient` instance.

    The XML uses a `prop.map` / `prop.list` / `prop.pair` structure with
    nested arrays of floats for color and alpha stops.

    Args:
        utf8: The Utf8 chunk containing the gradient XML.

    Returns:
        Parsed gradient data, or None if parsing fails.
    """
    xml_text = utf8.value
    if not xml_text:
        return None
    try:
        root = fromstring(xml_text)
    except ParseError:
        logger.warning("Invalid gradient XML")
        return None

    # Navigate: prop.map > prop.list
    prop_list = root.find("prop.list")
    if prop_list is None:
        return None

    pairs = _get_pairs(prop_list)
    gradient_data = pairs.get("Gradient Color Data")
    version_str = _get_string_value(pairs.get("Gradient Colors"))

    if gradient_data is None:
        return None

    data_pairs = _get_pairs(gradient_data)
    color_stops = _parse_color_stops(data_pairs.get("Color Stops"))
    alpha_stops = _parse_alpha_stops(data_pairs.get("Alpha Stops"))

    return Gradient._from_binary(
        color_stops=color_stops,
        alpha_stops=alpha_stops,
        version=version_str or "1.0",
        _utf8=utf8,
    )


def _get_pairs(prop_list_elem: Element) -> dict[str, Element]:
    """Extract key-value pairs from a prop.list element.

    Returns a dict mapping key text to the value element (the second
    child of each prop.pair).
    """
    pairs: dict[str, Element] = {}
    for pair in prop_list_elem.findall("prop.pair"):
        key_elem = pair.find("key")
        if key_elem is None or key_elem.text is None:
            continue
        # Value is the second child (after key)
        children = list(pair)
        if len(children) >= 2:
            pairs[key_elem.text] = children[1]
    return pairs


def _get_string_value(elem: Element | None) -> str | None:
    """Get text content from a <string> element."""
    if elem is None:
        return None
    if elem.tag == "string":
        return elem.text
    return None


def _parse_color_stops(
    color_stops_elem: Element | None,
) -> list[GradientColorStop]:
    """Parse the 'Color Stops' prop.list into GradientColorStop objects."""
    if color_stops_elem is None:
        return []

    pairs = _get_pairs(color_stops_elem)
    stops_list_elem = pairs.get("Stops List")
    if stops_list_elem is None:
        return []

    stops: list[GradientColorStop] = []
    # Each stop is a prop.pair with key "Stop-N"
    stop_pairs = _get_pairs(stops_list_elem)
    for i in range(len(stop_pairs)):
        key = f"Stop-{i}"
        stop_elem = stop_pairs.get(key)
        if stop_elem is None:
            break
        stop_inner = _get_pairs(stop_elem)
        array_elem = stop_inner.get("Stops Color")
        if array_elem is None:
            continue
        floats = _parse_float_array(array_elem)
        if len(floats) >= 5:
            stops.append(
                GradientColorStop(
                    offset=floats[0],
                    midpoint=floats[1],
                    color=(floats[2], floats[3], floats[4]),
                )
            )
    return stops


def _parse_alpha_stops(
    alpha_stops_elem: Element | None,
) -> list[GradientAlphaStop]:
    """Parse the 'Alpha Stops' prop.list into GradientAlphaStop objects."""
    if alpha_stops_elem is None:
        return []

    pairs = _get_pairs(alpha_stops_elem)
    stops_list_elem = pairs.get("Stops List")
    if stops_list_elem is None:
        return []

    stops: list[GradientAlphaStop] = []
    stop_pairs = _get_pairs(stops_list_elem)
    for i in range(len(stop_pairs)):
        key = f"Stop-{i}"
        stop_elem = stop_pairs.get(key)
        if stop_elem is None:
            break
        stop_inner = _get_pairs(stop_elem)
        array_elem = stop_inner.get("Stops Alpha")
        if array_elem is None:
            continue
        floats = _parse_float_array(array_elem)
        if len(floats) >= 3:
            stops.append(
                GradientAlphaStop(
                    offset=floats[0],
                    midpoint=floats[1],
                    alpha=floats[2],
                )
            )
    return stops


def _parse_float_array(array_elem: Element) -> list[float]:
    """Parse an <array> element containing <float> children."""
    floats: list[float] = []
    for child in array_elem:
        if child.tag == "float" and child.text is not None:
            try:
                floats.append(float(child.text))
            except ValueError:
                continue
    return floats
