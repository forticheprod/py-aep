"""TextDocument model for After Effects text layers."""

from __future__ import annotations

import typing

from ...cos import CosField, serialize
from ...enums import (
    AutoKernType,
    BaselineDirection,
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

if typing.TYPE_CHECKING:
    from typing import Any

    from ...binary.chunk import Chunk
    from .font_object import FontObject


_JUSTIFICATION_MAP: dict[int, ParagraphJustification] = {
    0: ParagraphJustification.LEFT_JUSTIFY,
    1: ParagraphJustification.RIGHT_JUSTIFY,
    2: ParagraphJustification.CENTER_JUSTIFY,
    3: ParagraphJustification.FULL_JUSTIFY_LASTLINE_LEFT,
    4: ParagraphJustification.FULL_JUSTIFY_LASTLINE_RIGHT,
    5: ParagraphJustification.FULL_JUSTIFY_LASTLINE_CENTER,
    6: ParagraphJustification.FULL_JUSTIFY_LASTLINE_FULL,
}
_REVERSE_JUSTIFICATION_MAP: dict[ParagraphJustification, int] = {
    v: k for k, v in _JUSTIFICATION_MAP.items()
}

_FONT_CAPS_MAP: dict[int, FontCapsOption] = {
    0: FontCapsOption.FONT_NORMAL_CAPS,
    1: FontCapsOption.FONT_SMALL_CAPS,
    2: FontCapsOption.FONT_ALL_CAPS,
    3: FontCapsOption.FONT_ALL_SMALL_CAPS,
}
_REVERSE_FONT_CAPS_MAP: dict[FontCapsOption, int] = {
    v: k for k, v in _FONT_CAPS_MAP.items()
}

_FONT_BASELINE_MAP: dict[int, FontBaselineOption] = {
    0: FontBaselineOption.FONT_NORMAL_BASELINE,
    1: FontBaselineOption.FONT_FAUXED_SUPERSCRIPT,
    2: FontBaselineOption.FONT_FAUXED_SUBSCRIPT,
}
_REVERSE_FONT_BASELINE_MAP: dict[FontBaselineOption, int] = {
    v: k for k, v in _FONT_BASELINE_MAP.items()
}

_LEADING_TYPE_MAP: dict[int, LeadingType] = {
    0: LeadingType.ROMAN_LEADING_TYPE,
    1: LeadingType.JAPANESE_LEADING_TYPE,
}
_REVERSE_LEADING_TYPE_MAP: dict[LeadingType, int] = {
    v: k for k, v in _LEADING_TYPE_MAP.items()
}


def _parse_color(paint: object) -> list[float] | None:
    """Extract [R, G, B] from a COS SimplePaint structure."""
    if not isinstance(paint, dict):
        return None
    inner = paint.get("0")
    if not isinstance(inner, dict):
        return None
    argb = inner.get("1")
    if isinstance(argb, list) and len(argb) >= 4:
        return [float(argb[1]), float(argb[2]), float(argb[3])]
    return None


def _build_color_paint(rgb: list[float]) -> dict[str, Any]:
    """Build a COS SimplePaint dict from [R, G, B]."""
    return {
        "0": {"0": 1, "1": [0.0, rgb[0], rgb[1], rgb[2]]},
        "99": "SimplePaint",
    }


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

    # -- Character-style CosField descriptors (_char_style dict) -----------

    font_size: float | None = CosField.float("_char_style", "1")  # type: ignore[assignment]
    """The Text layer's font size in pixels. Read / Write."""

    faux_bold: bool | None = CosField.bool("_char_style", "2")  # type: ignore[assignment]
    """`True` if a Text layer has faux bold enabled. Read / Write."""

    faux_italic: bool | None = CosField.bool("_char_style", "3")  # type: ignore[assignment]
    """`True` if a Text layer has faux italic enabled. Read / Write."""

    tracking: float | None = CosField.float("_char_style", "8")  # type: ignore[assignment]
    """The Text layer's spacing between characters. Read / Write."""

    auto_kern_type: AutoKernType = AutoKernType.NO_AUTO_KERN
    """The Text layer's auto kern type option. Read / Write."""

    horizontal_scale: float | None = CosField.float("_char_style", "6")  # type: ignore[assignment]
    """This Text layer's horizontal scale in pixels. Read / Write."""

    vertical_scale: float | None = CosField.float("_char_style", "7")  # type: ignore[assignment]
    """This Text layer's vertical scale in pixels. Read / Write."""

    baseline_shift: float | None = CosField.float("_char_style", "9")  # type: ignore[assignment]
    """This Text layer's baseline shift in pixels. Read / Write."""

    font_caps_option: FontCapsOption | None = CosField.enum(  # type: ignore[assignment]
        FontCapsOption,
        "_char_style",
        "12",
        map=_FONT_CAPS_MAP,
        reverse_map=_REVERSE_FONT_CAPS_MAP,
    )
    """The Text layer's font caps option. Read / Write."""

    font_baseline_option: FontBaselineOption | None = CosField.enum(  # type: ignore[assignment]
        FontBaselineOption,
        "_char_style",
        "13",
        map=_FONT_BASELINE_MAP,
        reverse_map=_REVERSE_FONT_BASELINE_MAP,
    )
    """The Text layer's font baseline option. Read / Write."""

    tsume: float | None = CosField.float("_char_style", "17")  # type: ignore[assignment]
    """This Text layer's tsume value (0.0 to 1.0). Read / Write."""

    apply_fill: bool | None = CosField.bool("_char_style", "56")  # type: ignore[assignment]
    """When `True`, the Text layer shows a fill. Read / Write."""

    apply_stroke: bool | None = CosField.bool("_char_style", "57")  # type: ignore[assignment]
    """When `True`, the Text layer shows a stroke. Read / Write."""

    stroke_over_fill: bool | None = CosField.bool("_char_style", "58")  # type: ignore[assignment]
    """When `True`, the stroke appears over the fill. Read / Write."""

    stroke_width: float | None = CosField.float("_char_style", "63")  # type: ignore[assignment]
    """The Text layer's stroke thickness in pixels. Read / Write."""

    # -- Paragraph-style CosField descriptors (_para_style dict) -----------

    justification: ParagraphJustification | None = CosField.enum(  # type: ignore[assignment]
        ParagraphJustification,
        "_para_style",
        "0",
        map=_JUSTIFICATION_MAP,
        reverse_map=_REVERSE_JUSTIFICATION_MAP,
    )
    """The paragraph justification for the Text layer. Read / Write."""

    first_line_indent: float | None = CosField.float("_para_style", "1")  # type: ignore[assignment]
    """The Text layer's paragraph first line indent. Read / Write."""

    start_indent: float | None = CosField.float("_para_style", "2")  # type: ignore[assignment]
    """The Text layer's paragraph start indent. Read / Write."""

    end_indent: float | None = CosField.float("_para_style", "3")  # type: ignore[assignment]
    """The Text layer's paragraph end indent. Read / Write."""

    space_before: float | None = CosField.float("_para_style", "4")  # type: ignore[assignment]
    """The Text layer's paragraph space before. Read / Write."""

    space_after: float | None = CosField.float("_para_style", "5")  # type: ignore[assignment]
    """The Text layer's paragraph space after. Read / Write."""

    auto_leading: bool | None = CosField.bool("_para_style", "6")  # type: ignore[assignment]
    """The Text layer's auto leading option. Read / Write."""

    leading_type: LeadingType | None = CosField.enum(  # type: ignore[assignment]
        LeadingType,
        "_para_style",
        "8",
        map=_LEADING_TYPE_MAP,
        reverse_map=_REVERSE_LEADING_TYPE_MAP,
    )
    """The Text layer's paragraph leading type. Read / Write."""

    auto_hyphenate: bool | None = CosField.bool("_para_style", "9")  # type: ignore[assignment]
    """The Text layer's auto hyphenate option. Read / Write."""

    hanging_roman: bool | None = CosField.bool("_para_style", "21")  # type: ignore[assignment]
    """The Text layer's Roman Hanging Punctuation. Read / Write."""

    kerning: int = 0
    """The Text layer's kerning value. Read / Write."""

    baseline_direction: BaselineDirection = (
        BaselineDirection.BASELINE_WITH_STREAM
    )
    """The Text layer's baseline direction. Read / Write."""

    ligature: bool = False
    """When `True`, ligature is used. Read / Write."""

    no_break: bool = False
    """When `True`, the no-break attribute is applied. Read / Write."""

    digit_set: DigitSet = DigitSet.DEFAULT_DIGITS
    """The Text layer's digit set option. Read / Write."""

    line_join_type: LineJoinType = LineJoinType.LINE_JOIN_MITER
    """The Text layer's line join type for strokes. Read / Write."""

    direction: ParagraphDirection = ParagraphDirection.DIRECTION_LEFT_TO_RIGHT
    """The Text layer's paragraph direction. Read / Write."""

    line_orientation: LineOrientation = LineOrientation.HORIZONTAL
    """The Text layer's line orientation. Read / Write."""

    # -- Constructor -------------------------------------------------------

    def __init__(
        self,
        *,
        _char_style: dict[str, Any] | None = None,
        _para_style: dict[str, Any] | None = None,
        _doc: dict[str, Any] | None = None,
        _fonts: list[FontObject] | None = None,
        _cos_data: dict[str, Any] | None = None,
        _btdk_body: Chunk | None = None,
        # Fallback kwargs for fields without COS backing
        text: str | None = None,
        font: str | None = None,
        font_object: FontObject | None = None,
        fill_color: list[float] | None = None,
        stroke_color: list[float] | None = None,
        paragraph_count: int | None = None,
        **kwargs: Any,
    ) -> None:
        self._char_style = _char_style
        self._para_style = _para_style
        self._doc = _doc
        self._fonts = _fonts or []
        self._cos_data = _cos_data
        self._btdk_body = _btdk_body
        # Instance overrides for non-descriptor fields
        if text is not None:
            self.__dict__["text"] = text
        if font is not None:
            self.__dict__["font"] = font
        if font_object is not None:
            self.__dict__["font_object"] = font_object
        if fill_color is not None:
            self.__dict__["fill_color"] = fill_color
        if stroke_color is not None:
            self.__dict__["stroke_color"] = stroke_color
        if paragraph_count is not None:
            self.__dict__["paragraph_count"] = paragraph_count
        # Accept any CosField-backed kwargs as instance overrides
        for key, val in kwargs.items():
            if val is not None:
                self.__dict__[key] = val

    # -- Computed properties -----------------------------------------------

    @property  # type: ignore[no-redef]
    def text(self) -> str:
        """The text value for the Source Text property. Read / Write."""
        if "text" in self.__dict__:
            return str(self.__dict__["text"])
        if self._doc is not None:
            val = self._doc.get("0", {}).get("0")
            if val is not None:
                return str(val).rstrip("\r\n")
        return ""

    @text.setter
    def text(self, value: str) -> None:
        self.__dict__.pop("text", None)
        if self._doc is not None:
            inner = self._doc.setdefault("0", {})
            inner["0"] = value
            self._propagate_cos()
        else:
            self.__dict__["text"] = value

    @property
    def font(self) -> str | None:
        """The Text layer's font PostScript name. Read / Write."""
        if "font" in self.__dict__:
            result: str | None = self.__dict__["font"]
            return result
        if self._char_style is not None:
            font_idx = self._char_style.get("0")
            if isinstance(font_idx, int) and 0 <= font_idx < len(self._fonts):
                return self._fonts[font_idx].post_script_name
        return None

    @font.setter
    def font(self, value: str | None) -> None:
        self.__dict__.pop("font", None)
        if value is None:
            self.__dict__["font"] = None
            return
        if self._char_style is not None:
            for idx, fo in enumerate(self._fonts):
                if fo.post_script_name == value:
                    self._char_style["0"] = idx
                    self.__dict__.pop("font_object", None)
                    self._propagate_cos()
                    return
        self.__dict__["font"] = value

    @property
    def font_object(self) -> FontObject | None:
        """The Text layer's [FontObject][]. Read / Write."""
        if "font_object" in self.__dict__:
            result: FontObject | None = self.__dict__["font_object"]
            return result
        if self._char_style is not None:
            font_idx = self._char_style.get("0")
            if isinstance(font_idx, int) and 0 <= font_idx < len(self._fonts):
                return self._fonts[font_idx]
        return None

    @font_object.setter
    def font_object(self, value: FontObject | None) -> None:
        self.__dict__["font_object"] = value

    @property
    def fill_color(self) -> list[float] | None:
        """The Text layer's fill color as `[r, g, b]`. Read / Write."""
        if "fill_color" in self.__dict__:
            result: list[float] | None = self.__dict__["fill_color"]
            return result
        if self._char_style is not None:
            return _parse_color(self._char_style.get("53"))
        return None

    @fill_color.setter
    def fill_color(self, value: list[float] | None) -> None:
        self.__dict__.pop("fill_color", None)
        if self._char_style is not None:
            if value is None:
                self._char_style.pop("53", None)
            else:
                self._char_style["53"] = _build_color_paint(value)
            self._propagate_cos()
        else:
            self.__dict__["fill_color"] = value

    @property
    def stroke_color(self) -> list[float] | None:
        """The Text layer's stroke color as `[r, g, b]`. Read / Write."""
        if "stroke_color" in self.__dict__:
            result: list[float] | None = self.__dict__["stroke_color"]
            return result
        if self._char_style is not None:
            return _parse_color(self._char_style.get("54"))
        return None

    @stroke_color.setter
    def stroke_color(self, value: list[float] | None) -> None:
        self.__dict__.pop("stroke_color", None)
        if self._char_style is not None:
            if value is None:
                self._char_style.pop("54", None)
            else:
                self._char_style["54"] = _build_color_paint(value)
            self._propagate_cos()
        else:
            self.__dict__["stroke_color"] = value

    @property
    def leading(self) -> float | None:
        """The Text layer's spacing between lines. Read / Write.

        When auto-leading is enabled, returns font_size * auto_leading_factor.
        """
        if "leading" in self.__dict__:
            result: float | None = self.__dict__["leading"]
            return result
        if self._char_style is not None:
            raw = self._char_style.get("10")
            if isinstance(raw, (int, float)):
                if raw == 0 and self.auto_leading and self._para_style is not None:
                    factor = self._para_style.get("7", 1.2)
                    fs = self.font_size
                    if fs is not None:
                        return fs * float(factor)
                return float(raw)
        return None

    @leading.setter
    def leading(self, value: float | None) -> None:
        self.__dict__.pop("leading", None)
        if self._char_style is not None and value is not None:
            self._char_style["10"] = value
            self._propagate_cos()
        else:
            self.__dict__["leading"] = value

    @property
    def paragraph_count(self) -> int | None:
        """The number of paragraphs in the text layer. Read-only."""
        if "paragraph_count" in self.__dict__:
            result: int | None = self.__dict__["paragraph_count"]
            return result
        if self._doc is not None:
            para_runs = self._doc.get("0", {}).get("5", {}).get("0")
            if isinstance(para_runs, list):
                return len(para_runs)
        return None

    @paragraph_count.setter
    def paragraph_count(self, value: int | None) -> None:
        self.__dict__["paragraph_count"] = value

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
    def every_line_composer(self) -> bool | None:
        """The Text layer's Every-Line Composer option. Read / Write.

        `True` when Every-Line Composer is used, `False` for Single-Line.
        """
        if "every_line_composer" in self.__dict__:
            result: bool | None = self.__dict__["every_line_composer"]
            return result
        if self._para_style is not None:
            # COS key "15" stores single-line composer flag (inverted)
            val = self._para_style.get("15")
            if val is not None:
                return not val
        return None

    @every_line_composer.setter
    def every_line_composer(self, value: bool | None) -> None:
        self.__dict__.pop("every_line_composer", None)
        if self._para_style is not None and value is not None:
            self._para_style["15"] = not value
            self._propagate_cos()
        else:
            self.__dict__["every_line_composer"] = value

    @property
    def composer_engine(self) -> ComposerEngine | None:
        """The Text layer's composer engine type. Read-only."""
        if self._cos_data is not None:
            engine_info = self._cos_data.get("1", {}).get("4")
            if isinstance(engine_info, dict):
                engine_name = engine_info.get("3")
                if engine_name == "DVA":
                    return ComposerEngine.LATIN_CJK_ENGINE
                if engine_name == "Universal":
                    return ComposerEngine.UNIVERSAL_TYPE_ENGINE
        return None

    @property
    def box_text(self) -> bool | None:
        """`True` if this is a box (paragraph) text layer. Read-only."""
        if self._doc is not None:
            frame_data = self._doc.get("1", {})
            # Box text has a "3" key with the bounding box coordinates
            return "3" in frame_data
        return None

    @property
    def point_text(self) -> bool | None:
        """`True` if this is a point text layer. Read-only."""
        bt = self.box_text
        if bt is None:
            return None
        return not bt

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
        if self._cos_data is not None and self._btdk_body is not None:
            self._btdk_body.data = serialize(self._cos_data)
