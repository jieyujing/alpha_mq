# src/pipelines/factor/factor_loader.py
"""加载 Qlib Alpha158 因子及额外特征。"""
import logging
import pandas as pd
from typing import Optional, List

import qlib
from qlib.contrib.data.handler import Alpha158


class FactorLoader:
    """加载 Qlib Alpha158 因子。"""

    def __init__(self, qlib_bin_path: str, provider_uri: Optional[str] = None):
        self.qlib_bin_path = qlib_bin_path
        self.provider_uri = provider_uri or qlib_bin_path

    def load_alpha158(
        self,
        instruments: str,
        start: str,
        end: str,
        extra_fields: Optional[List[str]] = None,
        drop_labels: bool = True,
    ) -> pd.DataFrame:
        """
        qlib.init() → Alpha158 handler → fetch DataFrame.

        如果指定 extra_fields，额外加载这些字段并合并到结果中。

        Args:
            drop_labels: 是否删除 Alpha158 内置的 LABEL 列（防止数据泄露）。
                         LABEL0 是当日收益率，不应作为预测特征。
        """
        qlib.init(provider_uri=self.provider_uri)

        handler = Alpha158(
            instruments=instruments,
            start_time=start,
            end_time=end,
        )
        df = handler.fetch()

        # 删除 qlib 内置的 LABEL 列（防止数据泄露）
        if drop_labels:
            label_cols = [c for c in df.columns if self._is_label_column(c)]
            if label_cols:
                df = df.drop(columns=label_cols)
                logging.info(f"Dropped {len(label_cols)} LABEL columns to prevent data leakage")

        logging.info(f"Loaded Alpha158 factors: {df.shape[1]} features, {len(df)} rows")

        # 加载额外特征
        if extra_fields:
            # 从已加载的 df 的 index 中提取 instrument 列表
            symbol_list = list(df.index.get_level_values("instrument").unique())
            from qlib.data import D
            extra_df = D.features(
                symbol_list,
                [f"${f}" for f in extra_fields],
                start_time=start,
                end_time=end,
                freq="day",
            )
            # 重命名列 (去掉 $ 前缀)
            extra_df.columns = [c.lstrip("$") for c in extra_df.columns]
            # D.features 返回的 index 是 (instrument, datetime)，需要对齐到 (datetime, instrument)
            if extra_df.index.names == ["instrument", "datetime"]:
                extra_df = extra_df.swaplevel("instrument", "datetime").sort_index()
                extra_df.index.names = ["datetime", "instrument"]
            # 合并
            common_index = df.index.intersection(extra_df.index)
            if len(common_index) == 0:
                logging.warning(f"No common index between Alpha158 and extra fields. Skipping extra fields.")
                return df
            df = df.loc[common_index]
            extra_df = extra_df.loc[common_index]
            for col in extra_df.columns:
                df[col] = extra_df[col]
            logging.info(f"Added {len(extra_fields)} extra fields. Total features: {df.shape[1]}")

        return df

    @staticmethod
    def _is_label_column(column) -> bool:
        """识别 Qlib flat columns 与 MultiIndex columns 中的标签列。"""
        if isinstance(column, tuple):
            parts = [str(part) for part in column if part is not None]
            return any(part.startswith("LABEL") for part in parts) or any(
                part.lower() == "label" for part in parts
            )
        return str(column).startswith("LABEL")
