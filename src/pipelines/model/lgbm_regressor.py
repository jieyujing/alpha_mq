"""LGBMRegressor: MSE regression for predicting returns."""
import numpy as np
import pandas as pd
import lightgbm as lgb

from pipelines.model.base_model import BaseModel


class LGBMRegModel(BaseModel):
    """LightGBM Regressor with MSE loss."""

    name = "lgbm_regressor"

    def __init__(self, **params):
        defaults = {
            "num_leaves": 31,
            "learning_rate": 0.05,
            "n_estimators": 200,
            "min_child_samples": 50,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "seed": 42,
            "verbose": -1,
        }
        defaults.update(params)
        super().__init__(**defaults)
        self._model: lgb.LGBMRegressor | None = None
        self._feature_names: list[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series, groups=None) -> "LGBMRegModel":
        self._feature_names = list(X.columns)
        X_clean = X.fillna(0).replace([np.inf, -np.inf], np.nan).fillna(0)
        self._model = lgb.LGBMRegressor(**self.params)
        self._model.fit(X_clean, y)
        return self

    def predict(self, X: pd.DataFrame) -> pd.Series:
        X_clean = X.fillna(0).replace([np.inf, -np.inf], np.nan).fillna(0)
        pred = self._model.predict(X_clean)
        return pd.Series(pred, index=X.index, name="prediction")

    def feature_importance(self) -> pd.Series:
        return pd.Series(self._model.feature_importances_, index=self._feature_names, name="importance")
