"""Descriptors for chunk-backed model fields.

Each descriptor reads from / writes to a binary chunk attribute,
so that modifying a model field directly mutates the underlying binary
data and `Project.save()` persists the change.

"""

from __future__ import annotations

import builtins
import contextlib
from contextvars import ContextVar
from enum import IntEnum
from typing import TYPE_CHECKING, Generic, TypeVar, cast, overload

from ..ae_version import get_ae_version_major
from .validators import validate_bool, validate_enum

if TYPE_CHECKING:
    from typing import Any, Callable, Iterator

T = TypeVar("T")

_SENTINEL = object()

# While a parser runs this is set to False so that `ChunkField.__set__`
# rejects writes: parsers must not mutate chunk data through descriptors
# (round-trip idempotency). Parsers cache values via `__dict__` overrides
# or the private `_cache_value` helpers instead. Outside parsing the
# default (True) lets end-user writes through.
_materialization_allowed: ContextVar[bool] = ContextVar(
    "_materialization_allowed",
    default=True,
)


@contextlib.contextmanager
def _suppress_materialization() -> Iterator[None]:
    """Forbid descriptor writes for the current context.

    Parser entry points are decorated with this so any descriptor
    write during parsing raises `RuntimeError` instead of silently
    mutating chunk data. Usable as a decorator
    (`@_suppress_materialization()`) or a `with` block.
    """
    token = _materialization_allowed.set(False)
    try:
        yield
    finally:
        _materialization_allowed.reset(token)


def _enum_class(transform: Callable[..., Any] | None) -> type[IntEnum] | None:
    """Return the IntEnum class behind `transform`, if any.

    Detects a `from_binary` classmethod (via `__self__`) or a direct
    enum class reference.
    """
    if transform is None:
        return None
    enum_cls = getattr(transform, "__self__", None)
    if enum_cls is None and isinstance(transform, type):
        enum_cls = transform
    if isinstance(enum_cls, type) and issubclass(enum_cls, IntEnum):
        return enum_cls
    return None


