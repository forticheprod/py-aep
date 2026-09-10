"""Measure the per-layer artwork bounds of an Illustrator/PDF file.

After Effects offers "Layer Size" footage dimensions for a `.ai`/`.pdf` layer
import (`ImportOptions.layer_dimensions`), sizing the footage to the layer's
artwork instead of the document. It records the artwork box in the footage
`opti` and derives the pixel dimensions from it, and it does not recompute
either on open, so py_aep has to reproduce the box.

The box is **not** the true visual extent of the art. It is a deliberately
conservative estimate that After Effects computes from the page content
stream, reverse-engineered against AE 2026 and reproduced here exactly for
123 probe layers (see `.claude/plans/ai-layer-size.md`):

- the box is the union of one contribution per painting operator, with the
  expansion applied **per contribution**, never to the union;
- paths are measured by their **control-point hull**, not their true curve
  bounds, so a curve whose control points sit far outside it measures large;
- a fill expands by `0.25`, a stroke by the stroke half-width times a
  shape-dependent factor, and text, images and form XObjects not at all;
- text is measured from the PDF's own font metrics (`/Widths` and the
  descriptor's `/FontBBox`), so no font file or glyph outline is needed, and
  from `data.std14_metrics` where the file supplies neither;
- clipping needs no work: Illustrator resolves clipping masks when it writes
  the page, emitting pre-trimmed geometry and omitting fully-clipped art, and
  AE measures straight through any residual `W n`.

Only the **first page** is measured. AE has a defect here: on a multi-artboard
document it measures the second page instead, reporting every layer whose art
is on the first artboard as empty. py_aep measures the first page and warns,
rather than reproducing behaviour that drops artwork.
"""

from __future__ import annotations

import math
import re
import warnings
import zlib
from pathlib import Path
from typing import TYPE_CHECKING

from ..cos import IndirectReference
from ..data.std14_metrics import (
    STD14_EXTENT,
    STD14_FIRST_CODE,
    STD14_STANDARD_QUOTES,
    STD14_WIDTHS,
)
from .ai_layers import (
    UnsupportedAiLayersError,
    _object_offsets,
    _parse_object_at,
    read_ai_layers,
)

if TYPE_CHECKING:
    import os
    from typing import Any, Iterator

    Box = tuple[float, float, float, float]
    Matrix = tuple[float, float, float, float, float, float]
    #: `(widths, default width, y-min, y-max, two-byte)` in glyph space.
    Metrics = tuple[dict[int, float], float, float, float, bool]

__all__ = ["EMPTY_BOX", "footage_size", "read_ai_layer_bounds"]

#: Uniform expansion applied to a filled path or a shading, in points.
FILL_PAD = 0.25

#: Largest value the `opti` artwork box can store (signed big-endian 16.16).
FIXED_MAX = (2**31 - 1) / 65536.0

#: The box After Effects stores for a layer with no artwork: a `1/65536`
#: square at the page origin, which yields 1x1 footage.
EMPTY_BOX = (0.0, 0.0, 1 / 65536.0, 1 / 65536.0)

_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

#: Advance assumed for a glyph with no width from any source.
_DEFAULT_WIDTH = 500.0

#: `_font_metrics` for text shown with no `Tf`, i.e. with no font at all.
_NO_FONT_METRICS: Metrics = ({}, _DEFAULT_WIDTH, -250.0, 750.0, False)

#: Filters the stream decoder understands. Anything else is a hard stop rather
#: than a silently wrong measurement.
_SUPPORTED_FILTERS = frozenset({"FlateDecode", "Fl"})

_PAINT_OPS = frozenset({"S", "s", "f", "F", "f*", "B", "B*", "b", "b*", "n"})
_STROKE_OPS = frozenset({"S", "s", "B", "B*", "b", "b*"})
#: Render modes that stroke the glyphs. Modes 3 and 7 are invisible but are
#: still measured - After Effects does not skip them.
_STROKING_TEXT_MODES = frozenset({1, 2, 5, 6})

#: Encodings that put `quotesingle` at 39 and `grave` at 96, where the
#: fonts' built-in StandardEncoding puts `quoteright` and `quoteleft`.
_ASCII_QUOTE_ENCODINGS = frozenset({"WinAnsiEncoding", "MacRomanEncoding"})

_DELIMITERS = b"()<>[]{}/%"
_WHITESPACE = b" \t\r\n\f\x00"
_NUMBER_START = b"+-.0123456789"

#: An image's own space, which its CTM maps onto the page.
_UNIT_SQUARE = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
_ROOT_RE = re.compile(rb"/Root[ \t\r\n]+(\d+)[ \t\r\n]+\d+[ \t\r\n]+R")
_INLINE_IMAGE_END = re.compile(rb"[\s\x00]EI[\s\x00]|[\s\x00]EI$")


# --------------------------------------------------------------------------
# geometry


def _mat_mul(a: Matrix, b: Matrix) -> Matrix:
    """Concatenate two PDF matrices: the result applies `a` then `b`."""
    return (
        a[0] * b[0] + a[1] * b[2],
        a[0] * b[1] + a[1] * b[3],
        a[2] * b[0] + a[3] * b[2],
        a[2] * b[1] + a[3] * b[3],
        a[4] * b[0] + a[5] * b[2] + b[4],
        a[4] * b[1] + a[5] * b[3] + b[5],
    )


