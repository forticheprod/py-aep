from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar, cast

from ...enums import LayerType, ParametricMeshType
from ...synthesis.property import _PARAMETRIC_MESH_ACTIVE_GROUPS
from ..descriptors import ChunkField
from ..preferences import label_index
from .av_layer import AVLayer

if TYPE_CHECKING:
    from ..items.composition import CompItem
    from ..properties.property import Property
    from ..properties.property_group import PropertyGroup

# Bound to float: ParaMeshField values are float/int/bool (numeric tower).
T = TypeVar("T", bound=float)
M = TypeVar("M", bound="ParametricMeshOptions")
B = TypeVar("B", bound="ParametricBevelOptions")


class ParametricMeshLayer(AVLayer):
    """
    The ParametricMeshLayer object represents a parametric mesh layer within a composition.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        comp = app.project.compositions[0]
        mesh = comp.parametric_mesh_layers[0]
        print(mesh.name)
        ```

    Info:
        `ParametricMeshLayer` is a subclass of [AVLayer][] object. All methods and
        attributes of [AVLayer][] are available when working with `ParametricMeshLayer`.

    Note:
        This functionality was added in After Effects 26.0

    See: https://ae-scripting.docsforadobe.dev/layer/parametricmeshlayer/
    """

    _auto_name: str = "Mesh Layer"

    parametric_mesh_type = ChunkField.enum(
        ParametricMeshType,
        "_ldta",
        "light_and_mesh_type",
        post_set=lambda obj: obj._update_options(),
    )
    """For a parametric mesh layer, its mesh type. Read / write."""

    parametric_mesh_options: ParametricMeshOptions
    """The ParametricMeshOptions object represents the options for a parametric mesh layer."""

    parametric_bevel_options: ParametricBevelOptions
    """The ParametricBevelOptions object represents the bevel options for a parametric mesh layer."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._update_options()

    @classmethod
    def _new(  # type: ignore[override]
        cls,
        *,
        name: str,
        layer_id: int,
        duration: float,
        containing_comp: CompItem,
        mesh_type: ParametricMeshType,
        effect_param_defs: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> ParametricMeshLayer:
        layer = cast(
            "ParametricMeshLayer",
            super()._new(
                name=name,
                layer_id=layer_id,
                duration=duration,
                containing_comp=containing_comp,
                effect_param_defs=effect_param_defs,
            ),
        )
        layer._ldta.layer_type = LayerType.PARAMETRIC_MESH
        layer._ldta.label = label_index(
            containing_comp._project._preferences, "Parametrics Label Index", 9
        )
        layer._ldta.three_d_layer = True
        layer._ldta.collapse_transformation = True
        # AE writes flags2=0x83 for mesh layers: effects are not applicable.
        layer._ldta.effects_active = False
        # AE expresses the layer's time fields in the comp's internal
        # timebase (e.g. 23976 for 29.97 fps), not a reduced rational.
        time_base = containing_comp._cdta.internal_timebase
        layer._ldta.start_time_divisor = time_base
        layer._ldta.in_point_divisor = time_base
        layer._ldta.out_point_dividend = round(duration * time_base)
        layer._ldta.out_point_divisor = time_base
        layer.parametric_mesh_type = mesh_type
        # AE writes the active mesh type's option/bevel groups expanded
        # (tdsb=1) while the other mesh groups stay collapsed (tdsb=3, the
        # synthesized default). Override the active groups before the layer
        # is materialized so the written tdsb matches AE.
        active_groups = _PARAMETRIC_MESH_ACTIVE_GROUPS.get(mesh_type.to_binary(), ())
        for child in layer.properties:
            if child.match_name in active_groups and child._tdsb is not None:
                child._tdsb._enable_flags = 1
        return layer

    def _update_options(self) -> None:
        """Update the parametric mesh options from the layer's current state."""
        options_cls = OPTION_TYPES.get(self._ldta.light_and_mesh_type)
        old_options = getattr(self, "parametric_mesh_options", None)
        if type(old_options) is not options_cls:
            try:
                del self.parametric_mesh_options
            except AttributeError:
                pass
            if options_cls is not None:
                self.parametric_mesh_options = options_cls(self)

        bevel_cls = BEVEL_OPTION_TYPES.get(self._ldta.light_and_mesh_type)
        old_bevel = getattr(self, "parametric_bevel_options", None)
        if type(old_bevel) is not bevel_cls:
            try:
                del self.parametric_bevel_options
            except AttributeError:
                pass
            if bevel_cls is not None:
                self.parametric_bevel_options = bevel_cls(self)

    @property
    def can_set_collapse_transformation(self) -> bool:
        """`False` for Parametric Mesh layers: collapse transformation is
        forced on and cannot be changed. Read-only."""
        return False

    @property
    def can_set_time_remap_enabled(self) -> bool:
        """`False` for Parametric Mesh layers (time remapping is not supported). Read-only."""
        return False


