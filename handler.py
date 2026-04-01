import sys
from pathlib import Path
from typing import Optional, Union, List

# Task 1: 修复导入路径 - 将项目根目录添加到 sys.path
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd
import polars as pl
from qlib.contrib.data.handler import Alpha158
from path_target import PathTargetBuilder, PathTargetConfig
from qlib.data import D


def _load_instruments(instruments: Optional[Union[str, List[str]]], provider_uri: str) -> List[str]:
    """
    Load instruments list from file if instruments is a string market name.

    Parameters
    ----------
    instruments : str or list or None
        If str, treat as market name and load from instruments/{market}.txt
        If list, return as-is
        If None, return empty list
    provider_uri : str
        Path to qlib data directory

    Returns
    -------
    list of instrument codes
    """
    if instruments is None:
        return []

    if isinstance(instruments, list):
        return instruments

    # It's a string - try to load from file
    instruments_file = Path(provider_uri) / "instruments" / f"{instruments}.txt"
    if instruments_file.exists():
        df = pd.read_csv(instruments_file, sep='\t', header=None)
        return df[0].tolist()
    else:
        # Fall back to trying as a single instrument code
        return [instruments]  # type: ignore


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
        """
        获取 Alpha158 features + Path Target label.

        Override Alpha158.fetch() to merge custom path_target label.

        Returns
        -------
        pd.DataFrame
            MultiIndex columns with FEATURE and LABEL levels.
            FEATURE: Alpha158 因子
            LABEL: path_target (路径质量评分, 值域 0-1)
        """
        # 1. Fetch Alpha158 features
        df = super().fetch(*args, **kwargs)

        # 2. Re-fetch raw close/bench
        instruments = self.instruments
        start_time = self.start_time
        end_time = self.end_time

        # Convert instruments to list if needed (qlib D.features expects list)
        from qlib.config import C
        provider_uri = C.provider_uri.get(C.DEFAULT_FREQ, "data/qlib_data")
        instruments_list = _load_instruments(instruments, str(provider_uri))

        # Fetch close price
        raw_close = D.features(instruments_list, ["$close"], start_time, end_time)

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

        # Task 4: 添加数据缺失处理 - benchmark 数据检查
        if bench_close.empty:
            raise ValueError(
                f"No benchmark data found for {self.benchmark} "
                f"between {start_time} and {end_time}"
            )

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
            df.columns = pd.MultiIndex.from_product([["feature"], df.columns])

        # Task 5: 合并时处理对齐
        target_df = target_df.reindex(df.index)
        result = pd.concat([df, target_df], axis=1)
        return result.sort_index(axis=1)


class Alpha158PlusFundamentalsHandler(Alpha158PathTargetHandler):
    """
    Alpha158 因子 + 财务因子 + Path Target Handler.

    在 Alpha158 技术因子基础上添加估值和基本面财务因子。

    Parameters
    ----------
    fundamental_fields : list of str, optional
        要包含的财务因子字段列表，默认包含估值因子和部分基本面因子。
        字段格式为 qlib 表达式，如 "$pe_ttm", "$pb_lyr"。

    可用财务因子：
        - 估值因子: $pe_ttm, $pe_lyr, $pb_lyr, $pb_mrq, $ps_ttm, $pcf_ttm_oper
        - 基本面因子: $ttl_ast, $ttl_eqy, $ttl_liab, $fix_ast, $mny_cptl
    """

    DEFAULT_FUNDAMENTAL_FIELDS = [
        "$pe_ttm", "$pb_lyr", "$ps_ttm", "$pcf_ttm_oper",
        "$ttl_ast", "$ttl_eqy", "$ttl_liab",
    ]

    def __init__(
        self,
        fundamental_fields: Optional[List[str]] = None,
        **kwargs
    ):
        self.fundamental_fields = fundamental_fields or self.DEFAULT_FUNDAMENTAL_FIELDS
        super().__init__(**kwargs)

    def fetch(self, selector, **kwargs):
        """
        获取 Alpha158 features + 财务因子 + Path Target label.

        Returns
        -------
        pd.DataFrame
            特征列: Alpha158 (158列) + 财务因子 (N列)
            标签列: path_target (1列)
        """
        # 获取父类数据 (Alpha158 features + path_target label)
        df = super().fetch(selector, **kwargs)

        # 从 selector 提取时间范围
        if isinstance(selector, (tuple, list)) and len(selector) == 2:
            start_time, end_time = selector[0], selector[1]
        elif isinstance(selector, slice):
            start_time, end_time = selector.start, selector.stop
        else:
            start_time, end_time = self.start_time, self.end_time

        # 获取财务因子数据
        instruments = self.instruments

        from qlib.config import C
        provider_uri = C.provider_uri.get(C.DEFAULT_FREQ, "data/qlib_data")
        instruments_list = _load_instruments(instruments, str(provider_uri))

        fund_data = D.features(
            instruments_list,
            self.fundamental_fields,
            start_time,
            end_time
        )

        # Task 6: 解决特征数量不一致 - 即使数据为空也返回占位列
        fund_cols = [c.replace("$", "") for c in self.fundamental_fields]
        fund_index = pd.MultiIndex.from_product([["feature"], fund_cols])
        
        if fund_data.empty:
            fund_df = pd.DataFrame(index=df.index, columns=fund_index)
        else:
            fund_df = fund_data.swaplevel().sort_index()
            fund_df.index.names = ["datetime", "instrument"]
            fund_df.columns = [c.replace("$", "") for c in fund_df.columns]
            fund_df.columns = pd.MultiIndex.from_product([["feature"], fund_df.columns])
            fund_df = fund_df.reindex(df.index)

        # 确保列名集合一致并合并
        fund_df = fund_df.reindex(columns=fund_index)
        df = pd.concat([df, fund_df], axis=1)
        print(f"DEBUG: FINAL Segment data shape: {df.shape}, Columns: {df.columns.get_level_values(0).value_counts().to_dict()}")
        return df