def _apply(m: Matrix, x: float, y: float) -> tuple[float, float]:
    return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])


class _Acc:
    """A growing axis-aligned bounding box."""

    __slots__ = ("x0", "y0", "x1", "y1")

    def __init__(self) -> None:
        self.x0 = self.y0 = math.inf
        self.x1 = self.y1 = -math.inf

    @property
    def empty(self) -> bool:
        return self.x0 > self.x1

    def add(self, x: float, y: float) -> None:
        if x < self.x0:
            self.x0 = x
        if y < self.y0:
            self.y0 = y
        if x > self.x1:
            self.x1 = x
        if y > self.y1:
            self.y1 = y

    def add_box(self, box: Box | None) -> None:
        if box is None:
            return
        self.add(box[0], box[1])
        self.add(box[2], box[3])

    def box(self) -> Box | None:
        if self.empty:
            return None
        return (self.x0, self.y0, self.x1, self.y1)


def _as_dict(value: Any) -> dict[str, Any] | None:
    """The dictionary of a plain dict or of a `Stream` object."""
    if isinstance(value, dict):
        return value
    dictionary = getattr(value, "dictionary", None)
    return dictionary if isinstance(dictionary, dict) else None


def _clamp(box: Box) -> Box:
    """Clamp a box to the range the `opti` fixed-point field can store."""
    return (
        max(-FIXED_MAX, min(FIXED_MAX, box[0])),
        max(-FIXED_MAX, min(FIXED_MAX, box[1])),
        max(-FIXED_MAX, min(FIXED_MAX, box[2])),
        max(-FIXED_MAX, min(FIXED_MAX, box[3])),
    )


def _grow(box: Box, dx: float, dy: float) -> Box:
    return (box[0] - dx, box[1] - dy, box[2] + dx, box[3] + dy)


def _intersect(current: Box | None, added: Box | None) -> Box | None:
    """Narrow a clip region by another clip path, as `W n` does.

    `None` means "no clip established", so it is the identity here. `None`
    also comes back for two boxes that miss entirely: an empty clip region
    paints nothing, which is what a missing clip yields at the one place the
    clip is read (`sh`).
    """
    if current is None:
        return added
    if added is None:
        return current
    box = (
        max(current[0], added[0]),
        max(current[1], added[1]),
        min(current[2], added[2]),
        min(current[3], added[3]),
    )
    return box if box[0] <= box[2] and box[1] <= box[3] else None


# --------------------------------------------------------------------------
# document access


