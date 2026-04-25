# Model Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pluggable model training pipeline with template pattern, supporting 4 models (ElasticNet, LGBMRegressor, LGBMRanker, LGBMClassifier) across 4 label periods, with purge-based time splits, direction-aware signal orientation, cost-adjusted TopK backtest, and dual output (Markdown report + Alphalens PDF).

**Architecture:** Independent `ModelPipeline` class inheriting `DataPipeline` template. Each model implements `BaseModel` ABC. Pipeline stages: load → prepare → split → train → predict → orient → backtest → alphalens → report.

**Tech Stack:** Python 3.12, qlib, lightgbm (LGBMRegressor/Ranker/Classifier), scikit-learn (ElasticNet), alphalens, pandas, numpy.

---

## File Structure

### New Files (16 total)

| # | File | Responsibility |
|---|------|----------------|
| 1 | `src/pipelines/model/__init__.py` | Register and export all model classes |
| 2 | `src/pipelines/model/base_model.py` | `BaseModel` abstract base class |
| 3 | `src/pipelines/model/feature_prep.py` | Cross-section normalization, winsorize, impute |
| 4 | `src/pipelines/model/evaluator.py` | IC, Rank IC, ICIR, factor importance |
| 5 | `src/pipelines/model/linear_model.py` | ElasticNet model wrapper |
| 6 | `src/pipelines/model/lgbm_regressor.py` | LGBMRegressor model wrapper |
| 7 | `src/pipelines/model/lgbm_ranker.py` | LGBMRanker (LambdaRank) with rank-based label generation |
| 8 | `src/pipelines/model/lgbm_classifier.py` | LGBMClassifier Top/Bottom binary classifier |
| 9 | `src/pipelines/model/backtest.py` | TopK backtest with lag, turnover, cost, benchmark |
| 10 | `src/pipelines/model/alphalens_report.py` | Alphalens tear sheet PDF generation |
| 11 | `src/pipelines/model/model_pipeline.py` | Main ModelPipeline class with 9-stage template |
| 12 | `configs/model_pipeline.yaml` | Pipeline configuration |
| 13 | `tests/pipelines/model/test_feature_prep.py` | Tests for feature preprocessing |
| 14 | `tests/pipelines/model/test_models.py` | Tests for all 4 model wrappers |
| 15 | `tests/pipelines/model/test_backtest.py` | Tests for backtest logic |
| 16 | `tests/pipelines/model/test_pipeline_integration.py` | End-to-end integration test |

### Modified Files (2)

| # | File | Change |
|---|------|--------|
| 1 | `src/pipelines/__init__.py` | Add `ModelPipeline` to `PIPELINE_REGISTRY` |
| 2 | `pyproject.toml` | Add scikit-learn dependency (already present via lightgbm transitive, but add explicitly) |

---

### Task 1: BaseModel ABC and model factory

**Files:**
- Create: `src/pipelines/model/base_model.py`
- Create: `src/pipelines/model/__init__.py`

- [ ] **Step 1: Write BaseModel abstract class**

```python
# src/pipelines/model/base_model.py
"""BaseModel abstract base class and model factory."""
from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd


class BaseModel(ABC):
    """Abstract base for all prediction models.

    All models share a unified interface: fit(X, y) → predict(X) → feature_importance().
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
```

- [ ] **Step 2: Write the __init__.py**

```python
# src/pipelines/model/__init__.py
"""Model training pipeline: pluggable models with template pattern."""
from pipelines.model.base_model import BaseModel, get_model

__all__ = ["BaseModel", "get_model"]
```

- [ ] **Step 3: Write the test**

```python
# tests/pipelines/model/test_models.py (add at top, more tests added later)
"""Tests for model wrappers and factory."""
import pytest
import numpy as np
import pandas as pd
from pipelines.model.base_model import get_model


@pytest.fixture
def sample_data():
    """Create sample (X, y) with MultiIndex."""
    dates = pd.date_range("2020-01-01", periods=100, freq="B")
    symbols = ["SH600000", "SZ000001", "SH600010"]
    index = pd.MultiIndex.from_product([dates, symbols], names=["datetime", "instrument"])
    rng = np.random.RandomState(42)
    X = pd.DataFrame({f"f{i}": rng.randn(len(index)) for i in range(5)}, index=index)
    y = pd.Series(rng.randn(len(index)), index=index, name="label")
    return X, y


def test_get_model_unknown():
    with pytest.raises(ValueError, match="Unknown model"):
        get_model("nonexistent_model")
```

- [ ] **Step 4: Run test to verify failure**

Run: `uv run pytest tests/pipelines/model/test_models.py::test_get_model_unknown -v`
Expected: FAIL — ImportError (model modules not yet created)

- [ ] **Step 5: Commit**

```bash
git add src/pipelines/model/base_model.py src/pipelines/model/__init__.py tests/pipelines/model/test_models.py
git commit -m "feat: add BaseModel ABC and model factory registry"
```

---

### Task 2: Feature preprocessing module

**Files:**
- Create: `src/pipelines/model/feature_prep.py`
- Create: `tests/pipelines/model/test_feature_prep.py`

- [ ] **Step 1: Write tests for feature_prep**

```python
# tests/pipelines/model/test_feature_prep.py
"""Tests for cross-section feature preprocessing."""
import numpy as np
import pandas as pd
import pytest
from pipelines.model.feature_prep import (
    cross_section_rank_normalize,
    cross_section_zscore,
    winsorize_label_by_date_quantile,
    make_rank_label_by_date,
    make_binary_label_by_date,
    FeaturePreprocessor,
)


@pytest.fixture
def multiindex_data():
    dates = pd.date_range("2020-01-01", periods=5, freq="B")
    symbols = [f"SH60000{i}" for i in range(1, 11)]  # 10 symbols per day
    index = pd.MultiIndex.from_product([dates, symbols], names=["datetime", "instrument"])
    rng = np.random.RandomState(42)
    X = pd.DataFrame({f"f{i}": rng.randn(len(index)) for i in range(3)}, index=index)
    return X


@pytest.fixture
def label_series():
    dates = pd.date_range("2020-01-01", periods=5, freq="B")
    symbols = [f"SH60000{i}" for i in range(1, 11)]
    index = pd.MultiIndex.from_product([dates, symbols], names=["datetime", "instrument"])
    rng = np.random.RandomState(99)
    y = pd.Series(rng.randn(len(index)), index=index)
    # Add extreme outliers
    y.iloc[0] = 100.0
    y.iloc[1] = -100.0
    return y


def test_rank_normalize_shape(multiindex_data):
    result = cross_section_rank_normalize(multiindex_data)
    assert result.shape == multiindex_data.shape
    assert list(result.columns) == list(multiindex_data.columns)


def test_rank_normalize_range(multiindex_data):
    result = cross_section_rank_normalize(multiindex_data)
    # Values should be in [-1, 1] approximately (after rank pct transform)
    assert result.min().min() >= -1.0 - 1e-9
    assert result.max().max() <= 1.0 + 1e-9


def test_winsorize_label_by_date(label_series):
    result = winsorize_label_by_date_quantile(label_series, lower_q=0.05, upper_q=0.95)
    assert result.shape == label_series.shape
    # Extreme outliers should be clipped
    assert result.max() < 50
    assert result.min() > -50


def test_rank_label_by_date(label_series):
    result = make_rank_label_by_date(label_series, n_bins=5, min_group_size=5)
    assert len(result) == len(label_series)
    non_null = result.dropna()
    assert set(non_null.unique()) <= {0.0, 1.0, 2.0, 3.0, 4.0}


def test_rank_label_drops_small_dates(label_series):
    result = make_rank_label_by_date(label_series, n_bins=5, min_group_size=1000)
    assert result.isna().all(), "All dates have < 1000 samples, should be all NaN"


def test_binary_label_by_date(label_series):
    y_bin, mask = make_binary_label_by_date(label_series, top_q=0.8, bottom_q=0.2)
    assert len(y_bin) == len(label_series)
    assert set(y_bin.dropna().unique()) <= {0.0, 1.0}
    assert mask.sum() <= len(label_series) * 0.4 + 10  # ~40% of samples (top 20% + bottom 20%)


def test_feature_preprocessor_pipeline(multiindex_data):
    prep = FeaturePreprocessor(
        impute="cross_section_median",
        transform="rank_pct",
        winsorize_enabled=True,
        winsorize_lower=0.01,
        winsorize_upper=0.99,
    )
    result = prep.transform(multiindex_data)
    assert result.shape == multiindex_data.shape
    assert not result.isna().any().any(), "No NaN after preprocessing"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pipelines/model/test_feature_prep.py -v`
