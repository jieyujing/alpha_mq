# backtest/config.py
"""
回测配置模块

定义策略、执行器和回测参数配置。
"""
from __future__ import annotations

from typing import Any, Dict


def get_strategy_config(
    topk: int = 50,
    n_drop: int = 5,
    signal: str = "<PREDICTION>",
) -> Dict[str, Any]:
    """
    获取 TopkDropoutStrategy 配置。

    Parameters
    ----------
    topk : int
        持仓股票数量
    n_drop : int
        每日调出数量
    signal : str
        信号列名，默认为模型预测值

    Returns
    -------
    dict
        策略配置字典
    """
    return {
        "class": "TopkDropoutStrategy",
        "module_path": "qlib.contrib.strategy.signal_strategy",
        "kwargs": {
            "topk": topk,
            "n_drop": n_drop,
            "signal": signal,
        },
    }


def get_executor_config(
    time_per_step: str = "day",
    generate_portfolio_metrics: bool = True,
    open_cost: float = 0.0015,
    close_cost: float = 0.0025,
    min_cost: float = 5.0,
    limit_threshold: float = 0.095,
) -> Dict[str, Any]:
    """
    获取 SimulatorExecutor 配置。

    Parameters
    ----------
    time_per_step : str
        时间步长
    generate_portfolio_metrics : bool
        是否生成组合指标
    open_cost : float
        开仓成本（买入佣金）
    close_cost : float
        平仓成本（卖出佣金）
    min_cost : float
        最低佣金
    limit_threshold : float
        涨跌停限制

    Returns
    -------
    dict
        执行器配置字典
    """
    return {
        "class": "SimulatorExecutor",
        "module_path": "qlib.contrib.executor.simulator_executor",
        "kwargs": {
            "time_per_step": time_per_step,
            "generate_portfolio_metrics": generate_portfolio_metrics,
            "trade_cost": {
                "buy": open_cost,
                "sell": close_cost,
            },
        },
    }


def get_backtest_config(
    start_time: str = "2023-07-01",
    end_time: str = "2024-12-31",
    account: float = 1000000.0,
    benchmark: str = "SH000852",  # 中证1000 指数代码
    topk: int = 50,
    n_drop: int = 5,
) -> Dict[str, Any]:
    """
    获取完整回测配置。

    Parameters
    ----------
    start_time : str
        回测开始时间
    end_time : str
        回测结束时间
    account : float
        初始资金
    benchmark : str
        基准指数
    topk : int
        持仓股票数量
    n_drop : int
        每日调出数量

    Returns
    -------
    dict
        回测配置字典
    """
    return {
        "strategy": get_strategy_config(topk=topk, n_drop=n_drop),
        "executor": get_executor_config(),
        "backtest": {
            "start_time": start_time,
            "end_time": end_time,
            "account": account,
            "benchmark": benchmark,
            "exchange_kwargs": {
                "freq": "day",
                "open_cost": 0.0015,
                "close_cost": 0.0025,
                "min_cost": 5.0,
                "limit_threshold": 0.095,
            },
        },
    }