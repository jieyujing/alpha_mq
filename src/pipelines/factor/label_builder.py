# src/pipelines/factor/label_builder.py
"""构建多周期收益率标签。"""
import logging
import pandas as pd
from typing import List, Dict


class LabelBuilder:
    """基于 pandas 构建多周期 forward return 标签。"""

    def __init__(self, qlib_bin_path: str):
        self.qlib_bin_path = qlib_bin_path

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
        instruments: str,
        start: str,
        end: str,
        buffer_days: int = 30,
    ) -> pd.DataFrame:
        """
        从 Qlib 加载 close 价格，带前后缓冲（用于 forward return 计算）。

        buffer_days: 向后多加载的天数，确保未来 N 日 return 不全部为 NaN。
        """
        from datetime import datetime, timedelta
        from qlib.data import D

        extended_end = (datetime.strptime(end, "%Y-%m-%d")
                        + timedelta(days=buffer_days)).strftime("%Y-%m-%d")
        close_df = D.features(instruments, ["$close"],
                              start_time=start, end_time=extended_end)
        close_df.columns = ["close"]
        logging.info(f"Loaded close prices: {len(close_df)} rows, range {start} to {extended_end}")
        return close_df
