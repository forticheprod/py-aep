from __future__ import annotations

from typing import TYPE_CHECKING, List, cast

from ...ae_version import get_ae_version_major
from ...binary.chunk import ListChunk
from ...binary.misc_chunks import MkifChunk
from ...binary.mutations import build_default_mask_shape
from ...binary.property_chunks import TdmnChunk, TdsbChunk, TdsnChunk
from ...binary.utils import find_by_list_type, find_by_type
from ...enums import MaskFeatherFalloff, MaskMode, MaskMotionBlur
from ..descriptors import ChunkField
from ..validators import validate_bool, validate_rgb_color
from .property_group import PropertyGroup, _insert_before_group_end

if TYPE_CHECKING:
    from ...binary.scalar_chunks import Utf8Chunk
    from .property import Property

# Mask outline colors cycled by creation index for new masks. AE picks
# from the label colors via an app-global counter that persists across
# sessions, so its exact choice is not reproducible from file content;
# py_aep cycles the same palette deterministically instead (RGB bytes,
# observed on AE 2026 defaults).
_MASK_COLOR_CYCLE: tuple[tuple[int, int, int], ...] = (
    (30, 64, 30),
    (181, 56, 56),
    (228, 216, 76),
    (169, 203, 199),
    (229, 188, 201),
    (169, 169, 202),
    (231, 193, 158),
    (179, 199, 179),
)


