# src/pipelines/factor/factor_loader.py
"""加载 Qlib Alpha158 因子及额外特征。"""
import logging
import pandas as pd
from typing import Optional, List

import qlib
from qlib.contrib.data.handler import Alpha158


class DFeatureLoader:
    """从 Qlib 数据加载额外特征（非 Alpha158 特征）。"""

    def __init__(self, fields: List[str], qlib_bin_path: str, instruments: str,
                 start: str, end: str):
        self.fields = fields
        self.qlib_bin_path = qlib_bin_path
        self.instruments = instruments
        self.start = start
        self.end = end

    def load(self) -> pd.DataFrame:
        """从 Qlib 加载指定字段。"""
        from qlib.data import D
        df = D.features(self.instruments, self.fields,
                        start_time=self.start, end_time=self.end)
        return df


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
    ) -> pd.DataFrame:
        """
        qlib.init() → Alpha158 handler → fetch DataFrame.

        如果指定 extra_fields，额外加载这些字段并合并到结果中。
        """
        qlib.init(provider_uri=self.provider_uri)

        handler = Alpha158(
            instruments=instruments,
            start_time=start,
            end_time=end,
        )
        df = handler.fetch()
        logging.info(f"Loaded Alpha158 factors: {df.shape[1]} features, {len(df)} rows")

        # 加载额外特征
        if extra_fields:
            extra_loader = DFeatureLoader(
                fields=extra_fields,
                qlib_bin_path=self.qlib_bin_path,
                instruments=instruments,
                start=start,
                end=end,
            )
            extra_df = extra_loader.load()
            # 合并
            common_index = df.index.intersection(extra_df.index)
            df = df.loc[common_index]
            extra_df = extra_df.loc[common_index]
            for col in extra_df.columns:
                df[col] = extra_df[col]
            logging.info(f"Added {len(extra_fields)} extra fields. Total features: {df.shape[1]}")

        return df
