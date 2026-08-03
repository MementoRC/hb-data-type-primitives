"""Tests for exceptions.py — Hummingbot sub-package exception hierarchy."""

import pytest

import data_type_primitives
from data_type_primitives.exceptions import (
    ArgumentParserError,
    HummingbotBaseException,
    InvalidController,
    InvalidScriptModule,
    OracleRateUnavailable,
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
