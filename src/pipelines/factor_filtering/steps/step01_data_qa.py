"""Stage 1 & 2：因子数据卫生与标签 QA。

- 将因子列中的 inf/-inf 替换为 null
- 支持 LazyFrame 或 DataFrame 输入
"""

from __future__ import annotations

import polars as pl


class DataQA:
    """因子数据卫生检查步骤：过滤无效值，为后续分析提供干净的数据基础。"""

    # 不属于因子列的元数据列名前缀/完整名
    _META_COLS = {"datetime", "instrument"}

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def _factor_cols(self, df: pl.DataFrame) -> list[str]:
        """识别因子列：排除元数据列和以 'label' 开头的列。"""
        return [
            c
            for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

    def process(self, df: pl.LazyFrame | pl.DataFrame) -> pl.DataFrame:
        """执行数据卫生清洗，返回干净的 DataFrame。"""
        if isinstance(df, pl.LazyFrame):
            df = df.collect()

        factor_cols = self._factor_cols(df)

        # 将 inf / -inf 替换为 null
        replacements = [
            pl.when(pl.col(c).is_infinite())
            .then(None)
            .otherwise(pl.col(c))
            .alias(c)
            for c in factor_cols
        ]
        if replacements:
            df = df.with_columns(replacements)

        return df
