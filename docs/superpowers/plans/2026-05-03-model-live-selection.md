# Model Live Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在模型 pipeline 最后新增独立实盘筛选器，按硬约束和综合评分保留最佳可实盘候选模型及参数。

**Architecture:** 新增 `src/pipelines/model/selector.py` 作为独立判断单元；`ModelPipeline` 只负责调用 selector、写出 JSON 审计文件、在静态和滚动报告中渲染选择结果。测试先覆盖 selector 的硬约束、评分、异常指标和无候选场景，再覆盖 pipeline 报告集成。

**Tech Stack:** Python 3.12, dataclasses, pandas/numpy, pytest, existing `TrainingResult` and `ModelPipeline` interfaces.

---

## 文件结构

- Create: `src/pipelines/model/selector.py`
  - 定义 `SelectionCandidate`、`SelectionResult`、`LiveModelSelector`。
  - 负责默认配置合并、指标抽取、硬约束、rank percentile 综合评分、JSON 序列化。
- Create: `tests/pipelines/model/test_selector.py`
  - 独立测试 selector 的所有核心判断。
- Modify: `src/pipelines/model/model_pipeline.py`
  - 导入 selector。
  - 在 `generate_report()` 内先计算 `self.selection_result`。
  - 新增写出 `model_selection.json` 的方法。
  - 新增 Markdown section 渲染方法，并插入静态和滚动报告。
- Modify: `configs/model_pipeline.yaml`
  - 扩展 `selection` 配置，保留兼容默认值。
- Modify: `tests/pipelines/model/test_pipeline_integration.py`
  - 增加一个轻量报告集成测试，验证报告文本和 JSON 输出。

---

### Task 1: Selector 数据结构与默认配置

**Files:**
- Create: `src/pipelines/model/selector.py`
- Test: `tests/pipelines/model/test_selector.py`

- [ ] **Step 1: 写失败测试，验证默认配置和空结果**

Create `tests/pipelines/model/test_selector.py` with:

```python
import math
from types import SimpleNamespace

import pytest

from pipelines.model.selector import LiveModelSelector, SelectionResult


def test_empty_results_returns_empty_selection():
    selector = LiveModelSelector(config={})

    result = selector.select([])

    assert isinstance(result, SelectionResult)
    assert result.best is None
    assert result.candidates == []
    assert result.rejected == []
    assert result.config["constraints"]["min_oos_ic"] == 0.0
    assert result.config["weights"]["oos_icir"] == pytest.approx(0.30)
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/pipelines/model/test_selector.py::test_empty_results_returns_empty_selection -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pipelines.model.selector'`.

- [ ] **Step 3: 实现最小 selector 结构**

Create `src/pipelines/model/selector.py`:

```python
"""Live-trading model selection for model pipeline results."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_CONSTRAINTS = {
    "min_oos_ic": 0.0,
    "min_oos_icir": 0.0,
    "min_ann_excess_return": 0.0,
    "min_excess_sharpe": 0.0,
    "max_drawdown": -0.25,
    "max_avg_turnover": 0.8,
    "min_positive_ratio": 0.52,
    "min_rolling_windows": 3,
}

DEFAULT_WEIGHTS = {
    "oos_icir": 0.30,
    "excess_sharpe": 0.30,
    "ann_excess_return": 0.20,
    "positive_ratio": 0.10,
    "drawdown": 0.05,
    "turnover": 0.05,
}


@dataclass
class SelectionCandidate:
    """One model/label candidate with live-selection audit details."""

    model_name: str
    label_name: str
    params: dict[str, Any]
    passed: bool
    score: float
    rank: int | None
    metrics: dict[str, float]
    constraint_results: dict[str, bool]
    rejection_reasons: list[str]
    direction: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["score"] = _json_float(self.score)
        data["metrics"] = {k: _json_float(v) for k, v in self.metrics.items()}
        return data


@dataclass
class SelectionResult:
    """Selection output for markdown reports and JSON audit files."""

    best: SelectionCandidate | None
    candidates: list[SelectionCandidate]
    rejected: list[SelectionCandidate]
    config: dict[str, Any]
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "best": self.best.to_dict() if self.best else None,
            "candidates": [c.to_dict() for c in self.candidates],
            "rejected": [c.to_dict() for c in self.rejected],
            "selection_config": self.config,
            "generated_at": self.generated_at,
        }


class LiveModelSelector:
    """Apply live-trading constraints and rank surviving model results."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = self._merge_config(config or {})

    def select(self, results: list[Any]) -> SelectionResult:
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not results:
            return SelectionResult(
                best=None,
                candidates=[],
                rejected=[],
                config=self.config,
                generated_at=generated_at,
            )

        raw_candidates = [self._build_candidate(result) for result in results]
        passed = [candidate for candidate in raw_candidates if candidate.passed]
        rejected = [candidate for candidate in raw_candidates if not candidate.passed]
        ranked = self._score_candidates(passed)
        best = ranked[0] if ranked else None
        return SelectionResult(
            best=best,
            candidates=ranked,
            rejected=rejected,
            config=self.config,
            generated_at=generated_at,
        )

    @staticmethod
    def _merge_config(config: dict[str, Any]) -> dict[str, Any]:
        constraints = DEFAULT_CONSTRAINTS.copy()
        constraints.update(config.get("constraints", {}))

        weights = DEFAULT_WEIGHTS.copy()
        weights.update(config.get("weights", {}))
        weights = _normalize_weights(weights)

        merged = {
            "mode": config.get("mode", "live"),
            "primary_metric": config.get("primary_metric", "live_score"),
            "constraints": constraints,
            "weights": weights,
        }
        return merged

    def _build_candidate(self, result: Any) -> SelectionCandidate:
        raise NotImplementedError("Task 2 implements candidate construction")

    def _score_candidates(self, candidates: list[SelectionCandidate]) -> list[SelectionCandidate]:
        return candidates


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    clean = {
        key: float(value)
        for key, value in weights.items()
        if key in DEFAULT_WEIGHTS and _is_finite_number(value) and float(value) > 0
    }
    total = sum(clean.values())
    if total <= 0:
        return DEFAULT_WEIGHTS.copy()
    return {key: value / total for key, value in clean.items()}


def _is_finite_number(value: Any) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _json_float(value: Any) -> float | None:
    if not _is_finite_number(value):
        return None
    return float(value)
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/pipelines/model/test_selector.py::test_empty_results_returns_empty_selection -v
```

Expected: PASS.

- [ ] **Step 5: 提交**

```bash
git add src/pipelines/model/selector.py tests/pipelines/model/test_selector.py
git commit -m "feat: add live model selector shell"
```

---

### Task 2: 候选指标抽取与硬约束

**Files:**
- Modify: `src/pipelines/model/selector.py`
- Modify: `tests/pipelines/model/test_selector.py`

- [ ] **Step 1: 写失败测试，验证通过候选和剔除原因**

Append to `tests/pipelines/model/test_selector.py`:

```python
def _result(
    model_name="lgbm_ranker",
    label_name="label_5d",
    params=None,
    test_metrics=None,
    backtest_metrics=None,
    metadata=None,
    direction=1,
):
    model = SimpleNamespace(params=params or {"num_leaves": 31, "learning_rate": 0.05})
    return SimpleNamespace(
        model_name=model_name,
        label_name=label_name,
        model=model,
        test_metrics=test_metrics
        or {"ic_mean": 0.03, "icir": 0.80, "positive_ratio": 0.58},
        backtest_metrics=backtest_metrics
        or {
            "ann_excess_return": 0.12,
            "excess_sharpe": 1.10,
            "max_drawdown": -0.12,
            "avg_turnover": 0.35,
        },
        oriented_direction=direction,
        metadata=metadata or {},
    )


def test_candidate_passes_all_live_constraints():
    selector = LiveModelSelector(config={})

    result = selector.select([_result()])

    assert result.best is not None
    assert result.best.model_name == "lgbm_ranker"
    assert result.best.label_name == "label_5d"
    assert result.best.passed is True
    assert result.best.rejection_reasons == []
    assert result.best.metrics["oos_ic"] == pytest.approx(0.03)
    assert result.best.metrics["excess_sharpe"] == pytest.approx(1.10)
    assert result.best.params["num_leaves"] == 31


def test_candidate_rejected_with_specific_reasons():
    selector = LiveModelSelector(config={})
    weak = _result(
        test_metrics={"ic_mean": -0.01, "icir": -0.20, "positive_ratio": 0.45},
        backtest_metrics={
            "ann_excess_return": -0.03,
            "excess_sharpe": -0.40,
            "max_drawdown": -0.31,
            "avg_turnover": 1.10,
        },
    )

    result = selector.select([weak])

    assert result.best is None
    assert len(result.rejected) == 1
    reasons = result.rejected[0].rejection_reasons
    assert "oos_ic -0.0100 <= min_oos_ic 0.0000" in reasons
    assert "oos_icir -0.2000 <= min_oos_icir 0.0000" in reasons
    assert "ann_excess_return -0.0300 <= min_ann_excess_return 0.0000" in reasons
    assert "excess_sharpe -0.4000 <= min_excess_sharpe 0.0000" in reasons
    assert "max_drawdown -0.3100 < max_drawdown -0.2500" in reasons
    assert "avg_turnover 1.1000 > max_avg_turnover 0.8000" in reasons
    assert "positive_ratio 0.4500 < min_positive_ratio 0.5200" in reasons
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/pipelines/model/test_selector.py -v
```