class _Document:
    """Indirect-object and stream access for a PDF-compatible file."""

    def __init__(self, data: bytes, name: str) -> None:
        self._data = data
        self._name = name
        self._offsets = _object_offsets(data)
        self._cache: dict[int, Any] = {}
        self._catalog: dict[str, Any] | None = None
        self._check_supported()

    def _reject(self, why: str) -> UnsupportedAiLayersError:
        return UnsupportedAiLayersError(f"{self._name}: {why}")

    def _check_supported(self) -> None:
        """Reject structures the plain object scanner cannot see through.

        Illustrator writes classic cross-reference tables and uncompressed
        objects, so these paths are unreachable from Illustrator output - but a
        PDF from another producer would otherwise be measured from whatever
        objects the scanner happened to find.
        """
        if b"/ObjStm" in self._data:
            raise self._reject(
                "the file uses compressed object streams (/ObjStm), which "
                "py_aep cannot read; re-save it with PDF 1.4 compatibility"
            )
        if b"/Encrypt" in self._data:
            raise self._reject("the file is encrypted")

    def resolve(self, value: Any) -> Any:
        """Follow an indirect reference to its object; pass values through."""
        while isinstance(value, IndirectReference):
            number = value.object_number
            if number in self._cache:
                value = self._cache[number]
                break
            offset = self._offsets.get(number)
            if offset is None:
                return None
            resolved = _parse_object_at(self._data, offset)
            self._cache[number] = resolved
            value = resolved
        return value

    def number(self, value: Any, default: float = 0.0) -> float:
        resolved = self.resolve(value)
        if isinstance(resolved, bool) or not isinstance(resolved, (int, float)):
            return default
        return float(resolved)

    def get(self, mapping: Any, key: str, default: Any = None) -> Any:
        table = _as_dict(self.resolve(mapping))
        if table is None or key not in table:
            return default
        return self.resolve(table[key])

    def stream(self, value: Any) -> bytes:
        """The decoded body of a stream object."""
        reference = value
        value = self.resolve(value)
        body: bytes | None = None
        info: dict[str, Any] = {}
        # `Stream` instances carry (dict, raw); a plain dict needs the raw
        # bytes located from the object's own offset.
        raw = getattr(value, "data", None)
        if isinstance(raw, bytes):
            info = getattr(value, "dictionary", None) or {}
            body = raw
        elif isinstance(value, dict) and isinstance(reference, IndirectReference):
            info = value
            body = self._raw_stream(reference.object_number, value)
        if body is None:
            raise self._reject("unreadable content stream")
        filters = self.get(info, "Filter")
        names = [filters] if not isinstance(filters, list) else filters
        if self.get(info, "DecodeParms") is not None:
            raise self._reject(
                "the content stream uses a decode-parameter filter "
                "(predictors), which py_aep cannot decode"
            )
        for entry in names:
            if entry is None:
                continue
            filter_name = str(self.resolve(entry))
            if filter_name not in _SUPPORTED_FILTERS:
                raise self._reject(
                    f"the content stream uses the {filter_name} filter, which "
                    "py_aep cannot decode"
                )
            try:
                body = zlib.decompress(body)
            except zlib.error as exc:
                raise self._reject(f"corrupt content stream ({exc})") from exc
        return body

    def _raw_stream(self, number: int, info: dict[str, Any]) -> bytes | None:
        offset = self._offsets.get(number)
        if offset is None:
            return None
        start = self._data.find(b"stream", offset)
        if start < 0:
            return None
        start += len(b"stream")
        if self._data[start : start + 2] == b"\r\n":
            start += 2
        elif self._data[start : start + 1] in (b"\n", b"\r"):
            start += 1
        length = self.get(info, "Length")
        if isinstance(length, (int, float)) and not isinstance(length, bool):
            return self._data[start : start + int(length)]
        end = self._data.find(b"endstream", start)
        return self._data[start:end] if end > 0 else None

    def reject(self, why: str) -> UnsupportedAiLayersError:
        return self._reject(why)

    def catalog(self) -> dict[str, Any]:
        """The document catalog, named by the trailer's `/Root`.

        A file whose trailer is unreadable falls back to scanning the objects
        for the first `/Type /Catalog`, which is what the object scanner can
        see without a cross-reference table.
        """
        if self._catalog is not None:
            return self._catalog
        numbers = [int(n) for n in _ROOT_RE.findall(self._data)]
        # The last trailer wins: an incrementally updated file supersedes the
        # /Root of every earlier revision.
        numbers.reverse()
        numbers += list(self._offsets)
        for number in numbers:
            candidate = self.resolve(IndirectReference(number, 0))
            if (
                isinstance(candidate, dict)
                and str(candidate.get("Type", "")) == "Catalog"
            ):
                self._catalog = candidate
                return candidate
        raise self._reject("no document catalog")

    def first_page(self) -> dict[str, Any]:
        """The first page dictionary, in `/Kids` order."""
        pages = list(self._walk_pages(self.get(self.catalog(), "Pages"), 0))
        if not pages:
            raise self._reject("the document has no pages")
        if len(pages) > 1:
            warnings.warn(
                f"{self._name}: the document has {len(pages)} artboards. "
                "py_aep measures the first one; After Effects measures the "
                "second and reports first-artboard layers as empty, so the "
                "stored artwork box will differ from AE's.",
                UserWarning,
                # user -> read_ai_layer_bounds -> first_page -> warn
                stacklevel=3,
            )
        return pages[0]

    def _walk_pages(self, node: Any, depth: int) -> Iterator[dict[str, Any]]:
        node = _as_dict(self.resolve(node))
        if node is None or depth > 32:
            return
        if str(node.get("Type", "")) == "Page":
            yield node
            return
        kids = self.get(node, "Kids")
        for kid in kids if isinstance(kids, list) else []:
            yield from self._walk_pages(kid, depth + 1)

    def page_content(self, page: dict[str, Any]) -> bytes:
        """The page's content stream(s), concatenated and decoded."""
        contents = self.resolve(self.resolve(page).get("Contents"))
        parts = contents if isinstance(contents, list) else [contents]
        return b"\n".join(self.stream(part) for part in parts if part is not None)


# --------------------------------------------------------------------------
# content-stream tokenizer


def _tokenize(data: bytes) -> Iterator[tuple[str, Any]]:
    """Yield `(kind, value)` content-stream tokens.

    `kind` is one of `num`, `name`, `str`, `array`, `dict` or `op`. The COS
    parser in `py_aep.cos` cannot be reused here: its keyword lexer rejects
    unknown barewords and only accepts alphabetic ones, so content-stream
    operators (`re`, `f*`, `W*`, `'`) would all raise.
    """
    pos = 0
    size = len(data)
    while pos < size:
        char = data[pos : pos + 1]
        if char in _WHITESPACE:
            pos += 1
            continue
        if char == b"%":
            end = pos
            while end < size and data[end : end + 1] not in b"\r\n":
                end += 1
            pos = end
            continue
        if char == b"/":
            end = pos + 1
            while end < size:
                nxt = data[end : end + 1]
                if nxt in _WHITESPACE or nxt in _DELIMITERS:
                    break
                end += 1
            yield ("name", data[pos + 1 : end].decode("latin-1"))
            pos = end
            continue
        if char == b"(":
            literal, pos = _read_literal_string(data, pos)
            yield ("str", literal)
            continue
        if char == b"<":
            if data[pos + 1 : pos + 2] == b"<":
                mapping, pos = _read_dict(data, pos)
                yield ("dict", mapping)
                continue
            hexed = _read_hex_string(data, pos)
            if hexed is None:
                return
            literal, pos = hexed
            yield ("str", literal)
            continue
        if char == b"[":
            array, pos = _read_array(data, pos)
            yield ("array", array)
            continue
        if char in b"]>}{":
            pos += 1
            continue
        if char in _NUMBER_START:
            end = pos
            while end < size and data[end : end + 1] in b"+-.0123456789eE":
                end += 1
            try:
                yield ("num", float(data[pos:end]))
            except ValueError:
                yield ("num", 0.0)
            pos = end
            continue
        end = pos
        while end < size:
            nxt = data[end : end + 1]
            if nxt in _WHITESPACE or nxt in _DELIMITERS:
                break
            end += 1
        if end == pos:
            end += 1
        operator = data[pos:end].decode("latin-1")
        pos = end
        if operator == "BI":
            # An inline image's binary body is not tokenizable: skip to `EI`
            # and report the whole thing as one operator, so the measurer can
            # still take its box.
            match = _INLINE_IMAGE_END.search(data, pos)
            pos = match.end() if match else size
            yield ("op", "BI")
            continue
        yield ("op", operator)


