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

import copy
from typing import TYPE_CHECKING, Generic, TypeVar, cast, overload

from ...cos import CosField, CosName, cos_get, run_spans
from ...cos.descriptors import _extract
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
from ...resolvers.text_composition import CompositionUnsupported, compose_lines
from ...svg.fonts import font_version_string
from ..validators import (
    validate_bool,
    validate_enum,
    validate_font_name,
    validate_normalized_float,
    validate_number,
    validate_positive_nonzero_number,
    validate_positive_number,
    validate_rgb_color,
    validate_s4,
    validate_text,
)
from .font_object import FontObject

if TYPE_CHECKING:
    from typing import Any, Callable

    from ...enums import ComposerEngine
    from .text_document import TextDocument

T = TypeVar("T")

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
    # ASCII (the common case) has no astral characters; skip the per-char
    # scan with a single C-level check. This primitive underlies almost
    # every range read and style write.
    if s.isascii():
        return len(s)
    return len(s) + sum(ord(c) > 0xFFFF for c in s)


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


def _char_run_spans(doc: TextDocument) -> list[tuple[int, int, dict[str, Any]]]:
    """Character style-run spans."""
    return run_spans(doc._doc, "6", "6")


def _para_run_spans(doc: TextDocument) -> list[tuple[int, int, dict[str, Any]]]:
    """Paragraph style-run spans (one run per paragraph)."""
    return run_spans(doc._doc, "5", "5")


def _kern_run_spans(doc: TextDocument) -> list[tuple[int, int, dict[str, Any]]]:
    """Manual-kerning run spans; payload key `"0"` holds the value."""
    return run_spans(doc._doc, "8", None)


def _cached_line_nodes(doc: TextDocument) -> list[dict[str, Any]]:
    """The persisted `/L` line records of the layout cache, in order.

    The cache lives at `doc["1"]["2"]` as a `/PC` node; `/L` records are
    collected depth-first through the nested `"6"` arrays. Empty when the
    document has no cache.
    """
    entries = cos_get(doc._doc, "1", "2")
    if not isinstance(entries, list):
        return []
    lines: list[dict[str, Any]] = []

    def collect(node: Any) -> None:
        if not isinstance(node, dict):
            return
        if str(node.get("99")) == "L":
            lines.append(node)
            return
        children = node.get("6")
        if isinstance(children, list):
            for child in children:
                collect(child)

    for entry in entries:
        collect(entry)
    return lines


def _cached_line_data(
    doc: TextDocument,
) -> tuple[list[tuple[int, int]], list[float | None]] | None:
    """Line `(start, end)` spans + baselines from the persisted cache.

    Returns `None` when the document has no cache. Callers that also need
    the `/L` nodes should fetch them once with `_cached_line_nodes` and
    use `_line_data_from_nodes` to avoid a second cache walk.
    """
    return _line_data_from_nodes(_cached_line_nodes(doc))


def _line_data_from_nodes(
    nodes: list[dict[str, Any]],
) -> tuple[list[tuple[int, int]], list[float | None]] | None:
    """Line `(start, end)` spans + baselines from `/L` cache nodes.

    Each line's length is the sum of its `/S` segment counts
    (`seg["15"]["0"]`) and its baseline is the `/L` `"10"` value. Returns
    `None` for an empty node list (no cache).
    """
    lengths: list[int] = []
    baselines: list[float | None] = []
    for node in nodes:
        total = 0
        children = node.get("6")
        if isinstance(children, list):
            for seg in children:
                count = cos_get(seg, "15", "0")
                if isinstance(count, int):
                    total += count
        lengths.append(total)
        baseline = node.get("10")
        baselines.append(
            float(baseline) if isinstance(baseline, (int, float)) else None
        )
    if not lengths:
        return None
    spans: list[tuple[int, int]] = []
    pos = 0
    for length in lengths:
        spans.append((pos, pos + length))
        pos += length
    return spans, baselines


def _line_origin(node: dict[str, Any]) -> tuple[float, float]:
    """A `/L` record's pen origin `(x, y)` in composition-cache space.

    Stored at `/L "0" "0"`; AE omits it on the first line (origin `(0, 0)`),
    where the baseline key `"10"` is absent too.
    """
    origin = cos_get(node, "0", "0")
    if isinstance(origin, list) and len(origin) >= 2:
        return float(origin[0]), float(origin[1])
    baseline = node.get("10")
    y = float(baseline) if isinstance(baseline, (int, float)) else 0.0
    return 0.0, y


def _line_advances(node: dict[str, Any]) -> list[float]:
    """Per-code-unit cumulative pen advances across a `/L` record's
    `/S` segments (`seg["15"]["7"]["7"]`).

    AE does not split segments on style or font changes - every observed
    line (including mixed-font ones) carries a single segment whose
    advances are cumulative from the line start. Multiple segments are
    chained by carrying the running total forward.
    """
    out: list[float] = []
    base = 0.0
    children = node.get("6")
    if not isinstance(children, list):
        return out
    for seg in children:
        advances = cos_get(seg, "15", "7", "7")
        if not isinstance(advances, list):
            continue
        for advance in advances:
            if isinstance(advance, (int, float)):
                out.append(base + float(advance))
        if out:
            base = out[-1]
    return out


def _fresh_composed_spans(doc: TextDocument) -> list[tuple[int, int]] | None:
    """Recompose the document when its calibration proved the composer.

    Returns `None` when the composer never calibrated against this
    document's own AE cache or now refuses it (envelope change) - the
    caller falls back to the stale-clamp semantics. The result (spans
    or the refusal) is cached on the document; every layout-affecting
    write invalidates it via `TextDocument._mark_layout_dirty`.
    """
    if getattr(doc, "_composition_calibrated", None) is not True:
        return None
    if "_composed_cache" in doc.__dict__:
        memo: list[tuple[int, int]] | None = doc.__dict__["_composed_cache"]
        return memo
    try:
        spans: list[tuple[int, int]] | None = compose_lines(doc).spans
    except CompositionUnsupported:
        spans = None
    doc.__dict__["_composed_cache"] = spans
    return spans


