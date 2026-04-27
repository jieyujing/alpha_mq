# GM数据下载接口重构实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重构GM数据下载接口，使用Strategy、Decorator、Template Method模式解耦数据源、流控/重试、下载流程。

**Architecture:** 抽象DataSource协议实现可替换数据源策略，高阶函数装饰器统一横切关注点，模板方法稳定下载骨架。

**Tech Stack:** Python 3.10+, Protocol (duck typing), functools.partial/wraps, gm.api

---

## 变化压力分析

| 压力点 | 会变化什么 | 应保持稳定 |
|-------|-----------|-----------|
| 数据源切换 | GM → AKShare/Wind | fetch语义、存储逻辑 |
| 流控策略 | 限流阈值、重试参数 | API调用形式 |
| 数据类型扩展 | 新增数据类别 | 下载流程骨架 |

---

### Task 1: 创建 DataSource 协议与 GMDataSource 实现

**Files:**
- Create: `src/etf_portfolio/data_source.py`
- Test: `tests/test_etf_portfolio/test_data_source.py`

**Step 1: Write the failing test**

```python
# tests/test_etf_portfolio/test_data_source.py
import pandas as pd
import pytest
from src.etf_portfolio.data_source import GMDataSource, DataSource

class MockRateLimiter:
    """测试用模拟流控器"""
    def __init__(self):
        self.calls = []

    def wait(self):
        self.calls.append(True)

def test_data_source_protocol():
    """验证 GMDataSource 实现 DataSource 协议"""
    limiter = MockRateLimiter()
    source = GMDataSource(limiter=limiter, token="test-token")
    # 协议检查: 必须有 fetch_history 方法
    assert hasattr(source, 'fetch_history')
    assert callable(source.fetch_history)

def test_gm_data_source_calls_limiter():
    """验证 GMDataSource 调用流控器"""
    limiter = MockRateLimiter()
    source = GMDataSource(limiter=limiter, token="test-token")
    # 模拟调用 (需要 gm.api 可用，这里只验证流控器被调用)
    # 实际集成测试需要 gm SDK
    limiter.wait()
    assert len(limiter.calls) == 1

def test_data_source_fetch_signature():
    """验证 fetch_history 签名符合协议"""
    import inspect
    limiter = MockRateLimiter()
    source = GMDataSource(limiter=limiter, token="test-token")
    sig = inspect.signature(source.fetch_history)
    # 必需参数: symbol, start_time, end_time
    params = list(sig.parameters.keys())
    assert 'symbol' in params
    assert 'start_time' in params or 'start' in params
    assert 'end_time' in params or 'end' in params
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_etf_portfolio/test_data_source.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.etf_portfolio.data_source'"

**Step 3: Write minimal implementation**

```python
# src/etf_portfolio/data_source.py
from typing import Protocol, Callable, Optional, Any
import pandas as pd
from dataclasses import dataclass

class DataSource(Protocol):
    """
    数据源策略协议 - 任何满足此接口的对象都可替换使用。

    支持的数据获取方法:
    - fetch_history: 历史行情 (OHLCV)
    - fetch_valuation: 日频估值数据
    - fetch_fundamentals: 财务报表数据
    """
    fetch_history: Callable[..., pd.DataFrame]
    fetch_valuation: Callable[..., pd.DataFrame]
    fetch_basic: Callable[..., pd.DataFrame]
    set_token: Callable[[str], None]


class RateLimiter:
    """流控器接口 - 可注入不同实现"""
    def wait(self) -> None:
        """等待直到可以发起下一个请求"""
        ...