class MaskPropertyGroup(PropertyGroup):
    """An individual mask applied to a layer.

    The `MaskPropertyGroup` object encapsulates mask attributes in a layer.

    Info:
        `MaskPropertyGroup` is a subclass of PropertyGroup object. All methods and
        attributes of [PropertyBase][py_aep.models.properties.property_base.PropertyBase]
        object and [PropertyGroup][], in addition to those listed below, are available
        when working with `MaskPropertyGroup`.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        comp = app.project.compositions[0]
        layer = comp.layers[0]
        mask = layer.masks[0]
        print(mask.inverted)
        ```

    See: https://ae-scripting.docsforadobe.dev/property/maskpropertygroup/
    """

    color = ChunkField[List[float]](
        "_mkif",
        "color",
        validate=validate_rgb_color,
    )
    """The color used to draw the mask outline as it appears in the user
    interface (Composition panel, Layer panel, and Timeline panel).
    The three array values specify the red, green, and blue components
    of the color. Read / Write."""

    inverted = ChunkField.bool(
        "_mkif",
        "inverted",
    )
    """When `True`, the mask is inverted. Read / Write."""

    locked = ChunkField.bool(
        "_mkif",
        "locked",
    )
    """When `True`, the mask is locked and cannot be edited in the user
    interface. Read / Write."""

    mask_feather_falloff = ChunkField.enum(
        MaskFeatherFalloff, "_mkif", "mask_feather_falloff"
    )
    """The feather falloff mode for the mask. Applies to all feather
    values for the mask. Read / Write."""

    mask_mode = ChunkField.enum(MaskMode, "_mkif", "mode")
    """The blending mode for the mask. Controls how the mask interacts with
    other masks and with the layer below. Read / Write."""

    mask_motion_blur = ChunkField.enum(MaskMotionBlur, "_mkif", "mask_motion_blur")
    """How motion blur is applied to this mask. Read / Write."""

    @property
    def roto_bezier(self) -> bool:
        """When `True`, the mask uses RotoBezier, enabling curved mask segments
        without direction handles. Read / Write.

        The flag lives in the Mask Shape's `tdsb`. A freshly added mask has
        no Mask Shape subtree (AE treats it as the implicit default
        full-frame rectangle), so enabling RotoBezier materializes that
        default path - mirroring what After Effects writes.
        """
        tdsb = self._mask_shape_tdsb
        return bool(tdsb.roto_bezier) if tdsb is not None else False

    @roto_bezier.setter
    def roto_bezier(self, value: bool) -> None:
        validate_bool(value)
        if self._mask_shape_tdsb is None:
            if not value:
                # Already the default; AE writes no Mask Shape for this state.
                return
            self._materialize_mask_shape(roto_bezier=True)
        assert self._mask_shape_tdsb is not None
        self._mask_shape_tdsb.roto_bezier = value

    @classmethod
    def _new(  # type: ignore[override]
        cls,
        parent_property: PropertyGroup,
        property_depth: int,
        *,
        name: str,
        mask_id: int,
    ) -> MaskPropertyGroup:
        """Create a new mask atom with backing chunks, as AE writes it.

        A freshly added mask has no Mask Shape subtree in binary: AE
        treats the bare atom as the default full-frame rectangle path,
        and the child properties (Mask Path, Feather, Opacity,
        Expansion) are synthesized on first access, like a fresh parse.

        Args:
            parent_property: The Masks parade group to add the atom to.
            property_depth: The depth of the mask atom in the tree.
            name: The display name, stored in the `tdsn` (AE bakes the
                positional `Mask N` name at creation).
            mask_id: 1-based creation id, stored in the `mkif` and used
                to pick the outline color from the cycle palette.
        """
        color = _MASK_COLOR_CYCLE[(mask_id - 1) % len(_MASK_COLOR_CYCLE)]
        _tdmn = TdmnChunk(value="ADBE Mask Atom")
        _mkif = MkifChunk(
            mode=1,  # binary PF_MaskMode for MaskMode.ADD
            mask_id=mask_id,
            color_r=color[0],
            color_g=color[1],
            color_b=color[2],
        )
        _tdsb = TdsbChunk()
        tdsn = TdsnChunk.new(name)
        name_utf8 = tdsn.utf8
        group_end = TdmnChunk(value="ADBE Group End")
        _tdgp = ListChunk(list_type="tdgp", chunks=[_tdsb, tdsn, group_end])

        parent_tdgp = parent_property._tdgp
        assert parent_tdgp is not None
        _insert_before_group_end(parent_tdgp, _tdmn)
        _insert_before_group_end(parent_tdgp, _mkif)
        _insert_before_group_end(parent_tdgp, _tdgp)

        mask = cls(
            _tdmn=_tdmn,
            _tdgp=_tdgp,
            _tdsb=_tdsb,
            _mkif=_mkif,
            _mask_shape_tdsb=None,
            _name_utf8=name_utf8,
            match_name="ADBE Mask Atom",
            property_depth=property_depth,
            auto_name=name,
            properties=[],
        )
        mask._parent_property = parent_property
        mask._is_mask = True
        # Children are filled from _MASK_ATOM_SPECS on first access.
        mask._deferred_ae_major = get_ae_version_major(
            parent_property._containing_layer
        )
        return mask

    def __init__(
        self,
        *,
        _tdmn: TdmnChunk,
        _tdgp: ListChunk,
        _tdsb: TdsbChunk | None,
        _mkif: MkifChunk,
        _mask_shape_tdsb: TdsbChunk | None,
        _name_utf8: Utf8Chunk | None = None,
        match_name: str,
        property_depth: int,
        auto_name: str | None = None,
        properties: list[Property | PropertyGroup],
    ) -> None:
        super().__init__(
            _tdmn=_tdmn,
            _tdgp=_tdgp,
            _tdsb=_tdsb,
            _name_utf8=_name_utf8,
            match_name=match_name,
            auto_name=auto_name,
            property_depth=property_depth,
            properties=properties,
        )
        self._mkif = _mkif
        self._mask_shape_tdsb = _mask_shape_tdsb

    def _materialize_mask_shape(self, *, roto_bezier: bool = False) -> None:
        """Insert the default full-frame Mask Shape AE writes when a
        path-less mask first needs one, and rebind the Mask Path child
        to it.

        Mirrors After Effects: a freshly added mask carries no Mask Shape
        subtree, and enabling RotoBezier (`roto_bezier=True`) or setting a
        plain bezier path (`False` - the tdsb roto flag stays clear, like
        AE's own imports) materializes the implicit default full-frame
        rectangle as an explicit path.
        """
        from ...parsers.property import parse_properties  # noqa: PLC0415

        self._ensure_materialized()
        self._ensure_children_synthesized()
        assert self._tdgp is not None
        comp = self._containing_layer.containing_comp
        tdmn, oms = build_default_mask_shape(
            comp._cdta.internal_timebase, roto_bezier=roto_bezier
        )

        # Synthesis inserts a bare synthetic `tdmn + tdbs` placeholder for
        # every child; replace the Mask Shape placeholder in place with the
        # real full-frame om-s (the other children stay synthetic, skipped
        # on write, exactly as AE leaves them).
        chunks = self._tdgp.chunks
        insert_at = len(chunks)
        for i, c in enumerate(chunks):
            if (
                c.chunk_type == "tdmn"
                and getattr(c, "value", None) == "ADBE Mask Shape"
                and c.synthetic
            ):
                insert_at = i
                del chunks[i : i + 2]
                break
        chunks.insert(insert_at, tdmn)
        chunks.insert(insert_at + 1, oms)

        # Rebind the Mask Path child to the inserted om-s via the canonical
        # parser, so its value and tdsb reflect the materialized path.
        parsed = parse_properties(
            match_name_runs=[("ADBE Mask Shape", [tdmn, oms])],
            child_depth=self.property_depth + 1,
            effect_param_defs={},
            composition=comp,
        )
        mask_path = parsed[0]
        mask_path._parent_property = self
        # Transplant the freshly parsed state onto the EXISTING Mask Shape
        # child rather than swapping in a new object, so a handle a caller
        # fetched before materialization keeps pointing at the live chunks.
        # A plain swap would orphan that handle - its backing placeholder
        # chunks were deleted above, so later writes through it would never
        # reach the saved file.
        existing = next(
            (c for c in self._properties if c.match_name == "ADBE Mask Shape"),
            None,
        )
        if existing is not None:
            existing.__dict__.update(mask_path.__dict__)
            cast("Property", existing)._link_keyframes()
        else:
            self._properties.insert(0, mask_path)
        tdbs = find_by_list_type(chunks=oms.chunks, list_type="tdbs")
        self._mask_shape_tdsb = cast(
            "TdsbChunk", find_by_type(chunks=tdbs.chunks, chunk_type="tdsb")
        )
