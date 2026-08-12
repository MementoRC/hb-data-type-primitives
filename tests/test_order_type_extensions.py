"""Native coverage for the ``OrderType`` extension members and predicate helpers.

These units are defined here, in ``data_type_primitives/common.py``: conditional
members 7-12 plus ``is_limit_type`` / ``is_delayed_market_type`` /
``is_conditional_type``.

The parent hummingbot repo previously owned this coverage and reached the symbols
through the ``hummingbot.core.data_type.common`` re-export shim. Nothing here imports
from ``hummingbot``; the assertions run against the definition site directly. See
hb-data-type-primitives#11.
"""

import pytest

from data_type_primitives.common import OrderType

# Conditional members that trigger a MARKET execution once their condition is met.
DELAYED_MARKET_MEMBERS = ("STOP_LOSS", "TAKE_PROFIT", "TRAILING_STOP")

# Conditional members that rest a LIMIT order once their condition is met.
CONDITIONAL_LIMIT_MEMBERS = ("STOP_LOSS_LIMIT", "TAKE_PROFIT_LIMIT", "TRAILING_STOP_LIMIT")

# Every member added on top of the original hummingbot OrderType (values 7-12).
EXTENSION_MEMBERS = DELAYED_MARKET_MEMBERS + CONDITIONAL_LIMIT_MEMBERS

# Full expected truth set for is_limit_type(), original members included.
LIMIT_TYPE_MEMBERS = ("LIMIT", "LIMIT_MAKER", *CONDITIONAL_LIMIT_MEMBERS)

ALL_MEMBER_NAMES = tuple(OrderType.__members__)

# --- Extension member existence ---


@pytest.mark.unit
@pytest.mark.parametrize("name", EXTENSION_MEMBERS)
def test_extension_member_exists(name: str) -> None:
    """Each conditional extension member is present on the enum."""
    assert name in OrderType.__members__


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("STOP_LOSS", 7),
        ("TAKE_PROFIT", 8),
        ("TRAILING_STOP", 9),
        ("STOP_LOSS_LIMIT", 10),
        ("TAKE_PROFIT_LIMIT", 11),
        ("TRAILING_STOP_LIMIT", 12),
    ],
)
def test_extension_member_value(name: str, value: int) -> None:
    """Extension members keep their wire values 7-12."""
    assert OrderType[name].value == value


# --- Original members preserved ---


@pytest.mark.unit
def test_original_types_preserved() -> None:
    """Adding the conditional members did not renumber the original three."""
    assert OrderType.MARKET.value == 1
    assert OrderType.LIMIT.value == 2
    assert OrderType.LIMIT_MAKER.value == 3


# --- is_limit_type ---


@pytest.mark.unit
@pytest.mark.parametrize("name", ALL_MEMBER_NAMES)
def test_is_limit_type(name: str) -> None:
    """is_limit_type() is true for exactly the resting-limit members."""
    assert OrderType[name].is_limit_type() is (name in LIMIT_TYPE_MEMBERS)


# --- is_delayed_market_type ---


@pytest.mark.unit
@pytest.mark.parametrize("name", ALL_MEMBER_NAMES)
def test_is_delayed_market_type(name: str) -> None:
    """is_delayed_market_type() is true for exactly the market-triggering members."""
    assert OrderType[name].is_delayed_market_type() is (name in DELAYED_MARKET_MEMBERS)


# --- is_conditional_type ---


@pytest.mark.unit
@pytest.mark.parametrize("name", ALL_MEMBER_NAMES)
def test_is_conditional_type(name: str) -> None:
    """is_conditional_type() is true for every conditional member and nothing else."""
    assert OrderType[name].is_conditional_type() is (name in EXTENSION_MEMBERS)


# --- Cross-predicate invariants ---


@pytest.mark.unit
@pytest.mark.parametrize("name", EXTENSION_MEMBERS)
def test_conditional_members_split_between_limit_and_delayed_market(name: str) -> None:
    """Every conditional member is either a resting limit or a delayed market, never both."""
    member = OrderType[name]
    assert member.is_limit_type() is not member.is_delayed_market_type()
