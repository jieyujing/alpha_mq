"""Linear models: ElasticNet (supports ridge/lasso/enet/huber)."""
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from pipelines.model.base_model import BaseModel


class LinearModel(BaseModel):
    """ElasticNet with standardization pipeline.

    Supports elastic_net (default), ridge (l1_ratio=0), lasso (l1_ratio=1), and huber.
    """

    name = "elastic_net"

    def __init__(self, alpha: float = 0.01, l1_ratio: float = 0.2, **kwargs):
        super().__init__(alpha=alpha, l1_ratio=l1_ratio, **kwargs)
        self.alpha = alpha
        self.l1_ratio = l1_ratio
        self._pipeline: Pipeline | None = None
        self._feature_names: list[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series, groups=None) -> "LinearModel":
        self._feature_names = list(X.columns)
        X_clean = X.fillna(X.median()).replace([np.inf, -np.inf], np.nan).fillna(0)
        self._pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", ElasticNet(alpha=self.alpha, l1_ratio=self.l1_ratio, max_iter=5000, random_state=42)),
        ])
        self._pipeline.fit(X_clean, y)
        return self

    def predict(self, X: pd.DataFrame) -> pd.Series:
        X_clean = X.fillna(X.median()).replace([np.inf, -np.inf], np.nan).fillna(0)
        pred = self._pipeline.predict(X_clean)
        return pd.Series(pred, index=X.index, name="prediction")

    def feature_importance(self) -> pd.Series:
        model = self._pipeline.named_steps["model"]
        return pd.Series(model.coef_, index=self._feature_names, name="importance")
