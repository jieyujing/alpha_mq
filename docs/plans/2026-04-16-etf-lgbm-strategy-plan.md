# ETF LightGBM Strategy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a LightGBM-based cross-asset style allocation strategy for the ETF pool with custom ReLU constraints and macro block features.

**Architecture:** Pure Pandas min-max feature engineering and `lightgbm` rolling training, encapsulated in a new `ml_strategy.py` module. Output interfaces with QuantStats reporting.

**Tech Stack:** pandas, numpy, lightgbm, pytest

---

### Task 1: Update Data Fetcher for Volume Data

**Files:**
- Modify: `src/etf_portfolio/main.py:27-66`

**Step 1: Write the failing test**
*Skipped for data fetcher to avoid external GM API mocks, we will modify the actual execution logic directly.*

**Step 2: Write minimal implementation**
We need to pull volume data into the MultiIndex DataFrame so we can compute `volume_z_20`.

```python
# In src/etf_portfolio/main.py
# Change fields string
fields = 'symbol,bob,open,high,low,close,volume'

# In align_and_ffill_prices
fields = ['open', 'high', 'low', 'close', 'volume']
```

**Step 3: Commit**
```bash
git add src/etf_portfolio/main.py
git commit -m "feat: add volume data to ETF history fetcher"
```

---

### Task 2: Implement Feature Engineering core functions

**Files:**
- Create: `src/etf_portfolio/ml_strategy.py`
- Test: `tests/test_etf_portfolio/test_ml_strategy.py`

**Step 1: Write the failing test**

```python
# tests/test_etf_portfolio/test_ml_strategy.py
import pandas as pd
import numpy as np
from src.etf_portfolio.ml_strategy import assemble_portfolio

def test_assemble_portfolio():
    # Mock scores
    scores = pd.Series({
        'SHSE.518800': 0.5, # Gold
        'SZSE.162411': 0.4, # Oil
        'SHSE.501018': 0.3, # Oil
        'SHSE.510300': 0.2, # HS300
        'SZSE.159915': 0.1, # ChiNext
    })
    
    weights = assemble_portfolio(scores, top_n=4, single_cap=0.35, energy_cap=0.20)
    
    # Check max 4 selected
    assert (weights > 0).sum() <= 4
    
    # Check single cap
    assert weights.max() <= 0.35
    
    # Check energy cap
    assert weights.get('SZSE.162411', 0) + weights.get('SHSE.501018', 0) <= 0.20
    
    # Check sum to 1
    np.testing.assert_almost_equal(weights.sum(), 1.0)
```

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_etf_portfolio/test_ml_strategy.py -v`
Expected: FAIL due to missing `ml_strategy.py`.

**Step 3: Write minimal implementation**

Create `src/etf_portfolio/ml_strategy.py`. Develop the `assemble_portfolio` function:

```python
import pandas as pd
import numpy as np

def assemble_portfolio(scores: pd.Series, top_n=4, single_cap=0.35, energy_cap=0.20) -> pd.Series:
    """Implement the ReLU Top-N capped allocation."""
    # 1. Top N and ReLU
    s = scores.copy()
    s = s.nlargest(top_n)
    s = s.clip(lower=0) 
    
    if s.sum() <= 0:
        # Fallback to defense
        fallback = pd.Series(0.0, index=scores.index)
        if 'SHSE.511260' in scores.index:
            fallback['SHSE.511260'] = 1.0
        elif 'SHSE.518800' in scores.index:
            fallback['SHSE.518800'] = 1.0
        return fallback

    # Initialize weights
    w = s / s.sum()
    
    # Energy indices
    energy_assets = [c for c in w.index if c in ['SZSE.162411', 'SHSE.501018']]
    
    # Iterative capping
    for _ in range(5):
        # Apply energy cap
        energy_w = w[energy_assets].sum()
        if energy_w > energy_cap:
            reduce_factor = energy_cap / energy_w
            w[energy_assets] = w[energy_assets] * reduce_factor
            
        # Apply single cap
        w = w.clip(upper=single_cap)
        
        # Normalize non-capped
        current_sum = w.sum()
        if np.isclose(current_sum, 1.0):
            break
            
        # Distribute remainder
        remainder = 1.0 - current_sum
        # Items that can receive more
        can_receive = w.index[(w < single_cap) & (~w.index.isin(energy_assets))]
        if len(can_receive) == 0:
            break
            
        add_per = remainder / len(can_receive)
        w[can_receive] += add_per

    return w / w.sum()
```

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_etf_portfolio/test_ml_strategy.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/etf_portfolio/ml_strategy.py tests/test_etf_portfolio/test_ml_strategy.py
git commit -m "feat: add ReLU and constrained portfolio assembler"
```

---

### Task 3: Implement Feature Generation and ML Pipeline

**Files:**
- Modify: `src/etf_portfolio/ml_strategy.py`

**Step 1: Write implementation for `build_features` and LightGBM pipeline**

Add `lightgbm` via `uv add lightgbm`.
Implement `build_features(prices)` containing all the indicator logic:
- Individual indicators: EMA/ROC/ATR/RSI using `prices_close`, `prices_high`, `prices_low`, `prices_volume`.
- Macro indicators: `gold_oil_ratio`, etc.
- Label: `fwd_ret_20 / fwd_vol_20`. Drop last 20 rows of label.
- Output: `X` dataframe and `y` series.

Implement `run_ml_rolling_backtest(prices)`:
- Find rebalance dates (Monthly).
- For each date `T`, get data up to `T`.
- Extract `X_train`, `y_train` from `T-750` to `T-20`.
- Extract `X_test` (just row `T`).
- Train `LGBMRegressor(n_estimators=100, max_depth=5, learning_rate=0.05)`.
- Predict `score_i`.
- Pass to `assemble_portfolio`.
- Store weights.
- Compute daily returns.

**Step 2: Commit**
```bash
git add src/etf_portfolio/ml_strategy.py pyproject.toml uv.lock
git commit -m "feat: build LGBM feature engine and rolling ML backtest"
```

---

### Task 4: Command Line Integration

**Files:**
- Modify: `src/etf_portfolio/ml_strategy.py`

**Step 1: Write main block**
Fetch data using `fetch_etf_history` from `main.py`.
Run `run_ml_rolling_backtest`.
Format the output into `all_returns = {'LightGBM_MVP': ml_returns}`.
Call `generate_reports(all_returns, output_dir='reports')`.

**Step 2: Run execution to verify full pipeline**
Run: `uv run python -m src.etf_portfolio.ml_strategy`
Expected: Outputs a teardown html in `reports/` with realistic constraints.

**Step 3: Commit**
```bash
git add src/etf_portfolio/ml_strategy.py
git commit -m "feat: run ML strategy and generate reports"
```