Expected: FAIL with `NotImplementedError: Task 2 implements candidate construction`.

- [ ] **Step 3: 实现指标抽取和硬约束**

Replace `_build_candidate` in `src/pipelines/model/selector.py` and add helper methods:

```python
    def _build_candidate(self, result: Any) -> SelectionCandidate:
        metrics = self._extract_metrics(result)
        constraint_results, rejection_reasons = self._check_constraints(metrics, result)
        passed = all(constraint_results.values())
        model = getattr(result, "model", None)
        params = getattr(model, "params", None) or {}

        return SelectionCandidate(
            model_name=getattr(result, "model_name", ""),
            label_name=getattr(result, "label_name", ""),
            params=dict(params),
            passed=passed,
            score=float("nan"),
            rank=None,
            metrics=metrics,
            constraint_results=constraint_results,
            rejection_reasons=rejection_reasons,
            direction=int(getattr(result, "oriented_direction", 1)),
            metadata=dict(getattr(result, "metadata", {}) or {}),
        )

    @staticmethod
    def _extract_metrics(result: Any) -> dict[str, float]:
        test_metrics = getattr(result, "test_metrics", {}) or {}
        backtest_metrics = getattr(result, "backtest_metrics", {}) or {}
        return {
            "oos_ic": _metric(test_metrics, "ic_mean"),
            "oos_icir": _metric(test_metrics, "icir"),
            "positive_ratio": _metric(test_metrics, "positive_ratio"),
            "ann_excess_return": _metric(backtest_metrics, "ann_excess_return"),
            "excess_sharpe": _metric(backtest_metrics, "excess_sharpe"),
            "max_drawdown": _metric(backtest_metrics, "max_drawdown"),
            "avg_turnover": _metric(backtest_metrics, "avg_turnover"),
        }

    def _check_constraints(
        self,
        metrics: dict[str, float],
        result: Any,
    ) -> tuple[dict[str, bool], list[str]]:
        constraints = self.config["constraints"]
        checks: dict[str, bool] = {}
        reasons: list[str] = []

        self._check_min("oos_ic", metrics["oos_ic"], constraints["min_oos_ic"], checks, reasons)
        self._check_min("oos_icir", metrics["oos_icir"], constraints["min_oos_icir"], checks, reasons)
        self._check_min(
            "ann_excess_return",
            metrics["ann_excess_return"],
            constraints["min_ann_excess_return"],
            checks,
            reasons,
        )
        self._check_min(
            "excess_sharpe",
            metrics["excess_sharpe"],
            constraints["min_excess_sharpe"],
            checks,
            reasons,
        )
        self._check_min(
            "positive_ratio",
            metrics["positive_ratio"],
            constraints["min_positive_ratio"],
            checks,
            reasons,
            fail_operator="<",
        )
        self._check_floor(
            "max_drawdown",
            metrics["max_drawdown"],
            constraints["max_drawdown"],
            checks,
            reasons,
        )
        self._check_max(
            "avg_turnover",
            metrics["avg_turnover"],
            constraints["max_avg_turnover"],
            checks,
            reasons,
        )

        metadata = getattr(result, "metadata", {}) or {}
        if metadata.get("rolling"):
            n_windows = metadata.get("n_windows")
            min_windows = constraints["min_rolling_windows"]
            ok = _is_finite_number(n_windows) and float(n_windows) >= float(min_windows)
            checks["min_rolling_windows"] = ok
            if not ok:
                reasons.append(f"n_windows {n_windows} < min_rolling_windows {min_windows}")

        return checks, reasons

    @staticmethod
    def _check_min(
        name: str,
        value: float,
        threshold: float,
        checks: dict[str, bool],
        reasons: list[str],
        fail_operator: str = "<=",
    ) -> None:
        ok = _is_finite_number(value) and float(value) > float(threshold)
        checks[name] = ok
        if not ok:
            if not _is_finite_number(value):
                reasons.append(f"{name} is missing")
            else:
                reasons.append(f"{name} {float(value):.4f} {fail_operator} {name_to_min(name)} {float(threshold):.4f}")

    @staticmethod
    def _check_floor(
        name: str,
        value: float,
        threshold: float,
        checks: dict[str, bool],
        reasons: list[str],
    ) -> None:
        ok = _is_finite_number(value) and float(value) >= float(threshold)
        checks[name] = ok
        if not ok:
            if not _is_finite_number(value):
                reasons.append(f"{name} is missing")
            else:
                reasons.append(f"{name} {float(value):.4f} < {name} {float(threshold):.4f}")

    @staticmethod
    def _check_max(
        name: str,
        value: float,
        threshold: float,
        checks: dict[str, bool],
        reasons: list[str],
    ) -> None:
        ok = _is_finite_number(value) and float(value) <= float(threshold)
        checks[name] = ok
        if not ok:
            if not _is_finite_number(value):
                reasons.append(f"{name} is missing")
            else:
                reasons.append(f"{name} {float(value):.4f} > max_{name} {float(threshold):.4f}")
```