def _composed_line_spans(doc: TextDocument) -> list[tuple[int, int]] | None:
    """Composed-line `(start, end)` spans for the document's CURRENT state.

    Point text never wraps, so its composed lines ARE the paragraphs
    (fixture-proven) - always fresh, no cache involved. Box text reads
    the persisted AE cache while the document is untouched; after a
    layout-affecting py-side write it recomposes via
    `resolvers.text_composition` when the per-document calibration
    succeeded, otherwise the stale cache (with
    the AE-parity clamp semantics) remains.
    """
    if not getattr(doc, "box_text", False):
        para = _para_run_spans(doc)
        if not para:
            return None
        return [(start, end) for start, end, _style in para]
    if getattr(doc, "_layout_dirty", False):
        fresh = _fresh_composed_spans(doc)
        if fresh is not None:
            return fresh
    cached = _cached_line_data(doc)
    return cached[0] if cached is not None else None


def _parse_color(paint: object) -> list[float] | None:
    """Extract `[R, G, B]` from a COS SimplePaint structure."""
    argb = cos_get(paint, "0", "1")
    if isinstance(argb, list) and len(argb) >= 4:
        return [float(argb[1]), float(argb[2]), float(argb[3])]
    return None


def _build_color_paint(rgb: list[float]) -> dict[str, Any]:
    """Build a COS SimplePaint dict from `[R, G, B]`.

    The 4-float array is `[alpha, R, G, B]`; AE stores a fully opaque
    alpha of `1.0`.
    """
    return {
        "99": CosName("SimplePaint"),
        "0": {"0": 1, "1": [1.0, float(rgb[0]), float(rgb[1]), float(rgb[2])]},
    }


def _build_font_entry(post_script_name: str) -> dict[str, Any]:
    """Build a COS CoolTypeFont entry for a font PostScript name."""
    return {"0": {"99": CosName("CoolTypeFont"), "0": {"0": post_script_name, "2": 1}}}


def _register_font_at(
    doc: TextDocument,
    post_script_name: str,
    index: int = 0,
    *,
    used_record: bool = True,
) -> int:
    """Insert a font entry at `index` and reindex the existing references.

    Every reference at or after `index` is bumped by one. Font indices live
    in the char-run styles of every keyframe document sharing this
    `_cos_data`, the document-default character style at `cos["1"]["2"]`,
    the typography settings at `cos["1"]["0"]`, the used-font records at
    `cos["1"]["5"][*]["4"]` (which also gain a record for the new font) and
    the header style presets at `cos["0"]["5"]["0"]`; the layout cache holds
    none. The host font's version string (name ID 5) is stamped on the entry
    and the used-font record like AE does, when the font is installed.

    `index` 0 is AE's insertion point for a new font on a style write
    (probed: `W_FONT`, `W_PASTE_XDOC`); `Project.replace_font` inserts
    directly after the font being replaced instead, and passes
    `used_record=False` because a replacement repoints the used-font
    record of the font it replaces rather than adding one. Returns `index`.
    """
    cos = doc._cos_data
    font_array = cos.setdefault("0", {}).setdefault("1", {}).setdefault("0", [])
    entry = _build_font_entry(post_script_name)
    version = font_version_string(post_script_name)
    if version is not None:
        entry["0"]["0"]["5"] = version
    font_array.insert(index, entry)

    def bump(holder: dict[str, Any]) -> None:
        current = holder.get("0")
        if isinstance(current, int) and current >= index:
            holder["0"] = current + 1

    for entry_doc in cos.get("1", {}).get("1", []) or []:
        runs = cos_get(entry_doc, "0", "6", "0")
        if not isinstance(runs, list):
            continue
        for run in runs:
            style = cos_get(run, "0", "0", "6")
            if isinstance(style, dict):
                bump(style)
    default_char = cos_get(cos, "1", "2")
    if isinstance(default_char, dict):
        bump(default_char)
    typography = cos_get(cos, "1", "0", "0")
    if isinstance(typography, dict):
        bump(typography)
    presets = cos_get(cos, "0", "5", "0")
    if isinstance(presets, list):
        for preset in presets:
            style = cos_get(preset, "0", "6")
            if isinstance(style, dict):
                bump(style)
    sessions = cos_get(cos, "1", "5")
    new_record: dict[str, Any] = {"0": index}
    if version is not None:
        new_record["1"] = version
    if isinstance(sessions, list):
        appended = False
        for session in sessions:
            records = session.get("4") if isinstance(session, dict) else None
            if not isinstance(records, list):
                continue
            for record in records:
                if isinstance(record, dict):
                    bump(record)
            if used_record and not appended:
                records.append(new_record)
                appended = True
    doc._fonts.insert(
        index, FontObject(_font_data=entry["0"]["0"], _font_entry=entry["0"])
    )
    return index


def _replace_layer_font(docs: list[TextDocument], from_name: str, to_name: str) -> bool:
    """Repoint one text layer's `from_name` character runs at `to_name`.

    All of a layer's keyframe documents share one font table and one COS
    tree, so the font is registered once per layer. After Effects inserts
    the replacement directly AFTER the font it replaces and leaves the old
    entry in place (probed AE 2026: `Verdana`@0 -> `Georgia`@1), which is
    what `_register_font_at` reproduces.

    A font table can hold SEVERAL entries with one PostScript name (AE
    writes a second `MyriadPro-Regular` when a style reset re-applies the
    panel font), and the runs may reference any of them, so every entry
    carrying `from_name` is matched - taking only the first would silently
    skip layers whose runs point at a later duplicate.
    """
    first = docs[0]
    from_indices = {
        i for i, font in enumerate(first._fonts) if font.post_script_name == from_name
    }
    if not from_indices:
        return False
    if not any(
        style.get("0") in from_indices
        for doc in docs
        for _start, _end, style in _char_run_spans(doc)
    ):
        return False

    to_index = next(
        (i for i, font in enumerate(first._fonts) if font.post_script_name == to_name),
        None,
    )
    if to_index is None:
        # Inserting past the LAST matching entry leaves every from-index
        # unshifted (`_register_font_at` only bumps references at or after
        # the insertion point).
        to_index = _register_font_at(
            first, to_name, max(from_indices) + 1, used_record=False
        )

    for doc in docs:
        for _start, _end, style in _char_run_spans(doc):
            if style.get("0") in from_indices:
                style["0"] = to_index
    _repoint_used_font_record(first, from_indices, to_index, to_name)
    first._propagate_cos()
    return True