class Alpha158RankingHandler(Alpha158):
    """
    Alpha158 因子 + 财务因子 Handler (使用 Alpha158 原生 label).

    在 Alpha158 技术因子基础上添加估值和基本面财务因子。
    标签使用 Alpha158 默认的下期收益率。

    Parameters
    ----------
    fundamental_fields : list of str, optional
        要包含的财务因子字段列表，默认包含估值因子和部分基本面因子。

    可用财务因子：
        - 估值因子: $pe_ttm, $pe_lyr, $pb_lyr, $pb_mrq, $ps_ttm, $pcf_ttm_oper
        - 基本面因子: $ttl_ast, $ttl_eqy, $ttl_liab, $fix_ast, $mny_cptl
    """

    DEFAULT_FUNDAMENTAL_FIELDS = [
        "$pe_ttm", "$pb_lyr", "$ps_ttm", "$pcf_ttm_oper",
        "$ttl_ast", "$ttl_eqy", "$ttl_liab",
    ]

    def __init__(
        self,
        fundamental_fields: Optional[List[str]] = None,
        benchmark: str = "SH000852",
        **kwargs
    ):
        self.fundamental_fields = fundamental_fields or self.DEFAULT_FUNDAMENTAL_FIELDS
        self.benchmark = benchmark
        super().__init__(**kwargs)

    def fetch(self, selector, **kwargs):
        """
        获取 Alpha158 features + 财务因子 + Alpha158 原生 label.
        """
        # print(f"DEBUG: FETCH CALLED for {self.__class__.__name__}, selector={selector}, kwargs={kwargs}")
        
        # 获取父类数据 (Alpha158 features + 原生 label)
        df = super().fetch(selector, **kwargs)
        
        # 从 selector 提取时间范围
        if isinstance(selector, (tuple, list)) and len(selector) == 2:
            start_time, end_time = selector[0], selector[1]
        elif isinstance(selector, slice):
            start_time, end_time = selector.start, selector.stop
        else:
            start_time, end_time = self.start_time, self.end_time

        # 获取财务因子数据
        instruments = self.instruments

        from qlib.config import C
        provider_uri = C.provider_uri.get(C.DEFAULT_FREQ, "data/qlib_data")
        instruments_list = _load_instruments(instruments, str(provider_uri))

        fund_data = D.features(
            instruments_list,
            self.fundamental_fields,
            start_time,
            end_time
        )

        # Task 6: 解决特征数量不一致 - 即使数据为空也返回占位列
        fund_cols = [c.replace("$", "") for c in self.fundamental_fields]
        fund_index = pd.MultiIndex.from_product([["feature"], fund_cols])

        if fund_data.empty:
            fund_df = pd.DataFrame(index=df.index, columns=fund_index)
        else:
            fund_df = fund_data.swaplevel().sort_index()
            fund_df.index.names = ["datetime", "instrument"]
            fund_df.columns = [c.replace("$", "") for c in fund_df.columns]
            fund_df.columns = pd.MultiIndex.from_product([["feature"], fund_df.columns])
            fund_df = fund_df.reindex(df.index)

        # 合并并保证列的一致性
        fund_df = fund_df.reindex(columns=fund_index)
        df = pd.concat([df, fund_df], axis=1)
        print(f"DEBUG: FINAL Segment data shape: {df.shape}, Columns: {df.columns.get_level_values(0).value_counts().to_dict()}")
        return df