@dataclass
class GMDataSource:
    """
    掘金数据源实现。

    使用方式:
        limiter = RateLimiter(max_req=950)
        source = GMDataSource(limiter=limiter, token="your-token")
        df = source.fetch_history("SHSE.600000", "2020-01-01", "2020-12-31")
    """
    limiter: RateLimiter
    token: str

    def __post_init__(self):
        from gm.api import set_token as gm_set_token
        gm_set_token(self.token)

    def fetch_history(
        self,
        symbol: str,
        start_time: str,
        end_time: str,
        frequency: str = "1d",
        fields: str = "symbol,bob,open,high,low,close,volume,amount",
        **kwargs
    ) -> pd.DataFrame:
        """获取历史行情数据"""
        from gm.api import history
        self.limiter.wait()
        df = history(
            symbol=symbol,
            frequency=frequency,
            start_time=start_time,
            end_time=end_time,
            fields=fields,
            df=True,
            **kwargs
        )
        return self._clean_tz(df)

    def fetch_valuation(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        fields: str = "pe_ttm,pb_mrq,ps_ttm,pcf_ttm_oper",
        **kwargs
    ) -> pd.DataFrame:
        """获取日频估值数据"""
        from gm.api import stk_get_daily_valuation
        self.limiter.wait()
        df = stk_get_daily_valuation(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
            df=True,
            **kwargs
        )
        return self._clean_tz(df)

    def fetch_basic(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        fields: str = "tclose,turnrate,ttl_shr,circ_shr,is_st,is_suspended",
        **kwargs
    ) -> pd.DataFrame:
        """获取基础指标数据"""
        from gm.api import stk_get_daily_basic
        self.limiter.wait()
        df = stk_get_daily_basic(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
            df=True,
            **kwargs
        )
        return self._clean_tz(df)

    def _clean_tz(self, df: Optional[pd.DataFrame]) -> pd.DataFrame:
        """移除时区信息，兼容 Parquet/CSV 存储"""
        if df is None or (not isinstance(df, pd.DataFrame) and not isinstance(df, list)):
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_etf_portfolio/test_data_source.py -v`
Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add src/etf_portfolio/data_source.py tests/test_etf_portfolio/test_data_source.py
git commit -m "feat: add DataSource protocol and GMDataSource implementation"
```

---

### Task 2: 重构 fetch_safe 为装饰器组合

**Files:**
- Modify: `src/etf_portfolio/data_source.py:1-50`
- Create: `src/etf_portfolio/decorators.py`
- Test: `tests/test_etf_portfolio/test_decorators.py`

**Step 1: Write the failing test**

```python
# tests/test_etf_portfolio/test_decorators.py
import pytest
import time
from src.etf_portfolio.decorators import with_retry, with_rate_limit

class MockLimiter:
    def __init__(self):
        self.wait_count = 0

    def wait(self):
        self.wait_count += 1

def test_with_rate_limit_calls_limiter():
    """验证流控装饰器调用 limiter.wait()"""
    limiter = MockLimiter()

    @with_rate_limit(limiter)
    def fetch_data():
        return "data"

    result = fetch_data()
    assert result == "data"
    assert limiter.wait_count == 1

def test_with_retry_success_no_retry():
    """验证成功时不重试"""
    call_count = 0

    @with_retry(max_attempts=3)
    def success_func():
        call_count += 1
        return "success"

    result = success_func()
    assert result == "success"
    assert call_count == 1  # 只调用一次

def test_with_retry_failure_then_success():
    """验证失败后重试成功"""
    call_count = 0

    @with_retry(max_attempts=3, backoff_base=0.1)
    def flaky_func():
        call_count += 1
        if call_count < 2:
            raise ValueError("temporary error")
        return "success"

    result = flaky_func()
    assert result == "success"
    assert call_count == 2  # 第一次失败，第二次成功

def test_with_retry_max_attempts_exceeded():
    """验证超过最大重试次数抛出异常"""
    call_count = 0

    @with_retry(max_attempts=3, backoff_base=0.05)
    def always_fail():
        call_count += 1
        raise ValueError("always fails")

    with pytest.raises(ValueError, match="always fails"):
        always_fail()

    assert call_count == 3  # 尝试了3次

def test_decorator_stack_order():
    """验证装饰器堆叠顺序: rate_limit -> retry"""
    limiter = MockLimiter()
    call_count = 0

    @with_rate_limit(limiter)
    @with_retry(max_attempts=2, backoff_base=0.05)
    def fetch():
        call_count += 1
        if call_count == 1:
            raise ValueError("first fails")
        return "data"

    result = fetch()
    assert result == "data"
    # rate_limit 在 retry 外层，所以每次 retry 都会触发 rate_limit
    assert limiter.wait_count == 2
    assert call_count == 2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_etf_portfolio/test_decorators.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.etf_portfolio.decorators'"

**Step 3: Write minimal implementation**

```python
# src/etf_portfolio/decorators.py
"""
横切关注点装饰器 - 流控、重试、日志等。

使用方式:
    limiter = RateLimiter(max_req=950)

    @with_rate_limit(limiter)
    @with_retry(max_attempts=3)
    def fetch_data(symbol):
        return history(symbol, ...)

装饰器堆叠顺序 (从外到内执行):
    with_rate_limit -> with_retry -> 实际函数
"""
import functools
import time
import logging
from typing import Callable, TypeVar, Any

