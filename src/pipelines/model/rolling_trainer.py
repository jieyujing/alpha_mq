"""Rolling/Expanding window training infrastructure.

Provides window generation, per-window training, OOS prediction concatenation,
and cross-window metric aggregation for walk-forward model evaluation.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from pipelines.model.base_model import BaseModel, get_model
from pipelines.model.evaluator import compute_ic_by_date, compute_metrics_from_ic_series


@dataclass
class RollingWindow:
    """One walk-forward window definition."""
    window_id: int
    train_start: str
    train_end: str
    val_start: str
    val_end: str
    oos_start: str
    oos_end: Optional[str] = None


@dataclass
class WindowTrainingResult:
    """Results for one model in one rolling window."""
    window_id: int
    model_name: str
    label_name: str
    train_start: str
    train_end: str
    val_mean_ic: float
    val_metrics: dict
    oos_predictions: pd.Series = field(default_factory=pd.Series)
    oos_ic_series: pd.Series = field(default_factory=pd.Series)
    oos_metrics: dict = field(default_factory=dict)
    feature_importance: pd.Series = field(default_factory=pd.Series)
    model: Optional[BaseModel] = None


class RollingTrainer:
    """Manages rolling/expanding window training lifecycle."""

    def __init__(self, config: dict, df: pd.DataFrame, X: pd.DataFrame, labels: dict):
        self.config = config["rolling"]
        self.df = df
        self.X = X
        self.labels = labels
        self.model_cfg = config["model"]
        self.split_cfg = config.get("split", {})

    # -- Window generation --

    def generate_windows(self, label_name: str) -> list[RollingWindow]:
        """Generate walk-forward windows based on config."""
        all_dates = self._get_calendar_dates()
        if len(all_dates) == 0:
            return []

        step_days = self._months_to_trading_days(
            self.config.get("step_months", 3), all_dates
        )
        val_days = self._months_to_trading_days(
            self.config.get("val_period_months", 3), all_dates
        )
        embargo = self.config.get("embargo_days", 5)
        mode = self.config.get("mode", "expanding")
        train_months = self.config.get("train_period_months", 12)

        global_start = self.config.get("start_date") or self.split_cfg.get("train_start", "2020-01-01")
        start_idx = self._find_date_index(all_dates, global_start)

        # For rolling mode, ensure minimum training window before first step
        min_train_days = self._months_to_trading_days(
            train_months if mode == "rolling" else 3,  # 3 months minimum for expanding
            all_dates,
        )
        # First train_end should have enough data
        first_train_end_idx = min(start_idx + min_train_days, len(all_dates) - 1)

        windows = []
        current_idx = first_train_end_idx

        while True:
            train_end_idx = current_idx

            if mode == "expanding":
                train_start_idx = start_idx
            else:
                train_days = self._months_to_trading_days(train_months, all_dates)
                train_start_idx = max(start_idx, train_end_idx - train_days)

            val_start_idx = train_end_idx + embargo
            if val_start_idx >= len(all_dates):
                break
            val_end_idx = min(val_start_idx + val_days, len(all_dates) - 1)

            oos_start_idx = val_end_idx + 1
            if oos_start_idx >= len(all_dates):
                break

            oos_end_idx = min(oos_start_idx + step_days - 1, len(all_dates) - 1)

            windows.append(RollingWindow(
                window_id=len(windows),
                train_start=all_dates[train_start_idx].strftime("%Y-%m-%d"),
                train_end=all_dates[train_end_idx].strftime("%Y-%m-%d"),
                val_start=all_dates[val_start_idx].strftime("%Y-%m-%d"),
                val_end=all_dates[val_end_idx].strftime("%Y-%m-%d"),
                oos_start=all_dates[oos_start_idx].strftime("%Y-%m-%d"),
                oos_end=all_dates[oos_end_idx].strftime("%Y-%m-%d") if oos_end_idx < len(all_dates) else None,
            ))

            current_idx += step_days
            if current_idx >= len(all_dates) - val_days - embargo:
                break

        logging.info(f"Generated {len(windows)} rolling windows for {label_name}")
        return windows

    def generate_windows_for_all_labels(self) -> dict[str, list[RollingWindow]]:
        """Generate windows keyed by label name."""
        label_names = self.model_cfg.get("target_labels", ["label_5d"])
        return {ln: self.generate_windows(ln) for ln in label_names}

    # -- Per-window training --

    def train_window(self, window: RollingWindow, model_name: str, label_name: str) -> WindowTrainingResult:
        """Train one model for one window, return results."""
        label = self.labels[label_name]

        # Build date masks
        train_mask = self._date_mask(label, window.train_start, window.train_end)
        val_mask = self._date_mask(label, window.val_start, window.val_end)

        X_train = self.X[train_mask]
        y_train = label[train_mask]
        X_val = self.X[val_mask]
        y_val = label[val_mask]

        # Drop NaN
        train_valid = y_train.notna()
        val_valid = y_val.notna()
        X_train, y_train = X_train[train_valid], y_train[train_valid]
        X_val, y_val = X_val[val_valid], y_val[val_valid]

        if X_train.empty or X_val.empty:
            logging.warning(f"Empty train/val for window {window.window_id} {model_name}/{label_name}")
            return WindowTrainingResult(
                window_id=window.window_id, model_name=model_name, label_name=label_name,
                train_start=window.train_start, train_end=window.train_end,
                val_mean_ic=0.0, val_metrics={},
            )

        # Train
        params = self.model_cfg.get("params", {}).get(model_name, {})
        model = get_model(model_name, params)
        model.fit(X_train, y_train)

        # Val predictions & metrics
        val_pred = model.predict(X_val)
        val_ic = compute_ic_by_date(val_pred, y_val)
        val_metrics = compute_metrics_from_ic_series(val_ic)
        val_mean_ic = val_metrics.get("ic_mean", 0.0)

        # OOS predictions
        oos_mask = self._date_mask(label, window.oos_start, window.oos_end)
        X_oos = self.X[oos_mask]
        y_oos = label[oos_mask]
        oos_valid = y_oos.notna()
        X_oos = X_oos[oos_valid]

        oos_pred = model.predict(X_oos) if not X_oos.empty else pd.Series(dtype=float)

        # OOS IC
        if not oos_pred.empty and not y_oos[oos_pred.index].empty:
            y_oos_aligned = y_oos.loc[oos_pred.index]
            oos_ic_series = compute_ic_by_date(oos_pred, y_oos_aligned)
            oos_metrics = compute_metrics_from_ic_series(oos_ic_series)
        else:
            oos_ic_series = pd.Series(dtype=float)
            oos_metrics = {}

        feat_imp = model.feature_importance() if hasattr(model, "feature_importance") else pd.Series(dtype=float)

        return WindowTrainingResult(
            window_id=window.window_id,
            model_name=model_name,
            label_name=label_name,
            train_start=window.train_start,
            train_end=window.train_end,
            val_mean_ic=val_mean_ic,
            val_metrics=val_metrics,
            oos_predictions=oos_pred,
            oos_ic_series=oos_ic_series,
            oos_metrics=oos_metrics,
            feature_importance=feat_imp,
            model=model,
        )

    # -- OOS concatenation --

    @staticmethod
    def concatenate_oos_signals(
        window_results: list[WindowTrainingResult],
    ) -> pd.Series:
        """Merge OOS predictions across windows. Overlaps resolved by latest-window-wins."""
        all_preds = [wr.oos_predictions for wr in window_results if not wr.oos_predictions.empty]
        if not all_preds:
            return pd.Series(dtype=float)

        combined = pd.concat(all_preds)
        # Overlap resolution: latest window wins
        combined = combined.groupby(combined.index).last()
        return combined

    @staticmethod
    def aggregate_ic_metrics(
        window_results: list[WindowTrainingResult],
    ) -> dict:
        """Aggregate IC metrics across all windows."""
        all_ic = pd.concat([wr.oos_ic_series for wr in window_results if not wr.oos_ic_series.empty])
        if all_ic.empty:
            return {"mean_ic": 0.0, "ic_std": 0.0, "icir": 0.0, "positive_ratio": 0.0, "n_dates": 0}

        return compute_metrics_from_ic_series(all_ic)

    # -- Helpers --

    def _get_calendar_dates(self) -> pd.DatetimeIndex:
        """Extract sorted unique trading dates from data."""
        dates = pd.Series(self.df.index.get_level_values(0).unique()).sort_values()
        return pd.DatetimeIndex(dates)

    @staticmethod
    def _months_to_trading_days(months: int, all_dates: pd.DatetimeIndex) -> int:
        """Convert calendar months to approximate trading days using actual calendar density."""
        if len(all_dates) < 30:
            return months * 21

        # Estimate trading days per month from data density
        span_days = (all_dates[-1] - all_dates[0]).days
        n_dates = len(all_dates)
        days_per_month = (n_dates / span_days) * 30 if span_days > 0 else 21
        return max(1, int(months * days_per_month))

    @staticmethod
    def _find_date_index(all_dates: pd.DatetimeIndex, date_str: str) -> int:
        """Find the index of the closest date <= target."""
        target = pd.Timestamp(date_str)
        mask = all_dates <= target
        if not mask.any():
            return 0
        return int(mask.argmax())  # last True before first False

    @staticmethod
    def _date_mask(series: pd.Series, start: str, end: str) -> pd.Series:
        """Boolean mask for dates in [start, end]."""
        dates = series.index.get_level_values(0)
        mask = dates >= start
        if end:
            mask &= dates <= end
        return mask
