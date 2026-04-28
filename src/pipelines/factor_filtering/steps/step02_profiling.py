"""Stage 3 & 4：单因子画像与稳定性评估。

- compute_ic：基于 Polars 原生 Spearman 相关计算截面 Rank IC
- process：流水线接口（后续可扩展为逐期 IC 序列 + 滚动稳定性分析）
"""

from __future__ import annotations

import polars as pl


class FactorProfiler:
    """单因子截面 IC 计算与稳定性评估。"""

    def __init__(self, label_col: str, config: dict | None = None):
        self.label_col = label_col
        self.config = config or {}

    def compute_ic(self, df: pl.DataFrame, factor_col: str) -> dict[str, float]:
        """计算因子列与标签列之间的截面 Spearman Rank IC。

        Args:
            df: 包含因子列和标签列的 DataFrame。
            factor_col: 目标因子列名。

        Returns:
            包含 ``rank_ic`` 键的指标字典。
        """
        valid_df = df.drop_nulls(subset=[factor_col, self.label_col])
        if valid_df.height < 2:
            return {"rank_ic": 0.0}

        # Polars 原生 Spearman 相关（不引入 scipy 依赖）
        corr = valid_df.select(
            pl.corr(factor_col, self.label_col, method="spearman")
        ).item()
        return {"rank_ic": float(corr) if corr is not None else 0.0}

    def process(self, df: pl.DataFrame) -> pl.DataFrame:
        """流水线接口：当前透传，后续扩展为输出 IC 序列与稳定性报告。"""
        return df
