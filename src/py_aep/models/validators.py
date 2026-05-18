"""Reusable validator factories for descriptor fields.

Each factory returns a callable `(value, instance) -> None` that raises
`ValueError` or `TypeError` when the value is invalid.  Pass the
returned callable as the `validate` parameter of a descriptor.

The `instance` argument is the model object being modified, allowing
cross-field validation (e.g. checking that one field is >= another).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable, Sequence


def validate_number(
    *,
    min: float | Callable[[Any], float | None] | None = None,
    max: float | Callable[[Any], float | None] | None = None,
    integer: bool = False,
) -> Callable[[object, Any], None]:
    """Return a validator that checks a numeric value.

    Args:
        min: Minimum allowed value (inclusive). May be a static number
            or a callable `(instance) -> float` for dynamic bounds.
        max: Maximum allowed value (inclusive). May be a static number
            or a callable `(instance) -> float` for dynamic bounds.
        integer: When `True`, reject non-`int` values.
    """
    type_label = "an integer" if integer else "a number"

    def _validator(value: object, instance: Any = None) -> None:
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
    length: int | Callable[[Any], int | None] | None = None,
    min: float | Callable[[Any], float | None] | None = None,
    max: float | Callable[[Any], float | None] | None = None,
    integer: bool = False,
) -> Callable[[object, Any], None]:
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
    _element_validator = validate_number(min=min, max=max, integer=integer)

    def _validator(value: object, instance: Any = None) -> None:
        try:
            items: Sequence[object] = list(value)  # type: ignore[call-overload]
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


def validate_one_of(
    allowed: Sequence[object],
) -> Callable[[object, Any], None]:
    """Return a validator that checks value is in the allowed set.

    Args:
        allowed: Sequence of valid values.
    """
    allowed_set = set(allowed)
    formatted = ", ".join(str(v) for v in allowed)

    def _validator(value: object, instance: Any = None) -> None:
        try:
            if float(value) not in allowed_set:  # type: ignore[arg-type]
                raise ValueError(f"must be one of [{formatted}], got {value}")
        except TypeError:
            raise TypeError(f"expected a number, got {type(value).__name__}") from None

    return _validator


def validate_string(
    *,
    allow_empty: bool = True,
    max_length: int | None = None,
) -> Callable[[object, Any], None]:
    """Return a validator that checks a string value.

    Args:
        allow_empty: When `False`, reject empty strings.
        max_length: Maximum allowed character count.
    """

    def _validator(value: object, instance: Any = None) -> None:
        if not isinstance(value, str):
            raise TypeError(f"expected a string, got {type(value).__name__}")
        if not allow_empty and not value:
            raise ValueError("must not be empty")
        if max_length is not None and len(value) > max_length:
            raise ValueError(
                f"must be at most {max_length} characters, got {len(value)}"
            )

    return _validator
