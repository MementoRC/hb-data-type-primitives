"""Smoke + basic tests for in_flight_order module."""

import logging
from decimal import Decimal

import pytest

import data_type_primitives
from data_type_primitives.common import OrderType, PositionAction, TradeType
from data_type_primitives.in_flight_order import (
    InFlightOrder,
    OrderState,
    OrderUpdate,
    PerpetualDerivativeInFlightOrder,
    TradeUpdate,
)
from data_type_primitives.trade_fee import AddedToCostTradeFee, TokenAmount


def _make_order(
    client_order_id: str = "OID-1",
    trading_pair: str = "ETH-USDT",
    amount: Decimal = Decimal("1.0"),
    price: Decimal = Decimal("2000.0"),
) -> InFlightOrder:
    return InFlightOrder(
        client_order_id=client_order_id,
        trading_pair=trading_pair,
        order_type=OrderType.LIMIT,
        trade_type=TradeType.BUY,
        amount=amount,
        creation_timestamp=1_000_000.0,
        price=price,
    )


@pytest.mark.unit
def test_in_flight_order_classes_importable_from_package() -> None:
    """All in_flight_order classes are accessible from the top-level package."""
    assert data_type_primitives.InFlightOrder is InFlightOrder
    assert data_type_primitives.PerpetualDerivativeInFlightOrder is PerpetualDerivativeInFlightOrder
    assert data_type_primitives.OrderUpdate is OrderUpdate
    assert data_type_primitives.TradeUpdate is TradeUpdate
    assert data_type_primitives.OrderState is OrderState


@pytest.mark.unit
def test_in_flight_order_initial_state() -> None:
    order = _make_order()
    assert order.client_order_id == "OID-1"
    assert order.trading_pair == "ETH-USDT"
    assert order.current_state == OrderState.PENDING_CREATE
    assert order.is_pending_create
    assert order.is_open
    assert not order.is_done


@pytest.mark.unit
def test_in_flight_order_base_and_quote_asset() -> None:
    order = _make_order(trading_pair="BTC-USDC")
    assert order.base_asset == "BTC"
    assert order.quote_asset == "USDC"


@pytest.mark.unit
def test_order_update_transitions_state() -> None:
    order = _make_order()
    update = OrderUpdate(
        trading_pair="ETH-USDT",
        update_timestamp=1_000_001.0,
        new_state=OrderState.OPEN,
        client_order_id="OID-1",
        exchange_order_id="EX-42",
    )
    changed = order.update_with_order_update(update)
    assert changed
    assert order.current_state == OrderState.OPEN
    assert order.exchange_order_id == "EX-42"


@pytest.mark.unit
def test_trade_update_registers_fill() -> None:
    order = _make_order(amount=Decimal("2.0"))
    fee = AddedToCostTradeFee(percent=Decimal("0.001"))
    tu = TradeUpdate(
        trade_id="T1",
        client_order_id="OID-1",
        exchange_order_id="EX-42",
        trading_pair="ETH-USDT",
        fill_timestamp=1_000_002.0,
        fill_price=Decimal("2000.0"),
        fill_base_amount=Decimal("1.0"),
        fill_quote_amount=Decimal("2000.0"),
        fee=fee,
    )
    changed = order.update_with_trade_update(tu)
    assert changed
    assert order.executed_amount_base == Decimal("1.0")
    assert not order.is_filled  # only half filled


@pytest.mark.unit
def test_perpetual_order_build_message_includes_position() -> None:
    order = PerpetualDerivativeInFlightOrder(
        client_order_id="PO-1",
        trading_pair="BTC-USDT",
        order_type=OrderType.LIMIT,
        trade_type=TradeType.BUY,
        amount=Decimal("0.1"),
        creation_timestamp=1_000_000.0,
        price=Decimal("50000.0"),
        position=PositionAction.OPEN,
    )
    msg = order.build_order_created_message()
    assert "OPEN" in msg
    assert "BTC-USDT" in msg


@pytest.mark.unit
def test_cumulative_fee_paid_uses_stdlib_logger_on_error(caplog: pytest.LogCaptureFixture) -> None:
    """Verify that fee calculation errors are logged via stdlib logger (not HummingbotLogger)."""
    order = _make_order()
    # Inject a fee object whose fee_amount_in_token will raise
    broken_fee = AddedToCostTradeFee(
        percent=Decimal("0.001"),
        flat_fees=[TokenAmount("UNKNOWN_TOKEN_XYZ", Decimal("1"))],
    )
    tu = TradeUpdate(
        trade_id="T-err",
        client_order_id="OID-1",
        exchange_order_id=None,  # type: ignore[arg-type]
        trading_pair="ETH-USDT",
        fill_timestamp=1_000_002.0,
        fill_price=Decimal("2000.0"),
        fill_base_amount=Decimal("0.5"),
        fill_quote_amount=Decimal("1000.0"),
        fee=broken_fee,
    )
    order.order_fills["T-err"] = tu

    with caplog.at_level(logging.ERROR, logger="data_type_primitives.in_flight_order"):
        # cumulative_fee_paid triggers fee_amount_in_token which calls _get_exchange_rate
        # which does a lazy import of hummingbot.core.rate_oracle — not available in sub-pkg,
        # so it will raise ImportError, which cumulative_fee_paid catches and logs.
        result = order.cumulative_fee_paid("ETH")

    assert result == Decimal("0")
    # Confirm at least one log record was emitted via stdlib (not a crash)
    assert any("Error calculating fee paid" in r.message for r in caplog.records)
