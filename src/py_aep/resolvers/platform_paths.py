"""File paths in the `alas` records After Effects stores, per platform.

After Effects locates footage and render output by an absolute path written
in its own platform's style (POSIX on macOS, drive letter or UNC on Windows),
and falls back to a path relative to the project file when that is gone (a
moved project folder, another machine). The fallback is stored as two
counts: `ascendcount_base`, the path components from the common folder down
to the project file, and `ascendcount_target`, the same down to the target.
"""

from __future__ import annotations

import re
from pathlib import PurePath, PurePosixPath, PureWindowsPath

_DRIVE = re.compile(r"^([A-Za-z]):[\\/]?(.*)$", re.DOTALL)
_UNC = re.compile(r"^(?:\\\\|//)[^\\/]+[\\/]([^\\/]+)[\\/]?(.*)$", re.DOTALL)


def _is_posix(path: str) -> bool:
    return path.startswith("/") and not path.startswith("//")


def platform_path(path: str, *, windows: bool) -> str:
    """`path` in the style of After Effects on the target platform.

    After Effects on Windows opens a macOS path `/Users/x/a.png` as
    `C:\\Users\\x\\a.png` (and `/Volumes/v/a.png` as
    `C:\\Volumes\\v\\a.png`), measured on AE 2026; the reverse is the
    inverse of that. A Windows path on another drive or on a UNC share has no
    such counterpart, so it maps to a macOS mount point - `D:\\x` to
    `/Volumes/D/x`, `\\\\server\\share\\x` to `/Volumes/share/x` (the
    usual macOS mount of a share, not measured). A path already in the target
    style, or a relative one, is returned unchanged.

    Args:
        path: An absolute path in either style.
        windows: `True` for After Effects on Windows, `False` for macOS.
    """
    if windows:
        if _is_posix(path):
            return "C:" + path.replace("/", "\\")
        return path
    if _is_posix(path):
        return path
    drive = _DRIVE.match(path)
    unc = None if drive else _UNC.match(path)
    if drive:
        letter = drive.group(1).upper()
        root = "" if letter == "C" else "/Volumes/" + letter
        rest = drive.group(2)
    elif unc:
        root, rest = "/Volumes/" + unc.group(1), unc.group(2)
    else:
        return path
    rest = rest.replace("\\", "/")
    return f"{root}/{rest}" if rest or not root else root


def _pure_path(path: str) -> PurePath | None:
    if _is_posix(path):
        return PurePosixPath(path)
    if _DRIVE.match(path) or _UNC.match(path):
        return PureWindowsPath(path)
    return None


def _volume_parts(path: PurePath) -> int:
    """How many leading parts name the volume: the drive or UNC share, or
    on macOS `/Volumes/<name>` (else the root)."""
    if isinstance(path, PurePosixPath):
        return 3 if len(path.parts) > 2 and path.parts[1] == "Volumes" else 1
    return 1


def relative_path_counts(
    project_file: str, target: str, *, target_is_folder: bool
) -> tuple[int, int]:
    """The `(ascendcount_base, ascendcount_target)` pair After Effects stores.

    Each count is the number of path components below the deepest folder
    the project file and the target share. A folder target (an image
    sequence's folder, a render output folder) counts one component more, as
    for a file inside it. Paths on different volumes or in different path
    styles have no relative path: `(0, 0)`.

    Matches the counts After Effects writes on Windows - AE 2026 saves on a
    local drive, and production projects saved on a UNC share - for footage
    files, sequence folders and render output folders. On macOS a
    `/Volumes/<name>` mount is taken as its own volume, like a drive or share
    (not measured).

    Args:
        project_file: Absolute path of the saved `.aep` file, in the same
            style as `target` (see `platform_path`).
        target: The record's absolute `fullpath`.
        target_is_folder: The record's `target_is_folder`.
    """
    base = _pure_path(project_file)
    goal = _pure_path(target)
    if base is None or goal is None or type(base) is not type(goal):
        return 0, 0
    if target_is_folder:
        goal = goal / "_"
    # Windows paths compare case-insensitively.
    fold = isinstance(base, PureWindowsPath)
    a = [p.lower() if fold else p for p in base.parts]
    b = [p.lower() if fold else p for p in goal.parts]
    volume = _volume_parts(base)
    if a[:volume] != b[: _volume_parts(goal)]:
        return 0, 0
    common = 0
    while common < min(len(a), len(b)) and a[common] == b[common]:
        common += 1
    return len(a) - common, len(b) - common
