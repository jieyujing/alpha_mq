# ETF Portfolio Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a data fetching, rolling backtest, and evaluation pipeline for 15 ETFs using GM SDK, Riskfolio-Lib, and Quantstats.

**Architecture:** 
The pipeline consists of three main components: data extraction (`gm_data`), calculation engine (`riskfolio_engine` executing rolling windows), and evaluation (`evaluator` generating quantstats reports). The code will strictly adhere to Python 3.13, type hints, and PEP-8, utilizing `uv` for dependency management.

**Tech Stack:** Python 3.13, `uv`, GM SDK, `riskfolio-lib`, `quantstats`, `pandas`.

---

### Task 1: Environment & Dependency Setup

**Files:**
- Modify: `pyproject.toml`
- Create: `src/etf_portfolio/__init__.py`
- Create: `tests/test_etf_portfolio/__init__.py`

**Step 1: Install dependencies**
Run: `uv add riskfolio-lib quantstats openpyxl`
Verify: `uv check`

**Step 2: Commit**
```bash
git add pyproject.toml uv.lock src/etf_portfolio/ tests/test_etf_portfolio/
git commit -m "chore: setup etf portfolio optimization dependencies"
```

### Task 2: Data Acquisition Module (`gm_data`)

**Files:**
- Create: `src/etf_portfolio/gm_data.py`
- Create: `tests/test_etf_portfolio/test_gm_data.py`

**Step 1: Write the failing test**
Create `test_gm_data.py` with mock data to test `align_and_ffill_prices`.

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_etf_portfolio/test_gm_data.py -v`
Expected: FAIL 

**Step 3: Write minimal implementation**
Implement `gm_data.py` containing `fetch_etf_history(symbols, start_date, end_date)` using `gm.api.history`, returning a pivoted DataFrame of close prices, forward-filling `NaN`s for missing trading days. 

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_etf_portfolio/test_gm_data.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/etf_portfolio/gm_data.py tests/test_etf_portfolio/test_gm_data.py
git commit -m "feat: add gm data fetching and alignment module"
```

### Task 3: Riskfolio Single-Period Optimization Wrapper

**Files:**
- Create: `src/etf_portfolio/optimizer.py`
- Create: `tests/test_etf_portfolio/test_optimizer.py`

**Step 1: Write the failing test**
Create `test_optimizer.py` with dummy returns dataframe to evaluate `get_optimal_weights(returns, model, obj)`.

**Step 2: Run test**
Run: `uv run pytest tests/test_etf_portfolio/test_optimizer.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**
Write `optimizer.py` containing a mapping of algorithms to instantiate `rp.Portfolio`, calculate historical stats, and return optimal weights. Support models: EW, GMV, MaxSharpe, ERC, HRP, HERC, NCO.

**Step 4: Run test**
Run: `uv run pytest tests/test_etf_portfolio/test_optimizer.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/etf_portfolio/optimizer.py tests/test_etf_portfolio/test_optimizer.py
git commit -m "feat: add single-period riskfolio optimization wrapper"
```

### Task 4: Rolling Backtest Engine

**Files:**
- Create: `src/etf_portfolio/rolling.py`
- Create: `tests/test_etf_portfolio/test_rolling.py`

**Step 1: Write the failing test**
Create `test_rolling.py` feeding simulated 2-year daily prices to `run_rolling_backtest(prices, window=252, freq='M')`.

**Step 2: Run test**
Run: `uv run pytest tests/test_etf_portfolio/test_rolling.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**
Implement `rolling.py` that computes daily returns, slices 252-day windows at month-ends, pulls weights from `get_optimal_weights`, and vectors them with forward 1-month returns to piece together continuous daily portfolio returns. Return a dictionary of daily return Series indexed by model name.

**Step 4: Run test**
Run: `uv run pytest tests/test_etf_portfolio/test_rolling.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/etf_portfolio/rolling.py tests/test_etf_portfolio/test_rolling.py
git commit -m "feat: add rolling backtest engine for portfolio strategies"
```

### Task 5: Evaluation & Report Generator

**Files:**
- Create: `src/etf_portfolio/report.py`

**Step 1: Write minimal implementation**
Implement `report.py` using `quantstats.reports.html`. It accepts a dictionary of portfolio return Series and a target `reports/` output directory, generating `HTML` performance files for each model. 

**Step 2: Commit**
```bash
git add src/etf_portfolio/report.py
git commit -m "feat: add quantstats HTML report generation"
```

### Task 6: Master Script Assembly

**Files:**
- Create: `src/etf_portfolio/main.py`

**Step 1: Write main.py**
Assemble `fetch_etf_history`, `run_rolling_backtest` (looping through all our 7 target models), and `generate_reports`. Ensure `__main__` block executes properly.

**Step 2: Dry Run Test**
Run: `uv run python -m src.etf_portfolio.main`
Expected: Check reports are generated locally in `reports/` folder.

**Step 3: Commit**
```bash
git add src/etf_portfolio/main.py
git commit -m "feat: integrate main execution script for etf pipeline"
```
