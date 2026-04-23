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
    - ingest_bin: CSV -> Qlib binary
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

    # -- Stage: ingest_bin --

    def ingest_bin(self):
        """调用 QlibIngestor.dump_bin() 将 CSV 转为 Qlib binary。"""
        ingestor = QlibIngestor(qlib_dir=self.qlib_bin)
        success = ingestor.dump_bin(csv_path=self.qlib_csv)
        if not success:
            raise RuntimeError("dump_bin failed -- cannot proceed without Qlib binary data")
        logging.info(f"Qlib binary data written to {self.qlib_bin}")

    # -- Stage: factor_compute --

    def factor_compute(self):
        """Alpha158 handler -> DataFrame。"""
        loader = FactorLoader(qlib_bin_path=self.qlib_bin)
        extra_fields = self.config.get("data", {}).get("extra_fields", None)
        self.factors_df = loader.load_alpha158(
            instruments=self.instruments,
            start=self.start_date,
            end=self.end_date,
            extra_fields=extra_fields,
        )
        logging.info(f"Factor compute done: {self.factors_df.shape}")

    # -- Stage: label_compute --

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

    # -- Stage: filter --

    def run_filter(self):
        """构建 FilterContext -> 执行责任链。"""
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
        self.filter_artifacts["filter_logs"] = ctx.logs

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

    # -- Stage: export --

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

    # -- Stage: report --

    def generate_report(self):
        """生成因子质量报告。"""
        from pipelines.factor.factor_report import FactorQualityReporter

        output_cfg = self.config.get("output", {})
        report_path = output_cfg.get("report", "data/quality/factor_report.md")

        reporter = FactorQualityReporter(output_path=report_path)
        reporter.generate(
            X_before=self.factors_df,
            X_after=self.filtered_X,
            y=self.filtered_y,
            filter_artifacts=self.filter_artifacts or {},
            filter_logs=self.filter_artifacts.get("filter_logs", []) if self.filter_artifacts else [],
            all_labels=self.labels_dict or {},
        )