def _read_literal_string(data: bytes, pos: int) -> tuple[bytes, int]:
    pos += 1
    depth = 1
    out = bytearray()
    size = len(data)
    while pos < size:
        char = data[pos : pos + 1]
        if char == b"\\":
            nxt = data[pos + 1 : pos + 2]
            simple = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f"}
            if nxt in simple:
                out += simple[nxt]
                pos += 2
            elif nxt.isdigit():
                pos += 1
                digits = b""
                while len(digits) < 3 and data[pos : pos + 1].isdigit():
                    digits += data[pos : pos + 1]
                    pos += 1
                out.append(int(digits, 8) & 0xFF)
            elif nxt in (b"\n", b"\r"):
                # PDF 7.3.4.2: a reverse solidus before an end-of-line marker
                # is a line continuation - both bytes are dropped. Keeping the
                # newline would measure it as one more glyph.
                pos += 2
                if nxt == b"\r" and data[pos : pos + 1] == b"\n":
                    pos += 1
            else:
                out += nxt
                pos += 2
            continue
        if char == b"(":
            depth += 1
        elif char == b")":
            depth -= 1
            if depth == 0:
                return (bytes(out), pos + 1)
        out += char
        pos += 1
    return (bytes(out), pos)


def _read_hex_string(data: bytes, pos: int) -> tuple[bytes, int] | None:
    """Decode a `<...>` hex string; `None` when it is never terminated.

    Shared by the operator tokenizer and the array/dictionary reader: a hex
    string inside a `TJ` array has to decode to the same bytes a bare `Tj`
    operand does, or its glyph codes come out as their own hex digits.
    """
    end = data.find(b">", pos)
    if end < 0:
        return None
    digits = re.sub(rb"[^0-9A-Fa-f]", b"", data[pos + 1 : end])
    if len(digits) % 2:
        digits += b"0"
    return (bytes.fromhex(digits.decode("ascii")), end + 1)


def _read_array(data: bytes, pos: int) -> tuple[list[Any], int]:
    pos += 1
    out: list[Any] = []
    size = len(data)
    while pos < size:
        if data[pos : pos + 1] == b"]":
            return (out, pos + 1)
        if data[pos : pos + 1] in _WHITESPACE:
            pos += 1
            continue
        sub = _next_simple(data, pos)
        if sub is None:
            return (out, pos + 1)
        value, pos = sub
        out.append(value)
    return (out, pos)


def _read_dict(data: bytes, pos: int) -> tuple[dict[str, Any], int]:
    pos += 2
    out: dict[str, Any] = {}
    size = len(data)
    key: str | None = None
    while pos < size:
        if data[pos : pos + 2] == b">>":
            return (out, pos + 2)
        if data[pos : pos + 1] in _WHITESPACE:
            pos += 1
            continue
        sub = _next_simple(data, pos)
        if sub is None:
            return (out, pos + 1)
        value, pos = sub
        if key is None:
            key = str(value)
        else:
            out[key] = value
            key = None
    return (out, pos)


def _next_simple(data: bytes, pos: int) -> tuple[Any, int] | None:
    """Read one array/dictionary element starting at `pos`."""
    char = data[pos : pos + 1]
    size = len(data)
    if char == b"/":
        end = pos + 1
        while end < size:
            nxt = data[end : end + 1]
            if nxt in _WHITESPACE or nxt in _DELIMITERS:
                break
            end += 1
        return (data[pos + 1 : end].decode("latin-1"), end)
    if char == b"(":
        return _read_literal_string(data, pos)
    if char == b"[":
        return _read_array(data, pos)
    if char == b"<":
        if data[pos + 1 : pos + 2] == b"<":
            return _read_dict(data, pos)
        return _read_hex_string(data, pos)
    if char in _NUMBER_START:
        end = pos
        while end < size and data[end : end + 1] in b"+-.0123456789eE":
            end += 1
        try:
            return (float(data[pos:end]), end)
        except ValueError:
            return (0.0, end)
    end = pos
    while end < size:
        nxt = data[end : end + 1]
        if nxt in _WHITESPACE or nxt in _DELIMITERS:
            break
        end += 1
    if end == pos:
        end += 1
    word = data[pos:end].decode("latin-1")
    if word == "true":
        return (True, end)
    if word == "false":
        return (False, end)
    return (None, end)


# --------------------------------------------------------------------------
# graphics state


