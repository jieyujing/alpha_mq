# RQAlpha DataSource Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `RQAlphaDataSource` adapter to support offline research using RQAlpha's local bundle data, conforming to the existing `DataSource` protocol.

**Architecture:** Use the Adapter Pattern to map the existing `DataSource` protocol (`fetch_history`, `fetch_valuation`, `fetch_basic`, `set_token`) to RQAlpha's `LocalDataSource` and `DataProxy`.

**Tech Stack:** Python 3, `pandas`, `rqalpha`

---

### Task 1: Create RQAlphaDataSource and Symbol Translation

**Files:**
- Create: `src/etf_portfolio/rqalpha_data.py`
- Create: `tests/test_etf_portfolio/test_rqalpha_data.py`

- [ ] **Step 1: Write the failing test for symbol translation**

```python
# tests/test_etf_portfolio/test_rqalpha_data.py
import pytest
from src.etf_portfolio.rqalpha_data import RQAlphaDataSource

def test_symbol_translation():
    # Use a dummy path; we will mock validation later or bypass it for static methods
    assert RQAlphaDataSource._translate_symbol("SHSE.600000") == "600000.XSHG"
    assert RQAlphaDataSource._translate_symbol("SZSE.000001") == "000001.XSHE"
    
    # Unmatched should just return the original or handled gracefully
    assert RQAlphaDataSource._translate_symbol("UNKNOWN.123") == "UNKNOWN.123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_etf_portfolio/test_rqalpha_data.py::test_symbol_translation -v`
Expected: FAIL with ModuleNotFoundError or ImportError

- [ ] **Step 3: Write minimal implementation**

```python
# src/etf_portfolio/rqalpha_data.py
import os
import logging
from typing import Optional, Any
import pandas as pd
from rqalpha.data.local_data_source import LocalDataSource
from rqalpha.data.data_proxy import DataProxy

logger = logging.getLogger(__name__)

class RQAlphaDataSource:
    def __init__(self, bundle_path: str):
        if not os.path.exists(bundle_path):
            raise FileNotFoundError(f"RQAlpha bundle not found at: {bundle_path}")
        
        self.bundle_path = bundle_path
        self._data_source = LocalDataSource(bundle_path)
        self._data_proxy = DataProxy(self._data_source)

    @staticmethod
    def _translate_symbol(symbol: str) -> str:
        if symbol.startswith("SHSE."):
            return symbol.replace("SHSE.", "") + ".XSHG"
        elif symbol.startswith("SZSE."):
            return symbol.replace("SZSE.", "") + ".XSHE"
        return symbol
```

- [ ] **Step 4: Fix test and run to verify it passes**
*Note: Since `__init__` now validates the bundle path, we should mock it or bypass it in the test since `_translate_symbol` is a static method.*

```python
# tests/test_etf_portfolio/test_rqalpha_data.py
import pytest
from src.etf_portfolio.rqalpha_data import RQAlphaDataSource

def test_symbol_translation():
    assert RQAlphaDataSource._translate_symbol("SHSE.600000") == "600000.XSHG"
    assert RQAlphaDataSource._translate_symbol("SZSE.000001") == "000001.XSHE"
    assert RQAlphaDataSource._translate_symbol("UNKNOWN.123") == "UNKNOWN.123"
```

Run: `uv run pytest tests/test_etf_portfolio/test_rqalpha_data.py::test_symbol_translation -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/etf_portfolio/rqalpha_data.py tests/test_etf_portfolio/test_rqalpha_data.py
git commit -m "feat(etf_portfolio): add RQAlphaDataSource and symbol translation"
```

---

### Task 2: Implement Protocol Methods (Basic, Valuation, Set Token)

**Files:**
- Modify: `src/etf_portfolio/rqalpha_data.py`
- Modify: `tests/test_etf_portfolio/test_rqalpha_data.py`

- [ ] **Step 1: Write failing tests for basic methods and token**

```python
# append to tests/test_etf_portfolio/test_rqalpha_data.py
import os
from unittest.mock import patch, MagicMock
import pandas as pd

@patch('src.etf_portfolio.rqalpha_data.LocalDataSource')
@patch('src.etf_portfolio.rqalpha_data.DataProxy')
@patch('os.path.exists')
def test_protocol_methods(mock_exists, mock_data_proxy, mock_local_data_source):
    mock_exists.return_value = True
    ds = RQAlphaDataSource("/fake/path")
    
    # set_token should do nothing and not raise
    ds.set_token("any_token")
    
    # fetch_basic and fetch_valuation should return empty dataframes
    df_basic = ds.fetch_basic("SHSE.600000", "2023-01-01", "2023-01-10")
    assert isinstance(df_basic, pd.DataFrame)
    assert df_basic.empty

    df_val = ds.fetch_valuation("SHSE.600000", "2023-01-01", "2023-01-10")
    assert isinstance(df_val, pd.DataFrame)
    assert df_val.empty
    
def test_init_raises_on_missing_bundle():
    with pytest.raises(FileNotFoundError):
        RQAlphaDataSource("/path/that/definitely/does/not/exist/12345")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_etf_portfolio/test_rqalpha_data.py::test_protocol_methods -v`
