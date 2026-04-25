from __future__ import annotations

import typing
from typing import TYPE_CHECKING, Any

from py_aep.data.match_names import MATCH_NAME_TO_AUTO_NAME
from py_aep.enums import PropertyType

from ...kaitai.materializer import materialize_group
from ...kaitai.proxy import ProxyBody
from .overrides import _PROPERTY_MIN_MAX
from .property import Property
from .property_base import PropertyBase
from .specs import (
    _GROUP_CHILD_SPECS,
    _LAYER_STYLE_CHILD_SPECS,
    _USE_VALUE,
    _GroupSpec,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Literal

    from ...kaitai import Aep
    from .specs import _GroupSpec, _PropSpec


def _reorder_and_fill(
    container: PropertyGroup | Any,
    specs: Sequence[_PropSpec | _GroupSpec],
    child_depth: int,
    *,
    skip: frozenset[str] = frozenset(),
    value_overrides: dict[str, tuple[Any, Any]] | None = None,
    tail_mode: Literal["none", "groups", "all"] = "groups",
) -> None:
    """Reorder *container.properties* according to *specs*, synthesizing missing entries.

    Existing children whose match name appears in *specs* are preserved in
    canonical order. Missing children are created via `Property.synthesized`
    (for `_PropSpec`) or as empty `PropertyGroup` instances (for `_GroupSpec`).

    Args:
        container: Object whose `.properties` list is reordered/filled.
            Also set as `parent_property` on synthesized children.
        specs: Full canonical spec list (NOT pre-filtered by *skip*).
        child_depth: `property_depth` for synthesized children.
        skip: Match names to skip synthesis for.  Checked only when the
            match name is **not** already in the container - existing
            children are always preserved in canonical position.
        value_overrides: `{match_name: (value, default_value)}` for
            overriding synthesized property values.  When `None`, uses
            `spec.value` / `spec.default_value`.
        tail_mode: What non-spec children to append after the canonical
            entries: `"groups"` (only `PropertyGroup`), `"all"`
            (everything), or `"none"` (nothing).
    """
    existing: dict[str, Property | PropertyGroup] = {}
    for child in container.properties:
        existing[child.match_name] = child

    ordered: list[Property | PropertyGroup] = []
    for spec in specs:
        mn = spec.match_name
        if mn in existing:
            child = existing[mn]
            child._auto_name = spec.auto_name
            if not isinstance(spec, _GroupSpec) and isinstance(child, Property):
                child.__dict__["_color"] = spec.color
                if spec.min_value is not None:
                    child._min_value_fallback = spec.min_value
                if spec.max_value is not None:
                    child._max_value_fallback = spec.max_value
                if spec.can_vary_over_time is not None:
                    child._can_vary_over_time = spec.can_vary_over_time
                if child.default_value is None:
                    dv = (
                        spec.value
                        if spec.default_value is _USE_VALUE
                        else spec.default_value
                    )
                    if dv is not None:
                        child.default_value = dv
            ordered.append(child)
        elif mn in skip:
            continue
        elif isinstance(spec, _GroupSpec):
            group = PropertyGroup(
                _tdsb=ProxyBody(
                    enabled=1,
                    locked_ratio=0,
                    roto_bezier=0,
                    dimensions_separated=0,
                ),
                match_name=spec.match_name,
                auto_name=spec.auto_name,
                property_depth=child_depth,
                properties=[],
                parent_property=container,
            )
            ordered.append(group)
        else:
            v, d = (value_overrides or {}).get(mn, (_USE_VALUE, _USE_VALUE))
            prop = Property.synthesized(
                spec,
                child_depth,
                parent_property=container,
                value=v,
                default_value=d,
            )
            ordered.append(prop)

    if tail_mode != "none":
        spec_match_names = {s.match_name for s in specs}
        for child in container.properties:
            if child.match_name not in spec_match_names:
                if tail_mode == "all" or isinstance(child, PropertyGroup):
                    ordered.append(child)

    container.properties = ordered  # type: ignore[assignment]


_INDEXED_GROUP_MATCH_NAMES: set[str] = {
    "ADBE Effect Parade",
    "ADBE Mask Parade",
    "ADBE Effect Mask Parade",
    "ADBE Text Animators",
}


class PropertyGroup(PropertyBase):
    """The `PropertyGroup` object represents a group of properties. It can contain
    [Property][] objects and other `PropertyGroup` objects. Property groups can
    be nested to provide a parent-child hierarchy, with a [Layer][] object at the
    top (root) down to a single [Property][] object, such as the mask feather of
    the third mask. To traverse the group hierarchy, use [PropertyBase][] methods
    and attributes; see `PropertyBase.propertyGroup()`. For examples of how to
    access properties and property groups, see [PropertyBase][] object.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        comp = app.project.compositions[0]
        effects = comp.layers[0].effects
        if effects is not None:
            for effect in effects:
                ...
        ```

    Info:
        `PropertyGroup` is a subclass of [PropertyBase][]. All methods and
        attributes of [PropertyBase][] are available when working with
        `PropertyGroup`.

    Info:
        `PropertyGroup` is a base class for [Layer][] and `MaskPropertyGroup`.
        `PropertyGroup` attributes and methods are available when working with
        layer or mask groups.

    See: https://ae-scripting.docsforadobe.dev/property/propertygroup/
    """

    properties: list[Property | PropertyGroup]
    """List of properties in this group. Read-only."""

    def __init__(
        self,
        *,
        _tdgp: Aep.ListBody | None = None,
        _tdsb: Aep.TdsbBody | None,
        _name_utf8: Aep.Utf8Body | None = None,
        _fnam_utf8: Aep.Utf8Body | None = None,
        parent_property: PropertyGroup | Any | None = None,
        match_name: str,
        property_depth: int,
        properties: list[Property | PropertyGroup],
        auto_name: str | None = None,
    ) -> None:
        super().__init__(
            _tdsb=_tdsb,
            _name_utf8=_name_utf8,
            parent_property=parent_property,
            match_name=match_name,
            property_depth=property_depth,
            auto_name=auto_name,
        )

        self._tdgp = _tdgp
        self._fnam_utf8 = _fnam_utf8

        self.properties = properties

        for child in self.properties:
            child._parent_property = self

        if match_name in _INDEXED_GROUP_MATCH_NAMES:
            self._property_type = PropertyType.INDEXED_GROUP

        if match_name in ("ADBE Effect Mask Parade", "ADBE Vectors Group"):
            self._elided = True
        elif match_name == "ADBE Text Animators" and not properties:
            self._elided = True

    @property
    def auto_name(self) -> str:
        """The automatic (display) name derived from `match_name`."""
        if self._auto_name is not None:
            return self._auto_name
        if self._fnam_utf8 is not None:
            name: str = self._fnam_utf8.contents.split("\0")[0]
            return name
        return MATCH_NAME_TO_AUTO_NAME.get(self.match_name, self.match_name)

    def _ensure_materialized(self) -> None:
        """Replace ProxyBody backing with real Kaitai chunks.

        Called automatically by `__setattr__` on first end-user write
        to a synthesized group. Creates a tdmn + LIST:tdgp in the
        parent's _tdgp, with a group-level tdsb inside. After this,
        child properties can materialize into this group's _tdgp.
        """
        if not isinstance(self._tdsb, ProxyBody):
            return

        parent = self.parent_property
        if parent is None:
            return

        parent._ensure_materialized()

        parent_tdgp = parent._tdgp
        if parent_tdgp is None:
            return

        result = materialize_group(
            parent_tdgp, self.match_name, self._tdsb, display_name=self._name
        )
        object.__setattr__(self, "_tdsb", result.tdsb)
        object.__setattr__(self, "_tdgp", result.tdgp)
        object.__setattr__(self, "_name_utf8", result.name_utf8)

    def __iter__(self) -> typing.Iterator[Property | PropertyGroup]:
        """Return an iterator over the properties in this group."""
        return iter(self.properties)

    def __len__(self) -> int:
        """Return the number of child properties in this group."""
        return len(self.properties)

    def __getattr__(self, name: str) -> Property | PropertyGroup:
        """Look up a child property by attribute access.

        Converts the Python `snake_case` attribute name to match
        against the lowered, underscore-separated display names of
        child properties.  This allows natural syntax such as:

        ```python
        layer.transform.position.value
        layer.transform.anchor_point.value
        ```

        Note:
            Only invoked when normal attribute lookup has already
            failed, so class attributes and `@property` descriptors
            always take priority.
        """
        # Avoid infinite recursion during __init__ (before
        # `properties` has been set on the instance).
        try:
            object.__getattribute__(self, "properties")
        except AttributeError:
            raise AttributeError(name) from None
        try:
            return self[name]
        except KeyError:
            raise AttributeError(
                f"'{type(self).__name__}' has no property '{name}'"
            ) from None

    def __getitem__(self, key: int | str) -> Property | PropertyGroup:
        """Look up a child property by index or name.

        This is the canonical access method. Both `property()` and
        `__getattr__` (snake_case attribute access) delegate here.

        Example:
            ```python
            layer["ADBE Transform Group"]["ADBE Position"]
            layer["ADBE Masks"][0]
            layer[0]
            ```

        Args:
            key: An `int` index or a `str` display name / match name.

        Raises:
            KeyError: If the string key does not match any child.
            IndexError: If the integer index is out of range.
            TypeError: If *key* is neither `int` nor `str`.
        """
        if isinstance(key, int):
            return self.properties[key]
        if isinstance(key, str):
            for prop in self.properties:
                if (
                    prop.name == key
                    or prop.match_name == key
                    or prop.name.lower().replace(" ", "_") == key
                ):
                    return prop
            raise KeyError(key)
        raise TypeError(f"Property key must be int or str, not {type(key).__name__}")

    @property
    def is_modified(self) -> bool:
        """`True` if any child property is modified.

        For indexed groups (such as Effects or Masks parades), the group
        is considered modified when it has any children - adding items to
        an indexed group is itself a modification.  Shape vector groups
        (Contents) follow the same rule.
        """
        if self.property_type == PropertyType.INDEXED_GROUP and not self.is_effect:
            return len(self.properties) > 0
        if self.match_name == "ADBE Vectors Group" and len(self.properties) > 0:
            return True
        return any(child.is_modified for child in self.properties)

    @property
    def num_properties(self) -> int:
        """The number of child properties in this group.

        Equivalent to ExtendScript `PropertyGroup.numProperties`.
        """
        return len(self.properties)

    def property(self, key: int | str) -> Property | PropertyGroup:
        """Look up a child property by index or name.

        Mirrors ExtendScript `PropertyGroup.property(indexOrName)`.
        Delegates to `__getitem__`.

        Args:
            key: An `int` index or a `str` display name / match name.
        """
        return self[key]

    def _apply_min_max_bounds(self) -> None:
        """Set `min_value`/`max_value` on properties with known bounds.

        Walks all children recursively and applies overrides from
        `_PROPERTY_MIN_MAX` unconditionally.  Uses fallback fields
        so the binary tdum/tduM chunks are not mutated.
        """
        for child in self.properties:
            if isinstance(child, Property):
                bounds = _PROPERTY_MIN_MAX.get(child.match_name)
                if bounds is not None:
                    child._min_value_fallback = bounds[0]
                    child._max_value_fallback = bounds[1]
            elif isinstance(child, PropertyGroup):
                child._apply_min_max_bounds()

    def _synthesize_children(self) -> None:
        """Synthesize missing children in this standard property group.

        Uses `_reorder_and_fill` for groups with known canonical children,
        or a specialized handler for layer styles.  For Layer Styles, also
        derives the collapsed `enabled` state: ExtendScript reports the
        group as disabled when no individual style is enabled, and Blend
        Options mirrors the parent.
        """
        specs = _GROUP_CHILD_SPECS.get(self.match_name)
        if specs is not None:
            _reorder_and_fill(self, specs, self.property_depth + 1)
            # Don't return: recurse into preserved sub-groups below.

        if self.match_name == "ADBE Layer Styles":
            any_style_enabled = False
            blend_options: PropertyGroup | None = None
            for child in self.properties:
                if not isinstance(child, PropertyGroup):
                    continue
                child_specs = _LAYER_STYLE_CHILD_SPECS.get(child.match_name)
                if child_specs is not None:
                    _reorder_and_fill(child, child_specs, child.property_depth + 1)
                # Blend Options mirrors the parent; skip for the check
                if child.match_name == "ADBE Blend Options Group":
                    blend_options = child
                elif child.enabled:
                    any_style_enabled = True
            # Avoid mutating chunk fields (preserves round-trip)
            self.__dict__["enabled"] = any_style_enabled
            if blend_options is not None:
                blend_options.__dict__["enabled"] = any_style_enabled

        for child in self.properties:
            if isinstance(child, PropertyGroup):
                child._synthesize_children()