def enum_or_raw(convert: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Wrap a get-transform so out-of-enum stored values read back raw.

    Real `.aep` files can hold values outside our enums (e.g. a garbage
    `Rouu.depth`, or a format id from a third-party output plugin); the
    binary is trusted, so reads must not raise. Mirrors the fallback
    `_try_enum_or_int` uses for XML params.

    For a chunk-backed field prefer
    `ChunkField.enum(..., allow_out_of_enum_values=True)`, which applies
    this wrapper and restores write-side strictness for you. This helper
    is for the read paths that are not `ChunkField`s (e.g. a `@property`
    over decoded JSON).
    """

    def _transform(value: Any) -> Any:
        try:
            return convert(value)
        except (ValueError, TypeError):
            # TypeError: a `convert` that coerces first (e.g. `int(v)` over
            # decoded JSON) raises it, not ValueError, for a non-scalar.
            return value

    return _transform


def _validate_enum_member(
    enum_cls: type[IntEnum], value: Any, public_name: str
) -> None:
    """Raise `ValueError` if `value` is not a valid member of `enum_cls`.

    Raw ints must appear in the enum's value map; any other type must
    already be an instance of the enum.
    """
    if isinstance(value, enum_cls):
        return
    if isinstance(value, int):
        if value not in enum_cls._value2member_map_:
            members = ", ".join(f"{m.name} ({m.value})" for m in enum_cls)
            raise ValueError(
                f"Invalid value {value!r} for {public_name!r}. "
                f"Valid {enum_cls.__name__} values: {members}"
            )
    else:
        raise ValueError(f"{value!r} is not a valid {enum_cls.__name__}")


class ChunkField(Generic[T]):
    """Descriptor that proxies a single field on a chunk body.

    Args:
        chunk_attr: Name of the model attribute holding the chunk body
            reference (e.g. `"_cdta"`).
        field: Name of the field on the chunk body (e.g. `"width"`).
        transform: Optional callable applied when *getting* (binary ->
            user-facing value).
        reverse: 1-arg callable applied when *setting*
            (user-facing -> binary value). Returns a scalar written
            to `field`.
        read_only: When `True`, the field cannot be set. Defaults to
            `False`.
        validate: Optional callable called with the user-facing value
            before any reverse transform. Must raise `ValueError`
            or `TypeError` if the value is invalid.
        default: Optional default value returned when the chunk body is
            `None`. If not given, accessing the field when the body is
            `None` raises `AttributeError`.
        post_set: Optional method name on the model instance, or a
            callable receiving the model instance, invoked after the
            value has been written.
    """

    def __init__(
        self,
        chunk_attr: str,
        field: str,
        *,
        transform: Callable[..., Any] | None = None,
        reverse: Callable[..., Any] | None = None,
        read_only: bool = False,
        validate: Callable[..., None] | None = None,
        default: Any = _SENTINEL,
        post_set: Callable[[Any], None] | str | None = None,
        min_version: int | None = None,
    ) -> None:
        self.chunk_attr = chunk_attr
        self.field = field
        self.transform = transform
        self.reverse = reverse
        self.read_only = read_only
        self.validate = validate
        self.default = default
        self.post_set = post_set
        self.min_version = min_version
        # Derived once so __set__ validates membership without
        # re-inspecting the transform on every write.
        self._enum_cls = _enum_class(transform)

    def __set_name__(self, owner: type, name: str) -> None:
        self.public_name = name

    @overload
    def __get__(self, obj: None, objtype: type) -> ChunkField[T]: ...

    @overload
    def __get__(self, obj: Any, objtype: type | None = None) -> T: ...

    def __get__(self, obj: Any, objtype: type | None = None) -> T | ChunkField[T]:
        if obj is None:
            return self
        # Parse-time overrides (e.g. ExtendScript-compatible values that
        # differ from the binary) are stored in __dict__ and take priority
        # over the chunk body.
        if self.public_name in obj.__dict__:
            return cast(T, obj.__dict__[self.public_name])
        body = getattr(obj, self.chunk_attr)
        if body is None:
            if self.default is not _SENTINEL:
                return cast(T, self.default)
            raise AttributeError(f"chunk body {self.chunk_attr!r} is None")
        value = getattr(body, self.field)
        return cast(T, self.transform(value) if self.transform else value)

    def __set__(self, obj: Any, value: T) -> None:
        if self.read_only:
            raise AttributeError(f"{self.public_name!r} is read-only.")
        if self.min_version is not None:
            try:
                major: int | None = get_ae_version_major(obj)
            except TypeError:
                # Version undeterminable (e.g. a ViewOptions whose viewer
                # has no AVItem); skip the gate and allow the write.
                major = None
            if major is not None and major < self.min_version:
                raise AttributeError(
                    f"{self.public_name!r} requires AE {self.min_version}+ file format."
                )
        if not _materialization_allowed.get():
            raise RuntimeError(
                f"Cannot write {self.public_name!r} via descriptor during "
                f"parsing. Use obj.__dict__[{self.public_name!r}] for "
                f"parse-time overrides."
            )
        # Validate BEFORE touching anything. `_ensure_materialized` flips
        # synthetic chunks to real, so a rejected write that reached it
        # would mutate the tree and break the byte-identical round-trip
        # (`parse()` -> `save()`). A field with no backing chunk body must
        # validate too, or its `__dict__` fallback below would accept a
        # value the chunk-backed path rejects.
        if self.validate:
            self.validate(value, obj)
        if self._enum_cls is not None:
            _validate_enum_member(self._enum_cls, value, self.public_name)
        obj.__dict__.pop(self.public_name, None)
        body = getattr(obj, self.chunk_attr)
        if body is None:
            obj.__dict__[self.public_name] = value
            return
        if getattr(body, "synthetic", False):
            obj._ensure_materialized()
            body = getattr(obj, self.chunk_attr)
        if self.reverse is not None:
            setattr(body, self.field, self.reverse(value))
        else:
            setattr(body, self.field, value)
        if self.post_set is not None:
            if isinstance(self.post_set, str):
                getattr(obj, self.post_set)()
            else:
                self.post_set(obj)

    # NOTE: this shadows the builtin `bool` inside the class body, so
    # annotations below it must spell it `builtins.bool`.
    @classmethod
    def bool(
        cls, chunk_attr: str, field: str, **kwargs: Any
    ) -> ChunkField[builtins.bool]:
        """Create a ChunkField for a boolean field.

        Bakes in `validate=validate_bool` so a writable bool field cannot
        silently accept a non-bool: the binary layer packs the value
        straight into a 1-byte field, so `= 2` would write a byte AE never
        writes and `= "no"` would only blow up later, at `save()`.

        Pass `validate=` to override (compose by calling `validate_bool`
        first). For a bool backed by a generic integer chunk field (e.g.
        `U1Chunk.value`) add `transform=bool, reverse=int`.
        """
        kwargs.setdefault("validate", validate_bool)
        return cast("ChunkField[builtins.bool]", cls(chunk_attr, field, **kwargs))

    @classmethod
    def enum(
        cls,
        enum_cls: type[T],
        chunk_attr: str,
        field: str,
        *,
        allow_out_of_enum_values: builtins.bool = False,
        **kwargs: Any,
    ) -> ChunkField[T]:
        """Create a ChunkField for IntEnum-backed fields.

        Auto-detects `from_binary`/`to_binary` on the enum class. If
        the enum has a `from_binary` classmethod it is used as
        `transform`; otherwise the class itself is used. If the enum
        has a `to_binary` method it is used as `reverse`; otherwise
        `int` is used.

        Args:
            allow_out_of_enum_values: When `True`, a stored value outside
                the enum reads back raw instead of raising - real `.aep`
                files hold them (a garbage `Rouu.depth`, a format id from a
                third-party output plugin) and the binary is trusted.
                Wrapping the transform hides the enum class from
                `_enum_class`, so write-side membership strictness is
                restored via `validate=validate_enum(enum_cls)` unless the
                caller passes its own `validate` (which must then check
                membership itself).
        """
        if "transform" not in kwargs:
            kwargs["transform"] = getattr(enum_cls, "from_binary", enum_cls)
        if "reverse" not in kwargs:
            kwargs["reverse"] = getattr(enum_cls, "to_binary", int)
        if allow_out_of_enum_values:
            kwargs["transform"] = enum_or_raw(kwargs["transform"])
            if not kwargs.get("read_only"):
                kwargs.setdefault("validate", validate_enum(enum_cls))
        return cls(chunk_attr, field, **kwargs)
