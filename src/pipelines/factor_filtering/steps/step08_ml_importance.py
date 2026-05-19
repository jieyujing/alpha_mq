"""Ring 8: 模型增量验证。

LightGBM 回归 + Permutation Importance 确认筛选后因子的增量信息。
"""

from __future__ import annotations

import numpy as np
import polars as pl
import lightgbm as lgb
from scipy.stats import pearsonr
from pipelines.factor_filtering.context import FilteringContext
from pipelines.factor_filtering.steps.base_step import FilteringStep


class MLImportanceVerifier(FilteringStep):
    """模型增量信息验证。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(
        self,
        config: dict | None = None,
        n_estimators: int | None = None,
        random_state: int | None = None,
    ):
        self.config = config or {}
        self.n_estimators: int = (
            n_estimators
            if n_estimators is not None
            else self.config.get("n_estimators", 50)
        )
        self.random_state: int = (
            random_state
            if random_state is not None
            else self.config.get("random_state", 42)
        )

    def _factor_cols(self, df: pl.DataFrame) -> list[str]:
        return [
            c
            for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

    def process(self, ctx: FilteringContext) -> FilteringContext:
        """训练 LightGBM 并计算重要性，保存到 FilteringContext。"""
        df = ctx.df
        factor_cols = self._factor_cols(df)
        label_col = next((c for c in df.columns if c.startswith("label")), None)
        if not label_col or len(factor_cols) == 0:
            ctx.reports["ml_report"] = {"importance": {}, "permutation_importance": {}}
            return ctx

        valid = df.drop_nulls(subset=factor_cols + [label_col])
        if valid.height < 10:
            ctx.reports["ml_report"] = {
                "importance": {c: 0.0 for c in factor_cols},
                "permutation_importance": {c: 0.0 for c in factor_cols},
            }
            return ctx

        X = valid.select(factor_cols).to_pandas()
        y = valid.select(pl.col(label_col)).to_pandas().iloc[:, 0]

        model = lgb.LGBMRegressor(
            n_estimators=self.n_estimators, random_state=self.random_state, verbose=-1
        )
        model.fit(X, y)

        # Gain importance
        gain = {
            col: float(imp) for col, imp in zip(factor_cols, model.feature_importances_)
        }

        # Permutation importance (simple: shuffle each column, measure IC drop)
        base_pred = model.predict(X)
        y_rank = y.rank(method="average")
        pred_rank = pl.Series(base_pred).rank(method="average")
        base_ic = float(pearsonr(pred_rank, y_rank)[0])

        perm = {}
        for col in factor_cols:
            ic_diffs = []
            for _ in range(3):
                X_shuffled = X.copy()
                vals = X_shuffled[col].to_numpy(copy=True)
                np.random.shuffle(vals)
                X_shuffled[col] = vals
                pred = model.predict(X_shuffled)
                perm_pred_rank = pl.Series(pred).rank(method="average")
                perm_ic = float(pearsonr(perm_pred_rank, y_rank)[0])
                ic_diffs.append(base_ic - perm_ic)
            perm[col] = float(np.mean(ic_diffs))

        ctx.reports["ml_report"] = {"importance": gain, "permutation_importance": perm}

        return ctx
