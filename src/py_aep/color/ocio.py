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
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator, NamedTuple

import yaml

from .envelope import _compact, build_ocio_envelope
from .murmur3 import dva_guid


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


@lru_cache(maxsize=8)
def _load_config_cached(config_path: Path, _stamp: tuple[int, int]) -> dict | None:
    try:
        with config_path.open(encoding="utf-8") as f:
            doc = yaml.load(f, Loader=_OcioLoader)
    except (OSError, yaml.YAMLError):
        return None
    return doc if isinstance(doc, dict) else None


def _config_stamp(config_path: Path) -> tuple[int, int] | None:
    """`(mtime_ns, size)` cache key for `config_path`, or `None` if unreadable."""
    try:
        st = config_path.stat()
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def _load_config(config_path: Path) -> dict | None:
    """Parse a `.ocio` config, or `None` if it cannot be read or parsed.

    Memoized on `(path, mtime, size)`: parsing a real config is expensive
    (~350ms for AE's bundled ACES 1.2) and every color-space read and write
    resolves through it, so a project with several output modules would
    otherwise re-parse the same unchanged file once per access. The stamp
    keeps an edited config from going stale.

    The returned dict is shared with every other caller - treat it as
    read-only.
    """
    stamp = _config_stamp(config_path)
    if stamp is None:
        return None
    return _load_config_cached(config_path, stamp)


def list_config_color_spaces(config_path: Path) -> list[str]:
    """Return the active color-space names declared in a `.ocio` config.

    Collects `colorspaces[].name` and `display_colorspaces[].name`, dropping any
    listed in `inactive_colorspaces`. Returns `[]` if the file cannot be read or
    parsed.

    Args:
        config_path: Path to a `.ocio` configuration file.
    """
    doc = _load_config(config_path)
    if doc is None:
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


def require_ocio_config(config: str | None, purpose: str) -> Path:
    """Resolve an `ocio_configuration_file` value, raising if that fails.

    The config is REQUIRED for envelope/id computation: the stored bytes
    depend on whether the name is a direct colorspace, a role/alias, or a
    `display/view` pair, and only the config can tell those apart.

    Args:
        config: The project's `ocio_configuration_file` value (`None` when
            there is no project to read it from).
        purpose: Completes the error message, e.g.
            `"build the color-profile envelope for 'ACEScg'"`.

    Raises:
        ValueError: If the configuration cannot be located.
    """
    resolved = resolve_ocio_config(config) if config is not None else None
    if resolved is None:
        raise ValueError(
            f"Cannot resolve the project's OCIO configuration ({config!r}), "
            f"which is needed to {purpose}."
        )
    return resolved


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


#: `baseProfileType` for an OCIO color space (see `color/envelope.py`).
_OCIO_PROFILE_TYPE = 3


def _color_space_guid(profile_name: str, profile_data: str) -> bytes:
    """The 16-byte After Effects `Guid` of an OCIO color space.

    Two-stage MurmurHash3 (reverse-engineered from `dvamediatypes.dll`):
    the inner `ColorProfile` Guid hashes the display name + the
    `colorProfileData` JSON; the outer `ColorSpace` Guid wraps that with the
    `baseProfileType` and a flag byte.

    Args:
        profile_name: The `colorProfileName` (e.g. `"ACES/ACEScg yo"`).
        profile_data: The `colorProfileData` JSON (e.g. `{"colorSpace1":"ACEScg yo"}`).
    """
    inner = dva_guid(
        b"DVAColorProfile" + profile_name.encode("utf-8") + profile_data.encode("utf-8")
    )
    return dva_guid(
        b"DVAColorSpace" + inner + _OCIO_PROFILE_TYPE.to_bytes(4, "little") + b"\x00"
    )


class _ConfigIndex(NamedTuple):
    """A `.ocio` config indexed for output-color-space resolution."""

    families: dict[str, str]  # color-space name -> family
    aliases: set[str]  # alias names
    roles: dict[str, str]  # role -> target name
    displays: dict[str, list[str]]  # display -> its view names


def _config_index(config_path: Path) -> _ConfigIndex:
    """Index a `.ocio` config for output-color-space resolution.

    Memoized like `_load_config` (same stamp scheme): every color-space read
    and write needs the index, and rebuilding it walks the whole config. The
    returned index is shared with every other caller - treat it as read-only.
    """
    stamp = _config_stamp(config_path)
    if stamp is None:
        return _ConfigIndex({}, set(), {}, {})
    return _config_index_cached(config_path, stamp)


@lru_cache(maxsize=8)
def _config_index_cached(config_path: Path, _stamp: tuple[int, int]) -> _ConfigIndex:
    doc = _load_config_cached(config_path, _stamp)
    if doc is None:
        return _ConfigIndex({}, set(), {}, {})
    families: dict[str, str] = {}
    aliases: set[str] = set()
    for key in ("colorspaces", "display_colorspaces"):
        for cs in doc.get(key) or []:
            if isinstance(cs, dict) and isinstance(cs.get("name"), str):
                families[cs["name"]] = cs.get("family") or ""
                for alias in cs.get("aliases") or []:
                    if isinstance(alias, str):
                        aliases.add(alias)
    roles = {r: t for r, t in (doc.get("roles") or {}).items() if isinstance(t, str)}
    displays: dict[str, list[str]] = {}
    for display, items in (doc.get("displays") or {}).items():
        views: list[str] = []
        for item in items or []:
            # `!<Views> [name, ..]` (shared views) or `!<View> {name: ..}`; the
            # OCIO loader strips the tags to a list or a dict respectively.
            if isinstance(item, list):
                views.extend(v for v in item if isinstance(v, str))
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                views.append(item["name"])
        displays[display] = views
    return _ConfigIndex(families, aliases, roles, displays)


