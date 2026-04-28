# 截面因子过滤责任链（8 环）实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将因子筛选流水线从"指标收集器"改造为真正的责任链，每环执行筛选/剔除，最终输出筛选后的因子池和 8 环报告。

**Architecture:** 单流水线 9 阶段（load + 8 rings + report），每 step 的 `process(df)` 返回 `(DataFrame, metrics_dict)`，Ring 3 起 DataFrame 列真实减少。

**Tech Stack:** Polars (DataFrame), scikit-learn (聚类), LightGBM (ML), pandas (IC 计算), pytest (测试)

---

## 文件总览

| 操作 | 文件路径 |
|------|----------|
| **重写** | `src/pipelines/factor_filtering/pipeline.py` |
| **重写** | `src/pipelines/factor_filtering/steps/step00_data_qa.py` |
| **新建** | `src/pipelines/factor_filtering/steps/step01_preprocess.py` |
| **重写** | `src/pipelines/factor_filtering/steps/step02_profiling.py` |
| **新建** | `src/pipelines/factor_filtering/steps/step03_cs_filter.py` |
| **新建** | `src/pipelines/factor_filtering/steps/step04_stability.py` |
| **重命名+重写** | `src/pipelines/factor_filtering/steps/step05_clustering.py` |
| **新建** | `src/pipelines/factor_filtering/steps/step06_representative.py` |
| **重命名+重写** | `src/pipelines/factor_filtering/steps/step07_portfolio.py` |
| **重命名+重写** | `src/pipelines/factor_filtering/steps/step08_ml_importance.py` |
| **更新** | `configs/factor_filtering.yaml` |
| **更新** | `tests/pipelines/factor_filtering/test_pipeline.py` |
| **更新** | `tests/pipelines/factor_filtering/test_step01_data_qa.py` |
| **新建** | `tests/pipelines/factor_filtering/test_step01_preprocess.py` |
| **更新** | `tests/pipelines/factor_filtering/test_step02_profiling.py` |
| **新建** | `tests/pipelines/factor_filtering/test_step03_cs_filter.py` |
| **新建** | `tests/pipelines/factor_filtering/test_step04_stability.py` |
| **更新** | `tests/pipelines/factor_filtering/test_step03_clustering.py` → `test_step05_clustering.py` |
| **新建** | `tests/pipelines/factor_filtering/test_step06_representative.py` |
| **更新** | `tests/pipelines/factor_filtering/test_step04_portfolio.py` → `test_step07_portfolio.py` |
| **更新** | `tests/pipelines/factor_filtering/test_step05_ml_importance.py` → `test_step08_ml_importance.py` |
| **更新** | `src/pipelines/__init__.py` (无需改动，已注册) |
| **删除** | `src/pipelines/factor_filtering/steps/step04_portfolio.py` (被 step07 替代) |
| **删除** | `src/pipelines/factor_filtering/steps/step05_ml_importance.py` (被 step08 替代) |
| **删除** | `src/pipelines/factor_filtering/steps/step03_clustering.py` (被 step05 替代) |

---

### Task 1: 更新配置文件

**Files:**
- Modify: `configs/factor_filtering.yaml`

添加新的 stages 列表和 filter/clustering/preprocess 配置节：

```yaml
pipeline:
  name: factor_filtering
  stages:
    - load
    - ring0_qa
    - ring1_preprocess
    - ring2_profile
    - ring3_filter
    - ring4_stability
    - ring5_cluster
    - ring6_select
    - ring7_portfolio
    - ring8_ml
    - report
  output_dir: "data/reports/factor_filtering"

data:
  factor_path: "data/alpha158_pool.parquet"
  label_col: "label_20d"
  fundamentals_path: "data/parquet/fundamentals"  # 可选

filter:
  min_abs_ic: 0.01
  min_coverage: 0.60

clustering:
  distance_threshold: 0.5
  method: "factor_return_correlation"
  max_sample_rows: 50000

preprocess:
  winsorize_lower: 0.01
  winsorize_upper: 0.99
  transform_method: "rank_pct"

representative:
  n_per_cluster: 2
```

**Step: 写入配置并验证**

Run: `python -c "import yaml; print(yaml.safe_load(open('configs/factor_filtering.yaml')))"`
Expected: 打印 config dict，无报错

**Commit:**
```bash
git add configs/factor_filtering.yaml
git commit -m "refactor: expand factor_filtering config for 8-ring pipeline"
```

---

### Task 2: Ring 0 — DataAndLabelQA

**Files:**
- Rewrite: `src/pipelines/factor_filtering/steps/step00_data_qa.py`
- Update: `tests/pipelines/factor_filtering/test_step01_data_qa.py`

**Step 1: 重写 step00_data_qa.py**

删除旧的 `step01_data_qa.py`，新建 `step00_data_qa.py`：

```python
"""Ring 0: 数据与标签卫生检查。

检查项：
- inf/-inf → null
- 缺失率/覆盖率
- 常数/低方差因子
- 标签分布
"""

from __future__ import annotations

import polars as pl


class DataAndLabelQA:
    """数据与标签卫生检查步骤。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.min_coverage: float = self.config.get("min_coverage", 0.5)
        self.variance_threshold: float = self.config.get("variance_threshold", 1e-8)

    def _factor_cols(self, df: pl.DataFrame) -> list[str]:
        return [
            c for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

    def _label_cols(self, df: pl.DataFrame) -> list[str]:
        return [c for c in df.columns if c.startswith("label")]

    def process(self, df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
        """执行卫生检查，返回干净 DataFrame 和 QA 报告。"""
        report: dict = {"coverage": {}, "constant_factors": [], "label_stats": {}, "rejected": []}

        # 1. inf/-inf → null
        factor_cols = self._factor_cols(df)
        replacements = [
            pl.when(pl.col(c).is_infinite()).then(None).otherwise(pl.col(c)).alias(c)
            for c in factor_cols
        ]
        if replacements:
            df = df.with_columns(replacements)

        # 2. 覆盖率 + 常数检测
        height = df.height
        for col in factor_cols:
            non_null = df.select(pl.col(col).drop_nulls().len()).item()
            coverage = non_null / height if height > 0 else 0.0
            report["coverage"][col] = coverage

            valid = df.select(pl.col(col).drop_nulls())
            if valid.height >= 2:
                std = valid.select(pl.col(col).std()).item() or 0.0
                if std < self.variance_threshold:
                    report["constant_factors"].append(col)
                    report["rejected"].append((col, "constant/low_variance"))

        # 3. 标签分布
        for col in self._label_cols(df):
            report["label_stats"][col] = {
                "mean": df.select(pl.col(col).mean()).item(),
                "std": df.select(pl.col(col).std()).item(),
                "null_pct": 1.0 - df.select(pl.col(col).drop_nulls().len()).item() / height,
            }

        # 4. 低覆盖率因子剔除
        cols_to_drop = [col for col, cov in report["coverage"].items() if cov < self.min_coverage]
        report["rejected"].extend((c, "low_coverage") for c in cols_to_drop)
        if cols_to_drop:
            df = df.drop(cols_to_drop)

        return df, report
```

**Step 2: 更新测试 test_step01_data_qa.py**

