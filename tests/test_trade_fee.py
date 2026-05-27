"""Smoke + basic tests for trade_fee module."""

from decimal import Decimal

import pytest

import data_type_primitives
from data_type_primitives.trade_fee import (
    AddedToCostTradeFee,
    DeductedFromReturnsTradeFee,
    MakerTakerExchangeFeeRates,
    TokenAmount,
    TradeFeeBase,
    TradeFeeSchema,
)


@pytest.mark.unit
def test_trade_fee_module_importable_from_package() -> None:
    """All trade_fee classes are accessible from the top-level package."""
    assert data_type_primitives.TradeFeeBase is TradeFeeBase
    assert data_type_primitives.AddedToCostTradeFee is AddedToCostTradeFee
    assert data_type_primitives.DeductedFromReturnsTradeFee is DeductedFromReturnsTradeFee
    assert data_type_primitives.TradeFeeSchema is TradeFeeSchema
    assert data_type_primitives.TokenAmount is TokenAmount
    assert data_type_primitives.MakerTakerExchangeFeeRates is MakerTakerExchangeFeeRates


@pytest.mark.unit
def test_token_amount_construction_and_json_roundtrip() -> None:
    ta = TokenAmount(token="ETH", amount=Decimal("0.01"))
    assert ta.token == "ETH"
    assert ta.amount == Decimal("0.01")
    data = ta.to_json()
    assert data == {"token": "ETH", "amount": "0.01"}
    ta2 = TokenAmount.from_json(data)
    assert ta2.token == ta.token
    assert ta2.amount == ta.amount


@pytest.mark.unit
def test_trade_fee_schema_defaults() -> None:
    schema = TradeFeeSchema()
    assert schema.percent_fee_token is None
    assert schema.maker_percent_fee_decimal == Decimal(0)
    assert schema.taker_percent_fee_decimal == Decimal(0)
    assert schema.buy_percent_fee_deducted_from_returns is False


@pytest.mark.unit
def test_added_to_cost_fee_json_roundtrip() -> None:
    fee = AddedToCostTradeFee(percent=Decimal("0.001"))
    data = fee.to_json()
    assert data["fee_type"] == "AddedToCost"
    assert data["percent"] == "0.001"
    fee2 = TradeFeeBase.from_json(data)
    assert isinstance(fee2, AddedToCostTradeFee)
    assert fee2.percent == Decimal("0.001")


@pytest.mark.unit
def test_deducted_from_returns_fee_json_roundtrip() -> None:
    fee = DeductedFromReturnsTradeFee(
        percent=Decimal("0.002"),
        flat_fees=[TokenAmount("BNB", Decimal("0.05"))],
    )
    data = fee.to_json()
    assert data["fee_type"] == "DeductedFromReturns"
    fee2 = TradeFeeBase.from_json(data)
    assert isinstance(fee2, DeductedFromReturnsTradeFee)
    assert len(fee2.flat_fees) == 1
    assert fee2.flat_fees[0].token == "BNB"


@pytest.mark.unit
def test_fee_asset_returns_percent_token_when_set() -> None:
    fee = AddedToCostTradeFee(percent=Decimal("0.001"), percent_token="BNB")
    assert fee.fee_asset == "BNB"


@pytest.mark.unit
def test_maker_taker_exchange_fee_rates_construction() -> None:
    rates = MakerTakerExchangeFeeRates(
        maker=Decimal("0.001"),
        taker=Decimal("0.002"),
        maker_flat_fees=[],
        taker_flat_fees=[],
    )
    assert rates.maker == Decimal("0.001")
    assert rates.taker == Decimal("0.002")
