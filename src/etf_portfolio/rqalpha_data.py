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
        
        self.bundle_path = bundle_path
        self._data_source = BaseDataSource(bundle_path)
        self._data_proxy = DataProxy(self._data_source)

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
                fields=fields,
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