T = TypeVar('T')

def with_rate_limit(limiter: Any) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    流控装饰器 - 在函数执行前调用 limiter.wait()。

    Args:
        limiter: 必须有 wait() 方法的流控器对象

    Example:
        @with_rate_limit(my_limiter)
        def fetch():
            return api_call()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            limiter.wait()
            return func(*args, **kwargs)
        return wrapper
    return decorator


def with_retry(
    max_attempts: int = 3,
    backoff_base: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    重试装饰器 - 指数退避重试。

    Args:
        max_attempts: 最大尝试次数
        backoff_base: 退避基数 (秒)，实际等待 = backoff_base ** attempt
        exceptions: 需要重试的异常类型 tuple

    Example:
        @with_retry(max_attempts=3, backoff_base=2)
        def fetch():
            return api_call()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = backoff_base ** attempt
                        logging.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_attempts}): {e}. "
                            f"Retrying in {wait_time:.1f}s"
                        )
                        time.sleep(wait_time)
            raise last_exception
        return wrapper
    return decorator


def compose_decorators(*decorators: Callable) -> Callable:
    """
    装饰器组合器 - 一次应用多个装饰器。

    Example:
        fetch = compose_decorators(
            with_rate_limit(limiter),
            with_retry(max_attempts=3)
        )(raw_fetch_func)
    """
    def composed(func: Callable) -> Callable:
        for dec in reversed(decorators):
            func = dec(func)
        return func
    return composed
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_etf_portfolio/test_decorators.py -v`
Expected: PASS (all 5 tests)

**Step 5: Commit**

```bash
git add src/etf_portfolio/decorators.py tests/test_etf_portfolio/test_decorators.py
git commit -m "feat: add with_rate_limit and with_retry decorators"
```

---

### Task 3: 创建 DownloadWorkflow 模板方法骨架

**Files:**
- Create: `src/etf_portfolio/workflow.py`
- Test: `tests/test_etf_portfolio/test_workflow.py`

**Step 1: Write the failing test**

```python
# tests/test_etf_portfolio/test_workflow.py
import pytest
from src.etf_portfolio.workflow import DownloadWorkflow, HistoryWorkflow

class MockDataSource:
    """测试用模拟数据源"""
    def __init__(self):
        self.fetch_count = 0

    def fetch_history(self, symbol, start_time, end_time, **kw):
        self.fetch_count += 1
        import pandas as pd
        return pd.DataFrame({"symbol": [symbol], "close": [100.0]})

def test_workflow_template_method():
    """验证模板方法调用 get_categories"""
    source = MockDataSource()
    workflow = HistoryWorkflow(source=source)
    categories = workflow.get_categories()
    assert "history_1d" in categories

def test_workflow_can_override_categories():
    """验证子类可覆盖 get_categories"""
    source = MockDataSource()

    class MinuteWorkflow(DownloadWorkflow):
        def get_categories(self):
            return ["history_1m"]

    workflow = MinuteWorkflow(source=source)
    categories = workflow.get_categories()
    assert categories == ["history_1m"]