```python
import polars as pl
from src.pipelines.factor_filtering.steps.step00_data_qa import DataAndLabelQA


def test_inf_replacement():
    df = pl.DataFrame({
        "datetime": ["2023-01-01"],
        "instrument": ["000001.SZ"],
        "factor1": [float("inf")],
        "label_20d": [0.05],
    })
    step = DataAndLabelQA()
    result, report = step.process(df)
    assert result.filter(pl.col("factor1").is_infinite()).height == 0


def test_constant_factor_detection():
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-02", "2023-01-03"],
        "instrument": ["A", "B", "C"],
        "factor_const": [1.0, 1.0, 1.0],
        "factor_var": [1.0, 2.0, 3.0],
        "label_20d": [0.01, 0.02, 0.03],
    })
    step = DataAndLabelQA()
    result, report = step.process(df)
    assert "factor_const" in report["constant_factors"]
    assert "factor_var" not in report["constant_factors"]


def test_low_coverage_rejection():
    df = pl.DataFrame({
        "datetime": ["2023-01-01"] * 10 + ["2023-01-02"] * 10,
        "instrument": ["A", "B", "C", "D", "E"] * 2,
        "factor_good": [1.0] * 20,
        "factor_bad": [1.0] * 10 + [None] * 10,
        "label_20d": [0.01] * 20,
    })
    step = DataAndLabelQA(min_coverage=0.8)
    result, report = step.process(df)
    assert "factor_bad" not in result.columns
    assert "factor_good" in result.columns
```

**Step 3: 运行测试**

Run: `pytest tests/pipelines/factor_filtering/test_step01_data_qa.py -v`
Expected: 3 tests pass

**Step 4: Commit**

```bash
git rm src/pipelines/factor_filtering/steps/step01_data_qa.py
git add src/pipelines/factor_filtering/steps/step00_data_qa.py tests/pipelines/factor_filtering/test_step01_data_qa.py
git commit -m "feat(ring0): data and label QA with coverage/constant detection"
```

---

### Task 3: Ring 1 — PreprocessAndNeutralize

**Files:**
- Create: `src/pipelines/factor_filtering/steps/step01_preprocess.py`
- Create: `tests/pipelines/factor_filtering/test_step01_preprocess.py`

**Step 1: 创建 step01_preprocess.py**

```python
"""Ring 1: 因子预处理（去极值/标准化/方向统一）。"""

from __future__ import annotations

import polars as pl


class PreprocessAndNeutralize:
    """截面因子预处理步骤。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.winsorize_lower: float = self.config.get("winsorize_lower", 0.01)
        self.winsorize_upper: float = self.config.get("winsorize_upper", 0.99)
        self.transform_method: str = self.config.get("transform_method", "rank_pct")

    def _factor_cols(self, df: pl.DataFrame) -> list[str]:
        return [
            c for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

    def _winsorize(self, df: pl.DataFrame, cols: list[str]) -> pl.DataFrame:
        """截面 winsorize：按 datetime 分组做分位截断。"""
        def _clip_expr(col: str) -> pl.Expr:
            lower = pl.col(col).quantile(self.winsorize_lower)
            upper = pl.col(col).quantile(self.winsorize_upper)
            return pl.col(col).clip(lower, upper)

        return df.with_columns([_clip_expr(c) for c in cols])

    def _rank_pct(self, df: pl.DataFrame, cols: list[str]) -> pl.DataFrame:
        """截面 rank_pct：映射到 [-1, 1]。"""
        exprs = [pl.col(c).rank(method="average") / pl.col(c).count() * 2 - 1 for c in cols]
        return df.with_columns(exprs)

    def _zscore(self, df: pl.DataFrame, cols: list[str]) -> pl.DataFrame:
        """截面 z-score 标准化。"""
        exprs = [
            (pl.col(c) - pl.col(c).mean()) / pl.col(c).std()
            for c in cols
        ]
        return df.with_columns(exprs)

    def process(self, df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
        """执行预处理，返回处理后 DataFrame 和操作记录。"""
        factor_cols = self._factor_cols(df)
        applied = []

        # 1. Winsorize
        df = df.group_by("datetime").map_groups(
            lambda g: self._winsorize(g, factor_cols)
        )
        applied.append("winsorize")

        # 2. Transform
        df = df.group_by("datetime").map_groups(
            lambda g: self._rank_pct(g, factor_cols) if self.transform_method == "rank_pct"
            else self._zscore(g, factor_cols)
        )
        applied.append(self.transform_method)

        return df, {"transform_applied": applied}
```

**Step 2: 创建测试**

```python
import polars as pl
from src.pipelines.factor_filtering.steps.step01_preprocess import PreprocessAndNeutralize


def test_rank_pct_normalization():
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-01", "2023-01-01"],
        "instrument": ["A", "B", "C"],
        "factor1": [1.0, 5.0, 3.0],
        "label_20d": [0.01, 0.02, 0.03],
    })
    step = PreprocessAndNeutralize(transform_method="rank_pct")
    result, report = step.process(df)
    # rank_pct 结果应在 [-1, 1] 范围内
    assert result["factor1"].min() >= -1.0
    assert result["factor1"].max() <= 1.0
    assert "rank_pct" in report["transform_applied"]


def test_winsorize_clips_extremes():
    df = pl.DataFrame({
        "datetime": ["2023-01-01"] * 100,
        "instrument": [f"INST_{i}" for i in range(100)],
        "factor1": list(range(100)),
        "label_20d": [0.01] * 100,
    })
    step = PreprocessAndNeutralize(
        winsorize_lower=0.01, winsorize_upper=0.99, transform_method="rank_pct"
    )
    result, _ = step.process(df)
    # 极端值应被截断
    assert result["factor1"].is_finite().all()
```

**Step 3: 运行测试**

Run: `pytest tests/pipelines/factor_filtering/test_step01_preprocess.py -v`
Expected: 2 tests pass

**Step 4: Commit**

```bash
git add src/pipelines/factor_filtering/steps/step01_preprocess.py tests/pipelines/factor_filtering/test_step01_preprocess.py
git commit -m "feat(ring1): preprocess with winsorize + rank_pct normalization"
```

---

### Task 4: Ring 2 — SingleFactorProfiler

**Files:**
- Rewrite: `src/pipelines/factor_filtering/steps/step02_profiling.py`
- Update: `tests/pipelines/factor_filtering/test_step02_profiling.py`

**Step 1: 重写 step02_profiling.py**

```python
"""Ring 2: 单因子横截面画像。

计算每日 Rank IC，聚合为 mean/icir/win_rate/分组收益/单调性等指标。
"""

from __future__ import annotations

import polars as pl


class SingleFactorProfiler:
    """单因子截面 IC 计算与稳定性评估。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(self, label_col: str, config: dict | None = None):
        self.label_col = label_col
        self.config = config or {}
        self.n_groups: int = self.config.get("n_groups", 5)

    def _factor_cols(self, df: pl.DataFrame) -> list[str]:
        return [
            c for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

    def compute_daily_ic(self, df: pl.DataFrame, factor_col: str) -> pl.DataFrame:
        """计算每日截面 Rank IC。"""
        return df.group_by("datetime").agg(
            pl.corr(pl.col(factor_col), pl.col(self.label_col), method="spearman").alias("ic")
        ).drop_nulls()

    def compute_group_returns(self, df: pl.DataFrame, factor_col: str) -> dict:
        """按因子值分 N 组，计算每组平均 label（代理收益）。"""
        n = self.n_groups
        ranked = df.with_columns(
            pl.col(factor_col).rank(method="average") / pl.col(factor_col).count()
        ).with_columns(
            (pl.col(factor_col) * n).clip(0, n - 1).cast(pl.Int64).alias("group")
        )
        group_avg = ranked.group_by("group").agg(
            pl.col(self.label_col).mean().alias("mean_label")
        ).sort("group")

        return {
            f"Q{i+1}": row["mean_label"].item()
            for i, row in enumerate(group_avg.iter_rows(named=True))
            if len(row) > 0
        }

    def process(self, df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
        """计算所有因子的画像指标。"""
        factor_cols = self._factor_cols(df)
        metrics = {}

        for col in factor_cols:
            daily_ic = self.compute_daily_ic(df, col)
            ic_series = daily_ic.select(pl.col("ic")).to_series().drop_nulls()

            if len(ic_series) < 2:
                metrics[col] = {"mean_rank_ic": 0.0, "icir": 0.0, "ic_win_rate": 0.0,
                                "group_returns": {}, "long_short": 0.0, "monotonicity": 0.0}
                continue

            mean_ic = ic_series.mean()
            std_ic = ic_series.std()
            icir = mean_ic / std_ic if std_ic > 0 else 0.0
            win_rate = (ic_series > 0).sum() / len(ic_series)

            group_ret = self.compute_group_returns(df, col)
            long_short = group_ret.get(f"Q{self.n_groups}", 0) - group_ret.get("Q1", 0)

            # 单调性：组号与平均收益的 Spearman 相关
            if len(group_ret) >= 3:
                gs = list(group_ret.keys())
                vs = list(group_ret.values())
                from scipy.stats import spearmanr
                mono, _ = spearmanr(gs, vs)
            else:
                mono = 0.0

            metrics[col] = {
                "mean_rank_ic": mean_ic,
                "icir": icir,
                "ic_win_rate": win_rate,
                "group_returns": group_ret,
                "long_short": long_short,
                "monotonicity": mono,
                "n_days": len(ic_series),
            }

        return df, metrics
```

