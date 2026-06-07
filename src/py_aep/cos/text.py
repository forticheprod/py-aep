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
# extracted from an AE 2025-created text layer (Myriad Pro, 36px)
POINT_TEXT_COS_TEMPLATE = (
    "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"
    "2L+x/Qd8Zm2Tax8AAA=="
)
