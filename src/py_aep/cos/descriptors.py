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

from ..ae_version import get_ae_version_major

if TYPE_CHECKING:
    from typing import Any, Callable

T = TypeVar("T")

_SENTINEL = object()


def _extract(
    d: dict[str, Any],
    key: str,
    transform: Callable[..., Any] | None,
    default: Any,
) -> Any:
    """Read `key` from a COS dict with the descriptors' fault-tolerant
    fallback: a missing key, or a `transform` that raises, yields
    `default`. Shared by `CosField.__get__` and the range models'
    mixed-value resolution.
    """
    raw = d.get(key, _SENTINEL)
    if raw is _SENTINEL:
        return default
    if transform is not None:
        try:
            return transform(raw)
        except (TypeError, ValueError, KeyError, IndexError):
            return default
    return raw


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
        min_version: Minimum AE major version required to *set* this
            field. Writes to an older file raise `AttributeError`;
            reads are always allowed. Mirrors
            `models.descriptors.ChunkField`.
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
        min_version: int | None = None,
    ) -> None:
        self.dict_attr = dict_attr
        self.key = key
        self.transform = transform
        self.reverse = reverse
        self.read_only = read_only
        self.validate = validate
        self.default = default
        self.min_version = min_version

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
        d: dict[str, Any] | None = getattr(obj, self.dict_attr)
        if d is None:
            return cast(T, self.default)
        return cast(T, _extract(d, self.key, self.transform, self.default))

    def _check_writable(self, obj: Any) -> None:
        """Raise if this field cannot be written to `obj` - read-only, or
        the file predates the field's `min_version`."""
        if self.read_only:
            raise AttributeError(f"{self.public_name!r} is read-only.")
        if self.min_version is not None:
            if get_ae_version_major(obj) < self.min_version:
                raise AttributeError(
                    f"{self.public_name!r} requires AE {self.min_version}+ file format."
                )

    def _coerce(self, obj: Any, value: Any) -> Any:
        """Validate a non-`None` user value and reverse-transform it to
        the form stored in the COS dict."""
        if self.validate is not None:
            self.validate(value, obj)
        if self.reverse is not None:
            return self.reverse(value)
        return value

    def __set__(self, obj: Any, value: T) -> None:
        self._check_writable(obj)
        # Clear any instance-dict override
        obj.__dict__.pop(self.public_name, None)
        d: dict[str, Any] | None = getattr(obj, self.dict_attr)
        if d is None:
            # No backing dict - store as instance override
            obj.__dict__[self.public_name] = value
            return
        # `None` clears the key (an optional field is being unset); there is
        # no value to validate in that case.
        if value is None:
            d.pop(self.key, None)
        else:
            d[self.key] = self._coerce(obj, value)
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
        return cast(
            "CosField[bool | None]",
            cls(dict_attr, key, transform=bool, reverse=bool, **kwargs),
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
        """Create a CosField that coerces to float in both directions.

        The write-side coercion matters for byte fidelity: AE stores
        these keys as floats, and an `int` passed by a caller would
        serialize without the decimal marker.
        """
        if "reverse" not in kwargs:
            kwargs["reverse"] = float
        return cast(
            "CosField[float | None]", cls(dict_attr, key, transform=float, **kwargs)
        )

    @classmethod
    def int(
        cls,
        dict_attr: str,
        key: str,
        **kwargs: Any,
    ) -> CosField[int | None]:
        """Create a CosField for integer-stored keys.

        Coerces to `int` on read and rounds to the nearest integer on
        write. AE stores these keys as integers; a real-typed value is
        misread at 16.16 scale (stored `50.0` read back as `3276800`,
        probed AE 2026), so the write-side coercion matters for fidelity.
        """
        if "reverse" not in kwargs:
            kwargs["reverse"] = round
        return cast(
            "CosField[int | None]", cls(dict_attr, key, transform=int, **kwargs)
        )