def _repoint_used_font_record(
    doc: TextDocument, from_indices: set[int], to_index: int, to_name: str
) -> None:
    """Point the replaced font's used-font records at its replacement.

    After Effects rewrites the existing record in place - index and name-ID-5
    version - rather than appending one and leaving the now-unused font
    behind (probed AE 2026: Verdana's record becomes Georgia's).
    """
    version = font_version_string(to_name)
    sessions = cos_get(doc._cos_data, "1", "5")
    if not isinstance(sessions, list):
        return
    for session in sessions:
        records = session.get("4") if isinstance(session, dict) else None
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict) or record.get("0") not in from_indices:
                continue
            record["0"] = to_index
            if version is None:
                record.pop("1", None)
            else:
                record["1"] = version


# ---------------------------------------------------------------------------
# Write engine (run splitting / merging)
#
# All rules below are AE-probed via samples/models/text/text_writes.aep;
# see .claude/plans/text-range-writes.md for the fixture-to-rule mapping.
# ---------------------------------------------------------------------------


#: Char-style keys that cannot change line composition (paints, their
#: gates, stroke geometry); every other style write marks the layout
#: dirty so the composed-line APIs know the cache no longer applies.
_NON_LAYOUT_CHAR_KEYS = frozenset({"53", "54", "56", "57", "58", "62", "63"})


def _mark_layout_dirty(doc: TextDocument) -> None:
    """Flag a layout-affecting write on documents that track it.

    Must run BEFORE the mutation lands: the first call calibrates the
    composer against the still-clean cache (see
    `TextDocument._mark_layout_dirty`). Duck-typed test documents
    without the hook are skipped.
    """
    mark = getattr(doc, "_mark_layout_dirty", None)
    if mark is not None:
        mark()


def _refresh_style_aliases(doc: TextDocument) -> None:
    """Re-point `_char_style` / `_para_style` at the current first runs.

    TextDocument's document-level accessors alias the first run's style
    dict by object identity; merges can replace that object, so every
    structural op must end here.
    """
    char = cos_get(doc._doc, "0", "6", "0", 0, "0", "0", "6")
    if isinstance(char, dict):
        doc._char_style = char
    para = cos_get(doc._doc, "0", "5", "0", 0, "0", "0", "5")
    if isinstance(para, dict):
        doc._para_style = para


def _snap_to_pairs(raw: str, start: int, end: int) -> tuple[int, int]:
    """Expand u16 boundaries outward so they never split a surrogate pair.

    AE expands a mid-pair style write to cover the whole pair
    (`W_SURROGATE_STYLE`). A zero-span caret cannot expand - it moves
    past the pair instead, so caret writes stay zero-span no-ops
    (`W_ZERO_STYLE`) rather than covering (or deleting) the glyph.
    """
    # No astral characters -> no surrogate pairs to split, so snapping is a
    # no-op. Skips the repeated full-text scans below on the common (BMP)
    # path; matches the fast-path guard in `u16_slice`.
    if u16_len(raw) == len(raw):
        return start, end

    def mid_pair(index: int) -> bool:
        if index <= 0 or index >= u16_len(raw):
            return False
        before = u16_slice(raw, index - 1, index)
        after = u16_slice(raw, index, index + 1)
        return 0xD800 <= ord(before) <= 0xDBFF and 0xDC00 <= ord(after) <= 0xDFFF

    if start == end:
        if mid_pair(start):
            return start + 1, end + 1
        return start, end
    if mid_pair(start):
        start -= 1
    if mid_pair(end):
        end += 1
    return start, end


def _split_run_array(runs: list[dict[str, Any]], offsets: set[int]) -> None:
    """Split `{"0": payload, "1": count}` entries in place at u16 offsets.

    The original entry keeps its identity as the LEFT fragment, so run
    0's payload object only ever narrows (never detaches) and the
    `_char_style` alias stays inside the serialized tree.
    """
    cuts = sorted(offsets)
    pos = 0
    i = 0
    while i < len(runs):
        length = runs[i].get("1", 0)
        run_end = pos + length
        cut = None
        for offset in cuts:
            if pos < offset < run_end:
                cut = offset
                break
        if cut is None:
            pos = run_end
            i += 1
            continue
        clone = copy.deepcopy(runs[i])
        runs[i]["1"] = cut - pos
        clone["1"] = run_end - cut
        runs.insert(i + 1, clone)
        pos = cut
        i += 1


def _merge_adjacent_runs(runs: list[dict[str, Any]]) -> None:
    """Coalesce adjacent runs whose full payloads compare equal.

    AE merges after every write (`W_MERGE_SAME`, `W_PARTIAL_EQ`) and a
    no-op set leaves a uniform document at one run (`W_NOOP`). The first
    run of each merged group keeps its object (aliasing, key order).
    """
    i = 0
    while i + 1 < len(runs):
        if runs[i].get("0") == runs[i + 1].get("0"):
            runs[i]["1"] = runs[i].get("1", 0) + runs[i + 1].get("1", 0)
            del runs[i + 1]
        else:
            i += 1


def _apply_char_key(
    doc: TextDocument, start: int, end: int, key: str, value: Any
) -> None:
    """Write one char-style key over `[start, end)` with AE's rules.

    Zero-span writes are silent no-ops (`W_ZERO_STYLE`); a write ending
    at the visible length extends through the raw terminator
    (`W_MERGE_SAME`); `value=None` clears the key.
    """
    raw = _raw_text(doc)
    start, end = _snap_to_pairs(raw, start, end)
    if start == end:
        return
    if key not in _NON_LAYOUT_CHAR_KEYS:
        _mark_layout_dirty(doc)
    if end == _visible_length(doc):
        end = u16_len(raw)
    runs = cos_get(doc._doc, "0", "6", "0")
    if not isinstance(runs, list) or not runs:
        return
    _split_run_array(runs, {start, end})
    pos = 0
    for run in runs:
        run_end = pos + run.get("1", 0)
        if pos >= start and run_end <= end:
            style = cos_get(run, "0", "0", "6")
            if isinstance(style, dict):
                if value is None:
                    style.pop(key, None)
                else:
                    style[key] = value
        pos = run_end
    _merge_adjacent_runs(runs)
    _refresh_style_aliases(doc)


def _kern_values(doc: TextDocument) -> list[Any]:
    """Per-character manual-kern values decoded from the kern runs."""
    total = u16_len(_raw_text(doc))
    values: list[Any] = [None] * total
    for start, end, payload in _kern_run_spans(doc):
        value = payload.get("0")
        if value is not None:
            for i in range(start, min(end, total)):
                values[i] = value
    return values