Add these module-level helpers:

```python
def _metric(metrics: dict[str, Any], key: str) -> float:
    value = metrics.get(key, np.nan)
    return float(value) if _is_finite_number(value) else float("nan")


def name_to_min(name: str) -> str:
    mapping = {
        "oos_ic": "min_oos_ic",
        "oos_icir": "min_oos_icir",
        "ann_excess_return": "min_ann_excess_return",
        "excess_sharpe": "min_excess_sharpe",
        "positive_ratio": "min_positive_ratio",
    }
    return mapping[name]
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/pipelines/model/test_selector.py -v
```

Expected: PASS.

- [ ] **Step 5: 提交**

```bash
git add src/pipelines/model/selector.py tests/pipelines/model/test_selector.py
git commit -m "feat: apply live selection constraints"
```

---

### Task 3: 综合评分、排序和异常权重

**Files:**
- Modify: `src/pipelines/model/selector.py`
- Modify: `tests/pipelines/model/test_selector.py`

- [ ] **Step 1: 写失败测试，验证评分排序、NaN 剔除、异常权重回退**

Append to `tests/pipelines/model/test_selector.py`:

```python
def test_passed_candidates_are_ranked_by_live_score():
    selector = LiveModelSelector(config={})
    stable = _result(
        model_name="stable",
        test_metrics={"ic_mean": 0.025, "icir": 1.20, "positive_ratio": 0.64},
        backtest_metrics={
            "ann_excess_return": 0.09,
            "excess_sharpe": 1.40,
            "max_drawdown": -0.08,
            "avg_turnover": 0.20,
        },
    )
    noisy = _result(
        model_name="noisy",
        test_metrics={"ic_mean": 0.040, "icir": 0.60, "positive_ratio": 0.54},
        backtest_metrics={
            "ann_excess_return": 0.14,
            "excess_sharpe": 0.50,
            "max_drawdown": -0.20,
            "avg_turnover": 0.70,
        },
    )

    result = selector.select([noisy, stable])

    assert [candidate.rank for candidate in result.candidates] == [1, 2]
    assert result.best.model_name == "stable"
    assert result.candidates[0].score > result.candidates[1].score


def test_nan_metrics_are_rejected_as_missing():
    selector = LiveModelSelector(config={})
    bad = _result(test_metrics={"ic_mean": math.nan, "icir": 0.3, "positive_ratio": 0.6})

    result = selector.select([bad])

    assert result.best is None
    assert "oos_ic is missing" in result.rejected[0].rejection_reasons


def test_invalid_weights_fall_back_to_defaults():
    selector = LiveModelSelector(config={"weights": {"oos_icir": 0, "excess_sharpe": -1}})

    assert selector.config["weights"] == {
        "oos_icir": 0.30,
        "excess_sharpe": 0.30,
        "ann_excess_return": 0.20,
        "positive_ratio": 0.10,
        "drawdown": 0.05,
        "turnover": 0.05,
    }
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/pipelines/model/test_selector.py -v
```

