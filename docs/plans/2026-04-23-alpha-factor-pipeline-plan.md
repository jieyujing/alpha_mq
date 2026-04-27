# Alpha158 Factor Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an independent pipeline that computes Alpha158 factors via Qlib, calculates multi-period return labels (5D primary), filters them through a configurable responsibility chain, exports a final candidate factor pool as Parquet + YAML, and generates a comprehensive factor quality report.

**Architecture:** New `AlphaFactorPipeline` class inheriting `DataPipeline` (Template Method). Stages: `ingest_bin` → `factor_compute` → `label_compute` → `filter` → `export` → `report`. The base class `run()` method is refactored to support dynamic stage names via a `STAGE_METHOD_MAP` class attribute.

**Tech Stack:** Python 3.12+, pyqlib 0.9.7, pandas 3.0, PyYAML, pytest.

---

### Task 1: Move filter.txt to proper location and refactor base class

**Files:**
- Move: `filter.txt` → `src/pipelines/factor/filter_chain.py`
- Create: `src/pipelines/factor/__init__.py`
- Modify: `src/pipelines/base.py` — refactor `run()` for dynamic stage dispatch
- Modify: `tests/pipelines/test_base.py` — add test for dynamic stages

**Context:** Currently `filter.txt` is an untracked Python file at the project root. The `DataPipeline.run()` method hardcodes stage names ("download", "validate", "clean", "ingest"), preventing new pipelines from using different stage names. We refactor to dynamic dispatch via `STAGE_METHOD_MAP`.

**Step 1: Create the factor package and move filter code**

```bash
mkdir -p src/pipelines/factor
mkdir -p tests/pipelines/factor
touch src/pipelines/factor/__init__.py
mv filter.txt src/pipelines/factor/filter_chain.py
```

Create `src/pipelines/factor/__init__.py`:
```python
"""因子计算与过滤 Pipeline 子包"""
```

**Step 2: Refactor DataPipeline.run() for dynamic stage dispatch**

The current `run()` hardcodes stage names. Replace with dynamic dispatch:

```python
# src/pipelines/base.py
from abc import ABC, abstractmethod


class DataPipeline(ABC):
    # Subclasses override this to define their own stages and method mapping
    STAGE_METHOD_MAP: dict[str, str] = {
        "download": "download",
        "validate": "validate",
        "clean": "clean",
        "ingest": "ingest_to_qlib",
    }

    def __init__(self, config: dict):
        self.config = config
        self.stages = config["pipeline"]["stages"]
        self._completed = False

    def run(self) -> None:
        self.setup()
        try:
            for stage in self.stages:
                method_name = self.STAGE_METHOD_MAP.get(stage)
                if method_name is None:
                    raise ValueError(f"Unknown stage: {stage}. Map: {self.STAGE_METHOD_MAP}")
                method = getattr(self, method_name)
                result = method()
                # validate stage returns a list of errors; check if non-empty
                if stage == "validate" and result:
                    fail_on_error = self.config.get("pipeline", {}).get("validate", {}).get("fail_on_error", False)
                    if fail_on_error:
                        raise RuntimeError(f"Validation failed: {result}")
            self._completed = True
            self.on_success()
        finally:
            self.teardown()

    def setup(self):
        pass

    def teardown(self):
        """资源清理（无论成功或失败都会执行）"""
        pass

    def on_success(self):
        """成功完成后的回调（只有所有 stage 成功完成才执行）"""
        pass

    @abstractmethod
    def download(self):
        ...

    @abstractmethod
    def validate(self):
        ...

    @abstractmethod
    def clean(self):
        ...

    @abstractmethod
    def ingest_to_qlib(self):
        ...
```

**Step 3: Update existing test and add dynamic stage test**

Replace `tests/pipelines/test_base.py` with:

```python
import pytest
from pipelines.base import DataPipeline


class MockPipeline(DataPipeline):
    def __init__(self, config):
        super().__init__(config)
        self.called = []

    def download(self):
        self.called.append("download")

    def validate(self):
        return []

    def clean(self):
        self.called.append("clean")

    def ingest_to_qlib(self):
        self.called.append("ingest")


def test_pipeline_flow():
    config = {"pipeline": {"name": "Mock", "stages": ["download", "clean"]}}
    pipeline = MockPipeline(config)
    pipeline.run()
    assert pipeline.called == ["download", "clean"]


class MockFactorPipeline(DataPipeline):
    """Mock pipeline with custom stages to test dynamic dispatch."""
    STAGE_METHOD_MAP = {
        "ingest_bin": "ingest_bin",
        "factor_compute": "factor_compute",
        "export": "export",
    }

    def __init__(self, config):
        super().__init__(config)
        self.called = []

    def download(self): ...
    def validate(self): return []
    def clean(self): ...
    def ingest_to_qlib(self): ...

    def ingest_bin(self):
        self.called.append("ingest_bin")

    def factor_compute(self):
        self.called.append("factor_compute")

    def export(self):
        self.called.append("export")


def test_custom_stage_dispatch():
    config = {"pipeline": {"name": "MockFactor", "stages": ["ingest_bin", "factor_compute"]}}
    pipeline = MockFactorPipeline(config)
    pipeline.run()
    assert pipeline.called == ["ingest_bin", "factor_compute"]


def test_custom_stage_all():
    config = {"pipeline": {"name": "MockFactor", "stages": ["ingest_bin", "factor_compute", "export"]}}
    pipeline = MockFactorPipeline(config)
    pipeline.run()
    assert pipeline.called == ["ingest_bin", "factor_compute", "export"]
```

**Step 4: Run tests to verify all pass**

Run: `uv run pytest tests/pipelines/test_base.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add src/pipelines/factor/__init__.py src/pipelines/factor/filter_chain.py src/pipelines/base.py tests/pipelines/test_base.py
git commit -m "refactor: support dynamic stage dispatch in DataPipeline, move filter.txt to factor package"
```

