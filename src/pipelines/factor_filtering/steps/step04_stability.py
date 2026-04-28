"""Ring 4: 稳定性与状态分层检验。

检验因子在不同时间段和截面分层中的 IC 稳定性。
"""

from __future__ import annotations

import polars as pl


class StabilityChecker:
    """稳定性分层检验。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def _factor_cols(self, df: pl.DataFrame) -> list[str]:
        return [
            c for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

    def _compute_yearly_ic(self, df: pl.DataFrame, factor_col: str, label_col: str) -> dict[int, float]:
        """按年计算 IC。"""
        df_year = df.with_columns(pl.col("datetime").dt.year().alias("year"))
        yearly = df_year.group_by("year").agg(
            pl.corr(pl.col(factor_col), pl.col(label_col), method="spearman").alias("ic")
        )
        return {int(row["year"]): float(row["ic"] or 0) for row in yearly.iter_rows(named=True)}

    def _compute_rolling_ic(self, df: pl.DataFrame, factor_col: str, label_col: str, window: int = 60) -> list[float]:
        """滚动 window 日 IC 序列。"""
        dates = df.select("datetime").unique().sort("datetime")["datetime"].to_list()
        ics = []
        for i in range(window, len(dates) + 1):
            start_date = dates[i - window]
            end_date = dates[i - 1]
            subset = df.filter((pl.col("datetime") >= start_date) & (pl.col("datetime") <= end_date))
            ic = subset.select(
                pl.corr(pl.col(factor_col), pl.col(label_col), method="spearman")
            ).item()
            ics.append(float(ic) if ic else 0.0)
        return ics

    def _size_stratification(self, df: pl.DataFrame, factor_col: str, label_col: str) -> dict[str, float]:
        """按 instrument 编号分位模拟市值分层。"""
        df_ranked = df.with_columns(
            pl.col("instrument").rank(method="dense").over("datetime").alias("size_rank")
        )
        n = df_ranked.select(pl.col("size_rank").max()).item() or 1
        df_ranked = df_ranked.with_columns(
            pl.when(pl.col("size_rank") <= n * 0.33).then(pl.lit("small"))
            .when(pl.col("size_rank") <= n * 0.66).then(pl.lit("mid"))
            .otherwise(pl.lit("large"))
            .alias("size_group")
        )
        strat = df_ranked.group_by("size_group").agg(
            pl.corr(pl.col(factor_col), pl.col(label_col), method="spearman").alias("ic")
        )
        return {row["size_group"]: float(row["ic"] or 0) for row in strat.iter_rows(named=True)}

    def process(self, df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
        """计算所有因子的稳定性指标。"""
        # Ensure datetime is properly typed
        if df["datetime"].dtype == pl.String:
            df = df.with_columns(pl.col("datetime").str.to_datetime(time_unit="us"))

        factor_cols = self._factor_cols(df)
        label_col = next((c for c in df.columns if c.startswith("label")), None)
        if not label_col:
            return df, {"error": "no label column found"}

        stability = {}
        for col in factor_cols:
            yearly_ic = self._compute_yearly_ic(df, col, label_col)
            rolling_ic = self._compute_rolling_ic(df, col, label_col, window=60)
            size_ic = self._size_stratification(df, col, label_col)

            # 综合稳定性得分
            ic_values = list(yearly_ic.values())
            year_consistency = 1.0 - (pl.Series(ic_values).std() if len(ic_values) > 1 else 0)

            roll_std = pl.Series(rolling_ic).std() if len(rolling_ic) > 1 else 1.0
            roll_stability = 1.0 / (1.0 + roll_std)

            size_values = list(size_ic.values())
            size_consistency = 1.0 - (pl.Series(size_values).std() if len(size_values) > 1 else 0)

            stability_score = 0.4 * year_consistency + 0.3 * roll_stability + 0.3 * size_consistency

            stability[col] = {
                "yearly_ic": yearly_ic,
                "rolling_ic_mean": sum(rolling_ic) / max(len(rolling_ic), 1),
                "size_ic": size_ic,
                "stability_score": float(stability_score),
            }

        return df, stability