Expected: FAIL — ModuleNotFoundError (feature_prep not yet created)

- [ ] **Step 3: Implement feature_prep**

```python
# src/pipelines/model/feature_prep.py
"""Cross-section feature preprocessing for model training."""
import numpy as np
import pandas as pd
from dataclasses import dataclass


def cross_section_rank_normalize(X: pd.DataFrame) -> pd.DataFrame:
    """Transform features to cross-sectional rank percentiles [-1, 1]."""
    return X.groupby(level="datetime").transform(
        lambda s: s.rank(pct=True) * 2 - 1
    )


def cross_section_zscore(X: pd.DataFrame) -> pd.DataFrame:
    """Standardize features by cross-sectional z-score."""
    def _zscore(s):
        s = s.dropna()
        if len(s) < 2:
            return s
        return (s - s.mean()) / s.std()
    return X.groupby(level="datetime").transform(_zscore)


def cross_section_impute_median(X: pd.DataFrame) -> pd.DataFrame:
    """Fill NaN values with cross-sectional median."""
    return X.groupby(level="datetime").transform(
        lambda s: s.fillna(s.median())
    )


def cross_section_winsorize_quantile(
    X: pd.DataFrame, lower: float = 0.01, upper: float = 0.99,
) -> pd.DataFrame:
    """Winsorize features by cross-sectional quantiles."""
    def _clip(s):
        s = s.dropna()
        if len(s) < 2:
            return s
        return s.clip(s.quantile(lower), s.quantile(upper))
    return X.groupby(level="datetime").transform(_clip)


# --- Label transforms ---

def winsorize_label_by_date_quantile(
    y: pd.Series, lower_q: float = 0.01, upper_q: float = 0.99,
) -> pd.Series:
    """Winsorize labels by cross-sectional quantile per date."""
    def _clip(s):
        s = s.dropna()
        if len(s) < 2:
            return s
        return s.clip(s.quantile(lower_q), s.quantile(upper_q))
    return y.groupby(level="datetime").transform(_clip)


def make_rank_label_by_date(
    y: pd.Series, n_bins: int = 5, min_group_size: int = 30,
) -> pd.Series:
    """Convert continuous labels to ordinal bins for LGBMRanker.

    Uses rank(method='first') to avoid qcut failure on duplicate values.
    """
    def _rank_bin(s):
        s = s.dropna()
        if len(s) < min_group_size:
            return pd.Series(index=s.index, dtype=float)
        ranked = s.rank(method="first")
        return pd.qcut(ranked, q=n_bins, labels=False, duplicates="drop")
    return y.groupby(level="datetime", group_keys=False).apply(_rank_bin)


def make_binary_label_by_date(
    y: pd.Series, top_q: float = 0.8, bottom_q: float = 0.2,
) -> tuple[pd.Series, pd.Series]:
    """Create Top/Bottom binary labels for LGBMClassifier.

    Returns:
        (y_binary, mask): y_binary has 1 for top, 0 for bottom; mask indicates valid samples.
    """
    def _classify(s):
        s = s.dropna()
        if len(s) < 30:
            return pd.Series(index=s.index, dtype=float), pd.Series(False, index=s.index)
        upper = s.quantile(top_q)
        lower = s.quantile(bottom_q)
        y_bin = pd.Series(0, index=s.index)
        y_bin[s >= upper] = 1
        y_bin[s <= lower] = 0
        mask = (y_bin == 1) | (y_bin == 0)
        return y_bin, mask
    return y.groupby(level="datetime", group_keys=False).apply(_classify)


# --- Preprocessor ---

@dataclass
class FeaturePreprocessor:
    """Cross-section feature preprocessing pipeline.

    Steps (in order):
    1. Winsorize (quantile clipping)
    2. Impute (cross-section median)
    3. Transform (rank_pct or zscore)
    """

    impute: str = "cross_section_median"
    transform: str = "rank_pct"
    winsorize_enabled: bool = True
    winsorize_lower: float = 0.01
    winsorize_upper: float = 0.99

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        result = X.copy()

        # 1. Winsorize
        if self.winsorize_enabled:
            result = cross_section_winsorize_quantile(
                result, self.winsorize_lower, self.winsorize_upper
            )

        # 2. Impute
        if self.impute == "cross_section_median":
            result = cross_section_impute_median(result)

        # 3. Transform
        if self.transform == "rank_pct":
            result = cross_section_rank_normalize(result)
        elif self.transform == "zscore":
            result = cross_section_zscore(result)

        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pipelines/model/test_feature_prep.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/pipelines/model/feature_prep.py tests/pipelines/model/test_feature_prep.py
git commit -m "feat: add cross-section feature preprocessing with winsorize, impute, rank transform"
```

---

### Task 3: Evaluator module (IC, Rank IC, ICIR)

**Files:**
- Create: `src/pipelines/model/evaluator.py`
- Modify: `tests/pipelines/model/test_models.py` (add evaluator tests at end)

- [ ] **Step 1: Write evaluator module**

```python
# src/pipelines/model/evaluator.py
"""Model evaluation metrics: IC, Rank IC, ICIR, factor importance."""
import numpy as np
import pandas as pd


def compute_ic(
    predictions: pd.Series, actuals: pd.Series
) -> tuple[float, float, float, float]:
    """Compute IC (Spearman correlation) between predictions and actuals.

    Returns:
        (ic_mean, ic_std, icir, rank_ic_mean)
    """
    df = pd.DataFrame({"pred": predictions, "actual": actuals}).dropna()
    if len(df) < 5:
        return (np.nan, np.nan, np.nan, np.nan)

    ic = df["pred"].corr(df["actual"], method="spearman")
    return (ic, np.nan, np.nan, ic)


def compute_ic_by_date(
    predictions: pd.Series, actuals: pd.Series, min_obs: int = 5
) -> pd.Series:
    """Compute daily cross-sectional IC (Spearman).

    Expects MultiIndex(datetime, instrument).
    """
    df = pd.DataFrame({"pred": predictions, "actual": actuals})
    records = []
    for dt, grp in df.groupby(level=0):
        grp = grp.dropna()
        if len(grp) >= min_obs:
            ic = grp["pred"].corr(grp["actual"], method="spearman")
            records.append((dt, ic))

    if not records:
        return pd.Series(dtype=float, name="ic")

    ic_series = pd.DataFrame(records, columns=["datetime", "ic"]).set_index("datetime")["ic"]
    return ic_series


def compute_metrics_from_ic_series(ic_series: pd.Series) -> dict:
    """Compute summary metrics from daily IC series."""
    ic_mean = ic_series.mean()
    ic_std = ic_series.std()
    icir = ic_mean / ic_std if ic_std and ic_std > 0 else np.nan
    positive_ratio = (ic_series > 0).mean()
    return {
        "ic_mean": float(ic_mean),
        "ic_std": float(ic_std),
        "icir": float(icir),
        "rank_ic_mean": float(ic_mean),   # Same as ic_mean since we use Spearman
        "positive_ratio": float(positive_ratio),
    }


def compute_model_metrics(
    train_pred: pd.Series,
    train_actual: pd.Series,
    val_pred: pd.Series | None = None,
    val_actual: pd.Series | None = None,
    test_pred: pd.Series | None = None,
    test_actual: pd.Series | None = None,
) -> dict:
    """Compute evaluation metrics for train/val/test splits.

    Returns dict with keys: train_ic, train_icir, val_ic, val_icir, test_ic, test_icir, etc.
    """
    metrics = {}

    train_ic = compute_ic_by_date(train_pred, train_actual)
    metrics["train"] = compute_metrics_from_ic_series(train_ic)

    if val_pred is not None and val_actual is not None:
        val_ic = compute_ic_by_date(val_pred, val_actual)
        metrics["val"] = compute_metrics_from_ic_series(val_ic)

    if test_pred is not None and test_actual is not None:
        test_ic = compute_ic_by_date(test_pred, test_actual)
        metrics["test"] = compute_metrics_from_ic_series(test_ic)

    return metrics


def orient_signal(val_mean_ic: float, predictions: pd.Series) -> tuple[pd.Series, int]:
    """Flip signal direction if validation IC is negative.

    Returns:
        (oriented_signal, direction) where direction is +1 or -1.
    """
    if val_mean_ic < 0:
        return -predictions, -1
    return predictions, 1
```

