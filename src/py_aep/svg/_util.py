"""Shared low-level helpers for the SVG reader package."""

from __future__ import annotations

import math
import re
from typing import NamedTuple

# An SVG/CSS number token: optional sign, decimal or integer, optional exponent.
NUMBER_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
# The same token allowing a trailing `%` (CSS color / ratio values).
NUMBER_PCT_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?%?")
# A length: a number and an optional unit or `%`.
_LENGTH_RE = re.compile(r"([-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?)\s*(%|[A-Za-z]+)?")
# CSS absolute units in user units (px): CSS Values 3 fixes 1in = 96px.
_ABSOLUTE_UNITS = {
    "px": 1.0,
    "in": 96.0,
    "cm": 96.0 / 2.54,
    "mm": 96.0 / 25.4,
    "q": 96.0 / 101.6,
    "pt": 96.0 / 72.0,
    "pc": 16.0,
}
#: The CSS initial font size (`medium`), the `em` reference by default.
DEFAULT_FONT_SIZE = 16.0


class LengthContext(NamedTuple):
    """What relative SVG lengths resolve against: the nearest viewport's
    size in user units (its viewBox) and the element's font size."""

    width: float
    height: float
    font_size: float = DEFAULT_FONT_SIZE

    @property
    def diagonal(self) -> float:
        """The normalized diagonal a percentage of no particular axis (a
        radius, a stroke width) refers to: `sqrt((w^2 + h^2) / 2)`."""
        return math.hypot(self.width, self.height) / math.sqrt(2.0)


def local_name(tag: str) -> str:
    """Strip an XML namespace, e.g. `{http://...}rect` -> `rect`."""
    return tag.rsplit("}", 1)[-1]


def clamp01(value: float) -> float:
    """Clamp a float to the `[0.0, 1.0]` range."""
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)


def parse_number(text: str | None, default: float = 0.0) -> float:
    """Leading numeric value of `text`, ignoring a unit suffix (e.g.
    `"40px"` -> `40.0`); `default` when absent or non-numeric."""
    if not text:
        return default
    m = NUMBER_RE.match(text.strip())
    return float(m.group()) if m else default


def parse_length(
    text: str | None,
    default: float = 0.0,
    percent_of: float | None = None,
    font_size: float = DEFAULT_FONT_SIZE,
) -> float:
    """An SVG length in user units: CSS absolute units (`mm`, `pt`, `in`,
    ...) at 96 px per inch, `em` / `ex` from `font_size`, a percentage of
    `percent_of` (the bare number when `None`); a unitless number or an
    unknown unit is taken as px. `default` when absent or non-numeric."""
    if not text:
        return default
    m = _LENGTH_RE.match(text.strip())
    if m is None:
        return default
    value = float(m.group(1))
    unit = (m.group(2) or "").lower()
    if unit == "%":
        return value * percent_of / 100.0 if percent_of is not None else value
    if unit == "em":
        return value * font_size
    if unit == "ex":
        return value * font_size / 2.0
    return value * _ABSOLUTE_UNITS.get(unit, 1.0)


def parse_ratio(text: str | None, default: float) -> float:
    """CSS ratio (`0.5` or `50%`) clamped to `[0, 1]`; `default` when the
    value is absent or non-numeric (e.g. the keyword `inherit`)."""
    if text is None:
        return default
    text = text.strip()
    m = NUMBER_RE.match(text)
    if m is None:
        return default
    val = float(m.group())
    return clamp01(val / 100.0 if text.endswith("%") else val)