---

### Task 2: Implement FactorLoader

**Files:**
- Create: `src/pipelines/factor/factor_loader.py`
- Create: `tests/pipelines/factor/test_factor_loader.py`

**Context:** FactorLoader wraps Qlib's Alpha158 handler to load factors. It initializes Qlib, creates the Alpha158 handler, and returns a MultiIndex DataFrame. Extra fields (valuation, market cap) are loaded separately and merged.

**Step 1: Write the failing test**

```python
# tests/pipelines/factor/test_factor_loader.py
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock
from pipelines.factor.factor_loader import FactorLoader


@pytest.fixture
def loader():
    return FactorLoader(qlib_bin_path="data/qlib_bin")


def make_mock_index(n=10):
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.MultiIndex.from_product(
        [dates, ["SH600000"]], names=["datetime", "instrument"]
    )


def test_load_alpha158_returns_dataframe(loader):
    """Alpha158 handler should return a MultiIndex DataFrame with factors."""
    idx = make_mock_index()
    mock_data = pd.DataFrame({
        "KMID": np.random.randn(len(idx)),
        "KLEN": np.random.randn(len(idx)),
    }, index=idx)

    mock_handler = MagicMock()
    mock_handler.fetch.return_value = mock_data

    with patch("pipelines.factor.factor_loader.qlib") as mock_qlib:
        with patch("pipelines.factor.factor_loader.Alpha158", return_value=mock_handler):
            df = loader.load_alpha158(
                instruments="csi1000",
                start="2020-01-01",
                end="2020-12-31",
            )

    assert isinstance(df, pd.DataFrame)
    assert isinstance(df.index, pd.MultiIndex)
    assert "KMID" in df.columns
    assert "KLEN" in df.columns
    mock_qlib.init.assert_called_once()


def test_load_with_extra_fields(loader):
    """Extra fields should be appended to Alpha158 factors."""
    idx = make_mock_index()
    mock_alpha = pd.DataFrame({"f0": np.ones(len(idx))}, index=idx)
    mock_extra = pd.DataFrame({"pe_ttm": np.full(len(idx), 10.0)}, index=idx)

    mock_handler = MagicMock()
    mock_handler.fetch.return_value = mock_alpha

    with patch("pipelines.factor.factor_loader.qlib") as mock_qlib:
        with patch("pipelines.factor.factor_loader.Alpha158", return_value=mock_handler):
            with patch("pipelines.factor.factor_loader.DFeatureLoader") as mock_dloader:
                mock_dloader.return_value.load.return_value = mock_extra

                df = loader.load_alpha158(
                    instruments="csi1000",
                    start="2020-01-01",
                    end="2020-12-31",
                    extra_fields=["pe_ttm"],
                )

    assert "f0" in df.columns
    assert "pe_ttm" in df.columns
    assert df.shape[1] == 2
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/pipelines/factor/test_factor_loader.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'pipelines.factor.factor_loader'"

**Step 3: Write minimal implementation**

```python
# src/pipelines/factor/factor_loader.py
"""加载 Qlib Alpha158 因子及额外特征。"""
import logging
import pandas as pd
from typing import Optional, List

import qlib
from qlib.contrib.data.handler import Alpha158


class DFeatureLoader:
    """从 Qlib 数据加载额外特征（非 Alpha158 特征）。"""

    def __init__(self, fields: List[str], qlib_bin_path: str, instruments: str,
                 start: str, end: str):
        self.fields = fields
        self.qlib_bin_path = qlib_bin_path
        self.instruments = instruments
        self.start = start
        self.end = end

    def load(self) -> pd.DataFrame:
        """从 Qlib 加载指定字段。"""
        from qlib.data import D
        df = D.features(self.instruments, self.fields,
                        start_time=self.start, end_time=self.end)
        return df