- [ ] **Step 2: Add evaluator tests to test_models.py**

```python
# Append to tests/pipelines/model/test_models.py
from pipelines.model.evaluator import (
    compute_ic_by_date,
    compute_metrics_from_ic_series,
    orient_signal,
)


def test_ic_by_date_returns_series(sample_data):
    X, y = sample_data
    ic = compute_ic_by_date(y, y)  # Perfect correlation
    assert isinstance(ic, pd.Series)
    assert ic.mean() == pytest.approx(1.0, abs=0.01)


def test_ic_by_date_random_low(sample_data):
    X, y = sample_data
    rng = np.random.RandomState(123)
    random_pred = pd.Series(rng.randn(len(y)), index=y.index, name="pred")
    ic = compute_ic_by_date(random_pred, y)
    # Random predictions should have low mean IC
    assert abs(ic.mean()) < 0.2


def test_orient_signal_positive(sample_data):
    X, y = sample_data
    oriented, direction = orient_signal(0.05, y)
    assert direction == 1
    assert oriented.equals(y)


def test_orient_signal_negative(sample_data):
    X, y = sample_data
    oriented, direction = orient_signal(-0.05, y)
    assert direction == -1
    assert oriented.equals(-y)


def test_compute_metrics_from_ic_series():
    ic = pd.Series([0.05, 0.03, -0.01, 0.04, 0.06], name="ic")
    metrics = compute_metrics_from_ic_series(ic)
    assert "ic_mean" in metrics
    assert "icir" in metrics
    assert metrics["ic_mean"] > 0
    assert metrics["positive_ratio"] == pytest.approx(0.8)
```

- [ ] **Step 3: Run evaluator tests**

Run: `uv run pytest tests/pipelines/model/test_models.py::test_ic_by_date_returns_series tests/pipelines/model/test_models.py::test_orient_signal_positive tests/pipelines/model/test_models.py::test_orient_signal_negative tests/pipelines/model/test_models.py::test_compute_metrics_from_ic_series tests/pipelines/model/test_models.py::test_ic_by_date_random_low -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/pipelines/model/evaluator.py tests/pipelines/model/test_models.py
git commit -m "feat: add evaluator module with IC, ICIR computation and direction-aware signal orientation"
```

---

### Task 4: Model implementations (all 4 models)

**Files:**
- Create: `src/pipelines/model/linear_model.py`
- Create: `src/pipelines/model/lgbm_regressor.py`
- Create: `src/pipelines/model/lgbm_ranker.py`
- Create: `src/pipelines/model/lgbm_classifier.py`

- [ ] **Step 1: Write LinearModel (ElasticNet)**

```python
# src/pipelines/model/linear_model.py
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

    def fit(self, X: pd.DataFrame, y: pd.Series, groups=None) -> "LinearModel":
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
        return pd.Series(model.coef_, index=self._pipeline.named_steps["scaler"].get_feature_names_out(), name="importance")
```

- [ ] **Step 2: Write LGBMRegressor**

```python
# src/pipelines/model/lgbm_regressor.py
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

    def fit(self, X: pd.DataFrame, y: pd.Series, groups=None) -> "LGBMRegModel":
        X_clean = X.fillna(0).replace([np.inf, -np.inf], np.nan).fillna(0)
        self._model = lgb.LGBMRegressor(**self.params)
        self._model.fit(X_clean, y)
        return self

    def predict(self, X: pd.DataFrame) -> pd.Series:
        X_clean = X.fillna(0).replace([np.inf, -np.inf], np.nan).fillna(0)
        pred = self._model.predict(X_clean)
        return pd.Series(pred, index=X.index, name="prediction")

    def feature_importance(self) -> pd.Series:
        return pd.Series(self._model.feature_importances_, index=X.columns if hasattr(self, 'X') else [], name="importance")
```

- [ ] **Step 2b: Fix LGBMRegModel.feature_importance to track columns**

Update `fit` method to store feature names:

```python
    def fit(self, X: pd.DataFrame, y: pd.Series, groups=None) -> "LGBMRegModel":
        self._feature_names = list(X.columns)
        X_clean = X.fillna(0).replace([np.inf, -np.inf], np.nan).fillna(0)
        self._model = lgb.LGBMRegressor(**self.params)
        self._model.fit(X_clean, y)
        return self

    def feature_importance(self) -> pd.Series:
        return pd.Series(self._model.feature_importances_, index=self._feature_names, name="importance")
```

- [ ] **Step 3: Write LGBMRanker**

```python
# src/pipelines/model/lgbm_ranker.py
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

        # Compute groups from valid data
        if groups is None:
            counts = y.groupby(level=0).count()
            valid_counts = counts[valid_mask.groupby(level=0).any()]
            groups_list = valid_counts.tolist()
        else:
            groups_list = groups

        self._model = lgb.LGBMRanker(objective="lambdarank", metric="ndcg", group=groups_list, **self.params)
        self._model.fit(X_train, y_train.astype(int))
        self._valid_mask = valid_mask
        return self

    def predict(self, X: pd.DataFrame) -> pd.Series:
        X_clean = X.fillna(0).replace([np.inf, -np.inf], np.nan).fillna(0)
        pred = self._model.predict(X_clean)
        return pd.Series(pred, index=X.index, name="prediction")

    def feature_importance(self) -> pd.Series:
        return pd.Series(self._model.feature_importances_, index=self._feature_names, name="importance")
```

- [ ] **Step 4: Write LGBMClassifier**

```python
# src/pipelines/model/lgbm_classifier.py
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
```

- [ ] **Step 5: Add model wrapper tests to test_models.py**