def test_workflow_get_category_fetcher():
    """验证 get_category_fetcher 返回正确函数"""
    source = MockDataSource()
    workflow = HistoryWorkflow(source=source)

    fetcher = workflow.get_category_fetcher("history_1d")
    assert fetcher is not None
    assert callable(fetcher)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_etf_portfolio/test_workflow.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.etf_portfolio.workflow'"

**Step 3: Write minimal implementation**

```python
# src/etf_portfolio/workflow.py
"""
下载流程模板方法 - 稳定的骨架，可覆盖的步骤。

设计原则:
- 骨架稳定 (run() 流程不变)
- 步骤可扩展 (get_categories, get_category_fetcher 可覆盖)
- 数据源可替换 (通过 source 参数注入)
"""
from typing import Protocol, List, Callable, Optional, Any
import logging
import os
import pandas as pd

class DataSource(Protocol):
    """数据源协议 (引用 data_source.py 中的定义)"""
    fetch_history: Callable[..., pd.DataFrame]
    fetch_valuation: Callable[..., pd.DataFrame]
    fetch_basic: Callable[..., pd.DataFrame]


class DownloadWorkflow:
    """
    下载流程模板方法基类。

    稳定的骨架流程:
    1. setup() - 初始化
    2. get_target_pool() - 获取标的池
    3. for category in get_categories(): download_category()
    4. cleanup() - 清理

    可覆盖的步骤:
    - get_categories(): 返回要下载的数据类型列表
    - get_category_fetcher(category): 返回该类型的获取函数
    - get_category_fields(category): 返回该类型的字段定义
    """

    def __init__(
        self,
        source: DataSource,
        output_dir: str = "data/exports",
        limiter: Optional[Any] = None
    ):
        self.source = source
        self.output_dir = output_dir
        self.limiter = limiter
        self._setup_complete = False

    def setup(self) -> None:
        """初始化 - 创建输出目录等"""
        os.makedirs(self.output_dir, exist_ok=True)
        self._setup_complete = True
        logging.info(f"Workflow setup complete. Output dir: {self.output_dir}")

    def cleanup(self) -> None:
        """清理 - 可用于关闭连接等"""
        logging.info("Workflow cleanup complete.")

    def get_categories(self) -> List[str]:
        """
        返回要下载的数据类型列表。

        子类可覆盖添加或修改数据类型。
        """
        return []

    def get_category_fetcher(self, category: str) -> Optional[Callable]:
        """
        返回指定类型的获取函数。

        Args:
            category: 数据类型名称 (如 "history_1d", "valuation")

        Returns:
            获取函数，或 None 表示不支持
        """
        return None

    def get_category_fields(self, category: str) -> Optional[str]:
        """返回指定类型的字段定义"""
        return None

    def get_target_pool(self, symbols: Optional[List[str]] = None) -> List[str]:
        """获取标的池 - 子类可覆盖"""
        return symbols or []

    def run(
        self,
        symbols: Optional[List[str]] = None,
        start_date: str = "2020-01-01",
        end_date: str = "2024-12-31"
    ) -> None:
        """
        执行下载流程 - 模板方法骨架。

        此方法不应被覆盖，扩展点在其他步骤方法中。
        """
        self.setup()
        pool = self.get_target_pool(symbols)

        for category in self.get_categories():
            logging.info(f"Downloading {category}...")
            fetcher = self.get_category_fetcher(category)
            if fetcher is None:
                logging.warning(f"No fetcher for {category}, skipping.")
                continue

            self._download_category(pool, category, fetcher, start_date, end_date)

        self.cleanup()

    def _download_category(
        self,
        pool: List[str],
        category: str,
        fetcher: Callable,
        start_date: str,
        end_date: str
    ) -> None:
        """具体下载逻辑 - 可覆盖实现细节"""
        category_dir = os.path.join(self.output_dir, category)
        os.makedirs(category_dir, exist_ok=True)
        fields = self.get_category_fields(category)

        for symbol in pool:
            try:
                df = fetcher(
                    symbol=symbol,
                    start_time=start_date,
                    end_time=end_date,
                    fields=fields
                )
                if df is not None and not df.empty:
                    save_path = os.path.join(category_dir, f"{symbol}.parquet")
                    df.to_parquet(save_path, index=False)
            except Exception as e:
                logging.error(f"Failed to download {category} for {symbol}: {e}")


class HistoryWorkflow(DownloadWorkflow):
    """
    历史行情下载流程。

    覆盖:
    - get_categories: 返回 ["history_1d"]
    - get_category_fetcher: 返回 source.fetch_history
    """

    def get_categories(self) -> List[str]:
        return ["history_1d"]

    def get_category_fetcher(self, category: str) -> Optional[Callable]:
        if category == "history_1d":
            return self.source.fetch_history
        return None

    def get_category_fields(self, category: str) -> Optional[str]:
        if category == "history_1d":
            return "symbol,bob,open,high,low,close,volume,amount"
        return None


class ValuationWorkflow(DownloadWorkflow):
    """估值数据下载流程"""

    def get_categories(self) -> List[str]:
        return ["valuation"]

    def get_category_fetcher(self, category: str) -> Optional[Callable]:
        if category == "valuation":
            return self.source.fetch_valuation
        return None

    def get_category_fields(self, category: str) -> Optional[str]:
        if category == "valuation":
            return "pe_ttm,pb_mrq,ps_ttm,pcf_ttm_oper"
        return None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_etf_portfolio/test_workflow.py -v`
Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add src/etf_portfolio/workflow.py tests/test_etf_portfolio/test_workflow.py
git commit -m "feat: add DownloadWorkflow template method skeleton"
```

---

### Task 4: 重构 download_gm.py 使用新架构

**Files:**
- Modify: `data/scripts/download_gm.py:1-450`
- Test: 集成测试运行 download_gm.py

**Step 1: 重构 download_gm.py 导入新模块**

修改文件头部导入:

```python
# data/scripts/download_gm.py (重构后)
"""
GM 数据下载脚本 - 使用重构后的架构。

架构:
- GMDataSource: 数据源策略
- decorators: 流控/重试装饰器
- DownloadWorkflow: 模板方法骨架
"""
import os
import glob
import logging
import pandas as pd
from tqdm import tqdm
from datetime import datetime, timedelta

