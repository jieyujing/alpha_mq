# src/pipelines/factor/label_builder.py
"""构建多周期收益率标签。"""
import logging
import os
import pandas as pd
import polars as pl
from typing import List, Dict, Union
from datetime import datetime, timedelta

class LabelBuilder:
    """基于 pandas 构建多周期 forward return 标签。"""

    def __init__(self, qlib_bin_path: str):
        # 兼容原来的参数名，实际为 parquet_input
        self.parquet_input = qlib_bin_path

    def compute_labels(
        self,
        close_data: pd.DataFrame,
        periods: List[int] = [1, 5, 10, 20],
    ) -> Dict[str, pd.Series]:
        """
        对每个 period N: label_Nd = close(t+N) / close(t) - 1

        close_data: DataFrame with MultiIndex(datetime, instrument) and 'close' column.
        返回 {"label_1d": Series, "label_5d": Series, ...}
        """
        labels = {}
        for period in periods:
            label_name = f"label_{period}d"
            shifted = close_data.groupby(level="instrument")["close"].shift(-period)
            labels[label_name] = shifted / close_data["close"] - 1
            logging.info(f"Computed {label_name}: {labels[label_name].notna().sum()} valid values")
        return labels

    def load_close_prices(
        self,
        instruments: Union[str, List[str]],
        start: str,
        end: str,
        buffer_days: int = 30,
    ) -> pd.DataFrame:
        """
        从 Parquet 宽表加载 close 价格，带前后缓冲（用于 forward return 计算）。

        buffer_days: 向后多加载的天数，确保未来 N 日 return 不全部为 NaN。
        instruments: symbol 列表（此处为了简化，由于我们直接扫描所有 parquet，可以全量加载然后再过滤，或依赖输入 parquet 的自然内容）
        """
        extended_end = (datetime.strptime(end, "%Y-%m-%d") + timedelta(days=buffer_days)).strftime("%Y-%m-%d")
        
        daily_path = os.path.join(self.parquet_input, "daily", "*.parquet")
        logging.info(f"Scanning parquet files for labels from {daily_path}")
        
        lf = pl.scan_parquet(daily_path, include_file_paths="filepath")
        
        # 提取 instrument
        lf = lf.with_columns(
            pl.col("filepath")
            .str.split("/")
            .list.last()
            .str.split(r"\\")
            .list.last()
            .str.replace(".parquet", "")
            .alias("instrument")
        )
        
        # 筛选时间和列
        lf = lf.filter((pl.col("date") >= start) & (pl.col("date") <= extended_end))
        lf = lf.select(["date", "instrument", "close"])
        
        # 按需过滤 instruments
        if isinstance(instruments, list) and len(instruments) > 0:
            lf = lf.filter(pl.col("instrument").is_in(instruments))
            
        df = lf.collect().to_pandas()
        
        if df.empty:
            logging.warning("No close prices found for the given date range and instruments.")
            # 返回一个空的结构保证下游不崩溃
            pdf = pd.DataFrame(columns=["close"])
            pdf.index = pd.MultiIndex.from_arrays([[], []], names=["datetime", "instrument"])
            return pdf

        df["datetime"] = pd.to_datetime(df["date"])
        df = df.set_index(["datetime", "instrument"]).sort_index()
        
        close_df = df[["close"]]
        
        logging.info(f"Loaded close prices: {len(close_df)} rows, range {start} to {extended_end}")
        return close_df