```python
# Append to tests/pipelines/model/test_models.py
from pipelines.model.linear_model import LinearModel
from pipelines.model.lgbm_regressor import LGBMRegModel
from pipelines.model.lgbm_ranker import LGBMRankModel
from pipelines.model.lgbm_classifier import LGBMClassModel
from pipelines.model.base_model import get_model


def _make_train_data(n_dates=20, n_symbols=20, n_features=5):
    """Create sufficiently large training data for model tests."""
    dates = pd.date_range("2020-01-01", periods=n_dates, freq="B")
    symbols = [f"SH60000{i}" for i in range(1, n_symbols + 1)]
    index = pd.MultiIndex.from_product([dates, symbols], names=["datetime", "instrument"])
    rng = np.random.RandomState(42)
    X = pd.DataFrame({f"f{i}": rng.randn(len(index)) for i in range(n_features)}, index=index)
    y = pd.Series(rng.randn(len(index)), index=index)
    return X, y


def test_get_model_all_types():
    for name in ["elastic_net", "lgbm_regressor", "lgbm_ranker", "lgbm_classifier"]:
        model = get_model(name)
        assert model.name in [name, "elastic_net", "lgbm_regressor", "lgbm_ranker", "lgbm_classifier"]


def test_linear_model_fit_predict():
    X, y = _make_train_data()
    model = LinearModel(alpha=0.01, l1_ratio=0.2)
    model.fit(X, y)
    pred = model.predict(X)
    assert len(pred) == len(y)
    assert not pred.isna().any()
    imp = model.feature_importance()
    assert len(imp) == X.shape[1]


def test_lgbm_regressor_fit_predict():
    X, y = _make_train_data()
    model = LGBMRegModel(n_estimators=10, verbose=-1)
    model.fit(X, y)
    pred = model.predict(X)
    assert len(pred) == len(y)
    assert not pred.isna().any()
    imp = model.feature_importance()
    assert len(imp) == X.shape[1]


def test_lgbm_ranker_fit_predict():
    X, y = _make_train_data()
    model = LGBMRankModel(n_estimators=10, verbose=-1)
    model.fit(X, y)
    pred = model.predict(X)
    assert len(pred) == len(y)


def test_lgbm_classifier_fit_predict():
    X, y = _make_train_data()
    model = LGBMClassModel(n_estimators=10, verbose=-1)
    model.fit(X, y)
    pred = model.predict(X)
    assert len(pred) == len(y)
    # Should be probability values (0 to 1)
    assert pred.min() >= 0
    assert pred.max() <= 1
```

- [ ] **Step 6: Run all model tests**

Run: `uv run pytest tests/pipelines/model/test_models.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/pipelines/model/linear_model.py src/pipelines/model/lgbm_regressor.py src/pipelines/model/lgbm_ranker.py src/pipelines/model/lgbm_classifier.py tests/pipelines/model/test_models.py
git commit -m "feat: implement all 4 model wrappers (ElasticNet, LGBMRegressor, LGBMRanker, LGBMClassifier)"
```

---

### Task 5: Backtest module

**Files:**
- Create: `src/pipelines/model/backtest.py`
- Create: `tests/pipelines/model/test_backtest.py`

- [ ] **Step 1: Write backtest tests**

```python
# tests/pipelines/model/test_backtest.py
"""Tests for TopK backtest with lag, turnover, cost, and benchmark."""
import numpy as np
import pandas as pd
import pytest
from pipelines.model.backtest import topk_backtest


@pytest.fixture
def returns_and_signals():
    """Create returns matrix and signals for backtest."""
    dates = pd.date_range("2020-01-01", periods=30, freq="B")
    symbols = [f"SH60000{i}" for i in range(1, 21)]
    index = pd.MultiIndex.from_product([dates, symbols], names=["datetime", "instrument"])
    rng = np.random.RandomState(42)

    returns_wide = pd.DataFrame(
        rng.randn(len(dates), len(symbols)) * 0.02,
        index=dates, columns=symbols,
    )
    signals_wide = pd.DataFrame(
        rng.randn(len(dates), len(symbols)),
        index=dates, columns=symbols,
    )
    return returns_wide, signals_wide


def test_backtest_returns_length(returns_and_signals):
    ret_wide, sig_wide = returns_and_signals
    port_ret, excess, turnover, weights = topk_backtest(ret_wide, sig_wide, topk=5)
    assert len(port_ret) == len(ret_wide)
    assert len(excess) == len(ret_wide)
    assert len(turnover) == len(ret_wide)


def test_backtest_excess_reasonable(returns_and_signals):
    ret_wide, sig_wide = returns_and_signals
    port_ret, excess, turnover, weights = topk_backtest(ret_wide, sig_wide, topk=5)
    # Excess should be portfolio - benchmark (equal weight)
    ew_ret = ret_wide.mean(axis=1)
    assert (excess + ew_ret - port_ret).abs().max() < 1e-10


def test_backtest_costs_applied(returns_and_signals):
    ret_wide, sig_wide = returns_and_signals
    port_ret, excess, turnover, weights = topk_backtest(ret_wide, sig_wide, topk=5, transaction_cost_bps=100)
    port_ret_no_cost, _, _, _ = topk_backtest(ret_wide, sig_wide, topk=5, transaction_cost_bps=0)
    # With 100bps cost, net returns should be lower
    assert (port_ret - port_ret_no_cost).sum() < 0


def test_backtest_lag_signal_shift(returns_and_signals):
    ret_wide, sig_wide = returns_and_signals
    port_ret, excess, turnover, weights = topk_backtest(ret_wide, sig_wide, topk=5, shift_signal_days=1)
    # First row of weights should be NaN (no prior signal)
    assert weights.iloc[0].isna().all()


def test_backtest_turnover_positive(returns_and_signals):
    ret_wide, sig_wide = returns_and_signals
    port_ret, excess, turnover, weights = topk_backtest(ret_wide, sig_wide, topk=5)
    assert (turnover >= 0).all()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pipelines/model/test_backtest.py -v`
Expected: FAIL — ModuleNotFoundError (backtest not yet created)

- [ ] **Step 3: Implement backtest module**

```python
# src/pipelines/model/backtest.py
"""TopK backtest with signal lag, turnover, and transaction costs."""
import numpy as np
import pandas as pd
from dataclasses import dataclass


def topk_backtest(
    returns_wide: pd.DataFrame,
    signals_wide: pd.DataFrame,
    topk: int = 50,
    transaction_cost_bps: float = 10,
    shift_signal_days: int = 1,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.DataFrame]:
    """Run TopK backtest.

    Args:
        returns_wide: Daily returns, index=datetime, columns=instrument.
        signals_wide: Model signals, index=datetime, columns=instrument.
        topk: Number of stocks to hold.
        transaction_cost_bps: Transaction cost in basis points.
        shift_signal_days: Days to lag signal (T signal → T+lag execution).

    Returns:
        (portfolio_returns, excess_returns, turnover, weights)
        All with datetime index.
    """
    # Ensure aligned dates
    common_dates = returns_wide.index.intersection(signals_wide.index)
    returns_wide = returns_wide.loc[common_dates]
    signals_wide = signals_wide.loc[common_dates]

    # Shift signals forward (lag)
    lagged_signals = signals_wide.shift(shift_signal_days)

    n_assets = len(returns_wide.columns)
    ew_returns = returns_wide.mean(axis=1)  # Equal-weight benchmark

    port_returns = []
    excess_returns = []
    turnovers = []
    weights_history = []

    prev_weights = pd.Series(0.0, index=returns_wide.columns)

    for date in common_dates:
        sig = lagged_signals.loc[date].dropna()
        if len(sig) < topk:
            # Not enough signals, hold cash
            w = pd.Series(0.0, index=returns_wide.columns)
            port_returns.append(np.nan)
            excess_returns.append(np.nan)
        else:
            top_k = sig.nlargest(topk).index
            w = pd.Series(0.0, index=returns_wide.columns)
            w[top_k] = 1.0 / topk

        # Turnover
        turnover = (w - prev_weights).abs().sum() / 2
        cost = turnover * transaction_cost_bps / 10000

        # Portfolio return
        gross_ret = (w * returns_wide.loc[date]).sum()
        net_ret = gross_ret - cost

        port_returns.append(net_ret)
        excess_returns.append(net_ret - ew_returns.loc[date])
        turnovers.append(turnover)
        weights_history.append(w)
        prev_weights = w

    port_ret = pd.Series(port_returns, index=common_dates, name="portfolio_return")
    excess_ret = pd.Series(excess_returns, index=common_dates, name="excess_return")
    turnover = pd.Series(turnovers, index=common_dates, name="turnover")
    weights = pd.DataFrame(weights_history, index=common_dates)

    return port_ret, excess_ret, turnover, weights


def compute_backtest_metrics(
    port_ret: pd.Series,
    excess_ret: pd.Series,
    turnover: pd.Series,
    ann_factor: int = 252,
) -> dict:
    """Compute backtest performance metrics."""
    port_ret = port_ret.dropna()
    excess_ret = excess_ret.dropna()

    ann_ret = (1 + port_ret).prod() ** (ann_factor / len(port_ret)) - 1
    ann_excess = excess_ret.mean() * ann_factor
    sharpe = port_ret.mean() / port_ret.std() * np.sqrt(ann_factor) if port_ret.std() > 0 else 0
    excess_sharpe = excess_ret.mean() / excess_ret.std() * np.sqrt(ann_factor) if excess_ret.std() > 0 else 0

    cum_ret = (1 + port_ret).cumprod()
    max_dd = ((cum_ret / cum_ret.cummax()) - 1).min()

    avg_turnover = turnover.mean()
    win_rate = (port_ret > 0).mean()

    return {
        "ann_return": float(ann_ret),
        "ann_excess_return": float(ann_excess),
        "sharpe": float(sharpe),
        "excess_sharpe": float(excess_sharpe),
        "max_drawdown": float(max_dd),
        "win_rate": float(win_rate),
        "avg_turnover": float(avg_turnover),
        "n_periods": len(port_ret),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pipelines/model/test_backtest.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/pipelines/model/backtest.py tests/pipelines/model/test_backtest.py
git commit -m "feat: add TopK backtest with 1-day lag, turnover, transaction cost, and benchmark excess"
```

