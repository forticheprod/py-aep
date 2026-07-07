"""Text document enumerations for After Effects.

These enums match the values used in After Effects ExtendScript.
"""

from __future__ import annotations

from enum import IntEnum


class AutoKernType(IntEnum):
    """Auto kerning type option for text characters.

    See: https://ae-scripting.docsforadobe.dev/text/textdocument/#textdocumentautokerntype
    """

    NO_AUTO_KERN = 11412
    METRIC_KERN = 11413
    OPTICAL_KERN = 11414

    @classmethod
    def from_binary(cls, value: int) -> AutoKernType:
        """Convert COS value (0-2) to AutoKernType."""
        return cls(value + 11412)

    def to_binary(self) -> int:
        """Convert AutoKernType to COS value (0-2)."""
        return int(self) - 11412


class BaselineDirection(IntEnum):
    """Baseline direction option for text characters.

    This is significant for Japanese language in vertical texts.
    `BASELINE_VERTICAL_CROSS_STREAM` is also known as Tate-Chu-Yoko.

    See: https://ae-scripting.docsforadobe.dev/text/textdocument/#textdocumentbaselinedirection
    """

    BASELINE_WITH_STREAM = 11612
    BASELINE_VERTICAL_ROTATED = 11613
    BASELINE_VERTICAL_CROSS_STREAM = 11614

    @classmethod
    def from_binary(cls, value: int) -> BaselineDirection:
        """Convert COS value (1-3) to BaselineDirection.

        COS stores this 1-based (`member value - 11611`).
        """
        return cls(value + 11611)

    def to_binary(self) -> int:
        """Convert BaselineDirection to COS value (1-3)."""
        return int(self) - 11611


class BoxAutoFitPolicy(IntEnum):
    """Box auto fit policy for paragraph text boxes.

    See: https://ae-scripting.docsforadobe.dev/text/textdocument/#textdocumentboxautofitpolicy
    """

    NONE = 13412
    HEIGHT_CURSOR = 13413
    HEIGHT_PRECISE_BOUNDS = 13414
    HEIGHT_BASELINE = 13415

    @classmethod
    def from_binary(cls, value: int) -> BoxAutoFitPolicy:
        """Convert COS value (0-3) to BoxAutoFitPolicy."""
        try:
            return cls(value + 13412)
        except ValueError:
            return cls.NONE

    def to_binary(self) -> int:
        """Convert BoxAutoFitPolicy to COS value (0-3)."""
        return int(self) - 13412


class BoxFirstBaselineAlignment(IntEnum):
    """First baseline alignment for paragraph text boxes.

    See: https://ae-scripting.docsforadobe.dev/text/textdocument/#textdocumentboxfirstbaselinealignment
    """

    MINIMUM_VALUE_ROMAN = 13012
    ASCENT = 13013
    CAP_HEIGHT = 13014
    LEADING = 13015
    X_HEIGHT = 13016
    EM_BOX = 13017
    LEGACY_METRIC = 13018
    MINIMUM_VALUE_ASIAN = 13019
    TYPO_ASCENT = 13020

    @classmethod
    def from_binary(cls, value: int) -> BoxFirstBaselineAlignment:
        """Convert COS value (0-8) to BoxFirstBaselineAlignment."""
        try:
            return cls(value + 13012)
        except ValueError:
            return cls.ASCENT

    def to_binary(self) -> int:
        """Convert BoxFirstBaselineAlignment to COS value (0-8)."""
        return int(self) - 13012


class BoxVerticalAlignment(IntEnum):
    """Vertical alignment for paragraph text boxes.

    See: https://ae-scripting.docsforadobe.dev/text/textdocument/#textdocumentboxverticalalignment
    """

    TOP = 12812
    CENTER = 12813
    BOTTOM = 12814
    JUSTIFY = 12815

    @classmethod
    def from_binary(cls, value: int) -> BoxVerticalAlignment:
        """Convert COS value (0-3) to BoxVerticalAlignment."""
        try:
            return cls(value + 12812)
        except ValueError:
            return cls.TOP

    def to_binary(self) -> int:
        """Convert BoxVerticalAlignment to COS value (0-3)."""
        return int(self) - 12812


class ComposerEngine(IntEnum):
    """Text composer engine type.

    See: https://ae-scripting.docsforadobe.dev/text/textdocument/#textdocumentcomposerengine
    """

    LATIN_CJK_ENGINE = 10413
    UNIVERSAL_TYPE_ENGINE = 10414


class DigitSet(IntEnum):
    """Digit set option for text characters.

    See: https://ae-scripting.docsforadobe.dev/text/textdocument/#textdocumentdigitset
    """

    DEFAULT_DIGITS = 12012
    ARABIC_DIGITS = 12013
    HINDI_DIGITS = 12014
    FARSI_DIGITS = 12015
    ARABIC_DIGITS_RTL = 12016

    @classmethod
    def from_binary(cls, value: int) -> DigitSet:
        """Convert COS value (0-4) to DigitSet."""
        return cls(value + 12012)

    def to_binary(self) -> int:
        """Convert DigitSet to COS value (0-4)."""
        return int(self) - 12012


class FontBaselineOption(IntEnum):
    """Font baseline option for superscript and subscript.

    See: https://ae-scripting.docsforadobe.dev/text/textdocument/#textdocumentfontbaselineoption
    """

    FONT_NORMAL_BASELINE = 11212
    FONT_FAUXED_SUPERSCRIPT = 11213
    FONT_FAUXED_SUBSCRIPT = 11214

    @classmethod
    def from_binary(cls, value: int) -> FontBaselineOption:
        """Convert COS value (0-2) to FontBaselineOption."""
        return cls(value + 11212)

    def to_binary(self) -> int:
        """Convert FontBaselineOption to COS value (0-2)."""
        return int(self) - 11212


