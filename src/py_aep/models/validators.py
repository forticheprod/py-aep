"""Reusable validator factories for descriptor fields.

Each factory returns a callable `(value, instance) -> None` that raises
`ValueError` or `TypeError` when the value is invalid.  Pass the
returned callable as the `validate` parameter of a descriptor.

The `instance` argument is the model object being modified, allowing
cross-field validation (e.g. checking that one field is >= another).
"""

from __future__ import annotations

import math
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
    exclusive_min: bool = False,
) -> Callable[..., None]:
    """Return a validator that checks a numeric value.

    Args:
        min: Minimum allowed value. May be a static number or a callable
            `(instance) -> float` for dynamic bounds. Inclusive unless
            `exclusive_min` is set.
        max: Maximum allowed value (inclusive). May be a static number
            or a callable `(instance) -> float` for dynamic bounds.
        integer: When `True`, reject non-`int` values.
        exclusive_min: When `True`, the value must be strictly greater than
            `min` (e.g. a positive-but-non-zero size).
    """
    type_label = "an integer" if integer else "a number"

    def _validator(value: object, instance: object | None = None) -> None:
        if isinstance(value, (list, tuple)):
            raise TypeError(f"expected {type_label}, got {type(value).__name__}")
        if integer and (not isinstance(value, int) or isinstance(value, bool)):
            # `bool` subclasses `int`, so an isinstance check alone lets
            # `skip_frames = True` through as 1. AE rejects it outright
            # ("true is not an unsigned integer"), and so does every other
            # place in this codebase that had to hand-roll the same guard.
            # Not `type(value) is not int`: that would also reject IntEnum
            # members and numpy integers.
            raise TypeError(f"expected {type_label}, got {type(value).__name__}")
        if isinstance(value, float) and not math.isfinite(value):
            # NaN/inf would pass any `value < min or value > max` check (those
            # comparisons are always False for NaN) and serialize as a corrupt
            # IEEE special into a float32 field that AE may reject.
            raise ValueError(f"must be a finite number, got {value}")
        lo = min(instance) if callable(min) else min
        hi = max(instance) if callable(max) else max
        if lo is None and hi is None:
            # Unbounded fields accept non-numeric values: complex property
            # values (Gradient, Shape, ...) flow through this validator
            # with dynamic bounds that resolve to None.
            return
        if not isinstance(value, (int, float)):
            raise TypeError(f"expected {type_label}, got {type(value).__name__}")
        if lo is not None:
            if exclusive_min and value <= lo:
                raise ValueError(f"must be > {lo}, got {value}")
            if not exclusive_min and value < lo:
                raise ValueError(f"must be >= {lo}, got {value}")
        if hi is not None and value > hi:
            raise ValueError(f"must be <= {hi}, got {value}")

    return _validator


def validate_sequence(
    *,
    length: int | Callable[..., int | None] | None = None,
    min: float | Callable[..., float | None] | None = None,
    max: float | Callable[..., float | None] | None = None,
    integer: bool = False,
    exclusive_min: bool = False,
) -> Callable[..., None]:
    """Return a validator that checks a fixed-length numeric sequence.

    Args:
        length: Required number of elements. When `None`, any length
            is accepted. May be a callable `(instance) -> int` for
            dynamic bounds.
        min: Minimum allowed value per element. May be a static number
            or a callable `(instance) -> float` for dynamic bounds.
            Inclusive unless `exclusive_min` is set.
        max: Maximum allowed value per element (inclusive). May be a
            static number or a callable `(instance) -> float` for
            dynamic bounds.
        integer: When `True`, reject non-`int` elements.
        exclusive_min: When `True`, each element must be strictly greater
            than `min` (e.g. a non-zero-area box size).
    """
    type_label = "an integer" if integer else "a number"
    _element_validator = _validate_number(
        min=min, max=max, integer=integer, exclusive_min=exclusive_min
    )

    def _validator(value: object, instance: object | None = None) -> None:
        n = length(instance) if callable(length) else length
        if not isinstance(value, (list, tuple)):
            raise TypeError(
                f"expected a sequence{f' of {n} elements' if n is not None else ''}"
            )
        items = list(value)
        if n is not None and len(items) != n:
            raise ValueError(f"expected {n} elements, got {len(items)}")
        for i, v in enumerate(items):
            # Elements are numeric whatever the bounds are. `_validate_number`
            # skips its own type check once both bounds resolve to None, an
            # exemption for unbounded SCALAR fields carrying complex values
            # (Gradient, Shape, ...) - never for a member of a fixed-length
            # numeric sequence, which would otherwise accept a string here.
            if not isinstance(v, (int, float)):
                raise TypeError(
                    f"element [{i}] expected {type_label}, got {type(v).__name__}"
                )
            try:
                _element_validator(v, instance)
            except (TypeError, ValueError) as exc:
                raise type(exc)(f"element [{i}] {exc}") from None

    return _validator


