"""Tests for the LinkedOrderSpec value object (#58)."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from data_type_primitives.common import OrderType, TradeType
from data_type_primitives.linked_order_spec import (
    CancelOutcome,
    LegRole,
    LegSpec,
    LinkedCancelOutcome,
    LinkedCancelStatus,
    LinkedOrderSpec,
    LinkKind,
)
from data_type_primitives.trigger_spec import (
    TrailSpec,
    TriggerKind,
    TriggerSpec,
)

OT = OrderType
TT = TradeType
BUY, SELL = TT.BUY, TT.SELL


def trig(trail: bool = False) -> TriggerSpec:
    t = TrailSpec(kind=TriggerKind.PERCENT, distance="0.02") if trail else None
    return TriggerSpec(kind=TriggerKind.ABSOLUTE, value=100, trail=t)


def leg(role=LegRole.ENTRY, ot=OT.MARKET, tt=BUY, amount=1, **kw) -> LegSpec:
    """Build a leg, auto-filling the price/trigger/offset the type requires."""
    if "price" not in kw and ot.is_limit_type() and ot != OT.TRAILING_STOP_LIMIT:
        kw["price"] = 10
    if "trigger" not in kw and ot.is_conditional_type():
        kw["trigger"] = trig(trail=ot in (OT.TRAILING_STOP, OT.TRAILING_STOP_LIMIT))
    if "limit_offset" not in kw and ot == OT.TRAILING_STOP_LIMIT:
        kw["limit_offset"] = -1
    return LegSpec(role=role, order_type=ot, trade_type=tt, amount=amount, **kw)


def entry(**kw) -> LegSpec:
    return leg(LegRole.ENTRY, kw.pop("ot", OT.MARKET), kw.pop("tt", BUY), **kw)


def tp(ot=OT.LIMIT, tt=SELL, amount=1, **kw) -> LegSpec:
    return leg(LegRole.TAKE_PROFIT, ot, tt, amount, **kw)


def sl(ot=OT.STOP_LOSS, tt=SELL, amount=1, **kw) -> LegSpec:
    return leg(LegRole.STOP_LOSS, ot, tt, amount, **kw)


def oco(ot=OT.LIMIT, tt=SELL, amount=1, **kw) -> LegSpec:
    return leg(LegRole.OCO_LEG, ot, tt, amount, **kw)


def bracket(*legs) -> LinkedOrderSpec:
    return LinkedOrderSpec(kind=LinkKind.BRACKET, legs=legs)


def oco_spec(*legs) -> LinkedOrderSpec:
    return LinkedOrderSpec(kind=LinkKind.OCO, legs=legs)


# --------------------------------------------------------------------- LegSpec


class TestLegSpec:
    @pytest.mark.parametrize(
        "ot", [OT.MARKET, OT.LIMIT, OT.LIMIT_MAKER, OT.STOP_LOSS, OT.TAKE_PROFIT]
    )
    def test_accepts_non_amm(self, ot):
        assert leg(ot=ot).order_type == ot

    @pytest.mark.parametrize("ot", [OT.AMM_SWAP, OT.AMM_ADD, OT.AMM_REMOVE])
    def test_rejects_amm(self, ot):
        with pytest.raises(ValidationError, match="not allowed"):
            LegSpec(role=LegRole.ENTRY, order_type=ot, trade_type=BUY, amount=1)

    @pytest.mark.parametrize("tt", [BUY, SELL])
    def test_accepts_buy_sell(self, tt):
        assert leg(tt=tt).trade_type == tt

    def test_rejects_range(self):
        with pytest.raises(ValidationError, match="BUY or SELL"):
            leg(tt=TT.RANGE)

    @pytest.mark.parametrize("amount", [1, "0.5", 0.25])
    def test_amount_accepted_and_coerced(self, amount):
        assert leg(amount=amount).amount == Decimal(str(amount))

    @pytest.mark.parametrize("amount", [0, -1, "-0.1"])
    def test_amount_must_be_positive(self, amount):
        with pytest.raises(ValidationError):
            leg(amount=amount)

    # trigger rules
    @pytest.mark.parametrize(
        "ot", [OT.STOP_LOSS, OT.TAKE_PROFIT, OT.STOP_LOSS_LIMIT, OT.TAKE_PROFIT_LIMIT]
    )
    def test_conditional_accepts_trigger(self, ot):
        assert leg(ot=ot).trigger is not None

    @pytest.mark.parametrize("ot", [OT.TRAILING_STOP, OT.TRAILING_STOP_LIMIT])
    def test_trailing_accepts_trigger_with_trail(self, ot):
        assert leg(ot=ot).trigger.trail is not None

    @pytest.mark.parametrize("ot", [m for m in OT if m.is_conditional_type()])
    def test_conditional_requires_trigger(self, ot):
        kw = {"price": 10} if ot.is_limit_type() and ot != OT.TRAILING_STOP_LIMIT else {}
        if ot == OT.TRAILING_STOP_LIMIT:
            kw["limit_offset"] = 0
        with pytest.raises(ValidationError, match="requires a trigger"):
            LegSpec(role=LegRole.ENTRY, order_type=ot, trade_type=BUY, amount=1, **kw)

    @pytest.mark.parametrize("ot", [OT.MARKET, OT.LIMIT, OT.LIMIT_MAKER])
    def test_non_conditional_rejects_trigger(self, ot):
        kw = {"price": 10} if ot.is_limit_type() else {}
        with pytest.raises(ValidationError, match="does not accept a trigger"):
            leg(ot=ot, trigger=trig(), **kw)

    def test_trigger_must_pass_validate_for_missing_trail(self):
        with pytest.raises(ValidationError, match="requires a trail"):
            leg(ot=OT.TRAILING_STOP, trigger=trig(trail=False))

    def test_trigger_must_pass_validate_for_unexpected_trail(self):
        with pytest.raises(ValidationError, match="does not accept a trail"):
            leg(ot=OT.STOP_LOSS, trigger=trig(trail=True))

    # price rules
    @pytest.mark.parametrize(
        "ot", [OT.LIMIT, OT.LIMIT_MAKER, OT.STOP_LOSS_LIMIT, OT.TAKE_PROFIT_LIMIT]
    )
    def test_limit_types_accept_price(self, ot):
        assert leg(ot=ot, price="12.5").price == Decimal("12.5")

    @pytest.mark.parametrize(
        "ot", [OT.LIMIT, OT.LIMIT_MAKER, OT.STOP_LOSS_LIMIT, OT.TAKE_PROFIT_LIMIT]
    )
    def test_limit_types_require_price(self, ot):
        kw = {"trigger": trig()} if ot.is_conditional_type() else {}
        with pytest.raises(ValidationError, match="requires a price"):
            LegSpec(role=LegRole.ENTRY, order_type=ot, trade_type=BUY, amount=1, **kw)

    @pytest.mark.parametrize("ot", [OT.LIMIT, OT.STOP_LOSS_LIMIT])
    @pytest.mark.parametrize("price", [0, -1])
    def test_price_must_be_positive(self, ot, price):
        with pytest.raises(ValidationError, match="price must be > 0"):
            leg(ot=ot, price=price)

    @pytest.mark.parametrize("ot", [OT.MARKET, OT.STOP_LOSS, OT.TAKE_PROFIT, OT.TRAILING_STOP])
    def test_non_limit_types_accept_no_price(self, ot):
        assert leg(ot=ot).price is None

    @pytest.mark.parametrize("ot", [OT.MARKET, OT.STOP_LOSS, OT.TAKE_PROFIT, OT.TRAILING_STOP])
    def test_non_limit_types_reject_price(self, ot):
        with pytest.raises(ValidationError, match="does not accept a price"):
            leg(ot=ot, price=10)

    # limit_offset rules
    @pytest.mark.parametrize("offset", [5, 0, "0", -5, "-0.25"])
    def test_trailing_stop_limit_accepts_signed_offset(self, offset):
        assert leg(ot=OT.TRAILING_STOP_LIMIT, limit_offset=offset).limit_offset == Decimal(
            str(offset)
        )

    def test_trailing_stop_limit_requires_offset(self):
        with pytest.raises(ValidationError, match="requires limit_offset"):
            LegSpec(
                role=LegRole.ENTRY,
                order_type=OT.TRAILING_STOP_LIMIT,
                trade_type=BUY,
                amount=1,
                trigger=trig(trail=True),
            )

    def test_trailing_stop_limit_rejects_price(self):
        with pytest.raises(ValidationError, match="forbids price"):
            leg(ot=OT.TRAILING_STOP_LIMIT, price=10)

    @pytest.mark.parametrize(
        "ot",
        [
            OT.MARKET,
            OT.LIMIT,
            OT.STOP_LOSS,
            OT.STOP_LOSS_LIMIT,
            OT.TAKE_PROFIT_LIMIT,
            OT.TRAILING_STOP,
        ],
    )
    def test_offset_forbidden_elsewhere(self, ot):
        with pytest.raises(ValidationError, match="only valid for TRAILING_STOP_LIMIT"):
            leg(ot=ot, limit_offset=1)

    def test_leg_is_frozen(self):
        with pytest.raises(ValidationError):
            leg().amount = Decimal(2)


# ------------------------------------------------------------------- BRACKET


class TestBracket:
    def test_entry_plus_both_exits(self):
        assert len(bracket(entry(), tp(), sl()).legs) == 3

    def test_entry_plus_tp_only(self):
        assert len(bracket(entry(), tp()).legs) == 2

    def test_entry_plus_sl_only(self):
        assert len(bracket(entry(), sl()).legs) == 2

    def test_rejects_no_entry(self):
        with pytest.raises(ValidationError, match="exactly one ENTRY"):
            bracket(tp(), sl())

    def test_rejects_two_entries(self):
        with pytest.raises(ValidationError, match="exactly one ENTRY"):
            bracket(entry(), entry(), tp())

    def test_rejects_no_exits(self):
        with pytest.raises(ValidationError, match="at least one exit"):
            bracket(entry())

    def test_rejects_empty(self):
        with pytest.raises(ValidationError, match="exactly one ENTRY"):
            bracket()

    def test_rejects_two_take_profits(self):
        with pytest.raises(ValidationError, match="at most one TAKE_PROFIT"):
            bracket(entry(), tp(), tp())

    def test_rejects_two_stop_losses(self):
        with pytest.raises(ValidationError, match="at most one STOP_LOSS"):
            bracket(entry(), sl(), sl())

    def test_rejects_oco_leg(self):
        with pytest.raises(ValidationError, match="OCO_LEG"):
            bracket(entry(), tp(), oco())

    @pytest.mark.parametrize(("entry_tt", "exit_tt"), [(BUY, SELL), (SELL, BUY)])
    def test_exits_opposite_side_accepted(self, entry_tt, exit_tt):
        assert bracket(entry(tt=entry_tt), tp(tt=exit_tt), sl(tt=exit_tt))

    @pytest.mark.parametrize("exit_fn", [tp, sl])
    def test_exits_same_side_rejected(self, exit_fn):
        with pytest.raises(ValidationError, match="opposite trade_type"):
            bracket(entry(tt=BUY), exit_fn(tt=BUY))

    @pytest.mark.parametrize("exit_amount", [1, "0.5"])
    @pytest.mark.parametrize("exit_fn", [tp, sl])
    def test_exit_amount_le_entry_accepted(self, exit_fn, exit_amount):
        assert bracket(entry(amount=1), exit_fn(amount=exit_amount))

    @pytest.mark.parametrize("exit_fn", [tp, sl])
    def test_exit_amount_gt_entry_rejected(self, exit_fn):
        with pytest.raises(ValidationError, match="must not exceed ENTRY"):
            bracket(entry(amount=1), exit_fn(amount="1.01"))

    @pytest.mark.parametrize("ot", [OT.LIMIT, OT.LIMIT_MAKER, OT.TAKE_PROFIT, OT.TAKE_PROFIT_LIMIT])
    def test_tp_types_accepted(self, ot):
        assert bracket(entry(), tp(ot=ot))

    @pytest.mark.parametrize(
        "ot",
        [OT.MARKET, OT.STOP_LOSS, OT.STOP_LOSS_LIMIT, OT.TRAILING_STOP, OT.TRAILING_STOP_LIMIT],
    )
    def test_tp_types_rejected(self, ot):
        with pytest.raises(ValidationError, match="TAKE_PROFIT does not accept"):
            bracket(entry(), tp(ot=ot))

    @pytest.mark.parametrize(
        "ot", [OT.STOP_LOSS, OT.STOP_LOSS_LIMIT, OT.TRAILING_STOP, OT.TRAILING_STOP_LIMIT]
    )
    def test_sl_types_accepted(self, ot):
        assert bracket(entry(), sl(ot=ot))

    @pytest.mark.parametrize(
        "ot", [OT.MARKET, OT.LIMIT, OT.LIMIT_MAKER, OT.TAKE_PROFIT, OT.TAKE_PROFIT_LIMIT]
    )
    def test_sl_types_rejected(self, ot):
        with pytest.raises(ValidationError, match="STOP_LOSS does not accept"):
            bracket(entry(), sl(ot=ot))

    @pytest.mark.parametrize(
        "ot", [OT.MARKET, OT.LIMIT, OT.LIMIT_MAKER, OT.STOP_LOSS, OT.TRAILING_STOP_LIMIT]
    )
    def test_entry_accepts_any_non_amm(self, ot):
        assert bracket(entry(ot=ot), tp())

    def test_entry_rejects_amm(self):
        with pytest.raises(ValidationError, match="not allowed"):
            entry(ot=OT.AMM_SWAP)


# ----------------------------------------------------------------------- OCO


class TestOco:
    def test_two_legs(self):
        assert len(oco_spec(oco(), oco(ot=OT.STOP_LOSS)).legs) == 2

    def test_three_legs_differing_amounts(self):
        assert len(oco_spec(oco(amount=1), oco(amount=2), oco(amount="0.5")).legs) == 3

    @pytest.mark.parametrize("tt", [BUY, SELL])
    def test_same_side_accepted(self, tt):
        assert oco_spec(oco(tt=tt), oco(ot=OT.STOP_LOSS, tt=tt))

    def test_mixed_side_rejected(self):
        with pytest.raises(ValidationError, match="same trade_type"):
            oco_spec(oco(tt=BUY), oco(tt=SELL))

    def test_single_leg_rejected(self):
        with pytest.raises(ValidationError, match="at least two"):
            oco_spec(oco())

    def test_empty_rejected(self):
        with pytest.raises(ValidationError, match="at least two"):
            oco_spec()

    @pytest.mark.parametrize("role", [LegRole.ENTRY, LegRole.TAKE_PROFIT, LegRole.STOP_LOSS])
    def test_non_oco_roles_rejected(self, role):
        bad = leg(role, OT.LIMIT, SELL)
        with pytest.raises(ValidationError, match="all legs to be OCO_LEG"):
            oco_spec(oco(), bad)


# ------------------------------------------------------------------- helpers


class TestHelpers:
    def test_leg_order_independent_validation(self):
        e, t, s = entry(), tp(), sl()
        assert bracket(s, t, e).kind == bracket(e, t, s).kind
        assert bracket(s, e, t)

    def test_ordered_legs_deterministic(self):
        e, t, s = entry(), tp(), sl()
        for perm in [(e, t, s), (s, t, e), (t, e, s), (s, e, t)]:
            assert bracket(*perm).ordered_legs() == (e, t, s)

    def test_ordered_legs_oco_preserves_order(self):
        a, b, c = oco(amount=1), oco(amount=2), oco(amount=3)
        assert oco_spec(b, a, c).ordered_legs() == (b, a, c)

    def test_entry_and_exits_bracket(self):
        e, t, s = entry(), tp(), sl()
        spec = bracket(s, e, t)
        assert spec.entry == e
        assert spec.exits == (s, t)

    def test_entry_and_exits_oco(self):
        a, b = oco(), oco(amount=2)
        spec = oco_spec(a, b)
        assert spec.entry is None
        assert spec.exits == (a, b)


# ----------------------------------------------------------- frozen / serialise


class TestFrozenAndRoundTrip:
    def test_spec_frozen(self):
        spec = bracket(entry(), tp())
        with pytest.raises(ValidationError):
            spec.kind = LinkKind.OCO
        with pytest.raises(ValidationError):
            spec.legs = ()

    def _full(self) -> LinkedOrderSpec:
        return bracket(
            entry(ot=OT.LIMIT, price="99.5", amount="2"),
            tp(ot=OT.TAKE_PROFIT_LIMIT, price="120", amount="1.5"),
            sl(ot=OT.TRAILING_STOP_LIMIT, limit_offset="-0.5", amount="2"),
        )

    def test_python_round_trip(self):
        spec = self._full()
        assert LinkedOrderSpec.model_validate(spec.model_dump()) == spec

    def test_json_round_trip(self):
        spec = self._full()
        assert LinkedOrderSpec.model_validate_json(spec.model_dump_json()) == spec

    def test_json_mode_dump_round_trip(self):
        spec = self._full()
        assert LinkedOrderSpec.model_validate(spec.model_dump(mode="json")) == spec

    def test_oco_round_trip(self):
        spec = oco_spec(oco(), oco(ot=OT.STOP_LOSS))
        assert LinkedOrderSpec.model_validate_json(spec.model_dump_json()) == spec


def lco(**kw) -> LinkedCancelOutcome:
    base = {
        "group_id": "g1",
        "all_legs_terminal": True,
        "residual_filled": "0",
        "leg_outcomes": (CancelOutcome.CANCELED, CancelOutcome.ALREADY_FILLED),
    }
    base.update(kw)
    return LinkedCancelOutcome(**base)


class TestCancelOutcome:
    def test_values(self):
        assert {m.name: m.value for m in CancelOutcome} == {
            "CANCELED": "canceled",
            "ALREADY_FILLED": "already_filled",
            "NOT_FOUND": "not_found",
            "UNKNOWN": "unknown",
        }

    def test_is_str(self):
        assert all(isinstance(m, str) for m in CancelOutcome)
        assert CancelOutcome.CANCELED == "canceled"


class TestLinkedCancelOutcome:
    def test_valid(self):
        o = lco(residual_filled="1.5")
        assert o.group_id == "g1"
        assert o.all_legs_terminal is True
        assert o.residual_filled == Decimal("1.5")
        assert o.leg_outcomes == (CancelOutcome.CANCELED, CancelOutcome.ALREADY_FILLED)

    @pytest.mark.parametrize("residual", [-1, "-0.01"])
    def test_rejects_negative_residual(self, residual):
        with pytest.raises(ValidationError, match="residual_filled"):
            lco(residual_filled=residual)

    def test_rejects_empty_leg_outcomes(self):
        with pytest.raises(ValidationError, match="leg_outcomes"):
            lco(leg_outcomes=())

    def test_rejects_int_group_id(self):
        with pytest.raises(ValidationError, match="group_id"):
            lco(group_id=1)

    def test_none_entries_allowed(self):
        o = lco(leg_outcomes=(CancelOutcome.CANCELED, None, None))
        assert o.leg_outcomes[1:] == (None, None)

    def test_frozen(self):
        o = lco()
        with pytest.raises(ValidationError):
            o.group_id = "g2"
        with pytest.raises(ValidationError):
            o.residual_filled = Decimal(1)

    def test_python_round_trip(self):
        o = lco(residual_filled="2.5", leg_outcomes=(CancelOutcome.UNKNOWN, None))
        assert LinkedCancelOutcome.model_validate(o.model_dump()) == o

    def test_json_round_trip(self):
        o = lco(residual_filled="2.5", leg_outcomes=(CancelOutcome.NOT_FOUND, None))
        assert LinkedCancelOutcome.model_validate_json(o.model_dump_json()) == o
        assert LinkedCancelOutcome.model_validate(o.model_dump(mode="json")) == o


class TestLinkedCancelStatus:
    def test_values(self):
        assert {m.name: m.value for m in LinkedCancelStatus} == {
            "PENDING": "pending",
            "CANCELED": "canceled",
            "FILLED": "filled",
            "FAILED": "failed",
            "UNKNOWN": "unknown",
        }

    def test_is_str(self):
        assert all(isinstance(m, str) for m in LinkedCancelStatus)
        assert LinkedCancelStatus.PENDING == "pending"

    def test_default_status_is_none(self):
        assert lco().status is None

    @pytest.mark.parametrize(
        "status",
        [LinkedCancelStatus.CANCELED, LinkedCancelStatus.FILLED, LinkedCancelStatus.FAILED],
    )
    def test_terminal_status_with_terminal_legs(self, status):
        assert lco(status=status, all_legs_terminal=True).status == status

    @pytest.mark.parametrize("status", [LinkedCancelStatus.PENDING, LinkedCancelStatus.UNKNOWN])
    def test_non_terminal_allowed_statuses(self, status):
        assert lco(status=status, all_legs_terminal=False).status == status

    def test_unknown_with_terminal_legs_allowed(self):
        assert lco(status=LinkedCancelStatus.UNKNOWN).status == LinkedCancelStatus.UNKNOWN

    def test_none_status_with_non_terminal_legs_allowed(self):
        assert lco(all_legs_terminal=False).status is None

    def test_rejects_pending_with_terminal_legs(self):
        with pytest.raises(ValidationError, match="PENDING"):
            lco(status=LinkedCancelStatus.PENDING, all_legs_terminal=True)

    @pytest.mark.parametrize(
        "status",
        [LinkedCancelStatus.CANCELED, LinkedCancelStatus.FILLED, LinkedCancelStatus.FAILED],
    )
    def test_rejects_terminal_status_with_non_terminal_legs(self, status):
        with pytest.raises(ValidationError, match="all_legs_terminal"):
            lco(status=status, all_legs_terminal=False)

    def test_python_round_trip_with_status(self):
        o = lco(status=LinkedCancelStatus.FILLED, residual_filled="1")
        assert LinkedCancelOutcome.model_validate(o.model_dump()) == o

    def test_json_round_trip_with_status(self):
        o = lco(status=LinkedCancelStatus.CANCELED, residual_filled="1")
        assert LinkedCancelOutcome.model_validate_json(o.model_dump_json()) == o
        assert LinkedCancelOutcome.model_validate(o.model_dump(mode="json")) == o

    def test_v0_12_0_payload_still_valid(self):
        o = LinkedCancelOutcome.model_validate(
            {
                "group_id": "g1",
                "all_legs_terminal": False,
                "residual_filled": "0",
                "leg_outcomes": ("canceled", None),
            }
        )
        assert o.status is None

    def test_exported_from_root(self):
        import data_type_primitives as dtp

        assert "LinkedCancelStatus" in dtp.__all__
        assert dtp.LinkedCancelStatus is LinkedCancelStatus


def test_cancel_types_exported_from_root():
    import data_type_primitives as dtp

    for name in ("CancelOutcome", "LinkedCancelOutcome"):
        assert name in dtp.__all__
        assert hasattr(dtp, name)


def test_exports():
    import data_type_primitives as dtp

    for name in ("LinkKind", "LegRole", "LegSpec", "LinkedOrderSpec"):
        assert name in dtp.__all__
        assert hasattr(dtp, name)
