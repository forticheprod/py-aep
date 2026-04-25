"""Griffe extension that reclassifies @property functions as attributes.

Griffe's static analysis classifies `@property` decorated methods as
`Function` objects. When a property has a setter, the setter overwrites
the getter - losing the docstring and return annotation. This extension
captures getter info during function processing, then converts property
functions to `Attribute` objects in the class members phase.
"""

from __future__ import annotations

from typing import Any

from griffe import Attribute, Class, Extension, Function


class PropertiesAsAttributes(Extension):
    """Convert `@property` functions into `Attribute` objects."""

    def __init__(self) -> None:
        super().__init__()
        self._getter_info: dict[tuple[str, str], dict[str, Any]] = {}

    def on_function_instance(
        self, *, node: Any, func: Function, agent: Any, **kwargs: Any
    ) -> None:
        """Capture property getter info before the setter overwrites it."""
        for dec in func.decorators:
            if str(dec.value) == "property":
                parent_path = func.parent.path if func.parent else ""
                self._getter_info[(parent_path, func.name)] = {
                    "docstring": func.docstring,
                    "annotation": func.returns,
                    "lineno": func.lineno,
                    "endlineno": func.endlineno,
                }
                break

    def on_class_members(
        self, *, node: Any, cls: Class, agent: Any, **kwargs: Any
    ) -> None:
        """Replace property functions with attributes."""
        to_replace: dict[str, Attribute] = {}
        for name, member in cls.members.items():
            if not isinstance(member, Function):
                continue
            is_property = any(
                str(d.value) == "property" or str(d.value).endswith(".setter")
                for d in member.decorators
            )
            if not is_property:
                continue

            info = self._getter_info.get((cls.path, name), {})
            attr = Attribute(
                name=name,
                lineno=info.get("lineno", member.lineno),
                endlineno=info.get("endlineno", member.endlineno),
                annotation=info.get("annotation", member.returns),
            )
            attr.docstring = info.get("docstring", member.docstring)
            to_replace[name] = attr

        for name, attr in to_replace.items():
            cls.del_member(name)
            cls.set_member(name, attr)
