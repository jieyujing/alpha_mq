# src/etf_portfolio/gm_data.py
"""
ETF 数据获取工具库 - 使用重构后的 DataSource。
"""
import pandas as pd
from typing import Dict, List, Optional

from src.etf_portfolio.data_source import GMDataSource, RateLimiter

# Token (保持硬编码)
TOKEN = "478dc4635c5198dbfcc962ac3bb209e5327edbff"

# 创建默认数据源实例 (延迟初始化)
_DEFAULT_SOURCE: Optional[GMDataSource] = None


def _get_default_source() -> GMDataSource:
    """获取默认数据源实例 (延迟初始化)"""
    global _DEFAULT_SOURCE
    if _DEFAULT_SOURCE is None:
        limiter = RateLimiter(max_req=950)
        _DEFAULT_SOURCE = GMDataSource(limiter=limiter, token=TOKEN)
    return _DEFAULT_SOURCE


def fetch_etf_history(
    symbols: List[str],
    start_date: str,
    end_date: str,
    source: Optional[GMDataSource] = None
) -> pd.DataFrame:
    """
    获取 ETF 历史数据并返回 MultiIndex DataFrame。

    Args:
        symbols: ETF 代码列表
        start_date: 起始日期
        end_date: 结束日期
        source: 数据源 (可选，默认使用全局实例)

    Returns:
        MultiIndex DataFrame (symbol, field) -> open/high/low/close
    """
    if source is None:
        source = _get_default_source()

    data_dict = {}
    fields = 'symbol,bob,open,high,low,close'

    for symbol in symbols:
        df = source.fetch_history(
            symbol=symbol,
            start_time=start_date,
            end_time=end_date,
            frequency='1d',
            fields=fields
        )
        if df is None or df.empty:
            continue
        df['bob'] = pd.to_datetime(df['bob'])
        df.set_index('bob', inplace=True)
        data_dict[symbol] = df[['open', 'high', 'low', 'close']]

    return align_and_ffill_prices(data_dict)


def align_and_ffill_prices(data_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    对齐多个 DataFrame (OHLC) 并使用 MultiIndex 填充缺失值。

    Args:
        data_dict: 字典，key 为 symbol，value 为 OHLC DataFrame

    Returns:
        MultiIndex DataFrame，列索引为 (symbol, field)
    """
    if not data_dict:
        return pd.DataFrame()

    # 创建 MultiIndex 列索引
    symbols = sorted(data_dict.keys())
    fields = ['open', 'high', 'low', 'close']
    col_index = pd.MultiIndex.from_product([symbols, fields], names=['symbol', 'field'])

    # 获取所有唯一日期
    all_dates = pd.DatetimeIndex([])
    for df in data_dict.values():
        all_dates = all_dates.union(df.index)
    all_dates = all_dates.sort_values()

    # 创建空的 MultiIndex DataFrame
    aligned_df = pd.DataFrame(index=pd.to_datetime(all_dates), columns=col_index)

    for symbol, df in data_dict.items():
        for field in fields:
            if field in df.columns:
                aligned_df.loc[:, (symbol, field)] = df[field]

    # 前向填充缺失值
    aligned_df = aligned_df.sort_index().ffill()

    return aligned_df