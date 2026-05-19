"""Ring 4: 稳定性与状态分层检验。

检验因子在不同时间段和截面分层中的 IC 稳定性。
"""

from __future__ import annotations

import polars as pl
import numpy as np
from pipelines.factor_filtering.context import FilteringContext
from pipelines.factor_filtering.steps.base_step import FilteringStep


class StabilityChecker(FilteringStep):
    """稳定性分层检验。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def _factor_cols(self, df: pl.DataFrame) -> list[str]:
        return [
            c
            for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

    def _compute_daily_ic_all(
        self, df: pl.DataFrame, factor_cols: list[str], label_col: str
    ) -> pl.DataFrame:
        """向量化计算所有因子的每日 IC。"""
        return (
            df.group_by("datetime")
            .agg(
                [
                    pl.corr(pl.col(c), pl.col(label_col), method="spearman").alias(c)
                    for c in factor_cols
                ]
            )
            .sort("datetime")
        )

    def process(self, ctx: FilteringContext) -> FilteringContext:
        """计算所有因子的稳定性指标（优化版），并更新 FilteringContext。"""
        df = ctx.df
        if df["datetime"].dtype == pl.String:
            df = df.with_columns(pl.col("datetime").str.to_datetime(time_unit="us"))

        factor_cols = self._factor_cols(df)
        label_col = next((c for c in df.columns if c.startswith("label")), None)
        if not label_col:
            ctx.reports["stability_report"] = {"error": "no label column found"}
            return ctx

        # 1. 核心优化：一次性计算所有因子的每日 IC 矩阵
        daily_ic_df = self._compute_daily_ic_all(df, factor_cols, label_col)

        # 2. 市值分层计算（每个因子计算一次，但使用已计算好的 size_group）
        df_strat = df.with_columns(
            pl.col("instrument")
            .rank(method="dense")
            .over("datetime")
            .alias("size_rank")
        )
        max_rank_df = df_strat.group_by("datetime").agg(
            pl.col("size_rank").max().alias("max_rank")
        )
        df_strat = df_strat.join(max_rank_df, on="datetime").with_columns(
            pl.when(pl.col("size_rank") <= pl.col("max_rank") * 0.33)
            .then(pl.lit("small"))
            .when(pl.col("size_rank") <= pl.col("max_rank") * 0.66)
            .then(pl.lit("mid"))
            .otherwise(pl.lit("large"))
            .alias("size_group")
        )

        stability = {}
        for col in factor_cols:
            # 获取该因子的 IC 序列 (排除 null 和 nan)
            ic_series = (
                daily_ic_df.select(pl.col(col)).to_series().drop_nulls().drop_nans()
            )
            if len(ic_series) < 2:
                stability[col] = {"stability_score": 0.0}
                continue

            # 年度 IC
            yearly_ic_df = (
                daily_ic_df.select(
                    [pl.col("datetime").dt.year().alias("year"), pl.col(col)]
                )
                .filter(pl.col(col).is_not_nan())
                .group_by("year")
                .agg(pl.col(col).mean().alias("ic"))
            )
            yearly_ic = {
                int(row["year"]): float(row["ic"] or 0)
                for row in yearly_ic_df.iter_rows(named=True)
            }

            # 滚动 IC (基于已有的每日 IC 序列，极快)
            rolling_ic = ic_series.rolling_mean(window_size=60).drop_nulls()

            # 市值分层 IC
            size_strat = (
                df_strat.filter(
                    pl.col(col).is_not_nan() & pl.col(label_col).is_not_nan()
                )
                .group_by("size_group")
                .agg(
                    pl.corr(pl.col(col), pl.col(label_col), method="spearman").alias(
                        "ic"
                    )
                )
            )
            size_ic = {
                row["size_group"]: float(row["ic"] or 0)
                for row in size_strat.iter_rows(named=True)
            }

            # 稳定性得分
            ic_values = [v for v in yearly_ic.values() if not np.isnan(v)]
            year_consistency = 1.0 - (
                float(pl.Series(ic_values).std()) if len(ic_values) > 1 else 0.0
            )

            roll_std = float(rolling_ic.std()) if len(rolling_ic) > 1 else 1.0
            roll_stability = 1.0 / (1.0 + roll_std)

            size_values = [v for v in size_ic.values() if not np.isnan(v)]
            size_consistency = 1.0 - (
                float(pl.Series(size_values).std()) if len(size_values) > 1 else 0.0
            )

            stability_score = (
                0.4 * year_consistency + 0.3 * roll_stability + 0.3 * size_consistency
            )
            if np.isnan(stability_score):
                stability_score = 0.0

            stability[col] = {
                "yearly_ic": yearly_ic,
                "rolling_ic_mean": float(rolling_ic.mean() or 0),
                "size_ic": size_ic,
                "stability_score": float(stability_score),
            }

        ctx.df = df
        ctx.stability_report = stability

        return ctx
