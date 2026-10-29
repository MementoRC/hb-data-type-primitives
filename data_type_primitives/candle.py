"""OHLCV candle data primitive.

Moved verbatim from ``strategy_framework.primitives.candle`` (hb-data-type-primitives#20)
so L2 packages can share it without depending on hb-strategy-framework.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class CandleData(BaseModel):
    """Immutable OHLCV candle record.

    All price/volume fields accept strings and coerce to Decimal.
    """

    model_config = ConfigDict(frozen=True)

    timestamp: int
    """Unix timestamp in milliseconds."""
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    @field_validator("open", "high", "low", "close", "volume", mode="before")
    @classmethod
    def _coerce_to_decimal(cls, v: object) -> Decimal:
        """Coerce strings and numbers to Decimal."""
        return Decimal(str(v))
