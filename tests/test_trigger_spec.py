"""Tests for the TriggerSpec value object (#50)."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

import data_type_primitives as dtp
from data_type_primitives.common import OrderType
from data_type_primitives.trigger_spec import (
    TrailSpec,
    TriggerKind,
    TriggerReference,
    TriggerSpec,
)

CONDITIONAL = [m for m in OrderType if m.is_conditional_type()]
TRAILING = [OrderType.TRAILING_STOP, OrderType.TRAILING_STOP_LIMIT]
NON_TRAILING_CONDITIONAL = [m for m in CONDITIONAL if m not in TRAILING]
NON_CONDITIONAL = [m for m in OrderType if not m.is_conditional_type()]


class TestEnums:
    def test_trigger_kind_values(self):
        assert {m.name: m.value for m in TriggerKind} == {
            "ABSOLUTE": "absolute",
            "RELATIVE_OFFSET": "relative_offset",
            "PERCENT": "percent",
        }

    def test_trigger_reference_values(self):
        assert {m.name: m.value for m in TriggerReference} == {
            "LAST": "last",
            "MARK": "mark",
            "INDEX": "index",
            "BID_ASK": "bid_ask",
        }


class TestTrailSpec:
    def test_valid_offset(self):
        t = TrailSpec(kind=TriggerKind.RELATIVE_OFFSET, distance="50")
        assert t.distance == Decimal("50")

    def test_valid_percent(self):
        t = TrailSpec(kind=TriggerKind.PERCENT, distance=0.02)
        assert t.distance == Decimal("0.02")

    def test_absolute_rejected(self):
        with pytest.raises(ValidationError):
            TrailSpec(kind=TriggerKind.ABSOLUTE, distance=1)

    @pytest.mark.parametrize("bad", [0, -1, "-0.5"])
    def test_non_positive_rejected(self, bad):
        with pytest.raises(ValidationError):
            TrailSpec(kind=TriggerKind.RELATIVE_OFFSET, distance=bad)

    @pytest.mark.parametrize("bad", [0, 1, 2, "1.5"])
    def test_percent_out_of_range_rejected(self, bad):
        with pytest.raises(ValidationError):
            TrailSpec(kind=TriggerKind.PERCENT, distance=bad)

    def test_offset_may_exceed_one(self):
        assert TrailSpec(kind=TriggerKind.RELATIVE_OFFSET, distance=5).distance == 5

    def test_frozen(self):
        t = TrailSpec(kind=TriggerKind.PERCENT, distance="0.01")
        with pytest.raises(ValidationError):
            t.distance = Decimal("0.02")


class TestTriggerSpec:
    def test_defaults(self):
        s = TriggerSpec(kind=TriggerKind.ABSOLUTE, value="100.5")
        assert s.value == Decimal("100.5")
        assert s.reference is TriggerReference.LAST
        assert s.trail is None

    def test_input_coercion(self):
        assert TriggerSpec(kind=TriggerKind.ABSOLUTE, value=100).value == Decimal("100")
        assert TriggerSpec(kind=TriggerKind.ABSOLUTE, value=0.5).value == Decimal("0.5")

    @pytest.mark.parametrize("bad", [0, -1])
    def test_non_positive_rejected(self, bad):
        with pytest.raises(ValidationError):
            TriggerSpec(kind=TriggerKind.ABSOLUTE, value=bad)

    @pytest.mark.parametrize("bad", [0, 1, "1.2"])
    def test_percent_out_of_range_rejected(self, bad):
        with pytest.raises(ValidationError):
            TriggerSpec(kind=TriggerKind.PERCENT, value=bad)

    def test_percent_valid(self):
        assert TriggerSpec(kind=TriggerKind.PERCENT, value="0.02").value == Decimal("0.02")

    def test_frozen(self):
        s = TriggerSpec(kind=TriggerKind.ABSOLUTE, value=1)
        with pytest.raises(ValidationError):
            s.value = Decimal(2)

    def test_with_trail_and_reference(self):
        trail = TrailSpec(kind=TriggerKind.PERCENT, distance="0.02")
        s = TriggerSpec(
            kind=TriggerKind.ABSOLUTE, value=100, reference=TriggerReference.MARK, trail=trail
        )
        assert s.trail is trail or s.trail == trail
        assert s.reference is TriggerReference.MARK


class TestValidateFor:
    @pytest.mark.parametrize("ot", NON_CONDITIONAL)
    def test_non_conditional_rejected(self, ot):
        with pytest.raises(ValueError, match="conditional"):
            TriggerSpec(kind=TriggerKind.ABSOLUTE, value=1).validate_for(ot)

    @pytest.mark.parametrize("ot", NON_TRAILING_CONDITIONAL)
    def test_plain_conditional_ok(self, ot):
        assert TriggerSpec(kind=TriggerKind.ABSOLUTE, value=1).validate_for(ot) is None

    @pytest.mark.parametrize("ot", NON_TRAILING_CONDITIONAL)
    def test_plain_conditional_with_trail_rejected(self, ot):
        trail = TrailSpec(kind=TriggerKind.PERCENT, distance="0.01")
        spec = TriggerSpec(kind=TriggerKind.ABSOLUTE, value=1, trail=trail)
        with pytest.raises(ValueError, match="trail"):
            spec.validate_for(ot)

    @pytest.mark.parametrize("ot", TRAILING)
    def test_trailing_requires_trail(self, ot):
        with pytest.raises(ValueError, match="trail"):
            TriggerSpec(kind=TriggerKind.ABSOLUTE, value=1).validate_for(ot)

    @pytest.mark.parametrize("ot", TRAILING)
    def test_trailing_with_trail_ok(self, ot):
        trail = TrailSpec(kind=TriggerKind.RELATIVE_OFFSET, distance=5)
        spec = TriggerSpec(kind=TriggerKind.ABSOLUTE, value=1, trail=trail)
        assert spec.validate_for(ot) is None


class TestExports:
    @pytest.mark.parametrize(
        "name", ["TriggerKind", "TriggerReference", "TrailSpec", "TriggerSpec"]
    )
    def test_exported(self, name):
        assert hasattr(dtp, name)
        assert name in dtp.__all__

    def test_version(self):
        assert dtp.__version__ == "0.13.0"
