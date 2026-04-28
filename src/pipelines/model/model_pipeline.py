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
from pipelines.model.rolling_trainer import RollingTrainer


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
        if "rolling" in self.config:
            self._make_rolling_splits()
        else:
            self._make_static_splits()

    def _make_static_splits(self):
        """Original static split logic."""
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
        """Subtract N trading days from a date string using the data's own calendar."""
        if self.df is None or self.df.empty:
            return end_date
        
        # Get unique sorted dates from data
        cal = pd.Series(self.df.index.get_level_values(0).unique()).sort_values()
        end = pd.Timestamp(end_date)
        
        cal_before = cal[cal <= end]
        if cal_before.empty:
            return end_date
            
        if len(cal_before) <= days:
            return cal_before.iloc[0].strftime("%Y-%m-%d")
        
        return cal_before.iloc[-days - 1].strftime("%Y-%m-%d")

    def _get_date_mask(self, y: pd.Series, start: str, end: Optional[str]) -> pd.Series:
        """Boolean mask for dates in [start, end]."""
        dates = y.index.get_level_values(0)
        mask = dates >= start
        if end:
            mask &= dates <= end
        return mask

    # --- Stage: train ---

    def train_models(self):
        if "rolling" in self.config:
            self._rolling_train_models()
        else:
            self._static_train_models()

    def _static_train_models(self):
        """Original static training logic."""
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

                train_valid = y_train.notna()
                val_valid = y_val.notna()
                X_train = X_train[train_valid]
                y_train = y_train[train_valid]
                X_val = X_val[val_valid]
                y_val = y_val[val_valid]

                params = model_params.get(model_name, {})
                model = get_model(model_name, params)
                model.fit(X_train, y_train)

                train_pred = model.predict(X_train)
                val_pred = model.predict(X_val)

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
        if "rolling" in self.config:
            self._rolling_concatenate_predictions()
        else:
            self._static_run_predict()

    def _static_run_predict(self):
        """Original static test prediction logic."""
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
            test_valid = y_test.notna()
            X_test = X_test[test_valid]
            y_test = y_test[test_valid]

            if X_test.empty:
                logging.warning(f"Empty test set for {result.model_name} / {label_name}")
                continue

            test_pred = result.model.predict(X_test)
            result.test_predictions = test_pred

            test_ic = compute_ic_by_date(test_pred, y_test)
            result.test_metrics = compute_metrics_from_ic_series(test_ic)

    # --- Stage: orient ---

    def orient_signals(self):
        if "rolling" in self.config:
            self._rolling_orient_signals()
        else:
            self._static_orient_signals()

    def _static_orient_signals(self):
        """Original signal orientation for static split."""
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
        elif "CLOSE" in self.df.columns:
            close_col = "CLOSE"
        
        if close_col is None:
            # Check if we can use label_1d to reconstruct returns (approximate)
            if "label_1d" in self.df.columns:
                logging.info("Using label_1d as returns for backtest")
                returns_wide = self.df["label_1d"].unstack().shift(1) # label_1d is usually r(t+1)
            else:
                logging.warning("No close price or label_1d found. Backtest skipped.")
                return
        else:
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
        from pipelines.model.alphalens_report import generate_multi_model_tear_sheet

        output_cfg = self.config.get("output", {})
        alphalens_dir = Path(output_cfg.get("alphalens", "data/model_results/alphalens"))

        # Get close prices: try factor pool columns first, then reconstruct from label_1d
        close_col = None
        for col in self.df.columns:
            if "close" in col.lower():
                close_col = col
                break

        if close_col:
            prices_wide = self.df[[close_col]].unstack()
            prices_wide.columns = prices_wide.columns.droplevel(0)
        elif "label_1d" in self.df.columns:
            logging.info("No close price column found. Reconstructing from label_1d returns.")
            # label_1d ≈ close(t+1)/close(t) - 1; reconstruct price series
            returns_wide = self.df["label_1d"].unstack()
            prices_wide = (1 + returns_wide).cumprod() * 100
        else:
            logging.warning("No close prices or label_1d found for Alphalens. Skipping.")
            return

        # Group results by label_name
        target_labels = self.config["model"].get("target_labels", [])
        results_by_label = {}
        for r in self.results:
            if r.label_name not in target_labels:
                continue
            results_by_label.setdefault(r.label_name, []).append(r)

        # Generate one tear sheet per label
        for label_name in target_labels:
            label_results = results_by_label.get(label_name, [])
            if not label_results:
                logging.warning(f"No results found for {label_name}. Skipping alphalens.")
                continue

            logging.info(f"Generating alphalens for {label_name} with {len(label_results)} models")
            generate_multi_model_tear_sheet(
                label_name=label_name,
                results=label_results,
                prices=prices_wide,
                output_dir=alphalens_dir,
            )

    # --- Stage: report ---

    def generate_report(self):
        if "rolling" in self.config:
            self._generate_rolling_report()
        else:
            self._generate_static_report()

    # -- Rolling pipeline methods --

    def _make_rolling_splits(self):
        """Generate walk-forward windows via RollingTrainer."""
        self.rolling_trainer = RollingTrainer(
            config=self.config, df=self.df, X=self.X, labels=self.labels,
        )
        self.rolling_windows = self.rolling_trainer.generate_windows_for_all_labels()
        self.rolling_results = {}
        logging.info(f"Rolling splits: {sum(len(v) for v in self.rolling_windows.values())} total windows")

    def _rolling_train_models(self):
        """Train each model for each rolling window."""
        model_names = self.config["model"].get("names", ["lgbm_regressor"])
        label_names = self.config["model"].get("target_labels", ["label_5d"])

        self.rolling_results = {}

        for label_name in label_names:
            windows = self.rolling_windows.get(label_name, [])
            if not windows:
                logging.warning(f"No windows for {label_name}")
                continue

            self.rolling_results[label_name] = []
            for window in windows:
                for model_name in model_names:
                    wr = self.rolling_trainer.train_window(window, model_name, label_name)
                    self.rolling_results[label_name].append(wr)
                    if wr.oos_metrics:
                        oos_ic = wr.oos_metrics.get("ic_mean", 0)
                        logging.info(
                            f"Window {wr.window_id} {model_name}/{label_name}: "
                            f"val IC={wr.val_mean_ic:.4f}, oos IC={oos_ic:.4f}"
                        )

            logging.info(f"Trained {len(self.rolling_results[label_name])} window-results for {label_name}")

    def _rolling_concatenate_predictions(self):
        """Merge OOS predictions across windows and create synthetic TrainingResult."""
        self.rolling_oos_signals = {}

        for label_name, window_results in self.rolling_results.items():
            # Group by (model_name, label_name) across windows
            model_names = set(wr.model_name for wr in window_results)
            for model_name in model_names:
                model_results = [wr for wr in window_results if wr.model_name == model_name]
                combined = RollingTrainer.concatenate_oos_signals(model_results)
                key = f"{model_name}/{label_name}"
                self.rolling_oos_signals[key] = combined

        # Create synthetic TrainingResult objects for downstream stages
        self.results = []
        for label_name, window_results in self.rolling_results.items():
            model_names = set(wr.model_name for wr in window_results)
            for model_name in model_names:
                model_results = [wr for wr in window_results if wr.model_name == model_name]
                key = f"{model_name}/{label_name}"
                oos_signal = self.rolling_oos_signals.get(key, pd.Series(dtype=float))

                # Aggregate val metrics across windows
                val_ics = [wr.val_mean_ic for wr in model_results]
                avg_val_ic = float(np.mean(val_ics)) if val_ics else 0.0
                # Average val_metrics
                avg_val_metrics = {}
                if model_results and model_results[0].val_metrics:
                    for k in model_results[0].val_metrics:
                        vals = [wr.val_metrics.get(k, 0) for wr in model_results]
                        avg_val_metrics[k] = float(np.mean(vals))

                # Aggregate OOS metrics
                agg_oos = RollingTrainer.aggregate_ic_metrics(model_results)

                # Use last window's feature importance
                last_wr = model_results[-1]
                feat_imp = last_wr.feature_importance

                result = TrainingResult(
                    model_name=model_name,
                    label_name=label_name,
                    model=None,
                    train_metrics={},
                    val_metrics=avg_val_metrics,
                    test_metrics=agg_oos,
                    val_mean_ic=avg_val_ic,
                    train_predictions=pd.Series(dtype=float),
                    val_predictions=pd.Series(dtype=float),
                    test_predictions=oos_signal,
                    oriented_test_signal=pd.Series(dtype=float),
                    oriented_direction=1,
                    feature_importance=feat_imp,
                    metadata={"rolling": True, "n_windows": len(model_results)},
                )
                self.results.append(result)

        logging.info(f"Concatenated OOS signals for {len(self.rolling_oos_signals)} model/label combos")

    def _rolling_orient_signals(self):
        """Orient unified rolling OOS signals based on aggregate val IC."""
        for result in self.results:
            meta = result.metadata or {}
            if not meta.get("rolling"):
                self._static_orient_signals()
                continue
            if result.test_predictions.empty:
                continue
            oriented, direction = orient_signal(result.val_mean_ic, result.test_predictions)
            result.oriented_test_signal = oriented
            result.oriented_direction = direction

    def _generate_rolling_report(self):
        """Generate rolling-specific markdown report."""
        output_cfg = self.config.get("output", {})
        report_path = Path(output_cfg.get("report", "data/model_results/model_report.md"))
        report_path.parent.mkdir(parents=True, exist_ok=True)

        rolling_cfg = self.config.get("rolling", {})
        n_windows = len(next(iter(self.rolling_results.values()), []))
        if not n_windows and self.rolling_results:
            n_windows = max(len(v) for v in self.rolling_results.values())

        lines = []
        lines.append("# Rolling Model Training Report")
        lines.append("")
        lines.append(f"**Generated**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Mode**: {rolling_cfg.get('mode', 'expanding')}")
        lines.append(f"**Windows**: {n_windows} retraining cycles")
        lines.append(f"**Step**: every {rolling_cfg.get('step_months', 3)} months")
        lines.append("")

        # 1. Per-window performance
        lines.append("## 1. Per-Window Performance")
        lines.append("")
        lines.append("| Model | Label | Window | Train Range | Val IC | OOS IC | OOS ICIR |")
        lines.append("|-------|-------|--------|-------------|--------|--------|----------|")
        for label_name, window_results in self.rolling_results.items():
            for wr in window_results:
                oos_ic = wr.oos_metrics.get("ic_mean", 0)
                oos_icir = wr.oos_metrics.get("icir", 0)
                lines.append(
                    f"| {wr.model_name} | {wr.label_name} | {wr.window_id} | "
                    f"{wr.train_start} to {wr.train_end} | "
                    f"{wr.val_mean_ic:.4f} | {oos_ic:.4f} | {oos_icir:.4f} |"
                )
        lines.append("")

        # 2. Aggregated OOS metrics
        lines.append("## 2. Aggregated OOS Metrics (across windows)")
        lines.append("")
        lines.append("| Model | Label | Mean IC | IC Std | ICIR | Positive Ratio |")
        lines.append("|-------|-------|---------|--------|------|----------------|")
        for label_name, window_results in self.rolling_results.items():
            model_names = set(wr.model_name for wr in window_results)
            for model_name in model_names:
                model_results = [wr for wr in window_results if wr.model_name == model_name]
                agg = RollingTrainer.aggregate_ic_metrics(model_results)
                lines.append(
                    f"| {model_name} | {label_name} | "
                    f"{agg['mean_ic']:.4f} | {agg['ic_std']:.4f} | "
                    f"{agg['icir']:.4f} | {agg['positive_ratio']:.2%} |"
                )
        lines.append("")

        # 3. OOS Backtest (same format as static)
        lines.append("## 3. Unified OOS Backtest")
        lines.append("")
        lines.append("| Model | Label | Ann Ret | Excess Ann Ret | Sharpe | Max DD | Turnover |")
        lines.append("|-------|-------|---------|----------------|--------|--------|----------|")
        for r in self.results:
            m = r.backtest_metrics
            if not m:
                lines.append(f"| {r.model_name} | {r.label_name} | - | - | - | - | - |")
            else:
                lines.append(
                    f"| {r.model_name} | {r.label_name} | "
                    f"{m.get('ann_return', 0)*100:.2f}% | "
                    f"{m.get('ann_excess_return', 0)*100:.2f}% | "
                    f"{m.get('sharpe', 0):.2f} | "
                    f"{m.get('max_drawdown', 0)*100:.2f}% | "
                    f"{m.get('avg_turnover', 0):.3f} |"
                )
        lines.append("")

        # 4. Best model
        valid_results = [r for r in self.results if not np.isnan(r.val_metrics.get("icir", np.nan))]
        if valid_results:
            best = max(valid_results, key=lambda r: abs(r.val_metrics.get("icir", 0)))
            lines.append(f"## 4. Best Model: {best.model_name} + {best.label_name}")
            lines.append("")
            lines.append(f"- Mean Val IC: {best.val_mean_ic:.4f}")
            lines.append(f"- Mean Val ICIR: {best.val_metrics.get('icir', 0):.4f}")
            lines.append(f"- OOS IC: {best.test_metrics.get('ic_mean', 0):.4f}")
            lines.append(f"- OOS ICIR: {best.test_metrics.get('icir', 0):.4f}")
            lines.append(f"- Windows: {best.metadata.get('n_windows', 0)}")
            if best.backtest_metrics:
                m = best.backtest_metrics
                lines.append(f"- OOS annual return: {m.get('ann_return', 0)*100:.2f}%")
                lines.append(f"- OOS Sharpe: {m.get('sharpe', 0):.2f}")
                lines.append(f"- OOS max drawdown: {m.get('max_drawdown', 0)*100:.2f}%")
            lines.append("")

            # 5. Feature importance
            imp = best.model.feature_importance() if best.model else best.feature_importance
            if not imp.empty:
                lines.append("## 5. Top 20 Feature Importance (last window)")
                lines.append("")
                lines.append("| Rank | Feature | Importance |")
                lines.append("|------|---------|------------|")
                top20 = imp.abs().nlargest(20)
                for rank, (feat, val) in enumerate(top20.items(), 1):
                    lines.append(f"| {rank} | {feat} | {val:.4f} |")
                lines.append("")

        report_path.write_text("\n".join(lines), encoding="utf-8")
        logging.info(f"Rolling report saved to {report_path}")

    def _generate_static_report(self):
        """Original static report generation."""
        output_cfg = self.config.get("output", {})
        report_path = Path(output_cfg.get("report", "data/model_results/model_report.md"))
        report_path.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        lines.append("# Model Training Report")
        lines.append("")
        lines.append(f"**Generated**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("**Static split - results may not reflect rolling live performance**")
        lines.append("")

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

        imp = best.model.feature_importance() if best.model else pd.Series(dtype=float)
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
