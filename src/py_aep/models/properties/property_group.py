from __future__ import annotations

from typing import TYPE_CHECKING, Any

from py_aep.data.effect_controls import EXPRESSION_CONTROLS
from py_aep.data.match_names import MATCH_NAME_TO_AUTO_NAME
from py_aep.enums import PropertyType
from py_aep.resolvers.can_add_property import AddableKind, resolve_addable
from py_aep.resolvers.can_add_property import (
    can_add_property as _can_add_property,
)

from ...ae_version import get_ae_version_major, requires_version
from ...binary.chunk import ListChunk
from ...binary.mutations import (
    build_dropdown_control,
    build_expression_control,
    build_text_animator,
    build_text_selector,
    build_vector_element,
    clone_chunk_tree,
    rewrite_owner_tdpi,
)
from ...binary.property_chunks import (
    TDSN_SENTINEL,
    TdmnChunk,
    TdsbChunk,
    TdsnChunk,
    TdumChunk,
    VfdnChunk,
    tdb4_apply_vf_axis_template,
)
from ...binary.scalar_chunks import Utf8Chunk
from ...binary.utils import ChunkNotFoundError, find_by_list_type, index_by_identity
from ...data.dropdown_control import DROPDOWN_CONTROL
from ...resolvers.font_axes import read_design_axes
from ...resolvers.transform import default_camera_zoom
from ...svg.fonts import resolve_font_exact
from ...synthesis.property import (
    _GROUP_CHILD_SPECS,
    _LAYER_STYLE_CHILD_SPECS,
    _USE_VALUE,
    GroupSpec,
)
from ..validators import validate_string
from .overrides import _PROPERTY_MIN_MAX
from .property import Property, _values_equal, _vf_tag_from_str
from .property_base import _INDEXED_GROUP_MATCH_NAMES, PropertyBase

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from typing import Literal

    from ...synthesis.property import PropSpec
    from .mask_property_group import MaskPropertyGroup


# Mandatory empty subgroups AE writes inside some freshly added shape
# elements, as (match name, tdsb lock flags, tdsb enable flags) triples. A
# group's own contents carries lock-flag 0x04, like the Root Vectors Group.
# Enable-flags is 1 (enabled) except the Materials Group, which AE writes
# as 3 (enabled + collapsed) - matching its default-collapsed UI state.
_STROKE_SUBGROUPS: tuple[tuple[str, int, int], ...] = (
    ("ADBE Vector Stroke Dashes", 0, 1),
    ("ADBE Vector Stroke Taper", 0, 1),
    ("ADBE Vector Stroke Wave", 0, 1),
)
_VECTOR_SUBGROUPS: dict[str, tuple[tuple[str, int, int], ...]] = {
    "ADBE Vector Group": (
        ("ADBE Vectors Group", 4, 1),
        ("ADBE Vector Transform Group", 0, 1),
        ("ADBE Vector Materials Group", 0, 3),
    ),
    "ADBE Vector Graphic - Stroke": _STROKE_SUBGROUPS,
    "ADBE Vector Graphic - G-Stroke": _STROKE_SUBGROUPS,
    "ADBE Vector Filter - Repeater": (("ADBE Vector Repeater Transform", 0, 1),),
    "ADBE Vector Filter - Wiggler": (("ADBE Vector Wiggler Transform", 0, 1),),
}

# AE's creation names for shape elements, where they differ from the
# auto-name table ("Rectangle Path 1" vs auto-name "Rectangle").
_VECTOR_CREATION_NAMES: dict[str, str] = {
    "ADBE Vector Shape - Rect": "Rectangle Path",
    "ADBE Vector Shape - Ellipse": "Ellipse Path",
    "ADBE Vector Shape - Star": "Polystar Path",
}

# Per-type creation-name base for text selectors. The Range Selector
# also carries an empty Advanced subgroup in binary.
_TEXT_SELECTOR_NAMES: dict[str, str] = {
    "ADBE Text Selector": "Range Selector",
    "ADBE Text Wiggly Selector": "Wiggly Selector",
    "ADBE Text Expressible Selector": "Expression Selector",
}


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