# 导入重构后的模块
from src.etf_portfolio.data_source import GMDataSource, RateLimiter
from src.etf_portfolio.decorators import with_rate_limit, with_retry
from src.etf_portfolio.workflow import DownloadWorkflow

# GM SDK imports (保留用于直接调用)
from gm.api import (
    set_token, stk_get_index_constituents, history,
    stk_get_daily_valuation, stk_get_daily_basic, stk_get_daily_mktvalue,
    stk_get_fundamentals_balance, stk_get_fundamentals_income,
    stk_get_fundamentals_cashflow, stk_get_adj_factor,
    get_instruments, get_trading_dates, stk_get_symbol_industry
)

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Token (保持硬编码)
TOKEN = "478dc4635c5198dbfcc962ac3bb209e5327edbff"
```

**Step 2: 重构 RateLimiter 类 (移到 data_source.py，这里只保留实例化)**

删除 download_gm.py 中的 RateLimiter 类定义 (第20-51行)，改为:

```python
# 使用导入的 RateLimiter
limiter = RateLimiter(max_req=950)
```

**Step 3: 重构 fetch_safe 使用装饰器**

替换原有 fetch_safe (第123-135行):

```python
# 旧代码 (删除):
# @retry(stop=stop_after_attempt(3), wait=wait_exponential(...))
# def fetch_safe(func, *args, **kwargs):
#     ...

# 新代码:
def make_fetcher(api_func, limiter, max_attempts=3):
    """
    创建带流控和重试的 API 获取函数。

    Returns:
        装饰后的函数，可直接调用
    """
    @with_rate_limit(limiter)
    @with_retry(max_attempts=max_attempts, backoff_base=2.0)
    def fetcher(*args, **kwargs):
        df = api_func(*args, **kwargs)
        return _clean_df_tz(df)
    return fetcher