class _GState:
    """The subset of the PDF graphics and text state the box depends on."""

    __slots__ = (
        "ctm",
        "clip",
        "line_width",
        "miter",
        "font",
        "metrics",
        "size",
        "char_spacing",
        "word_spacing",
        "h_scale",
        "leading",
        "rise",
        "render_mode",
    )

    def __init__(self) -> None:
        self.ctm: Matrix = _IDENTITY
        self.clip: Box | None = None
        self.line_width = 1.0
        self.miter = 10.0
        self.font: dict[str, Any] | None = None
        self.metrics: Metrics = _NO_FONT_METRICS
        self.size = 0.0
        self.char_spacing = 0.0
        self.word_spacing = 0.0
        self.h_scale = 100.0
        self.leading = 0.0
        self.rise = 0.0
        self.render_mode = 0

    def copy(self) -> _GState:
        clone = _GState()
        for slot in _GState.__slots__:
            setattr(clone, slot, getattr(self, slot))
        return clone

    def stroke_half_width(self) -> tuple[float, float]:
        """The stroke half-width in device space, per axis.

        After Effects expands a stroked path by the line width scaled through
        each of the CTM's column norms independently, so a `4 0 0 1 cm` with a
        10pt line expands x by 20 and y by 5. A single geometric-mean scale
        would give 10 for both.
        """
        half = self.line_width / 2.0
        return (
            half * math.hypot(self.ctm[0], self.ctm[1]),
            half * math.hypot(self.ctm[2], self.ctm[3]),
        )


def _base_encoding(doc: _Document, font: dict[str, Any]) -> str:
    """The font's base encoding name, empty when it uses its built-in one."""
    encoding = doc.get(font, "Encoding")
    table = _as_dict(doc.resolve(encoding))
    if table is not None:
        return str(doc.get(table, "BaseEncoding", ""))
    return "" if encoding is None else str(encoding)


def _builtin_widths(
    doc: _Document, font: dict[str, Any], base: str
) -> dict[int, float]:
    """The advances After Effects supplies for a font with no `/Widths`."""
    table = STD14_WIDTHS.get(base)
    if table is None:
        return {}
    widths = {STD14_FIRST_CODE + i: float(w) for i, w in enumerate(table)}
    quotes = STD14_STANDARD_QUOTES.get(base)
    if quotes is not None and _base_encoding(doc, font) not in _ASCII_QUOTE_ENCODINGS:
        widths[39], widths[96] = float(quotes[0]), float(quotes[1])
    return widths


def _font_metrics(doc: _Document, font: dict[str, Any] | None) -> Metrics:
    """`(widths, default width, y-min, y-max, two-byte)` in glyph space.

    The vertical extent comes from the descriptor's `/FontBBox`, **not** its
    `/Ascent`/`/Descent`: every font Illustrator embeds happens to give both
    the same values, but a font where they disagree measures by the
    `/FontBBox`.
    """
    if not isinstance(font, dict):
        return _NO_FONT_METRICS
    subtype = str(doc.get(font, "Subtype", ""))
    if subtype == "Type0":
        return _type0_metrics(doc, font)
    first = int(doc.number(font.get("FirstChar"), 0.0))
    raw_widths = doc.get(font, "Widths")
    widths: dict[int, float] = {}
    if isinstance(raw_widths, list):
        for index, entry in enumerate(raw_widths):
            widths[first + index] = doc.number(entry)
    descriptor = doc.get(font, "FontDescriptor")
    base = _base_font(str(doc.get(font, "BaseFont", "")))
    default = doc.number(doc.get(descriptor, "MissingWidth"), 0.0)
    if not widths:
        widths = _builtin_widths(doc, font, base)
    y_min, y_max = _vertical_extent(doc, descriptor, STD14_EXTENT.get(base))
    return (widths, default or _DEFAULT_WIDTH, y_min, y_max, False)


def _type0_metrics(doc: _Document, font: dict[str, Any]) -> Metrics:
    descendants = doc.get(font, "DescendantFonts")
    child = (
        doc.resolve(descendants[0])
        if isinstance(descendants, list) and descendants
        else {}
    )
    default = doc.number(doc.get(child, "DW"), 1000.0) or 1000.0
    widths: dict[int, float] = {}
    table = doc.get(child, "W")
    entries = table if isinstance(table, list) else []
    index = 0
    while index < len(entries):
        start = doc.number(entries[index])
        following = (
            doc.resolve(entries[index + 1]) if index + 1 < len(entries) else None
        )
        if isinstance(following, list):
            for offset, value in enumerate(following):
                widths[int(start) + offset] = doc.number(value)
            index += 2
        elif index + 2 < len(entries):
            end = int(doc.number(entries[index + 1]))
            value = doc.number(entries[index + 2])
            for code in range(int(start), end + 1):
                widths[code] = value
            index += 3
        else:
            break
    descriptor = doc.get(child, "FontDescriptor")
    y_min, y_max = _vertical_extent(doc, descriptor, None)
    return (widths, default, y_min, y_max, True)


def _vertical_extent(
    doc: _Document, descriptor: Any, std: tuple[float, float] | None
) -> tuple[float, float]:
    bbox = doc.get(descriptor, "FontBBox")
    if isinstance(bbox, list) and len(bbox) == 4:
        return (doc.number(bbox[1]), doc.number(bbox[3]))
    if isinstance(doc.resolve(descriptor), dict):
        return (
            doc.number(doc.get(descriptor, "Descent"), -250.0),
            doc.number(doc.get(descriptor, "Ascent"), 750.0),
        )
    if std is not None:
        return std
    return (-250.0, 750.0)


def _base_font(name: str) -> str:
    """Strip a subset tag and a style suffix from a `/BaseFont` name."""
    return name.split("+")[-1].split(",")[0]


