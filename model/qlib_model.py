# model/qlib_model.py
"""
qlib Model 配置

使用 qlib 内置的 LGBModel。
"""
from __future__ import annotations

from typing import Any, Dict


def get_model_config(
    fast: bool = False,
    learning_rate: float = 0.05,
    n_estimators: int = 1000,
    num_leaves: int = 31,
    max_depth: int = -1,
    colsample_bytree: float = 0.8,
    subsample: float = 0.8,
) -> Dict[str, Any]:
    """
    获取 qlib LGBModel 配置字典。

    Parameters
    ----------
    fast : bool
        是否使用快速配置（调试用）
    learning_rate : float
        学习率
    n_estimators : int
        树的数量
    num_leaves : int
        叶子节点数
    max_depth : int
        最大深度，-1 表示不限制
    colsample_bytree : float
        列采样比例
    subsample : float
        行采样比例

    Returns
    -------
    dict
        qlib Model 配置字典
    """
    if fast:
        n_estimators = 100

    return {
        "class": "LGBModel",
        "module_path": "qlib.contrib.model.gbdt",
        "kwargs": {
            "loss": "mse",
            "learning_rate": learning_rate,
            "n_estimators": n_estimators,
            "num_leaves": num_leaves,
            "max_depth": max_depth,
            "colsample_bytree": colsample_bytree,
            "subsample": subsample,
            "early_stopping_rounds": 50,
        },
    }