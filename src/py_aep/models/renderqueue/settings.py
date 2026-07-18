"""Settings-view infrastructure for render queue settings.

`SettingsView` provides a thin `MutableMapping` wrapper that proxies
attribute access on the owner class: each ExtendScript key maps to a
model attribute (either a ChunkField descriptor or a `@property`).
"""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, Any, Dict, MutableMapping, Optional, Tuple, Type, cast

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from ...parsers.comp_presets import CompPreset
    from ..preferences import Preferences

#: Type alias for a settings spec: (attribute_name, optional_enum_class).
SettingsSpec = Dict[str, Tuple[str, Optional[Type[IntEnum]]]]


class SettingsView(MutableMapping[str, Any]):
    """Dict-like view mapping ExtendScript setting keys to model attributes.

    Every read delegates to `getattr(owner, attr_name)` and every write
    delegates to `setattr(owner, attr_name, value)`. Validation is handled by
    the underlying ChunkField descriptors or `@property` setters.

    When `enum_class` is provided for a key, `__setitem__` coerces
    the value (int, string label, or enum member) before passing it
    to the descriptor.
    """

    def __init__(
        self,
        owner: object,
        specs: SettingsSpec,
    ) -> None:
        self._owner = owner
        self._specs = specs

    # -- reads -------------------------------------------------------------

    def __getitem__(self, key: str) -> Any:
        spec = self._specs.get(key)
        if spec is None:
            raise KeyError(key)
        attr_name, _ = spec
        return getattr(self._owner, attr_name)

    # -- writes ------------------------------------------------------------

    def __setitem__(self, key: str, value: Any) -> None:
        spec = self._specs.get(key)
        if spec is None:
            valid = sorted(self._specs)
            raise KeyError(f"Unknown setting {key!r}. Valid keys: {valid}")
        attr_name, enum_class = spec
        if enum_class is not None:
            value = _coerce_enum(enum_class, value)
        try:
            setattr(self._owner, attr_name, value)
        except AttributeError:
            raise AttributeError(f"Setting {key!r} is read-only.") from None

    def __delitem__(self, key: str) -> None:
        raise TypeError("Cannot delete settings keys")

    # -- iteration ---------------------------------------------------------

    def __iter__(self) -> Iterator[str]:
        return iter(self._specs)

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, key: object) -> bool:
        return key in self._specs

    def __repr__(self) -> str:
        return f"SettingsView({dict(self.items())!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, MutableMapping):
            return dict(self.items()) == dict(other.items())
        return NotImplemented


def _coerce_enum(enum_class: type[IntEnum], value: Any) -> IntEnum:
    """Coerce a value to an enum member.

    Accepts:
        - An enum member of the correct type
        - An int matching an enum member's value
        - A string matching an enum member's label
    """
    if isinstance(value, enum_class):
        return value
    if isinstance(value, bool):
        # bool is int: settings["Output Audio"] = True would silently
        # coerce to OutputAudio.OFF (== 1). Reject rather than surprise.
        raise TypeError(f"Expected {enum_class.__name__}, int, or str, got bool")
    if isinstance(value, int):
        try:
            return enum_class(value)
        except ValueError:
            members = ", ".join(f"{m.name} ({int(m)})" for m in enum_class)
            raise ValueError(
                f"Invalid int value {value!r} for {enum_class.__name__}. "
                f"Valid members: {members}"
            ) from None
    if isinstance(value, str):
        by_label = {m.label: m for m in enum_class}  # type: ignore[attr-defined]
        if value in by_label:
            return by_label[value]
        labels = ", ".join(
            f"{m.label!r}"  # type: ignore[attr-defined]
            for m in enum_class
        )
        raise ValueError(
            f"Invalid string {value!r} for {enum_class.__name__}. "
            f"Valid labels: {labels}"
        )
    raise TypeError(
        f"Expected {enum_class.__name__}, int, or str, got {type(value).__name__}"
    )


_RESOLUTION_STRINGS: dict[tuple[int, int], str] = {
    # [0, 0] is the "use the comp's own resolution" sentinel (probed AE
    # 2026: getSettings(STRING) reads back "Current Settings").
    (0, 0): "Current Settings",
    (1, 1): "Full",
    (2, 2): "Half",
    (3, 3): "Third",
    (4, 4): "Quarter",
}