注意：`compute_group_returns` 中的排名逻辑需要修正——应该用因子值排名分组而不是直接操作因子值列。修正：

```python
    def compute_group_returns(self, df: pl.DataFrame, factor_col: str) -> dict:
        n = self.n_groups
        ranked = df.with_columns(
            (pl.col(factor_col).rank(method="average") / pl.col(factor_col).count() * n - 1)
            .clip(0, n - 1)
            .floor()
            .cast(pl.Int64)
            .alias("group")
        )
        # ...
```

实际上 Polars 的 `group_by.map_groups` 在每日截面计算时更合适。但为了简洁，用 `with_columns` + `over` 窗口函数：

```python
    def compute_group_returns(self, df: pl.DataFrame, factor_col: str) -> dict:
        n = self.n_groups
        ranked = df.with_columns([
            (pl.col(factor_col).rank(method="average").over("datetime")
             / pl.col(factor_col).count().over("datetime") * n - 1)
            .clip(0, n - 1)
            .floor()
            .cast(pl.Int64)
            .alias("group"),
        ])
        group_avg = (ranked
            .group_by("group")
            .agg(pl.col(self.label_col).mean().alias("mean_label"))
            .sort("group"))

        return {
            f"Q{int(row['group'])+1}": row["mean_label"]
            for row in group_avg.iter_rows(named=True)
        }
```

**Step 2: 更新测试**

```python
import polars as pl
from src.pipelines.factor_filtering.steps.step02_profiling import SingleFactorProfiler


def test_ic_computation():
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-01", "2023-01-01"],
        "instrument": ["A", "B", "C"],
        "factor1": [1.0, 2.0, 3.0],
        "label_20d": [0.01, 0.02, 0.03],
    })
    step = SingleFactorProfiler(label_col="label_20d")
    result, metrics = step.process(df)
    assert "factor1" in metrics
    assert "mean_rank_ic" in metrics["factor1"]


def test_group_returns():
    df = pl.DataFrame({
        "datetime": ["2023-01-01"] * 10,
        "instrument": [f"INST_{i}" for i in range(10)],
        "factor1": list(range(10)),
        "label_20d": [float(i) / 10 for i in range(10)],
    })
    step = SingleFactorProfiler(label_col="label_20d")
    _, metrics = step.process(df)
    assert "group_returns" in metrics["factor1"]
```

**Step 3: 运行测试**

Run: `pytest tests/pipelines/factor_filtering/test_step02_profiling.py -v`
Expected: 2 tests pass

**Step 4: Commit**

```bash
git add src/pipelines/factor_filtering/steps/step02_profiling.py tests/pipelines/factor_filtering/test_step02_profiling.py
git commit -m "feat(ring2): single factor profiling with IC/ICIR/group_returns/monotonicity"
```

---

### Task 5: Ring 3 — CrossSectionFilter

**Files:**
- Create: `src/pipelines/factor_filtering/steps/step03_cs_filter.py`
- Create: `tests/pipelines/factor_filtering/test_step03_cs_filter.py`

**Step 1: 创建 step03_cs_filter.py**

```python
"""Ring 3: 横截面有效性筛选。

基于宽松阈值过滤无效因子，首次真实 drop DataFrame 列。
"""

from __future__ import annotations

import polars as pl


class CrossSectionFilter:
    """基于 Ring 2 指标执行因子过滤。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.min_abs_ic: float = self.config.get("min_abs_ic", 0.01)
        self.min_coverage: float = self.config.get("min_coverage", 0.60)

    def process(
        self, df: pl.DataFrame, ic_metrics: dict
    ) -> tuple[pl.DataFrame, dict]:
        """根据 IC 指标过滤因子列。

        Args:
            df: 预处理后的 DataFrame。
            ic_metrics: Ring 2 输出的 {因子名: 指标字典}。

        Returns:
            (过滤后的 DataFrame, 筛选报告)
        """
        factor_cols = [
            c for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

        retained = []
        rejected = []

        for col in factor_cols:
            m = ic_metrics.get(col, {})
            abs_ic = abs(m.get("mean_rank_ic", 0.0))
            coverage = m.get("n_days", 0) / max(
                next(
                    (v.get("n_days", 0) for v in ic_metrics.values() if v.get("n_days")),
                    1
                ),
                1,
            )

            reasons = []
            if abs_ic < self.min_abs_ic:
                reasons.append(f"abs_ic={abs_ic:.4f} < {self.min_abs_ic}")
            if coverage < self.min_coverage:
                reasons.append(f"coverage={coverage:.2%} < {self.min_coverage:.0%}")

            if reasons:
                rejected.append((col, "; ".join(reasons)))
            else:
                retained.append(col)

        cols_to_drop = [c for c, _ in rejected]
        if cols_to_drop:
            df = df.drop(cols_to_drop)

        report = {
            "retained": retained,
            "rejected": rejected,
            "retained_count": len(retained),
            "rejected_count": len(rejected),
        }

        return df, report
```

**Step 2: 创建测试**

```python
import polars as pl
from src.pipelines.factor_filtering.steps.step03_cs_filter import CrossSectionFilter


def test_filter_weak_factors():
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-02"],
        "instrument": ["A", "B"],
        "strong_factor": [1.0, 2.0],
        "weak_factor": [0.0, 0.0],
        "label_20d": [0.01, 0.02],
    })
    ic_metrics = {
        "strong_factor": {"mean_rank_ic": 0.05, "n_days": 2},
        "weak_factor": {"mean_rank_ic": 0.001, "n_days": 2},
    }
    step = CrossSectionFilter(min_abs_ic=0.02)
    result, report = step.process(df, ic_metrics)
    assert "weak_factor" not in result.columns
    assert "strong_factor" in result.columns
    assert report["rejected_count"] == 1


def test_no_filter_when_all_strong():
    df = pl.DataFrame({
        "datetime": ["2023-01-01"],
        "instrument": ["A"],
        "f1": [1.0],
        "label_20d": [0.01],
    })
    ic_metrics = {"f1": {"mean_rank_ic": 0.05, "n_days": 1}}
    step = CrossSectionFilter(min_abs_ic=0.02)
    result, report = step.process(df, ic_metrics)
    assert "f1" in result.columns
    assert report["retained_count"] == 1
```

**Step 3: 运行测试**

Run: `pytest tests/pipelines/factor_filtering/test_step03_cs_filter.py -v`
Expected: 2 tests pass

**Step 4: Commit**

```bash
git add src/pipelines/factor_filtering/steps/step03_cs_filter.py tests/pipelines/factor_filtering/test_step03_cs_filter.py
git commit -m "feat(ring3): cross-section filter with configurable IC/coverage thresholds"
```

---

### Task 6: Ring 4 — StabilityChecker

**Files:**
- Create: `src/pipelines/factor_filtering/steps/step04_stability.py`
- Create: `tests/pipelines/factor_filtering/test_step04_stability.py`

