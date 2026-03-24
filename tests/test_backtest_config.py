# tests/test_backtest_config.py
"""回测配置测试"""
from __future__ import annotations


def test_get_backtest_config():
    """测试回测配置可以导入"""
    from backtest.config import get_backtest_config

    config = get_backtest_config()
    assert "strategy" in config
    assert "executor" in config
    assert "backtest" in config


def test_strategy_config():
    """测试策略配置"""
    from backtest.config import get_strategy_config

    config = get_strategy_config(topk=30, n_drop=3)
    assert config["kwargs"]["topk"] == 30
    assert config["kwargs"]["n_drop"] == 3


def test_executor_config():
    """测试执行器配置"""
    from backtest.config import get_executor_config

    config = get_executor_config()
    assert "time_per_step" in config["kwargs"]