Expected: FAIL because passed candidates are not scored or ranked.

- [ ] **Step 3: 实现 rank percentile 评分**

Replace `_score_candidates` in `src/pipelines/model/selector.py`:

```python
    def _score_candidates(self, candidates: list[SelectionCandidate]) -> list[SelectionCandidate]:
        if not candidates:
            return []

        frame = pd.DataFrame(
            [
                {
                    "idx": idx,
                    "oos_icir": candidate.metrics["oos_icir"],
                    "excess_sharpe": candidate.metrics["excess_sharpe"],
                    "ann_excess_return": candidate.metrics["ann_excess_return"],
                    "positive_ratio": candidate.metrics["positive_ratio"],
                    "drawdown": 1.0 + candidate.metrics["max_drawdown"],
                    "turnover": 1.0
                    - min(
                        candidate.metrics["avg_turnover"]
                        / self.config["constraints"]["max_avg_turnover"],
                        1.0,
                    ),
                }
                for idx, candidate in enumerate(candidates)
            ]
        ).set_index("idx")

        ranks = frame.rank(pct=True, method="average")
        weights = self.config["weights"]
        scores = sum(ranks[column] * weight for column, weight in weights.items())

        scored: list[SelectionCandidate] = []
        for idx, candidate in enumerate(candidates):
            candidate.score = float(scores.loc[idx])
            scored.append(candidate)

        scored.sort(
            key=lambda candidate: (
                candidate.score,
                candidate.metrics.get("excess_sharpe", float("-inf")),
                candidate.metrics.get("oos_icir", float("-inf")),
            ),
            reverse=True,
        )
        for rank, candidate in enumerate(scored, 1):
            candidate.rank = rank
        return scored
```

Replace `_merge_config` so `_normalize_weights` can distinguish missing weights from explicitly invalid supplied weights:

```python
    @staticmethod
    def _merge_config(config: dict[str, Any]) -> dict[str, Any]:
        constraints = DEFAULT_CONSTRAINTS.copy()
        constraints.update(config.get("constraints", {}))

        weights = _normalize_weights(config.get("weights"))

        merged = {
            "mode": config.get("mode", "live"),
            "primary_metric": config.get("primary_metric", "live_score"),
            "constraints": constraints,
            "weights": weights,
        }
        return merged
```

Replace `_normalize_weights` to ensure all invalid/zero supplied weights fall back to defaults:

```python
def _normalize_weights(weights: dict[str, float] | None) -> dict[str, float]:
    if not weights:
        return DEFAULT_WEIGHTS.copy()

    supplied_positive = [
        key
        for key, value in weights.items()
        if key in DEFAULT_WEIGHTS and _is_finite_number(value) and float(value) > 0
    ]
    if not supplied_positive:
        return DEFAULT_WEIGHTS.copy()

    merged = DEFAULT_WEIGHTS.copy()
    for key, value in weights.items():
        if key in DEFAULT_WEIGHTS and _is_finite_number(value) and float(value) > 0:
            merged[key] = float(value)

    total = sum(merged.values())
    if total <= 0:
        return DEFAULT_WEIGHTS.copy()
    return {key: merged[key] / total for key in DEFAULT_WEIGHTS}
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
uv run pytest tests/pipelines/model/test_selector.py -v
```

Expected: PASS.

- [ ] **Step 5: 提交**

```bash
git add src/pipelines/model/selector.py tests/pipelines/model/test_selector.py
git commit -m "feat: score live model candidates"
```

---

### Task 4: Pipeline 集成和 JSON 审计输出

**Files:**
- Modify: `src/pipelines/model/model_pipeline.py`
- Modify: `tests/pipelines/model/test_pipeline_integration.py`

