"""
qlib Dataset 配置

定义数据集配置，包括 DataHandler 和数据划分。
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def get_dataset_config(
    start_time: str = "2020-01-01",
    end_time: str = "2024-12-31",
    fit_start_time: str = "2020-01-01",
    fit_end_time: str = "2022-12-31",
    train_segment: Optional[Tuple[str, str]] = None,
    valid_segment: Optional[Tuple[str, str]] = None,
    test_segment: Optional[Tuple[str, str]] = None,
    label: Optional[str] = None,
) -> Dict[str, Any]:
    """
    获取 qlib Dataset 配置字典。

    Parameters
    ----------
    start_time : str
        数据开始时间
    end_time : str
        数据结束时间
    fit_start_time : str
        处理器拟合开始时间
    fit_end_time : str
        处理器拟合结束时间
    train_segment : tuple, optional
        训练集时间段，默认 ("2020-01-01", "2022-12-31")
    valid_segment : tuple, optional
        验证集时间段，默认 ("2023-01-01", "2023-06-30")
    test_segment : tuple, optional
        测试集时间段，默认 ("2023-07-01", "2024-12-31")
    label : str, optional
        标签表达式，默认 1 日收益率

    Returns
    -------
    dict
        qlib Dataset 配置字典
    """
    if train_segment is None:
        train_segment = ("2020-01-01", "2022-12-31")
    if valid_segment is None:
        valid_segment = ("2023-01-01", "2023-06-30")
    if test_segment is None:
        test_segment = ("2023-07-01", "2024-12-31")

    label_expr = [label] if label else ["Ref($close, -1) / $close - 1"]

    return {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "CSI1000Handler",
                "module_path": "factor.handler",
                "kwargs": {
                    "start_time": start_time,
                    "end_time": end_time,
                    "fit_start_time": fit_start_time,
                    "fit_end_time": fit_end_time,
                    "label": label_expr,
                },
            },
            "segments": {
                "train": train_segment,
                "valid": valid_segment,
                "test": test_segment,
            },
        },
    }


def get_triple_barrier_dataset_config(
    start_time: str = "2020-01-01",
    end_time: str = "2024-12-31",
    train_segment: Tuple[str, str] = ("2020-01-01", "2022-12-31"),
    valid_segment: Tuple[str, str] = ("2023-01-01", "2023-06-30"),
    test_segment: Tuple[str, str] = ("2023-07-01", "2024-12-31"),
) -> Dict[str, Any]:
    """
    获取使用 Triple Barrier Target 的 Dataset 配置。

    注意：Triple Barrier Target 需要在工作流中预处理生成，
    然后作为自定义 label 传入。
    """
    return get_dataset_config(
        start_time=start_time,
        end_time=end_time,
        train_segment=train_segment,
        valid_segment=valid_segment,
        test_segment=test_segment,
    )