# --------------------------------------------------------------------------
# the measuring pass


class _Measurer:
    """Accumulates each optional content group's artwork box."""

    def __init__(self, doc: _Document) -> None:
        self._doc = doc
        self.boxes: dict[int, _Acc] = {}
        self._stack: list[int] = []

    def _target(self) -> _Acc | None:
        """The box of the innermost open optional content group."""
        for number in reversed(self._stack):
            if number >= 0:
                return self.boxes.setdefault(number, _Acc())
        return None

    def _resource(self, resources: Any, category: str, name: Any) -> Any:
        return self._doc.get(self._doc.get(resources, category), str(name))

    def _resource_ref(self, resources: Any, category: str, name: Any) -> Any:
        table = _as_dict(self._doc.resolve(self._doc.get(resources, category)))
        if table is None:
            return None
        return table.get(str(name))

    def run(  # noqa: C901 - a flat operator dispatch, clearer in one place
        self,
        content: bytes,
        resources: Any,
    ) -> None:
        gs = _GState()
        saved: list[_GState] = []
        operands: list[Any] = []
        segments: list[tuple[Any, ...]] = []
        current: tuple[float, float] | None = None
        start: tuple[float, float] | None = None
        from_rect = False
        pending_clip = False
        text_matrix: Matrix = _IDENTITY
        line_matrix: Matrix = _IDENTITY

        for kind, value in _tokenize(content):
            if kind != "op":
                operands.append(value)
                continue
            op = value
            if op == "q":
                saved.append(gs.copy())
            elif op == "Q":
                if saved:
                    gs = saved.pop()
            elif op == "cm" and len(operands) >= 6:
                gs.ctm = _mat_mul(tuple(operands[-6:]), gs.ctm)  # type: ignore[arg-type]
            elif op == "w" and operands:
                gs.line_width = float(operands[-1])
            elif op == "M" and operands:
                gs.miter = float(operands[-1])
            elif op == "gs" and operands:
                ext = self._resource(resources, "ExtGState", operands[-1])
                if isinstance(ext, dict) and "LW" in ext:
                    gs.line_width = self._doc.number(ext["LW"], gs.line_width)
            # ---- path construction
            elif op == "m" and len(operands) >= 2:
                current = start = (float(operands[-2]), float(operands[-1]))
            elif op == "l" and len(operands) >= 2 and current is not None:
                point = (float(operands[-2]), float(operands[-1]))
                segments.append(("l", current, point))
                current = point
            elif op == "c" and len(operands) >= 6 and current is not None:
                a = [float(v) for v in operands[-6:]]
                segments.append(
                    ("c", current, (a[0], a[1]), (a[2], a[3]), (a[4], a[5]))
                )
                current = (a[4], a[5])
            elif op == "v" and len(operands) >= 4 and current is not None:
                a = [float(v) for v in operands[-4:]]
                segments.append(("c", current, current, (a[0], a[1]), (a[2], a[3])))
                current = (a[2], a[3])
            elif op == "y" and len(operands) >= 4 and current is not None:
                a = [float(v) for v in operands[-4:]]
                end = (a[2], a[3])
                segments.append(("c", current, (a[0], a[1]), end, end))
                current = end
            elif op == "h":
                if current is not None and start is not None and current != start:
                    segments.append(("l", current, start))
                current = start
            elif op == "re" and len(operands) >= 4:
                x, y, width, height = (float(v) for v in operands[-4:])
                corners = [
                    (x, y),
                    (x + width, y),
                    (x + width, y + height),
                    (x, y + height),
                ]
                for index in range(4):
                    segments.append(("l", corners[index], corners[(index + 1) % 4]))
                current = start = (x, y)
                from_rect = True
            elif op in ("W", "W*"):
                pending_clip = True
            elif op in _PAINT_OPS:
                if segments:
                    if op != "n":
                        self._commit_path(gs, segments, op in _STROKE_OPS, from_rect)
                    if pending_clip:
                        gs.clip = _intersect(gs.clip, self._hull(gs, segments))
                pending_clip = False
                segments = []
                from_rect = False
                current = start = None
            elif op == "sh":
                # A shading paints the whole clip region.
                target = self._target()
                if target is not None and gs.clip is not None:
                    target.add_box(_clamp(_grow(gs.clip, FILL_PAD, FILL_PAD)))
            elif op == "Do" and operands:
                self._draw_xobject(gs, resources, operands[-1])
            elif op == "BI":
                # Inferred from the `q_image` probe layer rather than measured
                # on its own: an inline image is the same painting operator as
                # an image XObject, spelled inline. Illustrator never emits one.
                self._add_image(gs.ctm)
            # ---- optional content
            elif op in ("BDC", "BMC"):
                number = -1
                if op == "BDC" and len(operands) >= 2 and str(operands[-2]) == "OC":
                    reference = self._resource_ref(
                        resources, "Properties", operands[-1]
                    )
                    if isinstance(reference, IndirectReference):
                        number = reference.object_number
                self._stack.append(number)
            elif op == "EMC":
                if self._stack:
                    self._stack.pop()
            # ---- text
            elif op == "BT":
                text_matrix = line_matrix = _IDENTITY
            elif op == "Tf" and len(operands) >= 2:
                font = self._resource(resources, "Font", operands[-2])
                gs.font = font if isinstance(font, dict) else None
                # The metrics are a property of the font, so they are resolved
                # here rather than rebuilt for every text-showing operator.
                gs.metrics = _font_metrics(self._doc, gs.font)
                gs.size = float(operands[-1])
            elif op == "Tm" and len(operands) >= 6:
                text_matrix = line_matrix = tuple(  # type: ignore[assignment]
                    float(v) for v in operands[-6:]
                )
            elif op in ("Td", "TD") and len(operands) >= 2:
                if op == "TD":
                    gs.leading = -float(operands[-1])
                line_matrix = _mat_mul(
                    (1.0, 0.0, 0.0, 1.0, float(operands[-2]), float(operands[-1])),
                    line_matrix,
                )
                text_matrix = line_matrix
            elif op == "T*":
                line_matrix = _mat_mul(
                    (1.0, 0.0, 0.0, 1.0, 0.0, -gs.leading), line_matrix
                )
                text_matrix = line_matrix
            elif op == "TL" and operands:
                gs.leading = float(operands[-1])
            elif op == "Tc" and operands:
                gs.char_spacing = float(operands[-1])
            elif op == "Tw" and operands:
                gs.word_spacing = float(operands[-1])
            elif op == "Tz" and operands:
                gs.h_scale = float(operands[-1])
            elif op == "Ts" and operands:
                gs.rise = float(operands[-1])
            elif op == "Tr" and operands:
                gs.render_mode = int(operands[-1])
            elif op in ("Tj", "TJ", "'", '"') and operands:
                if op in ("'", '"'):
                    line_matrix = _mat_mul(
                        (1.0, 0.0, 0.0, 1.0, 0.0, -gs.leading), line_matrix
                    )
                    text_matrix = line_matrix
                shown = operands[-1]
                items = shown if isinstance(shown, list) else [shown]
                text_matrix = self._show_text(gs, text_matrix, items)
            operands = []

    # -- contributions ----------------------------------------------------

    def _hull(self, gs: _GState, segments: list[tuple[Any, ...]]) -> Box | None:
        """The control-point hull of a path, in device space.

        After Effects measures the hull, not the true curve bounds, so a
        control point far outside the drawn curve still counts.
        """
        acc = _Acc()
        for segment in segments:
            for point in segment[1:]:
                acc.add(*_apply(gs.ctm, point[0], point[1]))
        return acc.box()

    def _commit_path(
        self,
        gs: _GState,
        segments: list[tuple[Any, ...]],
        stroked: bool,
        from_rect: bool,
    ) -> None:
        target = self._target()
        if target is None:
            return
        hull = self._hull(gs, segments)
        if hull is None:
            return
        hull = _clamp(hull)
        if not stroked:
            target.add_box(_clamp(_grow(hull, FILL_PAD, FILL_PAD)))
            return
        # A stroke's expansion depends only on the shape class, never on the
        # join or cap style: a `re` gets the exact 90-degree miter, a lone
        # straight segment gets no join term at all, and everything else gets
        # a worst-case half the miter limit. A path that is both filled and
        # stroked uses this alone - the fill pad is not also applied.
        if from_rect:
            factor = math.sqrt(2.0)
        elif len(segments) == 1 and segments[0][0] == "l":
            factor = 1.0
        else:
            factor = gs.miter / 2.0
        half_x, half_y = gs.stroke_half_width()
        target.add_box(_clamp(_grow(hull, half_x * factor, half_y * factor)))

    def _draw_xobject(self, gs: _GState, resources: Any, name: Any) -> None:
        """A form or image XObject contributes its box with no expansion."""
        xobject = _as_dict(self._resource(resources, "XObject", name))
        if xobject is None:
            return
        target = self._target()
        if target is None:
            return
        doc = self._doc
        ctm = gs.ctm
        subtype = str(doc.get(xobject, "Subtype", ""))
        if subtype == "Form":
            matrix = doc.get(xobject, "Matrix")
            if isinstance(matrix, list) and len(matrix) == 6:
                ctm = _mat_mul(
                    tuple(doc.number(v) for v in matrix),  # type: ignore[arg-type]
                    ctm,
                )
        bbox = doc.get(xobject, "BBox")
        if isinstance(bbox, list) and len(bbox) == 4:
            x0, y0, x1, y1 = (doc.number(v) for v in bbox)
            acc = _Acc()
            for point in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
                acc.add(*_apply(ctm, point[0], point[1]))
            box = acc.box()
            if box is not None:
                target.add_box(_clamp(box))
        elif subtype == "Image":
            self._add_image(ctm)

    def _add_image(self, ctm: Matrix) -> None:
        """An image contributes its unit square through the CTM, unexpanded."""
        target = self._target()
        if target is None:
            return
        acc = _Acc()
        for point in _UNIT_SQUARE:
            acc.add(*_apply(ctm, point[0], point[1]))
        box = acc.box()
        if box is not None:
            target.add_box(_clamp(box))

    def _show_text(self, gs: _GState, text_matrix: Matrix, items: list[Any]) -> Matrix:
        """Measure a text-showing operator and advance the text matrix."""
        widths, default, y_min, y_max, two_byte = gs.metrics
        target = self._target()
        scale = gs.h_scale / 100.0
        for item in items:
            if isinstance(item, (int, float)) and not isinstance(item, bool):
                shift = -float(item) / 1000.0 * gs.size * scale
                text_matrix = _mat_mul((1.0, 0.0, 0.0, 1.0, shift, 0.0), text_matrix)
                continue
            if not isinstance(item, bytes):
                continue
            if two_byte:
                codes = [
                    int.from_bytes(item[index : index + 2], "big")
                    for index in range(0, len(item) - 1, 2)
                ]
            else:
                codes = list(item)
            for code in codes:
                width = widths.get(code, default) / 1000.0
                spacing = gs.char_spacing
                if code == 32 and not two_byte:
                    spacing += gs.word_spacing
                advance = (width * gs.size + spacing) * scale
                if target is not None:
                    self._add_glyph_cell(
                        gs, target, text_matrix, advance, y_min, y_max, width
                    )
                text_matrix = _mat_mul((1.0, 0.0, 0.0, 1.0, advance, 0.0), text_matrix)
        return text_matrix

    def _add_glyph_cell(
        self,
        gs: _GState,
        target: _Acc,
        text_matrix: Matrix,
        advance: float,
        y_min: float,
        y_max: float,
        width: float,
    ) -> None:
        """Add one glyph's cell: pen to pen-plus-advance by the font's box.

        The horizontal extent is the full advance, so character and word
        spacing widen the cell. Invisible render modes are measured too; the
        stroking modes grow the cell by the stroke half-width.
        """
        scale = gs.h_scale / 100.0
        render = _mat_mul(
            (gs.size * scale, 0.0, 0.0, gs.size, 0.0, gs.rise), text_matrix
        )
        render = _mat_mul(render, gs.ctm)
        horizontal = advance / (gs.size * scale) if gs.size and scale else width
        acc = _Acc()
        for x, y in (
            (0.0, y_min / 1000.0),
            (horizontal, y_min / 1000.0),
            (horizontal, y_max / 1000.0),
            (0.0, y_max / 1000.0),
        ):
            acc.add(*_apply(render, x, y))
        box = acc.box()
        if box is None:
            return
        if gs.render_mode in _STROKING_TEXT_MODES:
            half_x, half_y = gs.stroke_half_width()
            box = _grow(box, half_x, half_y)
        target.add_box(_clamp(box))