def _effect_tdgp(sspc: ListChunk) -> ListChunk | None:
    """The instance `tdgp` (param container) inside an effect sspc."""
    try:
        return find_by_list_type(sspc.chunks, "tdgp")
    except ChunkNotFoundError:
        return None


def _set_effect_instance_name(sspc: ListChunk, name: str) -> None:
    """Replace the instance display name (tdsn) in a cloned effect sspc."""
    tdgp = _effect_tdgp(sspc)
    if tdgp is None:
        return
    for i, inner in enumerate(tdgp.chunks):
        if inner.chunk_type == "tdsn":
            tdgp.chunks[i] = TdsnChunk.new(name)
            return


def _reset_to_default_values(group: PropertyGroup) -> None:
    """Reset every value leaf of a freshly cloned effect to its default.

    AE's EfdG definition mirrors the project's first applied instance -
    including edited values, keyframes, and expressions - but
    `addProperty` must produce a static, default-valued instance. Each
    leaf is de-animated (keyframes removed) and stripped of any
    expression, then leaves whose value still differs from the `pard`
    default are reset. Leaves with no known default keep their value but
    are still de-animated / de-expressioned.

    Known limitation: 2D/3D point value params (e.g. a Lens Flare's
    Flare Center, a Point Control) carry no canonical default in the
    `pard` - AE's effect plugin defines it and it is not stored in the
    file - so their static value cannot be reset and is inherited from
    the source instance. Scalar/slider/angle/color/enum params all carry
    a stored default and reset correctly.
    """
    for child in group.properties:
        if isinstance(child, PropertyGroup):
            _reset_to_default_values(child)
            continue
        # Removing the last keyframe reverts the leaf to a static value,
        # so the value setter (which rejects keyframed properties) can run.
        while child.keyframes:
            child.remove_key(0)
        child._clear_expression()
        if child.default_value is not None and not _values_equal(
            child.value, child.default_value
        ):
            # Use the parse-path writer, not the public `value` setter: an
            # enum/popup leaf's stored default can sit below its own pard min
            # (e.g. a no-selection 0 with min=1), which the validating setter
            # would reject - here we are restoring AE's own default, not taking
            # user input, so validation must not run.
            child._cache_value(child.default_value)