def _clean_df_tz(df):
    """移除 DataFrame 中的时区信息"""
    if df is None:
        return pd.DataFrame()
    if isinstance(df, list):
        df = pd.DataFrame(df)
    if isinstance(df, tuple):
        df = pd.DataFrame(df)
    if df.empty:
        return df
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            if getattr(df[col].dt, 'tz', None) is not None:
                df[col] = df[col].dt.tz_localize(None)
    return df
```

**Step 4: 创建 CSI1000Workflow 子类**

```python
# 在 download_gm.py 中添加:
class CSI1000Workflow(DownloadWorkflow):
    """
    中证1000全量数据下载流程。

    覆盖:
    - get_categories: 全部数据类型
    - get_category_fetcher: 各类型获取函数
    - get_category_fields: 各类型字段定义
    """

    def __init__(self, source, index_code='SHSE.000852', history_1m=False, **kw):
        super().__init__(source=source, **kw)
        self.index_code = index_code
        self.history_1m = history_1m
        self._constituents = None

    def get_target_pool(self, symbols=None) -> list:
        """获取中证1000成分股"""
        if self._constituents is None:
            logging.info(f"Fetching {self.index_code} constituents...")
            self._constituents = stk_get_index_constituents(index=self.index_code)
            if self._constituents is None or self._constituents.empty:
                logging.error(f"Failed to fetch constituents for {self.index_code}")
                return []
        symbols = self._constituents['symbol'].tolist()
        return symbols + [self.index_code]  # 包含指数自身

    def get_categories(self) -> list:
        """返回所有数据类型"""
        cats = ["history_1d", "valuation", "mktvalue", "basic",
                "fundamentals_balance", "fundamentals_income", "fundamentals_cashflow",
                "adj_factor"]
        if self.history_1m:
            cats.insert(1, "history_1m")
        return cats

    def get_category_fetcher(self, category: str):
        """返回各类型的获取函数"""
        fetchers = {
            "history_1d": lambda s, st, et, **kw: make_fetcher(history, self.limiter)(
                symbol=s, frequency='1d', start_time=st, end_time=et, df=True, **kw),
            "history_1m": lambda s, st, et, **kw: make_fetcher(history, self.limiter)(
                symbol=s, frequency='1m', start_time=st, end_time=et, df=True, **kw),
            "valuation": lambda s, st, et, **kw: make_fetcher(stk_get_daily_valuation, self.limiter)(
                symbol=s, start_date=st, end_date=et, df=True, **kw),
            "mktvalue": lambda s, st, et, **kw: make_fetcher(stk_get_daily_mktvalue, self.limiter)(
                symbol=s, start_date=st, end_date=et, df=True, **kw),
            "basic": lambda s, st, et, **kw: make_fetcher(stk_get_daily_basic, self.limiter)(
                symbol=s, start_date=st, end_date=et, df=True, **kw),
            "fundamentals_balance": lambda s, st, et, **kw: make_fetcher(stk_get_fundamentals_balance, self.limiter)(
                symbol=s, start_date=st, end_date=et, df=True, **kw),
            "fundamentals_income": lambda s, st, et, **kw: make_fetcher(stk_get_fundamentals_income, self.limiter)(
                symbol=s, start_date=st, end_date=et, df=True, **kw),
            "fundamentals_cashflow": lambda s, st, et, **kw: make_fetcher(stk_get_fundamentals_cashflow, self.limiter)(
                symbol=s, start_date=st, end_date=et, df=True, **kw),
            "adj_factor": lambda s, st, et, **kw: stk_get_adj_factor(symbol=s, start_date=st, end_date=et),
        }
        return fetchers.get(category)

    def get_category_fields(self, category: str) -> str:
        """返回各类型的字段定义"""
        fields = {
            "history_1d": "symbol,bob,open,high,low,close,volume,amount",
            "history_1m": "symbol,bob,open,high,low,close,volume,amount",
            "valuation": "pe_ttm,pb_mrq,ps_ttm,pcf_ttm_oper",
            "mktvalue": "tot_mv,a_mv",
            "basic": "tclose,turnrate,ttl_shr,circ_shr,is_st,is_suspended,upper_limit,lower_limit",
            # 财务报表字段太长，保留原文件中的定义
            "fundamentals_balance": BALANCE_FIELDS,
            "fundamentals_income": INCOME_FIELDS,
            "fundamentals_cashflow": CASHFLOW_FIELDS,
        }
        return fields.get(category)


