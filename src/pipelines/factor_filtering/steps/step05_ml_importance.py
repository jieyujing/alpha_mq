"""Stage 8：基于机器学习的增量重要性验证（MDA / 特征重要性）。

使用 LightGBM 回归器在纯因子矩阵上拟合，输出各因子的特征重要性分数。
作为前序聚类+投组筛选的最终 ML 层校验，而非驱动筛选的主逻辑。
"""

from __future__ import annotations

import lightgbm as lgb
import polars as pl


class MLImportance:
    """LightGBM 特征重要性评估：检验因子在 ML 层面的增量贡献。"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.n_estimators: int = self.config.get("n_estimators", 10)
        self.random_state: int = self.config.get("random_state", 42)

    def evaluate_importance(
        self,
        df: pl.DataFrame,
        factor_cols: list[str],
        label_col: str,
    ) -> dict[str, float]:
        """训练 LightGBM 并返回各因子的特征重要性分数。

        Args:
            df: 包含因子列和标签列的 DataFrame。
            factor_cols: 输入特征列名列表。
            label_col: 目标标签列名。

        Returns:
            {因子名: 重要性分数} 字典。样本不足时返回全零占位。
        """
        if df.height < 4:
            return {c: 0.0 for c in factor_cols}

        X = df.select(factor_cols).to_pandas()
        y = df.select(label_col).to_pandas().iloc[:, 0]

        model = lgb.LGBMRegressor(
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            verbose=-1,  # 静默训练日志
        )
        model.fit(X, y)

        importance = model.feature_importances_
        return {col: float(imp) for col, imp in zip(factor_cols, importance)}

    def process(self, df: pl.DataFrame) -> pl.DataFrame:
        """流水线接口：当前透传，后续扩展为输出 MDA / Permutation Importance 报告。"""
        return df