# Keyed by the raw ldta value (0-5, `ParametricMeshType.to_binary()`) so
# unknown mesh types from newer AE versions look up as None instead of raising.
OPTION_TYPES: dict[int, type[ParametricMeshOptions]] = {}
BEVEL_OPTION_TYPES: dict[int, type[ParametricBevelOptions]] = {}


def register(mesh_type: ParametricMeshType) -> Callable[[type[M]], type[M]]:
    """Decorator that registers a ParametricMeshOptions subclass for one mesh_type."""

    def decorator(cls: type[M]) -> type[M]:
        OPTION_TYPES[mesh_type.to_binary()] = cls
        return cls

    return decorator


def register_bevel(mesh_type: ParametricMeshType) -> Callable[[type[B]], type[B]]:
    """Decorator that registers a ParametricBevelOptions subclass for one mesh_type."""

    def decorator(cls: type[B]) -> type[B]:
        BEVEL_OPTION_TYPES[mesh_type.to_binary()] = cls
        return cls

    return decorator


class ParaMeshField(Generic[T]):
    """Descriptor for a parametric mesh layer property.

    Args:
        property_name: Name of the property in the parametric mesh options group.
    """

    def __init__(self, property_name: str) -> None:
        self._property_name = property_name

    def __get__(
        self, obj: ParametricMeshOptions | ParametricBevelOptions, objtype: type
    ) -> T:
        if obj is None:
            return self
        value = obj._properties(self._property_name).value
        return cast(T, value)

    def __set__(
        self, obj: ParametricMeshOptions | ParametricBevelOptions, value: T
    ) -> None:
        obj._properties(self._property_name).value = value


class ParametricMeshOptions:
    """
    The ParametricMeshOptions object represents the options for a parametric mesh layer.

    Info:
        This functionality was added in After Effects 26.0
    """

    _match_name: str

    def __init__(self, layer: ParametricMeshLayer) -> None:
        self._layer = layer
        self._group: PropertyGroup | None = None

    def _properties(self, name: str) -> Property:
        if self._group is None:
            self._group = cast("PropertyGroup", self._layer.property(self._match_name))
        return cast("Property", self._group.property(name))

    def __repr__(self) -> str:
        result = {}
        for name, attr in vars(self.__class__).items():
            if hasattr(attr, "__get__"):
                result[name] = getattr(self, name)
        formatted = ", ".join(f"{key}={value}" for key, value in result.items())
        return f"<{self.__class__.__bases__[0].__name__}({formatted})>"


@register(ParametricMeshType.CUBE)
class CubeMeshOptions(ParametricMeshOptions):
    _match_name = "ADBE CubeMeshOptionsSGrp"

    width = ParaMeshField[float]("Width")
    height = ParaMeshField[float]("Height")
    depth = ParaMeshField[float]("Depth")
    smoothing_angle = ParaMeshField[float]("Smoothing Angle")


@register(ParametricMeshType.SPHERE)
class SphereMeshOptions(ParametricMeshOptions):
    _match_name = "ADBE SphereMeshOptionsSGrp"

    radius = ParaMeshField[float]("Radius")
    sides = ParaMeshField[int]("Sides")
    slice_caps = ParaMeshField[bool]("Slice Caps")
    slice_start = ParaMeshField[float]("Slice Start")
    slice_end = ParaMeshField[float]("Slice End")
    smoothing_angle = ParaMeshField[float]("Smoothing Angle")


