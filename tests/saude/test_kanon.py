"""Tests for src/saude/kanon.py — k-anonymity suppression."""

from __future__ import annotations

import pytest


def _make_df(values: list[int | None]):
    pl = pytest.importorskip("polars", reason="polars not installed")
    return pl.DataFrame({"count": values})


def test_suppress_k_below_threshold():
    from src.saude.kanon import suppress_k

    df = _make_df([1, 2, 3, 4])
    result = suppress_k(df, col="count", k=5)
    assert result["suprimido"].all()
    assert result["count"].is_null().all()


def test_suppress_k_above_threshold():
    from src.saude.kanon import suppress_k

    df = _make_df([5, 10, 100])
    result = suppress_k(df, col="count", k=5)
    assert not result["suprimido"].any()
    assert result["count"].to_list() == [5, 10, 100]


def test_suppress_k_exactly_at_threshold():
    """Value == k must NOT be suppressed (only < k is suppressed)."""
    from src.saude.kanon import suppress_k

    df = _make_df([5])
    result = suppress_k(df, col="count", k=5)
    assert not result["suprimido"][0]
    assert result["count"][0] == 5


def test_suppress_k_mixed():
    from src.saude.kanon import suppress_k

    df = _make_df([3, 5, 7, 2, 10])
    result = suppress_k(df, col="count", k=5)
    suppressed = result["suprimido"].to_list()
    assert suppressed == [True, False, False, True, False]


def test_suppress_k_adds_suprimido_column():
    from src.saude.kanon import suppress_k

    df = _make_df([10])
    result = suppress_k(df, col="count", k=5)
    assert "suprimido" in result.columns


def test_suppress_k_default_k_is_5():
    """Default k=5 matches the health data privacy requirement."""
    from src.saude.kanon import suppress_k, _DEFAULT_K

    assert _DEFAULT_K == 5
    df = _make_df([4])
    result = suppress_k(df, col="count")
    assert result["suprimido"][0]


def test_is_suppressed_none():
    from src.saude.kanon import is_suppressed

    assert is_suppressed(None) is True


def test_is_suppressed_nan():
    from src.saude.kanon import is_suppressed
    import math

    assert is_suppressed(float("nan")) is True


def test_is_suppressed_valid_value():
    from src.saude.kanon import is_suppressed

    assert is_suppressed(10) is False
    assert is_suppressed(0) is False
    assert is_suppressed(5) is False
