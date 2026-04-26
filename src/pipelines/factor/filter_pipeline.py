# src/pipelines/factor/filter_pipeline.py
"""因子过滤 Pipeline - 计算因子并筛选高质量因子池。"""
import logging
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from pipelines.base import DataPipeline
from pipelines.data_ingest.qlib_converter import QlibIngestor
from pipelines.data_quality import fill_financial_data, check_data_quality_summary, FINANCIAL_FIELDS
from pipelines.factor.factor_loader import FactorLoader
from pipelines.factor.label_builder import LabelBuilder
from pipelines.factor.filter_chain import (
    FilterContext,
    DropMissingLabelStep,
    DropLeakageStep,
    DropHighMissingFeatureStep,
    DropHighInfFeatureStep,
    DropLowVarianceFeatureStep,
    FactorQualityFilterStep,
    DeduplicateStep,
)


class FactorFilterPipeline(DataPipeline):
    """
    因子过滤 Pipeline - 计算因子并筛选高质量因子池。

    Stages:
    - merge_gm_data: 合并 GM 原生数据 (history_1d + valuation + mktvalue)
    - ingest_bin: 转换为 Qlib binary
    - factor_compute: Alpha158 handler -> DataFrame
    - data_quality_check: 检查数据质量，财务数据向后填充
    - label_compute: multi-period forward returns
    - filter: responsibility chain filtering
    - export: save Parquet + YAML
    - report: generate factor quality report
    """

    STAGE_METHOD_MAP = {
        "merge_gm_data": "merge_gm_data",
        "ingest_bin": "ingest_bin",
        "factor_compute": "factor_compute",
        "data_quality_check": "data_quality_check",
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

        # GM 原生数据目录
        self.exports_base = Path(data_cfg.get("exports_base", "data/exports"))
        self.history_dir = Path(data_cfg.get("history_dir", self.exports_base / "history_1d"))
        self.valuation_dir = Path(data_cfg.get("valuation_dir", self.exports_base / "valuation"))
        self.mktvalue_dir = Path(data_cfg.get("mktvalue_dir", self.exports_base / "mktvalue"))
        self.adj_factor_dir = Path(data_cfg.get("adj_factor_dir", self.exports_base / "adj_factor"))

        # Qlib 相关
        self.qlib_bin = data_cfg.get("qlib_bin", "data/qlib_bin")
        self.instruments = data_cfg.get("instruments", "csi1000")
        self.start_date = data_cfg.get("start_date", "2020-01-01")
        self.end_date = data_cfg.get("end_date") or datetime.now().strftime("%Y-%m-%d")

        # Runtime state
        self.merged_ohlcv: Optional[pd.DataFrame] = None
        self.factors_df: Optional[pd.DataFrame] = None
        self.labels_dict: Optional[dict] = None
        self.filtered_X: Optional[pd.DataFrame] = None
        self.filtered_y: Optional[pd.Series] = None
        self.filter_artifacts: Optional[dict] = None
        self.quality_summary: Optional[dict] = None

    # -- Stage: merge_gm_data --

    def merge_gm_data(self):
        """
        合并 GM 原生数据：history_1d + valuation + mktvalue + adj_factor

        输出格式：Qlib CSV 格式，保存到临时目录供 dump_bin 使用。
        """
        logging.info("Merging GM data from exports directory...")

        # 1. 加载日线行情
        ohlcv_df = self._load_history_1d()

        # 2. 加载估值数据 (PE/PB/PS/PCF)
        valuation_df = self._load_valuation()

        # 3. 加载市值数据
        mktvalue_df = self._load_mktvalue()

        # 4. 加载复权因子
        adj_factor_df = self._load_adj_factor()

        # 5. 合并所有数据
        merged_df = self._merge_all_data(ohlcv_df, valuation_df, mktvalue_df, adj_factor_df)

        # 6. 保存为 Qlib CSV 格式
        output_dir = Path(self.qlib_bin) / "ohlcv_tmp"
        output_dir.mkdir(parents=True, exist_ok=True)
        self._save_to_qlib_csv(merged_df, output_dir)

        self.merged_ohlcv = merged_df
        self.ohlcv_csv_dir = output_dir
        logging.info(f"Merged data saved to {output_dir}, {len(merged_df)} total rows")

    def _load_history_1d(self) -> pd.DataFrame:
        """加载日线 OHLCV 数据 (parquet 格式)。"""
        dfs = []
        for f in self.history_dir.glob("*.parquet"):
            try:
                df = pd.read_parquet(f)
                # GM 格式: symbol, frequency, open, high, low, close, volume, amount, pre_close, position, bob, eob
                if "bob" in df.columns:
                    df["date"] = pd.to_datetime(df["bob"]).dt.strftime("%Y-%m-%d")
                # 去掉交易所前缀: SHSE.600006 -> SH600006
                df["instrument"] = df["symbol"].str.replace("SHSE.", "SH").str.replace("SZSE.", "SZ")
                dfs.append(df[["instrument", "date", "open", "high", "low", "close", "volume", "amount"]])
            except Exception as e:
                logging.warning(f"Failed to load {f}: {e}")

        if not dfs:
            raise RuntimeError(f"No history_1d data found in {self.history_dir}")

        result = pd.concat(dfs, ignore_index=True)
        logging.info(f"Loaded history_1d: {len(result)} rows from {len(dfs)} files")
        return result

    def _load_valuation(self) -> pd.DataFrame:
        """加载估值数据 PE/PB/PS/PCF (CSV 格式)。"""
        dfs = []
        for f in self.valuation_dir.glob("*.csv"):
            try:
                df = pd.read_csv(f)
                df["instrument"] = df["symbol"].str.replace("SHSE.", "SH").str.replace("SZSE.", "SZ")
                dfs.append(df[["instrument", "trade_date", "pe_ttm", "pb_mrq", "ps_ttm", "pcf_ttm_oper"]])
            except Exception as e:
                logging.warning(f"Failed to load {f}: {e}")

        if not dfs:
            logging.warning(f"No valuation data found in {self.valuation_dir}")
            return pd.DataFrame(columns=["instrument", "trade_date", "pe_ttm", "pb_mrq", "ps_ttm", "pcf_ttm_oper"])

        result = pd.concat(dfs, ignore_index=True)
        result["date"] = pd.to_datetime(result["trade_date"]).dt.strftime("%Y-%m-%d")
        result = result.drop(columns=["trade_date"])
        logging.info(f"Loaded valuation: {len(result)} rows")
        return result

    def _load_mktvalue(self) -> pd.DataFrame:
        """加载市值数据 (CSV 格式)。"""
        dfs = []
        for f in self.mktvalue_dir.glob("*.csv"):
            try:
                df = pd.read_csv(f)
                df["instrument"] = df["symbol"].str.replace("SHSE.", "SH").str.replace("SZSE.", "SZ")
                # 保留总市值和流通市值
                cols = ["instrument", "trade_date"]
                if "total_mv" in df.columns:
                    cols.append("total_mv")
                if "circ_mv" in df.columns:
                    cols.append("circ_mv")
                dfs.append(df[cols])
            except Exception as e:
                logging.warning(f"Failed to load {f}: {e}")

        if not dfs:
            logging.warning(f"No mktvalue data found in {self.mktvalue_dir}")
            return pd.DataFrame(columns=["instrument", "trade_date", "tot_mv", "a_mv"])

        result = pd.concat(dfs, ignore_index=True)
        result["date"] = pd.to_datetime(result["trade_date"]).dt.strftime("%Y-%m-%d")
        result = result.drop(columns=["trade_date"])
        # 重命名列以匹配 Qlib 格式
        result = result.rename(columns={"total_mv": "tot_mv", "circ_mv": "a_mv"})
        logging.info(f"Loaded mktvalue: {len(result)} rows")
        return result

    def _load_adj_factor(self) -> pd.DataFrame:
        """加载复权因子 (CSV 格式，无 symbol 列，从文件名提取)。"""
        dfs = []
        for f in self.adj_factor_dir.glob("*.csv"):
            try:
                df = pd.read_csv(f)
                # 从文件名提取 symbol: SHSE.600006.csv -> SH600006
                symbol = f.stem  # SHSE.600006
                instrument = symbol.replace("SHSE.", "SH").replace("SZSE.", "SZ")
                df["instrument"] = instrument
                # 使用前复权因子 (adj_factor_fwd)
                df["factor"] = df.get("adj_factor_fwd", 1.0)
                dfs.append(df[["instrument", "trade_date", "factor"]])
            except Exception as e:
                logging.warning(f"Failed to load {f}: {e}")

        if not dfs:
            logging.warning(f"No adj_factor data found in {self.adj_factor_dir}")
            return pd.DataFrame(columns=["instrument", "trade_date", "factor"])

        result = pd.concat(dfs, ignore_index=True)
        result["date"] = pd.to_datetime(result["trade_date"]).dt.strftime("%Y-%m-%d")
        result = result.drop(columns=["trade_date"])
        logging.info(f"Loaded adj_factor: {len(result)} rows")
        return result

    def _merge_all_data(
        self,
        ohlcv: pd.DataFrame,
        valuation: pd.DataFrame,
        mktvalue: pd.DataFrame,
        adj_factor: pd.DataFrame,
    ) -> pd.DataFrame:
        """合并所有数据源。"""
        merged = ohlcv.copy()

        # 按 instrument + date 合并
        for df in [valuation, mktvalue, adj_factor]:
            if not df.empty:
                merged = merged.merge(df, on=["instrument", "date"], how="left")

        logging.info(f"Merged data: {merged.shape}, columns: {list(merged.columns)}")
        return merged

    def _save_to_qlib_csv(self, df: pd.DataFrame, output_dir: Path):
        """按股票保存为单独的 CSV 文件 (Qlib 格式，不含 instrument 列)。"""
        for instrument, group in df.groupby("instrument"):
            csv_path = output_dir / f"{instrument}.csv"
            group = group.sort_values("date")
            # 移除 instrument 列，Qlib CSV 格式只需要 date + 数值列
            data_cols = [c for c in group.columns if c not in ["instrument"]]
            group[data_cols].to_csv(csv_path, index=False, date_format="%Y-%m-%d")
        logging.info(f"Saved {len(df.groupby('instrument'))} instrument CSV files")

    # -- Stage: ingest_bin --

    def ingest_bin(self):
        """调用 QlibIngestor.dump_bin() 将合并后的 CSV 转为 Qlib binary。"""
        if not hasattr(self, "ohlcv_csv_dir") or not self.ohlcv_csv_dir.exists():
            raise RuntimeError("No merged data available - run merge_gm_data first")

        ingestor = QlibIngestor(qlib_dir=self.qlib_bin)
        success = ingestor.dump_bin(csv_path=str(self.ohlcv_csv_dir))
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

    # -- Stage: data_quality_check --

    def data_quality_check(self):
        """
        数据质量检查：财务数据向后填充，生成质量摘要。

        财务数据（PE、PB、PS、PCF）按季度发布，需要向后填充至下一个财报发布日。
        """
        quality_cfg = self.config.get("data_quality", {})
        max_fill_days = quality_cfg.get("max_fill_days", 90)

        # 检查填充前的数据质量
        pre_summary = check_data_quality_summary(self.factors_df)
        logging.info(f"Pre-fill quality: {len(pre_summary['missing_pct'])} features")

        # 执行财务数据向后填充
        fill_fields = [f for f in FINANCIAL_FIELDS if f in self.factors_df.columns]
        if fill_fields:
            self.factors_df = fill_financial_data(
                self.factors_df,
                fill_fields=fill_fields,
                max_fill_days=max_fill_days,
            )
            logging.info(f"Financial fields filled: {fill_fields}")

        # 检查填充后的数据质量
        post_summary = check_data_quality_summary(self.factors_df)
        self.quality_summary = {
            "pre_fill": pre_summary,
            "post_fill": post_summary,
            "fill_fields": fill_fields,
            "max_fill_days": max_fill_days,
        }

        # 记录财务数据覆盖改善情况
        for field in fill_fields:
            pre_cov = pre_summary["financial_coverage"].get(field, 0)
            post_cov = post_summary["financial_coverage"].get(field, 0)
            improvement = post_cov - pre_cov
            logging.info(f"  {field}: {pre_cov}% -> {post_cov}% (improved {improvement:.1f}%)")

    # -- Stage: label_compute --

    def label_compute(self):
        """计算多周期 forward return 标签。"""
        periods = self.config.get("labels", {}).get("periods", [1, 5, 10, 20])

        # 从已加载的因子数据中提取 instrument 列表
        symbol_list = list(self.factors_df.index.get_level_values("instrument").unique())
        date_range = self.factors_df.index.get_level_values("datetime")
        start = str(date_range.min().date())
        end = str(date_range.max().date())

        label_builder = LabelBuilder(qlib_bin_path=self.qlib_bin)
        close_df = label_builder.load_close_prices(
            instruments=symbol_list,
            start=start,
            end=end,
        )

        self.labels_dict = label_builder.compute_labels(close_df, periods=periods)
        logging.info(f"Labels computed: {list(self.labels_dict.keys())}")

    # -- Stage: filter --

    def run_filter(self):
        """构建 FilterContext -> 执行责任链。"""
        filter_cfg = self.config.get("filter", {})
        primary_label = self.config.get("labels", {}).get("primary", "label_5d")

        primary_y = self.labels_dict[primary_label]

        # 对齐 factors 和 labels：确保索引级别顺序一致
        # factors 使用 ['datetime', 'instrument']，labels 使用 ['instrument', 'datetime']
        if primary_y.index.names != self.factors_df.index.names:
            primary_y = primary_y.swaplevel().sort_index()
            primary_y.index.names = self.factors_df.index.names

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

        if "drop_leakage" in cfg:
            c = cfg["drop_leakage"]
            steps.append(DropLeakageStep(prefixes=c.get("prefixes", ["LABEL"])))

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

        if "deduplicate" in cfg:
            c = cfg["deduplicate"]
            steps.append(DeduplicateStep(
                corr_threshold=c.get("corr_threshold", 0.8),
                corr_method=c.get("corr_method", "spearman"),
                keep_by=c.get("keep_by", "ic_mean"),
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
                # 对齐索引顺序：labels 默认 ['instrument', 'datetime']，X 使用 ['datetime', 'instrument']
                if lbl.index.names != result_df.index.names:
                    lbl = lbl.swaplevel().sort_index()
                    lbl.index.names = result_df.index.names
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
