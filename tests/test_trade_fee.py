"""Smoke + basic tests for trade_fee module."""

from decimal import Decimal

import pytest

import data_type_primitives
from data_type_primitives.common import PositionAction, TradeType
from data_type_primitives.trade_fee import (
    AddedToCostTradeFee,
    DeductedFromReturnsTradeFee,
    MakerTakerExchangeFeeRates,
    TokenAmount,
    TradeFeeBase,
    TradeFeeSchema,
    set_default_rate_source_provider,
)


class _Rates:
    def __init__(self, rates: dict[str, Decimal | None]) -> None:
        self.rates = rates
        self.calls: list[str] = []

    def get_pair_rate(self, trading_pair: str) -> Decimal | None:
        self.calls.append(trading_pair)
        return self.rates.get(trading_pair)


class _Exchange:
    def __init__(self, prices: dict[str, Decimal]) -> None:
        self.prices = prices
        self.calls: list[tuple[str, bool]] = []

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        self.calls.append((trading_pair, is_buy))
        return self.prices[trading_pair]


class _Candidate:
    def __init__(
        self,
        collateral: TokenAmount | None,
        size_token: str = "ETH",
        size: Decimal = Decimal("2"),
        returns: TokenAmount | None = None,
    ) -> None:
        self.order_collateral = collateral
        self.potential_returns = returns
        self._size = (size_token, size)

    def get_size_token_and_order_size(self) -> tuple[str, Decimal]:
        return self._size


@pytest.fixture(autouse=True)
def _reset_rate_source_provider():
    yield
    set_default_rate_source_provider(None)


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
def test_token_amount_is_iterable_as_token_amount_pair() -> None:
    token, amount = TokenAmount("ETH", Decimal("1.5"))
    assert (token, amount) == ("ETH", Decimal("1.5"))


@pytest.mark.unit
def test_schema_coerces_values_to_decimal() -> None:
    schema = TradeFeeSchema(
        maker_percent_fee_decimal=0.5,  # type: ignore[arg-type]
        taker_percent_fee_decimal="0.25",  # type: ignore[arg-type]
        maker_fixed_fees=[TokenAmount("BNB", "0.1")],  # type: ignore[arg-type]
        taker_fixed_fees=[TokenAmount("ETH", 2)],  # type: ignore[arg-type]
    )
    assert schema.maker_percent_fee_decimal == Decimal("0.5")
    assert schema.taker_percent_fee_decimal == Decimal("0.25")
    assert schema.maker_fixed_fees == [TokenAmount("BNB", Decimal("0.1"))]
    assert isinstance(schema.maker_fixed_fees[0].amount, Decimal)
    assert isinstance(schema.taker_fixed_fees[0].amount, Decimal)


@pytest.mark.unit
def test_schema_rejects_fee_token_with_deduct_from_returns() -> None:
    with pytest.raises(AssertionError):
        TradeFeeSchema(percent_fee_token="BNB", buy_percent_fee_deducted_from_returns=True)


@pytest.mark.unit
def test_fee_class_for_type_resolves_known_and_rejects_unknown() -> None:
    assert TradeFeeBase.fee_class_for_type("AddedToCost") is AddedToCostTradeFee
    assert TradeFeeBase.fee_class_for_type("DeductedFromReturns") is DeductedFromReturnsTradeFee
    with pytest.raises(KeyError):
        TradeFeeBase.fee_class_for_type("Nope")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("trade_type", "deducted", "fee_token", "expected"),
    [
        (TradeType.BUY, False, None, AddedToCostTradeFee),
        (TradeType.BUY, True, None, DeductedFromReturnsTradeFee),
        (TradeType.BUY, False, "BNB", AddedToCostTradeFee),
        (TradeType.SELL, False, None, DeductedFromReturnsTradeFee),
        (TradeType.SELL, False, "BNB", DeductedFromReturnsTradeFee),
    ],
)
def test_new_spot_fee_selects_class(trade_type, deducted, fee_token, expected) -> None:
    schema = TradeFeeSchema(
        percent_fee_token=fee_token, buy_percent_fee_deducted_from_returns=deducted
    )
    fee = TradeFeeBase.new_spot_fee(schema, trade_type, percent=Decimal("0.01"), percent_token="X")
    assert type(fee) is expected
    assert fee.percent == Decimal("0.01")
    assert fee.percent_token == "X"
    assert fee.flat_fees == []


