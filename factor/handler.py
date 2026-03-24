"""
中证1000 DataHandler

使用 qlib 内置 Alpha158 因子集，配置中证1000股票池。
"""
from __future__ import annotations

from typing import List, Optional, Union

from qlib.contrib.data.handler import Alpha158
from qlib.data.dataset.handler import DataHandlerLP


class CSI1000Handler(Alpha158):
    """
    中证1000股票池的 Alpha158 因子处理器。

    继承 qlib 内置的 Alpha158，配置中证1000特定的参数。

    Parameters
    ----------
    start_time : str
        数据开始时间
    end_time : str
        数据结束时间
    fit_start_time : str
        训练集开始时间
    fit_end_time : str
        训练集结束时间
    label : list, optional
        标签表达式，默认为 1 日收益率
    **kwargs
        其他参数传递给 Alpha158
    """

    def __init__(
        self,
        start_time: str = "2020-01-01",
        end_time: str = "2024-12-31",
        fit_start_time: str = "2020-01-01",
        fit_end_time: str = "2022-12-31",
        label: Optional[List[Union[str, tuple]]] = None,
        **kwargs,
    ) -> None:
        # 默认标签：1 日收益率
        if label is None:
            label = ["Ref($close, -1) / $close - 1"]

        super().__init__(
            start_time=start_time,
            end_time=end_time,
            fit_start_time=fit_start_time,
            fit_end_time=fit_end_time,
            instruments="csi1000",
            infer_processors=[
                {"class": "ProcessInf", "module_path": "qlib.data.dataset.processor"},
                {"class": "ZScoreNorm", "module_path": "qlib.data.dataset.processor", "kwargs": {"fields_group": "feature"}},
                {"class": "Fillna", "module_path": "qlib.data.dataset.processor", "kwargs": {"fields_group": "feature"}},
            ],
            learn_processors=[
                {"class": "DropnaLabel", "module_path": "qlib.data.dataset.processor"},
                {"class": "CSRankNorm", "module_path": "qlib.data.dataset.processor", "kwargs": {"fields_group": "label"}},
            ],
            label=label,
            **kwargs,
        )