---

### Task 6: Alphalens report module

**Files:**
- Create: `src/pipelines/model/alphalens_report.py`

- [ ] **Step 1: Write alphalens report module**

```python
# src/pipelines/model/alphalens_report.py
"""Alphalens tear sheet generation from model prediction signals."""
import logging
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import alphalens


def generate_alphalens_tear_sheet(
    factor: pd.Series,
    prices: pd.DataFrame,
    output_dir: Path,
    periods: tuple = (1, 5, 10, 20),
    quantiles: int = 5,
) -> Path:
    """Generate Alphalens tear sheet PDF for model prediction signals.

    Args:
        factor: MultiIndex Series (datetime, instrument) — model predictions.
        prices: DataFrame (datetime × instrument) — close prices.
        output_dir: Directory to save outputs.
        periods: Forward return periods for Alphalens.
        quantiles: Number of quantile groups.

    Returns:
        Path to the PDF file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Prepare factor data
    factor = factor.copy()
    factor.index = factor.index.rename(["date", "asset"])
    factor = factor.sort_index()

    # Ensure prices index is datetime
    prices.index = pd.to_datetime(prices.index)
    prices = prices.sort_index()

    try:
        factor_data = alphalens.utils.get_clean_factor_and_forward_returns(
            factor=factor,
            prices=prices,
            periods=periods,
            quantiles=quantiles,
            filter_zscore=None,
        )
    except Exception as e:
        logging.warning(f"Alphalens get_clean_factor failed: {e}. Skipping tear sheet.")
        return None

    # Save factor data CSV
    factor_data.to_csv(output_dir / "factor_data.csv")

    # Save quantile returns CSV
    mean_ret = alphalens.performance.mean_return_by_quantile(factor_data)[0]
    mean_ret.to_csv(output_dir / "quantile_returns.csv")

    # Generate PDF
    pdf_path = output_dir / "tear_sheet.pdf"
    with PdfPages(str(pdf_path)) as pdf:
        matplotlib.rcParams["figure.figsize"] = (16, 10)

        # Page 1: IC Analysis
        ic = alphalens.performance.factor_information_coefficient(factor_data)
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        try:
            alphalens.plotting.plot_ic_ts(ic, ax=axes[0, 0])
        except Exception:
            axes[0, 0].text(0.5, 0.5, "IC Time Series: N/A", ha="center", va="center")
        try:
            alphalens.plotting.plot_ic_hist(ic, ax=axes[0, 1])
        except Exception:
            axes[0, 1].text(0.5, 0.5, "IC Histogram: N/A", ha="center", va="center")
        try:
            alphalens.plotting.plot_ic_monthly(ic, ax=axes[1, 0])
        except Exception:
            axes[1, 0].text(0.5, 0.5, "IC Monthly: N/A", ha="center", va="center")
        fig.suptitle("Information Coefficient Analysis", fontsize=16)
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # Page 2: Quantile Analysis
        mean_ret_q, std_q = alphalens.performance.mean_return_by_quantile(factor_data)
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        try:
            alphalens.plotting.plot_quantile_average_cumulative_return(
                mean_ret_q, ax=axes[0, 0]
            )
        except Exception:
            axes[0, 0].text(0.5, 0.5, "Cumulative Returns: N/A", ha="center", va="center")
        try:
            alphalens.plotting.plot_cumulative_returns_by_quantile(
                mean_ret_q, ax=axes[0, 1]
            )
        except Exception:
            axes[0, 1].text(0.5, 0.5, "Quantile Returns: N/A", ha="center", va="center")
        try:
            alphalens.plotting.plot_mean_quantile_returns_spread_time_series(
                mean_ret_q, std_q, ax=axes[1, 0]
            )
        except Exception:
            axes[1, 0].text(0.5, 0.5, "Spread Returns: N/A", ha="center", va="center")
        fig.suptitle("Quantile Analysis", fontsize=16)
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # Page 3: Turnover
        fig, ax = plt.subplots(1, 1, figsize=(16, 6))
        try:
            quantile_turnover = alphalens.performance.quantile_turnover(
                alphalens.utils.get_clean_factor_and_forward_returns(
                    factor=factor, prices=prices, periods=periods, quantiles=quantiles,
                    filter_zscore=None,
                ),
                quantiles,
            )
            quantile_turnover.plot(ax=ax, title="Quantile Turnover")
        except Exception:
            ax.text(0.5, 0.5, "Turnover: N/A", ha="center", va="center")
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

    logging.info(f"Alphalens tear sheet saved to {pdf_path}")
    return pdf_path
```

- [ ] **Step 2: Commit**

```bash
git add src/pipelines/model/alphalens_report.py
git commit -m "feat: add Alphalens tear sheet PDF generation using model predictions as factor"
```

---

### Task 7: ModelPipeline main class

**Files:**
- Create: `src/pipelines/model/model_pipeline.py`

- [ ] **Step 1: Write the ModelPipeline class**

