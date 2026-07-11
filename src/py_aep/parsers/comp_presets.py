"""Parse New Composition presets from After Effects preferences.

AE stores the Composition Settings dialog's preset dropdown in the
machine-independent composition preferences file:

- `Composition Preset Names Section v11` - display names, `"-"` entries
  are menu separators
- `Composition Presets Section v11` - 16-byte binary entries decoded by
  `CompPresetItem` (width, height, frame rate, pixel aspect)

Entries are matched by their shared 3-digit key (`"000"`, `"001"`, ...).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..binary.composition_chunks import CompPresetItem
from .prefs import PrefsFile, decode_pref_string, parse_hex_value

_NAMES_SECTION = "Composition Preset Names Section v11"
_PRESETS_SECTION = "Composition Presets Section v11"
_PRESET_SIZE = 16


@dataclass
class CompPreset:
    """A New Composition preset from the AE preferences.

    Attributes:
        name: Display name (e.g. `HD . 1920x1080 . 25 fps`, with
            bullet separators).
        width: Width in pixels.
        height: Height in pixels.
        pixel_aspect: Pixel aspect ratio.
        frame_rate: Frame rate in frames per second.
    """

    name: str
    width: int
    height: int
    pixel_aspect: float
    frame_rate: float


def parse_comp_presets(prefs_file: PrefsFile) -> list[CompPreset]:
    """Parse New Composition presets from a composition preferences file.

    Menu separators (`"-"` names, all-zero entries) are skipped.
    """
    names = prefs_file.section(_NAMES_SECTION)
    entries = prefs_file.section(_PRESETS_SECTION)
    presets: list[CompPreset] = []
    for key in sorted(entries):
        raw_name = names.get(key)
        if raw_name is None:
            continue
        name = decode_pref_string(raw_name)
        data = parse_hex_value(entries[key])
        if name == "-" or len(data) != _PRESET_SIZE:
            continue
        item = CompPresetItem.frombytes(data)
        assert isinstance(item, CompPresetItem)
        if item.width == 0 or item.pixel_aspect_divisor == 0:
            continue
        presets.append(
            CompPreset(
                name=name,
                width=item.width,
                height=item.height,
                pixel_aspect=item.pixel_aspect,
                frame_rate=item.frame_rate,
            )
        )
    return presets
