"""Stage 5 & 6：基于相关性距离的因子信息聚类与代表因子筛选。

将 Spearman 相关矩阵转换为距离矩阵，使用层次聚类（precomputed metric）
对因子进行分组，为后续代表因子选取提供结构依据。
"""

from __future__ import annotations

import numpy as np
import polars as pl
from sklearn.cluster import AgglomerativeClustering


class FactorClustering:
    """基于 Spearman 距离的层次聚类，将高相关因子归为同一簇。"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        # 默认距离阈值：sqrt(0.5*(1-0.5)) ≈ 0.5，对应 Spearman ρ ≈ 0.5
        self.distance_threshold: float = self.config.get("distance_threshold", 0.5)

    def fit_predict(self, df: pl.DataFrame, factor_cols: list[str]) -> dict[str, int]:
        """对因子列进行聚类，返回 {因子名: 簇标签} 字典。

        Args:
            df: 包含因子列的 DataFrame（行为观测，列为因子）。
            factor_cols: 需要聚类的因子列名列表。

        Returns:
            每个因子对应的整数簇标签字典。
        """
        if df.height < 2 or len(factor_cols) < 2:
            return {c: 0 for c in factor_cols}

        # 用 pandas 计算 Spearman 相关矩阵（polars 暂无批量相关矩阵接口）
        pd_df = df.select(factor_cols).to_pandas()
        corr_matrix = pd_df.corr(method="spearman").fillna(0).values

        # 转换为距离矩阵：d = sqrt(0.5 * (1 - ρ))，保证三角不等式
        dist_matrix = np.sqrt(np.clip(0.5 * (1.0 - corr_matrix), 0.0, None))

        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=self.distance_threshold,
            metric="precomputed",
            linkage="complete",
        )
        labels = clustering.fit_predict(dist_matrix)

        return {col: int(lbl) for col, lbl in zip(factor_cols, labels)}

    def process(self, df: pl.DataFrame) -> pl.DataFrame:
        """流水线接口：当前透传，后续扩展为输出聚类报告并过滤冗余因子。"""
        return df
