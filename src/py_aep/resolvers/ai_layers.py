"""Enumerate the layers of an Illustrator/PDF file (PDF Optional Content Groups).

After Effects imports a layered `.ai`/`.pdf` as a composition with one footage
layer per Illustrator layer. The layers map to PDF Optional Content Groups
(OCGs); the default configuration's `/D` `/Order` lists them top layer first,
so its reverse is the document order (bottom layer first). Illustrator writes
`/OCGs` as the exact reverse of `/Order`, but other PDF writers need not.
Only PDF-compatible files expose OCGs;
Illustrator files saved without PDF compatibility store their artwork in a
compressed PGF block and are not supported.
"""

from __future__ import annotations

import io
import re
import zlib
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from ..cos import (
    CosParser,
    IndirectObject,
    IndirectReference,
    decode_pdf_text_string,
)

if TYPE_CHECKING:
    import os
    from typing import Any


class UnsupportedAiLayersError(ValueError):
    """Raised when a `.ai`/`.pdf` file's layers cannot be enumerated."""


class AiLayer(NamedTuple):
    """One Illustrator/PDF layer (Optional Content Group)."""

    object_number: int
    """The OCG's PDF indirect-object number."""

    name: str
    """The layer name."""

    visible: bool
    """`False` when the default configuration hides the layer (the OCG is
    listed in `/D` `/OFF`). After Effects records this in the per-layer
    `opti` and gives the imported comp layer its video switch off."""


# The leading `\b` skips every `endobj`: a header needs whitespace before
# the keyword anyway.
_OBJ_KEYWORD_RE = re.compile(rb"\bobj\b")
_OBJ_HEADER_RE = re.compile(rb"(\d+)[ \t\r\n]+(\d+)[ \t\r\n]+\Z")
# How far before an `obj` keyword its `N G` header may start: far longer
# than any header a PDF writer emits.
_OBJ_HEADER_WINDOW = 64


def _object_offsets(data: bytes) -> dict[int, int]:
    """Map each indirect object number to its byte offset (last definition wins).

    Finds each `obj` keyword and matches its header just before it: a
    pattern led by the header's digits would be tried at every digit in the
    file's content streams, tens of times slower on a large document.
    """
    offsets: dict[int, int] = {}
    for keyword in _OBJ_KEYWORD_RE.finditer(data):
        end = keyword.start()
        header = _OBJ_HEADER_RE.search(data, max(0, end - _OBJ_HEADER_WINDOW), end)
        if header is not None:
            offsets[int(header.group(1))] = header.start()
    return offsets


def _parse_object_at(data: bytes, offset: int) -> Any:
    """Parse the single indirect object starting at `offset`, returning its value.

    Raises:
        UnsupportedAiLayersError: If the object is malformed or truncated.
    """
    parser = CosParser(io.BytesIO(data[offset:]))
    try:
        parser.lex()
        value = parser.parse_value()
    except (SyntaxError, RecursionError) as exc:
        raise UnsupportedAiLayersError(
            f"malformed PDF object at byte {offset}"
        ) from exc
    return value.data if isinstance(value, IndirectObject) else value


def _resolve(value: Any, data: bytes, offsets: dict[int, int]) -> Any:
    """Follow an indirect reference to its object; pass other values through."""
    if isinstance(value, IndirectReference):
        offset = offsets.get(value.object_number)
        return None if offset is None else _parse_object_at(data, offset)
    return value


def _order_object_numbers(value: Any, out: list[int]) -> list[int]:
    """Collect the OCG object numbers a `/D` `/Order` (or `/OFF`) tree
    references, depth first, each once."""
    if isinstance(value, list):
        for entry in value:
            _order_object_numbers(entry, out)
    elif isinstance(value, IndirectReference) and value.object_number not in out:
        out.append(value.object_number)
    return out