Expected: FAIL (missing methods)

- [ ] **Step 3: Implement methods**

```python
# append inside RQAlphaDataSource class in src/etf_portfolio/rqalpha_data.py

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_etf_portfolio/test_rqalpha_data.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/etf_portfolio/rqalpha_data.py tests/test_etf_portfolio/test_rqalpha_data.py
git commit -m "feat(etf_portfolio): implement basic methods for RQAlphaDataSource"
```

---

### Task 3: Implement `fetch_history`

**Files:**
- Modify: `src/etf_portfolio/rqalpha_data.py`
- Modify: `tests/test_etf_portfolio/test_rqalpha_data.py`

- [ ] **Step 1: Write failing test for `fetch_history`**

```python
# append to tests/test_etf_portfolio/test_rqalpha_data.py
import numpy as np

@patch('src.etf_portfolio.rqalpha_data.LocalDataSource')
@patch('src.etf_portfolio.rqalpha_data.DataProxy')
@patch('os.path.exists')
def test_fetch_history(mock_exists, mock_data_proxy_class, mock_local_data_source):
    mock_exists.return_value = True
    mock_proxy_instance = MagicMock()
    mock_data_proxy_class.return_value = mock_proxy_instance
    
    # Mock return value of history_bars (standard structured array from rqalpha)
    dt_type = np.dtype([('datetime', 'O'), ('close', 'f8'), ('volume', 'f8')])
    mock_array = np.array([(pd.Timestamp('2023-01-01'), 10.0, 100)], dtype=dt_type)
    mock_proxy_instance.history_bars.return_value = mock_array
    
    ds = RQAlphaDataSource("/fake/path")
    df = ds.fetch_history("SHSE.600000", "2023-01-01", "2023-01-10", frequency="1d")
    
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert 'close' in df.columns
    assert 'volume' in df.columns
    # symbol should be injected/re-mapped or we at least verify datetime index/column
    
    mock_proxy_instance.history_bars.assert_called_once_with(
        "600000.XSHG",
        bar_count=10000,  # Or whatever max we set, or dynamic
        frequency="1d",
        fields=None,
        dt=pd.Timestamp("2023-01-10"),
        skip_suspended=True,
        include_now=False
    )
```

*(Note: `history_bars` in RQAlpha proxy usually requires `bar_count` and `dt` (end date). To fetch between `start_time` and `end_time`, a common workaround is fetching a large `bar_count` and filtering the DataFrame by `start_time`, or using `get_all_bars` and filtering. We'll use `history_bars` with a large count and filter, as it matches the spec's intent to use `data_proxy`).*

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_etf_portfolio/test_rqalpha_data.py::test_fetch_history -v`
Expected: FAIL

- [ ] **Step 3: Implement `fetch_history`**

```python
# append inside RQAlphaDataSource class in src/etf_portfolio/rqalpha_data.py

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
```
*Note: Make sure to update the mock test if needed. The test checks `dt=pd.Timestamp("2023-01-10")`, `skip_suspended=True`.*

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_etf_portfolio/test_rqalpha_data.py::test_fetch_history -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/etf_portfolio/rqalpha_data.py tests/test_etf_portfolio/test_rqalpha_data.py
git commit -m "feat(etf_portfolio): implement fetch_history for RQAlphaDataSource"
```

---

### Task 4: Integration test (Optional / Verificaton)

**Files:**
- Modify: `tests/test_etf_portfolio/test_workflow.py` (or similar) or manually test.

- [ ] **Step 1: Check how `DataSource` is injected**

Typically the system uses `GMDataSource`. As the spec says, we should be able to substitute `GMDataSource` with `RQAlphaDataSource`. Create a small ad-hoc script or integration test if a bundle exists.
*Since we don't have a real bundle in CI, unit tests from Task 3 are sufficient to fulfill the adapter implementation.*

- [ ] **Step 2: Final static analysis check**

Run: `uv run ruff check src/etf_portfolio/rqalpha_data.py tests/test_etf_portfolio/test_rqalpha_data.py`
Run: `uv run ruff format src/etf_portfolio/rqalpha_data.py tests/test_etf_portfolio/test_rqalpha_data.py`

- [ ] **Step 3: Final Commit**

```bash
git commit -am "chore: format and lint RQAlphaDataSource"
```
