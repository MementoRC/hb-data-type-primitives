"""Tests for exceptions.py — Hummingbot sub-package exception hierarchy."""

import pickle

import pytest

import data_type_primitives
from data_type_primitives.exceptions import (
    ArgumentParserError,
    HummingbotBaseException,
    InvalidController,
    InvalidScriptModule,
    OracleRateUnavailable,
    OrderOutcomeUnknownError,
)

# --- Importability ---


@pytest.mark.unit
def test_top_level_exports_available() -> None:
    """All 5 exception classes are importable from data_type_primitives top-level."""
    assert data_type_primitives.HummingbotBaseException is HummingbotBaseException
    assert data_type_primitives.ArgumentParserError is ArgumentParserError
    assert data_type_primitives.OracleRateUnavailable is OracleRateUnavailable
    assert data_type_primitives.InvalidScriptModule is InvalidScriptModule
    assert data_type_primitives.InvalidController is InvalidController


# --- Hierarchy tests ---


@pytest.mark.unit
@pytest.mark.parametrize(
    "exc_cls",
    [ArgumentParserError, OracleRateUnavailable, InvalidScriptModule, InvalidController],
)
def test_all_exceptions_inherit_base(exc_cls: type[Exception]) -> None:
    assert issubclass(exc_cls, HummingbotBaseException)


@pytest.mark.unit
def test_base_inherits_exception() -> None:
    assert issubclass(HummingbotBaseException, Exception)


@pytest.mark.unit
def test_exceptions_are_raisable() -> None:
    with pytest.raises(HummingbotBaseException):
        raise ArgumentParserError("bad args")


# --- OrderOutcomeUnknownError ---


@pytest.mark.unit
def test_order_outcome_unknown_exported_and_subclasses_base() -> None:
    assert data_type_primitives.OrderOutcomeUnknownError is OrderOutcomeUnknownError
    assert "OrderOutcomeUnknownError" in data_type_primitives.__all__
    assert issubclass(OrderOutcomeUnknownError, HummingbotBaseException)


@pytest.mark.unit
def test_order_outcome_unknown_stores_client_order_id() -> None:
    err = OrderOutcomeUnknownError("timeout", client_order_id="abc-1")
    assert err.client_order_id == "abc-1"
    assert str(err) == "timeout"


@pytest.mark.unit
def test_order_outcome_unknown_client_order_id_required_keyword_only() -> None:
    with pytest.raises(TypeError):
        OrderOutcomeUnknownError("timeout")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        OrderOutcomeUnknownError("timeout", "abc-1")  # type: ignore[misc]


@pytest.mark.unit
def test_order_outcome_unknown_pickle_round_trip() -> None:
    err = OrderOutcomeUnknownError("lost response", client_order_id="abc-2")
    restored = pickle.loads(pickle.dumps(err))  # noqa: S301
    assert type(restored) is OrderOutcomeUnknownError
    assert restored.client_order_id == "abc-2"
    assert str(restored) == "lost response"
