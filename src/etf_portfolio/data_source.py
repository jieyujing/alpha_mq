# src/etf_portfolio/data_source.py
"""数据源协议与实现"""
from typing import Protocol, Callable, Optional, Any
import pandas as pd
from dataclasses import dataclass


class DataSource(Protocol):
    """数据源策略协议"""
    fetch_history: Callable[..., pd.DataFrame]
    fetch_valuation: Callable[..., pd.DataFrame]
    fetch_basic: Callable[..., pd.DataFrame]
    set_token: Callable[[str], None]


class RateLimiter:
    """流控器接口"""
    def __init__(self, max_req: int = 950, window: int = 300):
        self.max_req = max_req
        self.window = window
        self.history: list[float] = []
        self.min_interval = 0.35

    def wait(self) -> None:
        import time
        now = time.time()
        # 清理过期记录
        while self.history and now - self.history[0] > self.window:
            self.history.pop(0)
        # 如果达到限制，等待
        if len(self.history) >= self.max_req:
            sleep_time = self.window - (now - self.history[0]) + 0.1
            time.sleep(sleep_time)
        # 确保最小间隔
        now = time.time()
        if self.history and now - self.history[-1] < self.min_interval:
            import random
            jitter = random.uniform(0.05, 0.15)
            wait_time = self.min_interval - (now - self.history[-1]) + jitter
            time.sleep(max(0, wait_time))
        self.history.append(time.time())


@dataclass
class GMDataSource:
    """掘金数据源实现"""
    limiter: RateLimiter
    token: str

    def __post_init__(self):
        self.set_token(self.token)

    def set_token(self, token: str) -> None:
        """设置GM API token"""
        from gm.api import set_token as gm_set_token
        gm_set_token(token)

    def fetch_history(
        self,
        symbol: str,
        start_time: str,
        end_time: str,
        frequency: str = "1d",
        fields: Optional[list[str]] = None,
        **kw
    ) -> pd.DataFrame:
        from gm.api import history
        self.limiter.wait()
        df = history(
            symbol=symbol,
            frequency=frequency,
            start_time=start_time,
            end_time=end_time,
            df=True,
            **kw
        )
        return self._clean_tz(df)

    def fetch_valuation(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        fields: Optional[list[str]] = None,
        **kw
    ) -> pd.DataFrame:
        from gm.api import stk_get_daily_valuation
        self.limiter.wait()
        df = stk_get_daily_valuation(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            df=True,
            **kw
        )
        return self._clean_tz(df)

    def fetch_basic(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        fields: Optional[list[str]] = None,
        **kw
    ) -> pd.DataFrame:
        from gm.api import stk_get_daily_basic
        self.limiter.wait()
        df = stk_get_daily_basic(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            df=True,
            **kw
        )
        return self._clean_tz(df)

    def _clean_tz(self, df: Any) -> pd.DataFrame:
        """清理时区信息，确保兼容性"""
        if df is None or not isinstance(df, pd.DataFrame) and not isinstance(df, list):
            return pd.DataFrame()
        if isinstance(df, list):
            df = pd.DataFrame(df)
        if df.empty:
            return df
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                if getattr(df[col].dt, 'tz', None) is not None:
                    df[col] = df[col].dt.tz_localize(None)
        return df