```python
# src/pipelines/model/model_pipeline.py
"""ModelPipeline: Template-pattern pipeline for model training and backtest."""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from pipelines.base import DataPipeline
from pipelines.model.base_model import BaseModel, get_model
from pipelines.model.feature_prep import FeaturePreprocessor, winsorize_label_by_date_quantile
from pipelines.model.evaluator import compute_ic_by_date, compute_metrics_from_ic_series, orient_signal, compute_model_metrics
from pipelines.model.backtest import topk_backtest, compute_backtest_metrics


@dataclass
class TrainingResult:
    """Container for one model × label training result."""
    model_name: str
    label_name: str
    model: BaseModel
    train_metrics: dict = field(default_factory=dict)
    val_metrics: dict = field(default_factory=dict)
    test_metrics: dict = field(default_factory=dict)
    val_mean_ic: float = 0.0
    train_predictions: pd.Series = field(default_factory=pd.Series)
    val_predictions: pd.Series = field(default_factory=pd.Series)
    test_predictions: pd.Series = field(default_factory=pd.Series)
    oriented_test_signal: pd.Series = field(default_factory=pd.Series)
    oriented_direction: int = 1
    backtest_returns: pd.Series = field(default_factory=pd.Series)
    backtest_excess: pd.Series = field(default_factory=pd.Series)
    backtest_turnover: pd.Series = field(default_factory=pd.Series)
    backtest_metrics: dict = field(default_factory=dict)
    feature_importance: pd.Series = field(default_factory=pd.Series)
    metadata: dict = field(default_factory=dict)


class ModelPipeline(DataPipeline):
    """Pluggable model training and backtest pipeline.

    Stages: load → prepare → split → train → predict → orient → backtest → alphalens → report
    """

    STAGE_METHOD_MAP = {
        "load": "load_data",
        "prepare": "prepare_features_labels",
        "split": "make_time_splits",
        "train": "train_models",
        "predict": "run_predict",
        "orient": "orient_signals",
        "backtest": "run_backtest",
        "alphalens": "generate_alphalens",
        "report": "generate_report",
    }

    def download(self): ...
    def validate(self): return []
    def clean(self): ...
    def ingest_to_qlib(self): ...

    # --- Stage: load ---

    def load_data(self):
        data_cfg = self.config.get("data", {})
        factor_pool_path = data_cfg.get("factor_pool", "data/factor_pool_relaxed.parquet")
        self.df = pd.read_parquet(factor_pool_path)
        self.df.index = pd.MultiIndex.from_arrays(
            [self.df.index.get_level_values(0), self.df.index.get_level_values(1)],
            names=["datetime", "instrument"],
        )
        logging.info(f"Loaded factor pool: {self.df.shape}")

    # --- Stage: prepare ---

    def prepare_features_labels(self):
        feat_cfg = self.config.get("features", {})
        label_cfg = self.config.get("label", {})

        self.preprocessor = FeaturePreprocessor(
            impute=feat_cfg.get("impute", "cross_section_median"),
            transform=feat_cfg.get("transform", "rank_pct"),
            winsorize_enabled=feat_cfg.get("winsorize", {}).get("enabled", True),
            winsorize_lower=feat_cfg.get("winsorize", {}).get("lower", 0.01),
            winsorize_upper=feat_cfg.get("winsorize", {}).get("upper", 0.99),
        )

        # Separate factor columns from label columns
        label_cols = [c for c in self.df.columns if c.startswith("label_")]
        factor_cols = [c for c in self.df.columns if c not in label_cols]

        self.X_raw = self.df[factor_cols].copy()
        self.X = self.preprocessor.transform(self.X_raw)

        self.labels = {}
        for col in label_cols:
            y = self.df[col].copy()
            if label_cfg.get("winsorize", {}).get("enabled", True):
                y = winsorize_label_by_date_quantile(
                    y,
                    lower_q=label_cfg.get("winsorize", {}).get("lower", 0.01),
                    upper_q=label_cfg.get("winsorize", {}).get("upper", 0.99),
                )
            self.labels[col] = y

        logging.info(f"Features prepared: {self.X.shape}, Labels: {list(self.labels.keys())}")

    # --- Stage: split ---

    def make_time_splits(self):
        split_cfg = self.config.get("split", {})
        self.splits = {}
        for label_name in self.config["model"]["target_labels"]:
            horizon = int(label_name.replace("label_", "").replace("d", ""))
            train_start = split_cfg.get("train_start", "2020-01-01")
            train_end = split_cfg.get("train_end", "2023-12-31")
            val_start = split_cfg.get("val_start", "2024-01-01")
            val_end = split_cfg.get("val_end", "2024-06-30")
            test_start = split_cfg.get("test_start", "2024-07-01")
            test_end = split_cfg.get("test_end")

            # Purge: subtract horizon trading days from boundaries
            if split_cfg.get("purge_by_label", True):
                train_end_adj = self._subtract_trading_days(train_end, horizon)
                val_end_adj = self._subtract_trading_days(val_end, horizon)
            else:
                train_end_adj = train_end
                val_end_adj = val_end

            self.splits[label_name] = {
                "train": (train_start, train_end_adj),
                "val": (val_start, val_end_adj),
                "test": (test_start, test_end),
            }
        logging.info(f"Time splits computed for {len(self.splits)} labels")

    def _subtract_trading_days(self, end_date: str, days: int) -> str:
        """Subtract N trading days from a date string."""
        try:
            import qlib
            from qlib.data import D
            qlib.init(provider_uri=self.config["data"]["qlib_bin"])
            cal = D.calendar()
        except Exception:
            # Fallback: use calendar days (5 trading days ≈ 7 calendar days)
            from datetime import timedelta
            end = pd.Timestamp(end_date) if not isinstance(end_date, pd.Timestamp) else end_date
            return (end - timedelta(days=days * 7 // 5)).strftime("%Y-%m-%d")

        end = pd.Timestamp(end_date) if not isinstance(end_date, pd.Timestamp) else end_date
        cal_before = cal[cal <= end]
        if len(cal_before) <= days:
            return cal_before[0].strftime("%Y-%m-%d")
        return cal_before[-days - 1].strftime("%Y-%m-%d")

    def _get_date_mask(self, y: pd.Series, start: str, end: Optional[str]) -> pd.Series:
        """Boolean mask for dates in [start, end]."""
        dates = y.index.get_level_values(0)
        mask = dates >= start
        if end:
            mask &= dates <= end
        return mask

    # --- Stage: train ---

    def train_models(self):
        model_cfg = self.config["model"]
        model_names = model_cfg.get("names", ["elastic_net"])
        label_names = model_cfg.get("target_labels", ["label_5d"])
        model_params = model_cfg.get("params", {})

        self.results: list[TrainingResult] = []

        for model_name in model_names:
            for label_name in label_names:
                label = self.labels[label_name]
                splits = self.splits[label_name]

                train_mask = self._get_date_mask(label, *splits["train"])
                val_mask = self._get_date_mask(label, *splits["val"])

                X_train = self.X[train_mask]
                y_train = label[train_mask]
                X_val = self.X[val_mask]
                y_val = label[val_mask]

                # Train
                params = model_params.get(model_name, {})
                model = get_model(model_name, params)
                model.fit(X_train, y_train)

                # Predict
                train_pred = model.predict(X_train)
                val_pred = model.predict(X_val)

                # Metrics
                metrics = compute_model_metrics(train_pred, y_train, val_pred, y_val)

                val_mean_ic = metrics["val"]["ic_mean"] if "val" in metrics else 0.0

                result = TrainingResult(
                    model_name=model_name,
                    label_name=label_name,
                    model=model,
                    train_metrics=metrics["train"],
                    val_metrics=metrics.get("val", {}),
                    test_metrics={},
                    val_mean_ic=val_mean_ic,
                    train_predictions=train_pred,
                    val_predictions=val_pred,
                    test_predictions=pd.Series(dtype=float),
                )
                self.results.append(result)

        logging.info(f"Trained {len(self.results)} model×label combinations")

    # --- Stage: predict (test set) ---

    def run_predict(self):
        for result in self.results:
            label_name = result.label_name
            splits = self.splits[label_name]
            label = self.labels[label_name]
            test_mask = self._get_date_mask(label, *splits["test"])

            if test_mask.sum() == 0:
                logging.warning(f"No test data for {result.model_name} / {label_name}")
                continue

            X_test = self.X[test_mask]
            y_test = label[test_mask]

            test_pred = result.model.predict(X_test)
            result.test_predictions = test_pred

            # Test metrics
            test_ic = compute_ic_by_date(test_pred, y_test)
            result.test_metrics = compute_metrics_from_ic_series(test_ic)

    # --- Stage: orient ---

    def orient_signals(self):
        for result in self.results:
            if result.test_predictions.empty:
                continue
            oriented, direction = orient_signal(result.val_mean_ic, result.test_predictions)
            result.oriented_test_signal = oriented
            result.oriented_direction = direction

    # --- Stage: backtest ---

    def run_backtest(self):
        bt_cfg = self.config.get("backtest", {})
        topk = bt_cfg.get("topk", 50)
        cost_bps = bt_cfg.get("transaction_cost_bps", 10)
        shift = bt_cfg.get("shift_signal_days", 1)

        # Build returns wide from factor pool
        close_col = None
        # Try to find close price column in raw data
        if "close" in self.df.columns:
            close_col = "close"
        # Otherwise compute from qlib
        if close_col is None:
            try:
                import qlib
                from qlib.data import D
                qlib.init(provider_uri=self.config["data"]["qlib_bin"])
                instruments = list(self.df.index.get_level_values("instrument").unique())
                close_data = D.features(instruments, ["$close"], start_time="2020-01-01", end_time=None, freq="day")
                close_data.columns = ["close"]
                if close_data.index.names == ["instrument", "datetime"]:
                    close_data = close_data.swaplevel().sort_index()
                    close_data.index.names = ["datetime", "instrument"]
                close_col = "__close__"
                self.df[close_col] = close_data["close"]
            except Exception as e:
                logging.warning(f"Could not load close prices: {e}")
                return

        returns_wide = self.df.groupby("datetime")[close_col].pct_change().unstack()
        returns_wide = returns_wide.sort_index()

        for result in self.results:
            if result.oriented_test_signal.empty:
                continue

            # Convert signal to wide
            signals_wide = result.oriented_test_signal.unstack()

            port_ret, excess_ret, turnover, weights = topk_backtest(
                returns_wide, signals_wide,
                topk=topk, transaction_cost_bps=cost_bps, shift_signal_days=shift,
            )

            result.backtest_returns = port_ret
            result.backtest_excess = excess_ret
            result.backtest_turnover = turnover

            result.backtest_metrics = compute_backtest_metrics(port_ret, excess_ret, turnover)

    # --- Stage: alphalens ---

    def generate_alphalens(self):
        from pipelines.model.alphalens_report import generate_alphalens_tear_sheet

        output_cfg = self.config.get("output", {})
        alphalens_dir = Path(output_cfg.get("alphalens", "data/model_results/alphalens"))

        # Find best model by oriented_val_icir
        best = None
        best_icir = -np.inf
        for r in self.results:
            icir = abs(r.val_metrics.get("icir", 0))
            if icir > best_icir and not r.oriented_test_signal.empty:
                best_icir = icir
                best = r

        if best is None:
            logging.warning("No valid model result found for Alphalens.")
            return

        # Get close prices
        close_col = None
        for col in self.df.columns:
            if "close" in col.lower():
                close_col = col
                break

        if close_col:
            prices_wide = self.df.groupby("datetime")[close_col].mean().unstack()
        else:
            logging.warning("No close price column found for Alphalens.")
            return

        generate_alphalens_tear_sheet(
            factor=best.oriented_test_signal,
            prices=prices_wide,
            output_dir=alphalens_dir,
        )

    # --- Stage: report ---

    def generate_report(self):
        from pathlib import Path
        import yaml

        output_cfg = self.config.get("output", {})
        report_path = Path(output_cfg.get("report", "data/model_results/model_report.md"))
        report_path.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        lines.append("# Model Training Report")
        lines.append("")
        lines.append(f"**Generated**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Static split — results may not reflect rolling live performance**")
        lines.append("")

        # 1. Model × Period Direction Table
        lines.append("## 1. Model × Period Direction")
        lines.append("")
        lines.append("| Model | Label | Val IC | Direction | Oriented IC | Oriented ICIR |")
        lines.append("|-------|-------|--------|-----------|-------------|---------------|")
        for r in self.results:
            d = "→" if r.oriented_direction == 1 else "← (flipped)"
            lines.append(
                f"| {r.model_name} | {r.label_name} | "
                f"{r.val_mean_ic:.4f} | {d} | "
                f"{abs(r.val_mean_ic):.4f} | "
                f"{abs(r.val_metrics.get('icir', 0)):.4f} |"
            )
        lines.append("")

        # 2. OOS TopK Excess Table
        lines.append("## 2. Out-of-Sample TopK Performance")
        lines.append("")
        lines.append("| Model | Label | Ann Ret | Excess Ann Ret | Sharpe | Max DD | Turnover | Cost Adj Sharpe |")
        lines.append("|-------|-------|---------|----------------|--------|--------|----------|-----------------|")
        for r in self.results:
            m = r.backtest_metrics
            if not m:
                lines.append(f"| {r.model_name} | {r.label_name} | — | — | — | — | — | — |")
            else:
                lines.append(
                    f"| {r.model_name} | {r.label_name} | "
                    f"{m.get('ann_return', 0)*100:.2f}% | "
                    f"{m.get('ann_excess_return', 0)*100:.2f}% | "
                    f"{m.get('sharpe', 0):.2f} | "
                    f"{m.get('max_drawdown', 0)*100:.2f}% | "
                    f"{m.get('avg_turnover', 0):.3f} | "
                    f"{m.get('excess_sharpe', 0):.2f} |"
                )
        lines.append("")

        # 3. Best model summary
        best = max(self.results, key=lambda r: abs(r.val_metrics.get("icir", 0)))
        lines.append(f"## 3. Best Model: {best.model_name} + {best.label_name}")
        lines.append("")
        lines.append(f"- Validation IC: {best.val_mean_ic:.4f}")
        lines.append(f"- Validation ICIR: {best.val_metrics.get('icir', 0):.4f}")
        lines.append(f"- Signal direction: {'original' if best.oriented_direction == 1 else 'flipped'}")
        if best.backtest_metrics:
            m = best.backtest_metrics
            lines.append(f"- OOS annual return: {m.get('ann_return', 0)*100:.2f}%")
            lines.append(f"- OOS Sharpe: {m.get('sharpe', 0):.2f}")
            lines.append(f"- OOS max drawdown: {m.get('max_drawdown', 0)*100:.2f}%")
        lines.append("")

        # 4. Factor Importance (top 20 for best model)
        imp = best.feature_importance()
        if not imp.empty:
            lines.append("## 4. Top 20 Feature Importance")
            lines.append("")
            lines.append("| Rank | Feature | Importance |")
            lines.append("|------|---------|------------|")
            top20 = imp.abs().nlargest(20)
            for rank, (feat, val) in enumerate(top20.items(), 1):
                lines.append(f"| {rank} | {feat} | {val:.4f} |")
            lines.append("")

        report_path.write_text("\n".join(lines), encoding="utf-8")
        logging.info(f"Model report saved to {report_path}")
```