**Step 1: 创建 step04_stability.py**

```python
"""Ring 4: 稳定性与状态分层检验。

检验因子在不同时间段和截面分层中的 IC 稳定性。
"""

from __future__ import annotations

import polars as pl


class StabilityChecker:
    """稳定性分层检验。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def _factor_cols(self, df: pl.DataFrame) -> list[str]:
        return [
            c for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

    def _compute_yearly_ic(self, df: pl.DataFrame, factor_col: str, label_col: str) -> dict[int, float]:
        """按年计算 IC。"""
        df_year = df.with_columns(pl.col("datetime").dt.year().alias("year"))
        yearly = df_year.group_by("year").agg(
            pl.corr(pl.col(factor_col), pl.col(label_col), method="spearman").alias("ic")
        )
        return {int(row["year"]): float(row["ic"] or 0) for row in yearly.iter_rows(named=True)}

    def _compute_rolling_ic(self, df: pl.DataFrame, factor_col: str, label_col: str, window: int = 60) -> list[float]:
        """滚动 window 日 IC 序列。"""
        dates = df.select("datetime").unique().sort("datetime")["datetime"].to_list()
        ics = []
        for i in range(window, len(dates) + 1):
            start_date = dates[i - window]
            end_date = dates[i - 1]
            subset = df.filter((pl.col("datetime") >= start_date) & (pl.col("datetime") <= end_date))
            ic = subset.select(
                pl.corr(pl.col(factor_col), pl.col(label_col), method="spearman")
            ).item()
            ics.append(float(ic) if ic else 0.0)
        return ics

    def _size_stratification(self, df: pl.DataFrame, factor_col: str, label_col: str) -> dict[str, float]:
        """按 instrument 编号分位模拟市值分层。"""
        df_ranked = df.with_columns(
            pl.col("instrument").rank(method="dense").over("datetime").alias("size_rank")
        )
        n = df_ranked.select(pl.col("size_rank").max()).item() or 1
        df_ranked = df_ranked.with_columns(
            pl.when(pl.col("size_rank") <= n * 0.33).then("small")
            .when(pl.col("size_rank") <= n * 0.66).then("mid")
            .otherwise("large")
            .alias("size_group")
        )
        strat = df_ranked.group_by("size_group").agg(
            pl.corr(pl.col(factor_col), pl.col(label_col), method="spearman").alias("ic")
        )
        return {row["size_group"]: float(row["ic"] or 0) for row in strat.iter_rows(named=True)}

    def process(self, df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
        """计算所有因子的稳定性指标。"""
        factor_cols = self._factor_cols(df)
        label_col = next((c for c in df.columns if c.startswith("label")), None)
        if not label_col:
            return df, {"error": "no label column found"}

        stability = {}
        for col in factor_cols:
            yearly_ic = self._compute_yearly_ic(df, col, label_col)
            rolling_ic = self._compute_rolling_ic(df, col, label_col, window=60)
            size_ic = self._size_stratification(df, col, label_col)

            # 综合稳定性得分：年度 IC 一致性 + 滚动 IC 波动率倒数 + 分层 IC 一致性
            ic_values = list(yearly_ic.values())
            year_consistency = 1.0 - (pl.Series(ic_values).std() if len(ic_values) > 1 else 0)

            roll_std = pl.Series(rolling_ic).std() if len(rolling_ic) > 1 else 1.0
            roll_stability = 1.0 / (1.0 + roll_std)

            size_values = list(size_ic.values())
            size_consistency = 1.0 - (pl.Series(size_values).std() if len(size_values) > 1 else 0)

            stability_score = 0.4 * year_consistency + 0.3 * roll_stability + 0.3 * size_consistency

            stability[col] = {
                "yearly_ic": yearly_ic,
                "rolling_ic_mean": sum(rolling_ic) / max(len(rolling_ic), 1),
                "size_ic": size_ic,
                "stability_score": stability_score,
            }

        return df, stability
```

**Step 2: 创建测试**

```python
import polars as pl
from src.pipelines.factor_filtering.steps.step04_stability import StabilityChecker


def test_stability_computation():
    dates = ["2020-06-01"] * 100 + ["2021-06-01"] * 100
    df = pl.DataFrame({
        "datetime": dates,
        "instrument": [f"INST_{i % 100}" for i in range(200)],
        "factor1": list(range(200)),
        "label_20d": [float(i) / 200 for i in range(200)],
    })
    step = StabilityChecker()
    result, stability = step.process(df)
    assert "factor1" in stability
    assert "stability_score" in stability["factor1"]
    assert "yearly_ic" in stability["factor1"]
```

**Step 3: 运行测试**

Run: `pytest tests/pipelines/factor_filtering/test_step04_stability.py -v`
Expected: 1 test pass

**Step 4: Commit**

```bash
git add src/pipelines/factor_filtering/steps/step04_stability.py tests/pipelines/factor_filtering/test_step04_stability.py
git commit -m "feat(ring4): stability checker with yearly/rolling/size stratification"
```

---

### Task 7: Ring 5 — FactorClustering (因子收益相关性)

**Files:**
- Rename+Rewrite: `src/pipelines/factor_filtering/steps/step05_clustering.py` (was step03_clustering.py)
- Update: `tests/pipelines/factor_filtering/test_step05_clustering.py` (was test_step03_clustering.py)

**Step 1: 重写 step05_clustering.py**

```python
"""Ring 5: 基于因子收益序列相关性的信息结构聚类。

因子收益 = 每日截面 IC（因子值与 label 的 Spearman 相关）。
使用因子收益的 Pearson 相关矩阵构造距离矩阵，层次聚类。
"""

from __future__ import annotations

import numpy as np
import polars as pl
from sklearn.cluster import AgglomerativeClustering


class FactorClustering:
    """基于因子收益序列相关性的层次聚类。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.distance_threshold: float = self.config.get("distance_threshold", 0.5)

    def _factor_cols(self, df: pl.DataFrame) -> list[str]:
        return [
            c for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

    def _compute_factor_returns(self, df: pl.DataFrame, factor_cols: list[str], label_col: str) -> pl.DataFrame:
        """计算每个因子每日截面 IC 作为因子收益。"""
        daily_ic = df.group_by("datetime").agg(
            [pl.corr(pl.col(c), pl.col(label_col), method="spearman").alias(c) for c in factor_cols]
        ).sort("datetime").drop_nulls()
        return daily_ic

    def fit_predict(self, df: pl.DataFrame, factor_cols: list[str], label_col: str) -> dict[str, int]:
        """对因子收益序列进行聚类。"""
        if len(factor_cols) < 2:
            return {c: 0 for c in factor_cols}

        daily_ic = self._compute_factor_returns(df, factor_cols, label_col)
        if daily_ic.height < 3:
            return {c: 0 for c in factor_cols}

        # 转为 numpy 矩阵 [n_dates, n_factors]
        pd_df = daily_ic.select(factor_cols).to_pandas().fillna(0)

        # Pearson 相关性矩阵
        corr_matrix = pd_df.corr(method="pearson").values

        # 距离矩阵：d = sqrt(0.5 * (1 - corr))
        dist_matrix = np.sqrt(np.clip(0.5 * (1.0 - corr_matrix), 0.0, None))

        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=self.distance_threshold,
            metric="precomputed",
            linkage="complete",
        )
        labels = clustering.fit_predict(dist_matrix)

        return {col: int(lbl) for col, lbl in zip(factor_cols, labels)}

    def process(self, df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
        """流水线接口。"""
        factor_cols = self._factor_cols(df)
        label_col = next((c for c in df.columns if c.startswith("label")), None)
        if not label_col:
            return df, {"clusters": {}, "n_clusters": 0}

        clusters = self.fit_predict(df, factor_cols, label_col)
        n_clusters = len(set(clusters.values()))
        return df, {"clusters": clusters, "n_clusters": n_clusters}
```

