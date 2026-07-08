"""Text range models mirroring the AE 24.3+ ExtendScript range API.

`CharacterRange`, `ParagraphRange` and `ComposedLineRange` are computed,
read-only views over a [TextDocument][py_aep.models.text.TextDocument]'s
parsed COS data. They are created via the `TextDocument` factory methods
(`character_range`, `paragraph_range`, `composed_line_range`), never
constructed directly - matching ExtendScript, where `new CharacterRange()`
does not exist.

Index semantics (probed against AE 26.3, see
`samples/models/text/text_ranges_probe.json`):

* All indices are UTF-16 code units, exactly as in ExtendScript. Astral
  characters (e.g. emoji) count as two units, and AE allows ranges that
  split a surrogate pair - `text` then contains a lone surrogate.
* Style-run, kerning-run and composed-line counts stored in the COS data
  cover the raw text, which carries one terminator `\\r` beyond the
  user-visible text. Boundaries are clamped to the visible length.
* Ranges resolve dynamically: they hold their creation parameters and
  re-evaluate bounds on every access, so a range can become invalid (or
  valid again) as the backing document changes.
* Composed lines are a layout cache written by AE at save time. py_aep
  cannot recompose text; after py-side edits the cache goes stale with
  the same observable behavior as AE's own un-reapplied TextDocument
  values: counts stay cached, line boundaries clamp to the current text,
  and lines that fall wholly outside raise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar, cast, overload

from ...cos import cos_get
from ...enums import (
    AutoKernType,
    BaselineDirection,
    DigitSet,
    FontBaselineOption,
    FontCapsOption,
    LeadingType,
    LineJoinType,
    ParagraphDirection,
    ParagraphJustification,
)

if TYPE_CHECKING:
    from typing import Any, Callable

    from ...enums import ComposerEngine
    from .font_object import FontObject
    from .text_document import TextDocument

T = TypeVar("T")

_SENTINEL = object()

# AE's exact error strings (AE 26.3, English locale); py_aep raises these
# from ValueError so behavior parity does not depend on hosting AE.
CHARACTER_RANGE_OOB = "Character index range is outside of TextDocument bounds."
PARAGRAPH_RANGE_OOB = "Paragraph index range is outside of TextDocument bounds."
COMPOSED_LINE_OOB = (
    "ComposedLine index range is outside of TextDocument composed lines."
)
NOT_ASSOCIATED = "Unable to set value as it is not associated with a layer."


# ---------------------------------------------------------------------------
# UTF-16 code-unit helpers (AE index semantics)
# ---------------------------------------------------------------------------


def u16_len(s: str) -> int:
    """Length of `s` in UTF-16 code units (AE / ExtendScript indexing)."""
    extra = 0
    for c in s:
        if ord(c) > 0xFFFF:
            extra += 1
    return len(s) + extra


def u16_slice(s: str, start: int, end: int) -> str:
    """Slice `s` by UTF-16 code-unit offsets.

    A slice that splits a surrogate pair yields a lone surrogate, exactly
    as AE does (`surrogatepass` keeps it representable in a `str`).
    """
    if u16_len(s) == len(s):
        return s[start:end]
    data = s.encode("utf-16-be", "surrogatepass")
    return data[2 * start : 2 * end].decode("utf-16-be", "surrogatepass")


# ---------------------------------------------------------------------------
# COS accessors shared with TextDocument
# ---------------------------------------------------------------------------


def _raw_text(doc: TextDocument) -> str:
    """The stored text, including the terminator `\\r`."""
    val = cos_get(doc._doc, "0", "0")
    return str(val) if val is not None else ""


def _visible_length(doc: TextDocument) -> int:
    """Length in UTF-16 units of the user-visible text.

    The stored run counts cover one trailing terminator `\\r` that
    ExtendScript's indices never expose; everything user-facing is
    clamped to this length.
    """
    raw = _raw_text(doc)
    n = u16_len(raw)
    if raw.endswith("\r"):
        return n - 1
    return n


def _run_spans(
    doc: TextDocument, doc_key: str, style_key: str | None
) -> list[tuple[int, int, dict[str, Any]]]:
    """Decode a COS run array into `(start, end, payload)` spans.

    Run arrays (`doc["0"]["5"/"6"/"8"]["0"]`) store `{"0": payload,
    "1": count}` entries whose counts are UTF-16 units over the raw
    text. `style_key` picks the style sub-dict for paragraph ("5") and
    character ("6") runs; kerning runs ("8") use their payload directly.
    """
    runs = cos_get(doc._doc, "0", doc_key, "0")
    spans: list[tuple[int, int, dict[str, Any]]] = []
    if not isinstance(runs, list):
        return spans
    pos = 0
    for run in runs:
        length = run.get("1") if isinstance(run, dict) else None
        if not isinstance(length, int) or length < 0:
            continue
        if style_key is None:
            payload = cos_get(run, "0")
        else:
            payload = cos_get(run, "0", "0", style_key)
        spans.append((pos, pos + length, payload if isinstance(payload, dict) else {}))
        pos += length
    return spans


def _char_run_spans(doc: TextDocument) -> list[tuple[int, int, dict[str, Any]]]:
    """Character style-run spans."""
    return _run_spans(doc, "6", "6")


def _para_run_spans(doc: TextDocument) -> list[tuple[int, int, dict[str, Any]]]:
    """Paragraph style-run spans (one run per paragraph)."""
    return _run_spans(doc, "5", "5")


def _kern_run_spans(doc: TextDocument) -> list[tuple[int, int, dict[str, Any]]]:
    """Manual-kerning run spans; payload key `"0"` holds the value."""
    return _run_spans(doc, "8", None)


def _composed_line_spans(doc: TextDocument) -> list[tuple[int, int]] | None:
    """Composed-line `(start, end)` spans from the persisted layout cache.

    The cache lives at `doc["1"]["2"]` as a `/PC` node; `/L` records are
    collected depth-first through the nested `"6"` arrays and each line's
    length is the sum of its `/S` segment counts (`seg["15"]["0"]`).
    Returns `None` when the document has no cache.
    """
    entries = cos_get(doc._doc, "1", "2")
    if not isinstance(entries, list):
        return None
    lengths: list[int] = []

    def collect(node: Any) -> None:
        if not isinstance(node, dict):
            return
        if str(node.get("99")) == "L":
            total = 0
            children = node.get("6")
            if isinstance(children, list):
                for seg in children:
                    count = cos_get(seg, "15", "0")
                    if isinstance(count, int):
                        total += count
            lengths.append(total)
            return
        children = node.get("6")
        if isinstance(children, list):
            for child in children:
                collect(child)

    for entry in entries:
        collect(entry)
    if not lengths:
        return None
    spans: list[tuple[int, int]] = []
    pos = 0
    for length in lengths:
        spans.append((pos, pos + length))
        pos += length
    return spans


def _parse_color(paint: object) -> list[float] | None:
    """Extract `[R, G, B]` from a COS SimplePaint structure."""
    argb = cos_get(paint, "0", "1")
    if isinstance(argb, list) and len(argb) >= 4:
        return [float(argb[1]), float(argb[2]), float(argb[3])]
    return None


# ---------------------------------------------------------------------------
# RangeField descriptor
# ---------------------------------------------------------------------------


class RangeField(Generic[T]):
    """Read-only descriptor resolving one COS style key over a range.

    Evaluates the key across every style run overlapping the owning
    [CharacterRange][] with AE's mixed-value semantics: a uniform value
    is returned, disagreement reads as `None` (ExtendScript
    `undefined`). `gate` names a boolean style key that must be truthy
    for a run to participate at all (AE gates `strokeColor` on
    `applyStroke` and `fillColor` on `applyFill`); when no overlapping
    run passes the gate the field reads `None`.

    Unlike [CosField][py_aep.cos.CosField] this descriptor never writes:
    range writes require style-run splitting, which py_aep does not
    support yet.

    Args:
        kind: `"char"` or `"para"` - which run array to resolve over.
        key: String key into each run's style dict.
        transform: Optional callable applied to each stored value.
        default: Per-run value when the key is absent from a run.
        gate: Optional boolean style key gating run participation.
    """

    def __init__(
        self,
        kind: str,
        key: str,
        *,
        transform: Callable[..., Any] | None = None,
        default: Any = None,
        gate: str | None = None,
    ) -> None:
        self.kind = kind
        self.key = key
        self.transform = transform
        self.default = default
        self.gate = gate

    def __set_name__(self, owner: type, name: str) -> None:
        self.public_name = name

    @overload
    def __get__(self, obj: None, objtype: type) -> RangeField[T]: ...

    @overload
    def __get__(self, obj: Any, objtype: type | None = None) -> T | None: ...

    def __get__(
        self, obj: Any, objtype: type | None = None
    ) -> T | None | RangeField[T]:
        if obj is None:
            return self
        return cast(
            "T | None",
            obj._resolve_mixed(
                self.kind, self.key, self.transform, self.default, self.gate
            ),
        )

    def __set__(self, obj: Any, value: Any) -> None:
        raise AttributeError(
            f"{self.public_name!r} is read-only; text range writes are not supported."
        )

    @classmethod
    def bool(cls, kind: str, key: str, **kwargs: Any) -> RangeField[bool]:
        """Create a RangeField for boolean style flags."""
        return cast("RangeField[bool]", cls(kind, key, transform=bool, **kwargs))

    @classmethod
    def float(cls, kind: str, key: str, **kwargs: Any) -> RangeField[float]:
        """Create a RangeField that coerces to float."""
        return cast("RangeField[float]", cls(kind, key, transform=float, **kwargs))

    @classmethod
    def enum(
        cls, enum_cls: type[T], kind: str, key: str, **kwargs: Any
    ) -> RangeField[T]:
        """Create a RangeField for IntEnum-backed style keys."""
        if "transform" not in kwargs:
            kwargs["transform"] = getattr(enum_cls, "from_binary", enum_cls)
        return cls(kind, key, **kwargs)


# ---------------------------------------------------------------------------
# CharacterRange
# ---------------------------------------------------------------------------


class CharacterRange:
    """A contiguous character span of a [TextDocument][].

    Created via `TextDocument.character_range(character_start,
    signed_character_end)`. Most `TextDocument` styling attributes are
    readable on the range; when the range spans style runs with
    differing values the attribute reads `None` (ExtendScript
    `undefined`). Bounds re-resolve on every access, so a range created
    valid raises `ValueError` once the document shrinks beneath it.

    Zero-span ranges (`character_start == character_end`) are valid and
    report the style at that caret position with an empty `text`.

    See: https://ae-scripting.docsforadobe.dev/text/characterrange/
    """

    def __init__(
        self, doc: TextDocument, character_start: int, signed_character_end: int
    ) -> None:
        self._doc_ref = doc
        self._start = character_start
        self._signed_end = signed_character_end
        # AE validates at creation time and raises immediately.
        self._bounds()

    # -- Bounds --------------------------------------------------------------

    def _bounds(self) -> tuple[int, int]:
        """Resolve `(start, end)` against the current document.

        Raises:
            ValueError: When the range is outside the document bounds.
        """
        visible = _visible_length(self._doc_ref)
        end = visible if self._signed_end == -1 else self._signed_end
        if (
            self._start < 0
            or self._start > visible
            or end < self._start
            or end > visible
        ):
            raise ValueError(CHARACTER_RANGE_OOB)
        return self._start, end

    @property
    def character_start(self) -> int:
        """The range's first character index. Read-only."""
        return self._bounds()[0]

    @property
    def character_end(self) -> int:
        """The range's last character index + 1. Read-only."""
        return self._bounds()[1]

    @property
    def is_range_valid(self) -> bool:
        """`True` while the range lies within the document bounds. Read-only."""
        try:
            self._bounds()
        except ValueError:
            return False
        return True

    def __str__(self) -> str:
        return f"CharacterRange({self._start},{self._signed_end})"

    def __repr__(self) -> str:
        return f"<py_aep.CharacterRange({self._start},{self._signed_end})>"

    # -- Mixed-value resolution ----------------------------------------------

    def _overlapping(
        self, spans: list[tuple[int, int, dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        """Run payloads overlapping the half-open range.

        A zero-span range resolves to the single run containing its
        caret index (the raw runs cover the terminator, so an EOF caret
        still lands inside the final run).
        """
        start, end = self._bounds()
        if start == end:
            for run_start, run_end, payload in spans:
                if run_start <= start < run_end:
                    return [payload]
            return [spans[-1][2]] if spans else []
        return [
            payload
            for run_start, run_end, payload in spans
            if run_start < end and run_end > start
        ]

    def _spans_for(self, kind: str) -> list[tuple[int, int, dict[str, Any]]]:
        if kind == "char":
            return _char_run_spans(self._doc_ref)
        if kind == "para":
            return _para_run_spans(self._doc_ref)
        return _kern_run_spans(self._doc_ref)

    def _resolve_mixed(
        self,
        kind: str,
        key: str,
        transform: Callable[..., Any] | None,
        default: Any,
        gate: str | None,
    ) -> Any:
        """Resolve one style key over the overlapping runs.

        Uniform value -> that value; disagreement -> `None`; every run
        gated out -> `None`.
        """
        payloads = self._overlapping(self._spans_for(kind))
        if gate is not None:
            payloads = [p for p in payloads if p.get(gate)]
            if not payloads:
                return None
        if not payloads:
            return default
        values = []
        for payload in payloads:
            raw = payload.get(key, _SENTINEL)
            if raw is _SENTINEL:
                value = default
            elif transform is not None:
                try:
                    value = transform(raw)
                except (TypeError, ValueError, KeyError, IndexError):
                    value = default
            else:
                value = raw
            values.append(value)
        first = values[0]
        for value in values[1:]:
            if value != first:
                return None
        return first

    # -- Content ---------------------------------------------------------------

    @property
    def text(self) -> str:
        """The text within the range. Read-only.

        Line breaks are normalized to `\\n` like `TextDocument.text`
        (ExtendScript returns raw `\\r`). A range splitting a surrogate
        pair yields a lone surrogate, as in AE.
        """
        start, end = self._bounds()
        return u16_slice(_raw_text(self._doc_ref), start, end).replace("\r", "\n")

    # -- Character style fields --------------------------------------------------

    font_size = RangeField.float("char", "1")
    """The range's font size in pixels; `None` when mixed. Read-only."""

    faux_bold = RangeField.bool("char", "2")
    """`True` if faux bold is enabled across the range. Read-only."""

    faux_italic = RangeField.bool("char", "3")
    """`True` if faux italic is enabled across the range. Read-only."""

    auto_leading = RangeField.bool("char", "4", default=True)
    """The range's auto-leading option; `None` when mixed. Read-only."""

    horizontal_scale = RangeField.float("char", "6")
    """The range's horizontal scale; `None` when mixed. Read-only."""

    vertical_scale = RangeField.float("char", "7")
    """The range's vertical scale; `None` when mixed. Read-only."""

    tracking = RangeField.float("char", "8")
    """The range's spacing between characters; `None` when mixed. Read-only."""

    baseline_shift = RangeField.float("char", "9")
    """The range's baseline shift in pixels; `None` when mixed. Read-only."""

    auto_kern_type = RangeField.enum(
        AutoKernType, "char", "11", default=AutoKernType.NO_AUTO_KERN
    )
    """The range's auto kern type option; `None` when mixed. Read-only."""

    font_caps_option = RangeField.enum(FontCapsOption, "char", "12")
    """The range's font caps option; `None` when mixed. Read-only."""

    font_baseline_option = RangeField.enum(FontBaselineOption, "char", "13")
    """The range's font baseline option; `None` when mixed. Read-only."""

    ligature = RangeField.bool("char", "18", default=False)
    """`True` when ligature is used across the range. Read-only."""

    baseline_direction = RangeField.enum(
        BaselineDirection, "char", "35", default=BaselineDirection.BASELINE_WITH_STREAM
    )
    """The range's baseline direction; `None` when mixed. Read-only."""

    tsume = RangeField.float("char", "36", default=0.0)
    """The range's tsume value (0.0 to 1.0); `None` when mixed. Read-only."""

    no_break = RangeField.bool("char", "52", default=False)
    """`True` when no-break is applied across the range. Read-only."""

    apply_fill = RangeField.bool("char", "56")
    """When `True`, the range shows a fill; `None` when mixed. Read-only."""

    apply_stroke = RangeField.bool("char", "57", default=False)
    """When `True`, the range shows a stroke; `None` when mixed. Read-only."""

    stroke_over_fill = RangeField.bool("char", "58", default=True)
    """When `True`, the stroke appears over the fill; `None` when mixed. Read-only."""

    line_join_type = RangeField.enum(
        LineJoinType, "char", "62", default=LineJoinType.LINE_JOIN_MITER
    )
    """The range's line join type for strokes; `None` when mixed. Read-only."""

    stroke_width = RangeField.float("char", "63", default=1.0)
    """The range's stroke thickness; `None` when mixed. Read-only."""

    digit_set = RangeField.enum(DigitSet, "char", "70", default=DigitSet.DEFAULT_DIGITS)
    """The range's digit set option; `None` when mixed. Read-only."""

    # -- Paragraph style fields (resolved over paragraph runs) -------------------

    justification = RangeField.enum(ParagraphJustification, "para", "0")
    """The justification of paragraphs in the range; `None` when mixed. Read-only."""

    first_line_indent = RangeField.float("para", "1", default=0.0)
    """The paragraphs' first line indent; `None` when mixed. Read-only."""

    start_indent = RangeField.float("para", "2", default=0.0)
    """The paragraphs' start indent; `None` when mixed. Read-only."""

    end_indent = RangeField.float("para", "3", default=0.0)
    """The paragraphs' end indent; `None` when mixed. Read-only."""

    space_before = RangeField.float("para", "4", default=0.0)
    """The paragraphs' space before; `None` when mixed. Read-only."""

    space_after = RangeField.float("para", "5", default=0.0)
    """The paragraphs' space after; `None` when mixed. Read-only."""

    leading_type = RangeField.enum(
        LeadingType, "para", "8", default=LeadingType.ROMAN_LEADING_TYPE
    )
    """The paragraphs' leading type; `None` when mixed. Read-only."""

    auto_hyphenate = RangeField.bool("para", "9")
    """The paragraphs' auto-hyphenate option; `None` when mixed. Read-only."""

    hanging_roman = RangeField.bool("para", "21", default=False)
    """The paragraphs' Roman Hanging Punctuation; `None` when mixed. Read-only."""

    every_line_composer = RangeField.bool("para", "29", default=False)
    """The paragraphs' Every-Line Composer option; `None` when mixed. Read-only."""

    direction = RangeField.enum(
        ParagraphDirection,
        "para",
        "33",
        default=ParagraphDirection.DIRECTION_LEFT_TO_RIGHT,
    )
    """The paragraphs' direction; `None` when mixed. Read-only."""

    # -- Computed style properties ------------------------------------------------

    @property
    def fill_color(self) -> list[float] | None:
        """The range's fill color as `[r, g, b]`. Read-only.

        Only characters with `apply_fill` participate; `None` when no
        character in the range has a fill or the colors are mixed.
        """
        return cast(
            "list[float] | None",
            self._resolve_mixed("char", "53", _parse_color, None, "56"),
        )

    @property
    def stroke_color(self) -> list[float] | None:
        """The range's stroke color as `[r, g, b]`. Read-only.

        Only characters with `apply_stroke` participate; `None` when no
        character in the range has a stroke or the colors are mixed.
        """
        return cast(
            "list[float] | None",
            self._resolve_mixed("char", "54", _parse_color, None, "57"),
        )

    @property
    def font(self) -> str | None:
        """The range's font PostScript name; `None` when mixed. Read-only."""
        font_obj = self.font_object
        return font_obj.post_script_name if font_obj is not None else None

    @property
    def font_object(self) -> FontObject | None:
        """The range's [FontObject][]; `None` when mixed. Read-only."""
        idx = self._resolve_mixed("char", "0", None, None, None)
        fonts = self._doc_ref._fonts
        if isinstance(idx, int) and 0 <= idx < len(fonts):
            return fonts[idx]
        return None

    @property
    def leading(self) -> float | None:
        """The range's spacing between lines. Read-only.

        AE reads `undefined` while auto-leading is active (or mixed)
        anywhere in the range; the explicit value only surfaces when
        auto-leading is uniformly disabled.
        """
        auto = self.auto_leading
        if auto is None or auto:
            return None
        return cast("float | None", self._resolve_mixed("char", "5", float, None, None))

    @property
    def kerning(self) -> int | None:
        """The range's manual kerning value. Read-only.

        AE reads `undefined` unless auto-kerning is uniformly disabled
        over the range; the values themselves live in dedicated kerning
        runs (`doc["0"]["8"]`) and read `None` when mixed.
        """
        if self.auto_kern_type != AutoKernType.NO_AUTO_KERN:
            return None
        value = self._resolve_mixed("kern", "0", None, 0, None)
        return value if isinstance(value, int) else None

    @property
    def all_caps(self) -> bool | None:
        """`True` if the range has All Caps enabled; `None` when mixed. Read-only."""
        caps = self.font_caps_option
        if caps is None:
            return None
        return caps == FontCapsOption.FONT_ALL_CAPS

    @property
    def small_caps(self) -> bool | None:
        """`True` if the range has Small Caps enabled; `None` when mixed. Read-only."""
        caps = self.font_caps_option
        if caps is None:
            return None
        return caps == FontCapsOption.FONT_SMALL_CAPS

    @property
    def superscript(self) -> bool | None:
        """`True` if the range is superscript; `None` when mixed. Read-only."""
        baseline = self.font_baseline_option
        if baseline is None:
            return None
        return baseline == FontBaselineOption.FONT_FAUXED_SUPERSCRIPT

    @property
    def subscript(self) -> bool | None:
        """`True` if the range is subscript; `None` when mixed. Read-only."""
        baseline = self.font_baseline_option
        if baseline is None:
            return None
        return baseline == FontBaselineOption.FONT_FAUXED_SUBSCRIPT

    @property
    def composer_engine(self) -> ComposerEngine | None:
        """The document's composer engine (document-wide). Read-only."""
        return self._doc_ref.composer_engine


# ---------------------------------------------------------------------------
# ParagraphRange / ComposedLineRange
# ---------------------------------------------------------------------------


class ParagraphRange:
    """A paragraph span of a [TextDocument][].

    Created via `TextDocument.paragraph_range(paragraph_index_start,
    signed_paragraph_index_end)`. Paragraph character boundaries include
    each paragraph's trailing `\\r`; the final boundary is clamped to
    the visible text length, so a trailing empty paragraph reports a
    zero-span range.

    See: https://ae-scripting.docsforadobe.dev/text/paragraphrange/
    """

    def __init__(
        self, doc: TextDocument, paragraph_start: int, signed_paragraph_end: int
    ) -> None:
        self._doc_ref = doc
        self._start = paragraph_start
        self._signed_end = signed_paragraph_end
        self._char_bounds()

    def _char_bounds(self) -> tuple[int, int]:
        """Resolve the paragraph indices to character bounds.

        Raises:
            ValueError: When the paragraph indices are out of bounds.
        """
        spans = _para_run_spans(self._doc_ref)
        count = len(spans)
        end = count if self._signed_end == -1 else self._signed_end
        if self._start < 0 or self._start >= count or end <= self._start or end > count:
            raise ValueError(PARAGRAPH_RANGE_OOB)
        visible = _visible_length(self._doc_ref)
        return min(spans[self._start][0], visible), min(spans[end - 1][1], visible)

    @property
    def character_start(self) -> int:
        """The range's calculated first character index. Read-only."""
        return self._char_bounds()[0]

    @property
    def character_end(self) -> int:
        """The range's calculated last character index + 1. Read-only."""
        return self._char_bounds()[1]

    @property
    def is_range_valid(self) -> bool:
        """`True` while the range lies within the document bounds. Read-only."""
        try:
            self._char_bounds()
        except ValueError:
            return False
        return True

    def character_range(self) -> CharacterRange:
        """A [CharacterRange][] fixed to the current character bounds.

        The returned range holds resolved indices and does not follow
        later changes to this `ParagraphRange`'s paragraphs.
        """
        start, end = self._char_bounds()
        return CharacterRange(self._doc_ref, start, end)

    def __str__(self) -> str:
        return f"ParagraphRange({self._start},{self._signed_end})"

    def __repr__(self) -> str:
        return f"<py_aep.ParagraphRange({self._start},{self._signed_end})>"


class ComposedLineRange:
    """A composed-line span of a [TextDocument][].

    Created via `TextDocument.composed_line_range(
    composed_line_index_start, signed_composed_line_index_end)`.
    Composed lines come from the layout cache AE persisted at save
    time; py_aep cannot recompose text, so after py-side edits the
    ranges behave like AE's own un-reapplied TextDocument values: line
    boundaries clamp to the current text and lines falling wholly
    outside it raise `ValueError`.

    See: https://ae-scripting.docsforadobe.dev/text/composedlinerange/
    """

    def __init__(
        self, doc: TextDocument, composed_line_start: int, signed_composed_line_end: int
    ) -> None:
        self._doc_ref = doc
        self._start = composed_line_start
        self._signed_end = signed_composed_line_end
        self._char_bounds()

    def _char_bounds(self) -> tuple[int, int]:
        """Resolve the line indices to character bounds.

        Raises:
            ValueError: When the line indices are out of bounds, or the
                cached line lies wholly outside the current text.
        """
        spans = _composed_line_spans(self._doc_ref)
        if spans is None:
            raise ValueError(COMPOSED_LINE_OOB)
        count = len(spans)
        end = count if self._signed_end == -1 else self._signed_end
        if self._start < 0 or self._start >= count or end <= self._start or end > count:
            raise ValueError(COMPOSED_LINE_OOB)
        visible = _visible_length(self._doc_ref)
        start_char = spans[self._start][0]
        # A stale cached line lying wholly beyond the current text raises;
        # a line starting exactly at the end is a valid zero-span (e.g. the
        # trailing empty paragraph's line).
        if start_char > visible:
            raise ValueError(COMPOSED_LINE_OOB)
        return start_char, min(spans[end - 1][1], visible)

    @property
    def character_start(self) -> int:
        """The range's calculated first character index. Read-only."""
        return self._char_bounds()[0]

    @property
    def character_end(self) -> int:
        """The range's calculated last character index + 1. Read-only."""
        return self._char_bounds()[1]

    @property
    def is_range_valid(self) -> bool:
        """`True` while the range lies within the document bounds. Read-only."""
        try:
            self._char_bounds()
        except ValueError:
            return False
        return True

    def character_range(self) -> CharacterRange:
        """A [CharacterRange][] fixed to the current character bounds.

        The returned range holds resolved indices and does not follow
        later changes to this `ComposedLineRange`'s lines.
        """
        start, end = self._char_bounds()
        return CharacterRange(self._doc_ref, start, end)

    def __str__(self) -> str:
        return f"ComposedLineRange({self._start},{self._signed_end})"

    def __repr__(self) -> str:
        return f"<py_aep.ComposedLineRange({self._start},{self._signed_end})>"
