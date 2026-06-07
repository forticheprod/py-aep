"""Reusable validator factories for descriptor fields.

Each factory returns a callable `(value, instance) -> None` that raises
`ValueError` or `TypeError` when the value is invalid.  Pass the
returned callable as the `validate` parameter of a descriptor.

The `instance` argument is the model object being modified, allowing
cross-field validation (e.g. checking that one field is >= another).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Callable, Iterable


def _validate_number(
    *,
    min: float | Callable[..., float | None] | None = None,
    max: float | Callable[..., float | None] | None = None,
    integer: bool = False,
) -> Callable[..., None]:
    """Return a validator that checks a numeric value.

    Args:
        min: Minimum allowed value (inclusive). May be a static number
            or a callable `(instance) -> float` for dynamic bounds.
        max: Maximum allowed value (inclusive). May be a static number
            or a callable `(instance) -> float` for dynamic bounds.
        integer: When `True`, reject non-`int` values.
    """
    type_label = "an integer" if integer else "a number"

    def _validator(value: object, instance: object | None = None) -> None:
        if isinstance(value, (list, tuple)):
            raise TypeError(f"expected {type_label}, got {type(value).__name__}")
        if integer and not isinstance(value, int):
            raise TypeError(f"expected {type_label}, got {type(value).__name__}")
        try:
            lo = min(instance) if callable(min) else min
            hi = max(instance) if callable(max) else max
            if lo is not None and value < lo:  # type: ignore[operator]
                raise ValueError(f"must be >= {lo}, got {value}")
            if hi is not None and value > hi:  # type: ignore[operator]
                raise ValueError(f"must be <= {hi}, got {value}")
        except TypeError:
            raise TypeError(
                f"expected {type_label}, got {type(value).__name__}"
            ) from None

    return _validator


def validate_sequence(
    *,
    length: int | Callable[..., int | None] | None = None,
    min: float | Callable[..., float | None] | None = None,
    max: float | Callable[..., float | None] | None = None,
    integer: bool = False,
) -> Callable[..., None]:
    """Return a validator that checks a fixed-length numeric sequence.

    Args:
        length: Required number of elements. When `None`, any length
            is accepted. May be a callable `(instance) -> int` for
            dynamic bounds.
        min: Minimum allowed value per element (inclusive). May be a
            static number or a callable `(instance) -> float` for
            dynamic bounds.
        max: Maximum allowed value per element (inclusive). May be a
            static number or a callable `(instance) -> float` for
            dynamic bounds.
        integer: When `True`, reject non-`int` elements.
    """
    _element_validator = _validate_number(min=min, max=max, integer=integer)

    def _validator(value: object, instance: object | None = None) -> None:
        try:
            items: list[object] = list(value)  # type: ignore[call-overload]
        except TypeError:
            n = length(instance) if callable(length) else length
            raise TypeError(
                f"expected a sequence{f' of {n} elements' if n is not None else ''}"
            ) from None
        n = length(instance) if callable(length) else length
        if n is not None and len(items) != n:
            raise ValueError(f"expected {n} elements, got {len(items)}")
        for i, v in enumerate(items):
            try:
                _element_validator(v, instance)
            except (TypeError, ValueError) as exc:
                raise type(exc)(f"element [{i}] {exc}") from None

    return _validator


def validate_enum(enum_cls: type) -> Callable[..., None]:
    """Return a validator that checks value is a member of `enum_cls`.

    Accepts both enum instances and their int equivalents. An int that is
    not a valid member value raises `ValueError`; any other wrong type
    raises `TypeError`.

    Args:
        enum_cls: The enum class the value must be a member of.
    """

    def _validator(value: object, instance: object | None = None) -> None:
        if isinstance(value, enum_cls):
            return
        if isinstance(value, int):
            try:
                enum_cls(value)
            except ValueError:
                raise ValueError(
                    f"{value!r} is not a valid {enum_cls.__name__} value"
                ) from None
            return
        raise TypeError(f"expected a {enum_cls.__name__}, got {type(value).__name__}")

    return _validator


def validate_one_of(
    allowed: Iterable[object],
) -> Callable[..., None]:
    """Return a validator that checks value is in the allowed set.

    Args:
        allowed: Iterable of valid values.
    """
    allowed_list = list(allowed)
    allowed_set = set(allowed_list)
    formatted = ", ".join(str(v) for v in allowed_list)

    def _validator(value: object, instance: object | None = None) -> None:
        if value not in allowed_set:
            raise ValueError(f"must be one of [{formatted}], got {value!r}")

    return _validator


def _validate_str(
    *,
    allow_empty: bool = True,
    max_length: int | None = None,
) -> Callable[..., None]:
    """Return a validator that checks a string value.

    Args:
        allow_empty: When `False`, reject empty strings.
        max_length: Maximum allowed character count.
    """

    def _validator(value: object, instance: object | None = None) -> None:
        if not isinstance(value, str):
            raise TypeError(f"expected a string, got {type(value).__name__}")
        if not allow_empty and not value:
            raise ValueError("must not be empty")
        if max_length is not None and len(value) > max_length:
            raise ValueError(
                f"must be at most {max_length} characters, got {len(value)}"
            )

    return _validator


def _validate_path(
    *,
    must_exist: bool | None = None,
) -> Callable[..., None]:
    """Return a validator that checks a filesystem path.

    Args:
        must_exist: When `True`, reject paths that don't exist.
            When `False`, reject paths that do exist. When `None`, allow both.
    """

    def _validator(value: object, instance: object | None = None) -> None:
        if not isinstance(value, (str, os.PathLike)):
            raise TypeError(f"expected a file system path, got {type(value).__name__}")
        path = Path(value)
        if must_exist:
            if not path.exists():
                raise ValueError(f"path does not exist: {path}")
        else:
            if path.exists():
                raise ValueError(f"path already exists: {path}")

    return _validator


# ---- Shared domain validators ----
# Re-use these across models instead of defining per-module duplicates.

validate_number = _validate_number()

validate_positive_number = _validate_number(min=0.0)

validate_normalized_float = _validate_number(min=0.0, max=1.0)

validate_int = _validate_number(integer=True)

validate_positive_int = _validate_number(min=0, integer=True)

validate_footage_dimension = _validate_number(min=4, max=30000, integer=True)

validate_solid_dimension = _validate_number(min=1, max=30000, integer=True)

validate_pixel_aspect = _validate_number(min=0.01, max=100.0)

validate_duration = _validate_number(min=0.0, max=10800.0)

validate_frame_rate = _validate_number(min=1.0, max=99.0)

validate_vector2 = validate_sequence(length=2)

validate_rgb_color = validate_sequence(length=3, min=0.0, max=1.0)

validate_string = _validate_str()

validate_name = _validate_str(allow_empty=False)

validate_path = _validate_path()

validate_path_does_not_exist = _validate_path(must_exist=False)