- [ ] **Step 2: Commit**

```bash
git add src/pipelines/model/model_pipeline.py
git commit -m "feat: add ModelPipeline with 9-stage template: load, prepare, split, train, predict, orient, backtest, alphalens, report"
```

---

### Task 8: Register pipeline + config + pyproject.toml

**Files:**
- Modify: `src/pipelines/__init__.py`
- Create: `configs/model_pipeline.yaml`
- Modify: `pyproject.toml` (add scikit-learn)

- [ ] **Step 1: Register ModelPipeline**

```python
# src/pipelines/__init__.py - add to registry
from pipelines.model.model_pipeline import ModelPipeline

PIPELINE_REGISTRY: dict[str, type[DataPipeline]] = {
    "csi1000_qlib": CSI1000QlibPipeline,
    "alpha_factor": AlphaFactorPipeline,
    "model": ModelPipeline,  # ADD THIS LINE
}
```

- [ ] **Step 2: Create model_pipeline.yaml**

```yaml
# configs/model_pipeline.yaml
pipeline:
  name: model
  stages:
    - load
    - prepare
    - split
    - train
    - predict
    - orient
    - backtest
    - alphalens
    - report

data:
  factor_pool: data/factor_pool_relaxed.parquet
  qlib_bin: ../../data/qlib_bin
  instruments: "csi1000"
  datetime_col: "datetime"
  instrument_col: "instrument"

features:
  impute: "cross_section_median"
  transform: "rank_pct"
  winsorize:
    enabled: true
    method: "quantile"
    lower: 0.01
    upper: 0.99

label:
  winsorize:
    enabled: true
    method: "cross_section_quantile"
    lower: 0.01
    upper: 0.99
  rank_bins: 5
  ranker_min_group_size: 30
  classifier:
    top_quantile: 0.8
    bottom_quantile: 0.2

split:
  purge_by_label: true
  train_start: "2020-01-01"
  train_end: "2023-12-31"
  val_start: "2024-01-01"
  val_end: "2024-06-30"
  test_start: "2024-07-01"
  test_end: null

model:
  names: ["elastic_net", "lgbm_regressor", "lgbm_ranker", "lgbm_classifier"]
  target_labels: ["label_1d", "label_5d", "label_10d", "label_20d"]
  primary_label: "label_5d"
  params:
    elastic_net:
      alpha: 0.01
      l1_ratio: 0.2
    lgbm_regressor:
      num_leaves: 31
      learning_rate: 0.05
      n_estimators: 200
      min_child_samples: 50
      feature_fraction: 0.8
      bagging_fraction: 0.8
      bagging_freq: 5
      seed: 42
    lgbm_ranker:
      num_leaves: 31
      learning_rate: 0.05
      n_estimators: 200
      min_child_samples: 50
      seed: 42
    lgbm_classifier:
      num_leaves: 31
      learning_rate: 0.05
      n_estimators: 200
      min_child_samples: 50
      seed: 42

selection:
  metric: "oriented_val_icir"

backtest:
  topk: 50
  shift_signal_days: 1
  transaction_cost_bps: 10
  benchmark: "universe_equal_weight"
  quantiles: 5

output:
  dir: data/model_results
  report: data/model_results/model_report.md
  alphalens: data/model_results/alphalens
```

