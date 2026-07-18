"""TextDocument model for After Effects text layers."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, cast

from ...ae_version import requires_version
from ...binary.chunk import ListChunk
from ...cos import cos_get, get_cos_template, serialize
from ...enums import (
    AutoKernType,
    BaselineDirection,
    BoxAutoFitPolicy,
    BoxFirstBaselineAlignment,
    BoxVerticalAlignment,
    ComposerEngine,
    DigitSet,
    FontBaselineOption,
    FontCapsOption,
    LeadingType,
    LineJoinType,
    LineOrientation,
    ParagraphDirection,
    ParagraphJustification,
)
from ...resolvers.text_composition import (
    calibrate as calibrate_composition,
)
from ..preferences import (
    Preferences,
    default_character_style,
    default_paragraph_style,
)
from ..validators import (
    validate_bool,
    validate_box_size,
    validate_enum,
    validate_font_name,
    validate_int,
    validate_normalized_float,
    validate_number,
    validate_positive_int,
    validate_positive_nonzero_number,
    validate_positive_number,
    validate_rgb_color,
    validate_s4,
    validate_text,
    validate_vector2,
)
from .font_object import FontObject
from .ranges import (
    CHARACTER_RANGE_OOB,
    NOT_ASSOCIATED,
    CharacterRange,
    ComposedLineRange,
    DocumentWideCosField,
    ParagraphRange,
    _apply_char_key,
    _build_color_paint,
    _cached_line_data,
    _cached_line_nodes,
    _char_run_spans,
    _composed_line_spans,
    _fresh_composed_spans,
    _line_advances,
    _line_data_from_nodes,
    _line_origin,
    _para_run_spans,
    _parse_color,
    _raw_text,
    _rebuild_kern_runs,
    _register_font_at,
    _visible_length,
    u16_len,
    u16_slice,
)

if TYPE_CHECKING:
    from typing import Any

    from ...binary.item_chunks import HeadChunk


_EMPTY_LINE_LOC = 3.4028234663852886e38
"""`baseline_locs` entry for a line with no visible characters: the
maximum 32-bit float, as After Effects reports (`3.402823466e+38`)."""


def _box_coords(left: float, top: float, width: float, height: float) -> list[float]:
    """Build the 16-vertex box outline AE stores for paragraph text.

    Coordinates trace the rectangle corners (each corner duplicated, AE's
    bezier vertex layout), anchored at the top-left `(left, top)`.
    """
    right, bottom = left + width, top + height
    coords: list[float] = []
    for x, y in [
        (left, top),
        (left, top),
        (right, top),
        (right, top),
        (right, top),
        (right, top),
        (right, bottom),
        (right, bottom),
        (right, bottom),
        (right, bottom),
        (left, bottom),
        (left, bottom),
        (left, bottom),
        (left, bottom),
        (left, top),
        (left, top),
    ]:
        coords.extend([float(x), float(y)])
    return coords


def _numeric_sort(d: dict[str, Any]) -> None:
    """Reorder a COS sub-dict's keys numerically in place.

    AE stores the box-frame metadata keys in ascending numeric order;
    matching that order keeps serialized output byte-identical.
    """
    items = sorted(d.items(), key=lambda kv: int(kv[0]))
    d.clear()
    d.update(items)


def _apply_box_conversion(meta: dict[str, Any]) -> None:
    """Update a frame's `2` sub-dict for the point-to-box conversion.

    AE flips these metadata values when a point text layer becomes a box
    (paragraph) text layer; other keys in the sub-dict are preserved.
    """
    meta["0"] = 1
    meta["6"] = [-2.0, -2.0]
    eleven = meta.setdefault("11", {})
    eleven["4"] = -2
    eleven["18"] = -2.0
    _numeric_sort(meta)


class TextDocument:
    """Stores a value for a TextLayer's Source Text property.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        comp = app.project.compositions[0]
        text_doc = comp.text_layers[0].text.source_text.value
        print(text_doc.text)
        ```

    See: https://ae-scripting.docsforadobe.dev/text/textdocument/
    """

    # Explicit annotation so to_dict serializes it (bypasses SKIP_PROPERTIES)
    text: str

    # Back-reference to the project HeadChunk for version gating. Wired
    # lazily by the owning Property when the document is handed out (and at
    # parse time); `None` until then. Underscore-prefixed, so to_dict skips it.
    _head: HeadChunk | None = None

    # Back-reference to the project's AE preferences, wired at parse time.
    # Holds the Character/Paragraph panel defaults the reset methods restore;
    # `None` falls back to AE's factory values.
    _preferences: Preferences | None = None

    # `True` for documents parsed from a layer's btdk data. The range API
    # (AE 24.3+) refuses documents never associated with a layer, exactly
    # as ExtendScript does for an unapplied `new TextDocument()`.
    _associated: bool = False

    # Set by the first layout-affecting py-side write; while `False` the
    # persisted composed-line cache is authoritative. Underscore-prefixed,
    # so to_dict skips both.
    _layout_dirty: bool = False

    # Verdict of calibrating the composed-line resolver against this
    # document's own AE cache: `None` = never attempted, `True` = the
    # composer reproduces AE for this document (post-mutation
    # recomposition is trusted), `False` = refused or mismatched.
    _composition_calibrated: bool | None = None

    # Wrappers sharing this layer's btdk COS data (one per keyframe,
    # including self); `None` for template-constructed documents. Frame
    # writes live in the shared layer data, so they must dirty-mark
    # every sibling, not just the document written through.
    _siblings: list[TextDocument] | None = None

    def _mark_frame_layout_dirty(self) -> None:
        """Mark a frame-level write (box meta, orientation) on ALL
        documents sharing this layer's frame.

        Runs before the mutation lands so each sibling still calibrates
        against its own clean cache + text.
        """
        for doc in self._siblings or (self,):
            doc._mark_layout_dirty()

    def _mark_layout_dirty(self) -> None:
        """Record a layout-affecting write, calibrating the composer first.

        The write engine calls this BEFORE serializing any mutation that
        can change line composition, so the first call still sees the
        clean cache + text: composing them and comparing spans AND
        baselines against what AE persisted proves (or refutes) the
        composer + installed fonts for this document.
        """
        # Every layout write invalidates the memoized composition.
        self.__dict__.pop("_composed_cache", None)
        if self._layout_dirty:
            return
        if self.box_text and self._composition_calibrated is None:
            cached = _cached_line_data(self)
            if cached is not None:
                self._composition_calibrated = calibrate_composition(
                    self, cached[0], cached[1]
                )
        self._layout_dirty = True

    @property
    def composition_stale(self) -> bool:
        """`True` when the composed-line APIs may not reflect this
        document's current content. Read-only.

        Point text is never stale (its composed lines are the
        paragraphs). Box text goes stale after a layout-affecting
        py-side write unless the composed-line resolver calibrated
        against this document's own persisted cache and can recompose
        its current state (see the `resolvers.text_composition`
        module).

        The flag tracks writes made through THIS document object: a
        document re-parsed from a py-written file, or minted by
        `Layer.duplicate`, starts clean even when its persisted cache
        no longer matches its text.
        """
        if not self.box_text or not self._layout_dirty:
            return False
        return _fresh_composed_spans(self) is None

    # -- Character-style CosField descriptors (_char_style dict) -----------

    font_size = DocumentWideCosField.float(
        "_char_style", "1", default=None, validate=validate_positive_nonzero_number
    )
    """The Text layer's font size in pixels. Read / Write."""

    faux_bold = DocumentWideCosField.bool("_char_style", "2", default=None)
    """`True` if a Text layer has faux bold enabled. Read / Write."""

    faux_italic = DocumentWideCosField.bool("_char_style", "3", default=None)
    """`True` if a Text layer has faux italic enabled. Read / Write."""

    tracking = DocumentWideCosField.int(
        "_char_style", "8", default=None, validate=validate_s4
    )
    """The Text layer's spacing between characters. Read / Write."""

    @property
    def auto_kern_type(self) -> AutoKernType | None:
        """The Text layer's auto kern type option. Read / Write.

        Setting a non-manual kern type also clears the manual kerning
        values document-wide, dropping the kern-run array and the
        leading-edge value like the range setter (probed `X_AKT_SET`).
        """
        override: AutoKernType | None = self._override("auto_kern_type")
        if override is not None:
            return override
        if self._char_style is None:
            return AutoKernType.NO_AUTO_KERN
        raw = self._char_style.get("11")
        if raw is None:
            return AutoKernType.NO_AUTO_KERN
        return AutoKernType.from_binary(raw)

    @auto_kern_type.setter
    def auto_kern_type(self, value: AutoKernType) -> None:
        validate_enum(AutoKernType)(value)
        self.__dict__.pop("auto_kern_type", None)
        if self._char_style is None:
            self._set_override("auto_kern_type", AutoKernType(value))
            return
        total = u16_len(_raw_text(self))
        _apply_char_key(self, 0, total, "11", AutoKernType(value).to_binary())
        if value != AutoKernType.NO_AUTO_KERN:
            # Drops the kern-run array and leading-edge value with it.
            _rebuild_kern_runs(self, [None] * total)
        self._propagate_cos()

    horizontal_scale = DocumentWideCosField.float(
        "_char_style", "6", default=None, validate=validate_number
    )
    """This Text layer's horizontal scale in pixels. Read / Write."""

    vertical_scale = DocumentWideCosField.float(
        "_char_style", "7", default=None, validate=validate_number
    )
    """This Text layer's vertical scale in pixels. Read / Write."""

    baseline_shift = DocumentWideCosField.float(
        "_char_style", "9", default=None, validate=validate_number
    )
    """This Text layer's baseline shift in pixels. Read / Write."""

    font_caps_option = DocumentWideCosField.enum(
        FontCapsOption,
        "_char_style",
        "12",
        default=None,
    )
    """The Text layer's font caps option. Read / Write."""

    font_baseline_option = DocumentWideCosField.enum(
        FontBaselineOption,
        "_char_style",
        "13",
        default=None,
    )
    """The Text layer's font baseline option. Read / Write."""

    tsume = DocumentWideCosField.float(
        "_char_style", "36", default=0.0, validate=validate_normalized_float
    )
    """This Text layer's tsume value (0.0 to 1.0). Read / Write."""

    apply_fill = DocumentWideCosField.bool("_char_style", "56", default=None)
    """When `True`, the Text layer shows a fill. Read / Write."""

    apply_stroke = DocumentWideCosField.bool("_char_style", "57", default=False)
    """When `True`, the Text layer shows a stroke. Read / Write."""

    stroke_over_fill = DocumentWideCosField.bool("_char_style", "58", default=True)
    """When `True`, the stroke appears over the fill. Read / Write."""

    stroke_width = DocumentWideCosField.float(
        "_char_style", "63", default=1.0, validate=validate_positive_nonzero_number
    )
    """The Text layer's stroke thickness in pixels. Read / Write."""

    # -- Paragraph-style CosField descriptors (_para_style dict) -----------

    justification = DocumentWideCosField.enum(
        ParagraphJustification,
        "_para_style",
        "0",
        default=None,
    )
    """The paragraph justification for the Text layer. Read / Write."""

    first_line_indent = DocumentWideCosField.float(
        "_para_style", "1", default=0.0, validate=validate_number
    )
    """The Text layer's paragraph first line indent. Read / Write."""

    start_indent = DocumentWideCosField.float(
        "_para_style", "2", default=0.0, validate=validate_number
    )
    """The Text layer's paragraph start indent. Read / Write."""

    end_indent = DocumentWideCosField.float(
        "_para_style", "3", default=0.0, validate=validate_number
    )
    """The Text layer's paragraph end indent. Read / Write."""

    space_before = DocumentWideCosField.float(
        "_para_style", "4", default=0.0, validate=validate_number
    )
    """The Text layer's paragraph space before. Read / Write."""

    space_after = DocumentWideCosField.float(
        "_para_style", "5", default=0.0, validate=validate_number
    )
    """The Text layer's paragraph space after. Read / Write."""

    @property
    def auto_leading(self) -> bool | None:
        """The Text layer's auto leading option. Read / Write.

        Enabling auto-leading also resets the explicit leading key to
        AE's sentinel across the document (probed `X_AL_SET`).
        """
        override: bool | None = self._override("auto_leading")
        if override is not None:
            return override
        if self._char_style is None:
            return True
        return bool(self._char_style.get("4", True))

    @auto_leading.setter
    def auto_leading(self, value: bool) -> None:
        validate_bool(value)
        self.__dict__.pop("auto_leading", None)
        if self._char_style is None:
            self._set_override("auto_leading", value)
            return
        total = u16_len(_raw_text(self))
        _apply_char_key(self, 0, total, "4", value)
        if value:
            _apply_char_key(self, 0, total, "5", 0.01)
        self._propagate_cos()

    leading_type = DocumentWideCosField.enum(
        LeadingType,
        "_para_style",
        "8",
        default=LeadingType.ROMAN_LEADING_TYPE,
    )
    """The Text layer's paragraph leading type. Read / Write."""

    auto_hyphenate = DocumentWideCosField.bool("_para_style", "9", default=None)
    """The Text layer's auto hyphenate option. Read / Write."""

    hanging_roman = DocumentWideCosField.bool("_para_style", "21", default=False)
    """The Text layer's Roman Hanging Punctuation. Read / Write."""

    every_line_composer = DocumentWideCosField.bool("_para_style", "29", default=False)
    """The Text layer's Every-Line Composer option. Read / Write.

    `True` when Every-Line Composer is used, `False` for Single-Line.
    """

    baseline_direction = DocumentWideCosField.enum(
        BaselineDirection,
        "_char_style",
        "35",
        default=BaselineDirection.BASELINE_WITH_STREAM,
    )
    """The Text layer's baseline direction. Read / Write."""

    ligature = DocumentWideCosField.bool("_char_style", "18", default=False)
    """When `True`, ligature is used. Read / Write."""

    no_break = DocumentWideCosField.bool("_char_style", "52", default=False)
    """When `True`, the no-break attribute is applied. Read / Write."""

    digit_set = DocumentWideCosField.enum(
        DigitSet,
        "_char_style",
        "70",
        default=DigitSet.DEFAULT_DIGITS,
    )
    """The Text layer's digit set option. Read / Write."""

    line_join_type = DocumentWideCosField.enum(
        LineJoinType,
        "_char_style",
        "62",
        default=LineJoinType.LINE_JOIN_MITER,
    )
    """The Text layer's line join type for strokes. Read / Write."""

    direction = DocumentWideCosField.enum(
        ParagraphDirection,
        "_para_style",
        "33",
        default=ParagraphDirection.DIRECTION_LEFT_TO_RIGHT,
    )
    """The Text layer's paragraph direction. Read / Write."""

    # -- Constructor -------------------------------------------------------

    def __init__(
        self,
        text: str = "",
        box_size: list[float] | None = None,
        line_orientation: LineOrientation | None = None,
    ) -> None:
        """Build a [TextDocument][] from the point-text COS template.

        Creates a document whose `_cos_data` and `_btdk_body` are wired
        together so that descriptor / setter writes propagate to the
        backing `btdk` chunk.

        Args:
            text: Initial text content. When empty, the template's
                placeholder text is left unchanged.
            box_size: `[width, height]` for box (paragraph) text. When
                given, converts the document to box text; `None` leaves
                it as point text.
            line_orientation: Text [LineOrientation][]. When given, sets
                the layer's orientation (e.g. vertical); `None` leaves
                the template's horizontal default.
        """
        validate_text(text)
        if box_size is not None:
            validate_box_size(box_size)
        if line_orientation is not None:
            validate_enum(LineOrientation)(line_orientation)
        cos = copy.deepcopy(get_cos_template())
        btdk = ListChunk(list_type="btdk", data=serialize(cos))
        doc = cos["1"]["1"][0]
        char_style = doc["0"]["6"]["0"][0]["0"]["0"]["6"]
        para_style = doc["0"]["5"]["0"][0]["0"]["0"]["5"]
        fonts = [
            FontObject(_font_data=entry["0"]["0"], _font_entry=entry["0"])
            for entry in cos["0"]["1"]["0"]
        ]
        self._char_style: dict[str, Any] | None = char_style
        self._para_style: dict[str, Any] | None = para_style
        self._doc: dict[str, Any] = doc
        self._fonts: list[FontObject] = fonts
        self._cos_data: dict[str, Any] = cos
        self._btdk_body: ListChunk = btdk
        if text:
            self.text = text
        if box_size is not None:
            self.box_text_size = box_size
        if line_orientation is not None:
            self.line_orientation = line_orientation

    @classmethod
    def _from_binary(
        cls,
        *,
        _char_style: dict[str, Any] | None = None,
        _para_style: dict[str, Any] | None = None,
        _doc: dict[str, Any],
        _fonts: list[FontObject],
        _cos_data: dict[str, Any],
        _btdk_body: ListChunk,
        # Fallback kwargs for fields without COS backing
        text: str | None = None,
        font: str | None = None,
        font_object: FontObject | None = None,
        fill_color: list[float] | None = None,
        stroke_color: list[float] | None = None,
        paragraph_count: int | None = None,
        **kwargs: Any,
    ) -> TextDocument:
        """Wrap parsed COS data as a `TextDocument`."""
        obj = cls.__new__(cls)
        obj._char_style = _char_style
        obj._para_style = _para_style
        obj._doc = _doc
        obj._fonts = _fonts
        obj._cos_data = _cos_data
        obj._btdk_body = _btdk_body
        obj._associated = True
        # Instance overrides for non-descriptor fields, plus any
        # CosField-backed kwargs
        overrides = {
            "text": text,
            "font": font,
            "font_object": font_object,
            "fill_color": fill_color,
            "stroke_color": stroke_color,
            "paragraph_count": paragraph_count,
            **kwargs,
        }
        for key, val in overrides.items():
            if val is not None:
                obj.__dict__[key] = val
        return obj

    def _override(self, name: str) -> Any:
        """Instance override stored when a field has no COS backing.

        Set by `_from_binary` fallback kwargs and by setters when the
        backing style dict is `None`. Returns `None` when absent.
        """
        return self.__dict__.get(name)

    def _set_override(self, name: str, value: Any) -> None:
        """Store an instance override for a field without COS backing."""
        self.__dict__[name] = value

    # -- Computed properties -----------------------------------------------

    @property  # type: ignore[no-redef]
    def text(self) -> str:
        """The text value for the Source Text property. Read / Write."""
        override: str | None = self._override("text")
        if override is not None:
            return override
        val = cos_get(self._doc, "0", "0")
        if val is not None:
            # AE stores line breaks as CR; present them as LF to callers.
            # Strip exactly the one terminator CR - further trailing CRs
            # are real line breaks (trailing empty paragraphs).
            raw = str(val)
            if raw.endswith("\r"):
                raw = raw[:-1]
            return raw.replace("\r", "\n")
        return ""

    @text.setter
    def text(self, value: str) -> None:
        validate_text(value)
        self.__dict__.pop("text", None)
        self._mark_layout_dirty()
        inner = self._doc.setdefault("0", {})
        # AE stores every line break and the run terminator as CR (\r);
        # without a trailing CR terminator AE fails to read the layer.
        normalized = value.replace("\r\n", "\r").replace("\n", "\r")
        raw = normalized + "\r"
        self._rebuild_runs_for_text(raw)
        inner["0"] = raw
        self._propagate_cos()

    def _rebuild_runs_for_text(self, raw: str) -> None:
        """Collapse the style runs for newly assigned text.

        AE resets styling on text assignment (probed via the
        `RangesTextReset` fixture): the character runs collapse to a
        single run carrying the first run's style over the whole text,
        the paragraph runs become one clone of the first paragraph's
        run per new paragraph, and manual-kerning runs are dropped.

        Args:
            raw: The new stored text, including the terminator `\\r`.
        """
        inner = self._doc.get("0", {})
        char_runs = cos_get(inner, "6", "0")
        if isinstance(char_runs, list) and char_runs:
            char_runs[0]["1"] = u16_len(raw)
            del char_runs[1:]
        para_runs = cos_get(inner, "5", "0")
        if isinstance(para_runs, list) and para_runs:
            # One paragraph per CR; the final CR is the terminator, which
            # belongs to the last paragraph rather than opening a new one.
            parts = raw.split("\r")
            if parts[-1] == "":
                parts = parts[:-1]
            # Keep the first run object itself: `_para_style` (and the
            # parser's back-references) alias its style dict.
            template = para_runs[0]
            rebuilt = [template] + [copy.deepcopy(template) for _ in parts[1:]]
            for run, part in zip(rebuilt, parts):
                run["1"] = u16_len(part) + 1
            para_runs[:] = rebuilt
            self._rebuild_line_count_runs(parts)
        inner.pop("8", None)
        inner.pop("7", None)

    def _rebuild_line_count_runs(self, parts: list[str]) -> None:
        """Keep `doc["1"]["1"]` (per-paragraph composed-line counts)
        structurally consistent with the paragraphs.

        AE stores this cache-family array exactly when a document has
        more than one paragraph (probed across all text fixtures) and
        omits it otherwise. Counts of 1 are correct for point text
        (paragraphs never wrap); for box text AE recomputes the real
        counts when it next opens the file, like the `/PC` cache.
        """
        state = self._doc.get("1")
        if not isinstance(state, dict):
            return
        if len(parts) <= 1:
            state.pop("1", None)
            return
        runs = [{"0": {"1": 1}, "1": u16_len(part) + 1} for part in parts]
        if "1" in state:
            state["1"] = {"0": runs}
            return
        # Fresh key: AE orders it between "0" and the /PC cache "2";
        # rebuild the dict to splice it in place (insertion order is
        # what the serializer emits).
        items = list(state.items())
        state.clear()
        inserted = False
        for key, value in items:
            if key == "2" and not inserted:
                state["1"] = {"0": runs}
                inserted = True
            state[key] = value
        if not inserted:
            state["1"] = {"0": runs}

    # `fontFamily`, `fontStyle`, and `fontLocation` (deprecated ExtendScript
    # TextDocument fields) are deliberately not exposed: AE does not store them
    # in the .aep. It resolves them at runtime from the host font engine
    # (CoolType) given the stored PostScript name below, so their values are
    # host-dependent and not decodable from the binary. Use `font_object`.

    @property
    def font(self) -> str | None:
        """The Text layer's font PostScript name. Read / Write."""
        override: str | None = self._override("font")
        if override is not None:
            return override
        if self._char_style is not None:
            font_idx = self._char_style.get("0")
            if isinstance(font_idx, int) and 0 <= font_idx < len(self._fonts):
                return self._fonts[font_idx].post_script_name
        return None

    @font.setter
    def font(self, value: str) -> None:
        validate_font_name(value)
        if self._char_style is None:
            self._set_override("font", value)
            return
        idx = self._font_index(value)
        if idx is None:
            idx = self._register_font(value)
        _apply_char_key(self, 0, u16_len(_raw_text(self)), "0", idx)
        self.__dict__.pop("font", None)
        self.__dict__.pop("font_object", None)
        self._propagate_cos()

    def _font_index(self, post_script_name: str) -> int | None:
        """Return the index of a font in `_fonts`, or `None` if absent."""
        for idx, fo in enumerate(self._fonts):
            if fo.post_script_name == post_script_name:
                return idx
        return None

    def _register_font(self, post_script_name: str) -> int:
        """Prepend a new font to the COS font array and `_fonts`.

        AE inserts new fonts at index 0 and reindexes every existing
        font reference (probed via the `W_FONT` / `W_PASTE_XDOC` write
        fixtures). Returns the new font's index (always 0).
        """
        return _register_font_at(self, post_script_name)

    def _used_font_objects(self) -> list[FontObject]:
        """The distinct fonts this document's character runs reference, in
        first-appearance order.

        The document's `_fonts` table can hold entries no run points at
        (AE keeps them after an edit), so the runs - not the table - are
        authoritative for "used". An empty text layer still references a
        font through its terminator run, which is what AE reports.
        """
        used: list[FontObject] = []
        seen: set[int] = set()
        for _start, _end, style in _char_run_spans(self):
            index = style.get("0")
            if not isinstance(index, int) or index in seen:
                continue
            if 0 <= index < len(self._fonts):
                seen.add(index)
                used.append(self._fonts[index])
        return used

    @property
    def font_object(self) -> FontObject | None:
        """The Text layer's [FontObject][]. Read-only."""
        override: FontObject | None = self._override("font_object")
        if override is not None:
            return override
        if self._char_style is not None:
            font_idx = self._char_style.get("0")
            if isinstance(font_idx, int) and 0 <= font_idx < len(self._fonts):
                return self._fonts[font_idx]
        return None

    @property
    def fill_color(self) -> list[float] | None:
        """The Text layer's fill color as `[r, g, b]`. Read / Write."""
        override: list[float] | None = self._override("fill_color")
        if override is not None:
            return override
        if self._char_style is not None:
            return _parse_color(self._char_style.get("53"))
        return None

    @fill_color.setter
    def fill_color(self, value: list[float] | None) -> None:
        if value is not None:
            validate_rgb_color(value)
        self.__dict__.pop("fill_color", None)
        if self._char_style is not None:
            payload = _build_color_paint(value) if value is not None else None
            _apply_char_key(self, 0, u16_len(_raw_text(self)), "53", payload)
            self._propagate_cos()
        else:
            self._set_override("fill_color", value)

    @property
    def stroke_color(self) -> list[float] | None:
        """The Text layer's stroke color as `[r, g, b]`. Read / Write."""
        override: list[float] | None = self._override("stroke_color")
        if override is not None:
            return override
        if self._char_style is not None:
            return _parse_color(self._char_style.get("54"))
        return None

    @stroke_color.setter
    def stroke_color(self, value: list[float] | None) -> None:
        if value is not None:
            validate_rgb_color(value)
        self.__dict__.pop("stroke_color", None)
        if self._char_style is not None:
            payload = _build_color_paint(value) if value is not None else None
            _apply_char_key(self, 0, u16_len(_raw_text(self)), "54", payload)
            self._propagate_cos()
        else:
            self._set_override("stroke_color", value)

    @property
    def leading(self) -> float | None:
        """The Text layer's spacing between lines. Read / Write.

        When auto-leading is enabled, returns font_size * auto_leading_factor.
        """
        override: float | None = self._override("leading")
        if override is not None:
            return override
        if self._char_style is not None:
            raw = self._char_style.get("5")
            if isinstance(raw, (int, float)):
                # When auto-leading is on, AE stores a sentinel in key "5"
                # and displays font_size * auto_leading_factor (para "7").
                if self.auto_leading and self._para_style is not None:
                    factor = self._para_style.get("7", 1.2)
                    fs = self.font_size
                    if fs is not None:
                        return fs * float(factor)
                return float(raw)
        return None

    @leading.setter
    def leading(self, value: float | None) -> None:
        if value is not None:
            validate_positive_number(value)
        self.__dict__.pop("leading", None)
        if self._char_style is not None and value is not None:
            # Setting an explicit leading turns auto-leading off, matching AE.
            total = u16_len(_raw_text(self))
            _apply_char_key(self, 0, total, "5", float(value))
            _apply_char_key(self, 0, total, "4", False)
            self._propagate_cos()
        else:
            self._set_override("leading", value)

    @property
    def paragraph_count(self) -> int | None:
        """The number of paragraphs in the text layer. Read-only."""
        override: int | None = self._override("paragraph_count")
        if override is not None:
            return override
        para_runs = cos_get(self._doc, "0", "5", "0")
        if isinstance(para_runs, list):
            return len(para_runs)
        return None

    @property
    def all_caps(self) -> bool | None:
        """`True` if a Text layer has All Caps enabled. Read-only."""
        caps = self.font_caps_option
        if caps is None:
            return None
        return caps == FontCapsOption.FONT_ALL_CAPS

    @property
    def small_caps(self) -> bool | None:
        """`True` if a Text layer has Small Caps enabled. Read-only."""
        caps = self.font_caps_option
        if caps is None:
            return None
        return caps == FontCapsOption.FONT_SMALL_CAPS

    @property
    def superscript(self) -> bool | None:
        """`True` if a Text layer has superscript enabled. Read-only."""
        baseline = self.font_baseline_option
        if baseline is None:
            return None
        return baseline == FontBaselineOption.FONT_FAUXED_SUPERSCRIPT

    @property
    def subscript(self) -> bool | None:
        """`True` if a Text layer has subscript enabled. Read-only."""
        baseline = self.font_baseline_option
        if baseline is None:
            return None
        return baseline == FontBaselineOption.FONT_FAUXED_SUBSCRIPT

    @property
    def composer_engine(self) -> ComposerEngine | None:
        """The Text layer's composer engine type. Read-only."""
        engine_info = cos_get(self._cos_data, "1", "4")
        if isinstance(engine_info, dict):
            engine_name = engine_info.get("3")
            if engine_name == "DVA":
                return ComposerEngine.LATIN_CJK_ENGINE
            if engine_name == "Universal":
                return ComposerEngine.UNIVERSAL_TYPE_ENGINE
        return None

    @property
    def kerning(self) -> int:
        """The Text layer's kerning value. Read-only.

        Reads the leading-edge manual kern value AE stores at
        `doc["0"]["7"]` - written only when a kerning set includes pair
        position 0 (probed `W_KERN_START`). Documents without one read
        `0`, which is also what ExtendScript exports for every probed
        document-level read; per-character values live in the kerning
        runs via `character_range(...).kerning`.
        """
        val = cos_get(self._doc, "0", "7")
        if isinstance(val, int):
            return val
        return 0

    @property
    def line_orientation(self) -> LineOrientation:
        """The Text layer's line orientation. Read / Write."""
        val = cos_get(self._cos_data, "0", "8", "0", 0, "0", "2", "1")
        if isinstance(val, int):
            return LineOrientation.from_binary(val)
        return LineOrientation.HORIZONTAL

    @line_orientation.setter
    def line_orientation(self, value: LineOrientation) -> None:
        frame_meta = cos_get(self._cos_data, "0", "8", "0", 0, "0", "2")
        if not isinstance(frame_meta, dict):
            raise ValueError("text layer has no orientation frame to set")
        self._mark_frame_layout_dirty()
        frame_meta["1"] = value.to_binary()
        self._propagate_cos()

    def _box_frame(self) -> dict[str, Any] | None:
        """Return the COS box-frame dict, or `None` if absent."""
        frame = cos_get(self._cos_data, "0", "8", "0", 0, "0")
        return frame if isinstance(frame, dict) else None

    def _ensure_frame(self) -> dict[str, Any]:
        """Return the box-frame dict, creating the COS path if needed.

        Marks the layout dirty first (on every sibling document - the
        frame is layer-shared): every caller is a frame-meta setter
        whose write can change line composition, and the mark (with
        its calibration) must run before the mutation lands.
        """
        self._mark_frame_layout_dirty()
        eight = self._cos_data.setdefault("0", {}).setdefault("8", {})
        slot = eight.setdefault("0", [{}])
        if not slot:
            slot.append({})
        frame: dict[str, Any] = slot[0].setdefault("0", {})
        return frame

    def _box_outline(self) -> list[float] | None:
        """Return the box's 16-vertex outline coordinates, or `None`."""
        frame = self._box_frame()
        coords = cos_get(frame, "1", "0") if frame is not None else None
        if isinstance(coords, list) and len(coords) >= 14:
            return coords
        return None

    @property
    def box_text(self) -> bool:
        """`True` if this is a box (paragraph) text layer. Read-only.

        Box text stores the bounding-box vertex array in the frame; point
        text omits it.
        """
        frame = self._box_frame()
        return isinstance(frame, dict) and isinstance(frame.get("1"), dict)

    @property
    def point_text(self) -> bool:
        """`True` if this is a point text layer. Read-only."""
        return not self.box_text

    @property
    def box_text_size(self) -> list[float] | None:
        """The size of the text box as `[width, height]`. Read / Write.

        `None` for point text. Setting dimensions on point text converts
        it into a box (paragraph) text layer; on box text it resizes the
        box while keeping its top-left corner fixed.
        """
        coords = self._box_outline()
        if coords is None:
            return None
        return [abs(coords[12] - coords[0]), abs(coords[13] - coords[1])]

    @box_text_size.setter
    def box_text_size(self, value: list[float]) -> None:
        validate_box_size(value)
        width, height = float(value[0]), float(value[1])
        frame = self._ensure_frame()
        coords = self._box_outline()
        if coords is not None:
            left, top = coords[0], coords[1]
        else:
            # Point -> box conversion: AE centers the new box on the origin.
            left, top = -width / 2.0, -height / 2.0
            _apply_box_conversion(frame.setdefault("2", {}))
        frame.setdefault("1", {})["0"] = _box_coords(left, top, width, height)
        self._propagate_cos()

    @property
    def box_text_pos(self) -> list[float] | None:
        """The top-left position of the text box as `[x, y]`. Read / Write.

        `None` for point text. Setting moves the box while keeping its
        size; requires box (paragraph) text.
        """
        coords = self._box_outline()
        if coords is None:
            return None
        return [coords[0], coords[1]]

    @box_text_pos.setter
    def box_text_pos(self, value: list[float]) -> None:
        validate_vector2(value)
        coords = self._box_outline()
        if coords is None:
            raise ValueError("box_text_pos requires box text; set box_text_size first")
        width = abs(coords[12] - coords[0])
        height = abs(coords[13] - coords[1])
        frame = self._box_frame()
        assert frame is not None
        frame["1"]["0"] = _box_coords(float(value[0]), float(value[1]), width, height)
        self._propagate_cos()

    @property
    def box_inset_spacing(self) -> float:
        """The box's inset (padding) spacing in pixels. Read / Write."""
        val = cos_get(self._box_frame(), "2", "9")
        return float(val) if isinstance(val, (int, float)) else 0.0

    @box_inset_spacing.setter
    @requires_version(24)
    def box_inset_spacing(self, value: float) -> None:
        validate_positive_number(value)
        meta = self._ensure_frame().setdefault("2", {})
        meta["9"] = float(value)
        _numeric_sort(meta)
        self._propagate_cos()

    @property
    def box_vertical_alignment(self) -> BoxVerticalAlignment:
        """The box's vertical text alignment. Read / Write."""
        raw = cos_get(self._box_frame(), "2", "13")
        if isinstance(raw, int):
            return BoxVerticalAlignment.from_binary(raw)
        return BoxVerticalAlignment.TOP

    @box_vertical_alignment.setter
    @requires_version(24)
    def box_vertical_alignment(self, value: BoxVerticalAlignment) -> None:
        meta = self._ensure_frame().setdefault("2", {})
        meta["13"] = value.to_binary()
        _numeric_sort(meta)
        self._propagate_cos()

    @property
    def box_auto_fit_policy(self) -> BoxAutoFitPolicy:
        """The box's auto-fit policy. Read / Write."""
        raw = cos_get(self._box_frame(), "2", "14")
        if isinstance(raw, int):
            return BoxAutoFitPolicy.from_binary(raw)
        return BoxAutoFitPolicy.NONE

    @box_auto_fit_policy.setter
    @requires_version(24)
    def box_auto_fit_policy(self, value: BoxAutoFitPolicy) -> None:
        meta = self._ensure_frame().setdefault("2", {})
        meta["14"] = value.to_binary()
        _numeric_sort(meta)
        self._propagate_cos()

    @property
    def box_first_baseline_alignment(self) -> BoxFirstBaselineAlignment:
        """The box's first-baseline alignment. Read / Write."""
        sub = cos_get(self._box_frame(), "2", "10")
        if isinstance(sub, dict) and isinstance(sub.get("0"), int):
            return BoxFirstBaselineAlignment.from_binary(sub["0"])
        return BoxFirstBaselineAlignment.ASCENT

    @box_first_baseline_alignment.setter
    @requires_version(24)
    def box_first_baseline_alignment(self, value: BoxFirstBaselineAlignment) -> None:
        meta = self._ensure_frame().setdefault("2", {})
        sub = meta.setdefault("10", {})
        sub["0"] = value.to_binary()
        # AE always stores the minimum alongside the alignment.
        sub.setdefault("1", 0.0)
        _numeric_sort(meta)
        self._propagate_cos()

    @property
    def box_first_baseline_alignment_minimum(self) -> float:
        """The minimum for `MINIMUM_VALUE_*` first-baseline alignment. R/W."""
        sub = cos_get(self._box_frame(), "2", "10")
        if isinstance(sub, dict) and isinstance(sub.get("1"), (int, float)):
            return float(sub["1"])
        return 0.0

    @box_first_baseline_alignment_minimum.setter
    @requires_version(24)
    def box_first_baseline_alignment_minimum(self, value: float) -> None:
        meta = self._ensure_frame().setdefault("2", {})
        sub = meta.setdefault("10", {})
        sub.setdefault("0", BoxFirstBaselineAlignment.ASCENT.to_binary())
        sub["1"] = float(value)
        _numeric_sort(meta)
        self._propagate_cos()

    @property
    def box_overflow(self) -> bool | None:
        """`True` if the text overflows the box. Read-only.

        A composition covers fewer characters than the stored text
        exactly when the text overflows (probed via
        `samples/models/text/box_overflow.aep`). Reads the persisted AE
        cache while the document is untouched and the calibrated
        composer after layout-affecting py-side writes (see
        `composition_stale`). `None` for point text (ExtendScript reads
        undefined there) and for documents without a cache.
        """
        if not self._associated or not self.box_text:
            return None
        spans = _composed_line_spans(self)
        if spans is None:
            return None
        if not spans:
            # The calibrated composer clipped every line (box shorter
            # than the first baseline): all stored text overflows. The
            # cached path never yields an empty list.
            return True
        return spans[-1][1] < u16_len(_raw_text(self))

    @property
    def composed_line_count(self) -> int | None:
        """The number of composed lines in the Text layer. Read-only.

        Point text derives its lines from the paragraphs (always
        fresh). Box text reads the layout cache AE persisted at save
        time; after a layout-affecting py-side write the calibrated
        composed-line resolver recomposes it, otherwise the cached
        count stays (matching ExtendScript's un-reapplied values - see
        `composition_stale`). `None` for documents never parsed from a
        layer.
        """
        if not self._associated:
            return None
        spans = _composed_line_spans(self)
        if spans is None:
            return None
        return len(spans)

    @property
    def baseline_locs(self) -> list[float]:
        """The baseline (x,y) locations for a Text layer. Line wraps in a
        paragraph text box are treated as multiple lines. Read-only.

        Four floats per composed line - `line.start_x, line.start_y,
        line.end_x, line.end_y` - in layer coordinates. Empty for
        documents never parsed from a layer or without a layout cache.

        Tip:
            If a line has no characters, the x and y values for start and
            end are the maximum float value (`3.402823466e+38`).

        Note:
            Unlike [composed_line_count][TextDocument.composed_line_count],
            this always reports the layout After Effects persisted: the
            per-line pen origins and glyph advances only exist in that
            cache, and the composed-line resolver does not reproduce them.
            After a layout-affecting py-side write the values therefore
            stay at the persisted layout even when the resolver could
            recompose the line spans (see `composition_stale`).
        """
        if not self._associated:
            return []
        nodes = _cached_line_nodes(self)
        data = _line_data_from_nodes(nodes)
        if data is None:
            return []
        spans, _baselines = data
        raw = _raw_text(self)
        visible = _visible_length(self)
        offset_x = 0.0
        offset_y = 0.0
        if self.box_text:
            # A box's cache origins are box-relative; box_text_pos is the
            # box's top-left corner in layer coordinates (probed AE 2026:
            # a 220x140 centered box reports -110/-70).
            box_pos = self.box_text_pos
            if box_pos is not None:
                offset_x = float(box_pos[0])
                offset_y = float(box_pos[1])
        out: list[float] = []
        for (start, end), node in zip(spans, nodes):
            advances = _line_advances(node)
            line_text = u16_slice(raw, start, end)
            # The stored advances carry one entry per GLYPH, not per
            # character - a ligature ("ffi") merges several characters into
            # one. Rather than map characters to glyphs, count the glyphs to
            # drop from the END: a terminator, a character clipped past the
            # visible text and a trailing space are each exactly one glyph
            # (none of them ever joins a ligature), so this stays correct on
            # ligated text.
            tail = 0
            if line_text.endswith("\r"):
                line_text = line_text[:-1]
                tail += 1
            overshoot = max(0, u16_len(line_text) - max(0, visible - start))
            if overshoot:
                tail += overshoot
                line_text = u16_slice(line_text, 0, u16_len(line_text) - overshoot)
            if not line_text or not advances:
                out.extend([_EMPTY_LINE_LOC] * 4)
                continue
            # A wrapped line keeps the space group it broke on, but that
            # group sits outside the reported extent (probed AE 2026).
            tail += u16_len(line_text) - u16_len(line_text.rstrip(" "))
            index = len(advances) - tail - 1
            advance = advances[index] if 0 <= index < len(advances) else 0.0
            origin_x, origin_y = _line_origin(node)
            start_x = origin_x + offset_x
            start_y = origin_y + offset_y
            out.extend([start_x, start_y, start_x + advance, start_y])
        return out

    @property
    def paragraph_ranges(self) -> list[dict[str, int]]:
        """Character bounds of every paragraph as `{"start", "end"}`
        records. Read-only.

        Matches [paragraph_range][TextDocument.paragraph_range] bounds
        (paragraph spans clamped to the visible text) from one pass
        over the paragraph runs; empty for documents never parsed from
        a layer. Ground-truth validation compares this against
        ExtendScript's per-paragraph dump.
        """
        if not self._associated:
            return []
        visible = _visible_length(self)
        return [
            {"start": min(start, visible), "end": min(end, visible)}
            for start, end, _style in _para_run_spans(self)
        ]

    @property
    def composed_line_ranges(self) -> list[dict[str, int]]:
        """Character bounds of every composed line as `{"start", "end"}`
        records. Read-only.

        Matches [composed_line_range][TextDocument.composed_line_range]
        bounds (ends clamped to the visible text, stale cached lines
        beyond it dropped) from one span derivation; empty for
        documents never parsed from a layer or without a layout cache.
        Like the other composed-line APIs, recomposes freshly when the
        calibrated composer covers the document, otherwise reflects the
        composition AE last persisted.
        """
        if not self._associated:
            return []
        spans = _composed_line_spans(self)
        if spans is None:
            return []
        visible = _visible_length(self)
        out = []
        for start, end in spans:
            if start > visible:
                break  # stale cache: lines wholly beyond the current text
            out.append({"start": start, "end": min(end, visible)})
        return out

    # -- Style resets --------------------------------------------------------

    def reset_char_style(self) -> None:
        """Restores all characters in the Text layer to the default text
        character characteristics in the Character panel.

        After Effects applies its Character-panel defaults, which live in
        the AE preferences rather than the project file (the
        `["Text Style Sheet"]` section - the same values `addText` gives a
        new layer). py_aep reads them from the preferences directory the
        project was parsed with, and falls back to AE's factory values when
        no preference file is available.

        Note:
            Attributes the Character panel does not carry are left alone,
            matching After Effects.

        Raises:
            ValueError: If the document was never associated with a layer.
        """
        self._require_association()
        style = default_character_style(self._effective_preferences())
        self.font = cast("str", style["font"])
        self.font_size = style["font_size"]
        self.faux_bold = style["faux_bold"]
        self.faux_italic = style["faux_italic"]
        self.apply_fill = style["apply_fill"]
        self.fill_color = style["fill_color"]
        # Set the stroke colour and width before the toggle: AE refuses to
        # read strokeColor once applyStroke is off, and py mirrors that.
        self.stroke_color = style["stroke_color"]
        self.stroke_width = style["stroke_width"]
        self.stroke_over_fill = style["stroke_over_fill"]
        self.apply_stroke = style["apply_stroke"]
        self.tracking = style["tracking"]
        self.tsume = style["tsume"]
        self.horizontal_scale = style["horizontal_scale"]
        self.vertical_scale = style["vertical_scale"]
        self.baseline_shift = style["baseline_shift"]
        self.auto_leading = style["auto_leading"]
        # Last: the panel's kerning mode also clears any MANUAL kerning
        # (probed AE 2026 - a reset takes autoKernType back to Metric and
        # the per-pair values become undefined).
        self.auto_kern_type = style["auto_kern_type"]

    def reset_paragraph_style(self) -> None:
        """Restores all paragraphs in the Text layer to the default text
        paragraph characteristics in the Paragraph panel.

        After Effects applies its Paragraph-panel defaults, which live in
        the AE preferences rather than the project file (the
        `["Text Paragraph Sheet"]` section). py_aep reads them from the
        preferences directory the project was parsed with, and falls back to
        AE's factory values when no preference file is available.

        Note:
            Hyphenation has no entry in that sheet, so - like After Effects -
            this leaves [auto_hyphenate][TextDocument.auto_hyphenate]
            untouched.

        Raises:
            ValueError: If the document was never associated with a layer.
        """
        self._require_association()
        style = default_paragraph_style(self._effective_preferences())
        self.justification = style["justification"]
        self.first_line_indent = style["first_line_indent"]
        self.start_indent = style["start_indent"]
        self.end_indent = style["end_indent"]
        self.space_before = style["space_before"]
        self.space_after = style["space_after"]
        self.hanging_roman = style["hanging_roman"]
        self.every_line_composer = style["every_line_composer"]

    def _effective_preferences(self) -> Preferences:
        """The project's AE preferences, or an empty set (AE factory
        defaults) for a document parsed without a preferences directory."""
        if self._preferences is None:
            return Preferences()
        return self._preferences

    # -- Text ranges (AE 24.3+ ExtendScript API) -----------------------------

    def _require_association(self) -> None:
        """Raise unless this document was parsed from a layer's data.

        AE refuses every range API on a `new TextDocument()` never
        fetched from a layer ("Unable to set value as it is not
        associated with a layer."); template-constructed documents
        behave identically here.
        """
        if not self._associated:
            raise ValueError(NOT_ASSOCIATED)

    def character_range(
        self, character_start: int, signed_character_end: int | None = None
    ) -> CharacterRange:
        """A [CharacterRange][] over part of this document.

        Args:
            character_start: First character index (UTF-16 units,
                `0 <= character_start <= text length`).
            signed_character_end: Index past the last character. `-1`
                resolves dynamically to the text length; when omitted,
                defaults to `character_start + 1`.

        Raises:
            ValueError: When the indices are outside the document
                bounds (AE raises at creation time).
        """
        self._require_association()
        validate_positive_int(character_start, self)
        if signed_character_end is None:
            signed_character_end = character_start + 1
        else:
            validate_int(signed_character_end, self)
        return CharacterRange(self, character_start, signed_character_end)

    def paragraph_range(
        self, paragraph_index_start: int, signed_paragraph_index_end: int | None = None
    ) -> ParagraphRange:
        """A [ParagraphRange][] over part of this document.

        Args:
            paragraph_index_start: First paragraph index
                (`0 <= paragraph_index_start < paragraph count`).
            signed_paragraph_index_end: Index past the last paragraph.
                `-1` resolves dynamically to the paragraph count; when
                omitted, defaults to `paragraph_index_start + 1`.

        Raises:
            ValueError: When the indices are outside the document
                bounds (AE raises at creation time).
        """
        self._require_association()
        validate_positive_int(paragraph_index_start, self)
        if signed_paragraph_index_end is None:
            signed_paragraph_index_end = paragraph_index_start + 1
        else:
            validate_int(signed_paragraph_index_end, self)
        return ParagraphRange(self, paragraph_index_start, signed_paragraph_index_end)

    def composed_line_range(
        self,
        composed_line_index_start: int,
        signed_composed_line_index_end: int | None = None,
    ) -> ComposedLineRange:
        """A [ComposedLineRange][] over part of this document.

        Composed lines come from the layout cache AE persisted at save
        time, or from the calibrated composed-line resolver after
        py-side edits; see [ComposedLineRange][] for the semantics.

        Args:
            composed_line_index_start: First composed-line index
                (`0 <= composed_line_index_start < composed line count`).
            signed_composed_line_index_end: Index past the last line.
                `-1` resolves dynamically to the line count; when
                omitted, defaults to `composed_line_index_start + 1`.

        Raises:
            ValueError: When the indices are outside the cached
                composed lines (AE raises at creation time).
        """
        self._require_association()
        validate_positive_int(composed_line_index_start, self)
        if signed_composed_line_index_end is None:
            signed_composed_line_index_end = composed_line_index_start + 1
        else:
            validate_int(signed_composed_line_index_end, self)
        return ComposedLineRange(
            self, composed_line_index_start, signed_composed_line_index_end
        )

    def paragraph_character_indexes_at(self, character_index: int) -> dict[str, int]:
        """The character bounds of the paragraph containing an index.

        Args:
            character_index: A character index (UTF-16 units) within
                the text.

        Returns:
            `{"start": int, "end": int}` for the containing paragraph.

        Raises:
            ValueError: When `character_index` is outside the text.
        """
        self._require_association()
        validate_positive_int(character_index, self)
        visible = _visible_length(self)
        for start, end, _payload in _para_run_spans(self):
            if start <= character_index < end:
                return {"start": start, "end": min(end, visible)}
        raise ValueError(CHARACTER_RANGE_OOB)

    def composed_line_character_indexes_at(
        self, character_index: int
    ) -> dict[str, int]:
        """The character bounds of the composed line containing an index.

        Args:
            character_index: A character index (UTF-16 units) within
                the text.

        Returns:
            `{"start": int, "end": int}` for the containing composed line.

        Raises:
            ValueError: When `character_index` is outside the text or
                the document has no composed-line cache.
        """
        self._require_association()
        validate_positive_int(character_index, self)
        visible = _visible_length(self)
        spans = _composed_line_spans(self)
        if spans is not None:
            for start, end in spans:
                if start <= character_index < end:
                    return {"start": start, "end": min(end, visible)}
        raise ValueError(CHARACTER_RANGE_OOB)

    # -- COS write-back ----------------------------------------------------

    def _propagate_cos(self) -> None:
        """Serialize COS data back to the btdk chunk's binary_data."""
        self._btdk_body.data = serialize(self._cos_data)
