"""COS (Carousel Object Syntax) parser and serializer."""

from .cos import (
    CosName,
    CosParser,
    IndirectObject,
    IndirectReference,
    Stream,
    cos_get,
    run_spans,
)
from .descriptors import CosField
from .serializer import serialize
from .text import POINT_TEXT_COS_TEMPLATE, get_cos_template

__all__ = [
    "CosField",
    "CosName",
    "CosParser",
    "IndirectObject",
    "IndirectReference",
    "POINT_TEXT_COS_TEMPLATE",
    "Stream",
    "cos_get",
    "get_cos_template",
    "run_spans",
    "serialize",
]
