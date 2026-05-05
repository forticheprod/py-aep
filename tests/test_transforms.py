"""Tests for transform and reverse helper functions."""

from __future__ import annotations

import pytest

from py_aep.models.reverses import (
    denormalize_value,
    denormalize_values,
    reverse_fractional,
    reverse_frame_ticks,
    reverse_ratio,
    unpack_values,
)
from py_aep.models.transforms import (
    compute_fractional,
    compute_ratio,
    normalize_value,
    normalize_values,
    pack_values,
    strip_null,
)


class _Obj:
    """Simple attribute holder for tests."""

    def __init__(self, **kwargs: object) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# pack_values / unpack_values
# ---------------------------------------------------------------------------


class TestPackValues:
    def test_packs_multiple_fields(self) -> None:
        obj = _Obj(r=10, g=20, b=30)
        assert pack_values(obj, "r", "g", "b") == [10, 20, 30]

    def test_single_field(self) -> None:
        obj = _Obj(x=42)
        assert pack_values(obj, "x") == [42]

    def test_empty_fields(self) -> None:
        obj = _Obj()
        assert pack_values(obj) == []


class TestUnpackValues:
    def test_unpacks_matching_length(self) -> None:
        reverse = unpack_values("r", "g", "b")
        result = reverse([10, 20, 30], None)
        assert result == {"r": 10, "g": 20, "b": 30}

    def test_length_mismatch_raises(self) -> None:
        reverse = unpack_values("r", "g", "b")
        with pytest.raises(ValueError, match="Expected 3 values, got 2"):
            reverse([10, 20], None)

    def test_too_many_values_raises(self) -> None:
        reverse = unpack_values("x", "y")
        with pytest.raises(ValueError, match="Expected 2 values, got 3"):
            reverse([1, 2, 3], None)

    def test_single_field(self) -> None:
        reverse = unpack_values("x")
        assert reverse([42], None) == {"x": 42}


# ---------------------------------------------------------------------------
# compute_fractional / reverse_fractional
# ---------------------------------------------------------------------------


class TestComputeFractional:
    def test_integer_only(self) -> None:
        obj = _Obj(rate_int=30, rate_frac=0)
        assert compute_fractional(obj, "rate_int", "rate_frac") == 30.0

    def test_with_fractional(self) -> None:
        obj = _Obj(rate_int=29, rate_frac=63570)
        result = compute_fractional(obj, "rate_int", "rate_frac")
        assert abs(result - 29.97) < 0.01

    def test_custom_scale(self) -> None:
        obj = _Obj(ts_int=1, ts_frac=128)
        result = compute_fractional(obj, "ts_int", "ts_frac", scale=256)
        assert result == 1.5


class TestReverseFractional:
    def test_integer_value(self) -> None:
        reverse = reverse_fractional("rate_int", "rate_frac")
        result = reverse(30.0, None)
        assert result == {"rate_int": 30, "rate_frac": 0}

    def test_fractional_value(self) -> None:
        reverse = reverse_fractional("rate_int", "rate_frac")
        result = reverse(29.97, None)
        assert result["rate_int"] == 29
        assert abs(result["rate_frac"] - round(0.97 * 65536)) <= 1

    def test_custom_scale(self) -> None:
        reverse = reverse_fractional("ts_int", "ts_frac", scale=256)
        result = reverse(1.5, None)
        assert result == {"ts_int": 1, "ts_frac": 128}

    def test_roundtrip(self) -> None:
        reverse = reverse_fractional("i", "f")
        original = 23.976
        fields = reverse(original, None)
        obj = _Obj(i=fields["i"], f=fields["f"])
        restored = compute_fractional(obj, "i", "f")
        assert abs(restored - original) < 0.001


# ---------------------------------------------------------------------------
# compute_ratio / reverse_ratio
# ---------------------------------------------------------------------------