- [ ] **Step 1: 写失败测试，验证报告阶段写出 JSON**

Append to `tests/pipelines/model/test_pipeline_integration.py`:

```python
from types import SimpleNamespace

from pipelines.model.model_pipeline import ModelPipeline, TrainingResult


def test_report_writes_live_selection_json(tmp_path):
    pipeline = ModelPipeline(config={
        "output": {
            "report": str(tmp_path / "model_report.md"),
            "selection": str(tmp_path / "model_selection.json"),
        },
        "selection": {
            "mode": "live",
        },
    })
    model = SimpleNamespace(params={"num_leaves": 31})
    pipeline.results = [
        TrainingResult(
            model_name="lgbm_ranker",
            label_name="label_5d",
            model=model,
            test_metrics={"ic_mean": 0.03, "icir": 0.80, "positive_ratio": 0.58},
            backtest_metrics={
                "ann_excess_return": 0.12,
                "excess_sharpe": 1.10,
                "max_drawdown": -0.12,
                "avg_turnover": 0.35,
            },
            oriented_direction=1,
        )
    ]

    pipeline.generate_report()

    report_text = (tmp_path / "model_report.md").read_text(encoding="utf-8")
    selection_text = (tmp_path / "model_selection.json").read_text(encoding="utf-8")
    assert "Live Trading Selection" in report_text
    assert "Best Live Candidate" in report_text
    assert '"model_name": "lgbm_ranker"' in selection_text
    assert '"label_name": "label_5d"' in selection_text
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/pipelines/model/test_pipeline_integration.py::test_report_writes_live_selection_json -v
```

Expected: FAIL because `model_selection.json` is not created and report lacks the new section.

- [ ] **Step 3: 接入 selector 并写 JSON**

Modify imports at top of `src/pipelines/model/model_pipeline.py`:

```python
import json
```

Add after existing model imports:

```python
from pipelines.model.selector import LiveModelSelector, SelectionResult
```

Modify `generate_report`:

```python
    def generate_report(self):
        self.selection_result = self._run_live_selection()
        self._write_selection_json(self.selection_result)
        if "rolling" in self.config:
            self._generate_rolling_report()
        else:
            self._generate_static_report()
```

Add helper methods inside `ModelPipeline` before `_generate_rolling_report`:

```python
    def _run_live_selection(self) -> SelectionResult:
        selector = LiveModelSelector(self.config.get("selection", {}))
        return selector.select(getattr(self, "results", []))

    def _write_selection_json(self, selection_result: SelectionResult) -> None:
        output_cfg = self.config.get("output", {})
        default_dir = Path(output_cfg.get("dir", "data/model_results"))
        selection_path = Path(output_cfg.get("selection", default_dir / "model_selection.json"))
        selection_path.parent.mkdir(parents=True, exist_ok=True)
        selection_path.write_text(
            json.dumps(selection_result.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logging.info(f"Model selection saved to {selection_path}")
```

- [ ] **Step 4: 运行测试确认仍失败在报告章节**

Run:

```bash
uv run pytest tests/pipelines/model/test_pipeline_integration.py::test_report_writes_live_selection_json -v
```

Expected: FAIL because JSON exists but report does not yet contain `Live Trading Selection`.

- [ ] **Step 5: 提交集成骨架**

```bash
git add src/pipelines/model/model_pipeline.py tests/pipelines/model/test_pipeline_integration.py
git commit -m "feat: write live selection audit json"
```

---

### Task 5: Markdown 报告渲染

**Files:**
- Modify: `src/pipelines/model/model_pipeline.py`
- Modify: `tests/pipelines/model/test_pipeline_integration.py`

- [ ] **Step 1: 扩展测试，验证剔除候选也进入报告**

Extend `test_report_writes_live_selection_json` in `tests/pipelines/model/test_pipeline_integration.py` by adding a rejected result to `pipeline.results`:

```python
    pipeline.results.append(
        TrainingResult(
            model_name="lgbm_regressor",
            label_name="label_1d",
            model=SimpleNamespace(params={"num_leaves": 15}),
            test_metrics={"ic_mean": -0.01, "icir": -0.20, "positive_ratio": 0.40},
            backtest_metrics={
                "ann_excess_return": -0.02,
                "excess_sharpe": -0.10,
                "max_drawdown": -0.30,
                "avg_turnover": 1.20,
            },
            oriented_direction=-1,
        )
    )
```

