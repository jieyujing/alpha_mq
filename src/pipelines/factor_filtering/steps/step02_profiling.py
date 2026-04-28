"""Ring 2: 单因子横截面画像。

计算每日 Rank IC，聚合为 mean/icir/win_rate/分组收益/单调性等指标。
"""

from __future__ import annotations

import polars as pl


class SingleFactorProfiler:
    """单因子截面 IC 计算与稳定性评估。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(self, label_col: str, config: dict | None = None):
        self.label_col = label_col
        self.config = config or {}
        self.n_groups: int = self.config.get("n_groups", 5)

    def _factor_cols(self, df: pl.DataFrame) -> list[str]:
        return [
            c for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

    def compute_daily_ic(self, df: pl.DataFrame, factor_col: str) -> pl.DataFrame:
        """计算每日截面 Rank IC。"""
        return df.group_by("datetime").agg(
            pl.corr(pl.col(factor_col), pl.col(self.label_col), method="spearman").alias("ic")
        ).drop_nulls()

    def compute_group_returns(self, df: pl.DataFrame, factor_col: str) -> dict:
        """按因子值分 N 组，计算每组平均 label（代理收益）。"""
        n = self.n_groups
        ranked = df.with_columns(
            (pl.col(factor_col).rank(method="average").over("datetime")
             / pl.col(factor_col).count().over("datetime") * n - 1)
            .clip(0, n - 1)
            .floor()
            .cast(pl.Int64)
            .alias("group")
        )
        group_avg = (ranked
            .group_by("group")
            .agg(pl.col(self.label_col).mean().alias("mean_label"))
            .sort("group"))

        return {
            f"Q{int(row['group'])+1}": row["mean_label"]
            for row in group_avg.iter_rows(named=True)
        }

    def process(self, df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
        """计算所有因子的画像指标。"""
        factor_cols = self._factor_cols(df)
        metrics = {}

        for col in factor_cols:
            daily_ic = self.compute_daily_ic(df, col)
            ic_series = daily_ic.select(pl.col("ic")).to_series().drop_nulls()

            if len(ic_series) < 2:
                metrics[col] = {"mean_rank_ic": 0.0, "icir": 0.0, "ic_win_rate": 0.0,
                                "group_returns": {}, "long_short": 0.0, "monotonicity": 0.0, "n_days": 0}
                continue

            mean_ic = ic_series.mean()
            std_ic = ic_series.std()
            icir = mean_ic / std_ic if std_ic > 0 else 0.0
            win_rate = (ic_series > 0).sum() / len(ic_series)

            group_ret = self.compute_group_returns(df, col)
            long_short = group_ret.get(f"Q{self.n_groups}", 0) - group_ret.get("Q1", 0)

            # 单调性：组号与平均收益的 Spearman 相关
            if len(group_ret) >= 3:
                gs = list(group_ret.keys())
                vs = list(group_ret.values())
                from scipy.stats import spearmanr
                mono, _ = spearmanr(gs, vs)
            else:
                mono = 0.0

            metrics[col] = {
                "mean_rank_ic": float(mean_ic),
                "icir": float(icir),
                "ic_win_rate": float(win_rate),
                "group_returns": {k: float(v) for k, v in group_ret.items()},
                "long_short": float(long_short),
                "monotonicity": float(mono),
                "n_days": len(ic_series),
            }

        return df, metrics


# Backwards compatibility alias
FactorProfiler = SingleFactorProfiler
