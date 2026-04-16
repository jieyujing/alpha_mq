# Polars Data Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the L1, L2, and L3 data layers of a custom quantitative trading framework using Polars.

**Architecture:** We use Polars to read the distributed `.csv` chunks out of `data/exports/**/*.csv` using LazyFrame API `scan_csv`. Then, three independent scripts construct Parquet representations corresponding to specific data cleaning layers (Basic Structural, Tradability Features, and Trade Universe Filtering) resulting in `data/backend/*.parquet`.

**Tech Stack:** Python 3.13, `polars`, `pyarrow`

---

### Task 1: Initialize Backend Directory & Add Dependencies

**Files:**
- Create/Verify: `data/backend/` directory
- Modify: `pyproject.toml`

**Step 1: Install Polars and PyArrow via uv**

Run: `uv add polars pyarrow`
Expected: PASS and modifies `pyproject.toml`.

**Step 2: Create backend directory**

Run: `mkdir -p data/backend/` (or via Python `os.makedirs`)
Expected: Directory created.

---

### Task 2: L1 结构清洗层 `clean_basic_l1.py`

**Files:**
- Create: `data/scripts/clean_basic_l1.py`

**Step 1: Write the implementation script**

```python
import os
import polars as pl
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def process_l1():
    base_dir = "data/exports"
    backend_dir = "data/backend"
    os.makedirs(backend_dir, exist_ok=True)
    
    # 1. Load Calendar
    calendar_path = os.path.join(base_dir, "calendar", "trade_dates.csv")
    if not os.path.exists(calendar_path):
        logging.warning("Calendar not found. Run download_gm.py first.")
        return
        
    df_cal = pl.read_csv(calendar_path).with_columns(
        pl.col("trade_date").cast(pl.Datetime("us", time_zone=None)).alias("date")
    ).select("date")
    
    # 2. Lazy load history_1d
    # Note: A real implementation will scan_csv, cast bob to date, etc.
    logging.info("Scanning history_1d...")
    df_history = pl.scan_csv(os.path.join(base_dir, "history_1d", "*.csv")).with_columns(
        pl.col("bob").str.slice(0, 10).str.strptime(pl.Datetime).alias("date")
    )
    
    # 3. Lazy load adj_factor
    logging.info("Scanning adj_factor...")
    df_adj = pl.scan_csv(os.path.join(base_dir, "adj_factor", "*.csv")).with_columns(
        pl.col("trade_date").str.slice(0, 10).str.strptime(pl.Datetime).alias("date")
    )
    
    # 4. Lazy load basic
    logging.info("Scanning basic...")
    df_basic = pl.scan_csv(os.path.join(base_dir, "basic", "*.csv")).with_columns(
        pl.col("trade_date").str.slice(0, 10).str.strptime(pl.Datetime).alias("date")
    )
    
    # Combine everything via join
    df_l1 = (
        df_history.join(df_adj, on=["symbol", "date"], how="left", validate="m:1")
        .join(df_basic, on=["symbol", "date"], how="left", validate="m:1")
    )
    
    # Calculate adjusted prices
    df_l1 = df_l1.with_columns([
        (pl.col("open") * pl.col("adj_factor")).alias("open_adj"),
        (pl.col("high") * pl.col("adj_factor")).alias("high_adj"),
        (pl.col("low") * pl.col("adj_factor")).alias("low_adj"),
        (pl.col("close") * pl.col("adj_factor")).alias("close_adj"),
    ])
    
    # basic cleaning mask
    df_l1 = df_l1.with_columns(
        ((pl.col("volume") > 0) & (pl.col("amount") > 0) & (pl.col("low") > 0) & (pl.col("high") >= pl.col("open"))).alias("is_valid_bar")
    )
    
    logging.info("Collecting and saving to Parquet ...")
    df_final = df_l1.collect()
    
    # Avoid saving if empty
    if df_final.height == 0:
        logging.warning("No data found to process.")
        return
        
    out_path = os.path.join(backend_dir, "l1_basic.parquet")
    df_final.write_parquet(out_path, compression="zstd")
    logging.info(f"L1 Saved: {out_path} ({df_final.height} rows)")

if __name__ == "__main__":
    process_l1()
```

**Step 2: Run to make sure it functions**

Run: `uv run python data/scripts/clean_basic_l1.py`
Expected: Generates `l1_basic.parquet`

**Step 3: Commit**

```bash
git add data/scripts/clean_basic_l1.py pyproject.toml uv.lock
git commit -m "feat: setup polars backend and implement L1 data cleanup pipeline"
```

---

### Task 3: L2 交易状态层 `tradability_l2.py`

**Files:**
- Create: `data/scripts/tradability_l2.py`

**Step 1: Write the implementation script**

*(Using boolean logic for `is_limit_up`, `is_limit_down`, extracting `list_date` from static files, calculating `listed_days`, and generating `l2_status.parquet`)*

**Step 2: Run and verify execution**

Run: `uv run python data/scripts/tradability_l2.py`
Expected: Output `l2_status.parquet` smoothly.

**Step 3: Commit**

```bash
git add data/scripts/tradability_l2.py
git commit -m "feat: implement L2 tradability and listing status computation"
```

---

### Task 4: L3 研究股票池层 `universe_l3.py`

**Files:**
- Create: `data/scripts/universe_l3.py`

**Step 1: Write the implementation script**

*(Using Polars Window functions logic on L2 Data to compute rolling sum/mean of `amount` to determine liquidity universe, plus generation of the critical `can_buy_next_open` boolean shift logic)*

**Step 2: Run and verify execution**

Run: `uv run python data/scripts/universe_l3.py`
Expected: Output `l3_universe.parquet` smoothly.

**Step 3: Commit**

```bash
git add data/scripts/universe_l3.py
git commit -m "feat: implement L3 strategy universe definition and filters"
```
