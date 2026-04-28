"""Ring 3: 横截面有效性筛选。

基于宽松阈值过滤无效因子，首次真实 drop DataFrame 列。
"""

from __future__ import annotations

import polars as pl


class CrossSectionFilter:
    """基于 Ring 2 指标执行因子过滤。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(self, config: dict | None = None, **kwargs):
        self.config = config or {}
        self.min_abs_ic: float = kwargs.get("min_abs_ic", self.config.get("min_abs_ic", 0.01))
        self.min_coverage: float = kwargs.get("min_coverage", self.config.get("min_coverage", 0.60))

    def process(
        self, df: pl.DataFrame, ic_metrics: dict
    ) -> tuple[pl.DataFrame, dict]:
        """根据 IC 指标过滤因子列。

        Args:
            df: 预处理后的 DataFrame。
            ic_metrics: Ring 2 输出的 {因子名: 指标字典}。

        Returns:
            (过滤后的 DataFrame, 筛选报告)
        """
        factor_cols = [
            c for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

        retained = []
        rejected = []

        # Find max n_days for coverage normalization
        max_days = max(
            (v.get("n_days", 0) for v in ic_metrics.values() if v.get("n_days")),
            default=1
        )

        for col in factor_cols:
            m = ic_metrics.get(col, {})
            abs_ic = abs(m.get("mean_rank_ic", 0.0))
            coverage = m.get("n_days", 0) / max(max_days, 1)

            reasons = []
            if abs_ic < self.min_abs_ic:
                reasons.append(f"abs_ic={abs_ic:.4f} < {self.min_abs_ic}")
            if coverage < self.min_coverage:
                reasons.append(f"coverage={coverage:.2%} < {self.min_coverage:.0%}")

            if reasons:
                rejected.append((col, "; ".join(reasons)))
            else:
                retained.append(col)

        cols_to_drop = [c for c, _ in rejected]
        if cols_to_drop:
            df = df.drop(cols_to_drop)

        report = {
            "retained": retained,
            "rejected": rejected,
            "retained_count": len(retained),
            "rejected_count": len(rejected),
        }

        return df, report