**Step 2: 更新测试**

重命名 `test_step03_clustering.py` → `test_step05_clustering.py`：

```python
import polars as pl
from src.pipelines.factor_filtering.steps.step05_clustering import FactorClustering


def test_factor_clustering():
    dates = []
    instruments = []
    f1_vals = []
    f2_vals = []
    label_vals = []
    for d in range(30):
        for i in range(10):
            dates.append(f"2023-01-{d+1:02d}")
            instruments.append(f"INST_{i}")
            f1_vals.append(float(i))
            f2_vals.append(float(i) + 0.1)
            label_vals.append(float(i) / 10)

    df = pl.DataFrame({
        "datetime": dates,
        "instrument": instruments,
        "factor1": f1_vals,
        "factor2": f2_vals,
        "label_20d": label_vals,
    })
    step = FactorClustering()
    result, report = step.process(df)
    assert len(report["clusters"]) == 2
    assert report["n_clusters"] >= 1
```

**Step 3: 运行测试**

Run: `pytest tests/pipelines/factor_filtering/test_step05_clustering.py -v`
Expected: 1 test pass

**Step 4: Commit**

```bash
git rm src/pipelines/factor_filtering/steps/step03_clustering.py
git add src/pipelines/factor_filtering/steps/step05_clustering.py tests/pipelines/factor_filtering/test_step05_clustering.py
git commit -m "feat(ring5): factor clustering based on factor return correlation"
```

---

### Task 8: Ring 6 — RepresentativeSelector

**Files:**
- Create: `src/pipelines/factor_filtering/steps/step06_representative.py`
- Create: `tests/pipelines/factor_filtering/test_step06_representative.py`

**Step 1: 创建 step06_representative.py**

```python
"""Ring 6: 簇内代表因子选择。

每簇按综合评分选择 top_k 个代表因子。
score = 0.30*ICIR_norm + 0.20*monotonicity + 0.20*long_short_tstat
      + 0.15*coverage - 0.15*turnover_penalty
"""

from __future__ import annotations

import polars as pl


class RepresentativeSelector:
    """簇内代表因子选择。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.n_per_cluster: int = self.config.get("n_per_cluster", 2)

    def _factor_cols(self, df: pl.DataFrame) -> list[str]:
        return [
            c for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

    def _normalize(self, values: list[float]) -> list[float]:
        """Min-max 归一化到 [0, 1]。"""
        min_v = min(values)
        max_v = max(values)
        rng = max_v - min_v
        if rng == 0:
            return [0.5] * len(values)
        return [(v - min_v) / rng for v in values]

    def process(
        self, df: pl.DataFrame, clusters: dict[str, int],
        ic_metrics: dict, stability: dict
    ) -> tuple[pl.DataFrame, dict]:
        """选择每簇的代表因子。

        Args:
            df: 当前 DataFrame。
            clusters: {因子名: 簇ID}。
            ic_metrics: Ring 2 输出。
            stability: Ring 4 输出。
        """
        factor_cols = self._factor_cols(df)

        # 簇分组
        cluster_to_factors: dict[int, list[str]] = {}
        for f, cid in clusters.items():
            if f in factor_cols:
                cluster_to_factors.setdefault(cid, []).append(f)

        selected = []
        selection_detail = []

        for cid in sorted(cluster_to_factors):
            factors = cluster_to_factors[cid]
            scores = []
            for f in factors:
                m = ic_metrics.get(f, {})
                s = stability.get(f, {})

                icir = abs(m.get("icir", 0))
                mono = abs(m.get("monotonicity", 0))
                ls = abs(m.get("long_short", 0))
                stab = s.get("stability_score", 0.5)

                scores.append({
                    "factor": f,
                    "icir": icir,
                    "monotonicity": mono,
                    "long_short": ls,
                    "stability": stab,
                })

            if len(scores) == 0:
                continue

            # 归一化 + 加权
            icir_norm = self._normalize([s["icir"] for s in scores])
            mono_norm = self._normalize([s["monotonicity"] for s in scores])
            ls_norm = self._normalize([s["long_short"] for s in scores])
            stab_norm = self._normalize([s["stability"] for s in scores])

            for i, s in enumerate(scores):
                s["score"] = (
                    0.30 * icir_norm[i]
                    + 0.20 * mono_norm[i]
                    + 0.20 * ls_norm[i]
                    + 0.30 * stab_norm[i]
                )

            # 按 score 降序取 top_k
            scores.sort(key=lambda x: x["score"], reverse=True)
            top = scores[: self.n_per_cluster]
            for t in top:
                selected.append(t["factor"])
                selection_detail.append({
                    "factor": t["factor"],
                    "cluster": cid,
                    "score": t["score"],
                    "rank_in_cluster": top.index(t) + 1,
                })

        # 剔除未选中的因子
        cols_to_drop = [c for c in factor_cols if c not in selected]
        if cols_to_drop:
            df = df.drop(cols_to_drop)

        report = {
            "selected": selected,
            "selection_detail": selection_detail,
            "selected_count": len(selected),
        }
        return df, report
```

**Step 2: 创建测试**

```python
import polars as pl
from src.pipelines.factor_filtering.steps.step06_representative import RepresentativeSelector


def test_representative_selection():
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-02"],
        "instrument": ["A", "B"],
        "f1": [1.0, 2.0],
        "f2": [1.1, 2.1],
        "f3": [5.0, 6.0],
        "label_20d": [0.01, 0.02],
    })
    clusters = {"f1": 0, "f2": 0, "f3": 1}
    ic_metrics = {
        "f1": {"icir": 0.5, "monotonicity": 0.3, "long_short": 0.01},
        "f2": {"icir": 0.3, "monotonicity": 0.2, "long_short": 0.005},
        "f3": {"icir": 0.8, "monotonicity": 0.6, "long_short": 0.03},
    }
    stability = {
        "f1": {"stability_score": 0.7},
        "f2": {"stability_score": 0.4},
        "f3": {"stability_score": 0.9},
    }

    step = RepresentativeSelector(n_per_cluster=1)
    result, report = step.process(df, clusters, ic_metrics, stability)
    assert report["selected_count"] == 2  # 2 clusters, 1 each
    assert "f1" in result.columns or "f2" in result.columns  # one from cluster 0
    assert "f3" in result.columns  # cluster 1's only factor
```

**Step 3: 运行测试**

Run: `pytest tests/pipelines/factor_filtering/test_step06_representative.py -v`
Expected: 1 test pass

**Step 4: Commit**

```bash
git add src/pipelines/factor_filtering/steps/step06_representative.py tests/pipelines/factor_filtering/test_step06_representative.py
git commit -m "feat(ring6): representative factor selection with composite scoring"
```

---

### Task 9: Ring 7 — PortfolioValidator

**Files:**
- Rename+Rewrite: `src/pipelines/factor_filtering/steps/step07_portfolio.py` (was step04_portfolio.py)
- Update: `tests/pipelines/factor_filtering/test_step07_portfolio.py` (was test_step04_portfolio.py)

**Step 1: 重写 step07_portfolio.py**

