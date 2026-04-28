"""Ring 0: 数据与标签卫生检查。

检查项：
- inf/-inf → null
- 缺失率/覆盖率
- 常数/低方差因子
- 标签分布
"""

from __future__ import annotations

import polars as pl


class DataAndLabelQA:
    """数据与标签卫生检查步骤。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.min_coverage: float = self.config.get("min_coverage", 0.5)
        self.variance_threshold: float = self.config.get("variance_threshold", 1e-8)

    def _factor_cols(self, df: pl.DataFrame) -> list[str]:
        return [
            c for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

    def _label_cols(self, df: pl.DataFrame) -> list[str]:
        return [c for c in df.columns if c.startswith("label")]

    def process(self, df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
        """执行卫生检查，返回干净 DataFrame 和 QA 报告。"""
        report: dict = {"coverage": {}, "constant_factors": [], "label_stats": {}, "rejected": []}

        # 1. inf/-inf → null
        factor_cols = self._factor_cols(df)
        replacements = [
            pl.when(pl.col(c).is_infinite())
            .then(None)
            .otherwise(pl.col(c))
            .cast(df.schema[c])
            .alias(c)
            for c in factor_cols
        ]
        if replacements:
            df = df.with_columns(replacements)

        # 2. 覆盖率 + 常数检测
        height = df.height
        for col in factor_cols:
            non_null = df.select(pl.col(col).drop_nulls().len()).item()
            coverage = non_null / height if height > 0 else 0.0
            report["coverage"][col] = coverage

            valid = df.select(pl.col(col).drop_nulls())
            if valid.height >= 2:
                std = valid.select(pl.col(col).std()).item() or 0.0
                if std < self.variance_threshold:
                    report["constant_factors"].append(col)
                    report["rejected"].append((col, "constant/low_variance"))

        # 3. 标签分布
        for col in self._label_cols(df):
            report["label_stats"][col] = {
                "mean": df.select(pl.col(col).mean()).item(),
                "std": df.select(pl.col(col).std()).item(),
                "null_pct": 1.0 - df.select(pl.col(col).drop_nulls().len()).item() / height,
            }

        # 4. 低覆盖率因子剔除
        cols_to_drop = [col for col, cov in report["coverage"].items() if cov < self.min_coverage]
        report["rejected"].extend((c, "low_coverage") for c in cols_to_drop)
        if cols_to_drop:
            df = df.drop(cols_to_drop)

        return df, report
