"""TextDocument model for After Effects text layers."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from ...ae_version import requires_version
from ...binary.chunk import ListChunk
from ...cos import CosField, CosName, cos_get, get_cos_template, serialize
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
from ..validators import (
    validate_box_size,
    validate_enum,
    validate_font_name,
    validate_positive_nonzero_number,
    validate_positive_number,
    validate_rgb_color,
    validate_text,
    validate_vector2,
)
from .font_object import FontObject

if TYPE_CHECKING:
    from typing import Any

    from ...binary.item_chunks import HeadChunk


def _parse_color(paint: object) -> list[float] | None:
    """Extract [R, G, B] from a COS SimplePaint structure."""
    argb = cos_get(paint, "0", "1")
    if isinstance(argb, list) and len(argb) >= 4:
        return [float(argb[1]), float(argb[2]), float(argb[3])]
    return None


def _build_color_paint(rgb: list[float]) -> dict[str, Any]:
    """Build a COS SimplePaint dict from [R, G, B].

    The 4-float array is `[alpha, R, G, B]`; AE stores a fully opaque
    alpha of `1.0`.
    """
    return {
        "99": CosName("SimplePaint"),
        "0": {"0": 1, "1": [1.0, rgb[0], rgb[1], rgb[2]]},
    }


def _build_font_entry(post_script_name: str) -> dict[str, Any]:
    """Build a COS CoolTypeFont entry for a font PostScript name."""
    return {"0": {"99": CosName("CoolTypeFont"), "0": {"0": post_script_name, "2": 1}}}


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

    # -- Character-style CosField descriptors (_char_style dict) -----------

    font_size = CosField.float(
        "_char_style", "1", default=None, validate=validate_positive_nonzero_number
    )
    """The Text layer's font size in pixels. Read / Write."""

    faux_bold = CosField.bool("_char_style", "2", default=None)
    """`True` if a Text layer has faux bold enabled. Read / Write."""

    faux_italic = CosField.bool("_char_style", "3", default=None)
    """`True` if a Text layer has faux italic enabled. Read / Write."""

    tracking = CosField.float("_char_style", "8", default=None)
    """The Text layer's spacing between characters. Read / Write."""

    auto_kern_type = CosField.enum(
        AutoKernType,
        "_char_style",
        "11",
        default=AutoKernType.NO_AUTO_KERN,
    )
    """The Text layer's auto kern type option. Read / Write."""

    horizontal_scale = CosField.float("_char_style", "6", default=None)
    """This Text layer's horizontal scale in pixels. Read / Write."""

    vertical_scale = CosField.float("_char_style", "7", default=None)
    """This Text layer's vertical scale in pixels. Read / Write."""

    baseline_shift = CosField.float("_char_style", "9", default=None)
    """This Text layer's baseline shift in pixels. Read / Write."""

    font_caps_option = CosField.enum(
        FontCapsOption,
        "_char_style",
        "12",
        default=None,
    )
    """The Text layer's font caps option. Read / Write."""

    font_baseline_option = CosField.enum(
        FontBaselineOption,
        "_char_style",
        "13",
        default=None,
    )
    """The Text layer's font baseline option. Read / Write."""

    tsume = CosField.float("_char_style", "36", default=0.0)
    """This Text layer's tsume value (0.0 to 1.0). Read / Write."""

    apply_fill = CosField.bool("_char_style", "56", default=None)
    """When `True`, the Text layer shows a fill. Read / Write."""

    apply_stroke = CosField.bool("_char_style", "57", default=False)
    """When `True`, the Text layer shows a stroke. Read / Write."""

    stroke_over_fill = CosField.bool("_char_style", "58", default=True)
    """When `True`, the stroke appears over the fill. Read / Write."""

    stroke_width = CosField.float(
        "_char_style", "63", default=1.0, validate=validate_positive_nonzero_number
    )
    """The Text layer's stroke thickness in pixels. Read / Write."""

    # -- Paragraph-style CosField descriptors (_para_style dict) -----------

    justification = CosField.enum(
        ParagraphJustification,
        "_para_style",
        "0",
        default=None,
    )
    """The paragraph justification for the Text layer. Read / Write."""

    first_line_indent = CosField.float("_para_style", "1", default=0.0)
    """The Text layer's paragraph first line indent. Read / Write."""

    start_indent = CosField.float("_para_style", "2", default=0.0)
    """The Text layer's paragraph start indent. Read / Write."""

    end_indent = CosField.float("_para_style", "3", default=0.0)
    """The Text layer's paragraph end indent. Read / Write."""

    space_before = CosField.float("_para_style", "4", default=0.0)
    """The Text layer's paragraph space before. Read / Write."""

    space_after = CosField.float("_para_style", "5", default=0.0)
    """The Text layer's paragraph space after. Read / Write."""

    auto_leading = CosField.bool("_char_style", "4", default=True)
    """The Text layer's auto leading option. Read / Write."""

    leading_type = CosField.enum(
        LeadingType,
        "_para_style",
        "8",
        default=LeadingType.ROMAN_LEADING_TYPE,
    )
    """The Text layer's paragraph leading type. Read / Write."""

    auto_hyphenate = CosField.bool("_para_style", "9", default=None)
    """The Text layer's auto hyphenate option. Read / Write."""

    hanging_roman = CosField.bool("_para_style", "21", default=False)
    """The Text layer's Roman Hanging Punctuation. Read / Write."""

    every_line_composer = CosField.bool("_para_style", "29", default=False)
    """The Text layer's Every-Line Composer option. Read / Write.

    `True` when Every-Line Composer is used, `False` for Single-Line.
    """

    baseline_direction = CosField.enum(
        BaselineDirection,
        "_char_style",
        "35",
        default=BaselineDirection.BASELINE_WITH_STREAM,
    )
    """The Text layer's baseline direction. Read / Write."""

    ligature = CosField.bool("_char_style", "18", default=False)
    """When `True`, ligature is used. Read / Write."""

    no_break = CosField.bool("_char_style", "52", default=False)
    """When `True`, the no-break attribute is applied. Read / Write."""

    digit_set = CosField.enum(
        DigitSet,
        "_char_style",
        "70",
        default=DigitSet.DEFAULT_DIGITS,
    )
    """The Text layer's digit set option. Read / Write."""

    line_join_type = CosField.enum(
        LineJoinType,
        "_char_style",
        "62",
        default=LineJoinType.LINE_JOIN_MITER,
    )
    """The Text layer's line join type for strokes. Read / Write."""

    direction = CosField.enum(
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
            return str(val).rstrip("\r\n").replace("\r", "\n")
        return ""

    @text.setter
    def text(self, value: str) -> None:
        validate_text(value)
        self.__dict__.pop("text", None)
        inner = self._doc.setdefault("0", {})
        # AE stores every line break and the run terminator as CR (\r);
        # without a trailing CR terminator AE fails to read the layer.
        normalized = value.replace("\r\n", "\r").replace("\n", "\r")
        inner["0"] = normalized.rstrip("\r") + "\r"
        self._propagate_cos()

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
        self._char_style["0"] = idx
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
        """Append a new font to the COS font array and `_fonts`.

        AE prepends the active font, but appending avoids re-indexing the
        font references held by existing character/paragraph styles while
        still producing a valid file. Returns the new font's index.
        """
        font_array = (
            self._cos_data.setdefault("0", {}).setdefault("1", {}).setdefault("0", [])
        )
        entry = _build_font_entry(post_script_name)
        font_array.append(entry)
        self._fonts.append(
            FontObject(_font_data=entry["0"]["0"], _font_entry=entry["0"])
        )
        return len(self._fonts) - 1

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
            if value is None:
                self._char_style.pop("53", None)
            else:
                self._char_style["53"] = _build_color_paint(value)
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
            if value is None:
                self._char_style.pop("54", None)
            else:
                self._char_style["54"] = _build_color_paint(value)
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
            self._char_style["5"] = value
            self._char_style["4"] = False
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

        AE stores a uniform manual-kerning value at the document level;
        per-pair kerning is not exposed. Returns `0` when unset (the
        default for metric / optical auto-kerning).
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
        frame_meta["1"] = value.to_binary()
        self._propagate_cos()

    def _box_frame(self) -> dict[str, Any] | None:
        """Return the COS box-frame dict, or `None` if absent."""
        frame = cos_get(self._cos_data, "0", "8", "0", 0, "0")
        return frame if isinstance(frame, dict) else None

    def _ensure_frame(self) -> dict[str, Any]:
        """Return the box-frame dict, creating the COS path if needed."""
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
    def composed_line_count(self) -> int | None:
        """The number of composed lines in the Text layer. Read-only."""
        txt = self.text
        if not txt:
            return None
        return txt.count("\n") + 1

    # -- COS write-back ----------------------------------------------------

    def _propagate_cos(self) -> None:
        """Serialize COS data back to the btdk chunk's binary_data."""
        self._btdk_body.data = serialize(self._cos_data)
