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
    ) -> pd.DataFrame:
        """
        qlib.init() → Alpha158 handler → fetch DataFrame.

        如果指定 extra_fields，额外加载这些字段并合并到结果中。
        """
        # Windows spawn 模式导致多进程加载 scipy DLL 时页面文件不足
        # 限制并发进程数为 1，避免内存问题
        from qlib.config import C
        C["NUM_USABLE_CPU"] = 1

        qlib.init(provider_uri=self.provider_uri)

        handler = Alpha158(
            instruments=instruments,
            start_time=start,
            end_time=end,
        )
        df = handler.fetch()

        # LABEL0 = Ref($close, -2)/Ref($close, -1) - 1, 依赖未来数据 (T+1/T+2 收盘价)
        # 作为训练/回测特征会导致数据泄露, 必须排除
        if "LABEL0" in df.columns:
            df = df.drop(columns=["LABEL0"])
            logging.info("Dropped LABEL0 (future data leakage)")

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