```python
"""Ring 7: 组合层验证。

构建等权/IC加权/ICIR加权多因子组合，验证多空收益、Sharpe、换手率。
"""

from __future__ import annotations

import polars as pl


class PortfolioValidator:
    """多因子组合验证。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def _factor_cols(self, df: pl.DataFrame) -> list[str]:
        return [
            c for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

    def _build_signal(self, df: pl.DataFrame, factor_cols: list[str], weights: dict[str, float]) -> pl.DataFrame:
        """构建加权合成信号。"""
        exprs = [
            (pl.col(f) * w).alias(f"_weighted_{f}")
            for f, w in weights.items() if f in factor_cols
        ]
        if not exprs:
            return df.with_columns(pl.lit(0.0).alias("signal"))

        signal_expr = sum(pl.col(f"_weighted_{f}") for f in weights if f in factor_cols)
        return df.with_columns(signal_expr.alias("signal"))

    def _compute_portfolio_ic(self, df: pl.DataFrame, label_col: str) -> dict:
        """计算组合信号的 IC 序列和汇总指标。"""
        daily = df.group_by("datetime").agg(
            pl.corr(pl.col("signal"), pl.col(label_col), method="spearman").alias("ic")
        ).drop_nulls()

        ic_series = daily.select(pl.col("ic")).to_series().drop_nulls()
        if len(ic_series) < 2:
            return {"mean_ic": 0.0, "icir": 0.0, "n_days": 0}

        mean_ic = ic_series.mean()
        std_ic = ic_series.std()
        icir = mean_ic / std_ic if std_ic > 0 else 0.0

        # 换手率：信号排名的一阶自相关
        if daily.height >= 2:
            turnover = 1.0 - abs(ic_series.autocorrelation(1) or 0)
        else:
            turnover = 0.0

        return {
            "mean_ic": float(mean_ic),
            "icir": float(icir),
            "ic_win_rate": float((ic_series > 0).sum() / len(ic_series)),
            "turnover": float(turnover),
            "n_days": len(ic_series),
        }

    def process(self, df: pl.DataFrame, ic_metrics: dict) -> tuple[pl.DataFrame, dict]:
        """构建 3 种组合并验证。"""
        factor_cols = self._factor_cols(df)
        label_col = next((c for c in df.columns if c.startswith("label")), None)
        if not label_col or not factor_cols:
            return df, {"error": "no factors or label"}

        total_abs_ic = sum(abs(ic_metrics.get(f, {}).get("mean_rank_ic", 0)) for f in factor_cols)
        total_icir = sum(ic_metrics.get(f, {}).get("icir", 0) for f in factor_cols)

        portfolios = {}
        for name, weight_fn in [
            ("equal_weight", lambda f: 1.0 / len(factor_cols)),
            ("ic_weight", lambda f: abs(ic_metrics.get(f, {}).get("mean_rank_ic", 0)) / max(total_abs_ic, 1e-8)),
            ("icir_weight", lambda f: ic_metrics.get(f, {}).get("icir", 0) / max(abs(total_icir), 1e-8)),
        ]:
            weights = {f: weight_fn(f) for f in factor_cols}
            sig_df = self._build_signal(df, factor_cols, weights)
            portfolios[name] = self._compute_portfolio_ic(sig_df, label_col)

        return df, {"portfolios": portfolios}
```

**Step 2: 更新测试**

```python
import polars as pl
from src.pipelines.factor_filtering.steps.step07_portfolio import PortfolioValidator


def test_portfolio_validation():
    dates = []
    instruments = []
    f1 = []
    label = []
    for d in range(20):
        for i in range(50):
            dates.append(f"2023-01-{d+1:02d}")
            instruments.append(f"INST_{i}")
            f1.append(float(i))
            label.append(float(i) / 50)

    df = pl.DataFrame({
        "datetime": dates,
        "instrument": instruments,
        "factor1": f1,
        "label_20d": label,
    })
    ic_metrics = {"factor1": {"mean_rank_ic": 0.05, "icir": 0.3}}
    step = PortfolioValidator()
    result, report = step.process(df, ic_metrics)
    assert "portfolios" in report
    assert "equal_weight" in report["portfolios"]
    assert "mean_ic" in report["portfolios"]["equal_weight"]
```

**Step 3: 运行测试**

Run: `pytest tests/pipelines/factor_filtering/test_step07_portfolio.py -v`
Expected: 1 test pass

**Step 4: Commit**

```bash
git rm src/pipelines/factor_filtering/steps/step04_portfolio.py
git add src/pipelines/factor_filtering/steps/step07_portfolio.py tests/pipelines/factor_filtering/test_step07_portfolio.py
git commit -m "feat(ring7): portfolio validation with equal/IC/ICIR weighted combinations"
```

---

### Task 10: Ring 8 — MLImportanceVerifier

**Files:**
- Rename+Rewrite: `src/pipelines/factor_filtering/steps/step08_ml_importance.py` (was step05_ml_importance.py)
- Update: `tests/pipelines/factor_filtering/test_step08_ml_importance.py` (was test_step05_ml_importance.py)

**Step 1: 重写 step08_ml_importance.py**

```python
"""Ring 8: 模型增量验证。

LightGBM 回归 + Permutation Importance 确认筛选后因子的增量信息。
"""

from __future__ import annotations

import polars as pl
import lightgbm as lgb


class MLImportanceVerifier:
    """模型增量信息验证。"""

    _META_COLS = {"datetime", "instrument"}

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.n_estimators: int = self.config.get("n_estimators", 50)
        self.random_state: int = self.config.get("random_state", 42)

    def _factor_cols(self, df: pl.DataFrame) -> list[str]:
        return [
            c for c in df.columns
            if c not in self._META_COLS and not c.startswith("label")
        ]

    def _permutation_importance(
        self, model, X: pl.DataFrame, y: pl.Series, factor_cols: list[str], n_repeats: int = 3
    ) -> dict[str, float]:
        """Permutation importance: 打乱每列后看 IC 下降。"""
        import numpy as np

        base_pred = model.predict(X.to_pandas())
        base_ic = float(pl.Series(base_pred).rank(method="average").corr(y.rank(method="average"), method="pearson"))

        importance = {}
        for col in factor_cols:
            ic_diffs = []
            for _ in range(n_repeats):
                X_shuffled = X.with_columns(pl.col(col).shuffle())
                pred = model.predict(X_shuffled.to_pandas())
                perm_ic = float(pl.Series(pred).rank(method="average").corr(y.rank(method="average"), method="pearson"))
                ic_diffs.append(base_ic - perm_ic)
            importance[col] = float(np.mean(ic_diffs))

        return importance

    def process(self, df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
        """训练 LightGBM 并计算重要性。"""
        factor_cols = self._factor_cols(df)
        label_col = next((c for c in df.columns if c.startswith("label")), None)
        if not label_col or len(factor_cols) == 0:
            return df, {"importance": {}, "permutation_importance": {}}

        valid = df.drop_nulls(subset=factor_cols + [label_col])
        if valid.height < 10:
            return df, {"importance": {c: 0.0 for c in factor_cols}, "permutation_importance": {c: 0.0 for c in factor_cols}}

        X = valid.select(factor_cols).to_pandas()
        y = valid.select(pl.col(label_col)).to_pandas().iloc[:, 0]

        model = lgb.LGBMRegressor(n_estimators=self.n_estimators, random_state=self.random_state, verbose=-1)
        model.fit(X, y)

        # Gain importance
        gain = {col: float(imp) for col, imp in zip(factor_cols, model.feature_importances_)}

        # Permutation importance
        perm = self._permutation_importance(model, valid.select(factor_cols), valid.select(pl.col(label_col)).to_series(), factor_cols)

        return df, {"importance": gain, "permutation_importance": perm}
```

**Step 2: 更新测试**

```python
import polars as pl
from src.pipelines.factor_filtering.steps.step08_ml_importance import MLImportanceVerifier


def test_ml_importance():
    dates = []
    instruments = []
    f1 = []
    f2 = []
    label = []
    for d in range(10):
        for i in range(20):
            dates.append(f"2023-01-{d+1:02d}")
            instruments.append(f"INST_{i}")
            f1.append(float(i))
            f2.append(float(200 - i))
            label.append(float(i) / 20)

    df = pl.DataFrame({
        "datetime": dates,
        "instrument": instruments,
        "factor1": f1,
        "factor2": f2,
        "label_20d": label,
    })
    step = MLImportanceVerifier(n_estimators=5)
    result, report = step.process(df)
    assert "importance" in report
    assert "factor1" in report["importance"]
```

**Step 3: 运行测试**

