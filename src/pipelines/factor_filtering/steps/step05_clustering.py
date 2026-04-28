"""Ring 5: 基于因子收益序列相关性的信息结构聚类。

因子收益 = 每日截面 IC（因子值与 label 的 Spearman 相关）。
使用因子收益的 Pearson 相关矩阵构造距离矩阵，层次聚类。
"""

from __future__ import annotations

import numpy as np
import polars as pl
from sklearn.cluster import AgglomerativeClustering


class FactorClustering:
    """基于因子收益序列相关性的层次聚类。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.distance_threshold: float = self.config.get("distance_threshold", 0.5)

    def _factor_cols(self, df: pl.DataFrame) -> list[str]:
        return [
            c for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

    def _compute_factor_returns(self, df: pl.DataFrame, factor_cols: list[str], label_col: str) -> pl.DataFrame:
        """计算每个因子每日截面 IC 作为因子收益。"""
        exprs = [
            pl.corr(pl.col(c), pl.col(label_col), method="spearman").alias(c)
            for c in factor_cols
        ]
        daily_ic = df.group_by("datetime").agg(exprs).sort("datetime").drop_nulls()
        return daily_ic

    def fit_predict(self, df: pl.DataFrame, factor_cols: list[str], label_col: str) -> dict[str, int]:
        """对因子收益序列进行聚类。"""
        if len(factor_cols) < 2:
            return {c: 0 for c in factor_cols}

        daily_ic = self._compute_factor_returns(df, factor_cols, label_col)
        if daily_ic.height < 3:
            return {c: 0 for c in factor_cols}

        # 转为 pandas 矩阵 [n_dates, n_factors]
        pd_df = daily_ic.select(factor_cols).to_pandas().fillna(0)

        # Pearson 相关性矩阵
        corr_matrix = pd_df.corr(method="pearson").fillna(0).values

        # 距离矩阵：d = sqrt(0.5 * (1 - corr))
        dist_matrix = np.sqrt(np.clip(0.5 * (1.0 - corr_matrix), 0.0, None))

        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=self.distance_threshold,
            metric="precomputed",
            linkage="complete",
        )
        labels = clustering.fit_predict(dist_matrix)

        return {col: int(lbl) for col, lbl in zip(factor_cols, labels)}

    def process(self, df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
        """流水线接口。"""
        factor_cols = self._factor_cols(df)
        label_col = next((c for c in df.columns if c.startswith("label")), None)
        if not label_col:
            return df, {"clusters": {}, "n_clusters": 0}

        clusters = self.fit_predict(df, factor_cols, label_col)
        n_clusters = len(set(clusters.values()))
        return df, {"clusters": clusters, "n_clusters": n_clusters}