- [ ] **Step 3: Add scikit-learn to pyproject.toml**

```toml
# pyproject.toml - add to dependencies
"scikit-learn>=1.4",
```

- [ ] **Step 4: Commit**

```bash
git add src/pipelines/__init__.py configs/model_pipeline.yaml pyproject.toml
git commit -m "feat: register ModelPipeline in registry, add config, add scikit-learn dependency"
```

---

### Task 9: Integration test

**Files:**
- Create: `tests/pipelines/model/test_pipeline_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/pipelines/model/test_pipeline_integration.py
"""Integration test for ModelPipeline end-to-end with mock data."""
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock

from pipelines.model.feature_prep import FeaturePreprocessor, winsorize_label_by_date_quantile
from pipelines.model.evaluator import compute_ic_by_date, orient_signal, compute_model_metrics
from pipelines.model.backtest import topk_backtest, compute_backtest_metrics
from pipelines.model.linear_model import LinearModel
from pipelines.model.lgbm_regressor import LGBMRegModel


@pytest.fixture
def integration_data():
    """Create realistic mock data for pipeline testing."""
    rng = np.random.RandomState(42)
    dates = pd.date_range("2020-01-01", periods=50, freq="B")
    symbols = [f"SH60000{i}" for i in range(1, 31)]  # 30 symbols
    index = pd.MultiIndex.from_product([dates, symbols], names=["datetime", "instrument"])

    n_feat = 8
    X = pd.DataFrame({f"f{i}": rng.randn(len(index)) for i in range(n_feat)}, index=index)
    y_1d = pd.Series(rng.randn(len(index)) * 0.02, index=index, name="label_1d")
    y_5d = pd.Series(rng.randn(len(index)) * 0.04, index=index, name="label_5d")

    close = pd.DataFrame(
        100 + np.cumsum(rng.randn(len(dates), len(symbols)) * 0.01, axis=0),
        index=dates, columns=symbols,
    )
    returns = close.pct_change()

    return X, {"label_1d": y_1d, "label_5d": y_5d}, returns, close


def test_model_train_predict_e2e(integration_data):
    """Test: preprocess → train → predict → evaluate for one model."""
    X, labels, returns, close = integration_data

    # Preprocess
    prep = FeaturePreprocessor(impute="cross_section_median", transform="rank_pct")
    X_clean = prep.transform(X)

    # Train/val split
    split_idx = len(X_clean) // 2
    X_train, X_val = X_clean.iloc[:split_idx], X_clean.iloc[split_idx:]
    y_train, y_val = labels["label_1d"].iloc[:split_idx], labels["label_1d"].iloc[split_idx:]

    # Train
    model = LinearModel(alpha=0.01, l1_ratio=0.2)
    model.fit(X_train, y_train)

    # Predict
    train_pred = model.predict(X_train)
    val_pred = model.predict(X_val)

    # Evaluate
    metrics = compute_model_metrics(train_pred, y_train, val_pred, y_val)
    assert "train" in metrics
    assert "val" in metrics
    assert "ic_mean" in metrics["train"]


def test_backtest_e2e(integration_data):
    """Test: signals → backtest with lag and cost."""
    X, labels, returns, close = integration_data

    signals = pd.DataFrame(
        np.random.randn(*returns.shape),
        index=returns.index, columns=returns.columns,
    )

    port_ret, excess, turnover, weights = topk_backtest(
        returns, signals, topk=5, transaction_cost_bps=10, shift_signal_days=1,
    )

    assert len(port_ret) == len(returns)
    assert (turnover >= 0).all()
    # First row should be NaN due to lag
    assert port_ret.iloc[0] != port_ret.iloc[0]  # NaN check


def test_orient_and_metrics_e2e(integration_data):
    """Test direction correction + backtest metrics."""
    _, labels, returns, _ = integration_data

    # Create a deliberately negative signal
    y = labels["label_1d"]
    neg_pred = -y * 0.5  # Inverse signal

    ic = compute_ic_by_date(neg_pred, y)
    metrics = {"ic_mean": ic.mean(), "icir": ic.mean() / ic.std() if ic.std() > 0 else 0}

    oriented, direction = orient_signal(metrics["ic_mean"], neg_pred)
    assert direction == -1  # Should flip

    # Verify flipped signal has positive IC
    flipped_ic = compute_ic_by_date(oriented, y)
    assert flipped_ic.mean() > 0
```

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest tests/pipelines/model/test_pipeline_integration.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/pipelines/model/test_pipeline_integration.py
git commit -m "test: add integration tests for model train/predict/backtest/orient pipeline"
```

---

### Task 10: Final run + smoke test

**Files:** None new — verify full pipeline runs with config.

- [ ] **Step 1: Run full pipeline with single model for smoke test**

```bash
# Quick smoke test with just elastic_net and label_5d
uv run python scripts/run_pipeline.py --config configs/model_pipeline.yaml --stages load,prepare,split,train,predict,orient,backtest,alphalens,report 2>&1 | tail -30
```

- [ ] **Step 2: Verify outputs**

```bash
ls -la data/model_results/
ls -la data/model_results/alphalens/
cat data/model_results/model_report.md
```

- [ ] **Step 3: Commit any fixes**

```bash
git add -A && git commit -m "fix: resolve smoke test issues"
```

---

## Self-Review

**Spec coverage check:**

| Spec Section | Task |
|---|---|
| 9-stage pipeline stages | Task 7 (ModelPipeline) |
| Feature preprocessing (rank_pct, winsorize, impute) | Task 2 |
| Label winsorize (cross-section) | Task 2 |
| Rank label for LGBMRanker | Task 2, Task 4 |
| Binary label for LGBMClassifier | Task 2, Task 4 |
| Time split with purge | Task 7 (_subtract_trading_days) |
| 4 models: ElasticNet, LGBMReg, LGBMRank, LGBMClass | Task 4 |
| Direction correction | Task 3, Task 7 |
| TrainingResult dataclass | Task 7 |
| Backtest with lag, cost, turnover, benchmark | Task 5 |
| Alphalens using model predictions | Task 6 |
| Markdown report with 4 tables | Task 7 (generate_report) |
| Config file | Task 8 |
| Pipeline registration | Task 8 |

**No placeholders found.** All steps contain actual code.

**Type consistency checked:** `TrainingResult` fields match between Task 7 definition and usage. `BaseModel.fit()` signature consistent across Task 4. `get_model()` factory returns `BaseModel` in Task 1 and used in Task 7.

---

Plan complete and saved to `docs/superpowers/plans/2026-04-25-model-pipeline.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
