from __future__ import annotations

from typing import Any, Dict
import polars as pl


class FilteringContext:
    """因子筛选流程的共享上下文对象。

    统一保存 DataFrame 状态、流程配置以及各环生成的中间指标与报告，
    从而消除各处理步骤之间的时序耦合和多参数传递。
    """

    def __init__(self, df: pl.DataFrame, config: Dict[str, Any] | None = None):
        self.df: pl.DataFrame = df
        self.config: Dict[str, Any] = config or {}

        # 统一保存所有阶段性报告和度量指标
        self.reports: Dict[str, Any] = {}

    @property
    def ic_metrics(self) -> Dict[str, Any]:
        """单因子横截面画像度量指标 (Step 02 计算)。"""
        return self.reports.get("ic_metrics", {})

    @ic_metrics.setter
    def ic_metrics(self, value: Dict[str, Any]) -> None:
        self.reports["ic_metrics"] = value

    @property
    def stability_report(self) -> Dict[str, Any]:
        """因子稳定性度量报告 (Step 04 计算)。"""
        return self.reports.get("stability_report", {})

    @stability_report.setter
    def stability_report(self, value: Dict[str, Any]) -> None:
        self.reports["stability_report"] = value

    @property
    def cluster_report(self) -> Dict[str, Any]:
        """因子聚类报告 (Step 05 计算)。"""
        return self.reports.get("cluster_report", {})

    @cluster_report.setter
    def cluster_report(self, value: Dict[str, Any]) -> None:
        self.reports["cluster_report"] = value