Run: `pytest tests/pipelines/factor_filtering/test_step08_ml_importance.py -v`
Expected: 1 test pass

**Step 4: Commit**

```bash
git rm src/pipelines/factor_filtering/steps/step05_ml_importance.py
git add src/pipelines/factor_filtering/steps/step08_ml_importance.py tests/pipelines/factor_filtering/test_step08_ml_importance.py
git commit -m "feat(ring8): ML importance with LightGBM gain + permutation importance"
```

---

### Task 11: 重写 pipeline.py 主编排器 + 报告生成

**Files:**
- Rewrite: `src/pipelines/factor_filtering/pipeline.py`

**Step 1: 重写 pipeline.py**

```python
"""因子筛选流水线主编排器 — 8 环责任链。"""

import json
import logging
from datetime import datetime
from pathlib import Path

import polars as pl

from pipelines.base import DataPipeline
from pipelines.factor_filtering.steps.step00_data_qa import DataAndLabelQA
from pipelines.factor_filtering.steps.step01_preprocess import PreprocessAndNeutralize
from pipelines.factor_filtering.steps.step02_profiling import SingleFactorProfiler
from pipelines.factor_filtering.steps.step03_cs_filter import CrossSectionFilter
from pipelines.factor_filtering.steps.step04_stability import StabilityChecker
from pipelines.factor_filtering.steps.step05_clustering import FactorClustering
from pipelines.factor_filtering.steps.step06_representative import RepresentativeSelector
from pipelines.factor_filtering.steps.step07_portfolio import PortfolioValidator
from pipelines.factor_filtering.steps.step08_ml_importance import MLImportanceVerifier


class FactorFilteringPipeline(DataPipeline):
    """8 环责任链因子筛选流水线。

    Stages: load → ring0_qa → ring1_preprocess → ring2_profile →
            ring3_filter → ring4_stability → ring5_cluster →
            ring6_select → ring7_portfolio → ring8_ml → report
    """

    STAGE_METHOD_MAP = {
        "load": "load_data",
        "ring0_qa": "run_data_qa",
        "ring1_preprocess": "run_preprocess",
        "ring2_profile": "run_profiling",
        "ring3_filter": "run_filter",
        "ring4_stability": "run_stability",
        "ring5_cluster": "run_clustering",
        "ring6_select": "run_selection",
        "ring7_portfolio": "run_portfolio",
        "ring8_ml": "run_ml_importance",
        "report": "generate_report",
    }

    def download(self): ...
    def validate(self): return []
    def clean(self): ...
    def ingest_to_qlib(self): ...

    def load_data(self):
        data_cfg = self.config.get("data", {})
        factor_path = data_cfg.get("factor_path", "data/alpha158_pool.parquet")
        self.label_col = data_cfg.get("label_col", "label_20d")
        self.df = pl.read_parquet(factor_path)
        logging.info(f"Loaded factor pool: {self.df.shape}")

    def run_data_qa(self):
        step = DataAndLabelQA(self.config.get("data", {}))
        self.df, self.qa_report = step.process(self.df)
        logging.info(f"Ring 0 QA done. Rejected: {len(self.qa_report.get('rejected', []))}")

    def run_preprocess(self):
        step = PreprocessAndNeutralize(self.config.get("preprocess", {}))
        self.df, self.preprocess_report = step.process(self.df)
        logging.info(f"Ring 1 preprocess done. Applied: {self.preprocess_report['transform_applied']}")

    def run_profiling(self):
        step = SingleFactorProfiler(label_col=self.label_col)
        self.df, self.ic_metrics = step.process(self.df)
        valid_ics = [abs(m["mean_rank_ic"]) for m in self.ic_metrics.values() if m.get("mean_rank_ic")]
        mean_ic = sum(valid_ics) / max(len(valid_ics), 1) if valid_ics else 0
        logging.info(f"Ring 2 profiling done. Mean |IC|={mean_ic:.4f} across {len(self.ic_metrics)} factors")

    def run_filter(self):
        filter_cfg = self.config.get("filter", {})
        step = CrossSectionFilter(filter_cfg)
        self.df, self.filter_report = step.process(self.df, self.ic_metrics)
        logging.info(f"Ring 3 filter done. Retained: {self.filter_report['retained_count']}, "
                     f"Rejected: {self.filter_report['rejected_count']}")

    def run_stability(self):
        step = StabilityChecker()
        self.df, self.stability_report = step.process(self.df)
        logging.info(f"Ring 4 stability done. Factors checked: {len(self.stability_report)}")

    def run_clustering(self):
        cluster_cfg = self.config.get("clustering", {})
        step = FactorClustering(cluster_cfg)
        self.df, self.cluster_report = step.process(self.df)
        logging.info(f"Ring 5 clustering done. {self.cluster_report['n_clusters']} clusters")

    def run_selection(self):
        rep_cfg = self.config.get("representative", {})
        step = RepresentativeSelector(rep_cfg)
        self.df, self.selection_report = step.process(
            self.df, self.cluster_report["clusters"], self.ic_metrics, self.stability_report
        )
        logging.info(f"Ring 6 selection done. Selected: {self.selection_report['selected_count']} factors")

    def run_portfolio(self):
        step = PortfolioValidator()
        self.df, self.portfolio_report = step.process(self.df, self.ic_metrics)
        logging.info(f"Ring 7 portfolio done. Portfolios: {list(self.portfolio_report.get('portfolios', {}).keys())}")

    def run_ml_importance(self):
        step = MLImportanceVerifier()
        self.df, self.ml_report = step.process(self.df)
        top3 = sorted(self.ml_report.get("importance", {}).items(), key=lambda x: x[1], reverse=True)[:3]
        logging.info(f"Ring 8 ML importance done. Top 3: {top3}")

    def generate_report(self):
        output_cfg = self.config.get("pipeline", {})
        output_dir = Path(output_cfg.get("output_dir", "data/reports/factor_filtering"))
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. Markdown report
        lines = []
        lines.append("# Factor Filtering Report (8-Ring Responsibility Chain)")
        lines.append("")
        lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Data Source**: {self.config.get('data', {}).get('factor_path', 'N/A')}")
        lines.append(f"**Label Column**: {self.label_col}")
        lines.append("")

        # Ring 0
        lines.append("## Ring 0: Data & Label QA")
        lines.append("")
        lines.append(f"- Total rows: {self.df.height}")
        lines.append(f"- Total columns: {self.df.width}")
        n_rejected = len(self.qa_report.get("rejected", []))
        lines.append(f"- Rejected factors: {n_rejected}")
        if n_rejected:
            lines.append("")
            for factor, reason in self.qa_report["rejected"]:
                lines.append(f"  - `{factor}`: {reason}")
        lines.append("")

        # Ring 1
        lines.append("## Ring 1: Preprocessing")
        lines.append("")
        lines.append(f"- Transforms applied: {self.preprocess_report.get('transform_applied', [])}")
        lines.append("")

        # Ring 2
        lines.append("## Ring 2: Single Factor Profiling (Top 20 by |IC|)")
        lines.append("")
        lines.append("| Rank | Factor | Mean IC | ICIR | Win Rate | Long-Short |")
        lines.append("|------|--------|---------|------|----------|------------|")
        sorted_ic = sorted(self.ic_metrics.items(), key=lambda x: abs(x[1].get("mean_rank_ic", 0)), reverse=True)
        for rank, (feat, m) in enumerate(sorted_ic[:20], 1):
            lines.append(
                f"| {rank} | {feat} | {m.get('mean_rank_ic', 0):.4f} | "
                f"{m.get('icir', 0):.4f} | {m.get('ic_win_rate', 0):.2%} | "
                f"{m.get('long_short', 0):.4f} |"
            )
        lines.append("")

        # Ring 3
        lines.append("## Ring 3: Cross-Section Filter")
        lines.append("")
        lines.append(f"- Retained: {self.filter_report.get('retained_count', 0)}")
        lines.append(f"- Rejected: {self.filter_report.get('rejected_count', 0)}")
        if self.filter_report.get("rejected"):
            lines.append("")
            lines.append("| Factor | Reason |")
            lines.append("|--------|--------|")
            for factor, reason in self.filter_report["rejected"]:
                lines.append(f"| {factor} | {reason} |")
        lines.append("")

        # Ring 4
        lines.append("## Ring 4: Stability (Top 10 by Stability Score)")
        lines.append("")
        lines.append("| Rank | Factor | Stability | Yearly IC Range |")
        lines.append("|------|--------|-----------|-----------------|")
        stable = sorted(self.stability_report.items(), key=lambda x: x[1].get("stability_score", 0), reverse=True)
        for rank, (feat, s) in enumerate(stable[:10], 1):
            yearly = s.get("yearly_ic", {})
            ic_range = f"{min(yearly.values()):.4f}~{max(yearly.values()):.4f}" if yearly else "N/A"
            lines.append(f"| {rank} | {feat} | {s.get('stability_score', 0):.4f} | {ic_range} |")
        lines.append("")

        # Ring 5+6
        lines.append("## Ring 5+6: Clustering & Representative Selection")
        lines.append("")
        lines.append(f"- Total clusters: {self.cluster_report.get('n_clusters', 0)}")
        lines.append(f"- Selected representatives: {self.selection_report.get('selected_count', 0)}")
        lines.append("")
        if self.selection_report.get("selection_detail"):
            lines.append("| Cluster | Factor | Score | Rank |")
            lines.append("|---------|--------|-------|------|")
            for d in self.selection_report["selection_detail"]:
                lines.append(
                    f"| {d['cluster']} | {d['factor']} | {d['score']:.4f} | {d['rank_in_cluster']} |"
                )
        lines.append("")

        # Ring 7
        lines.append("## Ring 7: Portfolio Validation")
        lines.append("")
        portfolios = self.portfolio_report.get("portfolios", {})
        lines.append("| Portfolio | Mean IC | ICIR | Win Rate | Turnover |")
        lines.append("|-----------|---------|------|----------|----------|")
        for name, m in portfolios.items():
            lines.append(
                f"| {name} | {m.get('mean_ic', 0):.4f} | {m.get('icir', 0):.4f} | "
                f"{m.get('ic_win_rate', 0):.2%} | {m.get('turnover', 0):.4f} |"
            )
        lines.append("")

        # Ring 8
        lines.append("## Ring 8: ML Importance (Top 10 by Gain)")
        lines.append("")
        lines.append("| Rank | Factor | Gain | Permutation IC Drop |")
        lines.append("|------|--------|------|---------------------|")
        perm_imp = self.ml_report.get("permutation_importance", {})
        gain_imp = self.ml_report.get("importance", {})
        sorted_gain = sorted(gain_imp.items(), key=lambda x: x[1], reverse=True)
        for rank, (feat, gain) in enumerate(sorted_gain[:10], 1):
            perm_val = perm_imp.get(feat, 0)
            lines.append(f"| {rank} | {feat} | {gain} | {perm_val:.4f} |")
        lines.append("")

        report_path = output_dir / "factor_filter_report.md"
        report_path.write_text("\n".join(lines), encoding="utf-8")
        logging.info(f"Report saved to {report_path}")

        # 2. Filtered factor pool parquet
        factor_cols = [c for c in self.df.columns if c not in ("datetime", "instrument") and not c.startswith("label")]
        all_cols = ["datetime", "instrument"] + factor_cols + [c for c in self.df.columns if c.startswith("label")]
        final_df = self.df.select([c for c in all_cols if c in self.df.columns])
        filtered_path = output_dir / "factor_pool_filtered.parquet"
        final_df.write_parquet(filtered_path)
        logging.info(f"Filtered factor pool saved to {filtered_path} ({len(factor_cols)} factors)")

        # 3. Selection log JSON
        selection_log = {
            "qa": self.qa_report,
            "filter": self.filter_report,
            "stability": {k: {kk: vv for kk, vv in v.items() if kk != "yearly_ic"} for k, v in self.stability_report.items()},
            "clusters": self.cluster_report,
            "selection": self.selection_report,
            "portfolios": self.portfolio_report,
            "ml_importance": {"importance": self.ml_report.get("importance", {}), "permutation_importance": self.ml_report.get("permutation_importance", {})},
        }
        log_path = output_dir / "factor_selection_log.json"
        # 处理 JSON 不序列化的值
        import json
        class NumpyEncoder(json.JSONEncoder):
            def default(self, obj):
                import numpy as np
                if isinstance(obj, (np.integer,)): return int(obj)
                if isinstance(obj, (np.floating,)): return float(obj)
                if isinstance(obj, (np.ndarray,)): return obj.tolist()
                return super().default(obj)
        log_path.write_text(json.dumps(selection_log, indent=2, cls=NumpyEncoder, default=str), encoding="utf-8")
        logging.info(f"Selection log saved to {log_path}")
```

