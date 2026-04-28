"""Ring 1: 因子预处理（去极值/标准化/方向统一）。"""

from __future__ import annotations

import polars as pl


class PreprocessAndNeutralize:
    """截面因子预处理步骤。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(self, config: dict | None = None, **kwargs):
        self.config = config or {}
        self.winsorize_lower: float = kwargs.get(
            "winsorize_lower", self.config.get("winsorize_lower", 0.01)
        )
        self.winsorize_upper: float = kwargs.get(
            "winsorize_upper", self.config.get("winsorize_upper", 0.99)
        )
        self.transform_method: str = kwargs.get(
            "transform_method", self.config.get("transform_method", "rank_pct")
        )

    def _factor_cols(self, df: pl.DataFrame) -> list[str]:
        return [
            c for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

    def process(self, df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
        """执行预处理，返回处理后 DataFrame 和操作记录。"""
        factor_cols = self._factor_cols(df)
        applied = []

        if not factor_cols:
            return df, {"transform_applied": []}

        # 1. Winsorize per datetime group
        def _winsorize_group(gdf: pl.DataFrame) -> pl.DataFrame:
            exprs = []
            for c in factor_cols:
                lower = pl.col(c).quantile(self.winsorize_lower)
                upper = pl.col(c).quantile(self.winsorize_upper)
                exprs.append(pl.col(c).clip(lower, upper).alias(c))
            return gdf.with_columns(exprs)

        df = df.group_by("datetime").map_groups(_winsorize_group)
        applied.append("winsorize")

        # 2. Transform per datetime group
        def _transform_group(gdf: pl.DataFrame) -> pl.DataFrame:
            exprs = []
            for c in factor_cols:
                if self.transform_method == "rank_pct":
                    # rank_pct: map to [-1, 1]
                    exprs.append((pl.col(c).rank(method="average") / pl.col(c).count() * 2 - 1).alias(c))
                else:
                    # z-score
                    exprs.append(((pl.col(c) - pl.col(c).mean()) / pl.col(c).std()).alias(c))
            return gdf.with_columns(exprs)

        df = df.group_by("datetime").map_groups(_transform_group)
        applied.append(self.transform_method)

        return df, {"transform_applied": applied}
