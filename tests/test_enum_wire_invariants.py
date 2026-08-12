"""Regression tests pinning the enum contracts that external consumers depend on.

These make two implicit invariants explicit and enforced. See the OrderType and
TradeType class docstrings in data_type_primitives/common.py for full rationale.
"""

import pytest

from data_type_primitives.common import OrderType, TradeType

EXPECTED_ORDER_TYPE_NAMES = frozenset(
    {
        "MARKET",
        "LIMIT",
        "LIMIT_MAKER",
        "AMM_SWAP",
        "AMM_ADD",
        "AMM_REMOVE",
        "STOP_LOSS",
        "TAKE_PROFIT",
        "TRAILING_STOP",
        "STOP_LOSS_LIMIT",
        "TAKE_PROFIT_LIMIT",
        "TRAILING_STOP_LIMIT",
    }
)

EXPECTED_TRADE_TYPE_NAMES = frozenset({"BUY", "SELL", "RANGE"})


# --- TradeType: numeric order-book wire contract ---


@pytest.mark.unit
def test_trade_type_values_are_stable() -> None:
    """Hummingbot order-book messages encode side as float(TradeType.X.value).

    Reader: hummingbot/core/data_type/order_book_tracker.py:697.
    Renumbering breaks 55 sites across 43 files at runtime, with no type error.
    """
    assert TradeType.BUY.value == 1
    assert TradeType.SELL.value == 2
    assert TradeType.RANGE.value == 3


@pytest.mark.unit
def test_trade_type_values_survive_float_coercion() -> None:
    """float(member.value) IS the wire encoding; it must not raise and must round-trip."""
    for member in TradeType:
        assert isinstance(member.value, int)
        assert float(member.value) == member.value


@pytest.mark.unit
def test_trade_type_is_not_a_str_subclass() -> None:
    """Guards against a StrEnum conversion, which would make the wire encoding raise."""
    assert not issubclass(TradeType, str)


# --- Name stability: every cross-package bridge is name-keyed ---


@pytest.mark.unit
def test_order_type_member_names_are_stable() -> None:
    """Adapters bridge via Canonical[self.name]; persistence writes .name to TEXT.

    Renaming or removing a member silently breaks the hb-strategy-framework and
    hb-market-connector hb_compat adapters and orphans existing DB rows.
    """
    assert {member.name for member in OrderType} == EXPECTED_ORDER_TYPE_NAMES


@pytest.mark.unit
def test_trade_type_member_names_are_stable() -> None:
    assert {member.name for member in TradeType} == EXPECTED_TRADE_TYPE_NAMES


@pytest.mark.unit
def test_name_lookup_is_the_supported_api() -> None:
    """Canonical[name] round-trip is what every hb_compat adapter relies on."""
    for member in OrderType:
        assert OrderType[member.name] is member
    for member in TradeType:
        assert TradeType[member.name] is member