**Step 2: 更新 pipeline 测试**

```python
import pytest
from src.pipelines.factor_filtering.pipeline import FactorFilteringPipeline


def test_pipeline_initialization():
    pipeline = FactorFilteringPipeline(config_path="configs/factor_filtering.yaml")
    assert pipeline.config is not None
    assert len(pipeline.stages) == 11
    assert "ring0_qa" in pipeline.stages
    assert "ring8_ml" in pipeline.stages
```

**Step 3: 运行测试**

Run: `pytest tests/pipelines/factor_filtering/test_pipeline.py -v`
Expected: 1 test pass

**Step 4: Commit**

```bash
git add src/pipelines/factor_filtering/pipeline.py tests/pipelines/factor_filtering/test_pipeline.py
git commit -m "feat: rewrite pipeline orchestrator with 8-ring responsibility chain"
```

---

### Task 12: 集成测试 — 全链路运行

**Step 1: 更新配置中的 stages**

configs/factor_filtering.yaml 在 Task 1 已更新，确认 stages 列表正确。

**Step 2: 全链路运行**

Run: `uv run python scripts/run_pipeline.py --config configs/factor_filtering.yaml`
Expected: 所有 11 个 stage 依次执行，无报错

**Step 3: 验证产物**

```bash
ls -la data/reports/factor_filtering/
# 应包含：
# - factor_filter_report.md
# - factor_pool_filtered.parquet
# - factor_selection_log.json
```

Run: `python -c "import polars as pl; df=pl.read_parquet('data/reports/factor_filtering/factor_pool_filtered.parquet'); print(df.shape)"`
Expected: 列数 < 164（原始 158 因子 + 6 元数据），说明因子被真实剔除

**Step 4: 运行全部测试**

Run: `pytest tests/pipelines/factor_filtering/ -v`
Expected: 所有测试 pass

**Step 5: Commit**

```bash
git add data/reports/factor_filtering/
git commit -m "test: integration run of 8-ring factor filtering pipeline"
```

---

## 执行顺序总结

```
Task 1  → 更新 config
Task 2  → Ring 0 (QA)
Task 3  → Ring 1 (Preprocess)
Task 4  → Ring 2 (Profiling)
Task 5  → Ring 3 (Filter)
Task 6  → Ring 4 (Stability)
Task 7  → Ring 5 (Clustering)
Task 8  → Ring 6 (Representative)
Task 9  → Ring 7 (Portfolio)
Task 10 → Ring 8 (ML Importance)
Task 11 → 主编排器 + 报告
Task 12 → 集成测试
```

每个 Task 独立可测试、可 commit。依赖关系：
- Task 4 依赖 Task 2 的指标格式
- Task 5 依赖 Task 4 的指标输入
- Task 8 依赖 Task 7 的簇输出
- Task 11 依赖 Task 2-10 的所有 step 文件存在
