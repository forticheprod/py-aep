from __future__ import annotations

from typing import TYPE_CHECKING, Any

from py_aep.data.match_names import MATCH_NAME_TO_AUTO_NAME
from py_aep.enums import PropertyType
from py_aep.resolvers.can_add_property import (
    can_add_property as _can_add_property,
)

from ...binary.chunk import ListChunk
from ...binary.property_chunks import TdmnChunk, TdsbChunk, TdsnChunk
from ...binary.scalar_chunks import Utf8Chunk
from ...synthesis.specs import (
    _GROUP_CHILD_SPECS,
    _LAYER_STYLE_CHILD_SPECS,
    _USE_VALUE,
    _GroupSpec,
)
from .overrides import _PROPERTY_MIN_MAX
from .property import Property
from .property_base import _INDEXED_GROUP_MATCH_NAMES, _TDSN_SENTINEL, PropertyBase

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from typing import Literal

    from ...synthesis.specs import _PropSpec


def _insert_before_group_end(tdgp: ListChunk, chunk: Any) -> None:
    """Insert *chunk* before the 'ADBE Group End' tdmn in *tdgp*.

    Falls back to appending if no group end marker exists.
    """
    for i in range(len(tdgp.chunks) - 1, -1, -1):
        c = tdgp.chunks[i]
        if c.chunk_type == "tdmn" and getattr(c, "value", None) == "ADBE Group End":
            tdgp.chunks.insert(i, chunk)
            return
    tdgp.chunks.append(chunk)