def _output_envelope(index: _ConfigIndex, color_space: str) -> tuple[str, str]:
    """Resolve `color_space` to `(colorProfileName, colorProfileData)` - the
    envelope After Effects hashes for an OCIO output color space.

    Handles the four selection kinds (each verified byte-exact against
    AE-authored samples):

    - a direct color space (or display color space): `family/name`,
      `colorProfileData` = `{"colorSpace1": name}`.
    - a role: the role's target name, `{"colorSpace1": target, "ocioColorSpaceType": 2}`.
    - an alias: the alias name, `{"colorSpace1": alias, "ocioColorSpaceType": 2}`.
    - a `display/view` pair: `{"colorSpace1": display, "colorSpace2": view,
      "ocioColorSpaceType": 1}`.

    Raises:
        ValueError: If `color_space` is not found in the config.
    """
    if color_space in index.families:
        family = index.families[color_space]
        name = f"{family}/{color_space}" if family else color_space
        return name, _compact({"colorSpace1": color_space})
    if color_space in index.roles:
        target = index.roles[color_space]
        return target, _compact({"colorSpace1": target, "ocioColorSpaceType": 2})
    if color_space in index.aliases:
        return color_space, _compact(
            {"colorSpace1": color_space, "ocioColorSpaceType": 2}
        )
    if "/" in color_space:
        display, view = color_space.rsplit("/", 1)
        # The view must really be one of that display's: a config can name a
        # display after a family (ACES 1.2's only display is `ACES`, which is
        # also the family of `ACES - ACEScg`), and matching on the display
        # alone would claim the `family/name` form the getters return.
        if view in index.displays.get(display, ()):
            return color_space, _compact(
                {"colorSpace1": display, "colorSpace2": view, "ocioColorSpaceType": 1}
            )
    raise ValueError(f"{color_space!r} is not a color space in the OCIO config")


def _iter_output_color_spaces(index: _ConfigIndex) -> Iterator[str]:
    """Yield every assignable OCIO output color-space name (color spaces,
    aliases, roles, and `display/view` pairs)."""
    yield from index.families
    yield from index.aliases
    yield from index.roles
    for display, views in index.displays.items():
        for view in views:
            yield f"{display}/{view}"


@lru_cache(maxsize=8)
def _guid_table_cached(config_path: Path, _stamp: tuple[int, int]) -> dict[bytes, str]:
    """`Guid` -> name for every assignable output color space in the config."""
    index = _config_index_cached(config_path, _stamp)
    table: dict[bytes, str] = {}
    for color_space in _iter_output_color_spaces(index):
        name, data = _output_envelope(index, color_space)
        # Two names can resolve to the same envelope (e.g. two roles sharing
        # a target); keep the first, like the linear scan this table replaces.
        table.setdefault(_color_space_guid(name, data), color_space)
    return table


def ocio_color_space_for_profile_id(config_path: Path, profile_id: bytes) -> str | None:
    """Reverse-map a 16-byte `output_profile_id` to its OCIO color-space name.

    Returns `None` if no assignable color space in the config produces
    `profile_id`. The `Guid` of every candidate (~600 two-stage MurmurHash3
    computations for AE's bundled ACES 1.2) is memoized per config like
    `_load_config`, so repeated reads are dict lookups.

    Args:
        config_path: The resolved `.ocio` config path.
        profile_id: The 16-byte output profile id from the output module.
    """
    stamp = _config_stamp(config_path)
    if stamp is None:
        return None
    return _guid_table_cached(config_path, stamp).get(profile_id)


def ocio_color_profile_envelope(config_path: Path, color_space: str) -> str:
    """The color-profile envelope After Effects stores for an OCIO color space.

    The envelope's `(colorProfileName, colorProfileData)` pair depends on the
    SELECTION KIND, not on the slot it is stored in nor the AE version: the
    project working space uses exactly the same four kinds as an output color
    space (see `_output_envelope`). Verified against AE-authored samples: a
    direct colorspace pick (`ACEScg yo`, family `ACES`) stores
    `colorProfileName="ACES/ACEScg yo"` with `{"colorSpace1":"ACEScg yo"}`,
    while a role pick (`mari_int16`) stores `colorProfileName="sRGB
    (mari_int16)"` with `{...,"ocioColorSpaceType":2}` - and AE 25.6 and
    26.3 write byte-identical envelopes for the same pick.

    Accepts the qualified `"<family>/<name>"` form as well as the bare
    color-space name, because that qualified form is what AE stores as
    `colorProfileName` and therefore what `Project.working_space` reads back -
    without this, assigning a project its own working space would raise.

    Args:
        config_path: The resolved `.ocio` config path.
        color_space: The color-space, role, alias, `display/view`, or
            `family/color-space` name.

    Raises:
        ValueError: If `color_space` is not found in the config.
    """
    index = _config_index(config_path)
    try:
        name, data = _output_envelope(index, color_space)
    except ValueError:
        family, _, bare = color_space.rpartition("/")
        if not family or index.families.get(bare) != family:
            raise
        name, data = _output_envelope(index, bare)
    return build_ocio_envelope(name, data)


def ocio_output_profile_id(config_path: Path, color_space: str) -> bytes:
    """Return the 16-byte `output_profile_id` After Effects stores for an OCIO
    output color space.

    Resolves `color_space` against the config to build the color-profile
    envelope AE would hash (see `_output_envelope` for the four selection
    kinds), then computes its `Guid`.

    Args:
        config_path: The resolved `.ocio` config path.
        color_space: The output color-space name to assign.

    Raises:
        ValueError: If `color_space` is not found in the config.
    """
    name, data = _output_envelope(_config_index(config_path), color_space)
    return _color_space_guid(name, data)
