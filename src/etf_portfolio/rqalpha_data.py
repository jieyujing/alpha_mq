# src/etf_portfolio/rqalpha_data.py
import os
import logging
from typing import Optional, Any
import pandas as pd
from rqalpha.data.base_data_source import BaseDataSource
from rqalpha.data.data_proxy import DataProxy

logger = logging.getLogger(__name__)

class RQAlphaDataSource:
    """RQAlpha 本地数据源实现"""
    def __init__(self, bundle_path: str):
        if not os.path.exists(bundle_path):
            raise FileNotFoundError(f"RQAlpha bundle not found at: {bundle_path}")
        
        # Ensure RQAlpha Environment is initialized (required by BaseDataSource)
        from rqalpha.environment import Environment
        try:
            Environment.get_instance()
        except RuntimeError:
            # Create a minimal environment
            from rqalpha.utils.config import RqAttrDict
            from rqalpha.const import RUN_TYPE
            
            from datetime import datetime
            config = RqAttrDict({
                "base": {
                    "data_bundle_path": bundle_path,
                    "run_type": RUN_TYPE.BACKTEST,
                    "start_date": datetime.strptime("2020-01-01", "%Y-%m-%d"),
                    "end_date": datetime.now()
                },
                "validator": {
                    "cash_return_by_stock_delisted": False
                },
                "mod": {}
            })
            Environment(config, None)

        from rqalpha.data.bar_dict_price_board import BarDictPriceBoard
        self.bundle_path = bundle_path
        # RQAlpha 5.x BaseDataSource requires custom_future_info
        self._data_source = BaseDataSource(bundle_path, custom_future_info={})
        self._data_proxy = DataProxy(self._data_source, BarDictPriceBoard())

    @staticmethod
    def _translate_symbol(symbol: str) -> str:
        if symbol.startswith("SHSE."):
            return symbol.replace("SHSE.", "") + ".XSHG"
        elif symbol.startswith("SZSE."):
            return symbol.replace("SZSE.", "") + ".XSHE"
        return symbol

    def set_token(self, token: str) -> None:
        """RQAlpha local bundle does not require a token."""
        pass

    def fetch_valuation(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        fields: Optional[list[str]] = None,
        **kw
    ) -> pd.DataFrame:
        """Not supported in standard local bundle; returns empty DataFrame."""
        return pd.DataFrame()

    def fetch_basic(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        fields: Optional[list[str]] = None,
        **kw
    ) -> pd.DataFrame:
        """Not supported in standard local bundle; returns empty DataFrame."""
        return pd.DataFrame()

    def fetch_index_constituents(self, index_code: str) -> list[str]:
        """获取指数成分股列表 (RQAlpha 实现，带 AKShare 兜底)"""
        rq_symbol = self._translate_symbol(index_code)
        
        # 1. 尝试从本地 DataProxy 获取 (通常需要特定插件支持)
        try:
            if hasattr(self._data_proxy, "get_index_stocks"):
                stocks = self._data_proxy.get_index_stocks(rq_symbol)
                if stocks:
                    return [self._to_gm_symbol(s) for s in stocks]
        except Exception:
            pass

        # 2. 尝试使用 AKShare 兜底获取成分股 (因为本地 Bundle 可能不含成分股索引)
        try:
            import akshare as ak
            logging.info(f"Fetching constituents for {index_code} via AKShare...")
            # 中证1000: 000852
            code = index_code.split(".")[-1]
            df = ak.index_stock_cons_weight_csindex(symbol=code)
            if not df.empty:
                stocks = df["成分券代码"].tolist()
                # 转换为 GM 格式: SHSE.xxxxxx 或 SZSE.xxxxxx
                results = []
                for s in stocks:
                    if s.startswith("6"):
                        results.append(f"SHSE.{s}")
                    else:
                        results.append(f"SZSE.{s}")
                return results
        except Exception as e:
            logger.warning(f"Failed to fetch constituents via AKShare: {e}")

        return []

    def _to_gm_symbol(self, s: str) -> str:
        """RQAlpha symbol -> GM symbol"""
        if s.endswith(".XSHG"):
            return "SHSE." + s.replace(".XSHG", "")
        elif s.endswith(".XSHE"):
            return "SZSE." + s.replace(".XSHE", "")
        return s

    def fetch_history(
        self,
        symbol: str,
        start_time: str,
        end_time: str,
        frequency: str = "1d",
        fields: Optional[list[str]] = None,
        **kw
    ) -> pd.DataFrame:
        rq_symbol = self._translate_symbol(symbol)
        
        start_dt = pd.Timestamp(start_time)
        end_dt = pd.Timestamp(end_time)
        
        # Calculate a generous bar_count (max days ~ 10000 for 30 years)
        # If 1m, 10000 * 240. For safety we just use a sufficiently large number 
        # based on freq, or rely on rqalpha's history_bars behavior.
        bar_count = 10000 if frequency == "1d" else 10000 * 240
        
        try:
            # history_bars fetches up to `dt`. We'll fetch large count and slice.
            bars = self._data_proxy.history_bars(
                order_book_id=rq_symbol,
                bar_count=bar_count,
                frequency=frequency,
                field=fields,
                dt=end_dt,
                skip_suspended=True,
                include_now=False
            )
            
            if bars is None or len(bars) == 0:
                return pd.DataFrame()
                
            df = pd.DataFrame(bars)
            
            # rqalpha uses 'datetime' field, which is uint64 format (YYYYMMDD000000) or datetime object
            # Convert appropriately if needed. Usually it's integer format in standard rqalpha:
            if pd.api.types.is_numeric_dtype(df['datetime']):
                df['datetime'] = pd.to_datetime(df['datetime'], format='%Y%m%d%H%M%S')
            
            # Filter by start_time
            df = df[df['datetime'] >= start_dt].copy()
            
            # Rename datetime to bob for GM API compatibility
            df = df.rename(columns={
                'datetime': 'bob',
                'total_turnover': 'amount',
                'prev_close': 'pre_close'
            })
            
            # Add symbol column to match GM output if necessary
            df['symbol'] = symbol
            
            return self._clean_tz(df)
            
        except Exception as e:
            logger.warning(f"Failed to fetch history for {symbol} ({rq_symbol}): {e}")
            return pd.DataFrame()

    def _clean_tz(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove timezone info for compatibility with GM API output."""
        if df.empty:
            return df
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                if getattr(df[col].dt, 'tz', None) is not None:
                    df[col] = df[col].dt.tz_localize(None)
        return df