def _rebuild_kern_runs(doc: TextDocument, values: list[Any]) -> None:
    """Re-emit the kern-run array from a per-character value map.

    AE stores kerned characters as individual length-1 runs and merges
    only the empty gaps (probed `W_KERN_MID` / `W_KERN_START`); the
    array covers the raw text contiguously. The `doc["0"]["8"]` holder
    dict is kept in place when it exists so `doc["0"]`'s key order is
    preserved; a fresh key is appended, like AE's creation order.
    """
    inner = doc._doc.setdefault("0", {})
    has_value = any(v is not None for v in values)
    if not has_value:
        # AE drops the array entirely once no manual values remain
        # (probed `X_AKT_SET`); the leading-edge value at "7" only
        # exists alongside the array, so it goes too.
        inner.pop("8", None)
        inner.pop("7", None)
        return
    runs: list[dict[str, Any]] = []
    i = 0
    total = len(values)
    while i < total:
        if values[i] is None:
            j = i
            while j < total and values[j] is None:
                j += 1
            runs.append({"0": {}, "1": j - i})
            i = j
        else:
            runs.append({"0": {"0": values[i]}, "1": 1})
            i += 1
    holder = inner.get("8")
    if isinstance(holder, dict):
        holder["0"] = runs
    else:
        inner["8"] = {"0": runs}


def _splice_text(
    doc: TextDocument,
    start: int,
    end: int,
    new_text: str,
    insert_runs: list[dict[str, Any]] | None = None,
    insert_kern: list[Any] | None = None,
) -> None:
    """Replace `[start, end)` of the raw text, splicing every run array.

    AE's probed rules: the replacement takes the style of the first
    replaced character (the caret's containing run for zero-span
    inserts), a `\\r` in the replacement splits paragraphs (the donor
    paragraph's run is cloned), kern values survive for untouched
    characters only, and the trailing terminator is preserved
    (`W_TEXT_*`, `X_TEXT_KERN`, `X_TEXT_END`). `insert_runs` /
    `insert_kern` override the donor styling for paste transplants.
    """
    raw = _raw_text(doc)
    total = u16_len(raw)
    insert_len = u16_len(new_text)
    if start == end and insert_len == 0 and insert_runs is None:
        return
    _mark_layout_dirty(doc)
    kern_values = _kern_values(doc)
    new_raw = u16_slice(raw, 0, start) + new_text + u16_slice(raw, end, total)
    parts = new_raw.split("\r")
    if parts[-1] == "":
        parts = parts[:-1]
    inner = doc._doc.setdefault("0", {})

    runs = cos_get(inner, "6", "0")
    if isinstance(runs, list) and runs:
        if insert_runs is None:
            donor = None
            pos = 0
            for run in runs:
                run_end = pos + run.get("1", 0)
                if pos <= start < run_end:
                    donor = copy.deepcopy(run)
                    break
                pos = run_end
            if donor is None:
                donor = copy.deepcopy(runs[-1])
            donor["1"] = insert_len
            insert_entries = [donor] if insert_len else []
        else:
            insert_entries = insert_runs
        _split_run_array(runs, {start, end})
        rebuilt: list[dict[str, Any]] = []
        pos = 0
        inserted = False
        for run in runs:
            run_end = pos + run.get("1", 0)
            if run_end <= start:
                rebuilt.append(run)
            elif pos >= end:
                if not inserted:
                    rebuilt.extend(insert_entries)
                    inserted = True
                rebuilt.append(run)
            pos = run_end
        if not inserted:
            rebuilt.extend(insert_entries)
        runs[:] = rebuilt
        _merge_adjacent_runs(runs)

    para_runs = cos_get(inner, "5", "0")
    if isinstance(para_runs, list) and para_runs:
        old_spans: list[tuple[int, int, dict[str, Any]]] = []
        pos = 0
        for entry in para_runs:
            length = entry.get("1", 0)
            old_spans.append((pos, pos + length, entry))
            pos += length

        def donor_entry(new_pos: int) -> dict[str, Any]:
            if new_pos < start:
                old_pos = new_pos
            elif new_pos >= start + insert_len:
                old_pos = new_pos - insert_len + (end - start)
            else:
                old_pos = start
            old_pos = min(old_pos, total - 1) if total else 0
            for span_start, span_end, entry in old_spans:
                if span_start <= old_pos < span_end:
                    return entry
            return old_spans[-1][2]

        new_para_runs: list[dict[str, Any]] = []
        pos = 0
        for i, part in enumerate(parts):
            entry = donor_entry(pos)
            # Keep the first run's object identity when it stays first
            # (aliased by `_para_style`); clone everything else.
            clone = (
                entry if (i == 0 and entry is para_runs[0]) else copy.deepcopy(entry)
            )
            part_len = u16_len(part) + 1
            clone["1"] = part_len
            new_para_runs.append(clone)
            pos += part_len
        para_runs[:] = new_para_runs

    if insert_kern is None:
        insert_kern = [None] * insert_len
    _rebuild_kern_runs(doc, kern_values[:start] + insert_kern + kern_values[end:])
    if start == 0:
        # Replacing the leading edge invalidates the pair-0 kern value
        # (AE-unprobed; dropping it mirrors the auto_kern_type setter).
        inner.pop("7", None)

    inner["0"] = new_raw
    rebuild_lines = getattr(doc, "_rebuild_line_count_runs", None)
    if rebuild_lines is not None:
        rebuild_lines(parts)
    _refresh_style_aliases(doc)


