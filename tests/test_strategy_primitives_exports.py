"""Tests for the strategy primitives absorbed from hb-strategy-framework (#43)."""

import pytest

import data_type_primitives as dtp
from data_type_primitives import common, executor_actions, strategy_enums

NEW_NAMES = [
    "CreateExecutorAction",
    "StopExecutorAction",
    "UpdateExecutorAction",
    "StoreExecutorAction",
    "CloseType",
    "RunnableStatus",
    "DataRequirement",
    "ExecutorNotification",
    "PercentData",
    "TradingRules",
    "TrailingStop",
    "TripleBarrierConfig",
    "StrategyTradeType",
    "StrategyOrderType",
]


@pytest.mark.parametrize("name", NEW_NAMES)
def test_new_name_exported(name):
    assert hasattr(dtp, name)
    assert name in dtp.__all__


def test_strategy_aliases_point_to_strategy_enums():
    assert dtp.StrategyTradeType is strategy_enums.TradeType
    assert dtp.StrategyOrderType is strategy_enums.OrderType


def test_canonical_enums_unchanged():
    assert dtp.TradeType is common.TradeType
    assert dtp.OrderType is common.OrderType


def test_executor_action_base_is_importable():
    base = executor_actions._ExecutorAction
    assert issubclass(dtp.CreateExecutorAction, base)
    assert base in dtp.CreateExecutorAction.__bases__
    assert "_ExecutorAction" not in dtp.__all__


@pytest.mark.parametrize("model", [dtp.TripleBarrierConfig, dtp.TrailingStop])
def test_models_are_frozen(model):
    assert model.model_config["frozen"] is True