#: One shared validator per enum class. Enum validators are factory-built
#: closures (unlike the module-level singleton validators), so callers that
#: default their enum validator - e.g. `RangeField.enum` and
#: `DocumentWideCosField.enum` for the same field - would otherwise hold
#: distinct instances; memoizing keeps them identity-equal.
_ENUM_VALIDATORS: dict[type, Callable[..., None]] = {}


def validate_enum(enum_cls: type) -> Callable[..., None]:
    """Return a validator that checks value is a member of `enum_cls`.

    Accepts both enum instances and their int equivalents. An int that is
    not a valid member value raises `ValueError`; any other wrong type
    raises `TypeError`. The returned validator is memoized per `enum_cls`.

    Args:
        enum_cls: The enum class the value must be a member of.
    """
    cached = _ENUM_VALIDATORS.get(enum_cls)
    if cached is not None:
        return cached

    def _validator(value: object, instance: object | None = None) -> None:
        if isinstance(value, enum_cls):
            return
        # Before the int branch: `bool` subclasses `int`, so `om.format =
        # True` would otherwise silently select the member whose value is 1.
        if isinstance(value, bool):
            raise TypeError(
                f"expected a {enum_cls.__name__}, got {type(value).__name__}"
            )
        if isinstance(value, int):
            try:
                enum_cls(value)
            except ValueError:
                raise ValueError(
                    f"{value!r} is not a valid {enum_cls.__name__} value"
                ) from None
            return
        raise TypeError(f"expected a {enum_cls.__name__}, got {type(value).__name__}")

    _ENUM_VALIDATORS[enum_cls] = _validator
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
    allow_null: bool = True,
) -> Callable[..., None]:
    """Return a validator that checks a string value.

    Args:
        allow_empty: When `False`, reject empty strings.
        max_length: Maximum allowed character count.
        allow_null: When `False`, reject strings containing a NUL (`\\x00`)
            character, which corrupt the COS/text blobs AE reads.
    """

    def _validator(value: object, instance: object | None = None) -> None:
        if not isinstance(value, str):
            raise TypeError(f"expected a string, got {type(value).__name__}")
        if not allow_empty and not value:
            raise ValueError("must not be empty")
        if not allow_null and "\x00" in value:
            raise ValueError("must not contain null bytes")
        if max_length is not None and len(value) > max_length:
            raise ValueError(
                f"must be at most {max_length} characters, got {len(value)}"
            )

    return _validator


def _validate_path(
    *,
    must_exist: bool | None = None,
    must_be_file: bool = False,
) -> Callable[..., None]:
    """Return a validator that checks a filesystem path.

    Args:
        must_exist: When `True`, reject paths that don't exist
            (`ValueError`). When `False`, reject paths that do exist
            (`FileExistsError`). When `None`, allow both.
        must_be_file: When `True`, also reject an existing path that is not
            a regular file. Without this a directory passes `must_exist` and
            only fails later, deep in a reader, as an OS-specific error
            (`PermissionError` on Windows, `IsADirectoryError` elsewhere).
    """

    def _validator(value: object, instance: object | None = None) -> None:
        if not isinstance(value, (str, os.PathLike)):
            raise TypeError(f"expected a file system path, got {type(value).__name__}")
        path = Path(value)
        if must_exist is True:
            if not path.exists():
                raise ValueError(f"path does not exist: {path}")
            if must_be_file and not path.is_file():
                raise ValueError(f"path is not a file: {path}")
        elif must_exist is False:
            if path.exists():
                raise FileExistsError(f"path already exists: {path}")
        # must_exist is None: accept both existing and non-existing paths

    return _validator


