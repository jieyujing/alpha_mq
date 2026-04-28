# src/pipelines/factor/alpha158_pipeline.py
"""Alpha158 因子生成 Pipeline — 计算因子和标签，输出完整因子池。"""
import logging
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from pipelines.base import DataPipeline
from pipelines.factor.factor_loader import FactorLoader
from pipelines.factor.label_builder import LabelBuilder


class Alpha158Pipeline(DataPipeline):
    """
    Alpha158 因子生成 Pipeline。

    Stages:
    - factor_compute: Alpha158 handler -> DataFrame
    - label_compute: multi-period forward returns
    - export: save Parquet + YAML
    - report: generate factor summary
    """

    STAGE_METHOD_MAP = {
        "factor_compute": "factor_compute",
        "label_compute": "label_compute",
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

        # 数据输入配置
        self.parquet_input = data_cfg.get("parquet_input", "data/parquet")
        self.instruments = data_cfg.get("instruments", "csi1000")
        self.start_date = data_cfg.get("start_date", "2020-01-01")
        self.end_date = data_cfg.get("end_date") or datetime.now().strftime("%Y-%m-%d")

        # Runtime state
        self.factors_df: Optional[pd.DataFrame] = None
        self.labels_dict: Optional[dict] = None
        self.quality_summary: Optional[dict] = None

    # -- Stage: factor_compute --

    def factor_compute(self):
        """Alpha158 handler -> DataFrame。"""
        loader = FactorLoader(parquet_input=self.parquet_input)
        self.factors_df = loader.load_alpha158(
            instruments=self.instruments,
            start=self.start_date,
            end=self.end_date,
        )
        logging.info(f"Factor compute done: {self.factors_df.shape}")

    # -- Stage: label_compute --

    def label_compute(self):
        """计算多周期 forward return 标签。"""
        periods = self.config.get("labels", {}).get("periods", [1, 5, 10, 20])
        
        # 获取有效样本的日期范围
        date_range = self.factors_df.index.get_level_values("datetime")
        symbol_list = list(self.factors_df.index.get_level_values("instrument").unique())
        start = str(date_range.min().date())
        end = str(date_range.max().date())

        label_builder = LabelBuilder(qlib_bin_path=self.parquet_input)
        close_df = label_builder.load_close_prices(
            instruments=symbol_list,
            start=start,
            end=end,
            buffer_days=max(periods) + 5
        )

        self.labels_dict = label_builder.compute_labels(close_df, periods=periods)
        logging.info(f"Labels computed: {list(self.labels_dict.keys())}")

    # -- Stage: export --

    def export(self):
        """保存因子和标签到最终 Parquet，并附加 close 价格用于回测。"""
        output_cfg = self.config.get("output", {})
        periods = self.config.get("labels", {}).get("periods", [1, 5, 10, 20])

        # 合并因子与标签
        result_df = self.factors_df.copy()
        if self.labels_dict:
            for label_name, lbl in self.labels_dict.items():
                # 对齐索引顺序
                if lbl.index.names != result_df.index.names:
                    lbl = lbl.swaplevel().sort_index()
                    lbl.index.names = result_df.index.names
                result_df[label_name] = lbl.loc[result_df.index]

        # 附加 close 价格：从 daily parquet 重新加载并与因子池索引对齐
        close_series = self._load_close_for_export()
        if close_series is not None:
            # 对齐到因子池的索引
            result_df["close"] = close_series.reindex(result_df.index)
            n_close = result_df["close"].notna().sum()
            logging.info(f"Attached close prices: {n_close} valid values")

        # 保存 Parquet
        parquet_path = Path(output_cfg.get("parquet", "data/factor_pool.parquet"))
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        result_df.to_parquet(parquet_path)
        logging.info(f"Factor pool saved to {parquet_path} ({result_df.shape})")

        # 保存 YAML
        yaml_path = Path(output_cfg.get("yaml", "data/alpha158_pool.yaml"))
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        yaml_content = {
            "factor_pool": {
                "total_factors": int(self.factors_df.shape[1]),
                "total_rows": int(result_df.shape[0]),
                "factor_names": sorted(self.factors_df.columns.tolist()),
                "label_names": [f"label_{p}d" for p in periods if f"label_{p}d" in (self.labels_dict or {})],
            },
            "data_config": self.config.get("data", {}),
        }
        with open(yaml_path, "w") as f:
            yaml.dump(yaml_content, f, default_flow_style=False, sort_keys=False)
        logging.info(f"Factor pool metadata saved to {yaml_path}")

    def _load_close_for_export(self) -> pd.Series | None:
        """从 daily parquet 加载 close 价格，返回与因子池索引对齐的 Series。"""
        import os
        import polars as pl

        daily_path = os.path.join(self.parquet_input, "daily", "*.parquet")
        date_range = self.factors_df.index.get_level_values("datetime")
        start = str(date_range.min().date())
        end = str(date_range.max().date())

        try:
            lf = pl.scan_parquet(daily_path, include_file_paths="filepath").with_columns(
                pl.col("filepath").str.split("/").list.last().str.split(r"\\").list.last().str.replace(".parquet", "").alias("instrument")
            ).filter(
                (pl.col("date") >= start) & (pl.col("date") <= end)
            ).select(["date", "instrument", "close"])

            df = lf.collect().to_pandas()
            df["datetime"] = pd.to_datetime(df["date"])
            df = df.set_index(["datetime", "instrument"])
            return df["close"]
        except Exception as e:
            logging.warning(f"Failed to load close prices for export: {e}")
            return None

    # -- Stage: report --

    def generate_report(self):
        """生成因子摘要报告（Markdown 格式）。"""
        output_cfg = self.config.get("output", {})
        report_path = output_cfg.get("report", "data/quality/factor_report.md")

        Path(report_path).parent.mkdir(parents=True, exist_ok=True)

        lines = []
        lines.append("# Alpha158 Factor Summary")
        lines.append("")

        # Factor stats
        lines.append("## Factor Statistics")
        lines.append("")
        lines.append(f"- **Total factors**: {self.factors_df.shape[1]}")
        lines.append(f"- **Total samples**: {self.factors_df.shape[0]}")
        lines.append(f"- **Date range**: {self.factors_df.index.get_level_values('datetime').min()} to {self.factors_df.index.get_level_values('datetime').max()}")
        lines.append(f"- **Instruments**: {self.factors_df.index.get_level_values('instrument').nunique()}")
        lines.append("")

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        logging.info(f"Factor summary saved: {report_path}")
