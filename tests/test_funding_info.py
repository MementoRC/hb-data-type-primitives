"""Tests for funding_info.py — FundingInfo and FundingInfoUpdate."""

from decimal import Decimal

import pytest

import data_type_primitives
from data_type_primitives.funding_info import (
    FundingInfo,
    FundingInfoUpdate,
)

# --- Importability ---


@pytest.mark.unit
def test_top_level_exports_available() -> None:
    """FundingInfo and FundingInfoUpdate are importable from data_type_primitives top-level."""
    assert data_type_primitives.FundingInfo is FundingInfo
    assert data_type_primitives.FundingInfoUpdate is FundingInfoUpdate


# --- FundingInfo construction ---


@pytest.mark.unit
def test_funding_info_construction() -> None:
    info = FundingInfo(
        trading_pair="BTC-USDT",
        index_price=Decimal("30000.0"),
        mark_price=Decimal("30010.0"),
        next_funding_utc_timestamp=1700000000,
        rate=Decimal("0.0001"),
    )
    assert info.trading_pair == "BTC-USDT"
    assert info.index_price == Decimal("30000.0")
    assert info.mark_price == Decimal("30010.0")
    assert info.next_funding_utc_timestamp == 1700000000
    assert info.rate == Decimal("0.0001")


# --- FundingInfoUpdate and update() round-trip ---


@pytest.mark.unit
def test_funding_info_update_partial() -> None:
    info = FundingInfo(
        trading_pair="ETH-USDT",
        index_price=Decimal("2000.0"),
        mark_price=Decimal("2001.0"),
        next_funding_utc_timestamp=1700000000,
        rate=Decimal("0.0002"),
    )
    update = FundingInfoUpdate(
        trading_pair="ETH-USDT",
        mark_price=Decimal("2005.0"),
        rate=Decimal("0.0003"),
    )
    info.update(update)
    assert info.mark_price == Decimal("2005.0")
    assert info.rate == Decimal("0.0003")
    # Unchanged fields retain original values
    assert info.index_price == Decimal("2000.0")
    assert info.next_funding_utc_timestamp == 1700000000


@pytest.mark.unit
def test_funding_info_update_none_fields_ignored() -> None:
    info = FundingInfo(
        trading_pair="BTC-USDT",
        index_price=Decimal("30000.0"),
        mark_price=Decimal("30010.0"),
        next_funding_utc_timestamp=1700000000,
        rate=Decimal("0.0001"),
    )
    update = FundingInfoUpdate(trading_pair="BTC-USDT")  # all optional fields None
    info.update(update)
    assert info.index_price == Decimal("30000.0")
    assert info.mark_price == Decimal("30010.0")
    assert info.rate == Decimal("0.0001")