# --------------------------------------------------------------------------
# public entry point


def read_ai_layer_bounds(
    file: str | os.PathLike[str], data: bytes | None = None
) -> list[Box | None]:
    """Return each Illustrator/PDF layer's artwork bounds in document order.

    The bounds are the box After Effects stores for a "Layer Size" import,
    in page points with the origin at the page's bottom-left corner, as
    `(x0, y0, x1, y1)`. They are a conservative estimate of the artwork
    extent, not its true visual bounds - see the module docstring.

    Args:
        file: Path to a `.ai` or `.pdf` file.
        data: The file's bytes, if the caller already read them.

    Returns:
        One entry per layer in `resolvers.ai_layers.read_ai_layers` order
        (bottom layer first), `None` for a layer with no artwork on the page.

    Warns:
        UserWarning: If the document has more than one artboard, where After
            Effects measures the second page and py_aep measures the first.

    Raises:
        UnsupportedAiLayersError: If the file is not a PDF-compatible
            document, has no layers, or uses PDF structures py_aep cannot
            read (compressed object streams, encryption, or a content-stream
            filter other than Flate).
    """
    path = Path(file)
    if data is None:
        data = path.read_bytes()
    names = read_ai_layers(path, data)
    doc = _Document(data, path.name)
    page = doc.first_page()
    measurer = _Measurer(doc)
    measurer.run(doc.page_content(page), doc.get(page, "Resources"))
    # `read_ai_layers` walks the same `/OCGs` array, so the nth name and the
    # nth reference line up.
    order = _ocg_numbers(doc, len(names))
    return [
        measurer.boxes[number].box() if number in measurer.boxes else None
        for number in order
    ]


