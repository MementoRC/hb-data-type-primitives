"""Tests for cancellation_result.py — CancellationResult NamedTuple."""

import pytest

import data_type_primitives
from data_type_primitives.cancellation_result import (
    CancellationResult,
)

# --- Importability ---


@pytest.mark.unit
def test_top_level_export_available() -> None:
    """CancellationResult is importable from data_type_primitives top-level."""
    assert data_type_primitives.CancellationResult is CancellationResult


# --- Construction tests ---


@pytest.mark.unit
def test_cancellation_result_success() -> None:
    result = CancellationResult(order_id="order-123", success=True)
    assert result.order_id == "order-123"
    assert result.success is True


@pytest.mark.unit
def test_cancellation_result_failure() -> None:
    result = CancellationResult(order_id="order-456", success=False)
    assert result.order_id == "order-456"
    assert result.success is False


@pytest.mark.unit
def test_cancellation_result_is_named_tuple() -> None:
    result = CancellationResult(order_id="abc", success=True)
    assert result[0] == "abc"
    assert result[1] is True
    assert result._fields == ("order_id", "success")


@pytest.mark.unit
def test_cancellation_result_equality() -> None:
    a = CancellationResult(order_id="x", success=True)
    b = CancellationResult(order_id="x", success=True)
    c = CancellationResult(order_id="x", success=False)
    assert a == b
    assert a != c
