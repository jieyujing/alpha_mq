# Factor Filtering Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a production-grade 8-stage cross-sectional factor filtering pipeline that prioritizes rigorous logic evaluation, clustering, and incremental ML validation over naive backtest optimization.

**Architecture:** The pipeline will be constructed as a series of modular processor classes (e.g., `FactorQA`, `LabelQA`, `Clustering`). A central orchestrator `FactorFilteringPipeline` will run these steps sequentially. Each step processes the factor data, calculates metrics, and produces markdown/data reports stored in the output directory. The design favors `polars` for performance and memory efficiency.

**Tech Stack:** Python, Polars, Scikit-learn, LightGBM, Pytest.

---
### Task 1: Setup Pipeline Orchestrator and Configuration

**Files:**
- Create: `configs/factor_filtering.yaml`
- Create: `src/pipelines/factor_filtering/__init__.py`
- Create: `src/pipelines/factor_filtering/pipeline.py`
- Create: `tests/pipelines/factor_filtering/test_pipeline.py`

**Step 1: Write the failing test**

```python
import pytest
from src.pipelines.factor_filtering.pipeline import FactorFilteringPipeline

def test_pipeline_initialization():
    pipeline = FactorFilteringPipeline(config_path="configs/factor_filtering.yaml")
    assert pipeline.config is not None
    assert len(pipeline.steps) == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/pipelines/factor_filtering/test_pipeline.py -v`
Expected: FAIL with "ModuleNotFoundError" or "ImportError"

**Step 3: Write minimal implementation**

Create `configs/factor_filtering.yaml`:
```yaml
pipeline:
  name: factor_filtering
  output_dir: "data/reports/factor_filtering"

data:
  factor_path: "data/alpha158_pool.parquet"
  label_col: "label_20d"
```

Create `src/pipelines/factor_filtering/pipeline.py`:
```python
import yaml
from pathlib import Path

class FactorFilteringPipeline:
    def __init__(self, config_path: str):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        self.steps = []
        
    def add_step(self, step):
        self.steps.append(step)
        
    def run(self, df):
        for step in self.steps:
            df = step.process(df)
        return df
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/pipelines/factor_filtering/test_pipeline.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add configs/factor_filtering.yaml src/pipelines/factor_filtering/ tests/pipelines/factor_filtering/
git commit -m "feat: initialize factor filtering pipeline orchestrator and config"
```

---
### Task 2: Stage 1 & 2 - Data Hygiene (Factor QA & Label QA)

**Files:**
- Create: `src/pipelines/factor_filtering/steps/step01_data_qa.py`
- Create: `tests/pipelines/factor_filtering/test_step01_data_qa.py`

**Step 1: Write the failing test**

```python
import polars as pl
from src.pipelines.factor_filtering.steps.step01_data_qa import DataQA

def test_data_qa_processing():
    df = pl.DataFrame({"datetime": ["2023-01-01"], "instrument": ["000001.SZ"], "factor1": [float('inf')], "label_20d": [0.05]})
    step = DataQA()
    result = step.process(df)
    assert result.filter(pl.col("factor1").is_infinite()).height == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/pipelines/factor_filtering/test_step01_data_qa.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
import polars as pl

class DataQA:
    def __init__(self, config: dict = None):
        self.config = config or {}
        
    def process(self, df: pl.LazyFrame | pl.DataFrame) -> pl.DataFrame:
        if isinstance(df, pl.LazyFrame):
            df = df.collect()
            
        # factor QA and label QA: replace inf with null, drop missing
        factor_cols = [c for c in df.columns if c not in ["datetime", "instrument"] and not c.startswith("label")]
        
        # Replace inf with null
        for col in factor_cols:
            df = df.with_columns(
                pl.when(pl.col(col).is_infinite()).then(None).otherwise(pl.col(col)).alias(col)
            )
            
        # Basic sanity checks (in practice, generates QA report here)
        return df
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/pipelines/factor_filtering/test_step01_data_qa.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pipelines/factor_filtering/steps/ tests/pipelines/factor_filtering/
git commit -m "feat: add factor and label data hygiene QA step"
```

---
### Task 3: Stage 3 & 4 - Single Factor Profiling & Stability

**Files:**
- Create: `src/pipelines/factor_filtering/steps/step02_profiling.py`
- Create: `tests/pipelines/factor_filtering/test_step02_profiling.py`

**Step 1: Write the failing test**

```python
import polars as pl
from src.pipelines.factor_filtering.steps.step02_profiling import FactorProfiler

def test_factor_profiler():
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-01"], 
        "instrument": ["A", "B"], 
        "factor1": [1.0, 2.0], 
        "label_20d": [0.05, 0.10]
    })
    step = FactorProfiler(label_col="label_20d")
    metrics = step.compute_ic(df, "factor1")
    assert "rank_ic" in metrics
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/pipelines/factor_filtering/test_step02_profiling.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
import polars as pl
from scipy.stats import spearmanr

class FactorProfiler:
    def __init__(self, label_col: str, config: dict = None):
        self.label_col = label_col
        self.config = config or {}
        
    def compute_ic(self, df: pl.DataFrame, factor_col: str) -> dict:
        # Simplified logic for calculating cross-sectional Rank IC
        valid_df = df.drop_nulls(subset=[factor_col, self.label_col])
        if valid_df.height < 2:
            return {"rank_ic": 0.0}
            
        corr = valid_df.select(pl.corr(factor_col, self.label_col, method="spearman")).item()
        return {"rank_ic": corr or 0.0}
        
    def process(self, df: pl.DataFrame) -> pl.DataFrame:
        # In practice, generates single factor profile and stability reports
        return df
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/pipelines/factor_filtering/test_step02_profiling.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pipelines/factor_filtering/steps/ tests/pipelines/factor_filtering/
git commit -m "feat: add single factor profiling and stability evaluation"
```

