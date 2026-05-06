"""Descriptors for chunk-backed model fields.

Each descriptor reads from / writes to a binary chunk attribute,
so that modifying a model field directly mutates the underlying binary
data and `Project.save()` persists the change.

"""

from __future__ import annotations

import contextlib
from contextvars import ContextVar
from enum import IntEnum
from typing import TYPE_CHECKING, Generic, TypeVar, cast, overload

if TYPE_CHECKING:
    from typing import Any, Callable, Iterator

T = TypeVar("T")

_SENTINEL = object()

# During `parse()` this is set to False so that `ChunkField.__set__`
# rejects writes.  Outside `parse()` the default (True) lets end-user
# writes through.
_materialization_allowed: ContextVar[bool] = ContextVar(
    "_materialization_allowed",
    default=True,
)


@contextlib.contextmanager
def _suppress_materialization() -> Iterator[None]:
    """Context manager that disables materialization for the current context."""
    token = _materialization_allowed.set(False)
    try:
        yield
    finally:
        _materialization_allowed.reset(token)


def _validate_enum(
    transform: Callable[..., Any] | None, value: Any, public_name: str
) -> None:
    """Raise `ValueError` if *value* is not a valid IntEnum member.

    When *transform* points to an IntEnum subclass (via `from_binary`
    classmethod or direct class reference), non-member values are
    rejected: raw ints must appear in the enum's value map; any other
    type must already be an instance of the enum.
    """
    if transform is None:
        return
    enum_cls = getattr(transform, "__self__", None)
    if enum_cls is None and isinstance(transform, type):
        enum_cls = transform
    if (
        enum_cls is None
        or not isinstance(enum_cls, type)
        or not issubclass(enum_cls, IntEnum)
    ):
        return
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


def _prepare_write(
    obj: Any,
    chunk_attr: str,
    public_name: str,
    value: Any,
    validate: Callable[..., None] | None,
    enum_transform: Callable[..., Any] | None,
) -> Any:
    """Shared write preparation for chunk-backed descriptors.

    Handles materialization guard, parse-time override cleanup,
    None-body fallback (stores in ``__dict__``), synthetic body
    materialization, validation, and enum validation.

    Returns the chunk body ready for field writes, or ``None`` if
    the value was stored in ``obj.__dict__`` (no backing chunk).
    """
    if not _materialization_allowed.get():
        raise RuntimeError(
            f"Cannot write {public_name!r} via descriptor during "
            f"parsing. Use obj.__dict__[{public_name!r}] for "
            f"parse-time overrides."
        )
    obj.__dict__.pop(public_name, None)
    body = getattr(obj, chunk_attr)
    if body is None:
        obj.__dict__[public_name] = value
        return None
    if getattr(body, "synthetic", False):
        obj._ensure_materialized()
        body = getattr(obj, chunk_attr)
    if validate:
        validate(value, obj)
    _validate_enum(enum_transform, value, public_name)
    return body


