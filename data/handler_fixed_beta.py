import sys
from pathlib import Path
from typing import Optional, Union, List

# 将项目根目录添加到 sys.path
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd
import polars as pl
from qlib.contrib.data.handler import Alpha158 as QlibAlpha158
from qlib.data import D
from qlib.config import C
from qlib.data.dataset.handler import DataHandler, DATA_KEY_TYPE
from path_target import PathTargetBuilder, PathTargetConfig


class Alpha158FixedBetaHandler(QlibAlpha158):
    """
    Alpha158 因子 + Path Target Handler（固定 beta 版本）。

    与 Alpha158PathTargetHandler 的区别：
    - 不计算 rolling beta（省去 ~300-500 MB 内存）
    - 直接使用 beta=1（假设所有股票与基准完全相关）
    - pnl_adj = pnl - alpha * mkt_pnl（简单市场中性化）

    Parameters
    ----------
    benchmark : str
        市场基准代码，默认为 "SH000852" (中证1000)
    path_target_config : PathTargetConfig
        Path Target 配置对象
    beta_alpha : float
        市场 neutral 强度，默认 0.5
    """

    def __init__(
        self,
        benchmark: str = "SH000852",
        path_target_config: Optional[PathTargetConfig] = None,
        beta_alpha: float = 0.5,
        **kwargs
    ):
        self.benchmark = benchmark
        self.target_cfg = path_target_config or PathTargetConfig()
        self.beta_alpha = beta_alpha
        # 覆盖 PathTargetConfig 的 beta_alpha（因为不再传入 beta_df）
        self.target_cfg.beta_alpha = beta_alpha
        super().__init__(**kwargs)

    def fetch(
        self,
        selector=None,
        level: Union[str, int] = "datetime",
        col_set: Union[str, List[str]] = DataHandler.CS_ALL,
        data_key: DATA_KEY_TYPE = DataHandler.DK_I,
        squeeze: bool = False,
        proc_func=None,
    ) -> pd.DataFrame:
        """
        获取 Alpha158 features + Path Target label（固定 beta 版本）。

        内存优化：
        - 不计算 rolling beta，省去 ~300-500 MB
        - 直接使用 beta=1 矩阵

        Parameters
        ----------
        col_set : str or list
            - 'feature': 只返回特征列 (158列)
            - 'label': 只返回标签列 (1列)
            - '__all': 返回所有列（去掉 MultiIndex 第一级）
            - '__raw': 返回原始数据（保持 MultiIndex）
            - ['feature', 'label']: 返回特征和标签列

        Returns
        -------
        pd.DataFrame
            根据 col_set 过滤后的数据
        """
        from qlib.data.dataset.utils import fetch_df_by_col

        # 处理默认参数
        if selector is None:
            selector = slice(None, None, None)

        # 判断是否需要返回 label
        need_label = False
        if isinstance(col_set, str):
            need_label = col_set == "label" or col_set in (DataHandler.CS_ALL, DataHandler.CS_RAW)
        elif isinstance(col_set, list):
            need_label = "label" in col_set

        # 调用父类的 fetch 方法获取基础数据
        # 注意：父类会根据 col_set 进行过滤，但我们需要自己处理 label
        # 所以先获取 __raw 数据，然后自己处理 col_set
        df = super().fetch(
            selector=selector,
            level=level,
            col_set=DataHandler.CS_RAW,  # 获取原始 MultiIndex 数据
            data_key=data_key,
            squeeze=False,
            proc_func=proc_func,
        )

        # 移除默认的 LABEL0 列（如果存在）
        if isinstance(df.columns, pd.MultiIndex):
            label_cols = [c for c in df.columns if c[0] == 'label' and c[1] == 'LABEL0']
            if label_cols:
                df = df.drop(columns=label_cols)

        # 只有在需要 label 时才计算并添加 target
        if need_label:
            # 计算 Path Target
            instruments = self.instruments
            start_time = self.start_time
            end_time = self.end_time

            provider_uri = C.provider_uri.get(C.DEFAULT_FREQ, "data/qlib_data")

            # Handle instruments - could be string (market) or list
            if isinstance(instruments, str):
                instruments_file = Path(provider_uri) / "instruments" / f"{instruments}.txt"
                if instruments_file.exists():
                    inst_df = pd.read_csv(instruments_file, sep='\t', header=None)
                    instruments_list = inst_df[0].tolist()
                else:
                    instruments_list = [instruments]
            else:
                instruments_list = list(instruments)

            # Fetch stock close prices
            raw_close = D.features(instruments_list, ["$close"], start_time, end_time)
            if raw_close.empty:
                raise ValueError(f"No close data for {instruments} between {start_time} and {end_time}")

            close_wide = raw_close.unstack(level=0)
            close_wide.columns = close_wide.columns.get_level_values(1)
            close_wide = close_wide.reset_index().rename(columns={"datetime": "date"})

            # Fetch benchmark close
            bench_close = D.features([self.benchmark], ["$close"], start_time, end_time)
            if bench_close.empty:
                raise ValueError(f"No benchmark data for {self.benchmark}")

            bench_wide = bench_close.unstack(level=0)
            bench_wide.columns = bench_wide.columns.get_level_values(1)
            bench_wide = bench_wide.reset_index().rename(columns={"datetime": "date"})

            # Create fixed beta matrix (all 1s)
            codes = [c for c in close_wide.columns if c != "date"]
            T = len(close_wide)
            beta_fixed = pl.DataFrame({
                "date": close_wide["date"],
                **{c: pl.Series([1.0] * T) for c in codes}
            })

            # Convert to polars
            close_pl = pl.from_pandas(close_wide)
            bench_pl = pl.from_pandas(bench_wide)

            # Build target with fixed beta
            builder = PathTargetBuilder(self.target_cfg)
            target_series = builder.build(close_pl, bench_pl, beta_fixed)

            # Format target column (使用小写 'label' 以符合 qlib 规范)
            target_df = target_series.to_frame("target")
            target_df.index.names = ["datetime", "instrument"]
            target_df.columns = pd.MultiIndex.from_tuples([("label", "target")])

            # 确保 df 有正确的 MultiIndex 结构
            if not isinstance(df.columns, pd.MultiIndex):
                df.columns = pd.MultiIndex.from_product([["feature"], df.columns])

            # 对齐 index 并合并
            target_df = target_df.reindex(df.index)
            df = pd.concat([df, target_df], axis=1)

        # 使用 fetch_df_by_col 进行最终的列过滤
        df = fetch_df_by_col(df, col_set)

        # 处理 squeeze
        if squeeze:
            df = df.squeeze()
            if isinstance(selector, (str, pd.Timestamp)):
                df = df.reset_index(level=level, drop=True)

        return df