Then add assertions after reading report:

```python
    assert "Passed Candidates" in report_text
    assert "Rejected Candidates" in report_text
    assert "lgbm_regressor" in report_text
    assert "oos_ic -0.0100 <= min_oos_ic 0.0000" in report_text
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/pipelines/model/test_pipeline_integration.py::test_report_writes_live_selection_json -v
```

Expected: FAIL because report rendering helper does not exist.

- [ ] **Step 3: 新增报告渲染 helper**

Add these methods to `src/pipelines/model/model_pipeline.py`:

```python
    def _append_live_selection_section(self, lines: list[str]) -> None:
        selection = getattr(self, "selection_result", None)
        if selection is None:
            return

        lines.append("## Live Trading Selection")
        lines.append("")

        if selection.best is None:
            lines.append("### Best Live Candidate")
            lines.append("")
            lines.append("No model passed the live-trading constraints.")
            lines.append("")
        else:
            best = selection.best
            lines.append(f"### Best Live Candidate: {best.model_name} + {best.label_name}")
            lines.append("")
            lines.append(f"- Live score: {best.score:.4f}")
            lines.append(f"- Rank: {best.rank}")
            lines.append(f"- Signal direction: {'original' if best.direction == 1 else 'flipped'}")
            lines.append(f"- OOS IC: {best.metrics.get('oos_ic', 0):.4f}")
            lines.append(f"- OOS ICIR: {best.metrics.get('oos_icir', 0):.4f}")
            lines.append(f"- OOS positive ratio: {best.metrics.get('positive_ratio', 0):.2%}")
            lines.append(f"- Ann excess return: {best.metrics.get('ann_excess_return', 0)*100:.2f}%")
            lines.append(f"- Excess Sharpe: {best.metrics.get('excess_sharpe', 0):.2f}")
            lines.append(f"- Max drawdown: {best.metrics.get('max_drawdown', 0)*100:.2f}%")
            lines.append(f"- Avg turnover: {best.metrics.get('avg_turnover', 0):.3f}")
            lines.append(f"- Params: `{json.dumps(best.params, ensure_ascii=False, sort_keys=True)}`")
            lines.append("")

        lines.append("### Passed Candidates")
        lines.append("")
        lines.append("| Rank | Model | Label | Score | OOS ICIR | Excess Sharpe | Ann Excess | Max DD | Turnover |")
        lines.append("|------|-------|-------|-------|----------|---------------|------------|--------|----------|")
        if not selection.candidates:
            lines.append("| - | - | - | - | - | - | - | - | - |")
        else:
            for candidate in selection.candidates:
                m = candidate.metrics
                lines.append(
                    f"| {candidate.rank} | {candidate.model_name} | {candidate.label_name} | "
                    f"{candidate.score:.4f} | {m.get('oos_icir', 0):.4f} | "
                    f"{m.get('excess_sharpe', 0):.2f} | "
                    f"{m.get('ann_excess_return', 0)*100:.2f}% | "
                    f"{m.get('max_drawdown', 0)*100:.2f}% | "
                    f"{m.get('avg_turnover', 0):.3f} |"
                )
        lines.append("")

        lines.append("### Rejected Candidates")
        lines.append("")
        lines.append("| Model | Label | Reasons |")
        lines.append("|-------|-------|---------|")
        if not selection.rejected:
            lines.append("| - | - | - |")
        else:
            for candidate in selection.rejected:
                reasons = "; ".join(candidate.rejection_reasons)
                lines.append(f"| {candidate.model_name} | {candidate.label_name} | {reasons} |")
        lines.append("")

        lines.append("### Selection Constraints")
        lines.append("")
        lines.append("| Constraint | Value |")
        lines.append("|------------|-------|")
        for key, value in selection.config.get("constraints", {}).items():
            lines.append(f"| {key} | {value} |")
        lines.append("")
```

- [ ] **Step 4: 插入静态和滚动报告**

In `_generate_rolling_report`, insert before feature importance / final write:

```python
        self._append_live_selection_section(lines)
```

A safe location is after Unified OOS Backtest and before the old Best Model section.

In `_generate_static_report`, insert after Out-of-Sample TopK Performance and before old Best Model:

