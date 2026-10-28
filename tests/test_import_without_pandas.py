"""Importing the package must not require pandas (only LimitOrder.to_pandas does)."""

import subprocess
import sys

import pytest

IMPORT_CODE = """
import sys
sys.modules['pandas'] = None
import data_type_primitives
from data_type_primitives import TradeType, LimitOrder
from data_type_primitives.common import TradeType as T2
assert TradeType is T2
"""

TO_PANDAS_CODE = """
import sys
sys.modules['pandas'] = None
from data_type_primitives import LimitOrder
try:
    LimitOrder.to_pandas([], 1.0)
except ImportError as e:
    assert 'frames' in str(e), str(e)
    sys.exit(0)
sys.exit(1)
"""


@pytest.mark.unit
def test_import_succeeds_without_pandas() -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", IMPORT_CODE], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.unit
def test_to_pandas_without_pandas_raises_actionable_error() -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", TO_PANDAS_CODE], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