def read_ai_layer_ocgs(
    file: str | os.PathLike[str], data: bytes | None = None
) -> list[AiLayer]:
    """Return one `AiLayer` per layer, in document order (bottom layer first).

    The default configuration's `/Order` decides both which groups are layers
    and their order. Illustrator can leave the optional content groups of
    earlier revisions of the artwork behind in `/OCGs`: one 2019-vintage file
    lists 65 groups for the 25 layers it has, the stale 40 first. The
    leftovers are exactly the groups `/Order` omits, and that is the set After
    Effects imports - checked against an AE-authored project whose footage
    layer indices only line up with the `/Order` members. After Effects stacks
    the layers top-down in `/Order` sequence and counts each footage's layer
    index from the bottom of that stack (AE 2026, PDFs whose `/Order` is
    neither `/OCGs` nor its reverse). Without an `/Order`, `/OCGs` gives the
    order.

    Args:
        file: Path to a `.ai` or `.pdf` file.
        data: The file's bytes, if the caller already read them.

    Raises:
        UnsupportedAiLayersError: If the file is not a PDF-compatible document
            or has no Optional Content Groups (layers).
    """
    name = Path(file).name
    if data is None:
        data = Path(file).read_bytes()
    if not data.startswith(b"%PDF"):
        raise UnsupportedAiLayersError(
            f"{name}: not a PDF-compatible file; layered import requires an "
            "Illustrator/PDF file saved with PDF compatibility."
        )
    marker = data.find(b"/OCProperties")
    if marker < 0:
        raise UnsupportedAiLayersError(
            f"{name}: no layers (the file has no PDF Optional Content Groups)."
        )
    offsets = _object_offsets(data)
    layers: list[AiLayer] = []
    # The COS lexer reports malformed or truncated objects as SyntaxError (and
    # a pathologically nested one as RecursionError); either means the layers
    # cannot be read, which callers handle as this module's own error.
    try:
        parser = CosParser(io.BytesIO(data[marker + len(b"/OCProperties") :]))
        parser.lex()
        oc_properties = _resolve(parser.parse_value(), data, offsets)
        if not isinstance(oc_properties, dict):
            raise UnsupportedAiLayersError(f"{name}: unreadable /OCProperties.")
        config = _resolve(oc_properties.get("D"), data, offsets)
        if not isinstance(config, dict):
            config = {}
        order = _order_object_numbers(_resolve(config.get("Order"), data, offsets), [])
        hidden = set(
            _order_object_numbers(_resolve(config.get("OFF"), data, offsets), [])
        )
        ocgs = _resolve(oc_properties.get("OCGs"), data, offsets)
        listed = {
            ref.object_number: ref
            for ref in (ocgs if isinstance(ocgs, list) else [])
            if isinstance(ref, IndirectReference)
        }
        refs = (
            [listed[n] for n in reversed(order) if n in listed]
            if order
            else list(listed.values())
        )
        for ref in refs:
            ocg = _resolve(ref, data, offsets)
            if isinstance(ocg, dict) and isinstance(ocg.get("Name"), (str, bytes)):
                layers.append(
                    AiLayer(
                        ref.object_number,
                        decode_pdf_text_string(ocg["Name"]),
                        ref.object_number not in hidden,
                    )
                )
    except (SyntaxError, RecursionError) as exc:
        raise UnsupportedAiLayersError(f"{name}: malformed PDF objects.") from exc
    if not layers:
        raise UnsupportedAiLayersError(f"{name}: no named layers found.")
    return layers


def read_ai_layers(
    file: str | os.PathLike[str], data: bytes | None = None
) -> list[str]:
    """Return the Illustrator/PDF layer names in document order.

    Args:
        file: Path to a `.ai` or `.pdf` file.
        data: The file's bytes, if the caller already read them.

    Returns:
        Layer names in document (OCG) order, bottom layer first.

    Raises:
        UnsupportedAiLayersError: If the file is not a PDF-compatible
            document or has no Optional Content Groups (layers).
    """
    return [layer.name for layer in read_ai_layer_ocgs(file, data)]


_STREAM_RE = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)


def _find_ai_icc(
    file: str | os.PathLike[str], data: bytes | None = None
) -> bytes | None:
    """Return the embedded ICC profile body from a PDF-compatible file.

    Inflates each deflate stream and returns the first one that is an ICC
    profile (`acsp` signature at offset 36). `None` when the file is not
    PDF-compatible or has no embedded profile.
    """
    if data is None:
        data = Path(file).read_bytes()
    if not data.startswith(b"%PDF"):
        return None
    for match in _STREAM_RE.finditer(data):
        body = match.group(1)
        if len(body) > 8_000_000:
            continue
        try:
            profile = zlib.decompress(body)
        except zlib.error:
            continue
        if len(profile) >= 132 and profile[36:40] == b"acsp":
            return profile
    return None