@register(ParametricMeshType.PLANE)
class PlaneMeshOptions(ParametricMeshOptions):
    _match_name = "ADBE PlaneMeshOptionsSGrp"

    width = ParaMeshField[float]("Width")
    length = ParaMeshField[float]("Length")
    corner_radius = ParaMeshField[float]("Corner Radius")
    corner_sides = ParaMeshField[int]("Corner Sides")


@register(ParametricMeshType.TORUS)
class TorusMeshOptions(ParametricMeshOptions):
    _match_name = "ADBE TorusMeshOptionsSGrp"

    ring_radius = ParaMeshField[float]("Ring Radius")
    pipe_radius = ParaMeshField[float]("Pipe Radius")
    ring_sides = ParaMeshField[int]("Ring Sides")
    pipe_sides = ParaMeshField[int]("Pipe Sides")
    caps = ParaMeshField[bool]("Caps")
    slice_start = ParaMeshField[float]("Slice Start")
    slice_end = ParaMeshField[float]("Slice End")
    smoothing_angle = ParaMeshField[float]("Smoothing Angle")


@register(ParametricMeshType.CONE)
class ConeMeshOptions(ParametricMeshOptions):
    _match_name = "ADBE ConeMeshOptionsSGrp"

    top_radius = ParaMeshField[float]("Top Radius")
    bottom_radius = ParaMeshField[float]("Bottom Radius")
    height = ParaMeshField[float]("Height")
    sides = ParaMeshField[int]("Sides")
    top_cap = ParaMeshField[bool]("Top Cap")
    bottom_cap = ParaMeshField[bool]("Bottom Cap")
    slice_caps = ParaMeshField[bool]("Slice Caps")
    slice_start = ParaMeshField[float]("Slice Start")
    slice_end = ParaMeshField[float]("Slice End")
    smoothing_angle = ParaMeshField[float]("Smoothing Angle")


@register(ParametricMeshType.CYLINDER)
class CylinderMeshOptions(ParametricMeshOptions):
    _match_name = "ADBE CylinderMeshOptionsSGrp"

    radius = ParaMeshField[float]("Radius")
    height = ParaMeshField[float]("Height")
    sides = ParaMeshField[int]("Sides")
    top_cap = ParaMeshField[bool]("Top Cap")
    bottom_cap = ParaMeshField[bool]("Bottom Cap")
    slice_caps = ParaMeshField[bool]("Slice Caps")
    slice_start = ParaMeshField[float]("Slice Start")
    slice_end = ParaMeshField[float]("Slice End")
    smoothing_angle = ParaMeshField[float]("Smoothing Angle")


class ParametricBevelOptions(ParametricMeshOptions):
    """
    The ParametricBevelOptions object represents the bevel options for a parametric mesh layer.

    Info:
        This functionality was added in After Effects 26.0
    """

    pass


@register_bevel(ParametricMeshType.CUBE)
class CubeBevelOptions(ParametricBevelOptions):
    _match_name = "ADBE CubeBevelOptionsSGrp"

    radius = ParaMeshField[float]("Radius")
    sides = ParaMeshField[int]("Sides")


@register_bevel(ParametricMeshType.CONE)
class ConeBevelOptions(ParametricBevelOptions):
    _match_name = "ADBE ConeBevelBevelSGrp"

    top_radius = ParaMeshField[float]("Top Radius")
    top_sides = ParaMeshField[int]("Top Sides")
    bottom_radius = ParaMeshField[float]("Bottom Radius")
    bottom_sides = ParaMeshField[int]("Bottom Sides")


@register_bevel(ParametricMeshType.CYLINDER)
class CylinderBevelOptions(ParametricBevelOptions):
    _match_name = "ADBE CylinderBevelOptionsSGrp"

    radius = ParaMeshField[float]("Radius")
    sides = ParaMeshField[int]("Sides")
