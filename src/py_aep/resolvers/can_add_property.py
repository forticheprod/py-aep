"""Resolver for `PropertyGroup.can_add_property`.

Determines whether a property with a given match name or display name
can be added to a specific indexed group.
"""

from __future__ import annotations

from py_aep.data.match_names import MATCH_NAME_TO_AUTO_NAME
from py_aep.enums import PropertyType

# Match names that can be added to specific indexed groups via add_property().
_ADDABLE_MASK_MATCH_NAMES: frozenset[str] = frozenset({"ADBE Mask Atom"})

_ADDABLE_TEXT_ANIMATOR_MATCH_NAMES: frozenset[str] = frozenset({"ADBE Text Animator"})

# Shape elements that can be added to a Root Vectors Group (Contents).
_ADDABLE_SHAPE_MATCH_NAMES: frozenset[str] = frozenset(
    {
        "ADBE Vector Group",
        "ADBE Vector Shape - Rect",
        "ADBE Vector Shape - Ellipse",
        "ADBE Vector Shape - Star",
        "ADBE Vector Shape - Group",
        "ADBE Vector Graphic - Fill",
        "ADBE Vector Graphic - Stroke",
        "ADBE Vector Graphic - G-Fill",
        "ADBE Vector Graphic - G-Stroke",
        "ADBE Vector Filter - Merge",
        "ADBE Vector Filter - Offset",
        "ADBE Vector Filter - PB",
        "ADBE Vector Filter - Repeater",
        "ADBE Vector Filter - RC",
        "ADBE Vector Filter - Trim",
        "ADBE Vector Filter - Twist",
        "ADBE Vector Filter - Roughen",
        "ADBE Vector Filter - Wiggler",
        "ADBE Vector Filter - Zigzag",
    }
)

# Reverse lookup: display name -> match name for addable items.
_ADDABLE_DISPLAY_TO_MATCH: dict[str, str] = {}
for _mn in (
    _ADDABLE_MASK_MATCH_NAMES
    | _ADDABLE_TEXT_ANIMATOR_MATCH_NAMES
    | _ADDABLE_SHAPE_MATCH_NAMES
):
    _auto = MATCH_NAME_TO_AUTO_NAME.get(_mn)
    if _auto is not None:
        _ADDABLE_DISPLAY_TO_MATCH[_auto] = _mn
del _mn, _auto

# Per-group addable sets, keyed by parent match name.
_ADDABLE_BY_GROUP: dict[str, frozenset[str]] = {
    "ADBE Mask Parade": _ADDABLE_MASK_MATCH_NAMES,
    "ADBE Effect Mask Parade": _ADDABLE_MASK_MATCH_NAMES,
    "ADBE Text Animators": _ADDABLE_TEXT_ANIMATOR_MATCH_NAMES,
    "ADBE Root Vectors Group": _ADDABLE_SHAPE_MATCH_NAMES,
}


def can_add_property(
    match_name: str,
    property_type: PropertyType,
    name: str,
) -> bool:
    """Check whether a property with the given name can be added.

    Returns `True` if the group is an indexed group and `name` is a
    valid match name or display name for the group type. For the Effect
    Parade, any non-empty string is accepted (actual effect availability
    is validated at add time).

    Args:
        match_name: The match name of the parent group.
        property_type: The property type of the parent group.
        name: A match name or display name to check.
    """
    if property_type != PropertyType.INDEXED_GROUP:
        return False
    if not name:
        return False

    # Effect Parade: accept any name - validation deferred to add_property().
    if match_name == "ADBE Effect Parade":
        return True

    allowed = _ADDABLE_BY_GROUP.get(match_name)
    if allowed is None:
        return False

    if name in allowed:
        return True

    # Try display name -> match name reverse lookup.
    resolved = _ADDABLE_DISPLAY_TO_MATCH.get(name)
    return resolved is not None and resolved in allowed
