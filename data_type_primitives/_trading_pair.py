"""Vendored trading-pair string helpers (private module).

Source of truth: hb-connector-utils.connector_utils.trading_pair
This is a frozen contract mirror for internal use by trade_fee.py only.
DO NOT re-export from public __init__.py. External consumers needing
trading-pair helpers must import from hb-connector-utils.
"""


def split_hb_trading_pair(trading_pair: str) -> tuple[str, str]:
    base, quote = trading_pair.split("-")
    return base, quote


def combine_to_hb_trading_pair(base: str, quote: str) -> str:
    trading_pair = f"{base}-{quote}"
    return trading_pair
