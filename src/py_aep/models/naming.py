"""Name generation and incrementing utilities for project items."""

from __future__ import annotations

import re

_TRAILING_NUMBER_RE = re.compile(r"(\d+)$")


def _next_suffix(prefix: str, existing_names: set[str]) -> int:
    """Return the next available numeric suffix for `{prefix}{N}`.

    Returns 1 if no name in `existing_names` starts with `prefix`.
    If any name matches `prefix` (with or without a digit suffix),
    suffix 1 is skipped - returns at least 2.
    """
    max_suffix = 0
    for name in existing_names:
        if name.startswith(prefix):
            tail = name[len(prefix) :]
            if tail.isdigit():
                n = int(tail)
                max_suffix = max(max_suffix, n if n > 0 else 1)
            else:
                max_suffix = max(max_suffix, 1)
        elif name == prefix.rstrip():
            max_suffix = max(max_suffix, 1)
    return max_suffix + 1


def auto_name(name: str, existing_names: set[str]) -> str:
    """Find the next available incremented name.

    - Removes the number suffix if there is one
    - Finds the highest number suffix with the same prefix in `existing_names`
    - Increments it by 1
    - If no existing name starts with the base name, return `{name} 1`.
    - If existing names start with the base name but none has a number suffix, skip 1 and
    return `{name} 2`.
    """
    match = _TRAILING_NUMBER_RE.search(name)
    if match:
        prefix = name[: match.start()]
    else:
        prefix = f"{name} "
    suffix = _next_suffix(prefix, existing_names)
    return f"{prefix}{suffix}"
