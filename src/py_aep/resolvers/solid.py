"""Color-to-name resolver for solid footage sources.

After Effects auto-generates solid layer names from the solid's color
(e.g. "Red Solid 1", "Dark Blue Solid 2"). This module replicates that
naming logic using calibrated HSV thresholds.
"""

from __future__ import annotations

import colorsys

# -- Hue bands (degrees 0-360) ----------------------------------------

_HUE_BANDS = [
    (15, "Red"),
    (45, "Orange"),
    (75, "Yellow"),
    (105, "Lime Green"),
    (135, "Green"),
    (165, "Turquoise"),
    (195, "Cyan"),
    (225, "Royal Blue"),
    (255, "Blue"),
    (285, "Purple"),
    (315, "Magenta"),
    (345, "Magenta-Red"),
    (360, "Red"),
]


def _hue_name(h_deg: float) -> str:
    """Map a hue angle (0-360) to a color name."""
    for upper, name in _HUE_BANDS:
        if h_deg < upper:
            return name
    return "Red"


def solid_color_name(r: float, g: float, b: float) -> str:
    """Derive the base solid name from an RGB color.

    After Effects names solids by their perceived color category.
    Returns the base name (e.g. `"Red Solid"`) without a trailing
    number suffix; the caller is responsible for disambiguation.

    Args:
        r: Red channel in `[0.0, 1.0]`.
        g: Green channel in `[0.0, 1.0]`.
        b: Blue channel in `[0.0, 1.0]`.
    """
    h_raw, s_raw, v_raw = colorsys.rgb_to_hsv(r, g, b)
    h = h_raw * 360.0
    s = s_raw * 100.0
    v = v_raw * 100.0

    if s == 0:
        # Achromatic
        if v == 0:
            label = "Black"
        elif v < 38:
            label = "Dark Gray"
        elif v < 63:
            label = "Gray"
        elif v < 88:
            label = "Light Gray"
        else:
            label = "White"
    else:
        hue = _hue_name(h)
        if s < 25:
            if v == 0:
                label = "Black"
            elif v < 25:
                label = f"Dark {hue}"
            elif v < 75:
                label = f"Pale Gray-{hue}"
            else:
                label = f"Pale {hue}"
        elif s < 75:
            if v == 0:
                label = "Black"
            elif v < 25:
                label = f"Dark {hue}"
            elif v < 75:
                label = f"Medium Gray-{hue}"
            else:
                label = f"Medium {hue}"
        else:
            if v == 0:
                label = "Black"
            elif v < 25:
                label = f"Dark {hue}"
            elif v < 75:
                label = f"Deep {hue}"
            else:
                label = hue

    return f"{label} Solid"