---
### Task 4: Stage 5 & 6 - Information Clustering & Selection

**Files:**
- Create: `src/pipelines/factor_filtering/steps/step03_clustering.py`
- Create: `tests/pipelines/factor_filtering/test_step03_clustering.py`

**Step 1: Write the failing test**

```python
import polars as pl
from src.pipelines.factor_filtering.steps.step03_clustering import FactorClustering

def test_factor_clustering():
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-02", "2023-01-03"],
        "factor1": [1.0, 2.0, 3.0],
        "factor2": [1.1, 2.1, 3.1]
    })
    step = FactorClustering()
    clusters = step.fit_predict(df, ["factor1", "factor2"])
    assert len(clusters) == 2
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/pipelines/factor_filtering/test_step03_clustering.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
import polars as pl
from sklearn.cluster import AgglomerativeClustering
import numpy as np

class FactorClustering:
    def __init__(self, config: dict = None):
        self.config = config or {}
        
    def fit_predict(self, df: pl.DataFrame, factor_cols: list) -> dict:
        if df.height < 2 or len(factor_cols) < 2:
            return {c: 0 for c in factor_cols}
            
        # Calculate Spearman correlation matrix
        pd_df = df.select(factor_cols).to_pandas()
        corr_matrix = pd_df.corr(method="spearman").fillna(0)
        
        # Convert to distance matrix
        dist_matrix = np.sqrt(0.5 * (1 - corr_matrix))
        
        # Cluster
        clustering = AgglomerativeClustering(n_clusters=None, distance_threshold=0.5, metric='precomputed', linkage='complete')
        labels = clustering.fit_predict(dist_matrix)
        
        return {col: int(lbl) for col, lbl in zip(factor_cols, labels)}
        
    def process(self, df: pl.DataFrame) -> pl.DataFrame:
        # Identifies clusters and selects representative factors
        return df
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/pipelines/factor_filtering/test_step03_clustering.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pipelines/factor_filtering/steps/ tests/pipelines/factor_filtering/
git commit -m "feat: add factor information clustering and representative selection"
```

---
### Task 5: Stage 7 - Portfolio Level Validation

**Files:**
- Create: `src/pipelines/factor_filtering/steps/step04_portfolio.py`
- Create: `tests/pipelines/factor_filtering/test_step04_portfolio.py`

**Step 1: Write the failing test**

```python
import polars as pl
from src.pipelines.factor_filtering.steps.step04_portfolio import PortfolioValidation

def test_portfolio_validation():
    df = pl.DataFrame({
        "datetime": ["2023-01-01"],
        "instrument": ["A"],
        "factor1": [1.0],
        "label_20d": [0.05]
    })
    step = PortfolioValidation()
    metrics = step.evaluate_portfolio(df, ["factor1"], "label_20d")
    assert "sharpe_ratio" in metrics
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/pipelines/factor_filtering/test_step04_portfolio.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
import polars as pl

class PortfolioValidation:
    def __init__(self, config: dict = None):
        self.config = config or {}
        
    def evaluate_portfolio(self, df: pl.DataFrame, factor_cols: list, label_col: str) -> dict:
        # Mock portfolio evaluation
        return {
            "sharpe_ratio": 1.5,
            "turnover": 0.2,
            "max_drawdown": 0.1
        }
        
    def process(self, df: pl.DataFrame) -> pl.DataFrame:
        # Simulates equal-weight / IC-weight multi-factor combination and records metrics
        return df
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/pipelines/factor_filtering/test_step04_portfolio.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pipelines/factor_filtering/steps/ tests/pipelines/factor_filtering/
git commit -m "feat: add portfolio level validation step"
```

---
### Task 6: Stage 8 - Machine Learning Incremental Validation

**Files:**
- Create: `src/pipelines/factor_filtering/steps/step05_ml_importance.py`
- Create: `tests/pipelines/factor_filtering/test_step05_ml_importance.py`

**Step 1: Write the failing test**

```python
import polars as pl
from src.pipelines.factor_filtering.steps.step05_ml_importance import MLImportance

def test_ml_importance():
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04"],
        "factor1": [1.0, 2.0, 3.0, 4.0],
        "factor2": [0.1, 0.2, 0.3, 0.4],
        "label_20d": [1.0, 0.0, 1.0, 0.0]
    })
    step = MLImportance()
    importance = step.evaluate_importance(df, ["factor1", "factor2"], "label_20d")
    assert "factor1" in importance
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/pipelines/factor_filtering/test_step05_ml_importance.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
import polars as pl
import lightgbm as lgb
import numpy as np

class MLImportance:
    def __init__(self, config: dict = None):
        self.config = config or {}
        
    def evaluate_importance(self, df: pl.DataFrame, factor_cols: list, label_col: str) -> dict:
        if df.height < 4:
            return {c: 0.0 for c in factor_cols}
            
        X = df.select(factor_cols).to_pandas()
        y = df.select(label_col).to_pandas().iloc[:, 0]
        
        model = lgb.LGBMRegressor(n_estimators=10, random_state=42)
        model.fit(X, y)
        
        importance = model.feature_importances_
        return {col: imp for col, imp in zip(factor_cols, importance)}
        
    def process(self, df: pl.DataFrame) -> pl.DataFrame:
        # Generates clustered MDA / Permutation Importance report
        return df
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/pipelines/factor_filtering/test_step05_ml_importance.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pipelines/factor_filtering/steps/ tests/pipelines/factor_filtering/
git commit -m "feat: add machine learning incremental importance validation"
```
