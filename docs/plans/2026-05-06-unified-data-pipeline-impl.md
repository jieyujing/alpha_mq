# Unified Data Ingest Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finalize and verify the unified data pipeline that aligns CSI 1000 market data with fundamental data using Polars.

**Architecture:** The pipeline uses `CSI1000Downloader` and `FundamentalsDownloader` for data ingestion, and `UnifiedDataPipeline` for Polars-based alignment using `join_asof` to prevent lookahead bias.

**Tech Stack:** Python, Polars, Pandas, GM API.

---

### Task 1: Complete Configuration

**Files:**
- Modify: `configs/unified_data.yaml`

**Step 1: Update `configs/unified_data.yaml` with missing fields**

```yaml
pipeline:
  name: "unified_data"
  stages:
    - "download"
    - "clean"
    - "align"

version: "1.0"

# GM token (suggested to get from env var GM_TOKEN)
token: null
index_code: "SHSE.000852"
start_date: "2020-01-01"
end_date: null

# Which downloader modules to enable
download_modules:
  - "csi1000"
  - "fundamentals"

# Directory configuration
exports_base: "data/exports"
processed_output: "data/processed"
output_file: "unified_daily_features.parquet"

data:
  source_type: "gm"
```

**Step 2: Commit**

```bash
git add configs/unified_data.yaml
git commit -m "config: update unified_data pipeline configuration"
```

---

### Task 2: Refine `UnifiedDataPipeline` Type Casting

**Files:**
- Modify: `src/pipelines/data_ingest/unified_pipeline.py`

**Step 1: Fix numeric casting in `_get_daily_spine`**

Ensure columns like `pe_ttm`, `tot_mv`, `turnrate` etc. are cast to floats after `scan_csv`.

```python
    def _get_daily_spine(self) -> pl.LazyFrame:
        # ... (lines 92-101)
        # 2. 关联其它日频表
        for name, d_dir in self.daily_dirs.items():
            if name == "history_1d" or not d_dir.exists() or not list(d_dir.glob("*.csv")):
                continue
            
            # 读取并连接日频附表
            df_lazy = pl.scan_csv(str(d_dir / "*.csv"), infer_schema_length=0)
            if "trade_date" in df_lazy.columns:
                df_lazy = df_lazy.with_columns(pl.col("trade_date").str.slice(0, 10).alias("date"))
            
            # Type casting to Float64 for numeric columns
            numeric_cols = {
                "valuation": ["pe_ttm", "pb_mrq", "ps_ttm", "pcf_ttm_oper"],
                "mktvalue": ["tot_mv", "a_mv"],
                "basic": ["tclose", "turnrate", "ttl_shr", "circ_shr"],
                "adj_factor": ["adj_factor_fwd"]
            }
            
            if name in numeric_cols:
                cols_to_cast = [c for c in numeric_cols[name] if c in df_lazy.columns]
                df_lazy = df_lazy.with_columns([pl.col(c).cast(pl.Float64) for c in cols_to_cast])

            # ... rest of selection logic ...
```

**Step 2: Fix numeric casting in `_get_fundamentals_base`**

The fundamental columns should also be cast to floats where appropriate. Since there are many, we might want to cast everything except keys to floats.

```python
    def _get_fundamentals_base(self) -> pl.LazyFrame:
        # ... (lines 130-141)
            df = pl.scan_csv(str(f_dir / "*.csv"), infer_schema_length=0)
            
            # Cast non-key columns to Float64
            keys = ["symbol", "pub_date", "rpt_date", "rpt_type", "data_type"]
            non_key_cols = [c for c in df.columns if c not in keys]
            df = df.with_columns([pl.col(c).cast(pl.Float64) for c in non_key_cols])
            
            # 基础清洗: 去重
            df = df.unique(subset=["symbol", "pub_date", "rpt_date"])
```

**Step 3: Run existing tests (if any)**

Run: `uv run pytest tests/pipelines/test_unified_pipeline.py` (if it exists)

**Step 4: Commit**

```bash
git add src/pipelines/data_ingest/unified_pipeline.py
git commit -m "feat: add numeric type casting to UnifiedDataPipeline"
```

---

### Task 3: Test Anti-Lookahead Logic

**Files:**
- Create: `tests/pipelines/test_unified_pipeline_logic.py`

**Step 1: Write the test to verify `join_asof`**

Create a test that mocks daily prices and quarterly fundamentals with specific `pub_date` and verifies that data is only available on/after `pub_date`.

```python
import pytest
import polars as pl
from datetime import date
from src.pipelines.data_ingest.unified_pipeline import UnifiedDataPipeline

def test_asof_join_lookahead_prevention():
    # Mock daily spine
    spine = pl.DataFrame({
        "symbol": ["SHSE.600000"] * 5,
        "date": [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4), date(2023, 1, 5)],
        "close": [10.0, 10.1, 10.2, 10.3, 10.4]
    }).lazy()

    # Mock fundamentals: published on 2023-01-03
    fund = pl.DataFrame({
        "symbol": ["SHSE.600000"],
        "pub_date": [date(2023, 1, 3)],
        "net_profit": [1000.0]
    }).lazy()

    # Perform asof join (mimic align logic)
    result = spine.join_asof(
        fund,
        left_on="date",
        right_on="pub_date",
        by="symbol",
        strategy="backward"
    ).collect()

    # Check: net_profit should be null before 2023-01-03
    assert result.filter(pl.col("date") < date(2023, 1, 3))["net_profit"].null_count() == 2
    # Check: net_profit should be 1000.0 from 2023-01-03 onwards
    assert result.filter(pl.col("date") >= date(2023, 1, 3))["net_profit"].to_list() == [1000.0, 1000.0, 1000.0]
```

**Step 2: Run test**

Run: `uv run pytest tests/pipelines/test_unified_pipeline_logic.py`

**Step 3: Commit**

```bash
git add tests/pipelines/test_unified_pipeline_logic.py
git commit -m "test: verify anti-lookahead logic in UnifiedDataPipeline"
```

---

### Task 4: End-to-End Smoke Test (Optional/Mocked)

**Files:**
- Create: `scripts/smoke_test_unified_pipeline.py`

**Step 1: Write a script to run a slice of the pipeline**

Use `run_pipeline.py` but with a config that limits the scope (e.g. only "align" stage if data exists).

```bash
uv run python scripts/run_pipeline.py --config configs/unified_data.yaml --stages align
```

**Step 2: Verify output file exists**

```bash
Test-Path data/processed/unified_daily_features.parquet
```

**Step 3: Commit**

```bash
git add scripts/smoke_test_unified_pipeline.py
git commit -m "test: add smoke test script for unified pipeline"
```
