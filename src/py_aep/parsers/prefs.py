"""Generic reader for After Effects preference text files.

AE persists its preferences as INI-like text files under the user's
AppData directory (e.g.
`~/AppData/Roaming/Adobe/After Effects/26.0/`), one file per
[PREFType][] category:

- `Adobe After Effects <ver> Prefs.txt` - machine specific
- `... Prefs-indep-general.txt` - machine independent
- `... Prefs-indep-render.txt` - render settings templates
- `... Prefs-indep-output.txt` - output module templates
- `... Prefs-indep-composition.txt` - new-composition presets
- `... Prefs-text.txt` - text style defaults
- `... Prefs-paint.txt` - paint tool defaults

File format:

- section headers: `["Section Name"]`
- keys: one tab of indent, `"Key Name" = value`
- values: AE's mixed hex/ASCII encoding - quoted ASCII runs with bare
  hex bytes outside the quotes (e.g. `"HD  "E280A2"  1920x1080"`), or
  raw hex bytes (`01`), or quoted decimal strings (`"30.000000"`)
- long values continue on following lines (double-tab indent, trailing
  backslash); backslashes sit outside quoted runs and decode to nothing

This module is read-only: py_aep never writes AE preference files.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..enums.general import PREFType

if TYPE_CHECKING:
    from pathlib import Path

# One glob per preference file category; file names embed the AE version.
_PREF_FILE_GLOBS: dict[PREFType, str] = {
    PREFType.PREF_Type_MACHINE_SPECIFIC: "* Prefs.txt",
    PREFType.PREF_Type_MACHINE_INDEPENDENT: "*Prefs-indep-general.txt",
    PREFType.PREF_Type_MACHINE_INDEPENDENT_RENDER: "*Prefs-indep-render.txt",
    PREFType.PREF_Type_MACHINE_INDEPENDENT_OUTPUT: "*Prefs-indep-output.txt",
    PREFType.PREF_Type_MACHINE_INDEPENDENT_COMPOSITION: (
        "*Prefs-indep-composition.txt"
    ),
    PREFType.PREF_Type_MACHINE_SPECIFIC_TEXT: "*Prefs-text.txt",
    PREFType.PREF_Type_MACHINE_SPECIFIC_PAINT: "*Prefs-paint.txt",
}

_SECTION_RE = re.compile(r'^\["(.*)"\]')
_KEY_RE = re.compile(r'^\t"(.+?)" = (.*)$')


def find_prefs_file(prefs_dir: Path, pref_type: PREFType) -> Path | None:
    """Locate the preference file for `pref_type` under `prefs_dir`."""
    matches = sorted(prefs_dir.glob(_PREF_FILE_GLOBS[pref_type]))
    return matches[0] if matches else None


def collapse_continuation_lines(text: str) -> list[str]:
    """Collapse AE preference continuation lines into logical lines.

    Key lines start with a single tab followed by a quote; continuation
    lines are indented further (or start with a tab but no quote) and
    are appended to the previous logical line.
    """
    lines = text.split("\n")
    result: list[str] = []
    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            continue
        # Continuation lines start with tab and contain hex data
        if result and stripped.startswith("\t") and not stripped.startswith('\t"'):
            result[-1] += stripped.strip()
        else:
            result.append(stripped)
    return result


def parse_hex_value(value: str) -> bytes:
    """Decode a mixed hex/ASCII value from AE preferences.

    The value contains hex digits and quoted ASCII strings like:
    `00D00BEE..."Best Settings"0000...`
    """
    raw = bytearray()
    i = 0
    while i < len(value):
        if value[i] == '"':
            end = value.index('"', i + 1)
            raw.extend(value[i + 1 : end].encode("ascii"))
            i = end + 1
        elif value[i] in "0123456789ABCDEFabcdef":
            raw.append(int(value[i : i + 2], 16))
            i += 2
        else:
            i += 1
    return bytes(raw)


def parse_number_text(text: str) -> int | float:
    """Parse decimal text into an int when integral, else a float."""
    stripped = text.strip()
    try:
        return int(stripped)
    except ValueError:
        return float(stripped)


def decode_pref_string(raw: str) -> str:
    """Decode a preference value as text (hex escapes become UTF-8)."""
    return parse_hex_value(raw).decode("utf-8", errors="replace")


def decode_pref_number(raw: str) -> int | float:
    """Decode a preference value as a number.

    Quoted values parse as decimal text (`"30.000000"` -> 30.0,
    `"999"` -> 999); unquoted values are raw hex bytes interpreted as a
    big-endian unsigned integer (`01` -> 1).

    Raises:
        ValueError: If a quoted value is not numeric text.
    """
    if '"' in raw:
        return parse_number_text(decode_pref_string(raw))
    data = parse_hex_value(raw)
    return int.from_bytes(data, "big")


def decode_pref_bool(raw: str) -> bool:
    """Decode a preference value as a boolean (`01`, `"1"`, `00`, `"0"`)."""
    return decode_pref_number(raw) != 0


class PrefsFile:
    """Parsed section/key view of one AE preference text file.

    Values are kept in their raw text form; decode on demand with
    `decode_pref_string` / `decode_pref_number` / `decode_pref_bool` or
    `parse_hex_value` for binary blobs.
    """

    def __init__(self, sections: dict[str, dict[str, str]]) -> None:
        self._sections = sections

    @classmethod
    def from_text(cls, text: str) -> PrefsFile:
        """Parse preference file text into a `PrefsFile`."""
        sections: dict[str, dict[str, str]] = {}
        current: dict[str, str] | None = None
        for line in collapse_continuation_lines(text):
            section_match = _SECTION_RE.match(line)
            if section_match:
                current = sections.setdefault(section_match.group(1), {})
                continue
            key_match = _KEY_RE.match(line)
            if key_match and current is not None:
                current[key_match.group(1)] = key_match.group(2)
        return cls(sections)

    @classmethod
    def from_path(cls, path: Path) -> PrefsFile:
        """Read and parse a preference file from disk."""
        return cls.from_text(path.read_text(encoding="utf-8", errors="replace"))

    def get_raw(self, section: str, key: str) -> str | None:
        """Return the raw text value for `section`/`key`, or None."""
        return self._sections.get(section, {}).get(key)

    def section(self, name: str) -> dict[str, str]:
        """Return a copy of the raw key -> value mapping for a section
        (empty if the section is absent)."""
        return dict(self._sections.get(name, {}))