class FactorLoader:
    """加载 Qlib Alpha158 因子。"""

    def __init__(self, qlib_bin_path: str, provider_uri: Optional[str] = None):
        self.qlib_bin_path = qlib_bin_path
        self.provider_uri = provider_uri or qlib_bin_path

    def load_alpha158(
        self,
        instruments: str,
        start: str,
        end: str,
        extra_fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        qlib.init() → Alpha158 handler → fetch DataFrame.

        如果指定 extra_fields，额外加载这些字段并合并到结果中。
        """
        qlib.init(provider_uri=self.provider_uri)

        handler = Alpha158(
            instruments=instruments,
            start_time=start,
            end_time=end,
        )
        df = handler.fetch()
        logging.info(f"Loaded Alpha158 factors: {df.shape[1]} features, {len(df)} rows")

        # 加载额外特征
        if extra_fields:
            extra_loader = DFeatureLoader(
                fields=extra_fields,
                qlib_bin_path=self.qlib_bin_path,
                instruments=instruments,
                start=start,
                end=end,
            )
            extra_df = extra_loader.load()
            # 合并
            common_index = df.index.intersection(extra_df.index)
            df = df.loc[common_index]
            extra_df = extra_df.loc[common_index]
            for col in extra_df.columns:
                df[col] = extra_df[col]
            logging.info(f"Added {len(extra_fields)} extra fields. Total features: {df.shape[1]}")

        return df
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/pipelines/factor/test_factor_loader.py -v`
Expected: All 2 tests PASS

**Step 5: Commit**

```bash
git add src/pipelines/factor/factor_loader.py tests/pipelines/factor/test_factor_loader.py
git commit -m "feat: implement FactorLoader for Qlib Alpha158 factor loading"
```

---

### Task 3: Implement LabelBuilder

**Files:**
- Create: `src/pipelines/factor/label_builder.py`
- Create: `tests/pipelines/factor/test_label_builder.py`

**Context:** LabelBuilder computes multi-period forward returns (1D, 5D, 10D, 20D) from close prices loaded via Qlib. Uses pandas groupby to avoid cross-symbol shifts.

**Step 1: Write the failing test**

```python
# tests/pipelines/factor/test_label_builder.py
import pytest
import numpy as np
import pandas as pd
from pipelines.factor.label_builder import LabelBuilder


@pytest.fixture
def builder():
    return LabelBuilder(qlib_bin_path="data/qlib_bin")


def make_mock_close(n=10):
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    index = pd.MultiIndex.from_product(
        [dates, ["SH600000"]], names=["datetime", "instrument"]
    )
    return pd.DataFrame({"close": [100.0 + i for i in range(n)]}, index=index)


def test_compute_labels_returns_dict(builder):
    """Should return a dict of label Series keyed by label name."""
    close_data = make_mock_close()
    labels = builder.compute_labels(close_data, periods=[1, 5])
    assert "label_1d" in labels
    assert "label_5d" in labels
    assert isinstance(labels["label_1d"], pd.Series)
    assert len(labels["label_1d"]) == len(close_data)


def test_label_1d_values(builder):
    """1D label = close(t+1) / close(t) - 1."""
    close_data = pd.DataFrame({
        "close": [100.0, 105.0, 110.0],
    }, index=pd.MultiIndex.from_tuples([
        ("2020-01-01", "SH600000"),
        ("2020-01-02", "SH600000"),
        ("2020-01-03", "SH600000"),
    ], names=["datetime", "instrument"]))

    labels = builder.compute_labels(close_data, periods=[1])
    label_1d = labels["label_1d"].values
    # 100→105 = 5%, 105→110 ≈ 4.76%, last = NaN
    assert abs(label_1d[0] - 0.05) < 1e-6
    assert abs(label_1d[1] - (110.0 / 105.0 - 1)) < 1e-6
    assert np.isnan(label_1d[2])
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/pipelines/factor/test_label_builder.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/pipelines/factor/label_builder.py
"""构建多周期收益率标签。"""
import logging
import pandas as pd
from typing import List, Dict


class LabelBuilder:
    """基于 pandas 构建多周期 forward return 标签。"""

    def __init__(self, qlib_bin_path: str):
        self.qlib_bin_path = qlib_bin_path

    def compute_labels(
        self,
        close_data: pd.DataFrame,
        periods: List[int] = [1, 5, 10, 20],
    ) -> Dict[str, pd.Series]:
        """
        对每个 period N: label_Nd = close(t+N) / close(t) - 1

        close_data: DataFrame with MultiIndex(datetime, instrument) and 'close' column.
        返回 {"label_1d": Series, "label_5d": Series, ...}
        """
        labels = {}
        for period in periods:
            label_name = f"label_{period}d"
            shifted = close_data.groupby(level="instrument")["close"].shift(-period)
            labels[label_name] = shifted / close_data["close"] - 1
            logging.info(f"Computed {label_name}: {labels[label_name].notna().sum()} valid values")
        return labels

    def load_close_prices(
        self,
        instruments: str,
        start: str,
        end: str,
        buffer_days: int = 30,
    ) -> pd.DataFrame:
        """
        从 Qlib 加载 close 价格，带前后缓冲（用于 forward return 计算）。

        buffer_days: 向后多加载的天数，确保未来 N 日 return 不全部为 NaN。
        """
        from datetime import datetime, timedelta
        from qlib.data import D

        extended_end = (datetime.strptime(end, "%Y-%m-%d")
                        + timedelta(days=buffer_days)).strftime("%Y-%m-%d")
        close_df = D.features(instruments, ["$close"],
                              start_time=start, end_time=extended_end)
        close_df.columns = ["close"]
        logging.info(f"Loaded close prices: {len(close_df)} rows, range {start} to {extended_end}")
        return close_df
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/pipelines/factor/test_label_builder.py -v`
Expected: All 2 tests PASS

**Step 5: Commit**

```bash
git add src/pipelines/factor/label_builder.py tests/pipelines/factor/test_label_builder.py
git commit -m "feat: implement LabelBuilder for multi-period return computation"
```

---

### Task 4: Implement AlphaFactorPipeline

**Files:**
- Create: `src/pipelines/factor/alpha_pipeline.py`
- Create: `tests/pipelines/factor/test_alpha_pipeline.py`

**Context:** The main Pipeline class orchestrating all stages. Inherits `DataPipeline` with custom `STAGE_METHOD_MAP`.

**Step 1: Write the failing test**

```python
# tests/pipelines/factor/test_alpha_pipeline.py
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock
from pipelines.factor.alpha_pipeline import AlphaFactorPipeline


@pytest.fixture
def config():
    return {
        "pipeline": {
            "name": "AlphaFactorPipeline",
            "stages": ["ingest_bin", "factor_compute", "label_compute", "filter", "export"],
        },
        "data": {
            "qlib_csv": "data/qlib_output/ohlcv",
            "qlib_bin": "data/qlib_bin",
            "instruments": "csi1000",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
        },
        "labels": {
            "primary": "label_5d",
            "periods": [1, 5, 10, 20],
        },
        "filter": {
            "drop_missing_label": {},
            "drop_high_missing": {"threshold": 0.3},
            "drop_high_inf": {"threshold": 0.01},
            "drop_low_variance": {
                "variance_threshold": 1e-8,
                "unique_ratio_threshold": 0.01,
            },
            "factor_quality": {
                "min_abs_ic_mean": 0.005,
                "min_abs_icir": 0.1,
                "min_abs_monotonicity": 0.05,
                "max_sign_flip_ratio": 0.45,
            },
        },
        "output": {
            "parquet": "data/factor_pool.parquet",
            "yaml": "configs/factor_pool.yaml",
            "report": "data/quality/factor_report.md",
        },
    }


def test_pipeline_initialization(config):
    """Pipeline should initialize with correct config."""
    pipeline = AlphaFactorPipeline(config)
    assert pipeline.stages == config["pipeline"]["stages"]
    assert pipeline.qlib_csv == "data/qlib_output/ohlcv"
    assert pipeline.qlib_bin == "data/qlib_bin"


def test_stage_method_map(config):
    """Pipeline should have correct stage mapping."""
    expected_map = {
        "ingest_bin": "ingest_bin",
        "factor_compute": "factor_compute",
        "label_compute": "label_compute",
        "filter": "run_filter",
        "export": "export",
        "report": "generate_report",
    }
    assert AlphaFactorPipeline.STAGE_METHOD_MAP == expected_map
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/pipelines/factor/test_alpha_pipeline.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/pipelines/factor/alpha_pipeline.py
"""Alpha158 因子计算与过滤 Pipeline。"""
import logging
import yaml
from pathlib import Path
from typing import Optional

import pandas as pd

from pipelines.base import DataPipeline
from pipelines.data_ingest.qlib_converter import QlibIngestor
from pipelines.factor.factor_loader import FactorLoader
from pipelines.factor.label_builder import LabelBuilder
from pipelines.factor.factor_report import FactorQualityReporter
from pipelines.factor.filter_chain import (
    FilterContext,
    DropMissingLabelStep,
    DropHighMissingFeatureStep,
    DropHighInfFeatureStep,
    DropLowVarianceFeatureStep,
    FactorQualityFilterStep,
)


class AlphaFactorPipeline(DataPipeline):
    """
    独立因子计算与过滤 Pipeline。

    Stages:
    - ingest_bin: CSV → Qlib binary
    - factor_compute: Alpha158 + extra features
    - label_compute: multi-period forward returns
    - filter: responsibility chain filtering
    - export: save Parquet + YAML
    - report: generate factor quality report
    """

    STAGE_METHOD_MAP = {
        "ingest_bin": "ingest_bin",
        "factor_compute": "factor_compute",
        "label_compute": "label_compute",
        "filter": "run_filter",
        "export": "export",
        "report": "generate_report",
    }

    # Abstract methods from base (required but not used)
    def download(self): ...
    def validate(self): return []
    def clean(self): ...
    def ingest_to_qlib(self): ...

    def __init__(self, config: dict):
        super().__init__(config)
        data_cfg = config.get("data", {})
        self.qlib_csv = data_cfg.get("qlib_csv", "data/qlib_output/ohlcv")
        self.qlib_bin = data_cfg.get("qlib_bin", "data/qlib_bin")
        self.instruments = data_cfg.get("instruments", "csi1000")
        self.start_date = data_cfg.get("start_date", "2020-01-01")
        self.end_date = data_cfg.get("end_date")

        # Runtime state
        self.factors_df: Optional[pd.DataFrame] = None
        self.labels_dict: Optional[dict] = None
        self.filtered_X: Optional[pd.DataFrame] = None
        self.filtered_y: Optional[pd.Series] = None
        self.filter_artifacts: Optional[dict] = None

    # ── Stage: ingest_bin ──────────────────────────────────────────────

    def ingest_bin(self):
        """调用 QlibIngestor.dump_bin() 将 CSV 转为 Qlib binary。"""
        ingestor = QlibIngestor(qlib_dir=self.qlib_bin)
        success = ingestor.dump_bin(csv_path=self.qlib_csv)
        if not success:
            raise RuntimeError("dump_bin failed — cannot proceed without Qlib binary data")
        logging.info(f"Qlib binary data written to {self.qlib_bin}")

    # ── Stage: factor_compute ──────────────────────────────────────────

    def factor_compute(self):
        """Alpha158 handler → DataFrame。"""
        loader = FactorLoader(qlib_bin_path=self.qlib_bin)
        extra_fields = self.config.get("data", {}).get("extra_fields", None)
        self.factors_df = loader.load_alpha158(
            instruments=self.instruments,
            start=self.start_date,
            end=self.end_date,
            extra_fields=extra_fields,
        )
        logging.info(f"Factor compute done: {self.factors_df.shape}")

    # ── Stage: label_compute ───────────────────────────────────────────

    def label_compute(self):
        """计算多周期 forward return 标签。"""
        periods = self.config.get("labels", {}).get("periods", [1, 5, 10, 20])

        label_builder = LabelBuilder(qlib_bin_path=self.qlib_bin)
        close_df = label_builder.load_close_prices(
            instruments=self.instruments,
            start=self.start_date,
            end=self.end_date,
        )

        self.labels_dict = label_builder.compute_labels(close_df, periods=periods)
        logging.info(f"Labels computed: {list(self.labels_dict.keys())}")

    # ── Stage: filter ──────────────────────────────────────────────────

    def run_filter(self):
        """构建 FilterContext → 执行责任链。"""
        filter_cfg = self.config.get("filter", {})
        primary_label = self.config.get("labels", {}).get("primary", "label_5d")

        primary_y = self.labels_dict[primary_label]

        # 对齐 factors 和 labels
        common_index = self.factors_df.index.intersection(primary_y.index)
        X = self.factors_df.loc[common_index].copy()
        y = primary_y.loc[common_index].copy()

        ctx = FilterContext(X=X, y=y)

        chain = self._build_filter_chain(filter_cfg)
        ctx = chain.handle(ctx)

        self.filtered_X = ctx.X
        self.filtered_y = ctx.y
        self.filter_artifacts = ctx.artifacts

        logging.info(f"Filter done: {ctx.n_rows} rows, {ctx.n_features} features remaining")
        logging.info(f"Filter log:\n" + "\n".join(ctx.logs))

    def _build_filter_chain(self, cfg: dict):
        """从配置构建责任链。"""
        steps = []

        if "drop_missing_label" in cfg:
            steps.append(DropMissingLabelStep())

        if "drop_high_missing" in cfg:
            c = cfg["drop_high_missing"]
            steps.append(DropHighMissingFeatureStep(threshold=c.get("threshold", 0.3)))

        if "drop_high_inf" in cfg:
            c = cfg["drop_high_inf"]
            steps.append(DropHighInfFeatureStep(threshold=c.get("threshold", 0.01)))

        if "drop_low_variance" in cfg:
            c = cfg["drop_low_variance"]
            steps.append(DropLowVarianceFeatureStep(
                variance_threshold=c.get("variance_threshold", 1e-8),
                unique_ratio_threshold=c.get("unique_ratio_threshold", 0.01),
            ))

        if "factor_quality" in cfg:
            c = cfg["factor_quality"]
            steps.append(FactorQualityFilterStep(
                min_abs_ic_mean=c.get("min_abs_ic_mean", 0.005),
                min_abs_icir=c.get("min_abs_icir", 0.1),
                min_abs_monotonicity=c.get("min_abs_monotonicity", 0.05),
                max_sign_flip_ratio=c.get("max_sign_flip_ratio", 0.45),
            ))

        # 链接
        head = steps[0]
        for step in steps[1:]:
            head.set_next(step)
            head = step

        return steps[0]

    # ── Stage: export ──────────────────────────────────────────────────

    def export(self):
        """保存 Parquet + YAML。"""
        output_cfg = self.config.get("output", {})
        primary_label = self.config.get("labels", {}).get("primary", "label_5d")
        periods = self.config.get("labels", {}).get("periods", [1, 5, 10, 20])

        # 构建最终 DataFrame: factors + all labels
        result_df = self.filtered_X.copy()
        for period in periods:
            label_name = f"label_{period}d"
            if label_name in self.labels_dict:
                lbl = self.labels_dict[label_name]
                result_df[label_name] = lbl.loc[result_df.index]

        # 保存 Parquet
        parquet_path = Path(output_cfg.get("parquet", "data/factor_pool.parquet"))
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        result_df.to_parquet(parquet_path)
        logging.info(f"Factor pool saved to {parquet_path} ({result_df.shape})")

        # 保存 YAML
        yaml_path = Path(output_cfg.get("yaml", "configs/factor_pool.yaml"))
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        filter_stats = {
            "total_factors_before": int(self.factors_df.shape[1]),
            "total_factors_after": int(self.filtered_X.shape[1]),
            "total_rows": int(self.filtered_X.shape[0]),
            "primary_label": primary_label,
            "factor_names": sorted(self.filtered_X.columns.tolist()),
        }
        yaml_content = {
            "factor_pool": filter_stats,
            "filter_config": self.config.get("filter", {}),
            "data_config": self.config.get("data", {}),
        }
        with open(yaml_path, "w") as f:
            yaml.dump(yaml_content, f, default_flow_style=False, sort_keys=False)
        logging.info(f"Factor pool metadata saved to {yaml_path}")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/pipelines/factor/test_alpha_pipeline.py -v`
Expected: All 2 tests PASS

**Step 5: Commit**

```bash
git add src/pipelines/factor/alpha_pipeline.py tests/pipelines/factor/test_alpha_pipeline.py
git commit -m "feat: implement AlphaFactorPipeline with all stages"
```

---

### Task 5: Implement FactorQualityReporter

**Files:**
- Create: `src/pipelines/factor/factor_report.py`
- Create: `tests/pipelines/factor/test_factor_report.py`

**Context:** Generates a comprehensive Markdown quality report covering factor quality statistics (IC/ICIR/monotonicity distribution, filter funnel, group comparison) and label statistics (distribution, quantiles, factor-label correlation heatmap).

**Step 1: Write the failing test**

```python
# tests/pipelines/factor/test_factor_report.py
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from pipelines.factor.factor_report import FactorQualityReporter


def make_sample_data(n=200, n_features=10):
    dates = pd.date_range("2020-01-01", periods=n // 2, freq="B")
    symbols = ["SH600000", "SZ000001"]
    index = pd.MultiIndex.from_product([dates, symbols],
                                        names=["datetime", "instrument"])
    X = pd.DataFrame({
        f"f{j}": np.random.randn(len(index)) for j in range(n_features)
    }, index=index)
    y = pd.Series(np.random.randn(len(index)), index=index)
    return X, y


@pytest.fixture
def report_data():
    X_before, y = make_sample_data(n_features=10)
    X_after = X_before.iloc[:len(X_before)//2]  # simulate filter kept 50%
    y = y.loc[X_after.index]
    artifacts = {
        "DropHighMissingFeatureStep.missing_ratio": pd.Series(
            np.random.uniform(0, 0.5, 10), index=[f"f{j}" for j in range(10)]
        ),
        "FactorQualityFilterStep.factor_stats": pd.DataFrame({
            "ic_mean": np.random.uniform(-0.1, 0.1, len(X_after.columns)),
            "icir": np.random.uniform(-2, 2, len(X_after.columns)),
            "monotonicity": np.random.uniform(-0.3, 0.3, len(X_after.columns)),
            "sign_flip_ratio": np.random.uniform(0.1, 0.8, len(X_after.columns)),
        }, index=X_after.columns),
    }
    logs = [
        "[DropMissingLabelStep] rows: 400 -> 400",
        "[DropHighMissingFeatureStep] features: 20 -> 10",
        "[FactorQualityFilterStep] features: 10 -> 10",
    ]
    all_labels = {
        "label_1d": y,
        "label_5d": y,
        "label_10d": y,
        "label_20d": y,
    }
    return X_before, X_after, y, artifacts, logs, all_labels


def test_generate_report_creates_file(tmp_path, report_data):
    """Report should generate a valid Markdown file."""
    X_before, X_after, y, artifacts, logs, all_labels = report_data
    output_path = str(tmp_path / "factor_report.md")

    reporter = FactorQualityReporter(output_path=output_path)
    path = reporter.generate(
        X_before=X_before, X_after=X_after, y=y,
        filter_artifacts=artifacts, filter_logs=logs,
        all_labels=all_labels,
    )

    assert Path(output_path).exists()
    content = Path(output_path).read_text()
    assert "# Factor Quality Report" in content
    assert "IC Statistics" in content or "IC 统计" in content
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/pipelines/factor/test_factor_report.py -v`
Expected: FAIL (ModuleNotFoundError)

**Step 3: Write minimal implementation**

```python
# src/pipelines/factor/factor_report.py
"""生成因子质量报告（Markdown 格式）。"""
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


class FactorQualityReporter:
    """生成因子质量报告。

    报告内容:
    1. 因子质量统计: IC/ICIR/单调性分布, 过滤链漏斗, 按组对比
    2. Label 统计: 分布, 分位数, 因子-label 相关性
    """

    def __init__(self, output_path: str):
        self.output_path = Path(output_path)

    def generate(
        self,
        X_before: pd.DataFrame,
        X_after: pd.DataFrame,
        y: pd.Series,
        filter_artifacts: dict,
        filter_logs: list[str],
        all_labels: dict[str, pd.Series],
    ) -> Path:
        """生成报告并保存。"""
        lines = []
        lines.append("# Factor Quality Report")
        lines.append("")
        lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Primary Label**: {filter_logs[0] if filter_logs else 'N/A'}")
        lines.append("")

        # ── Section 1: Filter Funnel ──
        lines.extend(self._section_filter_funnel(filter_logs))

        # ── Section 2: Factor Quality Stats ──
        lines.extend(self._section_factor_quality(X_before, X_after, filter_artifacts))

        # ── Section 3: Label Stats ──
        lines.extend(self._section_label_stats(all_labels))

        # ── Section 4: Factor-Label Correlation ──
        lines.extend(self._section_factor_label_corr(X_after, y))

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text("\n".join(lines), encoding="utf-8")
        logging.info(f"Factor quality report saved: {self.output_path}")
        return self.output_path

    def _section_filter_funnel(self, logs: list[str]) -> list[str]:
        """过滤链漏斗。"""
        lines = ["---", "", "## 1. Filter Funnel (过滤链漏斗)", ""]
        lines.append("| Step | Rows | Features |")
        lines.append("|------|------|----------|")
        for log in logs:
            # Parse: [StepName] rows: X -> Y, features: A -> B
            parts = log.split("]")
            if len(parts) < 2:
                continue
            step_name = parts[0].lstrip("[")
            rest = parts[1].strip()
            lines.append(f"| {step_name} | {rest} |")
        lines.append("")
        return lines

    def _section_factor_quality(
        self, X_before: pd.DataFrame, X_after: pd.DataFrame, artifacts: dict
    ) -> list[str]:
        """因子质量统计。"""
        lines = ["---", "", "## 2. Factor Quality Statistics (因子质量统计)", ""]

        # IC statistics from FactorQualityFilterStep
        stats_key = "FactorQualityFilterStep.factor_stats"
        if stats_key in artifacts:
            stats = artifacts[stats_key]
            lines.append("### IC/ICIR/Monotonicity Distribution")
            lines.append("")
            lines.append("| Metric | Mean | Std | P25 | Median | P75 |")
            lines.append("|--------|------|-----|-----|--------|-----|")
            for col in ["ic_mean", "icir", "monotonicity"]:
                if col in stats.columns:
                    s = stats[col].dropna()
                    lines.append(
                        f"| {col} | {s.mean():.4f} | {s.std():.4f} | "
                        f"{s.quantile(0.25):.4f} | {s.median():.4f} | "
                        f"{s.quantile(0.75):.4f} |"
                    )
            lines.append("")

        # Before/After summary
        lines.append("### Factor Pool Summary")
        lines.append("")
        lines.append(f"- **Total factors before filtering**: {X_before.shape[1]}")
        lines.append(f"- **Total factors after filtering**: {X_after.shape[1]}")
        lines.append(f"- **Retained rate**: {X_after.shape[1] / max(X_before.shape[1], 1) * 100:.1f}%")
        lines.append(f"- **Total samples**: {X_after.shape[0]}")
        lines.append("")

        # Group comparison: Alpha158 vs extra
        alpha_cols = [c for c in X_after.columns if not c.startswith(("label_", "pe_", "pb_", "ps_", "pcf_", "tot_", "a_mv", "turn"))]
        extra_cols = [c for c in X_after.columns if c not in alpha_cols]
        lines.append("### Factor Group Comparison")
        lines.append("")
        lines.append(f"- **Alpha158 factors**: {len(alpha_cols)}")
        lines.append(f"- **Extra features (valuation/market-cap)**: {len(extra_cols)}")
        lines.append("")

        return lines

    def _section_label_stats(self, all_labels: dict[str, pd.Series]) -> list[str]:
        """Label 统计。"""
        lines = ["---", "", "## 3. Label Statistics (标签统计)", ""]

        lines.append("| Label | Count | Mean | Std | Min | P25 | Median | P75 | Max |")
        lines.append("|-------|-------|------|-----|-----|-----|--------|-----|-----|")

        for name, lbl in sorted(all_labels.items()):
            s = lbl.dropna()
            lines.append(
                f"| {name} | {len(s)} | {s.mean():.6f} | {s.std():.6f} | "
                f"{s.min():.6f} | {s.quantile(0.25):.6f} | "
                f"{s.median():.6f} | {s.quantile(0.75):.6f} | "
                f"{s.max():.6f} |"
            )
        lines.append("")
        return lines

    def _section_factor_label_corr(
        self, X: pd.DataFrame, y: pd.Series
    ) -> list[str]:
        """因子-label 相关性热力图 (top 20)。"""
        lines = ["---", "", "## 4. Top Factor-Label Correlations (因子-label 相关性 Top 20)", ""]

        # Compute Spearman correlation per factor
        corrs = {}
        for col in X.columns:
            valid = pd.concat([X[col], y], axis=1).dropna()
            if len(valid) > 10:
                corrs[col] = valid.iloc[:, 0].corr(valid.iloc[:, 1], method="spearman")

        if corrs:
            corr_series = pd.Series(corrs).dropna()
            top20 = corr_series.abs().nlargest(20)
            lines.append("| Rank | Factor | Correlation |")
            lines.append("|------|--------|-------------|")
            for rank, (factor, abs_corr) in enumerate(top20.items(), 1):
                actual_corr = corr_series[factor]
                lines.append(f"| {rank} | {factor} | {actual_corr:.4f} |")
            lines.append("")

        return lines
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/pipelines/factor/test_factor_report.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pipelines/factor/factor_report.py tests/pipelines/factor/test_factor_report.py
git commit -m "feat: implement FactorQualityReporter for comprehensive factor quality reports"
```

---

### Task 5b: Wire report stage into AlphaFactorPipeline

**Files:**
- Modify: `src/pipelines/factor/alpha_pipeline.py` — add `generate_report` stage method
- Modify: `tests/pipelines/factor/test_alpha_pipeline.py` — add report to stages config

**Step 1: Add report stage method to AlphaFactorPipeline**

Add the `generate_report` import and method to `alpha_pipeline.py`:

```python
from pipelines.factor.factor_report import FactorQualityReporter
```

Add after `export()` method:

```python
    # ── Stage: report ──────────────────────────────────────────────────

    def generate_report(self):
        """生成因子质量报告。"""
        output_cfg = self.config.get("output", {})
        report_path = output_cfg.get("report", "data/quality/factor_report.md")

        # 需要过滤前的因子 DataFrame
        X_before = self.factors_df
        X_after = self.filtered_X
        y = self.filtered_y
        artifacts = self.filter_artifacts or {}

        reporter = FactorQualityReporter(output_path=report_path)
        reporter.generate(
            X_before=X_before,
            X_after=X_after,
            y=y,
            filter_artifacts=artifacts,
            filter_logs=self.filter_artifacts.get("filter_logs", []),
            all_labels=self.labels_dict or {},
        )
```

**Step 2: Store filter logs in filter_artifacts**

In `run_filter()`, add the logs to artifacts:

```python
        ctx = chain.handle(ctx)

        self.filtered_X = ctx.X
        self.filtered_y = ctx.y
        self.filter_artifacts = ctx.artifacts
        self.filter_artifacts["filter_logs"] = ctx.logs  # ← add this line
```

**Step 3: Update test config to include report stage**

Update `tests/pipelines/factor/test_alpha_pipeline.py` config:

```python
        "output": {
            "parquet": "data/factor_pool.parquet",
            "yaml": "configs/factor_pool.yaml",
            "report": "data/quality/factor_report.md",
        },
```

Update stage map test:

```python
    expected_map = {
        "ingest_bin": "ingest_bin",
        "factor_compute": "factor_compute",
        "label_compute": "label_compute",
        "filter": "run_filter",
        "export": "export",
        "report": "generate_report",
    }
```

**Step 4: Commit**

```bash
git add src/pipelines/factor/alpha_pipeline.py tests/pipelines/factor/test_alpha_pipeline.py
git commit -m "feat: wire report stage into AlphaFactorPipeline"
```

---

### Task 6: Create config and register pipeline

**Files:**
- Create: `configs/alpha_factor.yaml`
- Modify: `src/pipelines/__init__.py` — register new pipeline
- Modify: `scripts/run_pipeline.py` — add alpha_factor default stages

**Context:** Wire up the new pipeline so it can be executed via CLI.

**Step 1: Create `configs/alpha_factor.yaml`**

```yaml
# Alpha158 因子池 Pipeline 配置
# 用法: uv run python scripts/run_pipeline.py --config configs/alpha_factor.yaml

pipeline:
  name: alpha_factor
  stages:
    - ingest_bin
    - factor_compute
    - label_compute
    - filter
    - export
    - report

data:
  qlib_csv: data/qlib_output/ohlcv
  qlib_bin: data/qlib_bin
  instruments: "csi1000"
  start_date: "2020-01-01"
  end_date: null
  extra_fields:
    - pe_ttm
    - pb_mrq
    - ps_ttm
    - pcf_ttm_oper
    - tot_mv
    - a_mv
    - turnrate

labels:
  primary: "label_5d"
  periods: [1, 5, 10, 20]

filter:
  drop_missing_label: {}
  drop_high_missing:
    threshold: 0.3
  drop_high_inf:
    threshold: 0.01
  drop_low_variance:
    variance_threshold: 1.0e-8
    unique_ratio_threshold: 0.01
  factor_quality:
    min_abs_ic_mean: 0.005
    min_abs_icir: 0.1
    min_abs_monotonicity: 0.05
    max_sign_flip_ratio: 0.45

output:
  parquet: data/factor_pool.parquet
  yaml: configs/factor_pool.yaml
  report: data/quality/factor_report.md
```

**Step 2: Register in `src/pipelines/__init__.py`**

Add to the existing file:

```python
from pipelines.factor.alpha_pipeline import AlphaFactorPipeline

PIPELINE_REGISTRY: dict[str, type[DataPipeline]] = {
    "csi1000_qlib": CSI1000QlibPipeline,
    "alpha_factor": AlphaFactorPipeline,
}
```

**Step 3: Update CLI default stages in `scripts/run_pipeline.py`**

Replace the hardcoded default stages logic (around line 50):

```python
# Replace:
# stages = args.stages.split(",") if args.stages else ["download", "validate", "clean", "ingest"]

# With:
DEFAULT_STAGES = {
    "csi1000_qlib": ["download", "validate", "clean", "ingest"],
    "alpha_factor": ["ingest_bin", "factor_compute", "label_compute", "filter", "export", "report"],
}

if args.config:
    config = load_config(args.config)
    pipeline_name = config["pipeline"]["name"]
else:
    pipeline_name = args.pipeline
    stages = args.stages.split(",") if args.stages else DEFAULT_STAGES.get(
        pipeline_name, ["download", "validate", "clean", "ingest"])
    config = {
        "pipeline": {"name": pipeline_name, "stages": stages},
        "exports_base": args.exports_base,
        "qlib_output": args.qlib_output,
        "qlib_bin": args.qlib_bin,
    }
```

**Step 4: Commit**

```bash
git add configs/alpha_factor.yaml src/pipelines/__init__.py scripts/run_pipeline.py
git commit -m "feat: register alpha_factor pipeline and create config"
```

---

### Task 7: Integration test (dry-run)

**Files:**
- Create: `tests/pipelines/factor/test_integration.py`

**Context:** Test the full pipeline flow end-to-end with mocked Qlib dependencies, including report generation.

**Step 1: Write integration test**

```python
# tests/pipelines/factor/test_integration.py
"""AlphaFactorPipeline 集成测试 — mock Qlib 依赖。"""
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock
from pathlib import Path
from pipelines.factor.alpha_pipeline import AlphaFactorPipeline


def make_mock_data(n_symbols=3, n_days=60):
    """生成 mock 因子和价格数据。"""
    dates = pd.date_range("2020-01-01", periods=n_days, freq="B")
    symbols = [f"SH60000{i}" for i in range(n_symbols)]
    index = pd.MultiIndex.from_product([dates, symbols],
                                        names=["datetime", "instrument"])
    n = len(index)

    factors = pd.DataFrame({
        f"factor_{j}": np.random.randn(n) * 0.1 + j * 0.01
        for j in range(5)
    }, index=index)

    close = pd.DataFrame({
        "close": np.random.uniform(10, 100, n),
    }, index=index)

    return factors, close


@pytest.fixture
def mock_config(tmp_path):
    """使用宽松过滤阈值，确保大多数因子能保留。"""
    return {
        "pipeline": {
            "name": "AlphaFactorPipeline",
            "stages": ["factor_compute", "label_compute", "filter", "export", "report"],
        },
        "data": {
            "qlib_csv": "data/qlib_output/ohlcv",
            "qlib_bin": str(tmp_path / "qlib_bin"),
            "instruments": "csi1000",
            "start_date": "2020-01-01",
            "end_date": "2020-06-30",
        },
        "labels": {
            "primary": "label_5d",
            "periods": [1, 5, 10, 20],
        },
        "filter": {
            "drop_missing_label": {},
            "drop_high_missing": {"threshold": 0.9},
            "drop_high_inf": {"threshold": 0.5},
            "drop_low_variance": {
                "variance_threshold": 1e-12,
                "unique_ratio_threshold": 0.001,
            },
            "factor_quality": {
                "min_abs_ic_mean": 0.0,
                "min_abs_icir": 0.0,
                "min_abs_monotonicity": 0.0,
                "max_sign_flip_ratio": 1.0,
            },
        },
        "output": {
            "parquet": str(tmp_path / "factor_pool.parquet"),
            "yaml": str(tmp_path / "factor_pool.yaml"),
            "report": str(tmp_path / "factor_report.md"),
        },
    }


def test_pipeline_dry_run_with_report(mock_config):
    """全链路 mock 测试：因子计算 → 标签 → 过滤 → 导出 → 报告。"""
    factors_df, close_df = make_mock_data()

    pipeline = AlphaFactorPipeline(mock_config)

    with patch.object(pipeline, "factor_compute") as mock_fc:
        mock_fc.side_effect = lambda: setattr(pipeline, "factors_df", factors_df.copy())
        with patch.object(pipeline, "label_compute") as mock_lc:
            # 构造 label dict
            periods = mock_config["labels"]["periods"]
            labels = {}
            for period in periods:
                shifted = close_df.groupby(level="instrument")["close"].shift(-period)
                labels[f"label_{period}d"] = shifted / close_df["close"] - 1
            pipeline.labels_dict = labels

            pipeline.run_filter()
            pipeline.export()
            pipeline.generate_report()

    # 验证过滤结果
    assert pipeline.filtered_X is not None
    assert pipeline.filtered_y is not None
    assert len(pipeline.filtered_X) > 0

    # 验证 Parquet 文件
    parquet_path = Path(mock_config["output"]["parquet"])
    assert parquet_path.exists()
    saved = pd.read_parquet(parquet_path)
    assert len(saved) > 0

    # 验证所有 label 列存在
    for period in periods:
        assert f"label_{period}d" in saved.columns

    # 验证 YAML 文件
    yaml_path = Path(mock_config["output"]["yaml"])
    assert yaml_path.exists()

    # 验证报告文件
    report_path = Path(mock_config["output"]["report"])
    assert report_path.exists()
    content = report_path.read_text()
    assert "# Factor Quality Report" in content
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/pipelines/factor/test_integration.py -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `uv run pytest tests/pipelines/ -v`
Expected: All tests PASS (existing + new)

**Step 4: Commit**

```bash
git add tests/pipelines/factor/test_integration.py
git commit -m "test: add integration test for AlphaFactorPipeline with report"
```

---

### Task 8: Run all tests and verify no regressions

**Files:** None (verification task)

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

**Step 2: Verify pipeline can be loaded via CLI**

Run: `uv run python scripts/run_pipeline.py --pipeline alpha_factor --stages ingest_bin --verbose`
Expected: Pipeline loads, attempts dump_bin (may succeed or fail depending on data state — just verifying the pipeline is wired up correctly)

**Step 3: Commit if any fixes needed**

```bash
git commit -am "fix: address any issues found during verification"
```
