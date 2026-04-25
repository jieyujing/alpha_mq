"""LGBMClassifier: Top/Bottom binary classification for high-conviction signals."""
import numpy as np
import pandas as pd
import lightgbm as lgb

from pipelines.model.base_model import BaseModel
from pipelines.model.feature_prep import make_binary_label_by_date


class LGBMClassModel(BaseModel):
    """LightGBM Classifier for Top/Bottom extreme returns.

    Trains on top 20% (label=1) vs bottom 20% (label=0), dropping middle 60%.
    """

    name = "lgbm_classifier"

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
        self._model: lgb.LGBMClassifier | None = None
        self._feature_names: list[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series, groups=None) -> "LGBMClassModel":
        self._feature_names = list(X.columns)
        X_clean = X.fillna(0).replace([np.inf, -np.inf], np.nan).fillna(0)

        y_bin, mask = make_binary_label_by_date(y, top_q=0.8, bottom_q=0.2)
        valid = mask & ~y_bin.isna()

        X_train = X_clean[valid]
        y_train = y_bin[valid].astype(int)

        self._model = lgb.LGBMClassifier(**self.params)
        self._model.fit(X_train, y_train)
        self._valid_mask = valid
        return self

    def predict(self, X: pd.DataFrame) -> pd.Series:
        """Return P(Top) as the signal score."""
        X_clean = X.fillna(0).replace([np.inf, -np.inf], np.nan).fillna(0)
        proba = self._model.predict_proba(X_clean)[:, 1]  # P(Top)
        return pd.Series(proba, index=X.index, name="prediction")

    def feature_importance(self) -> pd.Series:
        return pd.Series(self._model.feature_importances_, index=self._feature_names, name="importance")