class TestComputeRatio:
    def test_simple_ratio(self) -> None:
        obj = _Obj(dur_d=30000, dur_v=10000)
        assert compute_ratio(obj, "dur_d", "dur_v") == 3.0

    def test_fractional_ratio(self) -> None:
        obj = _Obj(px_d=909091, px_v=1000000)
        result = compute_ratio(obj, "px_d", "px_v")
        assert abs(result - 0.909091) < 1e-6

    def test_zero_dividend(self) -> None:
        obj = _Obj(d=0, v=100)
        assert compute_ratio(obj, "d", "v") == 0.0

    def test_zero_divisor_raises(self) -> None:
        obj = _Obj(d=100, v=0)
        with pytest.raises(ZeroDivisionError):
            compute_ratio(obj, "d", "v")


class TestReverseRatio:
    def test_default_denominator(self) -> None:
        reverse = reverse_ratio("px")
        result = reverse(0.909091, None)
        assert result == {"px_dividend": 90909, "px_divisor": 100000}

    def test_custom_denominator(self) -> None:
        reverse = reverse_ratio("d", denominator_value=10000)
        result = reverse(3.0, None)
        assert result == {"d_dividend": 30000, "d_divisor": 10000}

    def test_roundtrip(self) -> None:
        reverse = reverse_ratio("r")
        original = 1.333333
        fields = reverse(original, None)
        obj = _Obj(r_dividend=fields["r_dividend"], r_divisor=fields["r_divisor"])
        restored = compute_ratio(obj, "r_dividend", "r_divisor")
        assert abs(restored - original) < 0.001


# ---------------------------------------------------------------------------
# reverse_frame_ticks
# ---------------------------------------------------------------------------


class TestReverseFrameTicks:
    def test_simple_frame_count(self) -> None:
        reverse = reverse_frame_ticks("duration")
        body = _Obj(frame_rate_integer=30, frame_rate_fractional=0)
        result = reverse(90, body)
        # 90 frames / 30fps = 3.0 seconds -> 3.0 * 10000 = 30000
        assert result == {"duration_dividend": 30000, "duration_divisor": 10000}

    def test_fractional_frame_rate(self) -> None:
        reverse = reverse_frame_ticks("duration")
        body = _Obj(frame_rate_integer=29, frame_rate_fractional=63570)
        result = reverse(30, body)
        # 30 frames / ~29.97 fps ~= 1.001 seconds
        expected_dividend = round(30 / 29.97 * 10000)
        assert abs(result["duration_dividend"] - expected_dividend) <= 1
        assert result["duration_divisor"] == 10000


# ---------------------------------------------------------------------------
# normalize / denormalize
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_normalize_value(self) -> None:
        assert normalize_value(255) == 1.0
        assert normalize_value(0) == 0.0
        assert abs(normalize_value(128) - 128 / 255) < 1e-6

    def test_normalize_values(self) -> None:
        result = normalize_values([0, 128, 255])
        assert result[0] == 0.0
        assert result[2] == 1.0

    def test_custom_scale(self) -> None:
        assert normalize_value(50, scale=100) == 0.5


class TestDenormalize:
    def test_denormalize_value(self) -> None:
        assert denormalize_value(1.0) == 255
        assert denormalize_value(0.0) == 0

    def test_denormalize_values(self) -> None:
        result = denormalize_values([0.0, 0.5, 1.0])
        assert result[0] == 0
        assert result[1] == 128
        assert result[2] == 255

    def test_roundtrip(self) -> None:
        original = [0.2, 0.5, 0.8]
        raw = denormalize_values(original)
        restored = normalize_values(raw)
        for a, b in zip(original, restored):
            assert abs(a - b) < 0.01


# ---------------------------------------------------------------------------
# strip_null
# ---------------------------------------------------------------------------


class TestStripNull:
    def test_strips_trailing_nulls(self) -> None:
        assert strip_null("hello\x00\x00\x00") == "hello"

    def test_no_nulls(self) -> None:
        assert strip_null("hello") == "hello"

    def test_bytes_input(self) -> None:
        assert strip_null(b"hello\x00\x00") == "hello"

    def test_empty_string(self) -> None:
        assert strip_null("") == ""

    def test_only_nulls(self) -> None:
        assert strip_null("\x00\x00") == ""
