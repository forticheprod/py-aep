"""Enumerate the color spaces of an OCIO configuration.

Backs `Project.list_color_profiles()` in OCIO mode: given the project's
`ocio_configuration_file` (a `.ocio` path or a built-in config name like
`"ACES 1.2"`), return the assignable color-space names.

The list is the OCIO *active* color spaces (`colorspaces` +
`display_colorspaces`, minus `inactive_colorspaces`) - exactly what
`PyOpenColorIO.Config.getColorSpaceNames()` returns (verified set-equal for
AE's bundled `ACES 1.2` (353)), so no OCIO runtime dependency is needed.
See the `color-management-write-rev-eng` notes.
"""

from __future__ import annotations

import platform
import re
from pathlib import Path
from typing import Any

import yaml


class _OcioLoader(yaml.SafeLoader):
    """A YAML loader that ignores OCIO's custom tags."""


def _ignore_tag(loader: yaml.Loader, suffix: str, node: yaml.Node) -> Any:
    # OCIO writes tags as `!<ColorSpace>` etc.; these resolve to BARE tags
    # (`ColorSpace`, `View`, `Rule`, ...), so an empty-prefix multi-constructor
    # is required (a `"!"`-prefix one would not match). Return the underlying
    # value, discarding the tag.
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    return None


_OcioLoader.add_multi_constructor("", _ignore_tag)


def list_config_color_spaces(config_path: Path) -> list[str]:
    """Return the active color-space names declared in a `.ocio` config.

    Collects `colorspaces[].name` and `display_colorspaces[].name`, dropping any
    listed in `inactive_colorspaces`. Returns `[]` if the file cannot be read or
    parsed.

    Args:
        config_path: Path to a `.ocio` configuration file.
    """
    try:
        with config_path.open(encoding="utf-8") as f:
            doc = yaml.load(f, Loader=_OcioLoader)
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(doc, dict):
        return []
    names: list[str] = []
    for key in ("colorspaces", "display_colorspaces"):
        for entry in doc.get(key) or []:
            if isinstance(entry, dict):
                name = entry.get("name")
                if isinstance(name, str):
                    names.append(name)
    inactive = set(doc.get("inactive_colorspaces") or [])
    # A name may appear in both `colorspaces` and `display_colorspaces`;
    # getColorSpaceNames() returns a unique set, so de-duplicate (order kept).
    seen: set[str] = set()
    result: list[str] = []
    for n in names:
        if n in inactive or n in seen:
            continue
        seen.add(n)
        result.append(n)
    return result


def resolve_ocio_config(config: str) -> Path | None:
    """Resolve an `ocio_configuration_file` value to a `.ocio` path.

    Accepts either a filesystem path or a built-in config name (e.g.
    `"ACES 1.2"`), which After Effects ships under
    `<install>/Support Files/OpenColorIO-Configs/<name>/`.

    Args:
        config: The `ocio_configuration_file` value.

    Returns:
        The resolved `.ocio` path, or `None` if it cannot be located.
    """
    if not config:
        return None
    direct = Path(config)
    if direct.is_file():
        return direct
    for root in _builtin_config_roots():
        config_dir = root / config
        if config_dir.is_dir():
            ocio_files = sorted(config_dir.glob("*.ocio"))
            if ocio_files:
                return ocio_files[0]
    return None


def _builtin_config_roots() -> list[Path]:
    """Candidate `OpenColorIO-Configs` directories in standard AE installs."""
    if platform.system() == "Windows":
        bases = [Path(r"C:\Program Files\Adobe"), Path(r"C:\Program Files (x86)\Adobe")]
    else:  # macOS
        bases = [Path("/Applications")]
    roots: list[Path] = []
    for base in bases:
        if not base.is_dir():
            continue
        # Newest install first, by release year: a plain name sort would put
        # "Adobe After Effects CC 2019" before "Adobe After Effects 2026"
        # ("C" > "2"). Year-less installs (CS6, bare CC) sort last.
        for ae_dir in sorted(
            base.glob("Adobe After Effects *"),
            key=_install_year,
            reverse=True,
        ):
            roots.append(ae_dir / "Support Files" / "OpenColorIO-Configs")
    return roots


def _install_year(install_dir: Path) -> tuple[int, str]:
    match = re.search(r"(\d{4})", install_dir.name)
    return (int(match.group(1)) if match else 0, install_dir.name)
