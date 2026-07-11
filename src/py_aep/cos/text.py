"""COS text layer template builder.

Builds COS dictionaries for text layer `btdk` data from a gzip-compressed
template.
"""

from __future__ import annotations

import gzip
import io
from base64 import b64decode
from typing import Any

from .cos import CosParser

_COS_TEMPLATE_CACHE: dict[str, Any] | None = None


def get_cos_template() -> dict[str, Any]:
    """Parse and cache the COS template from the gzip blob."""
    global _COS_TEMPLATE_CACHE  # noqa: PLW0603
    if _COS_TEMPLATE_CACHE is not None:
        return _COS_TEMPLATE_CACHE

    raw = gzip.decompress(b64decode(POINT_TEXT_COS_TEMPLATE)).lstrip()
    parser = CosParser(io.BytesIO(raw), max_pos=len(raw))
    result = parser.parse()
    assert isinstance(result, dict)
    _COS_TEMPLATE_CACHE = result
    return result


# Point text COS template - gzip-compressed, base64-encoded btdk data
# captured from an AE 2026 `addText("Sample Text")` layer (MyriadPro-
# Regular, 36px), so a bare TextDocument matches AE 2026's own scripted
# addText output byte-for-byte. `add_text` additionally applies the
# "Text Style Sheet" preference on top when an ae_preferences_dir is
# provided (see models.preferences.apply_text_style_prefs).
POINT_TEXT_COS_TEMPLATE = (
    "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"
    "AA=="
)
