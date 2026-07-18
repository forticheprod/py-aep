"""After Effects preferences, mirroring the ExtendScript `app.preferences`."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from ..enums.general import PREFType
from ..enums.text_document import AutoKernType, ParagraphJustification
from ..parsers.comp_presets import CompPreset, parse_comp_presets
from ..parsers.prefs import (
    PrefsFile,
    decode_pref_bool,
    decode_pref_number,
    decode_pref_string,
    find_prefs_file,
    parse_hex_value,
    parse_number_text,
)
from .validators import validate_bool, validate_enum, validate_name, validate_number

if TYPE_CHECKING:
    import os
    from typing import Any, Callable

    from .text.text_document import TextDocument

_validate_pref_type = validate_enum(PREFType)

# Tombstone marking a key removed by delete_pref (masks the file value).
_DELETED = object()

_LABEL_INDICES_SECTION = "Label Preference Indices Section 5"


def label_index(preferences: Preferences, key: str, default: int) -> int:
    """Resolve a default label color index from the label preferences.

    Args:
        preferences: The project's [Preferences][].
        key: Key in the `Label Preference Indices Section 5` section
            (e.g. `Comp Label Index 2`).
        default: AE's factory value, used when no preferences directory
            was provided or the key is absent.
    """
    value = preferences.get_pref_as_number(
        _LABEL_INDICES_SECTION,
        key,
        PREFType.PREF_Type_MACHINE_INDEPENDENT,
        default=default,
    )
    return int(value)


def default_sequence_fps(preferences: Preferences) -> float:
    """Resolve AE's "Import Options Default Sequence FPS" preference.

    The frame rate AE assigns to imported image sequences (formats with
    no native rate). AE's factory value is 30.
    """
    value = preferences.get_pref_as_number(
        "Import Options Preference Section",
        "Import Options Default Sequence FPS",
        PREFType.PREF_Type_MACHINE_INDEPENDENT,
        default=30.0,
    )
    return float(value)


_CHOOSE_LAYER_SECTION = "Choose Layer Dialog"

# AE's PSD/PSB import-dialog popup indices, probed in AE 2026 by toggling
# each dropdown and re-reading the machine-specific prefs. These are dialog
# positions, NOT the `sspc` c9 byte enum - footage merge/ignore is reversed
# there ({merge:0, ignore:1} here vs the c9 {ignore:0, merge:1}). AE's own
# importFile follows the last sticky choice, so py_aep uses them to fill an
# unset ImportOptions field.
_PSD_COMP_LAYER_STYLES: dict[int, str] = {0: "editable", 1: "merge"}
_PSD_FOOTAGE_LAYER_STYLES: dict[int, str] = {0: "merge", 1: "ignore"}
_PSD_FOOTAGE_DIMENSIONS: dict[int, str] = {0: "layer", 1: "document"}


def _choose_layer_pref(
    preferences: Preferences, key: str, mapping: dict[int, str]
) -> str | None:
    """Resolve a `Choose Layer Dialog` popup index to its string value, or
    `None` when the preference is unset (or holds an unknown index)."""
    if not preferences.have_pref(
        _CHOOSE_LAYER_SECTION, key, PREFType.PREF_Type_MACHINE_SPECIFIC
    ):
        return None
    idx = int(
        preferences.get_pref_as_number(
            _CHOOSE_LAYER_SECTION, key, PREFType.PREF_Type_MACHINE_SPECIFIC
        )
    )
    return mapping.get(idx)


def psd_comp_layer_styles(preferences: Preferences) -> str | None:
    """The sticky Layer Options choice for a PSD/PSB COMP import (`"editable"`
    or `"merge"`), or `None` when the preference is unset.

    Mirrors the "PSD Comp Layer Styles Option v2" import-dialog preference
    that AE's own `importFile` follows.
    """
    return _choose_layer_pref(
        preferences, "PSD Comp Layer Styles Option v2", _PSD_COMP_LAYER_STYLES
    )


def psd_footage_layer_styles(preferences: Preferences) -> str | None:
    """The sticky Layer Options choice for a single-layer PSD/PSB FOOTAGE
    import (`"merge"` or `"ignore"`), or `None` when the preference is unset.

    Mirrors the "PSD Footage Layer Styles Option" import-dialog preference.
    """
    return _choose_layer_pref(
        preferences, "PSD Footage Layer Styles Option", _PSD_FOOTAGE_LAYER_STYLES
    )


def psd_footage_dimensions(preferences: Preferences) -> str | None:
    """The sticky Footage Dimensions choice for a single-layer PSD/PSB FOOTAGE
    import (`"document"` or `"layer"`), or `None` when the preference is unset.

    Mirrors the "PSD Dimensions Popup" import-dialog preference.
    """
    return _choose_layer_pref(
        preferences, "PSD Dimensions Popup", _PSD_FOOTAGE_DIMENSIONS
    )


_TEXT_STYLE_SECTION = "Text Style Sheet"
_PARA_SHEET_SECTION = "Text Paragraph Sheet"
_TXT = PREFType.PREF_Type_MACHINE_SPECIFIC_TEXT

# The horizontal/vertical scale preferences are percentages, while the
# document stores (and ExtendScript reports) a fraction.
_SCALE_PERCENT = 100.0

# AE's factory Character/Paragraph panel values, used when the preference
# file is unavailable (a project parsed without an `ae_preferences_dir`).
_FACTORY_CHAR_STYLE: dict[str, Any] = {
    "font": "MyriadPro-Regular",
    "font_size": 36.0,
    "faux_bold": False,
    "faux_italic": False,
    "apply_fill": True,
    "apply_stroke": False,
    # The full-precision value AE stores; the preference file mirrors it
    # rounded to six decimals, so a prefs-backed reset lands ~1e-7 away.
    "fill_color": [0.92156994342804, 0.92156994342804, 0.92156994342804],
    "stroke_color": [0.0, 0.0, 0.0],
    "stroke_width": 1.0,
    "stroke_over_fill": True,
    "tracking": 0.0,
    "tsume": 0.0,
    "horizontal_scale": 1.0,
    "vertical_scale": 1.0,
    "baseline_shift": 0.0,
    "auto_leading": True,
    "auto_kern_type": AutoKernType.METRIC_KERN,
}

# AE names the Character panel's kerning modes in prose.
_AUTO_KERN_BY_PREF: dict[str, AutoKernType] = {
    "No Auto Kerning": AutoKernType.NO_AUTO_KERN,
    "Metric Auto Kerning": AutoKernType.METRIC_KERN,
    "Optical Auto Kerning": AutoKernType.OPTICAL_KERN,
}
_FACTORY_PARA_STYLE: dict[str, Any] = {
    "justification": ParagraphJustification.LEFT_JUSTIFY,
    "first_line_indent": 0.0,
    "start_indent": 0.0,
    "end_indent": 0.0,
    "space_before": 0.0,
    "space_after": 0.0,
    "hanging_roman": False,
    "every_line_composer": False,
}

# AE writes the horizontal half of "Justification" before a `|`.
_JUSTIFICATION_BY_PREF: dict[str, ParagraphJustification] = {
    "Left": ParagraphJustification.LEFT_JUSTIFY,
    "Center": ParagraphJustification.CENTER_JUSTIFY,
    "Right": ParagraphJustification.RIGHT_JUSTIFY,
}


def _sheet_readers(
    preferences: Preferences, section: str
) -> tuple[Callable[[str, float], float], Callable[[str, bool], bool]]:
    """Build `(number, flag)` readers over one machine-specific text sheet."""

    def number(key: str, fallback: float) -> float:
        value = preferences.get_pref_as_number(section, key, _TXT, default=fallback)
        return float(value)

    def flag(key: str, fallback: bool) -> bool:
        return preferences.get_pref_as_bool(section, key, _TXT, default=fallback)

    return number, flag


def default_character_style(preferences: Preferences) -> dict[str, Any]:
    """AE's Character-panel defaults - the `["Text Style Sheet"]` section of
    the machine-specific text preferences.

    This is the style `TextDocument.reset_char_style()` restores and the
    style `addText` gives a new layer. Keys map to `TextDocument`
    attributes. Missing preferences fall back to AE's factory values.
    """
    number, flag = _sheet_readers(preferences, _TEXT_STYLE_SECTION)
    factory = _FACTORY_CHAR_STYLE
    fill = [
        number("Fill Red", factory["fill_color"][0]),
        number("Fill Green", factory["fill_color"][1]),
        number("Fill Blue", factory["fill_color"][2]),
    ]
    stroke = [
        number("Stroke Red", factory["stroke_color"][0]),
        number("Stroke Green", factory["stroke_color"][1]),
        number("Stroke Blue", factory["stroke_color"][2]),
    ]
    return {
        "font": preferences.get_pref_as_string(
            _TEXT_STYLE_SECTION,
            "Font PostScript Name",
            PREFType.PREF_Type_MACHINE_SPECIFIC_TEXT,
            default=cast("str", factory["font"]),
        ),
        "font_size": number("Size", factory["font_size"]),
        "faux_bold": flag("Synthetic Bold", factory["faux_bold"]),
        "faux_italic": flag("Synthetic Italic", factory["faux_italic"]),
        "apply_fill": flag("Render Fill", factory["apply_fill"]),
        "apply_stroke": flag("Render Stroke", factory["apply_stroke"]),
        "fill_color": fill,
        "stroke_color": stroke,
        "stroke_width": number("Stroke Width", factory["stroke_width"]),
        "stroke_over_fill": flag("Stroke Over Fill", factory["stroke_over_fill"]),
        "tracking": number("Tracking", factory["tracking"]),
        "tsume": number("Tsume", factory["tsume"]),
        "horizontal_scale": number(
            "Horizontal Scale", factory["horizontal_scale"] * _SCALE_PERCENT
        )
        / _SCALE_PERCENT,
        "vertical_scale": number(
            "Vertical Scale", factory["vertical_scale"] * _SCALE_PERCENT
        )
        / _SCALE_PERCENT,
        "baseline_shift": number("Baseline Shift", factory["baseline_shift"]),
        "auto_leading": flag("Auto Leading", factory["auto_leading"]),
        "auto_kern_type": _AUTO_KERN_BY_PREF.get(
            preferences.get_pref_as_string(
                _TEXT_STYLE_SECTION,
                "Auto Kerning Type",
                PREFType.PREF_Type_MACHINE_SPECIFIC_TEXT,
                default="Metric Auto Kerning",
            ).strip(),
            cast("AutoKernType", factory["auto_kern_type"]),
        ),
    }


def default_paragraph_style(preferences: Preferences) -> dict[str, Any]:
    """AE's Paragraph-panel defaults - the `["Text Paragraph Sheet"]`
    section of the machine-specific text preferences.

    This is the style `TextDocument.reset_paragraph_style()` restores.
    Note that hyphenation has no entry in this sheet, which is why After
    Effects leaves `auto_hyphenate` untouched on a reset.
    """
    number, flag = _sheet_readers(preferences, _PARA_SHEET_SECTION)
    factory = _FACTORY_PARA_STYLE
    raw_justification = preferences.get_pref_as_string(
        _PARA_SHEET_SECTION,
        "Justification",
        PREFType.PREF_Type_MACHINE_SPECIFIC_TEXT,
        default="Left",
    )
    justification = _JUSTIFICATION_BY_PREF.get(
        raw_justification.split("|")[0].strip(),
        cast("ParagraphJustification", factory["justification"]),
    )
    return {
        "justification": justification,
        "first_line_indent": number("First Line Indent", factory["first_line_indent"]),
        "start_indent": number("Start Indent", factory["start_indent"]),
        "end_indent": number("End Indent", factory["end_indent"]),
        "space_before": number("Space Before", factory["space_before"]),
        "space_after": number("Space After", factory["space_after"]),
        "hanging_roman": flag("Roman Hanging Punctuation", factory["hanging_roman"]),
        "every_line_composer": flag(
            "Every-line Composer", factory["every_line_composer"]
        ),
    }


def _default_out_point(preferences: Preferences, key: str) -> float | None:
    """Parse a `"value/scale"` default-out-point preference into seconds.

    Returns None for the `0/0` factory sentinel (or a missing/malformed
    value), meaning "composition duration". Semantics probed in AE 2026:
    `75/25` gives new layers a 3-second span.
    """
    raw = preferences.get_pref_as_string(
        "Main Pref Section v2",
        key,
        PREFType.PREF_Type_MACHINE_INDEPENDENT,
        default="0/0",
    )
    parts = raw.split("/")
    if len(parts) != 2:
        return None
    try:
        value, scale = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    if scale == 0 or value <= 0:
        return None
    return value / scale


def apply_text_style_prefs(document: TextDocument, preferences: Preferences) -> None:
    """Apply the AE "Text Style Sheet" preferences to a new text document.

    AE reads the machine-specific text style sheet once at startup and
    applies its character-level fields to every scripted `addText` layer;
    the paragraph sheet is NOT applied (scripted text is always
    left-justified). Probed in AE 2026 via disk-edited preferences.

    Only values that differ from the document's current state are
    written, so a factory style sheet leaves the baked template bytes
    untouched. The font is taken from "Font PostScript Name" as written
    by AE (AE itself validates the family/style/technology tuple and
    falls back to Myriad Pro when it is incoherent; a sheet written by
    AE is coherent by construction).
    """

    def number(key: str) -> int | float | None:
        if not preferences.have_pref(_TEXT_STYLE_SECTION, key, _TXT):
            return None
        return preferences.get_pref_as_number(_TEXT_STYLE_SECTION, key, _TXT)

    def differs(current: float | None, new: float) -> bool:
        # Absent COS keys read as None and mean the field's zero default.
        # AE writes the sheet with 6 decimals, so sub-1e-6 deltas are
        # representation rounding (e.g. 235/255 vs "0.921569"), not edits.
        return abs((current if current is not None else 0.0) - new) > 1e-6

    font = (
        preferences.get_pref_as_string(
            _TEXT_STYLE_SECTION, "Font PostScript Name", _TXT
        )
        if preferences.have_pref(_TEXT_STYLE_SECTION, "Font PostScript Name", _TXT)
        else None
    )
    if font and document.font != font:
        document.font = font

    size = number("Size")
    if size is not None and size > 0 and differs(document.font_size, size):
        document.font_size = size

    fill = [number("Fill Red"), number("Fill Green"), number("Fill Blue")]
    if None not in fill:
        current_fill = document.fill_color or [0.0, 0.0, 0.0]
        if any(differs(c, float(n)) for c, n in zip(current_fill, fill)):  # type: ignore[arg-type]
            document.fill_color = [float(n) for n in fill]  # type: ignore[arg-type]

    tracking = number("Tracking")
    if tracking is not None and differs(document.tracking, tracking):
        # tracking is an integer field, unlike the float Size/Baseline Shift.
        document.tracking = round(tracking)

    baseline_shift = number("Baseline Shift")
    if baseline_shift is not None and differs(document.baseline_shift, baseline_shift):
        document.baseline_shift = baseline_shift

    if preferences.have_pref(_TEXT_STYLE_SECTION, "Render Fill", _TXT):
        apply_fill = preferences.get_pref_as_bool(
            _TEXT_STYLE_SECTION, "Render Fill", _TXT
        )
        if bool(document.apply_fill) != apply_fill:
            document.apply_fill = apply_fill

    if preferences.have_pref(_TEXT_STYLE_SECTION, "Render Stroke", _TXT):
        apply_stroke = preferences.get_pref_as_bool(
            _TEXT_STYLE_SECTION, "Render Stroke", _TXT
        )
        if bool(document.apply_stroke) != apply_stroke:
            document.apply_stroke = apply_stroke
        # Stroke width/color were probed only with the stroke rendered;
        # leave them untouched when the sheet keeps the stroke off so the
        # factory sheet stays byte-identical to the baked template.
        if apply_stroke:
            stroke_width = number("Stroke Width")
            if stroke_width is not None and differs(
                document.stroke_width, stroke_width
            ):
                document.stroke_width = stroke_width
            stroke = [
                number("Stroke Red"),
                number("Stroke Green"),
                number("Stroke Blue"),
            ]
            if None not in stroke:
                current = document.stroke_color or [0.0, 0.0, 0.0]
                if any(differs(c, float(n)) for c, n in zip(current, stroke)):  # type: ignore[arg-type]
                    document.stroke_color = [float(n) for n in stroke]  # type: ignore[arg-type]


def default_still_out_point(preferences: Preferences) -> float | None:
    """Default span of new still-footage layers, in seconds.

    None means "composition duration" (the factory `0/0` sentinel).
    """
    return _default_out_point(preferences, "Pref_DEFAULT_STILL_OUT_POINT v2")


def default_synthetic_out_point(preferences: Preferences) -> float | None:
    """Default span of new sourceless layers (solid, null, text, shape,
    camera, light), in seconds.

    None means "composition duration" (the factory `0/0` sentinel).
    """
    return _default_out_point(preferences, "Pref_DEFAULT_SYNTHETIC_OUT_POINT v2")


class Preferences:
    """The Preferences object provides an easy way to manage internal AE
    preferences, such as you find in After Effects' Preferences menu. It
    is accessed through the `app.preferences` attribute.

    Preferences are identified by section and key within the file, and
    each key name is associated with a value.

    Differences from ExtendScript:

    - The preference `.txt` files are read-only: `set_pref_as_*` writes
      to an in-memory override layer that takes precedence over the
      files, and there is no `save_to_disk()`. Overrides last for the
      lifetime of this object and never modify the files.
    - `getPrefAsLong` / `getPrefAsFloat` are merged into a single
      [get_pref_as_number][] (Python does not need the distinction).
    - Getters accept an optional `default` returned when the key is
      absent instead of raising `KeyError`.

    See: https://ae-scripting.docsforadobe.dev/other/preferences/

    Example:
        ```python
        import py_aep
        from py_aep.enums import PREFType

        app = py_aep.parse("project.aep", ae_preferences_dir="...")
        fps = app.preferences.get_pref_as_number(
            "Import Options Preference Section",
            "Import Options Default Sequence FPS",
            PREFType.PREF_Type_MACHINE_INDEPENDENT,
        )
        ```
    """

    def __init__(self, prefs_dir: str | os.PathLike[str] | None = None) -> None:
        self._prefs_dir = Path(prefs_dir) if prefs_dir is not None else None
        self._files: dict[PREFType, PrefsFile | None] = {}
        self._overrides: dict[tuple[PREFType, str, str], Any] = {}

    def _file(self, pref_type: PREFType) -> PrefsFile | None:
        """Lazily parse the preference file for `pref_type` (None if absent)."""
        if pref_type not in self._files:
            path = (
                find_prefs_file(self._prefs_dir, pref_type)
                if self._prefs_dir is not None
                else None
            )
            self._files[pref_type] = PrefsFile.from_path(path) if path else None
        return self._files[pref_type]

    def _raw(self, section_name: str, key_name: str, pref_type: PREFType) -> str | None:
        prefs_file = self._file(pref_type)
        if prefs_file is None:
            return None
        return prefs_file.get_raw(section_name, key_name)

    def _resolve(
        self,
        section_name: str,
        key_name: str,
        pref_type: PREFType,
    ) -> tuple[bool, Any, bool]:
        """Return `(found, value, is_override)`.

        `value` is a typed Python value when `is_override` is `True`,
        otherwise the raw pref-file text (AE's mixed hex/ASCII encoding).
        """
        validate_name(section_name)
        validate_name(key_name)
        _validate_pref_type(pref_type)
        key = (PREFType(pref_type), section_name, key_name)
        if key in self._overrides:
            value = self._overrides[key]
            if value is _DELETED:
                return False, None, False
            return True, value, True
        raw = self._raw(section_name, key_name, key[0])
        if raw is None:
            return False, None, False
        return True, raw, False

    def _missing(
        self, section_name: str, key_name: str, pref_type: PREFType
    ) -> KeyError:
        return KeyError(
            f"no preference {key_name!r} in section {section_name!r} "
            f"({PREFType(pref_type).name})"
        )

    def get_pref_as_number(
        self,
        section_name: str,
        key_name: str,
        pref_type: PREFType = PREFType.PREF_Type_MACHINE_SPECIFIC,
        *,
        default: int | float | None = None,
    ) -> int | float:
        """The value of the given preference as a number.

        Merges ExtendScript's `getPrefAsLong` and `getPrefAsFloat`:
        integral values return `int`, others `float`.

        Args:
            section_name: The name of a preferences section.
            key_name: The key name of the preference.
            pref_type: The preference file the preference is read from.
            default: Returned when the key is absent (otherwise a missing
                key raises `KeyError`).
        """
        found, value, is_override = self._resolve(section_name, key_name, pref_type)
        if not found:
            if default is not None:
                return default
            raise self._missing(section_name, key_name, pref_type)
        if not is_override:
            return decode_pref_number(value)
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return value
        return parse_number_text(value)

    def get_pref_as_bool(
        self,
        section_name: str,
        key_name: str,
        pref_type: PREFType = PREFType.PREF_Type_MACHINE_SPECIFIC,
        *,
        default: bool | None = None,
    ) -> bool:
        """The value of the given preference as a boolean.

        Args:
            section_name: The name of a preferences section.
            key_name: The key name of the preference.
            pref_type: The preference file the preference is read from.
            default: Returned when the key is absent (otherwise a missing
                key raises `KeyError`).
        """
        found, value, is_override = self._resolve(section_name, key_name, pref_type)
        if not found:
            if default is not None:
                return default
            raise self._missing(section_name, key_name, pref_type)
        if not is_override:
            return decode_pref_bool(value)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return parse_number_text(value) != 0

    def get_pref_as_string(
        self,
        section_name: str,
        key_name: str,
        pref_type: PREFType = PREFType.PREF_Type_MACHINE_SPECIFIC,
        *,
        default: str | None = None,
    ) -> str:
        """The value of the given preference as a string.

        Args:
            section_name: The name of a preferences section.
            key_name: The key name of the preference.
            pref_type: The preference file the preference is read from.
            default: Returned when the key is absent (otherwise a missing
                key raises `KeyError`).
        """
        found, value, is_override = self._resolve(section_name, key_name, pref_type)
        if not found:
            if default is not None:
                return default
            raise self._missing(section_name, key_name, pref_type)
        if not is_override:
            return decode_pref_string(value)
        if isinstance(value, bool):
            return str(int(value))
        if isinstance(value, (int, float)):
            return str(value)
        return cast("str", value)

    def set_pref_as_number(
        self,
        section_name: str,
        key_name: str,
        value: int | float,
        pref_type: PREFType = PREFType.PREF_Type_MACHINE_SPECIFIC,
    ) -> None:
        """Override the given preference with a number value.

        The override is in-memory only; the preference file on disk is
        never modified. Merges ExtendScript's `savePrefAsLong` and
        `savePrefAsFloat`.

        Args:
            section_name: The name of a preferences section.
            key_name: The key name of the preference.
            value: The new numeric value.
            pref_type: The preference file the preference belongs to.
        """
        validate_name(section_name)
        validate_name(key_name)
        _validate_pref_type(pref_type)
        if not isinstance(value, (int, float)):
            raise TypeError(f"expected a number, got {type(value).__name__}")
        validate_number(value)  # rejects NaN/inf
        self._overrides[(PREFType(pref_type), section_name, key_name)] = value

    def set_pref_as_bool(
        self,
        section_name: str,
        key_name: str,
        value: bool,
        pref_type: PREFType = PREFType.PREF_Type_MACHINE_SPECIFIC,
    ) -> None:
        """Override the given preference with a boolean value.

        The override is in-memory only; the preference file on disk is
        never modified.

        Args:
            section_name: The name of a preferences section.
            key_name: The key name of the preference.
            value: The new boolean value.
            pref_type: The preference file the preference belongs to.
        """
        validate_name(section_name)
        validate_name(key_name)
        _validate_pref_type(pref_type)
        validate_bool(value)
        self._overrides[(PREFType(pref_type), section_name, key_name)] = value

    def set_pref_as_string(
        self,
        section_name: str,
        key_name: str,
        value: str,
        pref_type: PREFType = PREFType.PREF_Type_MACHINE_SPECIFIC,
    ) -> None:
        """Override the given preference with a string value.

        The override is in-memory only; the preference file on disk is
        never modified.

        Args:
            section_name: The name of a preferences section.
            key_name: The key name of the preference.
            value: The new string value.
            pref_type: The preference file the preference belongs to.
        """
        validate_name(section_name)
        validate_name(key_name)
        _validate_pref_type(pref_type)
        if not isinstance(value, str):
            raise TypeError(f"expected a string, got {type(value).__name__}")
        self._overrides[(PREFType(pref_type), section_name, key_name)] = value

    def have_pref(
        self,
        section_name: str,
        key_name: str,
        pref_type: PREFType = PREFType.PREF_Type_MACHINE_SPECIFIC,
    ) -> bool:
        """Whether the given preference exists (override or file value).

        Args:
            section_name: The name of a preferences section.
            key_name: The key name of the preference.
            pref_type: The preference file the preference is read from.
        """
        found, _value, _is_override = self._resolve(section_name, key_name, pref_type)
        return found

    def delete_pref(
        self,
        section_name: str,
        key_name: str,
        pref_type: PREFType = PREFType.PREF_Type_MACHINE_SPECIFIC,
    ) -> None:
        """Delete the given preference from this object's view.

        The file value (if any) is masked, not removed from disk:
        [have_pref][] returns `False` and getters fall back to their
        `default` afterwards.

        Args:
            section_name: The name of a preferences section.
            key_name: The key name of the preference.
            pref_type: The preference file the preference belongs to.
        """
        validate_name(section_name)
        validate_name(key_name)
        _validate_pref_type(pref_type)
        self._overrides[(PREFType(pref_type), section_name, key_name)] = _DELETED

    def _get_bytes(
        self,
        section_name: str,
        key_name: str,
        pref_type: PREFType,
    ) -> bytes | None:
        """Decoded bytes of a binary preference value, or None when absent.

        File layer only - `set_pref_as_*` overrides are not consulted
        (binary blobs cannot be expressed through the typed setters).
        """
        prefs_file = self._file(pref_type)
        raw = prefs_file.get_raw(section_name, key_name) if prefs_file else None
        return parse_hex_value(raw) if raw is not None else None

    def reload(self) -> None:
        """Reload preferences from disk, discarding in-memory overrides."""
        self._files.clear()
        self._overrides.clear()

    def composition_presets(self) -> list[CompPreset]:
        """The New Composition presets (py_aep extension, not in
        ExtendScript).

        Parsed from the "Composition Presets Section v11" of the
        composition preference file; menu separators are skipped and
        `set_pref_as_*` overrides are not consulted. Empty when no
        preferences directory was provided.
        """
        prefs_file = self._file(PREFType.PREF_Type_MACHINE_INDEPENDENT_COMPOSITION)
        if prefs_file is None:
            return []
        return parse_comp_presets(prefs_file)

    def output_name_template_presets(self) -> dict[str, str]:
        """The "File Name and Location" template presets as a
        `{name: template}` mapping (py_aep extension, not in ExtendScript).

        Parsed from the "Output File Name Template Presets Section v6"
        of the machine-specific preference file (e.g. `Comp Name` ->
        `[compName].[fileExtension]`); `set_pref_as_*` overrides are not
        consulted. Empty when no preferences directory was provided.
        """
        prefs_file = self._file(PREFType.PREF_Type_MACHINE_SPECIFIC)
        if prefs_file is None:
            return {}
        section = prefs_file.section("Output File Name Template Presets Section v6")
        presets: dict[str, str] = {}
        for key in sorted(section):
            # Each entry is `<name> NUL <template> NUL` in AE's mixed
            # hex/ASCII encoding.
            parts = [p for p in parse_hex_value(section[key]).split(b"\x00") if p]
            if len(parts) >= 2:
                name = parts[0].decode("utf-8", errors="replace")
                presets[name] = parts[1].decode("utf-8", errors="replace")
        return presets
