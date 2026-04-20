"""Descriptors for chunk-backed model fields.

Each descriptor reads from / writes to a Kaitai chunk body attribute,
so that modifying a model field directly mutates the underlying binary
data and `Project.save()` persists the change.

After every `__set__`, `propagate_check` walks the Kaitai
parent chain bottom-up: it calls `_check()` on each object (clearing
the `_dirty` flag) and updates every ancestor `Chunk.len_body` when
the body's serialized size has changed.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any, Callable, Generic, TypeVar, overload

from .proxy import ProxyBody, _materialization_allowed
from .utils import propagate_check

T = TypeVar("T")

_SENTINEL = object()


def _invalidate(body: Any, names: list[str]) -> None:
    """Clear cached Kaitai instances so they recompute on next access."""
    for name in names:
        invalidator = getattr(body, f"_invalidate_{name}", None)
        if invalidator is not None:
            try:
                invalidator()
            except AttributeError:
                pass


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


class ChunkField(Generic[T]):
    """Descriptor that proxies a single field on a chunk body.

    Two mutually exclusive write hooks are available:

    - `reverse_seq_field` (scalar): a 1-arg callable that converts the
      user-facing value to a single binary value, written to `field`.
      Use when `field` targets a Kaitai `seq:` field.
    - `reverse_instance_field` (multi-field): a 2-arg callable
      `(value, body)` that returns a `dict` of `{field_name: value}`
      pairs. Each pair is written to the body, and the field's own
      name is automatically invalidated (in addition to any names in
      `invalidates`). Use when `field` targets a Kaitai `instances:`
      field.

    Args:
        chunk_attr: Name of the model attribute holding the chunk body
            reference (e.g. `"_cdta"`).
        field: Name of the field on the chunk body (e.g. `"width"`).
        transform: Optional callable applied when *getting* (binary ->
            user-facing value).
        reverse_seq_field: 1-arg callable applied when *setting*
            (user-facing -> binary value). Returns a scalar written
            to `field`.
        reverse_instance_field: 2-arg callable `(value, body)` applied
            when *setting*. Returns a `dict` of field-name/value
            pairs. Mutually exclusive with `reverse_seq_field`.
        read_only: When `True`, the field cannot be set. Defaults to
            `False`.
        validate: Optional callable called with the user-facing value
            before any reverse transform. Must raise `ValueError`
            or `TypeError` if the value is invalid.
        invalidates: Kaitai instance names to clear after a set so they
            are recomputed on next access.
        default: Optional default value returned when the chunk body is
            `None`. If not given, accessing the field when the body is
            `None` raises `AttributeError`.
        post_set: Optional method name on the model instance to call
            after the value has been written and propagated.
    """

    def __init__(
        self,
        chunk_attr: str,
        field: str,
        *,
        transform: Callable[..., Any] | None = None,
        reverse_seq_field: Callable[..., Any] | None = None,
        reverse_instance_field: Callable[..., dict[str, Any]] | None = None,
        read_only: bool = False,
        validate: Callable[..., None] | None = None,
        invalidates: list[str] | None = None,
        default: Any = _SENTINEL,
        post_set: str | None = None,
    ) -> None:
        if reverse_seq_field is not None and reverse_instance_field is not None:
            raise TypeError(
                "Cannot set both 'reverse_seq_field' and 'reverse_instance_field'."
            )
        self.chunk_attr = chunk_attr
        self.field = field
        self.transform = transform
        self.reverse_seq_field = reverse_seq_field
        self.reverse_instance_field = reverse_instance_field
        self.read_only = read_only
        self.validate = validate
        self.invalidates = invalidates or []
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
            return obj.__dict__[self.public_name]  # type: ignore[no-any-return]
        body = getattr(obj, self.chunk_attr)
        if body is None:
            if self.default is not _SENTINEL:
                return self.default  # type: ignore[no-any-return,return-value]
            raise AttributeError(f"chunk body {self.chunk_attr!r} is None")
        value = getattr(body, self.field)
        return self.transform(value) if self.transform else value  # type: ignore[no-any-return,return-value]

    def __set__(self, obj: Any, value: T) -> None:
        if self.read_only:
            raise AttributeError(f"{self.public_name!r} is read-only.")
        if not _materialization_allowed.get():
            raise RuntimeError(
                f"Cannot write {self.public_name!r} via ChunkField during "
                f"parsing. Use obj.__dict__[{self.public_name!r}] for "
                f"parse-time overrides."
            )
        # Clear any parse-time override so the write goes to the chunk.
        obj.__dict__.pop(self.public_name, None)
        body = getattr(obj, self.chunk_attr)
        if body is None:
            # No backing chunk (e.g. synthesized properties) - store in
            # the instance dict so __get__ returns default or dict value.
            obj.__dict__[self.public_name] = value
            return
        # Eager materialization: when an end-user writes to a synthesized
        # property, replace the ProxyBody with real Kaitai chunks.
        if isinstance(body, ProxyBody):
            obj._ensure_materialized()
            body = getattr(obj, self.chunk_attr)
        if self.validate:
            self.validate(value, obj)
        _validate_enum(self.transform, value, self.public_name)
        if self.reverse_instance_field is not None:
            fields = self.reverse_instance_field(value, body)
            for field_name, field_value in fields.items():
                setattr(body, field_name, field_value)
            _invalidate(body, [self.field, *self.invalidates])
        elif self.reverse_seq_field is not None:
            setattr(body, self.field, self.reverse_seq_field(value))
            _invalidate(body, self.invalidates)
        else:
            setattr(body, self.field, value)
            _invalidate(body, self.invalidates)
        propagate_check(body)
        if self.post_set is not None:
            getattr(obj, self.post_set)()

    @classmethod
    def bool(cls, chunk_attr: str, field: str, **kwargs: Any) -> ChunkField[bool]:
        """Create a ChunkField for boolean flags.

        Bakes in `transform=bool` and `reverse_seq_field=int` so call sites only
        need the chunk attribute and field name.
        """
        return cls(chunk_attr, field, transform=bool, reverse_seq_field=int, **kwargs)  # type: ignore[return-value]

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
        if "reverse_seq_field" not in kwargs and "reverse_instance_field" not in kwargs:
            kwargs["reverse_seq_field"] = getattr(enum_cls, "to_binary", int)
        return cls(chunk_attr, field, **kwargs)