def _reorder_and_fill(
    container: PropertyGroup,
    specs: Sequence[PropSpec | GroupSpec],
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
    (for `PropSpec`) or as empty `PropertyGroup` instances (for `GroupSpec`).

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
            if not isinstance(spec, GroupSpec) and isinstance(child, Property):
                child.__dict__["_color"] = spec.color
                if spec.chunk_bounds_are_hints:
                    # tdum/tduM hold UI slider hints, not real bounds:
                    # the spec is authoritative (None = unbounded).
                    child._min_value_fallback = spec.min_value
                    child._max_value_fallback = spec.max_value
                else:
                    if spec.min_value is not None:
                        child._min_value_fallback = spec.min_value
                    if spec.max_value is not None:
                        child._max_value_fallback = spec.max_value
                if spec.can_vary_over_time is not None:
                    child._can_vary_over_time = spec.can_vary_over_time
                if spec.units_text is not None:
                    child._units_text = spec.units_text
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
        elif isinstance(spec, GroupSpec):
            group = PropertyGroup._new(
                spec.match_name,
                spec.auto_name,
                child_depth,
                parent_property=container,
                synthetic=True,
                enable_flags=spec.enable_flags,
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
        enable_flags: int = 1,
    ) -> PropertyGroup:
        """Create a synthetic empty PropertyGroup with backing chunks.

        Args:
            match_name: The property's match name.
            auto_name: The display name for the group.
            property_depth: The depth of the group in the tree.
            parent_property: The container that owns the synthesized group.
            synthetic: If True, mark backing chunks as synthetic
                (skipped during serialization).
            enable_flags: `tdsb` enable-flags byte (bit 0 enabled, bit 1
                collapsed). Defaults to `1` (enabled); pass `2` for a
                group AE leaves disabled (e.g. an unused layer style).
        """
        _tdsb = TdsbChunk(synthetic=synthetic)
        _tdsb._enable_flags = enable_flags
        # AE writes the unnamed sentinel; the display name resolves
        # from auto_name on the model.
        tdsn = TdsnChunk.new(TDSN_SENTINEL, synthetic=synthetic)
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

        if match_name in (
            "ADBE Effect Mask Parade",
            "ADBE Vectors Group",
            # Text-animator structural containers are elided in AE.
            "ADBE Text Animators",
            "ADBE Text Selectors",
            "ADBE Text Animator Properties",
        ):
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
                if c.chunk_type == "tdsn":
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
            _reorder_and_fill(
                self,
                specs,
                self.property_depth + 1,
                ae_major=ae_major,
                value_overrides=self._synthesis_value_overrides(),
            )

        if self.match_name == "ADBE Layer Styles":
            _derive_layer_styles_enabled(self, ae_major, synthesize_subgroups=True)

        for child in self._properties:
            if isinstance(child, PropertyGroup):
                child._deferred_ae_major = ae_major
            elif isinstance(child, Property):
                _apply_bounds(child)

    def _synthesis_value_overrides(
        self,
    ) -> dict[str, tuple[Any, Any]] | None:
        """Comp-dependent default values for synthesized children.

        Camera Zoom and Focus Distance default to AE's 50mm-lens zoom
        (`comp width * pixel aspect / 0.72`), a value the static spec table
        cannot express. Returns `None` for groups with no comp-dependent
        defaults.
        """
        if self.match_name != "ADBE Camera Options Group":
            return None
        try:
            comp = self._containing_layer.containing_comp
            width = comp.width
            pixel_aspect = comp.pixel_aspect
        except (ValueError, AttributeError):
            return None
        # AE rounds the zoom to 8 decimals before storing it.
        zoom = round(default_camera_zoom(width, pixel_aspect), 8)
        return {
            "ADBE Camera Zoom": (zoom, zoom),
            "ADBE Camera Focus Distance": (zoom, zoom),
        }

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
        # Essential Properties override groups report modified whenever they
        # hold any override, independent of whether a leaf differs from its
        # source value (AE treats having an override as a modification).
        if (
            self.match_name in ("ADBE Layer Overrides", "ADBE Layer Overrides Group")
            and len(self.properties) > 0
        ):
            return True
        # A parametric-mesh Material Assignment parade reports modified
        # whenever it holds a material atom (like an indexed group), even
        # when the atom's own streams are all at default. (AE 2026.)
        if self.match_name == "ADBE3D Para Mat Parade":
            return len(self.properties) > 0
        return any(child.is_modified for child in self.properties)

    @property
    def num_properties(self) -> int:
        """The number of child properties in this group.

        Equivalent to ExtendScript `PropertyGroup.numProperties`.
        """
        return len(self.properties)

    def remove_all_keys(self) -> None:
        """Remove every keyframe from all properties in this group,
        recursively.

        Calling this on a [Layer][] clears the keyframes of every
        property on the layer, including its marker keyframes. Each
        animated property reverts to a static value; see
        `Property.remove_all_keys`.
        """
        for child in self._properties:
            child.remove_all_keys()

    def can_add_property(self, name: str) -> bool:
        """Check whether a property with the given name can be added.

        Returns `True` if this group is an indexed group and `name` is
        a valid match name or display name for the group type. For the
        Effect Parade, the expression controls py_aep can create plus
        any effect already defined in the project (`LIST:EfdG`) are
        accepted.

        Args:
            name: A match name or display name to check.
        """
        if _can_add_property(self.match_name, self.property_type, name):
            return True
        return self._installed_effect_def(name) is not None

    @requires_version(26)
    def add_variable_font_axis(
        self,
        axis_tag: str,
        font_file: str | None = None,
    ) -> Property:
        """Create and return a [Property][] for a variable font axis, and
        add it to this group.

        Mirrors ExtendScript `PropertyGroup.addVariableFontAxis()`. Can
        only be called on the `ADBE Text Animator Properties` group
        within a text animator. The axis binds to the first free of the
        8 `ADBE Text VF Axis` slots; calling it again with an already
        active tag returns the existing property.

        The axis bounds, default value, and display name are read from
        the variable font file with fontTools (After Effects reads them
        from the installed font; the project file does not store a font
        path). Pass `font_file` explicitly, or leave it `None` to locate
        the installed font from the text document's font family.

        Note:
            This functionality was added in After Effects 26.0.

        Args:
            axis_tag: The 4-character tag identifying the variable font
                axis (e.g. `wght`, `wdth`, `slnt`, `ital`, `opsz`).
            font_file: Optional path to the variable font file. When
                `None`, the font is located in the OS font directories
                by the text document's font family.

        Raises:
            ValueError: If this group is not a text animator Properties
                group, the font cannot be located or is not a variable
                font, `axis_tag` is not one of the font's axes, or all
                8 axis slots are in use.
        """
        validate_string(axis_tag)
        if len(axis_tag) != 4:
            raise ValueError("axis_tag must be a 4-character tag (e.g. 'wght').")
        if self.match_name != "ADBE Text Animator Properties":
            raise ValueError(
                "add_variable_font_axis() can only be called on the "
                "'ADBE Text Animator Properties' group of a text animator."
            )
        # Typed Any: `.text.source_text` only resolves on a text layer.
        layer: Any = self._containing_layer

        font_number = 0
        if font_file is None:
            # The .aep stores only the PostScript name; its prefix is the
            # variable font's family (FontObject.familyPrefix semantics).
            text_doc = layer.text.source_text.value
            ps_name: str = text_doc.font or ""
            family = ps_name.split("-", 1)[0]
            resolved = resolve_font_exact(family) if family else None
            if resolved is None:
                raise ValueError(
                    f"Could not locate an installed font for family "
                    f"{family!r}; pass font_file explicitly."
                )
            font_file, font_number = str(resolved[0]), resolved[1]
        axes = read_design_axes(font_file, font_number)
        axis = next((a for a in axes if a.tag == axis_tag), None)
        if axis is None:
            available = ", ".join(a.tag for a in axes)
            raise ValueError(
                f"The font has no {axis_tag!r} axis (available: {available})."
            )

        slots = [
            p for p in self._properties if isinstance(p, Property) and p._is_vf_axis
        ]
        for p in slots:
            if p.axis_tag == axis_tag:
                return p
        slot = next((p for p in slots if p.axis_tag is None), None)
        if slot is None:
            raise ValueError("All 8 variable-font axis slots are in use.")

        slot._ensure_materialized()
        tag_raw = float(_vf_tag_from_str(axis_tag))
        tdbs = slot._tdbs
        tdb4_apply_vf_axis_template(slot._tdb4)
        assert slot._cdat is not None
        # AE writes [value, tag] plus eight zero-padding slots.
        slot._cdat.values = [axis.default_value, tag_raw] + [0.0] * 8
        slot._value = None
        # Axis bounds come from the font's range (single-component).
        for attr, chunk_type, bound in (
            ("_tdum", "tdum", axis.min_value),
            ("_tduM", "tduM", axis.max_value),
        ):
            existing = getattr(slot, attr)
            if existing is None:
                existing = TdumChunk(chunk_type=chunk_type, values=[bound])
                tdbs.chunks.append(existing)
                setattr(slot, attr, existing)
            else:
                existing.values = [bound]
        # AE stores the axis display name in a vfdn sibling after the tdbs.
        vfdn = VfdnChunk.new(f"Font Axis {axis.name}")
        assert self._tdgp is not None
        self._tdgp.chunks.insert(index_by_identity(self._tdgp.chunks, tdbs) + 1, vfdn)
        slot._vfdn = vfdn
        slot._vf_tag_cache = tag_raw
        return slot

    def add_property(self, name: str) -> Property | PropertyGroup:
        """Create and return a new property with the specified name,
        and add it to this group.

        Indexed groups (and, as a named-group exception, the text
        animator `Properties` pool) support adding properties; see
        `can_add_property`. Accepted names cover every ExtendScript
        addable family: mask atoms (`ADBE Mask Atom` / `Mask`), the
        expression controls including the Dropdown Menu Control (e.g.
        `ADBE Slider Control` / `Slider Control`, `ADBE Dropdown
        Control`), shape elements on a contents group (e.g.
        `ADBE Vector Shape - Rect`, `ADBE Vector Group`), text
        selectors (e.g. `ADBE Text Selector` / `Range Selector`), text
        animators (`ADBE Text Animator` / `Animator`), and animator
        properties from the fixed pool (e.g. `ADBE Text Position 3D` /
        `Position`).

        Note:
            Unlike ExtendScript, adding a property does not invalidate
            existing references to the group's other properties.

        Args:
            name: The display name or match name of the property to
                add.

        Raises:
            ValueError: If a property with this name cannot be added
                to this group.
        """
        result = resolve_addable(self.match_name, self.property_type, name)
        if result is None:
            # Effect Parade: any effect already defined in the project's
            # EfdG (re-applied by cloning its stored definition).
            installed = self._installed_effect_def(name)
            if installed is not None:
                return self._add_installed_effect(*installed)
            raise ValueError(
                f"Cannot add property '{name}' to group '{self.match_name}'"
            )
        resolved, kind = result
        if kind is AddableKind.MASK:
            return self._add_mask_atom()
        if kind is AddableKind.EXPRESSION_CONTROL:
            return self._add_expression_control(resolved)
        if kind is AddableKind.DROPDOWN:
            return self._add_dropdown_control()
        if kind is AddableKind.SHAPE:
            return self._add_vector_element(resolved)
        if kind is AddableKind.TEXT_SELECTOR:
            return self._add_text_selector(resolved)
        if kind is AddableKind.TEXT_ANIMATOR:
            return self._add_text_animator()
        if kind is AddableKind.ANIMATOR_PROPERTY:
            return self._add_animator_property(resolved)
        # Exhaustiveness guard: resolve_addable returns one of the seven
        # AddableKind members, each handled above. Reached only if a new
        # kind is added without a dispatch arm.
        raise NotImplementedError(f"no add_property builder for '{resolved}'")

    def _free_numbered_name(self, base: str, start: int) -> str:
        """`'{base} {n}'` with `n >= start`, skipping any number already
        used by a sibling so a new instance never duplicates an existing
        name. AE numbers same-type instances per container, but a count+1
        scheme collides once an instance is removed or the existing names
        are non-contiguous (e.g. `['Stroke 1', 'Stroke 3']`).
        """
        existing = {p.name for p in self.properties}
        n = start
        while f"{base} {n}" in existing:
            n += 1
        return f"{base} {n}"

    def _effect_instance_name(self, display: str, same_type: int) -> str:
        """The tdsn name for a new effect instance: the first instance uses
        the unnamed sentinel (so it shows the effect's own name); later ones
        get a baked `"{display} N"`. `same_type` is the count of existing
        instances (counted per match name, or per pseudo-effect namespace
        for the Dropdown Control)."""
        if same_type == 0:
            return TDSN_SENTINEL
        return self._free_numbered_name(display, same_type + 1)

    def _add_mask_atom(self) -> MaskPropertyGroup:
        """Add a new default mask atom to this Masks parade group."""
        from .mask_property_group import MaskPropertyGroup  # noqa: PLC0415

        self._ensure_materialized()
        # AE assigns a monotonic per-layer mask id (highest existing + 1),
        # not a positional count: len+1 collides after a mid-parade mask is
        # removed, or on a parsed layer whose mask ids are non-contiguous.
        existing = [m for m in self.properties if isinstance(m, MaskPropertyGroup)]
        next_id = max((m._mkif.mask_id for m in existing), default=0) + 1
        mask = MaskPropertyGroup._new(
            self,
            self.property_depth + 1,
            name=f"Mask {next_id}",
            mask_id=next_id,
        )
        self._properties.append(mask)
        return mask

    def _add_expression_control(self, match_name: str) -> PropertyGroup:
        """Add a fresh expression-control effect to this Effect Parade."""
        skeleton = EXPRESSION_CONTROLS[match_name]
        self._ensure_materialized()
        comp = self._containing_layer.containing_comp

        # AE names the first instance after the effect (unnamed tdsn
        # sentinel) and later instances "Name N" with a baked tdsn.
        display: str = skeleton["name"]
        same_type = sum(1 for p in self.properties if p.match_name == match_name)
        tdsn_name = self._effect_instance_name(display, same_type)

        tdmn, sspc = build_expression_control(
            match_name,
            display,
            bytes.fromhex(skeleton["part"]),
            tdsn_name=tdsn_name,
            time_base=comp._cdta.internal_timebase,
            layer_id=self._containing_layer.id,
            layer_param_name=skeleton["layer_param"],
        )
        return self._attach_effect(tdmn, sspc, match_name)

    def _add_dropdown_control(self) -> PropertyGroup:
        """Add a fresh Dropdown Menu Control to this Effect Parade.

        The Dropdown Menu Control is a pseudo-effect with a per-instance
        generated match name, so AE's "Name N" numbering counts existing
        dropdowns by the `Pseudo/` namespace rather than by match name.
        """
        self._ensure_materialized()
        comp = self._containing_layer.containing_comp

        display = DROPDOWN_CONTROL["name"]
        same_type = sum(
            1 for p in self.properties if p.match_name.startswith("Pseudo/@@")
        )
        tdsn_name = self._effect_instance_name(display, same_type)

        tdmn, sspc = build_dropdown_control(
            tdsn_name=tdsn_name,
            time_base=comp._cdta.internal_timebase,
            layer_id=self._containing_layer.id,
        )
        return self._attach_effect(tdmn, sspc, tdmn.value)

    def _installed_effect_def(self, name: str) -> tuple[str, str, ListChunk] | None:
        """Resolve `name` to an effect defined in the project's EfdG.

        Only the Effect Parade can host installed effects. Returns
        `(match_name, display_name, def_sspc)` for a project-defined
        effect, else `None`.
        """
        from ...parsers.effect import match_effect_definition  # noqa: PLC0415

        if self.match_name != "ADBE Effect Parade":
            return None
        project = self._containing_layer.containing_comp._project
        return match_effect_definition(project._effect_definitions(), name)

    def _add_installed_effect(
        self, match_name: str, display: str, def_sspc: ListChunk
    ) -> PropertyGroup:
        """Add an effect already defined in the project by cloning its
        `LIST:EfdG` definition.

        The stored definition is a complete sspc template, so cloning it
        and retargeting the hidden `-0000` internal param to this layer
        yields a valid applied effect. AE's EfdG entry mirrors the first
        applied instance (including edited values and keyframes), so the
        value parameters are de-animated and reset to their `pard`
        defaults to match `addProperty`'s static, default-valued
        semantics.
        """
        self._ensure_materialized()
        sspc = clone_chunk_tree(def_sspc)
        assert isinstance(sspc, ListChunk)
        rewrite_owner_tdpi(sspc, layer_id=self._containing_layer.id)

        # Name the instance: the first uses the unnamed tdsn sentinel
        # (so it shows the effect's fnam name); later ones get "Name N".
        same_type = sum(1 for p in self.properties if p.match_name == match_name)
        tdsn_name = self._effect_instance_name(display, same_type)
        _set_effect_instance_name(sspc, tdsn_name)

        effect = self._attach_effect(TdmnChunk(value=match_name), sspc, match_name)
        _reset_to_default_values(effect)
        return effect

    def _attach_effect(
        self, tdmn: TdmnChunk, sspc: ListChunk, match_name: str
    ) -> PropertyGroup:
        """Insert a built effect's chunks, parse, wire the model, append.

        `parse_effect` is the canonical chunks->model path for effects
        (param-def merging, child synthesis); `duplicate()` uses it too.
        """
        from ...parsers.effect import parse_effect  # noqa: PLC0415

        layer = self._containing_layer
        comp = layer.containing_comp
        parent_tdgp = self._tdgp
        assert parent_tdgp is not None
        _insert_before_group_end(parent_tdgp, tdmn)
        _insert_before_group_end(parent_tdgp, sspc)

        effect_param_defs = comp._project._effect_param_defs
        effect = parse_effect(
            sspc_chunk=sspc,
            group_match_name=match_name,
            property_depth=self.property_depth + 1,
            effect_param_defs=effect_param_defs,
            composition=comp,
            tdmn=tdmn,
        )
        effect._parent_property = self
        effect._deferred_ae_major = get_ae_version_major(layer)
        self._properties.append(effect)
        return effect

    def _attach_group(
        self, tdmn: TdmnChunk, tdgp: ListChunk, match_name: str
    ) -> PropertyGroup:
        """Insert a built group's chunks, parse, wire the model, append.

        `parse_property_group` is the canonical chunks->model path for
        added groups (mandatory subgroups, the Path element's om-s,
        deferred child synthesis); the shape, selector and animator
        builders share it, as `_attach_effect` does for effects.
        """
        from ...parsers.property import parse_property_group  # noqa: PLC0415

        layer = self._containing_layer
        comp = layer.containing_comp
        parent_tdgp = self._tdgp
        assert parent_tdgp is not None
        _insert_before_group_end(parent_tdgp, tdmn)
        _insert_before_group_end(parent_tdgp, tdgp)

        group = parse_property_group(
            tdgp_chunk=tdgp,
            group_match_name=match_name,
            property_depth=self.property_depth + 1,
            effect_param_defs=comp._project._effect_param_defs,
            composition=comp,
            tdmn=tdmn,
        )
        group._parent_property = self
        group._deferred_ae_major = get_ae_version_major(layer)
        self._properties.append(group)
        return group

    def _add_vector_element(self, match_name: str) -> PropertyGroup:
        """Add a fresh shape element to this contents group."""
        self._ensure_materialized()
        comp = self._containing_layer.containing_comp

        # AE bakes a per-container, per-type numbered name into the tdsn.
        base = _VECTOR_CREATION_NAMES.get(match_name) or MATCH_NAME_TO_AUTO_NAME.get(
            match_name, match_name
        )
        same_type = sum(1 for p in self.properties if p.match_name == match_name)
        path_time_base = (
            comp._cdta.internal_timebase
            if match_name == "ADBE Vector Shape - Group"
            else None
        )
        tdmn, tdgp = build_vector_element(
            match_name,
            self._free_numbered_name(base, same_type + 1),
            subgroups=_VECTOR_SUBGROUPS.get(match_name, ()),
            path_time_base=path_time_base,
        )
        return self._attach_group(tdmn, tdgp, match_name)

    def _add_animator_property(self, match_name: str) -> Property | PropertyGroup:
        """Apply an animator property from the fixed pool (the
        named-group exception).

        The `ADBE Text Animator Properties` group exposes a fixed pool
        of synthesized members; unlike indexed groups, "adding" one
        materializes the existing member in place (it keeps its pool
        position) rather than appending a new child. Idempotent: adding
        an already-applied property is a no-op, as in AE.
        """
        prop = next((p for p in self.properties if p.match_name == match_name), None)
        # resolve_addable returns only pool match names, so the member exists.
        assert prop is not None
        prop._ensure_materialized()
        return prop

    def _add_text_animator(self) -> PropertyGroup:
        """Add a fresh animator to this Text Animators group.

        A new animator is a minimal `[Animator N, Properties (empty)]`
        container; its (empty) Selectors group and the 103-property
        Properties pool are synthesized on parse.
        """
        self._ensure_materialized()
        same_type = sum(
            1 for p in self.properties if p.match_name == "ADBE Text Animator"
        )
        tdmn, tdgp = build_text_animator(
            self._free_numbered_name("Animator", same_type + 1)
        )
        return self._attach_group(tdmn, tdgp, "ADBE Text Animator")

    def _add_text_selector(self, match_name: str) -> PropertyGroup:
        """Add a fresh selector to this text animator's Selectors group.

        Like shape elements, a selector is a minimal named group whose
        value children are synthesized; the Range Selector additionally
        carries an empty `ADBE Text Range Advanced` subgroup in binary.
        """
        self._ensure_materialized()
        base = _TEXT_SELECTOR_NAMES[match_name]
        same_type = sum(1 for p in self.properties if p.match_name == match_name)
        tdmn, tdgp = build_text_selector(
            match_name,
            self._free_numbered_name(base, same_type + 1),
            has_advanced=match_name == "ADBE Text Selector",
        )
        return self._attach_group(tdmn, tdgp, match_name)

    def property(self, key: int | str) -> Property | PropertyGroup:
        """Look up a child property by index or name.

        Args:
            key: An `int` index or a `str` display name / match name.
        """
        # NOTE This property needs to be defined last to avoid ghosting the
        # @property decorator
        return self[key]
