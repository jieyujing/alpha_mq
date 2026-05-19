"""Live-trading model selection for model pipeline results."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import numpy as np


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
