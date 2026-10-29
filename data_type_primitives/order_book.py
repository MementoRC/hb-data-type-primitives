"""Order book value types shared by L2 packages (hb-data-type-primitives#20).

Part 1: ``OrderBookEntry`` and ``OrderBookSnapshot`` come from hb-strategy-framework.

Part 2: ``OrderBookRow``, ``ClientOrderBookRow``, ``OrderBookQueryResult``,
``ClientOrderBookQueryResult``, ``OrderBookMessageType`` and ``OrderBookMessage`` come from
hb-order-book ``order_book/core/{types,message}.py`` @ 9718f7d (hb-data-type-primitives#20).

``OrderBookEntry`` here is the pydantic price/quantity value, unrelated to hb-order-book's
engine ``OrderBookEntry``, which stays in hb-order-book. The Part 2 types are different
classes, so there is no symbol clash.

``OrderBookMessage`` deliberately diverges from hummingbot core (strict ``__lt__``/``__eq__``,
tuple ``__hash__``); see docs/divergences.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal  # noqa: TC003
from enum import Enum
from functools import total_ordering
from typing import Any, NamedTuple

from pydantic import BaseModel, ConfigDict


class OrderBookEntry(BaseModel):
    """Single price/quantity level in an order book."""

    model_config = ConfigDict(frozen=True)

    price: Decimal
    quantity: Decimal


class OrderBookSnapshot(BaseModel):
    """Immutable snapshot of an order book at a point in time.

    Bids and asks are ordered best-first (highest bid first, lowest ask first).
    """

    model_config = ConfigDict(frozen=True)

    timestamp: int
    """Unix timestamp in milliseconds."""
    bids: list[OrderBookEntry]
    asks: list[OrderBookEntry]

    @property
    def best_bid(self) -> Decimal:
        """Highest bid price. Raises ValueError if bids are empty."""
        if not self.bids:
            msg = "bids are empty"
            raise ValueError(msg)
        return self.bids[0].price

    @property
    def best_ask(self) -> Decimal:
        """Lowest ask price. Raises ValueError if asks are empty."""
        if not self.asks:
            msg = "asks are empty"
            raise ValueError(msg)
        return self.asks[0].price

    @property
    def spread(self) -> Decimal:
        """Spread between best ask and best bid."""
        return self.best_ask - self.best_bid


class OrderBookRow(NamedTuple):
    """Change applied to an OrderBook. Uses float internally for performance."""

    price: float
    amount: float
    update_id: int


class ClientOrderBookRow(NamedTuple):
    """Row used in market classes where OrderBook values are converted to Decimal."""

    price: Decimal
    amount: Decimal
    update_id: int


@dataclass(slots=True)
class OrderBookQueryResult:
    """Result of an OrderBook volume/price query (float values)."""

    query_price: float
    query_volume: float
    result_price: float
    result_volume: float


@dataclass(slots=True)
class ClientOrderBookQueryResult:
    """Result of an OrderBook volume/price query (Decimal values)."""

    query_price: Decimal
    query_volume: Decimal
    result_price: Decimal
    result_volume: Decimal


class OrderBookMessageType(Enum):
    SNAPSHOT = 1
    DIFF = 2
    TRADE = 3


class _OrderBookMessageBase(NamedTuple):
    type: OrderBookMessageType
    content: dict[str, Any]
    timestamp: float | None


@total_ordering
class OrderBookMessage(_OrderBookMessageBase):
    __slots__ = ()

    def __new__(
        cls,
        message_type: OrderBookMessageType,
        content: dict[str, Any],
        timestamp: float | None = None,
    ) -> OrderBookMessage:
        return super().__new__(cls, message_type, content, timestamp)

    @property
    def update_id(self) -> int:
        if self.type in (OrderBookMessageType.DIFF, OrderBookMessageType.SNAPSHOT):
            return self.content["update_id"]  # type: ignore[no-any-return]
        return -1

    @property
    def first_update_id(self) -> int:
        if self.type is OrderBookMessageType.DIFF:
            return self.content.get("first_update_id", self.update_id)  # type: ignore[no-any-return]
        return -1

    @property
    def trade_id(self) -> int:
        if self.type is OrderBookMessageType.TRADE:
            return self.content["trade_id"]  # type: ignore[no-any-return]
        return -1

    @property
    def trading_pair(self) -> str:
        return self.content["trading_pair"]  # type: ignore[no-any-return]

    @property
    def asks(self) -> list[OrderBookRow]:
        return [
            OrderBookRow(float(price), float(amount), self.update_id)
            for price, amount, *_ in self.content["asks"]
        ]

    @property
    def bids(self) -> list[OrderBookRow]:
        return [
            OrderBookRow(float(price), float(amount), self.update_id)
            for price, amount, *_ in self.content["bids"]
        ]

    @property
    def has_update_id(self) -> bool:
        return self.type in {OrderBookMessageType.DIFF, OrderBookMessageType.SNAPSHOT}

    @property
    def has_trade_id(self) -> bool:
        return self.type == OrderBookMessageType.TRADE

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OrderBookMessage):
            return NotImplemented
        if self.type != other.type:
            return False
        if self.has_update_id:
            return bool(self.update_id == other.update_id)
        return bool(self.trade_id == other.trade_id)

    def __ne__(self, other: object) -> bool:
        # tuple defines its own __ne__, which would bypass __eq__ above.
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    def __hash__(self) -> int:
        # Hash only what __eq__ compares: equal messages must hash equal.
        return hash((self.type, self.update_id if self.has_update_id else self.trade_id))

    def __lt__(self, other: OrderBookMessage) -> bool:  # type: ignore[override]
        if self.has_update_id and other.has_update_id:
            return bool(self.update_id < other.update_id)
        if self.has_trade_id and other.has_trade_id:
            return bool(self.trade_id < other.trade_id)
        # Mixed kinds: by timestamp; on a tie the order book message sorts before the trade.
        if self.timestamp != other.timestamp:
            return bool(self.timestamp < other.timestamp)  # type: ignore[operator]
        return self.has_update_id and not other.has_update_id
