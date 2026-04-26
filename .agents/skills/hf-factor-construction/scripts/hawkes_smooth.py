"""
Hawkes process smoothing utilities for factor research.

Design choices:
- Post-event recursion: the current event contributes immediately.
- Explicit time units via half-life helpers.
- Query decays the full latent state, including multivariate state matrices.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class HawkesParams:
    mu: float
    alpha: float
    beta: float
    time_unit: str = "seconds"

    @property
    def eta(self) -> float:
        return self.alpha / self.beta

    @property
    def half_life(self) -> float:
        return float(np.log(2.0) / self.beta)

    def validate(self) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        if self.mu < 0:
            errors.append(f"mu must be >= 0, got {self.mu}")
        if self.alpha < 0:
            errors.append(f"alpha must be >= 0, got {self.alpha}")
        if self.beta <= 0:
            errors.append(f"beta must be > 0, got {self.beta}")
        if self.beta > 0 and self.eta >= 1:
            errors.append(f"eta = alpha / beta must be < 1, got {self.eta:.4f}")
        return len(errors) == 0, errors

    def summary(self) -> Dict[str, float | str | bool]:
        return {
            "mu": self.mu,
            "alpha": self.alpha,
            "beta": self.beta,
            "eta": round(self.eta, 6),
            f"half_life_{self.time_unit}": round(self.half_life, 6),
            "stable": self.eta < 1.0,
            "time_unit": self.time_unit,
        }


def params_from_half_life(
    mu: float,
    half_life: float,
    eta: float,
    time_unit: str = "seconds",
) -> HawkesParams:
    if half_life <= 0:
        raise ValueError(f"half_life must be > 0, got {half_life}")
    if not (0 <= eta < 1):
        raise ValueError(f"eta must satisfy 0 <= eta < 1, got {eta}")
    beta = float(np.log(2.0) / half_life)
    alpha = float(eta * beta)
    params = HawkesParams(mu=mu, alpha=alpha, beta=beta, time_unit=time_unit)
    valid, errors = params.validate()
    if not valid:
        raise ValueError("; ".join(errors))
    return params


class HawkesSmooth:
    """Univariate Hawkes-style smoother with post-event updates."""

    def __init__(self, mu: float, alpha: float, beta: float, time_unit: str = "seconds"):
        self.params = HawkesParams(mu=mu, alpha=alpha, beta=beta, time_unit=time_unit)
        valid, errors = self.params.validate()
        if not valid:
            raise ValueError("; ".join(errors))
        self.R: float = 0.0
        self.t_last: Optional[float] = None
        self._event_count: int = 0

    def update(self, t: float, w: float = 1.0) -> float:
        if self.t_last is not None:
            dt = float(t - self.t_last)
            if dt < 0:
                raise ValueError(f"time must be monotonic; got dt={dt}")
            self.R = float(np.exp(-self.params.beta * dt) * self.R + self.params.alpha * w)
        else:
            self.R = float(self.params.alpha * w)
        self.t_last = float(t)
        self._event_count += 1
        return self.params.mu + self.R

    def query(self, t: float) -> float:
        if self.t_last is None:
            return self.params.mu
        dt = float(t - self.t_last)
        if dt < 0:
            raise ValueError(f"query time must be >= last event time; got dt={dt}")
        return self.params.mu + float(np.exp(-self.params.beta * dt) * self.R)

    def reset(self) -> None:
        self.R = 0.0
        self.t_last = None
        self._event_count = 0

    @property
    def event_count(self) -> int:
        return self._event_count

    def get_params_summary(self) -> Dict[str, float | str | bool]:
        return self.params.summary()


class MultiHawkesSmooth:
    """Multivariate Hawkes smoother with full-state decay on update and query."""

    def __init__(self, mu: Sequence[float], alpha: np.ndarray, beta: np.ndarray, time_unit: str = "seconds"):
        self.mu = np.asarray(mu, dtype=float)
        self.K = int(self.mu.shape[0])
        self.alpha = np.asarray(alpha, dtype=float)
        self.beta = np.asarray(beta, dtype=float)
        self.time_unit = time_unit

        if self.alpha.shape != (self.K, self.K):
            raise ValueError(f"alpha must have shape {(self.K, self.K)}, got {self.alpha.shape}")
        if self.beta.shape != (self.K, self.K):
            raise ValueError(f"beta must have shape {(self.K, self.K)}, got {self.beta.shape}")
        if np.any(self.beta <= 0):
            raise ValueError("all beta entries must be > 0")
        if np.any(self.alpha < 0):
            raise ValueError("all alpha entries must be >= 0")

        branching = self.alpha / self.beta
        spectral_radius = float(np.max(np.abs(np.linalg.eigvals(branching))))
        if spectral_radius >= 1:
            raise ValueError(f"spectral radius must be < 1, got {spectral_radius:.6f}")

        self.R = np.zeros((self.K, self.K), dtype=float)
        self.t_last: Optional[float] = None
        self._event_count = 0

    def _decay_state(self, dt: float) -> np.ndarray:
        return np.exp(-self.beta * dt) * self.R

    def update(self, t: float, event_type: int, w: float = 1.0) -> np.ndarray:
        if not 0 <= event_type < self.K:
            raise ValueError(f"event_type must be in [0, {self.K}), got {event_type}")
        if self.t_last is not None:
            dt = float(t - self.t_last)
            if dt < 0:
                raise ValueError(f"time must be monotonic; got dt={dt}")
            self.R = self._decay_state(dt)
        self.R[event_type, :] += self.alpha[event_type, :] * float(w)
        self.t_last = float(t)
        self._event_count += 1
        return self.mu + self.R.sum(axis=0)

    def query(self, t: float) -> np.ndarray:
        if self.t_last is None:
            return self.mu.copy()
        dt = float(t - self.t_last)
        if dt < 0:
            raise ValueError(f"query time must be >= last event time; got dt={dt}")
        decayed = self._decay_state(dt)
        return self.mu + decayed.sum(axis=0)

    def reset(self) -> None:
        self.R.fill(0.0)
        self.t_last = None
        self._event_count = 0

    @property
    def event_count(self) -> int:
        return self._event_count


DEFAULT_PRESETS: Dict[str, Dict[str, float | str]] = {
    "maker_toxicity_short": {"mu": 0.0, "half_life": 1.5, "eta": 0.35, "time_unit": "seconds"},
    "liquidation_cascade": {"mu": 0.0, "half_life": 2.5, "eta": 0.50, "time_unit": "seconds"},
    "orderflow_persistence": {"mu": 0.0, "half_life": 5.0, "eta": 0.40, "time_unit": "seconds"},
    "intraday_event_cluster": {"mu": 0.0, "half_life": 15.0, "eta": 0.30, "time_unit": "seconds"},
}


def create_hawkes_from_preset(name: str) -> HawkesSmooth:
    if name not in DEFAULT_PRESETS:
        raise ValueError(f"unknown preset {name!r}; choices={list(DEFAULT_PRESETS)}")
    preset = DEFAULT_PRESETS[name]
    params = params_from_half_life(
        mu=float(preset["mu"]),
        half_life=float(preset["half_life"]),
        eta=float(preset["eta"]),
        time_unit=str(preset["time_unit"]),
    )
    return HawkesSmooth(mu=params.mu, alpha=params.alpha, beta=params.beta, time_unit=params.time_unit)


def hawkes_smooth_series(
    timestamps: Sequence[float],
    weights: Sequence[float],
    mu: float,
    alpha: float,
    beta: float,
    time_unit: str = "seconds",
) -> np.ndarray:
    ts = np.asarray(timestamps, dtype=float)
    ws = np.asarray(weights, dtype=float)
    if ts.ndim != 1 or ws.ndim != 1 or len(ts) != len(ws):
        raise ValueError("timestamps and weights must be 1D arrays of the same length")
    if len(ts) == 0:
        return np.asarray([], dtype=float)
    if np.any(np.diff(ts) < 0):
        raise ValueError("timestamps must be monotonic non-decreasing")

    smoother = HawkesSmooth(mu=mu, alpha=alpha, beta=beta, time_unit=time_unit)
    out = np.empty(len(ts), dtype=float)
    for i, (t, w) in enumerate(zip(ts, ws)):
        out[i] = smoother.update(float(t), float(w))
    return out


def recommend_params(
    event_rate_per_unit: float,
    half_life_in_units: Optional[float] = None,
    self_excitation: str = "moderate",
    mu_scale: float = 0.0,
    time_unit: str = "seconds",
) -> Dict[str, float | str]:
    if event_rate_per_unit <= 0:
        raise ValueError("event_rate_per_unit must be > 0")
    eta_map = {"weak": 0.2, "moderate": 0.4, "strong": 0.6}
    eta = eta_map.get(self_excitation, 0.4)
    if half_life_in_units is None:
        half_life_in_units = 1.0 / event_rate_per_unit
    params = params_from_half_life(
        mu=mu_scale * event_rate_per_unit,
        half_life=half_life_in_units,
        eta=eta,
        time_unit=time_unit,
    )
    return params.summary()


if __name__ == "__main__":
    hs = create_hawkes_from_preset("maker_toxicity_short")
    print("preset:", hs.get_params_summary())

    events = [(1.0, 1.0), (1.4, 0.5), (2.0, 2.0), (3.0, 1.0)]
    for t, w in events:
        print(f"t={t:.2f}, w={w:.2f}, value={hs.update(t, w):.6f}")
    print("query@5.0 ->", hs.query(5.0))