def _reorder_and_fill(
    container: PropertyGroup,
    specs: Sequence[_PropSpec | _GroupSpec],
    child_depth: int,
    *,
    skip: frozenset[str] = frozenset(),
    value_overrides: dict[str, tuple[Any, Any]] | None = None,
    tail_mode: Literal["none", "groups", "all"] = "groups",
    ae_major: int,
) -> None:
    """Reorder `container.properties` according to `specs`, synthesizing missing entries.

    Existing children whose match name appears in `specs` are preserved in
    canonical order. Missing children are created via `Property.synthesized`
    (for `_PropSpec`) or as empty `PropertyGroup` instances (for `_GroupSpec`).

    Args:
        container: Object whose `.properties` list is reordered/filled.
            Also set as `parent_property` on synthesized children.
        specs: Full canonical spec list (NOT pre-filtered by `skip`).
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
        elif spec.min_major is not None and spec.min_major > ae_major:
            continue
        elif isinstance(spec, _GroupSpec):
            group = PropertyGroup._new(
                spec.match_name,
                spec.auto_name,
                child_depth,
                parent_property=container,
                synthetic=True,
            )
            ordered.append(group)
        else:
            v, d = (value_overrides or {}).get(mn, (_USE_VALUE, _USE_VALUE))
            prop = Property._new(
                spec,
                child_depth,
                parent_property=container,
                value=v,
                default_value=d,
                synthetic=True,
            )
            ordered.append(prop)

    if tail_mode != "none":
        spec_match_names = {s.match_name for s in specs}
        for child in container.properties:
            if child.match_name not in spec_match_names:
                if tail_mode == "all" or isinstance(child, PropertyGroup):
                    ordered.append(child)

    container._properties = ordered
    for child in ordered:
        child._parent_property = container


def _apply_bounds(prop: Property) -> None:
    """Apply min/max override from `_PROPERTY_MIN_MAX` if one exists."""
    bounds = _PROPERTY_MIN_MAX.get(prop.match_name)
    if bounds is not None:
        prop._min_value_fallback = bounds[0]
        prop._max_value_fallback = bounds[1]


def _derive_layer_styles_enabled(
    group: PropertyGroup,
    ae_major: int,
    *,
    synthesize_subgroups: bool,
) -> None:
    """Derive the collapsed `enabled` state for Layer Styles.

    ExtendScript reports the Layer Styles group as disabled when no
    individual style is enabled, and Blend Options mirrors the parent.
    Synthesized (not in binary) style groups default to disabled.
    """
    any_style_enabled = False
    blend_options: PropertyGroup | None = None
    for child in group.properties:
        if not isinstance(child, PropertyGroup):
            continue
        child_specs = _LAYER_STYLE_CHILD_SPECS.get(child.match_name)
        if child_specs is not None and synthesize_subgroups:
            _reorder_and_fill(
                child, child_specs, child.property_depth + 1, ae_major=ae_major
            )
        if child.match_name == "ADBE Blend Options Group":
            blend_options = child
        elif child._tdsb is not None and child._tdsb.synthetic:
            child.__dict__["enabled"] = False
        elif child.enabled:
            any_style_enabled = True
    # Avoid mutating chunk fields (preserves round-trip)
    group.__dict__["enabled"] = any_style_enabled
    if blend_options is not None:
        blend_options.__dict__["enabled"] = any_style_enabled


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

    _properties: list[Property | PropertyGroup]

    @classmethod
    def _new(
        cls,
        match_name: str,
        auto_name: str,
        property_depth: int,
        *,
        parent_property: PropertyGroup | None = None,
        synthetic: bool = False,
    ) -> PropertyGroup:
        """Create a synthetic empty PropertyGroup with backing chunks.

        Args:
            match_name: The property's match name.
            auto_name: The display name for the group.
            property_depth: The depth of the group in the tree.
            parent_property: The container that owns the synthesized group.
            synthetic: If True, mark backing chunks as synthetic
                (skipped during serialization).
        """
        _tdsb = TdsbChunk(synthetic=synthetic)
        # AE writes the unnamed sentinel; the display name resolves
        # from auto_name on the model.
        tdsn = TdsnChunk.new(_TDSN_SENTINEL, synthetic=synthetic)
        name_utf8 = tdsn.utf8
        group_end = TdmnChunk(value="ADBE Group End", synthetic=synthetic)
        _tdgp = ListChunk(
            list_type="tdgp",
            chunks=[_tdsb, tdsn, group_end],
            synthetic=synthetic,
        )

        # Insert into parent's chunk tree (before parent's group end).
        _tdmn: TdmnChunk | None = None
        if parent_property is not None:
            parent_tdgp = getattr(parent_property, "_tdgp", None)
            if parent_tdgp is not None:
                _tdmn = TdmnChunk(
                    value=match_name,
                    synthetic=synthetic,
                )
                _insert_before_group_end(parent_tdgp, _tdmn)
                _insert_before_group_end(parent_tdgp, _tdgp)

        return cls(
            _tdmn=_tdmn,
            _tdsb=_tdsb,
            _tdgp=_tdgp,
            _name_utf8=name_utf8,
            match_name=match_name,
            auto_name=auto_name,
            property_depth=property_depth,
            properties=[],
            parent_property=parent_property,
        )

    def __init__(
        self,
        *,
        _tdmn: TdmnChunk | None = None,
        _tdgp: ListChunk | None = None,
        _tdsb: TdsbChunk | None,
        _name_utf8: Utf8Chunk | None = None,
        _fnam_utf8: Utf8Chunk | None = None,
        parent_property: PropertyGroup | None = None,
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

        self._tdmn = _tdmn
        self._tdgp = _tdgp
        self._fnam_utf8 = _fnam_utf8
        self._deferred_ae_major: int | None = None

        self._properties = properties
        for child in self._properties:
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
            name: str = self._fnam_utf8.value.split("\0")[0]
            return name
        return MATCH_NAME_TO_AUTO_NAME.get(self.match_name, self.match_name)

    def _ensure_materialized(self) -> None:
        """Flip synthetic flags so backing chunks become visible to write_aep().

        Called automatically by `ChunkField.__set__` on first end-user write
        to a synthesized group. After this method, the group is
        indistinguishable from one that was parsed from binary.
        """
        if self._tdsb is None or not self._tdsb.synthetic:
            return

        parent = self.parent_property
        if parent is not None:
            parent._ensure_materialized()

        # Flip synthetic flags on tdmn + group-owned chunks (not children).
        if self._tdmn is not None:
            self._tdmn.synthetic = False
        assert self._tdgp is not None
        self._tdgp.synthetic = False
        self._tdsb.synthetic = False
        if self._name_utf8 is not None:
            self._name_utf8.synthetic = False
            # Also unflag tdsn container if present
            for c in self._tdgp.chunks:
                if getattr(c, "chunk_type", None) == "tdsn":
                    c.synthetic = False
                    break
        # Also flip the group end marker.
        for c in self._tdgp.chunks:
            if c.chunk_type == "tdmn" and getattr(c, "value", None) == "ADBE Group End":
                c.synthetic = False
                break

        self._reposition_canonically()

    def _chunk_body(self) -> ListChunk | None:
        return self._tdgp

    def _ensure_children_synthesized(self) -> None:
        """Run deferred child synthesis exactly once, on first access."""
        ae_major = self._deferred_ae_major
        if ae_major is None:
            return
        self._deferred_ae_major = None
        self._run_deferred_synthesis(ae_major)

    def _run_deferred_synthesis(self, ae_major: int) -> None:
        """Perform full child synthesis for this group.

        Looks up child specs for the group's match name, reorders/fills
        children, and defers synthesis on child groups recursively.
        """
        specs = _GROUP_CHILD_SPECS.get(self.match_name)
        if specs is not None:
            _reorder_and_fill(self, specs, self.property_depth + 1, ae_major=ae_major)

        if self.match_name == "ADBE Layer Styles":
            _derive_layer_styles_enabled(self, ae_major, synthesize_subgroups=True)

        for child in self._properties:
            if isinstance(child, PropertyGroup):
                child._deferred_ae_major = ae_major
            elif isinstance(child, Property):
                _apply_bounds(child)

    @property
    def properties(self) -> list[Property | PropertyGroup]:
        """List of properties in this group. Read-only."""
        self._ensure_children_synthesized()
        return self._properties

    def __iter__(self) -> Iterator[Property | PropertyGroup]:
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
            object.__getattribute__(self, "_properties")
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
            TypeError: If `key` is neither `int` nor `str`.
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
        (value) follow the same rule.
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

    def can_add_property(self, name: str) -> bool:
        """Check whether a property with the given name can be added.

        Returns `True` if this group is an indexed group and `name` is
        a valid match name or display name for the group type. For
        the Effect Parade, any non-empty string is accepted (actual
        effect availability is validated at add time).

        Args:
            name: A match name or display name to check.
        """
        return _can_add_property(self.match_name, self.property_type, name)

    def property(self, key: int | str) -> Property | PropertyGroup:
        """Look up a child property by index or name.

        Mirrors ExtendScript `PropertyGroup.property(indexOrName)`.
        Delegates to `__getitem__`.

        Args:
            key: An `int` index or a `str` display name / match name.
        """
        # NOTE This property needs to be defined last to avoid ghosting the
        # @property decorator
        return self[key]
