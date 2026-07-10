"""After Effects preferences, mirroring the ExtendScript `app.preferences`."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from ..enums.general import PREFType
from ..parsers.comp_presets import CompPreset, parse_comp_presets
from ..parsers.prefs import (
    PrefsFile,
    decode_pref_bool,
    decode_pref_number,
    decode_pref_string,
    find_prefs_file,
    parse_hex_value,
)
from .validators import validate_bool, validate_enum, validate_name, validate_number

if TYPE_CHECKING:
    import os
    from typing import Any

_validate_pref_type = validate_enum(PREFType)

# Tombstone marking a key removed by delete_pref (masks the file value).
_DELETED = object()


def _text_to_number(text: str) -> int | float:
    """Parse decimal text into an int when integral, else a float."""
    stripped = text.strip()
    try:
        return int(stripped)
    except ValueError:
        return float(stripped)


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
        return _text_to_number(value)

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
        return _text_to_number(value) != 0

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