@pytest.mark.unit
@pytest.mark.parametrize(
    ("action", "fee_token", "expected"),
    [
        (PositionAction.OPEN, None, AddedToCostTradeFee),
        (PositionAction.CLOSE, None, DeductedFromReturnsTradeFee),
        (PositionAction.CLOSE, "USDT", AddedToCostTradeFee),
    ],
)
def test_new_perpetual_fee_selects_class(action, fee_token, expected) -> None:
    flat = [TokenAmount("USDT", Decimal("1"))]
    fee = TradeFeeBase.new_perpetual_fee(
        TradeFeeSchema(percent_fee_token=fee_token), action, flat_fees=flat
    )
    assert type(fee) is expected
    assert fee.flat_fees == flat


@pytest.mark.unit
def test_fee_asset_falls_back_to_first_flat_fee_then_none() -> None:
    assert AddedToCostTradeFee().fee_asset is None
    fee = AddedToCostTradeFee(flat_fees=[TokenAmount("BNB", Decimal("1")), TokenAmount("X", 1)])
    assert fee.fee_asset == "BNB"


@pytest.mark.unit
def test_get_exchange_rate_uses_explicit_source() -> None:
    source = _Rates({"ETH-USDT": Decimal("2000")})
    assert TradeFeeBase._get_exchange_rate("ETH-USDT", source) == Decimal("2000")


@pytest.mark.unit
def test_get_exchange_rate_uses_registered_default_provider() -> None:
    source = _Rates({"ETH-USDT": Decimal("1900")})
    set_default_rate_source_provider(lambda: source)
    assert TradeFeeBase._get_exchange_rate("ETH-USDT") == Decimal("1900")
    assert source.calls == ["ETH-USDT"]


@pytest.mark.unit
def test_get_exchange_rate_without_source_raises() -> None:
    with pytest.raises(ValueError, match="Could not resolve a rate source"):
        TradeFeeBase._get_exchange_rate("ETH-USDT")


@pytest.mark.unit
def test_get_exchange_rate_missing_rate_raises() -> None:
    with pytest.raises(ValueError, match="Could not find the exchange rate for ETH-USDT"):
        TradeFeeBase._get_exchange_rate("ETH-USDT", _Rates({}))


@pytest.mark.unit
def test_fee_amount_in_token_percent_in_quote_needs_no_rate() -> None:
    fee = AddedToCostTradeFee(percent=Decimal("0.01"))
    result = fee.fee_amount_in_token("ETH-USDT", Decimal("2000"), Decimal("2"), "USDT")
    assert result == Decimal("40")


@pytest.mark.unit
def test_fee_amount_in_token_percent_converted_with_rate() -> None:
    fee = AddedToCostTradeFee(percent=Decimal("0.01"))
    source = _Rates({"ETH-USDT": Decimal("2000")})
    result = fee.fee_amount_in_token("ETH-USDT", Decimal("2000"), Decimal("2"), "ETH", source)
    assert result == Decimal("40") / Decimal("2000")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("price", "expected"),
    [(Decimal("2000"), Decimal("40") / Decimal("2000")), (Decimal("0"), Decimal("0"))],
)
def test_fee_amount_in_token_zero_rate_falls_back_to_price_or_one(price, expected) -> None:
    fee = AddedToCostTradeFee(percent=Decimal("0.01"))
    source = _Rates({"ETH-USDT": Decimal("0")})
    result = fee.fee_amount_in_token("ETH-USDT", price, Decimal("2"), "ETH", source)
    assert result == expected


