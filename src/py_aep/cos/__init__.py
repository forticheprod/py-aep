"""COS (Carousel Object Syntax) parser and serializer."""

from .cos import CosName, CosParser, IndirectObject, IndirectReference, Stream
from .descriptors import CosField
from .serializer import serialize
from .text import POINT_TEXT_COS_TEMPLATE, build_text_cos, get_cos_template

__all__ = [
    "CosField",
    "CosName",
    "CosParser",
    "IndirectObject",
    "IndirectReference",
    "POINT_TEXT_COS_TEMPLATE",
    "Stream",
    "build_text_cos",
    "get_cos_template",
    "serialize",
]
