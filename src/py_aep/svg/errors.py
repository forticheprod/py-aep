"""SVG import error types."""

from __future__ import annotations


class UnsupportedSVGError(ValueError):
    """Raised when an SVG uses a feature py_aep cannot import.

    The message names the offending element or feature so callers can
    report exactly what is unsupported (e.g. an unimplemented path
    command or a referenced filter).
    """
