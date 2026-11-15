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


@pytest.mark.unit
def test_grouped_set_dict_add_or_update_merges_existing_key() -> None:
    d: GroupedSetDict[str, str] = GroupedSetDict()
    assert d.add_or_update("k", "a") is d
    d.add_or_update("k", "b", "a")
    assert d["k"] == {"a", "b"}


@pytest.mark.unit
def test_grouped_set_dict_remove_missing_key_or_value_is_noop() -> None:
    d: GroupedSetDict[str, str] = GroupedSetDict()
    d.add_or_update("k", "a")
    assert d.remove("absent", "a") is d
    d.remove("k", "zzz")
    assert d == {"k": {"a"}}


@pytest.mark.unit
def test_grouped_set_dict_pydantic_validation() -> None:
    from pydantic import TypeAdapter

    result = TypeAdapter(GroupedSetDict).validate_python({"k": ["a", "b"]})
    assert isinstance(result, GroupedSetDict)
    assert result == {"k": {"a", "b"}}


@pytest.mark.unit
def test_lazy_dict_without_factory_raises_key_error() -> None:
    d: LazyDict[str, int] = LazyDict()
    with pytest.raises(KeyError, match="no default value factory"):
        d["x"]


@pytest.mark.unit
def test_lazy_dict_get_returns_existing_or_creates_via_factory() -> None:
    calls: list[str] = []

    def factory(key: str) -> int:
        calls.append(key)
        return len(key)

    d: LazyDict[str, int] = LazyDict(default_value_factory=factory)
    d["abc"] = 99
    assert d.get("abc") == 99
    assert d.get("xy") == 2
    assert d["xy"] == 2
    assert calls == ["xy"]


@pytest.mark.unit
def test_lazy_dict_get_or_add_only_calls_factory_when_absent() -> None:
    d: LazyDict[str, int] = LazyDict()
    assert d.get_or_add("a", lambda: 1) == 1
    assert d.get_or_add("a", lambda: 2) == 1