class ChunkField(Generic[T]):
    """Descriptor that proxies a single field on a chunk body.

    Two mutually exclusive write hooks are available:

    - `reverse` (scalar): a 1-arg callable that converts the
      user-facing value to a single binary value, written to `field`.
      Use when `field` targets a binary chunk field.
    - `reverse_multi` (multi-field): a 2-arg callable
      `(value, body)` that returns a `dict` of `{field_name: value}`
      pairs. Each pair is written to the body.

    Args:
        chunk_attr: Name of the model attribute holding the chunk body
            reference (e.g. `"_cdta"`).
        field: Name of the field on the chunk body (e.g. `"width"`).
        transform: Optional callable applied when *getting* (binary ->
            user-facing value).
        reverse: 1-arg callable applied when *setting*
            (user-facing -> binary value). Returns a scalar written
            to `field`.
        reverse_multi: 2-arg callable `(value, body)` applied
            when *setting*. Returns a `dict` of field-name/value
            pairs. Mutually exclusive with `reverse`.
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
        reverse_multi: Callable[..., dict[str, Any]] | None = None,
        read_only: bool = False,
        validate: Callable[..., None] | None = None,
        default: Any = _SENTINEL,
        post_set: Callable[[Any], None] | str | None = None,
    ) -> None:
        if reverse is not None and reverse_multi is not None:
            raise TypeError(
                "Cannot set both 'reverse' and 'reverse_multi'."
            )
        self.chunk_attr = chunk_attr
        self.field = field
        self.transform = transform
        self.reverse = reverse
        self.reverse_multi = reverse_multi
        self.read_only = read_only
        self.validate = validate
        self.default = default
        self.post_set = post_set

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
        body = _prepare_write(
            obj, self.chunk_attr, self.public_name,
            value, self.validate, self.transform,
        )
        if body is None:
            return
        if self.reverse_multi is not None:
            fields = self.reverse_multi(value, body)
            for field_name, field_value in fields.items():
                setattr(body, field_name, field_value)
        elif self.reverse is not None:
            setattr(body, self.field, self.reverse(value))
        else:
            setattr(body, self.field, value)
        if self.post_set is not None:
            if isinstance(self.post_set, str):
                getattr(obj, self.post_set)()
            else:
                self.post_set(obj)

    @classmethod
    def enum(
        cls, enum_cls: type[T], chunk_attr: str, field: str, **kwargs: Any
    ) -> ChunkField[T]:
        """Create a ChunkField for IntEnum-backed fields.

        Auto-detects `from_binary`/`to_binary` on the enum class. If
        the enum has a `from_binary` classmethod it is used as
        `transform`; otherwise the class itself is used. If the enum
        has a `to_binary` method it is used as `reverse`; otherwise
        `int` is used.
        """
        if "transform" not in kwargs:
            kwargs["transform"] = getattr(enum_cls, "from_binary", enum_cls)
        if "reverse" not in kwargs and "reverse_multi" not in kwargs:
            kwargs["reverse"] = getattr(enum_cls, "to_binary", int)
        return cls(chunk_attr, field, **kwargs)


class ComputedField(Generic[T]):
    """Descriptor for model fields derived from multiple chunk fields.

    Reads call `compute(body)` to derive a user-facing value from raw
    chunk fields.  Writes call `reverse(value, body)` which returns a
    ``dict`` of ``{field_name: raw_value}`` pairs written back to the
    chunk body.

    Omit `reverse` for read-only fields.

    Args:
        chunk_attr: Name of the model attribute holding the chunk body
            reference (e.g. ``"_cdta"``).
        compute: Callable that receives the chunk body and returns the
            user-facing value.
        reverse: Optional callable ``(value, body) -> dict``. If
            ``None``, the field is read-only.
        validate: Optional callable called with ``(value, obj)``
            before writing. Must raise on invalid input.
        default: Returned when the chunk body is ``None``. If not
            given, accessing the field when the body is ``None``
            raises ``AttributeError``.
    """

    def __init__(
        self,
        chunk_attr: str,
        *,
        compute: Callable[[Any], T],
        reverse: Callable[[Any, Any], dict[str, Any]] | None = None,
        validate: Callable[..., None] | None = None,
        default: Any = _SENTINEL,
        enum_transform: Callable[..., Any] | None = None,
    ) -> None:
        self.chunk_attr = chunk_attr
        self.compute = compute
        self.reverse_fn = reverse
        self.validate = validate
        self.default = default
        self.enum_transform = enum_transform

    def __set_name__(self, owner: type, name: str) -> None:
        self.public_name = name

    @overload
    def __get__(self, obj: None, objtype: type) -> ComputedField[T]: ...

    @overload
    def __get__(self, obj: Any, objtype: type | None = None) -> T: ...

    def __get__(
        self, obj: Any, objtype: type | None = None
    ) -> T | ComputedField[T]:
        if obj is None:
            return self
        if self.public_name in obj.__dict__:
            return cast(T, obj.__dict__[self.public_name])
        body = getattr(obj, self.chunk_attr)
        if body is None:
            if self.default is not _SENTINEL:
                return cast(T, self.default)
            raise AttributeError(
                f"chunk body {self.chunk_attr!r} is None"
            )
        return cast(T, self.compute(body))

    def __set__(self, obj: Any, value: T) -> None:
        if self.reverse_fn is None:
            raise AttributeError(f"{self.public_name!r} is read-only.")
        body = _prepare_write(
            obj, self.chunk_attr, self.public_name,
            value, self.validate, self.enum_transform,
        )
        if body is None:
            return
        for field_name, field_value in self.reverse_fn(value, body).items():
            setattr(body, field_name, field_value)

    @classmethod
    def enum(
        cls,
        enum_cls: type[T],
        chunk_attr: str,
        *,
        compute: Callable[[Any], T],
        reverse: Callable[[Any, Any], dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ComputedField[T]:
        """Create a ComputedField for IntEnum-backed computed fields.

        Auto-detects `from_binary` on the enum class for validation.
        The `compute` function should return the enum value directly.

        Args:
            enum_cls: The IntEnum subclass.
            chunk_attr: Name of the chunk body attribute.
            compute: Callable that receives the chunk body and returns
                the enum value.
            reverse: Optional callable ``(value, body) -> dict``.
        """
        enum_transform = getattr(enum_cls, "from_binary", enum_cls)
        return cls(
            chunk_attr,
            compute=compute,
            reverse=reverse,
            enum_transform=enum_transform,
            **kwargs,
        )