@pytest.mark.unit
def test_fee_amount_in_token_flat_fees_all_branches() -> None:
    fee = AddedToCostTradeFee(
        flat_fees=[
            TokenAmount("USDT", Decimal("1")),  # same as target token
            TokenAmount("ETH", Decimal("0.5")),  # base fee -> quote via price
            TokenAmount("BNB", Decimal("2")),  # converted via BNB-USDT rate
        ]
    )
    source = _Rates({"BNB-USDT": Decimal("300")})
    result = fee.fee_amount_in_token("ETH-USDT", Decimal("2000"), Decimal("1"), "USDT", source)
    assert result == Decimal("1") + Decimal("1000") + Decimal("600")
    assert source.calls == ["BNB-USDT"]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ("ETH", "ETH", True),
        ("WETH", "ETH", True),
        ("ETH", "WETH", True),
        ("USDC.E", "USDC", True),
        ("UBTC", "BTC", True),
        ("ETH", "BTC", False),
        ("WETH", "BTC", False),
    ],
)
def test_are_tokens_interchangeable(first, second, expected) -> None:
    assert AddedToCostTradeFee()._are_tokens_interchangeable(first, second) is expected


@pytest.mark.unit
def test_fee_amount_in_token_treats_wrapped_token_as_equal() -> None:
    fee = AddedToCostTradeFee(percent=Decimal("0.01"))
    result = fee.fee_amount_in_token("WETH-USDC", Decimal("10"), Decimal("1"), "USDC.E")
    assert result == Decimal("0.1")


@pytest.mark.unit
def test_added_to_cost_cost_impact_zero_percent_is_none() -> None:
    candidate = _Candidate(TokenAmount("USDT", Decimal("100")))
    assert AddedToCostTradeFee().get_fee_impact_on_order_cost(candidate, _Exchange({})) is None


@pytest.mark.unit
def test_added_to_cost_cost_impact_in_collateral_token() -> None:
    fee = AddedToCostTradeFee(percent=Decimal("0.01"))
    candidate = _Candidate(TokenAmount("USDT", Decimal("100")))
    result = fee.get_fee_impact_on_order_cost(candidate, _Exchange({}))
    assert result == TokenAmount("USDT", Decimal("1"))


@pytest.mark.unit
def test_added_to_cost_cost_impact_fee_token_equals_size_token() -> None:
    fee = AddedToCostTradeFee(percent=Decimal("0.01"), percent_token="ETH")
    candidate = _Candidate(TokenAmount("USDT", Decimal("100")), size_token="ETH", size=Decimal("2"))
    exchange = _Exchange({})
    result = fee.get_fee_impact_on_order_cost(candidate, exchange)
    assert result == TokenAmount("ETH", Decimal("0.02"))
    assert exchange.calls == []


@pytest.mark.unit
def test_added_to_cost_cost_impact_prices_fee_token_via_exchange() -> None:
    fee = AddedToCostTradeFee(percent=Decimal("0.01"), percent_token="BNB")
    candidate = _Candidate(TokenAmount("USDT", Decimal("100")), size_token="ETH", size=Decimal("2"))
    exchange = _Exchange({"ETH-BNB": Decimal("7")})
    result = fee.get_fee_impact_on_order_cost(candidate, exchange)
    assert result == TokenAmount("BNB", Decimal("2") * Decimal("7") * Decimal("0.01"))
    assert exchange.calls == [("ETH-BNB", True)]


@pytest.mark.unit
def test_added_to_cost_returns_impact_is_none() -> None:
    fee = AddedToCostTradeFee(percent=Decimal("0.01"))
    candidate = _Candidate(None, returns=TokenAmount("USDT", Decimal("100")))
    assert fee.get_fee_impact_on_order_returns(candidate, _Exchange({})) is None


@pytest.mark.unit
def test_deducted_from_returns_cost_impact_is_none() -> None:
    fee = DeductedFromReturnsTradeFee(percent=Decimal("0.01"))
    candidate = _Candidate(TokenAmount("USDT", Decimal("100")))
    assert fee.get_fee_impact_on_order_cost(candidate, _Exchange({})) is None


@pytest.mark.unit
def test_deducted_from_returns_returns_impact_is_percent_of_returns() -> None:
    fee = DeductedFromReturnsTradeFee(percent=Decimal("0.01"))
    candidate = _Candidate(None, returns=TokenAmount("USDT", Decimal("250")))
    assert fee.get_fee_impact_on_order_returns(candidate, _Exchange({})) == Decimal("2.5")


@pytest.mark.unit
def test_trade_fee_base_is_abstract() -> None:
    with pytest.raises(TypeError):
        TradeFeeBase()  # type: ignore[abstract]


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
