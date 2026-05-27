"""Tests for common.py — enums and data classes from hummingbot/core/data_type/common.py."""

import pytest

import data_type_primitives
from data_type_primitives.common import (
    GroupedSetDict,
    LazyDict,
    LPType,
    MarketDict,
    OpenOrder,
    OrderType,
    PositionAction,
    PositionMode,
    PositionSide,
    PriceType,
    TradeType,
)

# --- Importability from top-level package ---


@pytest.mark.unit
def test_top_level_exports_available() -> None:
    """All common.py symbols are importable from data_type_primitives top-level."""
    assert data_type_primitives.OrderType is OrderType
    assert data_type_primitives.TradeType is TradeType
    assert data_type_primitives.PositionAction is PositionAction
    assert data_type_primitives.PositionMode is PositionMode
    assert data_type_primitives.PositionSide is PositionSide
    assert data_type_primitives.PriceType is PriceType
    assert data_type_primitives.LPType is LPType
    assert data_type_primitives.OpenOrder is OpenOrder
    assert data_type_primitives.GroupedSetDict is GroupedSetDict
    assert data_type_primitives.LazyDict is LazyDict
    assert data_type_primitives.MarketDict is MarketDict


# --- Enum round-trip tests ---


@pytest.mark.unit
def test_order_type_round_trip() -> None:
    assert OrderType.LIMIT.name == "LIMIT"
    assert OrderType["MARKET"] is OrderType.MARKET
    assert OrderType.MARKET.value == 1


@pytest.mark.unit
def test_trade_type_round_trip() -> None:
    assert TradeType.BUY.name == "BUY"
    assert TradeType["SELL"] is TradeType.SELL
    assert TradeType.SELL.value == 2


@pytest.mark.unit
def test_position_action_round_trip() -> None:
    assert PositionAction.OPEN.name == "OPEN"
    assert PositionAction["CLOSE"] is PositionAction.CLOSE
    assert PositionAction.NIL.value == "NIL"


@pytest.mark.unit
def test_position_mode_round_trip() -> None:
    assert PositionMode.HEDGE.name == "HEDGE"
    assert PositionMode["ONEWAY"] is PositionMode.ONEWAY


@pytest.mark.unit
def test_position_side_round_trip() -> None:
    assert PositionSide.LONG.name == "LONG"
    assert PositionSide.SHORT.value == "SHORT"
    assert PositionSide["BOTH"] is PositionSide.BOTH


@pytest.mark.unit
def test_price_type_round_trip() -> None:
    assert PriceType.MidPrice.name == "MidPrice"
    assert PriceType["BestBid"] is PriceType.BestBid
    assert PriceType.LastTrade.value == 4


@pytest.mark.unit
def test_lp_type_round_trip() -> None:
    assert LPType.ADD.name == "ADD"
    assert LPType["REMOVE"] is LPType.REMOVE
    assert LPType.COLLECT.value == 3


# --- OrderType method tests ---


@pytest.mark.unit
def test_order_type_is_limit_type() -> None:
    assert OrderType.LIMIT.is_limit_type() is True
    assert OrderType.MARKET.is_limit_type() is False
    assert OrderType.STOP_LOSS_LIMIT.is_limit_type() is True


@pytest.mark.unit
def test_order_type_is_conditional_type() -> None:
    assert OrderType.STOP_LOSS.is_conditional_type() is True
    assert OrderType.LIMIT.is_conditional_type() is False
    assert OrderType.TRAILING_STOP_LIMIT.is_conditional_type() is True


# --- GroupedSetDict smoke test ---


@pytest.mark.unit
def test_grouped_set_dict_add_and_remove() -> None:
    d: GroupedSetDict[str, str] = GroupedSetDict()
    d.add_or_update("key1", "a", "b")
    assert d["key1"] == {"a", "b"}
    d.remove("key1", "a")
    assert d["key1"] == {"b"}
    d.remove("key1", "b")
    assert "key1" not in d


# --- LazyDict smoke test ---


@pytest.mark.unit
def test_lazy_dict_default_factory() -> None:
    d: LazyDict[str, list] = LazyDict(default_value_factory=lambda k: [k])
    assert d["missing"] == ["missing"]