def validate_bool(value: object, instance: object | None = None) -> None:
    """Validate that a value is a `bool` (rejects 0/1 integers)."""
    if not isinstance(value, bool):
        raise TypeError(f"expected a bool, got {type(value).__name__}")


# ---- Shared domain validators ----
# Re-use these across models instead of defining per-module duplicates.

validate_number = _validate_number()

validate_positive_number = _validate_number(min=0.0)

validate_normalized_float = _validate_number(min=0.0, max=1.0)

validate_int = _validate_number(integer=True)

validate_positive_int = _validate_number(min=0, integer=True)

# A u2 field (e.g. the project revision counter) holds 0..65535.
validate_u2 = _validate_number(min=0, max=0xFFFF, integer=True)

# A u4 frame counter (e.g. a marker's frame_duration) holds 0..4294967295.
validate_u4 = _validate_number(min=0, max=0xFFFFFFFF, integer=True)

# A signed 32-bit metric (e.g. text kerning/tracking). AE 2026 reads values
# up to 2**31 fine but rejects the whole text layer for larger magnitudes
# ("Error reading the text layer", probed 2**31 OK / 10**10 fails); the s4
# range is the conservative bound that stays inside that limit. Not
# `integer=True`: kerning/tracking accept a float and round it on write.
validate_s4 = _validate_number(min=-(2**31), max=2**31 - 1)

# A marker duration in seconds maps to a u4 600ths-of-a-second field
# (round(seconds * 600)); cap at the field capacity and reject NaN/inf/negative.
validate_marker_duration = _validate_number(min=0.0, max=0xFFFFFFFF / 600.0)

validate_footage_dimension = _validate_number(min=4, max=30000, integer=True)

validate_solid_dimension = _validate_number(min=1, max=30000, integer=True)

validate_pixel_aspect = _validate_number(min=0.01, max=100.0)

# Min is one frame at the maximum 99 fps: a composition / footage duration of
# exactly 0 has no frames and After Effects rejects it (ExtendScript raises).
validate_duration = _validate_number(min=1.0 / 99.0, max=10800.0)

validate_frame_rate = _validate_number(min=1.0, max=99.0)

validate_vector2 = validate_sequence(length=2)

validate_vector3 = validate_sequence(length=3)

validate_rgb_color = validate_sequence(length=3, min=0.0, max=1.0)

validate_string = _validate_str()

validate_name = _validate_str(allow_empty=False)

# Strictly positive (non-zero) size, e.g. font size or stroke width.
validate_positive_nonzero_number = _validate_number(min=0.0, exclusive_min=True)

# A font PostScript name must be a non-empty, NUL-free string.
validate_font_name = _validate_str(allow_empty=False, allow_null=False)

# Text content may be empty but must not contain NUL bytes (they corrupt the
# COS text blob AE reads).
validate_text = _validate_str(allow_null=False)

# A box-text size needs a strictly positive width and height (a zero-area box
# has nothing to lay text into).
validate_box_size = validate_sequence(length=2, min=0.0, exclusive_min=True)

validate_path = _validate_path()

validate_path_exists = _validate_path(must_exist=True)

# For media paths: a directory must be refused here, not by the format reader.
validate_file_exists = _validate_path(must_exist=True, must_be_file=True)

validate_path_does_not_exist = _validate_path(must_exist=False)

# 3D renderer options validators
validate_advanced_quality = _validate_number(min=1, max=125, integer=True)
validate_shadow_smoothness = _validate_number(min=1, max=20, integer=True)
validate_casting_box_size = _validate_number(min=0, max=30000)
validate_casting_box_center = validate_sequence(length=3, min=-30000, max=30000)
validate_cinema_4d_quality = _validate_number(min=1, max=99, integer=True)
