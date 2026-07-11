"""Parse COS (Carousel Object Structure) text data into text models.

Transforms the dict returned by [CosParser][py_aep.cos.CosParser] for a
`btdk` chunk into [TextDocument][py_aep.models.text.TextDocument] and
[FontObject][py_aep.models.text.FontObject] instances.

The COS data layout follows the structure documented in the
`lottie-docs AEP reference
<https://github.com/nickt/lottie-docs/blob/main/docs/aep.md#list-btdk>`_.

Fonts
-----
`data["0"]["1"]["0"]` contains an array of available fonts.  Each entry
carries a `CoolTypeFont` marker and exposes PostScript name, version, and
a flag at well-known sub-keys.

Text documents
--------------
`data["1"]["1"]` is an array of text documents (one per keyframe).  Inside
each document:

* `doc["0"]["0"]` - the text string
* `doc["0"]["5"]["0"]` - array of paragraph style runs
* `doc["0"]["6"]["0"]` - array of character style runs

Default styles live at `data["1"]["2"]` (character) and
`data["1"]["3"]` (paragraph).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..cos import cos_get
from ..models.text.font_object import FontObject
from ..models.text.text_document import TextDocument

if TYPE_CHECKING:
    from typing import Any

    from ..binary.chunk import ListChunk

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Font parsing
# ---------------------------------------------------------------------------


def parse_fonts(cos_data: dict[str, Any]) -> list[FontObject]:
    """Parse font entries from COS data.

    Reads the font array at `cos_data["0"]["1"]["0"]`.  Each font entry
    is a dict with structure::

        entry["0"]["0"]["0"]  -> PostScript name (str)
        entry["0"]["0"]["5"]  -> version string (optional)
        entry["0"]["99"]      -> "CoolTypeFont" marker

    Args:
        cos_data: The parsed COS dict from a `btdk` chunk.

    Returns:
        List of [FontObject][] instances in the same order as the COS
        array (the index is referenced by character styles).
    """
    font_array = cos_get(cos_data, "0", "1", "0")
    if not font_array or not isinstance(font_array, list):
        return []

    fonts: list[FontObject] = []
    for entry in font_array:
        font_data = cos_get(entry, "0", "0")
        if font_data is None or not isinstance(font_data, dict):
            continue
        font_entry = cos_get(entry, "0")
        font = FontObject(
            _font_data=font_data,
            _font_entry=font_entry if isinstance(font_entry, dict) else None,
        )
        fonts.append(font)

    return fonts


# ---------------------------------------------------------------------------
# Text document sub-dict extraction
# ---------------------------------------------------------------------------


def _get_first_char_style(doc: dict[str, Any]) -> dict[str, Any] | None:
    """Return the first character style dict from a text document entry.

    Path: `doc["0"]["6"]["0"][0]["0"]["0"]["6"]`
    """
    result = cos_get(doc, "0", "6", "0", 0, "0", "0", "6")
    if isinstance(result, dict):
        return result
    return None


def _get_first_para_style(doc: dict[str, Any]) -> dict[str, Any] | None:
    """Return the first paragraph style dict from a text document entry.

    Path: `doc["0"]["5"]["0"][0]["0"]["0"]["5"]`
    """
    result = cos_get(doc, "0", "5", "0", 0, "0", "0", "5")
    if isinstance(result, dict):
        return result
    return None


def parse_text_documents(
    cos_data: dict[str, Any],
    fonts: list[FontObject],
    btdk_body: ListChunk,
) -> list[TextDocument]:
    """Parse text documents from COS data.

    Reads the document array at `cos_data["1"]["1"]`.  Each entry's COS
    sub-dicts are passed directly to [TextDocument][] which lazily
    extracts values via CosField descriptors.

    Args:
        cos_data: The parsed COS dict from a `btdk` chunk.
        fonts: The list of [FontObject][] parsed by
            [parse_fonts][] (font indices reference this list).
        btdk_body: The btdk chunk body for COS write-back.

    Returns:
        List of [TextDocument][] instances (one per keyframe).
    """
    doc_array = cos_get(cos_data, "1", "1")
    if not doc_array or not isinstance(doc_array, list):
        return []

    documents: list[TextDocument] = []

    for doc_entry in doc_array:
        char_style = _get_first_char_style(doc_entry)
        para_style = _get_first_para_style(doc_entry)

        documents.append(
            TextDocument._from_binary(
                _char_style=char_style,
                _para_style=para_style,
                _doc=doc_entry,
                _fonts=fonts,
                _cos_data=cos_data,
                _btdk_body=btdk_body,
            )
        )

    # Frame-level writes (box meta, orientation) live in the shared
    # cos_data and change composition for every keyframe's document,
    # so each wrapper knows its siblings to dirty-mark them together.
    for document in documents:
        document._siblings = documents

    return documents


# ---------------------------------------------------------------------------
# High-level entry point
# ---------------------------------------------------------------------------


def parse_btdk_cos(
    cos_data: dict[str, Any],
    btdk_body: ListChunk,
) -> tuple[list[TextDocument], list[FontObject]]:
    """Parse a btdk COS dict into text documents and fonts.

    This is the main entry point called by
    [parse_text_document][py_aep.parsers.property.parse_text_document].

    Args:
        cos_data: The parsed COS dict from a `btdk` chunk (the return
            value of [CosParser.parse][py_aep.cos.CosParser.parse]).
        btdk_body: The btdk chunk body for COS write-back.

    Returns:
        A tuple `(text_documents, fonts)` where `text_documents` is a
        list of [TextDocument][] (one per keyframe) and `fonts` is
        the list of [FontObject][] referenced by the documents.
    """
    fonts = parse_fonts(cos_data)
    documents = parse_text_documents(cos_data, fonts, btdk_body)
    return documents, fonts
