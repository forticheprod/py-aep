"""Enumerate the layers of an Illustrator/PDF file (PDF Optional Content Groups).

After Effects imports a layered `.ai`/`.pdf` as a composition with one footage
layer per Illustrator layer. The layers map to PDF Optional Content Groups
(OCGs); the order of the catalog's `/OCProperties` `/OCGs` array is the
document order (bottom layer first). Only PDF-compatible files expose OCGs;
Illustrator files saved without PDF compatibility store their artwork in a
compressed PGF block and are not supported.
"""

from __future__ import annotations

import io
import re
import zlib
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from ..color.icc import icc_profile_description
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


_OBJ_RE = re.compile(rb"(\d+)[ \t\r\n]+(\d+)[ \t\r\n]+obj\b")


def _object_offsets(data: bytes) -> dict[int, int]:
    """Map each indirect object number to its byte offset (last definition wins)."""
    offsets: dict[int, int] = {}
    for match in _OBJ_RE.finditer(data):
        offsets[int(match.group(1))] = match.start()
    return offsets


def _parse_object_at(data: bytes, offset: int) -> Any:
    """Parse the single indirect object starting at `offset`, returning its value."""
    parser = CosParser(io.BytesIO(data[offset:]))
    parser.lex()
    value = parser.parse_value()
    return value.data if isinstance(value, IndirectObject) else value


def _resolve(value: Any, data: bytes, offsets: dict[int, int]) -> Any:
    """Follow an indirect reference to its object; pass other values through."""
    if isinstance(value, IndirectReference):
        offset = offsets.get(value.object_number)
        return None if offset is None else _parse_object_at(data, offset)
    return value


def _order_object_numbers(value: Any, out: set[int]) -> set[int]:
    """Collect every OCG object number referenced by a `/D` `/Order` tree."""
    if isinstance(value, list):
        for entry in value:
            _order_object_numbers(entry, out)
    elif isinstance(value, IndirectReference):
        out.add(value.object_number)
    return out


def read_ai_layer_ocgs(
    file: str | os.PathLike[str], data: bytes | None = None
) -> list[AiLayer]:
    """Return one `AiLayer` per layer, in document order (bottom layer first).

    Illustrator can leave the optional content groups of earlier revisions of
    the artwork behind in `/OCGs`: one 2019-vintage file lists 65 groups for
    the 25 layers it has, the stale 40 first. The leftovers are exactly the
    groups the default configuration's `/Order` omits, and that is the set
    After Effects imports - checked against an AE-authored project whose
    footage layer indices only line up with the `/Order` members. `/Order`
    decides membership only; `/OCGs` still gives the order (see the module
    docstring).

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
    parser = CosParser(io.BytesIO(data[marker + len(b"/OCProperties") :]))
    parser.lex()
    oc_properties = _resolve(parser.parse_value(), data, offsets)
    if not isinstance(oc_properties, dict):
        raise UnsupportedAiLayersError(f"{name}: unreadable /OCProperties.")
    config = _resolve(oc_properties.get("D"), data, offsets)
    if not isinstance(config, dict):
        config = {}
    members = _order_object_numbers(_resolve(config.get("Order"), data, offsets), set())
    hidden = _order_object_numbers(_resolve(config.get("OFF"), data, offsets), set())
    ocgs = _resolve(oc_properties.get("OCGs"), data, offsets)
    layers: list[AiLayer] = []
    if isinstance(ocgs, list):
        for ref in ocgs:
            if not isinstance(ref, IndirectReference):
                continue
            if members and ref.object_number not in members:
                continue
            ocg = _resolve(ref, data, offsets)
            if isinstance(ocg, dict) and "Name" in ocg:
                layers.append(
                    AiLayer(
                        ref.object_number,
                        decode_pdf_text_string(ocg["Name"]),
                        ref.object_number not in hidden,
                    )
                )
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


def read_ai_color_profile(
    file: str | os.PathLike[str], data: bytes | None = None
) -> str | None:
    """Return the embedded ICC color profile name, or `None`.

    After Effects records a PDF-compatible Illustrator/PDF file's embedded
    color profile name (e.g. `Coated FOGRA39 (ISO 12647-2:2004)`) in the
    footage item, read here from the ICC `desc` tag. Returns `None` when the
    file is not PDF-compatible or has no embedded profile.

    The profile's data color space (the header signature at bytes 16-19) is
    NOT read: AE does not record it anywhere in the footage item. The `opti`
    byte that looked like a color-space flag is the document's layer count
    (`binary.footage_chunks.TextOptiChunk.text_document_layers`).

    Args:
        file: Path to a `.ai` or `.pdf` file.
        data: The file's bytes, if the caller already read them.
    """
    icc = _find_ai_icc(file, data)
    if icc is None:
        return None
    return icc_profile_description(icc)
