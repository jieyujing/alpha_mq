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
    """Container for one model x label training result."""
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

    Stages: load -> prepare -> split -> train -> predict -> orient -> backtest -> alphalens -> report
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
        # Ensure MultiIndex
        if not isinstance(self.df.index, pd.MultiIndex):
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
            transform_method=feat_cfg.get("transform_method", "rank_pct"),
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
            # Fallback: use calendar days (5 trading days ~ 7 calendar days)
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

                # Drop NaN labels
                train_valid = y_train.notna()
                val_valid = y_val.notna()
                X_train = X_train[train_valid]
                y_train = y_train[train_valid]
                X_val = X_val[val_valid]
                y_val = y_val[val_valid]

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

        logging.info(f"Trained {len(self.results)} model x label combinations")

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
            # Drop NaN labels
            test_valid = y_test.notna()
            X_test = X_test[test_valid]
            y_test = y_test[test_valid]

            if X_test.empty:
                logging.warning(f"Empty test set for {result.model_name} / {label_name}")
                continue

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

        # Pivot to wide format FIRST, then compute pct_change along time axis
        prices_wide = self.df[close_col].unstack()
        returns_wide = prices_wide.pct_change()

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

        # Find best model: prefer regressor with highest OOS Sharpe
        # (best分层收益表现, not validation ICIR)
        regressor_names = ["elastic_net", "lgbm_regressor"]
        best = None
        best_sharpe = -np.inf

        # Select by OOS Sharpe (from backtest_metrics)
        for r in self.results:
            if r.model_name not in regressor_names:
                continue
            sharpe = r.backtest_metrics.get("sharpe", np.nan)
            if np.isnan(sharpe):
                continue
            if sharpe > best_sharpe and not r.oriented_test_signal.empty:
                best_sharpe = sharpe
                best = r

        # Fallback to ICIR if no backtest metrics
        if best is None:
            best_icir = -np.inf
            for r in self.results:
                if r.model_name not in regressor_names:
                    continue
                icir = abs(r.val_metrics.get("icir", np.nan))
                if np.isnan(icir):
                    continue
                if icir > best_icir and not r.oriented_test_signal.empty:
                    best_icir = icir
                    best = r

        if best is None:
            logging.warning("No valid model result found for Alphalens.")
            return

        logging.info(f"Alphalens using {best.model_name} + {best.label_name} (Sharpe={best_sharpe:.2f})")

        # Get close prices - try factor pool first, then Qlib
        close_col = None
        for col in self.df.columns:
            if "close" in col.lower():
                close_col = col
                break

        if close_col:
            # Factor pool has close column - pivot to wide
            prices_wide = self.df[[close_col]].unstack()
            prices_wide.columns = prices_wide.columns.droplevel(0)
        else:
            # Load from Qlib
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
                prices_wide = close_data["close"].unstack()
            except Exception as e:
                logging.warning(f"Could not load close prices for Alphalens: {e}")
                return

        generate_alphalens_tear_sheet(
            factor=best.oriented_test_signal,
            prices=prices_wide,
            output_dir=alphalens_dir,
        )

    # --- Stage: report ---

    def generate_report(self):
        import yaml

        output_cfg = self.config.get("output", {})
        report_path = Path(output_cfg.get("report", "data/model_results/model_report.md"))
        report_path.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        lines.append("# Model Training Report")
        lines.append("")
        lines.append(f"**Generated**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("**Static split - results may not reflect rolling live performance**")
        lines.append("")

        # 1. Model x Period Direction Table
        lines.append("## 1. Model x Period Direction")
        lines.append("")
        lines.append("| Model | Label | Val IC | Direction | Oriented IC | Oriented ICIR |")
        lines.append("|-------|-------|--------|-----------|-------------|---------------|")
        for r in self.results:
            d = "original" if r.oriented_direction == 1 else "flipped"
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
                lines.append(f"| {r.model_name} | {r.label_name} | - | - | - | - | - | - |")
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

        # 3. Best model summary (filter NaN ICIR)
        valid_results = [r for r in self.results if not np.isnan(r.val_metrics.get("icir", np.nan))]
        best = max(valid_results, key=lambda r: abs(r.val_metrics.get("icir", 0))) if valid_results else self.results[0]
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
        imp = best.model.feature_importance()
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
