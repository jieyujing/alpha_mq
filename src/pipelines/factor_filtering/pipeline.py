"""因子筛选流水线主编排器。"""

import logging
from datetime import datetime
from pathlib import Path

import polars as pl

from pipelines.base import DataPipeline
from pipelines.factor_filtering.steps.step00_data_qa import DataAndLabelQA
from pipelines.factor_filtering.steps.step02_profiling import SingleFactorProfiler as FactorProfiler
from pipelines.factor_filtering.steps.step05_clustering import FactorClustering
from pipelines.factor_filtering.steps.step08_ml_importance import MLImportanceVerifier
from pipelines.factor_filtering.steps.step07_portfolio import PortfolioValidator


class FactorFilteringPipeline(DataPipeline):
    """按序执行各阶段因子筛选步骤的流水线编排器。

    Stages: load -> qa -> profile -> cluster -> portfolio -> ml_importance -> report
    """

    STAGE_METHOD_MAP = {
        "load": "load_data",
        "qa": "run_data_qa",
        "profile": "run_profiling",
        "cluster": "run_clustering",
        "portfolio": "run_portfolio",
        "ml_importance": "run_ml_importance",
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
        logging.info(f"Loaded factor pool: {self.df.shape}")

    # --- Stage: qa ---

    def run_data_qa(self):
        step = DataAndLabelQA()
        self.df, self.qa_report = step.process(self.df)
        n_null = self.df.null_count().sum_horizontal().sum()
        logging.info(f"Data QA done. Total nulls after cleaning: {n_null}")

    # --- Stage: profile ---

    def run_profiling(self):
        step = FactorProfiler(label_col=self.label_col)
        factor_cols = [c for c in self.df.columns if c not in ("datetime", "instrument") and not c.startswith("label")]

        self.ic_results = {}
        for col in factor_cols:
            daily_ic = step.compute_daily_ic(self.df, col)
            ic_series = daily_ic.select(pl.col("ic")).to_series().drop_nulls()
            rank_ic = ic_series.mean() if len(ic_series) > 0 else 0.0
            self.ic_results[col] = float(rank_ic)

        mean_ic = sum(self.ic_results.values()) / max(len(self.ic_results), 1)
        logging.info(f"Profiling done. Mean |IC|={abs(mean_ic):.4f} across {len(self.ic_results)} factors")

    # --- Stage: cluster ---

    def run_clustering(self):
        step = FactorClustering()
        factor_cols = [c for c in self.df.columns if c not in ("datetime", "instrument") and not c.startswith("label")]
        self.cluster_labels = step.fit_predict(self.df, factor_cols, self.label_col)
        n_clusters = len(set(self.cluster_labels.values()))
        logging.info(f"Clustering done. {n_clusters} clusters across {len(factor_cols)} factors")

    # --- Stage: portfolio ---

    def run_portfolio(self):
        step = PortfolioValidator()
        _, self.portfolio_metrics = step.process(self.df, self.ic_results)
        logging.info(f"Portfolio validation done. Metrics: {self.portfolio_metrics}")

    # --- Stage: ml_importance ---

    def run_ml_importance(self):
        step = MLImportanceVerifier()
        _, report = step.process(self.df)
        self.ml_importance = report.get("importance", {})
        top5 = sorted(self.ml_importance.items(), key=lambda x: x[1], reverse=True)[:5]
        logging.info(f"ML importance done. Top 5: {top5}")

    # --- Stage: report ---

    def generate_report(self):
        output_cfg = self.config.get("pipeline", {})
        output_dir = Path(output_cfg.get("output_dir", "data/reports/factor_filtering"))
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "factor_filter_report.md"

        lines = []
        lines.append("# Factor Filtering Report")
        lines.append("")
        lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Data Source**: {self.config.get('data', {}).get('factor_path', 'N/A')}")
        lines.append(f"**Label Column**: {self.label_col}")
        lines.append("")

        # 1. Data QA summary
        lines.append("## 1. Data QA Summary")
        lines.append("")
        n_null = self.df.null_count().sum_horizontal().sum()
        lines.append(f"- Total rows: {self.df.height}")
        lines.append(f"- Total columns: {self.df.width}")
        lines.append(f"- Total nulls after cleaning: {n_null}")
        lines.append("")

        # 2. Factor IC profiling
        lines.append("## 2. Factor IC Profiling (Top 20 by |IC|)")
        lines.append("")
        lines.append("| Rank | Factor | Rank IC |")
        lines.append("|------|--------|---------|")
        sorted_ic = sorted(self.ic_results.items(), key=lambda x: abs(x[1]), reverse=True)
        for rank, (feat, ic) in enumerate(sorted_ic[:20], 1):
            lines.append(f"| {rank} | {feat} | {ic:.4f} |")
        lines.append("")

        # 3. Clustering summary
        lines.append("## 3. Clustering Summary")
        lines.append("")
        lines.append("| Cluster | Factors |")
        lines.append("|---------|---------|")
        cluster_to_factors: dict[int, list[str]] = {}
        for factor, cluster_id in self.cluster_labels.items():
            cluster_to_factors.setdefault(cluster_id, []).append(factor)
        for cid in sorted(cluster_to_factors):
            factors_str = ", ".join(cluster_to_factors[cid][:5])
            if len(cluster_to_factors[cid]) > 5:
                factors_str += f" ... (+{len(cluster_to_factors[cid]) - 5})"
            lines.append(f"| {cid} | {factors_str} |")
        lines.append("")

        # 4. Portfolio metrics
        lines.append("## 4. Portfolio Validation Metrics")
        lines.append("")
        for k, v in self.portfolio_metrics.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

        # 5. ML importance
        lines.append("## 5. ML Feature Importance (Top 20)")
        lines.append("")
        lines.append("| Rank | Factor | Importance |")
        lines.append("|------|--------|------------|")
        sorted_imp = sorted(self.ml_importance.items(), key=lambda x: x[1], reverse=True)
        for rank, (feat, imp) in enumerate(sorted_imp[:20], 1):
            lines.append(f"| {rank} | {feat} | {imp} |")
        lines.append("")

        report_path.write_text("\n".join(lines), encoding="utf-8")
        logging.info(f"Report saved to {report_path}")