def _apply_para_key(
    doc: TextDocument, start: int, end: int, key: str, value: Any
) -> None:
    """Write one paragraph-style key to every paragraph overlapping the
    range (paragraph runs are structural: never split, never merged -
    `W_PARA_PARTIAL` styles the whole containing paragraph).
    """
    if start == end:
        return
    _mark_layout_dirty(doc)
    runs = cos_get(doc._doc, "0", "5", "0")
    if not isinstance(runs, list):
        return
    pos = 0
    for run in runs:
        run_end = pos + run.get("1", 0)
        if pos < end and run_end > start:
            style = cos_get(run, "0", "0", "5")
            if isinstance(style, dict):
                if value is None:
                    style.pop(key, None)
                else:
                    style[key] = value
        pos = run_end


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

    Writable fields split the style runs at the range boundaries, write
    the key into the covered runs and re-merge adjacent identical runs,
    mirroring AE's probed behavior (see plans/text-range-writes.md).
    Fields whose writes need coupled side effects (kerning runs,
    leading/auto-leading) stay `read_only` until their phase lands.

    Args:
        kind: `"char"` or `"para"` - which run array to resolve over.
        key: String key into each run's style dict.
        transform: Optional callable applied to each stored value.
        default: Per-run value when the key is absent from a run.
        gate: Optional boolean style key gating run participation.
        reverse: 1-arg callable applied when setting (user-facing ->
            COS value), mirroring `CosField.reverse`.
        validate: Optional callable `(value, instance)` run before any
            `reverse`, mirroring the TextDocument CosField validators.
        read_only: When `True`, the field cannot be set.
    """

    def __init__(
        self,
        kind: str,
        key: str,
        *,
        transform: Callable[..., Any] | None = None,
        default: Any = None,
        gate: str | None = None,
        reverse: Callable[..., Any] | None = None,
        validate: Callable[..., None] | None = None,
        read_only: bool = False,
    ) -> None:
        self.kind = kind
        self.key = key
        self.transform = transform
        self.default = default
        self.gate = gate
        self.reverse = reverse
        self.validate = validate
        self.read_only = read_only

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
        if self.read_only:
            raise AttributeError(f"{self.public_name!r} is read-only.")
        if value is not None:
            if self.validate is not None:
                self.validate(value, obj._doc_ref)
            if self.reverse is not None:
                value = self.reverse(value)
        start, end = obj._bounds()
        if self.kind == "char":
            _apply_char_key(obj._doc_ref, start, end, self.key, value)
        else:
            _apply_para_key(obj._doc_ref, start, end, self.key, value)
        obj._propagate()

    @classmethod
    def bool(cls, kind: str, key: str, **kwargs: Any) -> RangeField[bool]:
        """Create a RangeField for boolean style flags."""
        return cast(
            "RangeField[bool]", cls(kind, key, transform=bool, reverse=bool, **kwargs)
        )

    @classmethod
    def float(cls, kind: str, key: str, **kwargs: Any) -> RangeField[float]:
        """Create a RangeField that coerces to float."""
        if "reverse" not in kwargs:
            kwargs["reverse"] = float
        return cast(
            "RangeField[float]",
            cls(kind, key, transform=float, **kwargs),
        )

    @classmethod
    def int(cls, kind: str, key: str, **kwargs: Any) -> RangeField[int]:
        """Create a RangeField for integer-stored style keys.

        Coerces to `int` on read and rounds to the nearest integer on
        write. AE stores these keys as integers; a real-typed value is
        misread at 16.16 scale (stored `50.0` read back as `3276800`,
        probed AE 2026).
        """
        if "reverse" not in kwargs:
            kwargs["reverse"] = round
        return cast(
            "RangeField[int]",
            cls(kind, key, transform=int, **kwargs),
        )

    @classmethod
    def enum(
        cls, enum_cls: type[T], kind: str, key: str, **kwargs: Any
    ) -> RangeField[T]:
        """Create a RangeField for IntEnum-backed style keys."""
        if "transform" not in kwargs:
            kwargs["transform"] = getattr(enum_cls, "from_binary", enum_cls)
        if "reverse" not in kwargs:
            kwargs["reverse"] = getattr(enum_cls, "to_binary", int)
        if "validate" not in kwargs:
            # Reject out-of-enum ints on write (ExtendScript parity); reads
            # stay tolerant via `from_binary`. Without this a stray int
            # serializes a value that reads back as `None`/undefined.
            kwargs["validate"] = validate_enum(enum_cls)
        return cls(kind, key, **kwargs)


class DocumentWideCosField(CosField[T]):
    """A [CosField][py_aep.cos.CosField] whose writes style the whole
    document.

    AE document-level setters apply to every character or paragraph and
    re-merge the style runs (probed `W_DOCLEVEL`, `X_DOC_FILL`,
    `X_DOC_JUST`); a plain CosField write only touches the first run's
    style dict, which is correct only for single-run documents. Reads
    keep the first-run semantics of the base descriptor. Documents
    without run backing (parser fallbacks) fall back to the base
    override behavior.
    """

    def __set__(self, obj: Any, value: T) -> None:
        is_char = self.dict_attr == "_char_style"
        backing = getattr(obj, self.dict_attr, None)
        runs = None
        if backing is not None:
            runs = cos_get(obj._doc, "0", "6" if is_char else "5", "0")
        if not isinstance(runs, list) or not runs:
            # Single style dict (or a parser fallback with no runs): the
            # base descriptor's first-run write is already document-wide.
            super().__set__(obj, value)
            return
        self._check_writable(obj)
        obj.__dict__.pop(self.public_name, None)
        raw_value = None if value is None else self._coerce(obj, value)
        total = u16_len(_raw_text(obj))
        if is_char:
            _apply_char_key(obj, 0, total, self.key, raw_value)
        else:
            _apply_para_key(obj, 0, total, self.key, raw_value)
        propagate = getattr(obj, "_propagate_cos", None)
        if propagate is not None:
            propagate()

    @classmethod
    def enum(
        cls, enum_cls: type[T], dict_attr: str, key: str, **kwargs: Any
    ) -> CosField[T]:
        """Reject out-of-enum ints on write (ExtendScript parity).

        Mirrors `RangeField.enum`; the base `CosField.enum` does not
        validate, so a stray int would serialize a value that reads back
        as `None`/undefined. Reads stay tolerant via `from_binary`.
        """
        if "validate" not in kwargs:
            kwargs["validate"] = validate_enum(enum_cls)
        return super().enum(enum_cls, dict_attr, key, **kwargs)


# ---------------------------------------------------------------------------
# Range base classes
# ---------------------------------------------------------------------------


class _TextRange:
    """Shared boundary/validity/repr behavior for the text range views.

    Subclasses store `_doc_ref`, `_start` and `_signed_end`, and
    implement `_bounds()` (returning the current
    `(character_start, character_end)` and raising `ValueError` when the
    range is out of bounds). The public accessors and string forms below
    are shared across all three range types.
    """

    _doc_ref: TextDocument
    _start: int
    _signed_end: int

    def __init__(self, doc: TextDocument, start: int, signed_end: int) -> None:
        self._doc_ref = doc
        self._start = start
        self._signed_end = signed_end
        # AE validates at creation time and raises immediately.
        self._bounds()

    def _bounds(self) -> tuple[int, int]:
        raise NotImplementedError

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
        return f"{type(self).__name__}({self._start},{self._signed_end})"

    def __repr__(self) -> str:
        return f"<py_aep.{type(self).__name__}({self._start},{self._signed_end})>"


class _IndexRange(_TextRange):
    """A range addressed by an index into a span list (paragraphs or
    composed lines) and resolved to character bounds.

    Shares the index storage and the `character_range()` snapshot; only
    `_bounds()` (the per-kind span lookup and clamping) differs.
    """

    def character_range(self) -> CharacterRange:
        """A [CharacterRange][] fixed to the current character bounds.

        The returned range holds resolved indices and does not follow
        later changes to this range's paragraphs or lines.
        """
        start, end = self._bounds()
        return CharacterRange(self._doc_ref, start, end)


# ---------------------------------------------------------------------------
# CharacterRange
# ---------------------------------------------------------------------------


class CharacterRange(_TextRange):
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
        values = [_extract(payload, key, transform, default) for payload in payloads]
        first = values[0]
        return first if all(value == first for value in values[1:]) else None

    # -- Content ---------------------------------------------------------------

    @property
    def text(self) -> str:
        """The text within the range. Read / Write.

        Line breaks are normalized to `\\n` like `TextDocument.text`
        (ExtendScript returns raw `\\r`). A range splitting a surrogate
        pair yields a lone surrogate, as in AE. Writing replaces the
        ranged characters: the replacement takes the first replaced
        character's style, and this range keeps its creation indices
        (re-resolving against the new text, exactly like AE).
        """
        start, end = self._bounds()
        return u16_slice(_raw_text(self._doc_ref), start, end).replace("\r", "\n")

    @text.setter
    def text(self, value: str) -> None:
        validate_text(value)
        doc = self._doc_ref
        raw = _raw_text(doc)
        start, end = self._bounds()
        start, end = _snap_to_pairs(raw, start, end)
        normalized = value.replace("\r\n", "\r").replace("\n", "\r")
        _splice_text(doc, start, end, normalized)
        self._propagate()

    def paste_from(self, source_range: CharacterRange) -> None:
        """Paste the source range's text and character styling here.

        Mirrors ExtendScript's `pasteFrom()` (AE 25.1+, probed via the
        `W_PASTE_*` / `X_PASTE_KERN` fixtures): the ranged characters
        are replaced by the source span's text with its character style
        runs and manual-kern values transplanted. Cross-document pastes
        remap font references into this document's font array,
        prepending missing fonts like AE. This range keeps its creation
        indices and may become invalid when the pasted text is shorter.

        Args:
            source_range: The [CharacterRange][] to copy from (may
                belong to another document or project).
        """
        if not isinstance(source_range, CharacterRange):
            raise TypeError("paste_from expects a CharacterRange")
        doc = self._doc_ref
        src_doc = source_range._doc_ref
        src_raw = _raw_text(src_doc)
        src_start, src_end = source_range._bounds()
        src_start, src_end = _snap_to_pairs(src_raw, src_start, src_end)
        text_slice = u16_slice(src_raw, src_start, src_end)

        entries: list[dict[str, Any]] = []
        pos = 0
        for run in cos_get(src_doc._doc, "0", "6", "0") or []:
            run_end = pos + run.get("1", 0)
            overlap_start = max(pos, src_start)
            overlap_end = min(run_end, src_end)
            if overlap_end > overlap_start:
                clone = copy.deepcopy(run)
                clone["1"] = overlap_end - overlap_start
                entries.append(clone)
            pos = run_end

        if src_doc is not doc:
            needed: dict[int, str] = {}
            for clone in entries:
                style = cos_get(clone, "0", "0", "6")
                if isinstance(style, dict):
                    index = style.get("0")
                    if isinstance(index, int) and 0 <= index < len(src_doc._fonts):
                        needed[index] = src_doc._fonts[index].post_script_name
            existing = {f.post_script_name for f in doc._fonts}
            for name in needed.values():
                if name not in existing:
                    _register_font_at(doc, name)
                    existing.add(name)
            target_index = {f.post_script_name: i for i, f in enumerate(doc._fonts)}
            for clone in entries:
                style = cos_get(clone, "0", "0", "6")
                if isinstance(style, dict):
                    index = style.get("0")
                    if isinstance(index, int) and index in needed:
                        style["0"] = target_index[needed[index]]

        kern_slice = _kern_values(src_doc)[src_start:src_end]
        src_edge = None
        if src_start == 0:
            edge = cos_get(src_doc._doc, "0", "7")
            if isinstance(edge, int):
                src_edge = edge
        raw = _raw_text(doc)
        start, end = self._bounds()
        start, end = _snap_to_pairs(raw, start, end)
        _splice_text(
            doc, start, end, text_slice, insert_runs=entries, insert_kern=kern_slice
        )
        if src_edge is not None:
            # The source's leading-edge kern value (pair before char 0)
            # follows the paste: it stays the leading edge when pasting at
            # 0, otherwise it becomes the pair value between the preceding
            # character and the pasted text (probed Y_PASTE_EDGE0/_MID).
            if start == 0:
                doc._doc.setdefault("0", {})["7"] = src_edge
            else:
                values = _kern_values(doc)
                if start - 1 < len(values):
                    values[start - 1] = src_edge
                    _rebuild_kern_runs(doc, values)
        self._propagate()

    # -- Character style fields --------------------------------------------------

    font_size = RangeField.float("char", "1", validate=validate_positive_nonzero_number)
    """The range's font size in pixels; `None` when mixed. Read / Write."""

    faux_bold = RangeField.bool("char", "2")
    """`True` if faux bold is enabled across the range. Read / Write."""

    faux_italic = RangeField.bool("char", "3")
    """`True` if faux italic is enabled across the range. Read / Write."""

    @property
    def auto_leading(self) -> bool | None:
        """The range's auto-leading option; `None` when mixed. Read / Write.

        Enabling auto-leading also resets the explicit leading key to
        AE's sentinel (probed `X_AL_SET`).
        """
        return cast("bool | None", self._resolve_mixed("char", "4", bool, True, None))

    @auto_leading.setter
    def auto_leading(self, value: bool) -> None:
        validate_bool(value)
        start, end = self._bounds()
        _apply_char_key(self._doc_ref, start, end, "4", value)
        if value:
            _apply_char_key(self._doc_ref, start, end, "5", 0.01)
        self._propagate()

    horizontal_scale = RangeField.float("char", "6", validate=validate_number)
    """The range's horizontal scale; `None` when mixed. Read / Write."""

    vertical_scale = RangeField.float("char", "7", validate=validate_number)
    """The range's vertical scale; `None` when mixed. Read / Write."""

    tracking = RangeField.int("char", "8", validate=validate_s4)
    """The range's spacing between characters; `None` when mixed. Read / Write."""

    baseline_shift = RangeField.float("char", "9", validate=validate_number)
    """The range's baseline shift in pixels; `None` when mixed. Read / Write."""

    @property
    def auto_kern_type(self) -> AutoKernType | None:
        """The range's auto kern type option; `None` when mixed. Read / Write.

        Setting a non-manual kern type clears the manual kerning values
        over the range; AE drops the kern-run array entirely when no
        values remain (probed `X_AKT_SET`).
        """
        return cast(
            "AutoKernType | None",
            self._resolve_mixed(
                "char", "11", AutoKernType.from_binary, AutoKernType.NO_AUTO_KERN, None
            ),
        )

    @auto_kern_type.setter
    def auto_kern_type(self, value: AutoKernType) -> None:
        validate_enum(AutoKernType)(value)
        doc = self._doc_ref
        start, end = _snap_to_pairs(_raw_text(doc), *self._bounds())
        if start == end:
            # Zero-span writes are no-ops (W_ZERO_STYLE); guard before
            # the kern-clearing side effects below.
            return
        _apply_char_key(doc, start, end, "11", AutoKernType(value).to_binary())
        if value != AutoKernType.NO_AUTO_KERN:
            values = _kern_values(doc)
            for i in range(start, min(end, len(values))):
                values[i] = None
            _rebuild_kern_runs(doc, values)
            if start == 0:
                doc._doc.get("0", {}).pop("7", None)
        self._propagate()

    font_caps_option = RangeField.enum(FontCapsOption, "char", "12")
    """The range's font caps option; `None` when mixed. Read / Write."""

    font_baseline_option = RangeField.enum(FontBaselineOption, "char", "13")
    """The range's font baseline option; `None` when mixed. Read / Write."""

    ligature = RangeField.bool("char", "18", default=False)
    """`True` when ligature is used across the range. Read / Write."""

    baseline_direction = RangeField.enum(
        BaselineDirection, "char", "35", default=BaselineDirection.BASELINE_WITH_STREAM
    )
    """The range's baseline direction; `None` when mixed. Read / Write."""

    tsume = RangeField.float(
        "char", "36", default=0.0, validate=validate_normalized_float
    )
    """The range's tsume value (0.0 to 1.0); `None` when mixed. Read / Write."""

    no_break = RangeField.bool("char", "52", default=False)
    """`True` when no-break is applied across the range. Read / Write."""

    apply_fill = RangeField.bool("char", "56")
    """When `True`, the range shows a fill; `None` when mixed. Read / Write."""

    apply_stroke = RangeField.bool("char", "57", default=False)
    """When `True`, the range shows a stroke; `None` when mixed. Read / Write."""

    stroke_over_fill = RangeField.bool("char", "58", default=True)
    """When `True`, the stroke appears over the fill; `None` when mixed. Read / Write."""

    line_join_type = RangeField.enum(
        LineJoinType, "char", "62", default=LineJoinType.LINE_JOIN_MITER
    )
    """The range's line join type for strokes; `None` when mixed. Read / Write."""

    stroke_width = RangeField.float(
        "char", "63", default=1.0, validate=validate_positive_nonzero_number
    )
    """The range's stroke thickness; `None` when mixed. Read / Write."""

    digit_set = RangeField.enum(DigitSet, "char", "70", default=DigitSet.DEFAULT_DIGITS)
    """The range's digit set option; `None` when mixed. Read / Write."""

    # -- Paragraph style fields (resolved over paragraph runs) -------------------

    justification = RangeField.enum(ParagraphJustification, "para", "0")
    """The justification of paragraphs in the range; `None` when mixed. Read / Write."""

    first_line_indent = RangeField.float(
        "para", "1", default=0.0, validate=validate_number
    )
    """The paragraphs' first line indent; `None` when mixed. Read / Write."""

    start_indent = RangeField.float("para", "2", default=0.0, validate=validate_number)
    """The paragraphs' start indent; `None` when mixed. Read / Write."""

    end_indent = RangeField.float("para", "3", default=0.0, validate=validate_number)
    """The paragraphs' end indent; `None` when mixed. Read / Write."""

    space_before = RangeField.float("para", "4", default=0.0, validate=validate_number)
    """The paragraphs' space before; `None` when mixed. Read / Write."""

    space_after = RangeField.float("para", "5", default=0.0, validate=validate_number)
    """The paragraphs' space after; `None` when mixed. Read / Write."""

    leading_type = RangeField.enum(
        LeadingType, "para", "8", default=LeadingType.ROMAN_LEADING_TYPE
    )
    """The paragraphs' leading type; `None` when mixed. Read / Write."""

    auto_hyphenate = RangeField.bool("para", "9")
    """The paragraphs' auto-hyphenate option; `None` when mixed. Read / Write."""

    hanging_roman = RangeField.bool("para", "21", default=False)
    """The paragraphs' Roman Hanging Punctuation; `None` when mixed. Read / Write."""

    every_line_composer = RangeField.bool("para", "29", default=False)
    """The paragraphs' Every-Line Composer option; `None` when mixed. Read / Write."""

    direction = RangeField.enum(
        ParagraphDirection,
        "para",
        "33",
        default=ParagraphDirection.DIRECTION_LEFT_TO_RIGHT,
    )
    """The paragraphs' direction; `None` when mixed. Read / Write."""

    # -- Computed style properties ------------------------------------------------

    def _propagate(self) -> None:
        """Serialize the document's COS tree after a write."""
        propagate = getattr(self._doc_ref, "_propagate_cos", None)
        if propagate is not None:
            propagate()

    fill_color = cast(
        "RangeField[list[float]]",
        RangeField(
            "char",
            "53",
            transform=_parse_color,
            gate="56",
            reverse=_build_color_paint,
            validate=validate_rgb_color,
        ),
    )
    """The range's fill color as `[r, g, b]`. Read / Write.

    Only characters with `apply_fill` participate in the read; `None`
    when no character in the range has a fill or the colors are mixed.
    Setting writes the paint only - like the stroke, it does not enable
    `apply_fill`.
    """

    stroke_color = cast(
        "RangeField[list[float]]",
        RangeField(
            "char",
            "54",
            transform=_parse_color,
            gate="57",
            reverse=_build_color_paint,
            validate=validate_rgb_color,
        ),
    )
    """The range's stroke color as `[r, g, b]`. Read / Write.

    Only characters with `apply_stroke` participate in the read; `None`
    when no character in the range has a stroke or the colors are
    mixed. Setting writes the paint only - AE does NOT enable
    `apply_stroke` (probed `W_STROKE_GATE`; the Scripting Guide claims
    otherwise).
    """

    @property
    def font(self) -> str | None:
        """The range's font PostScript name; `None` when mixed. Read / Write.

        Setting a font absent from the document's font array prepends
        it and reindexes existing references, matching AE.
        """
        font_obj = self.font_object
        return font_obj.post_script_name if font_obj is not None else None

    @font.setter
    def font(self, value: str) -> None:
        validate_font_name(value)
        doc = self._doc_ref
        start, end = _snap_to_pairs(_raw_text(doc), *self._bounds())
        if start == end:
            # Zero-span writes are no-ops (W_ZERO_STYLE); guard before
            # registering the font, which mutates the whole document.
            return
        index = None
        for i, font_obj in enumerate(doc._fonts):
            if font_obj.post_script_name == value:
                index = i
                break
        if index is None:
            index = _register_font_at(doc, value)
        _apply_char_key(doc, start, end, "0", index)
        self._propagate()

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
        """The range's spacing between lines. Read / Write.

        AE reads `undefined` while auto-leading is active (or mixed)
        anywhere in the range; the explicit value only surfaces when
        auto-leading is uniformly disabled. Setting an explicit value
        also disables auto-leading over the range (probed `W_LEAD`);
        setting `None` clears the explicit value without touching
        auto-leading.
        """
        auto = self.auto_leading
        if auto is None or auto:
            return None
        return cast("float | None", self._resolve_mixed("char", "5", float, None, None))

    @leading.setter
    def leading(self, value: float | None) -> None:
        if value is not None:
            validate_positive_number(value)
        start, end = self._bounds()
        if value is None:
            _apply_char_key(self._doc_ref, start, end, "5", None)
        else:
            _apply_char_key(self._doc_ref, start, end, "5", float(value))
            _apply_char_key(self._doc_ref, start, end, "4", False)
        self._propagate()

    @property
    def kerning(self) -> int | None:
        """The range's manual kerning value. Read / Write.

        AE reads `undefined` unless auto-kerning is uniformly disabled
        AND a manual value is stored for every character in the range
        (probed `X_TEXT_KERN`: spliced-in characters under NO_AUTO_KERN
        without values read undefined). Values live in dedicated kerning
        runs (`doc["0"]["8"]`) and read `None` when mixed. Setting a
        value affects characters `[max(0, start - 1), end)` - AE's pair
        shift - disables auto-kerning for them, and stores the
        leading-edge value at `doc["0"]["7"]` when the range starts at 0.
        """
        if self.auto_kern_type != AutoKernType.NO_AUTO_KERN:
            return None
        value = self._resolve_mixed("kern", "0", None, None, None)
        return value if isinstance(value, int) else None

    @kerning.setter
    def kerning(self, value: int) -> None:
        validate_s4(value, self._doc_ref)
        # `validate_s4` accepts a float (see its definition): round it on
        # write, matching the sibling `tracking` field, whose `RangeField.int`
        # sets `reverse=round`. `round` also normalizes bools (a subclass of
        # int) so the serializer emits an integer, not a `true`/`false` token.
        value = round(value)
        doc = self._doc_ref
        raw = _raw_text(doc)
        start, end = self._bounds()
        start, end = _snap_to_pairs(raw, start, end)
        if start == end:
            return
        # Kern runs mutate before the auto-kern flag write reaches
        # _apply_char_key, so mark (and calibrate) here first.
        _mark_layout_dirty(doc)
        # No visible-end extension here: AE never kerns the raw `\r`
        # terminator (every probed kern fixture leaves it in an empty
        # run); `_apply_char_key` below re-extends the style write.
        kern_start = max(0, start - 1)
        values = _kern_values(doc)
        for i in range(kern_start, min(end, len(values))):
            values[i] = value
        _rebuild_kern_runs(doc, values)
        if start == 0:
            # Pair position 0 (before the first character): AE stores the
            # leading-edge value at doc["0"]["7"], created after key "8".
            doc._doc.setdefault("0", {})["7"] = value
        _apply_char_key(
            doc, kern_start, end, "11", AutoKernType.NO_AUTO_KERN.to_binary()
        )
        self._propagate()

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


