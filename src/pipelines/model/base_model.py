"""BaseModel abstract base class and model factory."""
from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd


class BaseModel(ABC):
    """Abstract base for all prediction models.

    All models share a unified interface: fit(X, y) -> predict(X) -> feature_importance().
    """

    name: str = "base"

    def __init__(self, **params):
        self.params = params
        self._model = None

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series, groups: Optional[list[int]] = None) -> "BaseModel":
        """Train the model.

        Args:
            X: Feature matrix, MultiIndex(datetime, instrument) or flat index.
            y: Label series, aligned with X.
            groups: Optional group sizes for ranking models (sum(len) == len(X)).
        """
        ...

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> pd.Series:
        """Generate prediction signals. Higher value = more bullish."""
        ...

    def feature_importance(self) -> pd.Series:
        """Return feature importance scores. Higher = more important."""
        return pd.Series(dtype=float)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, params={self.params})"


# --- Model Registry ---

def get_model(name: str, params: dict | None = None) -> BaseModel:
    """Create a model instance by name."""
    from pipelines.model.linear_model import LinearModel
    from pipelines.model.lgbm_classifier import LGBMClassModel
    from pipelines.model.lgbm_ranker import LGBMRankModel
    from pipelines.model.lgbm_regressor import LGBMRegModel

    registry: dict[str, type[BaseModel]] = {
        "elastic_net": LinearModel,
        "lgbm_regressor": LGBMRegModel,
        "lgbm_ranker": LGBMRankModel,
        "lgbm_classifier": LGBMClassModel,
    }
    if name not in registry:
        raise ValueError(f"Unknown model: {name!r}. Available: {list(registry.keys())}")
    return registry[name](**(params or {}))
