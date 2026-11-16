"""LinkedOrderSpec — venue-neutral value object for linked orders (bracket, OCO).

Pure data: this module holds no placement or emulation logic. Adapters and
managers interpret the spec.

The spec carries no instrument and no client ids. The instrument is passed at
placement time; venue ids come from strategy-framework's ``LinkedOrderIdCodec``.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import OrderType, TradeType
from .trigger_spec import TriggerSpec  # noqa: TC001  (pydantic needs it at runtime)


class LinkKind(StrEnum):
    """Kind of linked-order group."""

    BRACKET = "bracket"
    OCO = "oco"


class LegRole(StrEnum):
    """Role a leg plays within its group."""

    ENTRY = "entry"
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    OCO_LEG = "oco_leg"


_TAKE_PROFIT_TYPES = frozenset(
    {
        OrderType.LIMIT,
        OrderType.LIMIT_MAKER,
        OrderType.TAKE_PROFIT,
        OrderType.TAKE_PROFIT_LIMIT,
    }
)
_STOP_LOSS_TYPES = frozenset(
    {
        OrderType.STOP_LOSS,
        OrderType.STOP_LOSS_LIMIT,
        OrderType.TRAILING_STOP,
        OrderType.TRAILING_STOP_LIMIT,
    }
)
_AMM_TYPES = frozenset({OrderType.AMM_SWAP, OrderType.AMM_ADD, OrderType.AMM_REMOVE})
_EXIT_ORDER = (LegRole.TAKE_PROFIT, LegRole.STOP_LOSS)


def _to_decimal(v: object) -> Decimal:
    return Decimal(str(v))


class LegSpec(BaseModel):
    """Immutable description of one leg of a linked order.

    ``limit_offset`` applies only to ``TRAILING_STOP_LIMIT``: the limit price is
    the trigger's fire price plus ``limit_offset`` (literal arithmetic, no flip
    for the side, in price units). It is signed and may be zero or negative.
    Converting to venue units is the adapter's job. All other limit types use an
    absolute ``price`` > 0.
    """

    model_config = ConfigDict(frozen=True)

    role: LegRole
    order_type: OrderType
    trade_type: TradeType
    amount: Decimal = Field(gt=0)
    price: Decimal | None = None
    trigger: TriggerSpec | None = None
    limit_offset: Decimal | None = None

    @field_validator("amount", "price", "limit_offset", mode="before")
    @classmethod
    def _coerce_decimal(cls, v: object) -> Decimal | None:
        return None if v is None else _to_decimal(v)

    @model_validator(mode="after")
    def _validate(self) -> LegSpec:
        ot = self.order_type
        if ot in _AMM_TYPES:
            msg = f"{ot.name} is not allowed in a linked order leg"
            raise ValueError(msg)
        if self.trade_type not in (TradeType.BUY, TradeType.SELL):
            msg = "trade_type must be BUY or SELL"
            raise ValueError(msg)
        self._validate_trigger()
        self._validate_price()
        return self

    def _validate_trigger(self) -> None:
        ot = self.order_type
        if ot.is_conditional_type():
            if self.trigger is None:
                msg = f"{ot.name} requires a trigger"
                raise ValueError(msg)
            self.trigger.validate_for(ot)
        elif self.trigger is not None:
            msg = f"{ot.name} does not accept a trigger"
            raise ValueError(msg)

    def _validate_price(self) -> None:
        ot = self.order_type
        if ot == OrderType.TRAILING_STOP_LIMIT:
            if self.limit_offset is None:
                msg = "TRAILING_STOP_LIMIT requires limit_offset"
                raise ValueError(msg)
            if self.price is not None:
                msg = "TRAILING_STOP_LIMIT forbids price; use limit_offset"
                raise ValueError(msg)
            return
        if self.limit_offset is not None:
            msg = "limit_offset is only valid for TRAILING_STOP_LIMIT"
            raise ValueError(msg)
        if ot.is_limit_type():
            if self.price is None:
                msg = f"{ot.name} requires a price"
                raise ValueError(msg)
            if self.price <= 0:
                msg = "price must be > 0"
                raise ValueError(msg)
        elif self.price is not None:
            msg = f"{ot.name} does not accept a price"
            raise ValueError(msg)


class LinkedOrderSpec(BaseModel):
    """Immutable group of linked legs (bracket or OCO).

    This is a value object only; it contains no placement or emulation logic.
    It has no instrument and no client ids: the instrument is passed at
    placement and venue ids come from strategy-framework's ``LinkedOrderIdCodec``.

    BRACKET: exactly one ENTRY plus one or two exits (at most one TAKE_PROFIT and
    one STOP_LOSS). Exits take the opposite side of the entry and an amount no
    larger than the entry's.

    OCO: two or more OCO_LEG legs, all on the same side (strict for now; may be
    relaxed later without breaking callers). Amounts may differ.

    Leg order in ``legs`` is irrelevant; validation goes by role.
    """

    model_config = ConfigDict(frozen=True)

    kind: LinkKind
    legs: tuple[LegSpec, ...]

    @model_validator(mode="after")
    def _validate(self) -> LinkedOrderSpec:
        if self.kind == LinkKind.BRACKET:
            self._validate_bracket()
        else:
            self._validate_oco()
        return self

    def _validate_bracket(self) -> None:
        roles = [leg.role for leg in self.legs]
        if LegRole.OCO_LEG in roles:
            msg = "BRACKET does not allow OCO_LEG legs"
            raise ValueError(msg)
        if roles.count(LegRole.ENTRY) != 1:
            msg = "BRACKET requires exactly one ENTRY leg"
            raise ValueError(msg)
        for role in _EXIT_ORDER:
            if roles.count(role) > 1:
                msg = f"BRACKET allows at most one {role.name} leg"
                raise ValueError(msg)
        if len(self.legs) < 2:
            msg = "BRACKET requires at least one exit leg"
            raise ValueError(msg)
        entry = next(leg for leg in self.legs if leg.role == LegRole.ENTRY)
        for leg in self.legs:
            if leg.role == LegRole.ENTRY:
                continue
            self._validate_exit(entry, leg)

    @staticmethod
    def _validate_exit(entry: LegSpec, leg: LegSpec) -> None:
        if leg.trade_type == entry.trade_type:
            msg = f"{leg.role.name} must have the opposite trade_type of ENTRY"
            raise ValueError(msg)
        if leg.amount > entry.amount:
            msg = f"{leg.role.name} amount must not exceed ENTRY amount"
            raise ValueError(msg)
        allowed = _TAKE_PROFIT_TYPES if leg.role == LegRole.TAKE_PROFIT else _STOP_LOSS_TYPES
        if leg.order_type not in allowed:
            msg = f"{leg.role.name} does not accept order type {leg.order_type.name}"
            raise ValueError(msg)

    def _validate_oco(self) -> None:
        if len(self.legs) < 2:
            msg = "OCO requires at least two legs"
            raise ValueError(msg)
        if any(leg.role != LegRole.OCO_LEG for leg in self.legs):
            msg = "OCO requires all legs to be OCO_LEG"
            raise ValueError(msg)
        if len({leg.trade_type for leg in self.legs}) != 1:
            msg = "OCO requires all legs to have the same trade_type"
            raise ValueError(msg)

    @property
    def entry(self) -> LegSpec | None:
        """The ENTRY leg for a BRACKET, ``None`` for an OCO."""
        return next((leg for leg in self.legs if leg.role == LegRole.ENTRY), None)

    @property
    def exits(self) -> tuple[LegSpec, ...]:
        """All non-ENTRY legs, in their original order."""
        return tuple(leg for leg in self.legs if leg.role != LegRole.ENTRY)

    def ordered_legs(self) -> tuple[LegSpec, ...]:
        """ENTRY, TAKE_PROFIT, STOP_LOSS, then OCO legs in original order."""
        rank = {
            LegRole.ENTRY: 0,
            LegRole.TAKE_PROFIT: 1,
            LegRole.STOP_LOSS: 2,
            LegRole.OCO_LEG: 3,
        }
        return tuple(sorted(self.legs, key=lambda leg: rank[leg.role]))


class CancelOutcome(StrEnum):
    """Per-leg result of cancelling one leg of a linked-order group.

    Unlike ``CancellationResult`` (which pairs an order id with a success flag),
    this is a bare outcome with no order id, and it distinguishes an order that
    was already filled, one the venue does not know, and one whose state could
    not be determined.
    """

    CANCELED = "canceled"
    ALREADY_FILLED = "already_filled"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


class LinkedCancelStatus(StrEnum):
    """Venue-neutral terminal status of cancelling a whole linked-order group.

    Unlike ``CancelOutcome`` (per leg), this describes the group as a whole
    (per group). It has no emulation lifecycle states; those belong to the
    emulation layer, not to this venue-neutral value.
    """

    # The cancel was accepted, but not every leg is terminal yet.
    PENDING = "pending"
    # Every leg is terminal and the cancel ended the group. A partial fill before
    # that is still CANCELED; it is reported in ``residual_filled``.
    CANCELED = "canceled"
    # A fill decided the group (an OCO winner, or a bracket exit filled) before
    # the cancel took effect; the winning leg may still be working, so check
    # ``all_legs_terminal``.
    FILLED = "filled"
    # The group ended through a rejection or a placement failure.
    FAILED = "failed"
    # The venue cannot say how the group ended.
    UNKNOWN = "unknown"


class LinkedCancelOutcome(BaseModel):
    """Immutable result of cancelling a whole linked-order group.

    ``leg_outcomes`` must be non-empty. Its length equals
    ``len(spec.ordered_legs())``. ``ordered_legs()`` lists only the legs present
    in the spec, with no placeholders for absent optional exits (a BRACKET with
    entry and SL gives 2 positions). A ``None`` entry means the leg is in the spec
    but was never submitted or acknowledged. The length is NOT validated here,
    because the outcome does not carry the spec; it is a producer contract only.

    ``residual_filled`` is the signed net open exposure, relative to
    ``ordered_legs()[0]``. One rule covers both kinds: a leg on the same
    ``trade_type`` as ``ordered_legs()[0]`` ADDS its filled amount, and a leg on
    the opposite side SUBTRACTS it.

    - BRACKET: ``ordered_legs()[0]`` is the ENTRY, so the result is entry filled
      minus the exit legs' filled.
    - OCO: a same-side OCO gives the sum of fills; a breakout OCO (buy stop above,
      sell stop below) under a double fill nets to 0.
    - Units: base quantity, the same units as the legs' filled, measured when the
      outcome is built.
    - Sign: positive means exposure on ``ordered_legs()[0]``'s side. Negative
      means the exposure reversed, e.g. a BRACKET double fill where TP and SL
      both fill.

    Examples: BRACKET entry 1, TP 1 gives 0; entry 1, TP 0.4, then cancel gives
    0.6; entry 0.5, cancel before exits gives 0.5; entry 1, TP 1 and SL 1 (double
    fill) gives -1; OCO with no fill gives 0; same-side OCO winner filled 1 gives
    1; breakout OCO where both legs fill 1 gives 0.

    ``status`` is the group-level status. ``None`` means the producer did not
    report a status; this keeps v0.12.0 payloads valid. ``PENDING`` requires
    ``all_legs_terminal`` to be False. ``all_legs_terminal`` False allows only
    ``None``, ``PENDING``, ``FILLED`` or ``UNKNOWN``; ``CANCELED`` and ``FAILED``
    require it True.
    """

    model_config = ConfigDict(frozen=True)

    group_id: str
    all_legs_terminal: bool
    residual_filled: Decimal = Field(
        description=(
            "Signed net open exposure in base quantity, relative to "
            "ordered_legs()[0]: a leg on the same trade_type adds its filled, a leg "
            "on the opposite side subtracts it. BRACKET: entry filled minus exits "
            "filled. OCO: same-side legs sum; a breakout OCO double fill nets to 0. "
            "Negative means the exposure reversed."
        )
    )
    leg_outcomes: tuple[CancelOutcome | None, ...]
    status: LinkedCancelStatus | None = None

    @field_validator("residual_filled", mode="before")
    @classmethod
    def _coerce_decimal(cls, v: object) -> Decimal:
        return _to_decimal(v)

    @field_validator("leg_outcomes")
    @classmethod
    def _non_empty(cls, v: tuple[CancelOutcome | None, ...]) -> tuple[CancelOutcome | None, ...]:
        if not v:
            msg = "leg_outcomes must not be empty"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _validate_status(self) -> LinkedCancelOutcome:
        status = self.status
        if status == LinkedCancelStatus.PENDING and self.all_legs_terminal:
            msg = "status PENDING requires all_legs_terminal to be False"
            raise ValueError(msg)
        if not self.all_legs_terminal and status not in (
            None,
            LinkedCancelStatus.PENDING,
            LinkedCancelStatus.FILLED,
            LinkedCancelStatus.UNKNOWN,
        ):
            msg = (
                f"all_legs_terminal is False: status must be None, PENDING, FILLED or "
                f"UNKNOWN, got {status.name}"
            )
            raise ValueError(msg)
        return self
