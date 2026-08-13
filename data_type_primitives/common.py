from collections.abc import Callable
from decimal import Decimal
from enum import Enum
from typing import Any, NamedTuple, TypeVar

from pydantic_core import core_schema


class OrderType(Enum):
    """Canonical order type for the hb-* ecosystem.

    The integer values carry NO semantics. They are a historical artifact of the
    original hummingbot ``common.py``: they are not ordered, not persisted, and not
    part of any wire format. As of 2026-08-12 there are zero reads of
    ``OrderType.<MEMBER>.value`` anywhere in hummingbot/ or the sub-packages.

    ``name`` is the stable public identity. Every consumer is name-keyed:

    * persistence writes ``.name`` into TEXT columns
      (``hummingbot/connector/markets_recorder.py:401,457``)
    * cross-package adapters bridge via ``Canonical[self.name]``
      (hb-strategy-framework and hb-market-connector hb_compat layers)

    Do not introduce dependencies on ``.value``, and do not rename members --
    a rename silently breaks every name-keyed bridge and orphans existing DB rows.
    Enforced by tests/test_enum_wire_invariants.py.
    """

    MARKET = 1
    LIMIT = 2
    LIMIT_MAKER = 3
    AMM_SWAP = 4
    AMM_ADD = 5  # Add liquidity to AMM/CLMM pool
    AMM_REMOVE = 6  # Remove liquidity from AMM/CLMM pool
    # Conditional order types (exchange-native)
    STOP_LOSS = 7
    TAKE_PROFIT = 8
    TRAILING_STOP = 9
    STOP_LOSS_LIMIT = 10
    TAKE_PROFIT_LIMIT = 11
    TRAILING_STOP_LIMIT = 12

    def is_limit_type(self):
        return self in (
            OrderType.LIMIT,
            OrderType.LIMIT_MAKER,
            OrderType.STOP_LOSS_LIMIT,
            OrderType.TAKE_PROFIT_LIMIT,
            OrderType.TRAILING_STOP_LIMIT,
        )

    def is_delayed_market_type(self):
        """Returns True for conditional orders that trigger a market execution."""
        return self in (OrderType.STOP_LOSS, OrderType.TAKE_PROFIT, OrderType.TRAILING_STOP)

    def is_conditional_type(self):
        """Returns True for any conditional/triggered order type."""
        return self in (
            OrderType.STOP_LOSS,
            OrderType.TAKE_PROFIT,
            OrderType.TRAILING_STOP,
            OrderType.STOP_LOSS_LIMIT,
            OrderType.TAKE_PROFIT_LIMIT,
            OrderType.TRAILING_STOP_LIMIT,
        )


class OpenOrder(NamedTuple):
    client_order_id: str
    trading_pair: str
    price: Decimal
    amount: Decimal
    executed_amount: Decimal
    status: str
    order_type: OrderType
    is_buy: bool
    time: int
    exchange_order_id: str


class PositionAction(Enum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    NIL = "NIL"


# For Derivatives Exchanges
class PositionSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"


# For Derivatives Exchanges
class PositionMode(Enum):
    HEDGE = "HEDGE"
    ONEWAY = "ONEWAY"


class PriceType(Enum):
    MidPrice = 1
    BestBid = 2
    BestAsk = 3
    LastTrade = 4
    LastOwnTrade = 5
    InventoryCost = 6
    Custom = 7


class TradeType(Enum):
    """Canonical trade side for the hb-* ecosystem.

    Unlike OrderType, these integer values ARE load-bearing and must not change.
    Hummingbot's order-book message format encodes the trade side numerically::

        # connector/**/<exchange>_api_order_book_data_source.py  (writers)
        "trade_type": float(TradeType.SELL.value) if ... else float(TradeType.BUY.value)

        # core/data_type/order_book_tracker.py:697  (reader)
        if trade_message.content["trade_type"] == float(TradeType.SELL.value)

    As of 2026-08-12 this convention spans 55 sites across 43 files in hummingbot/:
    54 float-wrapped, plus one bare-int writer at
    ``connector/derivative/decibel_perpetual/decibel_perpetual_api_order_book_data_source.py:287``
    which currently interoperates only because ``2 == 2.0``.

    Converting this enum to StrEnum, or renumbering it, breaks all of them at
    runtime with no type error, because ``float("buy")`` raises ValueError. Any
    such change must migrate the order-book wire format first.
    Enforced by tests/test_enum_wire_invariants.py.
    """

    BUY = 1
    SELL = 2
    RANGE = 3


class LPType(Enum):
    ADD = 1
    REMOVE = 2
    COLLECT = 3


class LimitOrderStatus(Enum):
    UNKNOWN = 0
    NEW = 1
    OPEN = 2
    CANCELING = 3
    CANCELED = 4
    COMPLETED = 5
    FAILED = 6


_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class GroupedSetDict(dict[_KT, set[_VT]]):
    def add_or_update(self, key: _KT, *args: _VT) -> "GroupedSetDict":
        if key in self:
            self[key].update(args)
        else:
            self[key] = set(args)
        return self

    def remove(self, key: _KT, value: _VT) -> "GroupedSetDict":
        if key in self:
            self[key].discard(value)
            if not self[key]:  # If set becomes empty, remove the key
                del self[key]
        return self

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: Any,
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.dict_schema(
                core_schema.any_schema(), core_schema.set_schema(core_schema.any_schema())
            ),
        )


MarketDict = GroupedSetDict[str, set[str]]


# TODO? : Allow pulling the hash for _KT via a lambda so that things like type can be a key?
class LazyDict[KT, VT](dict[KT, VT]):
    def __init__(self, default_value_factory: Callable[[KT], VT] = None):
        super().__init__()
        self.default_value_factory = default_value_factory

    def __missing__(self, key: KT) -> VT:
        if self.default_value_factory is None:
            raise KeyError(f"Key {key} not found in {self} and no default value factory is set")
        self[key] = self.default_value_factory(key)
        return self[key]

    def get(self, key: KT) -> VT:
        if key in self:
            return self[key]
        return self.__missing__(key)

    def get_or_add(self, key: KT, value_factory: Callable[[], VT]) -> VT:
        if key not in self:
            self[key] = value_factory()
        return self[key]