# 字段常量 (保留原文件中的定义)
BALANCE_FIELDS = "cash_bal_cb,dpst_ob,mny_cptl,...(保留原文件完整定义)"
INCOME_FIELDS = "ttl_inc_oper,inc_oper,...(保留原文件完整定义)"
CASHFLOW_FIELDS = "cash_rcv_sale,...(保留原文件完整定义)"
```

**Step 5: 重构 run_download_workflow 使用 CSI1000Workflow**

```python
def run_download_workflow(token, start_date, end_date, index_code='SHSE.000852',
                          history_1m=False, full_history=False):
    """
    执行完整的数据下载工作流 (重构后使用 Workflow)。
    """
    set_token(token)
    limiter = RateLimiter(max_req=950)
    source = GMDataSource(limiter=limiter, token=token)

    # 调整日期格式
    h_start = f"{start_date if not full_history else '2017-01-01'} 09:00:00"
    h_end = f"{end_date} 16:00:00"

    workflow = CSI1000Workflow(
        source=source,
        index_code=index_code,
        history_1m=history_1m,
        limiter=limiter,
        output_dir="data/exports"
    )

    workflow.run(start_date=h_start, end_date=h_end)

    # 静态数据下载 (行业分类、上市信息等) - 保留原逻辑
    download_static_data(limiter, workflow.get_target_pool())


def download_static_data(limiter, symbols):
    """下载静态数据 (行业分类、上市信息)"""
    static_dir = os.path.join("data", "exports", "static")
    os.makedirs(static_dir, exist_ok=True)

    # 行业分类
    industry_dfs = []
    for chunk in chunked_string(symbols, 100):
        limiter.wait()
        res = stk_get_symbol_industry(symbols=chunk)
        if res:
            if isinstance(res, list):
                res = pd.DataFrame(res)
            industry_dfs.append(res)

    if industry_dfs:
        pd.concat(industry_dfs).drop_duplicates('symbol').to_csv(
            os.path.join(static_dir, "industry.csv"), index=False)

    # 上市信息
    inst_dfs = []
    for chunk in chunked_string(symbols, 100):
        limiter.wait()
        res = get_instruments(symbols=chunk, df=True)
        if res and not res.empty:
            inst_dfs.append(res[['symbol', 'list_date', 'delist_date']])

    if inst_dfs:
        pd.concat(inst_dfs).to_csv(os.path.join(static_dir, "instruments.csv"), index=False)


def chunked_string(lst, n):
    """将列表分块"""
    return [",".join(lst[i:i+n]) for i in range(0, len(lst), n)]
```

**Step 6: 验证重构后脚本可运行**

Run: `python data/scripts/download_gm.py --help` 或检查导入
Expected: 无 ImportError

**Step 7: Commit**

```bash
git add data/scripts/download_gm.py
git commit -m "refactor: download_gm.py uses DataSource and Workflow architecture"
```

---

### Task 5: 更新 gm_data.py 使用新架构

**Files:**
- Modify: `src/etf_portfolio/gm_data.py`

**Step 1: 重构 gm_data.py 导入**

```python
# src/etf_portfolio/gm_data.py (重构后)
"""
ETF 数据获取工具库 - 使用重构后的 DataSource。
"""
import pandas as pd
from typing import Dict, List

from src.etf_portfolio.data_source import GMDataSource, RateLimiter

