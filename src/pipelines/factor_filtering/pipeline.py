"""因子筛选流水线主编排器 — 8 环责任链。"""

import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
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


class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return super().default(obj)


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

    # --- Stage: load ---

    def load_data(self):
        data_cfg = self.config.get("data", {})
        factor_path = data_cfg.get("factor_path", "data/alpha158_pool.parquet")
        self.label_col = data_cfg.get("label_col", "label_20d")
        self.df = pl.read_parquet(factor_path)
        # Ensure datetime column is proper datetime type
        if self.df.schema.get("datetime") == pl.String:
            self.df = self.df.with_columns(pl.col("datetime").str.to_datetime())
        logging.info(f"Loaded factor pool: {self.df.shape}")

    # --- Ring 0: Data & Label QA ---

    def run_data_qa(self):
        step = DataAndLabelQA(self.config.get("data", {}))
        self.df, self.qa_report = step.process(self.df)
        rejected = len(self.qa_report.get("rejected", []))
        logging.info(f"Ring 0 QA done. Rejected: {rejected}")

    # --- Ring 1: Preprocess & Neutralize ---

    def run_preprocess(self):
        step = PreprocessAndNeutralize(self.config.get("preprocess", {}))
        self.df, self.preprocess_report = step.process(self.df)
        applied = self.preprocess_report.get("transform_applied", [])
        logging.info(f"Ring 1 preprocess done. Applied: {applied}")

    # --- Ring 2: Single Factor Profiling ---

    def run_profiling(self):
        step = SingleFactorProfiler(label_col=self.label_col)
        self.df, self.ic_metrics = step.process(self.df)
        valid_ics = [abs(m["mean_rank_ic"]) for m in self.ic_metrics.values() if m.get("mean_rank_ic")]
        mean_ic = sum(valid_ics) / max(len(valid_ics), 1) if valid_ics else 0
        logging.info(f"Ring 2 profiling done. Mean |IC|={mean_ic:.4f} across {len(self.ic_metrics)} factors")

    # --- Ring 3: Cross-Section Filter ---

    def run_filter(self):
        filter_cfg = self.config.get("filter", {})
        step = CrossSectionFilter(filter_cfg)
        self.df, self.filter_report = step.process(self.df, self.ic_metrics)
        ret = self.filter_report.get("retained_count", 0)
        rej = self.filter_report.get("rejected_count", 0)
        logging.info(f"Ring 3 filter done. Retained: {ret}, Rejected: {rej}")

    # --- Ring 4: Stability Checker ---

    def run_stability(self):
        step = StabilityChecker()
        self.df, self.stability_report = step.process(self.df)
        logging.info(f"Ring 4 stability done. Factors checked: {len(self.stability_report)}")

    # --- Ring 5: Factor Clustering ---

    def run_clustering(self):
        cluster_cfg = self.config.get("clustering", {})
        step = FactorClustering(cluster_cfg)
        self.df, self.cluster_report = step.process(self.df)
        n_clusters = self.cluster_report.get("n_clusters", 0)
        logging.info(f"Ring 5 clustering done. {n_clusters} clusters")

    # --- Ring 6: Representative Selection ---

    def run_selection(self):
        rep_cfg = self.config.get("representative", {})
        step = RepresentativeSelector(rep_cfg)
        self.df, self.selection_report = step.process(
            self.df, self.cluster_report["clusters"], self.ic_metrics, self.stability_report
        )
        logging.info(f"Ring 6 selection done. Selected: {self.selection_report.get('selected_count', 0)} factors")

    # --- Ring 7: Portfolio Validation ---

    def run_portfolio(self):
        step = PortfolioValidator()
        self.df, self.portfolio_report = step.process(self.df, self.ic_metrics)
        portfolios = list(self.portfolio_report.get("portfolios", {}).keys())
        logging.info(f"Ring 7 portfolio done. Portfolios: {portfolios}")

    # --- Ring 8: ML Importance ---

    def run_ml_importance(self):
        step = MLImportanceVerifier()
        self.df, self.ml_report = step.process(self.df)
        top3 = sorted(self.ml_report.get("importance", {}).items(), key=lambda x: x[1], reverse=True)[:3]
        logging.info(f"Ring 8 ML importance done. Top 3: {top3}")

    # --- Report & Outputs ---

    def generate_report(self):
        output_cfg = self.config.get("pipeline", {})
        output_dir = Path(output_cfg.get("output_dir", "data/reports/factor_filtering"))
        output_dir.mkdir(parents=True, exist_ok=True)

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
            if yearly:
                ic_range = f"{min(yearly.values()):.4f}~{max(yearly.values()):.4f}"
            else:
                ic_range = "N/A"
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
        if portfolios:
            lines.append("| Portfolio | Mean IC | ICIR | Win Rate | Turnover |")
            lines.append("|-----------|---------|------|----------|----------|")
            for name, m in portfolios.items():
                lines.append(
                    f"| {name} | {m.get('mean_ic', 0):.4f} | {m.get('icir', 0):.4f} | "
                    f"{m.get('ic_win_rate', 0):.2%} | {m.get('turnover', 0):.4f} |"
                )
        else:
            lines.append("No portfolio data available.")
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

        # Save filtered factor pool
        factor_cols = [c for c in self.df.columns if c not in ("datetime", "instrument") and not c.startswith("label")]
        all_cols = ["datetime", "instrument"] + factor_cols + [c for c in self.df.columns if c.startswith("label")]
        final_df = self.df.select([c for c in all_cols if c in self.df.columns])
        filtered_path = output_dir / "factor_pool_filtered.parquet"
        final_df.write_parquet(filtered_path)
        logging.info(f"Filtered factor pool saved to {filtered_path} ({len(factor_cols)} factors)")

        # Save selection log JSON
        selection_log = {
            "qa": self.qa_report,
            "filter": self.filter_report,
            "stability": {k: {kk: vv for kk, vv in v.items() if kk != "yearly_ic"} for k, v in self.stability_report.items()},
            "clusters": self.cluster_report,
            "selection": self.selection_report,
            "portfolios": self.portfolio_report,
            "ml_importance": {
                "importance": self.ml_report.get("importance", {}),
                "permutation_importance": self.ml_report.get("permutation_importance", {}),
            },
        }
        log_path = output_dir / "factor_selection_log.json"
        log_path.write_text(json.dumps(selection_log, indent=2, cls=_NumpyEncoder, default=str), encoding="utf-8")
        logging.info(f"Selection log saved to {log_path}")
