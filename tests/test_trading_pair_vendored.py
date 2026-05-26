"""Tests for vendored trading-pair helpers (private module _trading_pair)."""

import pytest

from data_type_primitives._trading_pair import combine_to_hb_trading_pair, split_hb_trading_pair


@pytest.mark.unit
def test_split_simple_pair() -> None:
    """split_hb_trading_pair returns (base, quote) for a standard pair."""
    base, quote = split_hb_trading_pair("BTC-USDT")
    assert base == "BTC"
    assert quote == "USDT"


@pytest.mark.unit
def test_combine_simple_pair() -> None:
    """combine_to_hb_trading_pair joins base and quote with a dash."""
    result = combine_to_hb_trading_pair("ETH", "BTC")
    assert result == "ETH-BTC"


@pytest.mark.unit
def test_split_combine_round_trip() -> None:
    """split then combine returns the original trading pair string."""
    original = "SOL-USDC"
    base, quote = split_hb_trading_pair(original)
    reconstructed = combine_to_hb_trading_pair(base, quote)
    assert reconstructed == original


@pytest.mark.unit
def test_split_no_separator_raises() -> None:
    """split_hb_trading_pair raises ValueError when no dash is present."""
    with pytest.raises(ValueError):
        split_hb_trading_pair("BTCUSDT")