class ParagraphRange(_IndexRange):
    """A paragraph span of a [TextDocument][].

    Created via `TextDocument.paragraph_range(paragraph_index_start,
    signed_paragraph_index_end)`. Paragraph character boundaries include
    each paragraph's trailing `\\r`; the final boundary is clamped to
    the visible text length, so a trailing empty paragraph reports a
    zero-span range.

    See: https://ae-scripting.docsforadobe.dev/text/paragraphrange/
    """

    def _bounds(self) -> tuple[int, int]:
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


class ComposedLineRange(_IndexRange):
    """A composed-line span of a [TextDocument][].

    Created via `TextDocument.composed_line_range(
    composed_line_index_start, signed_composed_line_index_end)`.
    Point text derives its lines from the paragraphs (always fresh).
    Box text reads the layout cache AE persisted at save time; after a
    layout-affecting py-side write the calibrated composed-line
    resolver recomposes it (see `TextDocument.composition_stale`).
    When no calibrated composer is available the stale cache behaves
    like AE's own un-reapplied TextDocument values: line boundaries
    clamp to the current text and lines falling wholly outside it
    raise `ValueError`.

    See: https://ae-scripting.docsforadobe.dev/text/composedlinerange/
    """

    def _bounds(self) -> tuple[int, int]:
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
