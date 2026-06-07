"""Descriptors for COS-dict-backed model fields.

Each descriptor reads from / writes to a COS dict stored on the model
instance, so that accessing a model attribute lazily extracts the value
from the underlying COS data.  After every `__set__`, the model's
`_propagate_cos()` hook is called to re-serialize the COS dict back
to the btdk chunk's `binary_data`.

This module mirrors the role of
`models.descriptors.ChunkField` but operates on nested Python dicts
(COS parsed data) instead of binary chunk fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar, cast, overload

if TYPE_CHECKING:
    from typing import Any, Callable

T = TypeVar("T")

_SENTINEL = object()


class CosField(Generic[T]):
    """Descriptor that proxies a single key on a COS dict.

    The dict is retrieved from the model instance via `getattr(obj,
    dict_attr)`.  When the dict is `None` the descriptor returns
    `default` (which defaults to `None`).

    Unlike `ChunkField`, this descriptor is scalar-only: `reverse`
    always returns a single value written to one dict key.

    Args:
        dict_attr: Name of the model attribute holding the COS sub-dict
            (e.g. `"_char_style"`).
        key: String key into that dict (e.g. `"1"` for font_size).
        transform: Optional callable applied when *getting* (COS value
            -> user-facing value).
        reverse: 1-arg callable applied when *setting* (user-facing ->
            COS value). Always returns a scalar.
        read_only: When `True`, the field cannot be set.
        validate: Optional callable called with the user-facing value
            before any `reverse` transform.
        default: Value returned when the dict is `None` or the key is
            absent. Defaults to `None`.
    """

    def __init__(
        self,
        dict_attr: str,
        key: str,
        *,
        transform: Callable[..., Any] | None = None,
        reverse: Callable[..., Any] | None = None,
        read_only: bool = False,
        validate: Callable[..., None] | None = None,
        default: Any = None,
    ) -> None:
        self.dict_attr = dict_attr
        self.key = key
        self.transform = transform
        self.reverse = reverse
        self.read_only = read_only
        self.validate = validate
        self.default = default

    def __set_name__(self, owner: type, name: str) -> None:
        self.public_name = name

    @overload
    def __get__(self, obj: None, objtype: type) -> CosField[T]: ...

    @overload
    def __get__(self, obj: Any, objtype: type | None = None) -> T: ...

    def __get__(self, obj: Any, objtype: type | None = None) -> T | CosField[T]:
        if obj is None:
            return self
        # Instance-dict overrides (set by parser or user when no dict)
        if self.public_name in obj.__dict__:
            return cast(T, obj.__dict__[self.public_name])
        d: dict[str, Any] | None = getattr(obj, self.dict_attr, None)
        if d is None:
            return cast(T, self.default)
        raw = d.get(self.key, _SENTINEL)
        if raw is _SENTINEL:
            return cast(T, self.default)
        if self.transform is not None:
            try:
                return cast(T, self.transform(raw))
            except (TypeError, ValueError, KeyError, IndexError):
                return cast(T, self.default)
        return cast(T, raw)

    def __set__(self, obj: Any, value: T) -> None:
        if self.read_only:
            raise AttributeError(f"{self.public_name!r} is read-only.")
        # Clear any instance-dict override
        obj.__dict__.pop(self.public_name, None)
        d: dict[str, Any] | None = getattr(obj, self.dict_attr, None)
        if d is None:
            # No backing dict - store as instance override
            obj.__dict__[self.public_name] = value
            return
        if self.validate is not None:
            self.validate(value, obj)
        if value is None:
            d.pop(self.key, None)
        elif self.reverse is not None:
            d[self.key] = self.reverse(value)
        else:
            d[self.key] = value
        propagate = getattr(obj, "_propagate_cos", None)
        if propagate is not None:
            propagate()

    @classmethod
    def bool(
        cls,
        dict_attr: str,
        key: str,
        **kwargs: Any,
    ) -> CosField[bool | None]:
        """Create a CosField for boolean flags.

        Bakes in `transform=bool` and `reverse=bool` so call sites only
        need the dict attribute and key.
        """
        return cls(  # type: ignore[return-value]
            dict_attr,
            key,
            transform=bool,
            reverse=bool,
            **kwargs,
        )

    @classmethod
    def enum(
        cls,
        enum_cls: type[T],
        dict_attr: str,
        key: str,
        **kwargs: Any,
    ) -> CosField[T]:
        """Create a CosField for IntEnum-backed fields.

        Auto-detects `from_binary`/`to_binary` on the enum class,
        mirroring `ChunkField.enum`. If the enum has a `from_binary`
        classmethod it is used as `transform`; otherwise the class
        itself is used. If the enum has a `to_binary` method it is used
        as `reverse`; otherwise `int` is used.
        """
        if "transform" not in kwargs:
            kwargs["transform"] = getattr(enum_cls, "from_binary", enum_cls)
        if "reverse" not in kwargs:
            kwargs["reverse"] = getattr(enum_cls, "to_binary", int)
        return cls(dict_attr, key, **kwargs)

    @classmethod
    def float(
        cls,
        dict_attr: str,
        key: str,
        **kwargs: Any,
    ) -> CosField[float | None]:
        """Create a CosField that coerces to float."""
        return cls(dict_attr, key, transform=float, **kwargs)  # type: ignore[return-value]
