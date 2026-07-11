"""Parse render queue templates from After Effects preferences files.

AE stores render settings and output module templates in text-based
preference files under the user's AppData directory:

- `Adobe After Effects <ver> Prefs-indep-render.txt` - render settings
- `Adobe After Effects <ver> Prefs-indep-output.txt` - output module templates

The output file also contains the "Output File Info Preference Section" with
Rouu chunk data (154 bytes per entry) for each output module template.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..binary.render_chunks import OutputModuleSettingsItem, RenderSettingsItem
from .prefs import collapse_continuation_lines, parse_hex_value

if TYPE_CHECKING:
    from pathlib import Path

# Render settings prefs format:
# RenderSettingsItem is 2182 bytes in prefs (2246 in AEP, difference = 64).
_RS_PREFS_ITEM_SIZE = 2182
_RS_AEP_ITEM_SIZE = 2246
_RS_ITEM_SIZE_DIFF = _RS_AEP_ITEM_SIZE - _RS_PREFS_ITEM_SIZE
_HEADER_SIZE = 32  # bytes before first item

# Output module prefs format:
# OutputModuleSettingsItem is 128 bytes (same in prefs and AEP).
_OM_PREFS_ITEM_SIZE = 128


@dataclass
class OutputModuleTemplate:
    """An output module template parsed from AE preferences.

    Attributes:
        settings: The binary settings for this template.
        name: The template name from the prefs spec strings section.
        format_info: Raw bytes of the `Rouu` chunk (output format header),
            or None if no format info was found.
        format_options: Raw bytes of the format-specific `Ropt` chunk (codec
            / image-sequence options), from the "Output File Options
            Preference Section". None if absent.
        format_options_xml: The XML format options string, or None.
    """

    settings: OutputModuleSettingsItem
    name: str
    format_info: bytes | None = None
    format_options: bytes | None = None
    format_options_xml: str | None = None


def _extract_section_value(lines: list[str], key: str) -> bytes | None:
    """Extract a hex/ASCII value from a preference section."""
    for i, line in enumerate(lines):
        if key not in line:
            continue
        m = re.match(r'\s*"' + re.escape(key) + r'"\s*=\s*(.+)', line)
        if not m:
            continue
        value_parts = [m.group(1).strip()]
        for j in range(i + 1, len(lines)):
            next_line = lines[j].strip()
            if not next_line or next_line.startswith("#") or next_line.startswith("["):
                break
            if next_line.startswith('"'):
                break
            value_parts.append(next_line)
        return parse_hex_value("".join(value_parts))
    return None


def parse_render_templates(
    prefs_dir: Path,
) -> tuple[list[RenderSettingsItem], int | None]:
    """Parse render settings templates from AE preferences.

    Args:
        prefs_dir: Path to the AE version preferences directory
            (e.g. `~/AppData/Roaming/Adobe/After Effects/25.6`).

    Returns:
        A tuple of (templates, default_index). Templates is a list of
        parsed [RenderSettingsItem][] objects. Default_index is the
        index of the default render settings template in the returned
        list, or None if not found (or the default entry was filtered
        out).
    """
    render_files = list(prefs_dir.glob("*-indep-render.txt"))
    if not render_files:
        return [], None

    text = render_files[0].read_text(encoding="utf-8", errors="replace")
    lines = collapse_continuation_lines(text)

    raw = _extract_section_value(lines, "Render Settings List")
    if raw is None:
        return [], None

    # The prefs format omits the last 64 bytes (_remaining field).
    # Pad to match the aep format.
    remaining = len(raw) - _HEADER_SIZE

    raw_default_index = _extract_int_value(lines, "Default RS Index")

    count = remaining // _RS_PREFS_ITEM_SIZE
    templates: list[RenderSettingsItem] = []
    default_index: int | None = None
    for idx in range(count):
        offset = _HEADER_SIZE + idx * _RS_PREFS_ITEM_SIZE
        item_data = raw[offset : offset + _RS_PREFS_ITEM_SIZE]
        item = RenderSettingsItem.frombytes(item_data + b"\x00" * _RS_ITEM_SIZE_DIFF)
        assert isinstance(item, RenderSettingsItem)
        if not item.clean_template_name:
            continue
        # The prefs default index counts raw entries; remap it to the
        # filtered list. A filtered-out default yields None (no default).
        if idx == raw_default_index:
            default_index = len(templates)
        templates.append(item)

    return templates, default_index


def _extract_int_value(lines: list[str], key: str) -> int | None:
    """Extract an integer value from a preference line like `"Key" = 42`."""
    for line in lines:
        m = re.match(r'\s*"' + re.escape(key) + r'"\s*=\s*"?(\d+)"?', line)
        if m:
            return int(m.group(1))
    return None


def parse_output_templates(
    prefs_dir: Path,
) -> tuple[list[OutputModuleTemplate], int | None]:
    """Parse output module templates from AE preferences.

    Args:
        prefs_dir: Path to the AE version preferences directory
            (e.g. `~/AppData/Roaming/Adobe/After Effects/25.6`).

    Returns:
        A tuple of (templates, default_index). Templates is a list of
        [OutputModuleTemplate][] objects. Default_index is the index
        of the default output module template in the returned list, or
        None if not found (or the default entry was filtered out).
        Templates whose name starts with `_HIDDEN` are excluded.
    """
    output_files = list(prefs_dir.glob("*-indep-output.txt"))
    if not output_files:
        return [], None

    text = output_files[0].read_text(encoding="utf-8", errors="replace")
    lines = collapse_continuation_lines(text)

    raw = _extract_section_value(lines, "Output Module List v28")
    if raw is None:
        return [], None

    names = _extract_template_names(lines)

    # Rouu header bytes ("Output File Info") and the format-specific Ropt
    # bytes ("Output File Options"), both keyed by the same template index.
    format_infos = _parse_id_hex_section(
        text, "Output File Info Preference Section", "Output File Info"
    )
    format_opts = _parse_id_hex_section(
        text, "Output File Options Preference Section", "Output File Options"
    )

    raw_default_index = _extract_int_value(lines, "Default OM Index")

    remaining = len(raw) - _HEADER_SIZE
    count = remaining // _OM_PREFS_ITEM_SIZE
    templates: list[OutputModuleTemplate] = []
    default_index: int | None = None
    for idx in range(count):
        offset = _HEADER_SIZE + idx * _OM_PREFS_ITEM_SIZE
        item_data = raw[offset : offset + _OM_PREFS_ITEM_SIZE]
        item = OutputModuleSettingsItem.frombytes(item_data)
        assert isinstance(item, OutputModuleSettingsItem)
        name = names.get(idx, "")
        if not name or name.startswith("_HIDDEN"):
            continue
        # The prefs default index counts raw entries; remap it to the
        # filtered list. A filtered-out default yields None (no default).
        if idx == raw_default_index:
            default_index = len(templates)
        templates.append(
            OutputModuleTemplate(
                settings=item,
                name=name,
                format_info=format_infos.get(idx),
                format_options=format_opts.get(idx),
            )
        )

    return templates, default_index


def _parse_id_hex_section(text: str, section: str, id_prefix: str) -> dict[int, bytes]:
    """Parse a `"<id_prefix> ID # N" = <hex/ascii>` preferences section.

    Used for both "Output File Info" (the `Rouu` header) and "Output File
    Options" (the `Ropt` format options). Values span continuation lines
    (double-tab indented, trailing backslash) and use AE's mixed hex/ASCII
    encoding decoded by `parse_hex_value`. Parsing is bounded to the named
    section so continuation lines never leak across section boundaries.

    Args:
        text: Full preferences file text.
        section: Substring identifying the section header line (e.g.
            "Output File Info Preference Section").
        id_prefix: The per-entry key prefix (e.g. "Output File Info").

    Returns:
        A dict mapping template index to decoded raw bytes.
    """
    entries: dict[int, bytes] = {}
    current_idx: int | None = None
    current_value = ""
    in_section = False
    entry_re = re.compile(r'\s*"' + re.escape(id_prefix) + r' ID #\s*(\d+)"\s*=\s*(.+)')

    def _flush() -> None:
        nonlocal current_idx
        if current_idx is not None:
            entries[current_idx] = parse_hex_value(current_value)
            current_idx = None

    for line in text.split("\n"):
        stripped = line.rstrip()
        if not stripped:
            continue
        if stripped.startswith("["):  # section boundary
            _flush()
            in_section = section in stripped
            continue
        if not in_section:
            continue
        m = entry_re.match(stripped)
        if m:
            _flush()
            current_idx = int(m.group(1))
            value = m.group(2).strip()
            current_value = value[:-1] if value.endswith("\\") else value
            continue
        if current_idx is not None and stripped.startswith("\t\t"):
            value = stripped.strip()
            current_value += value[:-1] if value.endswith("\\") else value

    _flush()
    return entries


def _extract_template_names(lines: list[str]) -> dict[int, str]:
    """Extract template names from Output Module Spec Strings section."""
    names: dict[int, str] = {}
    for line in lines:
        m = re.match(
            r'\s*"Output Module Spec Strings Name #?(\d+)"\s*=\s*"(.*)"',
            line,
        )
        if m:
            idx = int(m.group(1))
            names[idx] = m.group(2)
    return names