# AE's "Resize to" dropdown labels a target resolution with a New
# Composition preset name. When several presets share a resolution, AE
# picks the LOWEST frame rate (ties broken by the later preset) - probed
# in AE 2026 by reading OutputModule.getSetting("Resize to") for each
# collision resolution against the live comp presets. These labels are
# derived from the user's presets when a preferences directory is
# provided (see build_resize_to_strings); this table is the factory-
# preset fallback used when it is not, and holds AE's actual strings for
# a default install.
_RESIZE_TO_STRINGS: dict[tuple[int, int], str] = {
    (3656, 2664): "Cineon Full  •  3656x2664 • 24 fps",
    (1828, 1332): "Cineon Half  •  1828x1332 • 24 fps",
    (1280, 1080): "DVCPRO HD  •  1280x1080 (1.5) • 29.97 fps",
    (1440, 1080): "DVCPRO HD  •  1440x1080 (1.33) • 25 fps",
    (960, 720): "DVCPRO HD  •  960x720 (1.33) • 23.976 fps",
    (2048, 1556): "Film (2K)  •  2048x1556 • 24 fps",
    (4096, 3112): "Film (4K)  •  4096x3112 • 24 fps",
    (1920, 1080): "HD  •  1920x1080 • 24 fps",
    (1280, 720): "HDV/HDTV  •  1280x720 • 25 fps",
    (720, 1280): "Social Media Portrait  •  720x1280 • 30 fps",
    (1080, 1920): "Social Media Portrait HD  •  1080x1920 • 30 fps",
    (1080, 1080): "Social Media Square  •  1080x1080 • 30 fps",
    (3840, 2160): "UHD (4K)  •  3840x2160 • 23.976 fps",
    (7680, 4320): "UHD (8K)  •  7680x4320 • 23.976 fps",
}


def build_resize_to_strings(
    preferences: Preferences,
) -> dict[tuple[int, int], str]:
    """Build the "Resize to" resolution -> preset-name map from prefs.

    Mirrors AE's Resize dropdown: one label per resolution, choosing the
    lowest-frame-rate New Composition preset at that resolution (ties
    broken by the later preset). Falls back to [_RESIZE_TO_STRINGS][] (AE's
    factory-preset labels) when no preferences directory was provided.
    """
    presets = preferences.composition_presets()
    if not presets:
        return _RESIZE_TO_STRINGS
    best: dict[tuple[int, int], CompPreset] = {}
    for preset in presets:
        key = (preset.width, preset.height)
        current = best.get(key)
        if current is None or preset.frame_rate <= current.frame_rate:
            best[key] = preset
    return {key: preset.name for key, preset in best.items()}


def _to_number_value(value: Any) -> Any:
    """Convert a settings value to NUMBER format.

    IntEnum values are unwrapped to their integer value.
    All other types pass through unchanged.
    """
    if isinstance(value, IntEnum):
        return int(value)
    return value


def _to_string_value(
    key: str,
    value: Any,
    resize_map: dict[tuple[int, int], str] = _RESIZE_TO_STRINGS,
) -> str:
    """Convert a settings value to STRING format.

    Args:
        key: The settings key name.
        value: The settings value.
        resize_map: Resolution -> label map for the "Resize to" key
            (the AE-preference-derived map, or the factory fallback).
    """
    if isinstance(value, dict):
        return {  # type: ignore[return-value]
            k: _to_string_value(k, v, resize_map) for k, v in value.items()
        }
    if isinstance(value, IntEnum):
        return value.label  # type: ignore[attr-defined,no-any-return]
    if key == "Resolution":
        return _RESOLUTION_STRINGS.get(cast(Tuple[int, int], tuple(value)), "Custom")
    if key == "Resize to":
        return resize_map.get(cast(Tuple[int, int], tuple(value)), "Custom")
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def settings_to_number(
    settings: Mapping[str, Any],
) -> dict[str, Any]:
    """Convert settings to NUMBER format.

    IntEnum values are unwrapped to plain integers. Other values
    (bool, float, int, list) pass through unchanged.

    Args:
        settings: The typed settings dict.
    """
    return {k: _to_number_value(v) for k, v in settings.items()}


def settings_to_string(
    settings: Mapping[str, Any],
    resize_map: dict[tuple[int, int], str] = _RESIZE_TO_STRINGS,
) -> dict[str, str]:
    """Convert settings to STRING format.

    All values are converted to their ExtendScript STRING representation.

    Args:
        settings: The typed settings dict.
        resize_map: Resolution -> label map for the "Resize to" key
            (from [build_resize_to_strings][]); defaults to the factory
            fallback table.
    """
    return {k: _to_string_value(k, v, resize_map) for k, v in settings.items()}