def footage_size(box: Box | None) -> tuple[int, int]:
    """The footage pixel size After Effects derives from an artwork box.

    The box reaches AE through the `opti`'s signed 16.16 field, and AE sizes
    the footage from what it reads back, so the extent is quantized before it
    is ceilinged - an extent that lands a float hair above an integer must not
    gain a pixel. A layer with no artwork floors at 1x1.

    Args:
        box: An entry of `read_ai_layer_bounds`, or `None` for an empty layer.
    """
    x0, y0, x1, y1 = (round(v * 65536) for v in (EMPTY_BOX if box is None else box))
    return (
        max(1, math.ceil((x1 - x0) / 65536.0)),
        max(1, math.ceil((y1 - y0) / 65536.0)),
    )


def _ocg_numbers(doc: _Document, expected: int) -> list[int]:
    """The object numbers of the catalog's `/OCGs` array, in document order."""
    properties = doc.get(doc.catalog(), "OCProperties")
    if properties is None:  # pragma: no cover - read_ai_layers already checked
        raise doc.reject("no optional content groups")
    ocgs = doc.get(properties, "OCGs")
    numbers = [
        entry.object_number
        for entry in (ocgs if isinstance(ocgs, list) else [])
        if isinstance(entry, IndirectReference)
    ]
    if len(numbers) != expected:  # pragma: no cover - defensive
        raise doc.reject("the optional content groups could not be enumerated")
    return numbers
