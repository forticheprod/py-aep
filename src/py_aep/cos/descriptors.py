"""Descriptors for COS-dict-backed model fields.

Each descriptor reads from / writes to a COS dict stored on the model
instance, so that accessing a model attribute lazily extracts the value
from the underlying COS data.  After every `__set__`, the model's
`_propagate_cos()` hook is called to re-serialize the COS dict back
to the btdk chunk's `binary_data`.

This module mirrors the role of
`kaitai.descriptors.ChunkField` but operates on nested Python dicts
(COS parsed data) instead of Kaitai chunk bodies.
"""

from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar, overload

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
            return obj.__dict__[self.public_name]  # type: ignore[no-any-return]
        d: dict[str, Any] | None = getattr(obj, self.dict_attr, None)
        if d is None:
            return self.default  # type: ignore[return-value]
        raw = d.get(self.key, _SENTINEL)
        if raw is _SENTINEL:
            return self.default  # type: ignore[return-value]
        if self.transform is not None:
            try:
                return self.transform(raw)  # type: ignore[no-any-return,return-value]
            except (TypeError, ValueError, KeyError, IndexError):
                return self.default  # type: ignore[return-value]
        return raw  # type: ignore[no-any-return,return-value]

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

        Bakes in `transform=bool` and `reverse=int` so call
        sites only need the dict attribute and key.
        """
        return cls(  # type: ignore[return-value]
            dict_attr,
            key,
            transform=bool,
            reverse=int,
            **kwargs,
        )

    @classmethod
    def enum(
        cls,
        enum_cls: type[T],
        dict_attr: str,
        key: str,
        *,
        map: dict[int, Any] | None = None,
        reverse_map: dict[Any, int] | None = None,
        **kwargs: Any,
    ) -> CosField[T]:
        """Create a CosField for enum-backed fields.

        When *map* is provided, it is used as the lookup table (COS int
        value -> enum member).  Otherwise a direct `enum_cls(value)`
        call is attempted.  *reverse_map* inverts the mapping; if not
        given, `int(value)` is used.
        """
        if map is not None:
            kwargs.setdefault("transform", lambda v: map.get(v))  # type: ignore[arg-type]
        else:
            kwargs.setdefault("transform", enum_cls)
        if reverse_map is not None:
            kwargs.setdefault("reverse", lambda v: reverse_map.get(v, int(v)))  # type: ignore[arg-type]
        else:
            kwargs.setdefault("reverse", int)
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