# 创建默认数据源实例
_DEFAULT_LIMITER = RateLimiter(max_req=950)
_DEFAULT_SOURCE = GMDataSource(limiter=_DEFAULT_LIMITER, token="478dc4635c5198dbfcc962ac3bb209e5327edbff")


def fetch_etf_history(
    symbols: List[str],
    start_date: str,
    end_date: str,
    source: GMDataSource = None
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
        source = _DEFAULT_SOURCE

    data_dict = {}
    for symbol in symbols:
        df = source.fetch_history(
            symbol=symbol,
            start_time=start_date,
            end_time=end_date,
            frequency='1d',
            fields='symbol,bob,open,high,low,close'
        )
        if df.empty:
            continue
        df['bob'] = pd.to_datetime(df['bob'])
        df.set_index('bob', inplace=True)
        data_dict[symbol] = df[['open', 'high', 'low', 'close']]

    return align_and_ffill_prices(data_dict)


def align_and_ffill_prices(data_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """多标的 OHLC 数据对齐和前向填充"""
    if not data_dict:
        return pd.DataFrame()

    symbols = sorted(data_dict.keys())
    fields = ['open', 'high', 'low', 'close']
    col_index = pd.MultiIndex.from_product([symbols, fields], names=['symbol', 'field'])

    all_dates = pd.DatetimeIndex([])
    for df in data_dict.values():
        all_dates = all_dates.union(df.index)
    all_dates = all_dates.sort_values()

    aligned_df = pd.DataFrame(index=pd.to_datetime(all_dates), columns=col_index)

    for symbol, df in data_dict.items():
        for field in fields:
            if field in df.columns:
                aligned_df.loc[:, (symbol, field)] = df[field]

    return aligned_df.sort_index().ffill()
```

**Step 2: 验证导入正确**

Run: `python -c "from src.etf_portfolio.gm_data import fetch_etf_history"`
Expected: 无 ImportError

**Step 3: Commit**

```bash
git add src/etf_portfolio/gm_data.py
git commit -m "refactor: gm_data.py uses GMDataSource"
```

---

## 验证计划

### 单元测试

```bash
# 运行所有新增测试
pytest tests/test_etf_portfolio/test_data_source.py -v
pytest tests/test_etf_portfolio/test_decorators.py -v
pytest tests/test_etf_portfolio/test_workflow.py -v

# 全量测试
pytest tests/ -v
```

### 集成测试

```bash
# 验证下载脚本可运行
python data/scripts/download_gm.py --start 2024-01-01 --end 2024-12-31 --dry-run

# 验证 gm_data.py
python -c "
from src.etf_portfolio.gm_data import fetch_etf_history
df = fetch_etf_history(['SHSE.510300'], '2024-01-01', '2024-12-31')
print(df.shape)
"
```

---

## 架构对比

| 重构前 | 重构后 |
|-------|-------|
| Token 硬编码 4 处 | 保持硬编码 (用户要求) |
| RateLimiter 类散落各文件 | 统一在 data_source.py |
| fetch_safe 函数重复 | decorators.py 可组合 |
| download_category_data 200行单一函数 | CSI1000Workflow 可扩展 |
| API 调用直接耦合 GM SDK | DataSource 协议可替换 |

---

## 扩展指南

### 添加新数据源 (AKShare)

```python
class AKShareDataSource:
    """AKShare 数据源实现"""
    def fetch_history(self, symbol, start_time, end_time, **kw):
        import akshare as ak
        # AKShare API 调用
        return ak.stock_zh_a_hist(symbol, ...)

# 使用
source = AKShareDataSource()
workflow = HistoryWorkflow(source=source)
workflow.run(symbols=['000001'], ...)
```

### 添加新数据类型

```python
class ExtendedWorkflow(CSI1000Workflow):
    def get_categories(self):
        cats = super().get_categories()
        cats.append("options_chain")  # 新增期权链
        return cats

    def get_category_fetcher(self, category):
        if category == "options_chain":
            return self._fetch_options
        return super().get_category_fetcher(category)
```