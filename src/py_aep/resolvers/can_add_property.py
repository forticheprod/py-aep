"""Resolver for `PropertyGroup.can_add_property`.

Determines whether a property with a given match name or display name
can be added to a specific indexed group.
"""

from __future__ import annotations

import enum

from py_aep.data.effect_controls import EXPRESSION_CONTROLS
from py_aep.data.match_names import MATCH_NAME_TO_AUTO_NAME
from py_aep.data.text_animator_pool import TEXT_ANIMATOR_POOL
from py_aep.enums import PropertyType


class AddableKind(enum.Enum):
    """Category of an addable property - selects the model's builder.

    The resolver is the single source of truth for this classification so
    the model can dispatch on it without re-deriving the category from the
    resolved match name.
    """

    MASK = "mask"
    EXPRESSION_CONTROL = "expression_control"
    DROPDOWN = "dropdown"
    SHAPE = "shape"
    TEXT_ANIMATOR = "text_animator"
    TEXT_SELECTOR = "text_selector"
    ANIMATOR_PROPERTY = "animator_property"


# Match names that can be added to specific indexed groups via add_property().
_ADDABLE_MASK_MATCH_NAMES: frozenset[str] = frozenset({"ADBE Mask Atom"})

# Effects creatable via add_property(). The Dropdown Menu Control
# registers as a pseudo effect with a per-instance generated match name
# (`Pseudo/@@` + base64(uuid4)); add_property generates one on demand.
_ADDABLE_EFFECT_MATCH_NAMES: frozenset[str] = frozenset(EXPRESSION_CONTROLS) | {
    "ADBE Dropdown Control"
}

_EFFECT_DISPLAY_TO_MATCH: dict[str, str] = {
    entry["name"]: mn for mn, entry in EXPRESSION_CONTROLS.items()
}
_EFFECT_DISPLAY_TO_MATCH["Dropdown Menu Control"] = "ADBE Dropdown Control"

_ADDABLE_TEXT_ANIMATOR_MATCH_NAMES: frozenset[str] = frozenset({"ADBE Text Animator"})

# Selectors addable to a text animator's Selectors group.
_ADDABLE_TEXT_SELECTOR_MATCH_NAMES: frozenset[str] = frozenset(
    {
        "ADBE Text Selector",
        "ADBE Text Wiggly Selector",
        "ADBE Text Expressible Selector",
    }
)

# Animator properties applicable to a text animator's (NAMED) Properties
# group - the full pool minus the 8 variable-font axes (not addable).
_ADDABLE_ANIMATOR_PROPERTY_MATCH_NAMES: frozenset[str] = frozenset(
    e["mn"] for e in TEXT_ANIMATOR_POOL if not e["mn"].startswith("ADBE Text VF Axis")
)
_ANIMATOR_PROPERTY_DISPLAY_TO_MATCH: dict[str, str] = {
    e["name"]: e["mn"]
    for e in TEXT_ANIMATOR_POOL
    if e["name"] and not e["mn"].startswith("ADBE Text VF Axis")
}

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
    | _ADDABLE_TEXT_SELECTOR_MATCH_NAMES
    | _ADDABLE_SHAPE_MATCH_NAMES
):
    _auto = MATCH_NAME_TO_AUTO_NAME.get(_mn)
    if _auto is not None:
        _ADDABLE_DISPLAY_TO_MATCH[_auto] = _mn
del _mn, _auto

# Per-group addable sets + builder kind, keyed by parent match name.
# "ADBE Vectors Group" is a nested shape group's own contents.
_ADDABLE_BY_GROUP: dict[str, tuple[frozenset[str], AddableKind]] = {
    "ADBE Mask Parade": (_ADDABLE_MASK_MATCH_NAMES, AddableKind.MASK),
    "ADBE Effect Mask Parade": (_ADDABLE_MASK_MATCH_NAMES, AddableKind.MASK),
    "ADBE Text Animators": (
        _ADDABLE_TEXT_ANIMATOR_MATCH_NAMES,
        AddableKind.TEXT_ANIMATOR,
    ),
    "ADBE Text Selectors": (
        _ADDABLE_TEXT_SELECTOR_MATCH_NAMES,
        AddableKind.TEXT_SELECTOR,
    ),
    "ADBE Root Vectors Group": (_ADDABLE_SHAPE_MATCH_NAMES, AddableKind.SHAPE),
    "ADBE Vectors Group": (_ADDABLE_SHAPE_MATCH_NAMES, AddableKind.SHAPE),
    "ADBE Text Animator Properties": (
        _ADDABLE_ANIMATOR_PROPERTY_MATCH_NAMES,
        AddableKind.ANIMATOR_PROPERTY,
    ),
}

# Addable groups that are NAMED (not indexed) - the ExtendScript
# "named-group exception". Adding to them materializes a fixed-pool
# member in place rather than appending a new indexed child.
_NAMED_ADDABLE_GROUPS: frozenset[str] = frozenset({"ADBE Text Animator Properties"})


def resolve_addable(
    match_name: str,
    property_type: PropertyType,
    name: str,
) -> tuple[str, AddableKind] | None:
    """Resolve `name` to `(match_name, kind)` for an addable property.

    Returns the resolved match name plus its builder category if the
    group is an indexed group and `name` is a valid match name or display
    name for the group type, `None` otherwise. `kind` is the single
    source of truth for the category, so the model dispatches on it
    without re-classifying the match name. For the Effect Parade, only
    the expression controls py_aep can create are accepted (AE itself
    validates against the installed effects).

    Args:
        match_name: The match name of the parent group.
        property_type: The property type of the parent group.
        name: A match name or display name to resolve.
    """
    if not name:
        return None
    # Most addable groups are indexed; the text-animator Properties group
    # is the NAMED-group exception (see _NAMED_ADDABLE_GROUPS).
    if (
        property_type != PropertyType.INDEXED_GROUP
        and match_name not in _NAMED_ADDABLE_GROUPS
    ):
        return None

    if match_name == "ADBE Effect Parade":
        resolved = (
            name
            if name in _ADDABLE_EFFECT_MATCH_NAMES
            else _EFFECT_DISPLAY_TO_MATCH.get(name)
        )
        if resolved is None:
            return None
        kind = (
            AddableKind.DROPDOWN
            if resolved == "ADBE Dropdown Control"
            else AddableKind.EXPRESSION_CONTROL
        )
        return resolved, kind

    entry = _ADDABLE_BY_GROUP.get(match_name)
    if entry is None:
        return None
    allowed, kind = entry
    if name in allowed:
        return name, kind
    # Try display name -> match name reverse lookup (pool names for the
    # animator Properties group, since their registry names diverge).
    if kind is AddableKind.ANIMATOR_PROPERTY:
        resolved = _ANIMATOR_PROPERTY_DISPLAY_TO_MATCH.get(name)
    else:
        resolved = _ADDABLE_DISPLAY_TO_MATCH.get(name)
    if resolved is not None and resolved in allowed:
        return resolved, kind
    return None


def can_add_property(
    match_name: str,
    property_type: PropertyType,
    name: str,
) -> bool:
    """Check whether a property with the given name can be added.

    Returns `True` if the group is an indexed group and `name` is a
    valid match name or display name for the group type. For the Effect
    Parade, only the expression controls py_aep can create are
    accepted.

    Args:
        match_name: The match name of the parent group.
        property_type: The property type of the parent group.
        name: A match name or display name to check.
    """
    return resolve_addable(match_name, property_type, name) is not None
