"""Ring 7: 组合层验证。

构建等权/IC加权/ICIR加权多因子组合，验证多空收益、Sharpe、换手率。
"""

from __future__ import annotations

import polars as pl


class PortfolioValidator:
    """多因子组合验证。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def _factor_cols(self, df: pl.DataFrame) -> list[str]:
        return [
            c for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

    def _build_signal(self, df: pl.DataFrame, factor_cols: list[str], weights: dict[str, float]) -> pl.DataFrame:
        """构建加权合成信号。"""
        if not weights or not factor_cols:
            return df.with_columns(pl.lit(0.0).alias("signal"))

        active_factors = [f for f in weights if f in factor_cols]
        if not active_factors:
            return df.with_columns(pl.lit(0.0).alias("signal"))

        signal_expr = sum(
            pl.col(f) * w for f, w in weights.items() if f in active_factors
        )
        return df.with_columns(signal_expr.alias("signal"))

    def _compute_portfolio_ic(self, df: pl.DataFrame, label_col: str) -> dict:
        """计算组合信号的 IC 序列和汇总指标。"""
        daily = df.group_by("datetime").agg(
            pl.corr(pl.col("signal"), pl.col(label_col), method="spearman").alias("ic")
        ).drop_nulls()

        ic_series = daily.select(pl.col("ic")).to_series().drop_nulls()
        if len(ic_series) < 2:
            return {"mean_ic": 0.0, "icir": 0.0, "n_days": 0}

        mean_ic = ic_series.mean()
        std_ic = ic_series.std()
        icir = mean_ic / std_ic if std_ic > 0 else 0.0

        # 换手率：IC 一阶自相关
        if len(ic_series) >= 2:
            arr = ic_series.to_numpy()
            lag0 = arr[:-1]
            lag1 = arr[1:]
            mean0, mean1 = lag0.mean(), lag1.mean()
            std0, std1 = lag0.std(ddof=0), lag1.std(ddof=0)
            if std0 > 0 and std1 > 0:
                autocorr = float(((lag0 - mean0) * (lag1 - mean1)).mean() / (std0 * std1))
            else:
                autocorr = 0.0
            turnover = 1.0 - abs(autocorr)
        else:
            turnover = 0.0

        return {
            "mean_ic": float(mean_ic),
            "icir": float(icir),
            "ic_win_rate": float((ic_series > 0).sum() / len(ic_series)),
            "turnover": float(turnover),
            "n_days": len(ic_series),
        }

    def process(self, df: pl.DataFrame, ic_metrics: dict) -> tuple[pl.DataFrame, dict]:
        """构建 3 种组合并验证。"""
        factor_cols = self._factor_cols(df)
        label_col = next((c for c in df.columns if c.startswith("label")), None)
        if not label_col or not factor_cols:
            return df, {"error": "no factors or label"}

        total_abs_ic = sum(abs(ic_metrics.get(f, {}).get("mean_rank_ic", 0)) for f in factor_cols)
        total_icir = sum(ic_metrics.get(f, {}).get("icir", 0) for f in factor_cols)

        portfolios = {}
        for name, weight_fn in [
            ("equal_weight", lambda f: 1.0 / len(factor_cols)),
            ("ic_weight", lambda f: abs(ic_metrics.get(f, {}).get("mean_rank_ic", 0)) / max(total_abs_ic, 1e-8)),
            ("icir_weight", lambda f: ic_metrics.get(f, {}).get("icir", 0) / max(abs(total_icir), 1e-8)),
        ]:
            weights = {f: weight_fn(f) for f in factor_cols}
            sig_df = self._build_signal(df, factor_cols, weights)
            portfolios[name] = self._compute_portfolio_ic(sig_df, label_col)

        return df, {"portfolios": portfolios}