class FontCapsOption(IntEnum):
    """Font caps option for text characters.

    See: https://ae-scripting.docsforadobe.dev/text/textdocument/#textdocumentfontcapsoption
    """

    FONT_NORMAL_CAPS = 11012
    FONT_SMALL_CAPS = 11013
    FONT_ALL_CAPS = 11014
    FONT_ALL_SMALL_CAPS = 11015

    @classmethod
    def from_binary(cls, value: int) -> FontCapsOption:
        """Convert COS value (0-3) to FontCapsOption."""
        return cls(value + 11012)

    def to_binary(self) -> int:
        """Convert FontCapsOption to COS value (0-3)."""
        return int(self) - 11012


class LeadingType(IntEnum):
    """Paragraph leading type.

    See: https://ae-scripting.docsforadobe.dev/text/textdocument/#textdocumentleadingtype
    """

    ROMAN_LEADING_TYPE = 10812
    JAPANESE_LEADING_TYPE = 10813

    @classmethod
    def from_binary(cls, value: int) -> LeadingType:
        """Convert COS value (0-1) to LeadingType."""
        return cls(value + 10812)

    def to_binary(self) -> int:
        """Convert LeadingType to COS value (0-1)."""
        return int(self) - 10812


class LineJoinType(IntEnum):
    """Line join type for text stroke.

    See: https://ae-scripting.docsforadobe.dev/text/textdocument/#textdocumentlinejointype
    """

    LINE_JOIN_MITER = 11812
    LINE_JOIN_ROUND = 11813
    LINE_JOIN_BEVEL = 11814

    @classmethod
    def from_binary(cls, value: int) -> LineJoinType:
        """Convert COS value (0-2) to LineJoinType."""
        return cls(value + 11812)

    def to_binary(self) -> int:
        """Convert LineJoinType to COS value (0-2)."""
        return int(self) - 11812


class LineOrientation(IntEnum):
    """Line orientation for text layers.

    See: https://ae-scripting.docsforadobe.dev/text/textdocument/#textdocumentlineorientation
    """

    HORIZONTAL = 13212
    VERTICAL_RIGHT_TO_LEFT = 13213
    VERTICAL_LEFT_TO_RIGHT = 13214

    @classmethod
    def from_binary(cls, value: int) -> LineOrientation:
        """Convert COS value to LineOrientation.

        COS 1/2 are swapped relative to the enum's numeric order
        (1 = left-to-right, 2 = right-to-left).
        """
        return _LINE_ORIENTATION_BINARY_MAP.get(value, cls.HORIZONTAL)

    def to_binary(self) -> int:
        """Convert LineOrientation to COS value."""
        return _LINE_ORIENTATION_TO_BINARY[self]


_LINE_ORIENTATION_BINARY_MAP: dict[int, LineOrientation] = {
    0: LineOrientation.HORIZONTAL,
    1: LineOrientation.VERTICAL_LEFT_TO_RIGHT,
    2: LineOrientation.VERTICAL_RIGHT_TO_LEFT,
}
_LINE_ORIENTATION_TO_BINARY: dict[LineOrientation, int] = {
    v: k for k, v in _LINE_ORIENTATION_BINARY_MAP.items()
}


class ParagraphDirection(IntEnum):
    """Paragraph direction for text layers.

    See: https://ae-scripting.docsforadobe.dev/text/textdocument/#textdocumentdirection
    """

    DIRECTION_LEFT_TO_RIGHT = 10212
    DIRECTION_RIGHT_TO_LEFT = 10213

    @classmethod
    def from_binary(cls, value: int) -> ParagraphDirection:
        """Convert COS value (0-1) to ParagraphDirection."""
        return cls(value + 10212)

    def to_binary(self) -> int:
        """Convert ParagraphDirection to COS value (0-1)."""
        return int(self) - 10212


class ParagraphJustification(IntEnum):
    """Paragraph justification for text layers.

    See: https://ae-scripting.docsforadobe.dev/text/textdocument/#textdocumentjustification
    """

    MULTIPLE_JUSTIFICATIONS = 7412
    LEFT_JUSTIFY = 7413
    RIGHT_JUSTIFY = 7414
    CENTER_JUSTIFY = 7415
    FULL_JUSTIFY_LASTLINE_LEFT = 7416
    FULL_JUSTIFY_LASTLINE_RIGHT = 7417
    FULL_JUSTIFY_LASTLINE_CENTER = 7418
    FULL_JUSTIFY_LASTLINE_FULL = 7419

    @classmethod
    def from_binary(cls, value: int) -> ParagraphJustification:
        """Convert COS value (0-6) to ParagraphJustification.

        COS 0 is `LEFT_JUSTIFY`; the `MULTIPLE_JUSTIFICATIONS` sentinel
        is never stored, so the offset is the member value minus 7413.
        """
        return cls(value + 7413)

    def to_binary(self) -> int:
        """Convert ParagraphJustification to COS value (0-6)."""
        return int(self) - 7413


class VariableFontSpacing(IntEnum):
    """Variable Font Spacing behavior for a text layer.

    The value of the `ADBE Text Variable Font Spacing` property in the
    text layer's More Options group. Controls how After Effects handles
    character-spacing compensation when animating variable-font axes
    changes character widths.

    Note:
        This functionality was added in After Effects 26.0. The enum
        values match the property's stored value directly.
    """

    ADAPTIVE = 1
    PER_CHARACTER = 2
    DEFAULT = 3
