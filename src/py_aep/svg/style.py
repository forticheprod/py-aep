"""SVG style resolution: CSS cascade + inheritance.

Resolves the effective presentation properties for an element by
combining (weakest to strongest): inherited values, presentation
attributes, matching `<style>` rules ordered by specificity, and the
inline `style` attribute.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from typing import Collection

# Presentation properties py_aep tracks (the paintable subset plus the text
# properties needed to outline `<text>`/`<tspan>`).
_TRACKED = (
    "fill",
    "fill-opacity",
    "fill-rule",
    "stroke",
    "stroke-opacity",
    "stroke-width",
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-miterlimit",
    "stroke-dasharray",
    "color",
    "opacity",
    "display",
    "visibility",
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "text-anchor",
    "letter-spacing",
)
# Properties that inherit from parent to child (CSS-defined). Of the tracked
# set, only `opacity` and `display` do NOT inherit (`visibility` does).
INHERITABLE = frozenset(_TRACKED) - {"opacity", "display"}


class CssRule(NamedTuple):
    """A parsed CSS rule: one selector with its declarations."""

    specificity: tuple[int, int, int]
    order: int
    selector: str
    declarations: dict[str, str]


_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def parse_css(text: str) -> list[CssRule]:
    """Parse a `<style>` block into rules (comma groups split out).

    Supports simple selectors: `tag`, `.class`, `#id`, `*`, and chains
    of those (e.g. `rect.foo`). Combinators and pseudo-classes are not
    matched (treated as never-matching).
    """
    rules: list[CssRule] = []
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    order = 0
    for sel_group, body in _RULE_RE.findall(text):
        decls = _parse_declarations(body)
        if not decls:
            continue
        for sel in sel_group.split(","):
            sel = sel.strip()
            if not sel:
                continue
            rules.append(CssRule(_specificity(sel), order, sel, decls))
            order += 1
    return rules


_IMPORTANT_RE = re.compile(r"\s*!\s*important\s*$", re.IGNORECASE)


def _parse_declarations(
    body: str, tracked: Collection[str] = _TRACKED
) -> dict[str, str]:
    out: dict[str, str] = {}
    for decl in body.split(";"):
        if ":" not in decl:
            continue
        key, _, val = decl.partition(":")
        key = key.strip().lower()
        if key in tracked:
            # Drop the CSS `!important` priority flag so it does not leak into
            # the value and break downstream color/number parsing.
            out[key] = _IMPORTANT_RE.sub("", val).strip()
    return out


_SEL_TOKEN_RE = re.compile(r"([#.]?)([A-Za-z0-9_*-]+)")


def _specificity(selector: str) -> tuple[int, int, int]:
    ids = classes = types = 0
    for prefix, name in _SEL_TOKEN_RE.findall(selector):
        if prefix == "#":
            ids += 1
        elif prefix == ".":
            classes += 1
        elif name != "*":
            types += 1
    return (ids, classes, types)


def selector_matches(selector: str, tag: str, elem_id: str, classes: frozenset) -> bool:
    """Test a simple selector against an element.

    Only single compound selectors (no descendant combinators) match;
    a selector containing whitespace never matches.
    """
    if " " in selector.strip() or ">" in selector or "+" in selector or "~" in selector:
        return False
    if ":" in selector or "[" in selector:
        return False
    for prefix, name in _SEL_TOKEN_RE.findall(selector):
        if prefix == "#":
            if name != elem_id:
                return False
        elif prefix == ".":
            if name not in classes:
                return False
        elif name != "*":
            if name != tag:
                return False
    return True


def resolve_properties(
    parent: dict[str, str],
    tag: str,
    attrs: dict[str, str],
    css_rules: list[CssRule],
) -> dict[str, str]:
    """Compute the effective presentation properties for an element.

    Args:
        parent: The parent element's resolved properties.
        tag: Local element name.
        attrs: Element attributes.
        css_rules: Parsed document CSS rules.

    Returns:
        The resolved property dict for this element.
    """
    # Start from inherited properties only.
    style: dict[str, str] = {k: v for k, v in parent.items() if k in INHERITABLE}

    # Presentation attributes (weakest author level).
    for key in _TRACKED:
        if key in attrs:
            style[key] = attrs[key].strip()

    # Matching CSS rules, applied in (specificity, order) ascending so the
    # strongest wins.
    elem_id = attrs.get("id", "")
    classes = frozenset(attrs.get("class", "").split())
    matched = [
        r for r in css_rules if selector_matches(r.selector, tag, elem_id, classes)
    ]
    for rule in sorted(matched, key=lambda r: (r.specificity, r.order)):
        style.update(rule.declarations)

    # Inline style attribute (strongest).
    if "style" in attrs:
        style.update(_parse_declarations(attrs["style"]))

    return style
