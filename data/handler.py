import sys
from pathlib import Path
from typing import Optional

# Task 1: 修复导入路径 - 将项目根目录添加到 sys.path
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd
import polars as pl
from qlib.contrib.data.handler import Alpha158
from path_target import PathTargetBuilder, PathTargetConfig
from qlib.data import D


# Task 2: 重命名类为 Alpha158PathTargetHandler
class Alpha158PathTargetHandler(Alpha158):
    """
    Alpha158 因子 + Path Target (基于 Triple Barrier Method 的路径质量评分) Handler.

    Parameters
    ----------
    benchmark : str
        市场基准代码，默认为 "SH000852" (中证1000)
    path_target_config : PathTargetConfig
        Path Target 配置对象
    beta_window : int
        计算 rolling beta 的窗口期，默认 60 天
    """

    def __init__(
        self,
        benchmark: str = "SH000852",
        path_target_config: Optional[PathTargetConfig] = None,
        beta_window: int = 60,
        **kwargs
    ):
        self.benchmark = benchmark
        self.target_cfg = path_target_config or PathTargetConfig()
        self.beta_window = beta_window
        super().__init__(**kwargs)

    def _get_label_config(self):
        # Override Alpha158 default label
        # We merge our target in fetch()
        return [], []

    def fetch(self, *args, **kwargs):
        # 1. Fetch Alpha158 features
        df = super().fetch(*args, **kwargs)

        # 2. Re-fetch raw close/bench
        instruments = self.instruments
        start_time = self.start_time
        end_time = self.end_time

        # Fetch close price
        raw_close = D.features(instruments, ["$close"], start_time, end_time)

        # Task 4: 添加数据缺失处理 - 空数据检查
        if raw_close.empty:
            raise ValueError(
                f"No close data found for instruments {instruments} "
                f"between {start_time} and {end_time}"
            )

        close_wide = raw_close.unstack(level=0)
        close_wide.columns = close_wide.columns.get_level_values(1)
        close_wide = close_wide.reset_index().rename(columns={"datetime": "date"})

        # Task 3: 修复 benchmark 参数化 - 使用 self.benchmark
        bench_close = D.features([self.benchmark], ["$close"], start_time, end_time)
        bench_wide = bench_close.unstack(level=0)
        bench_wide.columns = bench_wide.columns.get_level_values(1)
        bench_wide = bench_wide.reset_index().rename(columns={"datetime": "date"})

        # 3. Calculate Rolling Beta (使用 self.beta_window)
        # Returns
        stock_ret = close_wide.set_index("date").pct_change()
        bench_ret = bench_wide.set_index("date")[self.benchmark].pct_change()

        def calculate_rolling_beta(s_ret, b_ret, window):
            # Beta = Cov(s, b) / Var(b)
            cov = s_ret.rolling(window, min_periods=window // 2).cov(b_ret)
            var = b_ret.rolling(window, min_periods=window // 2).var()
            return cov / var

        beta_df = stock_ret.apply(
            lambda x: calculate_rolling_beta(x, bench_ret, self.beta_window)
        )

        # Task 4: 添加数据缺失处理 - beta clip 处理
        beta_df = beta_df.fillna(1.0).clip(0.1, 3.0).reset_index()

        # Convert to polars for PathTargetBuilder
        close_pl = pl.from_pandas(close_wide)
        bench_pl = pl.from_pandas(bench_wide)
        beta_pl = pl.from_pandas(beta_df)

        # 4. Build target
        builder = PathTargetBuilder(self.target_cfg)
        target_series = builder.build(close_pl, bench_pl, beta_pl)
        # target_series is MultiIndex(date, code)

        # Task 5: 完善返回格式 - target 列名符合 qlib 规范
        target_df = target_series.to_frame("target")
        target_df.index.names = ["datetime", "instrument"]
        target_df.columns = pd.MultiIndex.from_tuples([("LABEL", "target")])

        # Ensure df columns are MultiIndex
        if not isinstance(df.columns, pd.MultiIndex):
            df.columns = pd.MultiIndex.from_product([["FEATURE"], df.columns])

        # Task 5: 合并时处理对齐
        target_df = target_df.reindex(df.index)
        result = pd.concat([df, target_df], axis=1)
        return result.sort_index(axis=1)