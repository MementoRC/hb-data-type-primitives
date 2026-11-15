"""TriggerSpec — value object describing when a conditional order triggers.

Pure data: no price-tracking logic lives here. Consumers (connectors, executors)
interpret the spec.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .common import OrderType


class TriggerKind(StrEnum):
    """How ``TriggerSpec.value`` (or ``TrailSpec.distance``) is interpreted."""

    ABSOLUTE = "absolute"
    RELATIVE_OFFSET = "relative_offset"
    PERCENT = "percent"


class TriggerReference(StrEnum):
    """Price feed the trigger is evaluated against."""

    LAST = "last"
    MARK = "mark"
    INDEX = "index"
    BID_ASK = "bid_ask"


def _to_decimal(v: object) -> Decimal:
    return Decimal(str(v))


def _check_amount(kind: TriggerKind, amount: Decimal, label: str) -> None:
    if amount <= 0:
        msg = f"{label} must be > 0"
        raise ValueError(msg)
    if kind == TriggerKind.PERCENT and amount >= 1:
        msg = f"{label} must be a fraction in (0, 1) when kind is PERCENT (0.02 = 2%)"
        raise ValueError(msg)


class TrailSpec(BaseModel):
    """Immutable trailing distance for a trailing conditional order.

    The trail is a ratchet: it follows price only in the favourable direction and
    fires on a pullback of ``distance`` from the best price seen since placement.

    - sell: ``PERCENT`` fires at ``peak * (1 - p)``; ``RELATIVE_OFFSET`` at ``peak - d``.
    - buy: ``PERCENT`` fires at ``trough * (1 + p)``; ``RELATIVE_OFFSET`` at ``trough + d``.

    ``distance`` is a fraction for ``PERCENT`` (0.02 = 2%). There is no activation
    threshold in v0.9.0. ``ABSOLUTE`` is not a valid trail kind.
    """

    model_config = ConfigDict(frozen=True)

    kind: TriggerKind
    distance: Decimal

    @field_validator("distance", mode="before")
    @classmethod
    def _coerce_distance(cls, v: object) -> Decimal:
        return _to_decimal(v)

    @model_validator(mode="after")
    def _validate(self) -> TrailSpec:
        if self.kind == TriggerKind.ABSOLUTE:
            msg = "TrailSpec kind must be RELATIVE_OFFSET or PERCENT"
            raise ValueError(msg)
        _check_amount(self.kind, self.distance, "distance")
        return self


class TriggerSpec(BaseModel):
    """Immutable trigger description for a conditional order.

    ``value`` is a price for ``ABSOLUTE``, a price offset for ``RELATIVE_OFFSET``,
    or a fraction for ``PERCENT`` (0.02 = 2%). ``trail`` is only meaningful for
    trailing order types; see ``TrailSpec`` for the ratchet semantics (follows price
    only in the favourable direction, fires on a pullback of ``distance`` from the
    best price since placement; no activation threshold in v0.9.0).
    """

    model_config = ConfigDict(frozen=True)

    kind: TriggerKind
    value: Decimal
    reference: TriggerReference = TriggerReference.LAST
    trail: TrailSpec | None = None

    @field_validator("value", mode="before")
    @classmethod
    def _coerce_value(cls, v: object) -> Decimal:
        return _to_decimal(v)

    @model_validator(mode="after")
    def _validate(self) -> TriggerSpec:
        _check_amount(self.kind, self.value, "value")
        return self

    def validate_for(self, order_type: OrderType) -> None:
        """Raise ``ValueError`` if this spec is inconsistent with ``order_type``.

        The order type must be conditional; trailing types require ``trail`` and
        all other conditional types forbid it.
        """
        if not order_type.is_conditional_type():
            msg = f"{order_type.name} is not a conditional order type"
            raise ValueError(msg)
        trailing = order_type in (OrderType.TRAILING_STOP, OrderType.TRAILING_STOP_LIMIT)
        if trailing and self.trail is None:
            msg = f"{order_type.name} requires a trail"
            raise ValueError(msg)
        if not trailing and self.trail is not None:
            msg = f"{order_type.name} does not accept a trail"
            raise ValueError(msg)
