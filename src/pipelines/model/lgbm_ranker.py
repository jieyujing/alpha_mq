"""LGBMRanker: LambdaRank for direct ranking optimization."""
import numpy as np
import pandas as pd
import lightgbm as lgb

from pipelines.model.base_model import BaseModel
from pipelines.model.feature_prep import make_rank_label_by_date


class LGBMRankModel(BaseModel):
    """LightGBM Ranker with LambdaRank objective.

    Converts continuous labels to ordinal bins per date for ranking.
    """

    name = "lgbm_ranker"

    def __init__(self, **params):
        defaults = {
            "num_leaves": 31,
            "learning_rate": 0.05,
            "n_estimators": 200,
            "min_child_samples": 50,
            "seed": 42,
            "verbose": -1,
        }
        defaults.update(params)
        super().__init__(**defaults)
        self._model: lgb.LGBMRanker | None = None
        self._feature_names: list[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series, groups: list[int] | None = None) -> "LGBMRankModel":
        """Train the ranker.

        Args:
            X: Features
            y: Continuous labels (will be converted to ordinal bins)
            groups: Group sizes per date (sum = len(X)). If None, computed from index.
        """
        self._feature_names = list(X.columns)
        X_clean = X.fillna(0).replace([np.inf, -np.inf], np.nan).fillna(0)

        # Convert continuous labels to ranking bins
        rank_labels = make_rank_label_by_date(y, n_bins=5, min_group_size=10)

        # Drop rows where rank label is NaN (insufficient sample date)
        valid_mask = ~rank_labels.isna()
        X_train = X_clean[valid_mask]
        y_train = rank_labels[valid_mask]

        # Compute groups (sample count per date) from valid data
        if groups is None:
            groups_list = y_train.groupby(level=0).count().tolist()
        else:
            groups_list = groups

        self._model = lgb.LGBMRanker(objective="lambdarank", metric="ndcg", **self.params)
        self._model.fit(X_train, y_train.astype(int), group=groups_list)
        self._valid_mask = valid_mask
        return self

    def predict(self, X: pd.DataFrame) -> pd.Series:
        X_clean = X.fillna(0).replace([np.inf, -np.inf], np.nan).fillna(0)
        pred = self._model.predict(X_clean)
        return pd.Series(pred, index=X.index, name="prediction")

    def feature_importance(self) -> pd.Series:
        return pd.Series(self._model.feature_importances_, index=self._feature_names, name="importance")