```python
        self._append_live_selection_section(lines)
```

- [ ] **Step 5: 运行测试确认通过**

Run:

```bash
uv run pytest tests/pipelines/model/test_pipeline_integration.py::test_report_writes_live_selection_json -v
```

Expected: PASS.

- [ ] **Step 6: 提交报告渲染**

```bash
git add src/pipelines/model/model_pipeline.py tests/pipelines/model/test_pipeline_integration.py
git commit -m "feat: render live selection report"
```

---

### Task 6: 配置扩展和全量验证

**Files:**
- Modify: `configs/model_pipeline.yaml`
- Modify: `src/pipelines/model/model_pipeline.py`
- Test: selector and model pipeline tests

- [ ] **Step 1: 更新配置**

Replace existing `selection` block in `configs/model_pipeline.yaml`:

```yaml
selection:
  mode: "live"
  primary_metric: "live_score"
  constraints:
    min_oos_ic: 0.0
    min_oos_icir: 0.0
    min_ann_excess_return: 0.0
    min_excess_sharpe: 0.0
    max_drawdown: -0.25
    max_avg_turnover: 0.8
    min_positive_ratio: 0.52
    min_rolling_windows: 3
  weights:
    oos_icir: 0.30
    excess_sharpe: 0.30
    ann_excess_return: 0.20
    positive_ratio: 0.10
    drawdown: 0.05
    turnover: 0.05
```

- [ ] **Step 2: 修正旧 Best Model 逻辑的空结果风险**

In `_generate_static_report`, replace:

```python
        valid_results = [r for r in self.results if not np.isnan(r.val_metrics.get("icir", np.nan))]
        best = max(valid_results, key=lambda r: abs(r.val_metrics.get("icir", 0))) if valid_results else self.results[0]
```

with:

```python
        valid_results = [r for r in self.results if not np.isnan(r.val_metrics.get("icir", np.nan))]
        best = max(valid_results, key=lambda r: abs(r.val_metrics.get("icir", 0))) if valid_results else None
        if best is None:
            lines.append("## 3. Best Model")
            lines.append("")
            lines.append("No model results available.")
            lines.append("")
            report_path.write_text("\n".join(lines), encoding="utf-8")
            logging.info(f"Model report saved to {report_path}")
            return
```

This keeps empty `self.results` compatible with selector behavior.

- [ ] **Step 3: 运行 selector 单测**

Run:

```bash
uv run pytest tests/pipelines/model/test_selector.py -v
```

Expected: PASS.

- [ ] **Step 4: 运行 pipeline 集成测试**

Run:

```bash
uv run pytest tests/pipelines/model/test_pipeline_integration.py -v
```

Expected: PASS.

- [ ] **Step 5: 运行模型相关测试**

Run:

```bash
uv run pytest tests/pipelines/model -v
```

Expected: PASS.

- [ ] **Step 6: 检查工作区差异**

Run:

```bash
git diff -- src/pipelines/model/selector.py src/pipelines/model/model_pipeline.py configs/model_pipeline.yaml tests/pipelines/model/test_selector.py tests/pipelines/model/test_pipeline_integration.py
```

Expected: diff only contains selector, report integration, config, and tests for live selection.

- [ ] **Step 7: 提交最终配置和验证修正**

```bash
git add configs/model_pipeline.yaml src/pipelines/model/model_pipeline.py tests/pipelines/model/test_selector.py tests/pipelines/model/test_pipeline_integration.py
git commit -m "feat: configure live model selection"
```

---

## 自检

- Spec coverage: Task 1-3 覆盖 selector 数据结构、默认配置、硬约束、综合评分、NaN/inf 和权重异常；Task 4-5 覆盖 pipeline 调用、JSON 输出和 Markdown 展示；Task 6 覆盖配置、空结果和验证。
- Scope: 本计划只做方案二的独立 selector 和报告接入，不做参数搜索、模型持久化或真实交易执行。
- Type consistency: `SelectionCandidate`、`SelectionResult`、`LiveModelSelector.select()` 在所有任务中使用同一签名；pipeline 通过 `selection_result.to_dict()` 写 JSON。
- Verification: 每个任务都有明确 pytest 命令；最终运行 `tests/pipelines/model`。
