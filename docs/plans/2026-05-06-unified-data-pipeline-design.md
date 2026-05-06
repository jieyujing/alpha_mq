# Unified Data Ingest Pipeline Design

## Overview
This design outlines a unified data pipeline that orchestrates the downloading, cleaning, merging, and daily alignment of all CSI 1000 constituent data (including daily OHLCV, valuation, basic metrics, and quarterly financial statements). The goal is to produce a highly performant, Polars-based daily-aligned cross-sectional wide table (`unified_daily_features.parquet`) that feeds directly into the factor calculation pipeline, strictly preventing lookahead bias.

## Architecture & Components
- **Configuration**: `configs/unified_data.yaml` defines the download parameters, target index, and pipeline stages.
- **Pipeline Class**: `src/pipelines/data_ingest/unified_pipeline.py` implements `UnifiedDataPipeline` inheriting from `DataPipeline`.
- **Downloader Modules**: Reuse the newly created `FundamentalsDownloader` and existing `CSI1000Downloader`.

## Data Flow (Polars)
1. **Stage: Download (Ingest)**
   - Run `CSI1000Downloader` for high-frequency daily data (`history_1d`, `valuation`, `mktvalue`, `basic`).
   - Run `FundamentalsDownloader` for low-frequency data (Income, Balance, Cashflow).
   - *Both support incremental fetching to minimize API calls.*

2. **Stage: Clean & Base Merge**
   - Use Polars to load the three financial statement CSVs.
   - Deduplicate based on `(symbol, pub_date, rpt_date)`.
   - Perform an Outer Join across the three statements to form a unified, low-frequency base financial table.

3. **Stage: Daily Alignment (Merge)**
   - **Spine**: Load `history_1d` (OHLCV) to serve as the daily trading calendar spine for each symbol.
   - **Daily Join**: Left-join `valuation`, `mktvalue`, and `basic` onto the spine using `date` and `symbol`.
   - **As-Of Join (Anti-Lookahead)**: Use Polars `join_asof` to match the low-frequency financial table to the daily spine. By joining on `spine.date >= financial.pub_date`, we ensure that quarterly financial data only becomes available to models on or after the day it was officially published.

4. **Stage: Quality Report (on_success)**
   - Generate a comprehensive data quality report using the existing `QualityReporter` framework.
   - The report will highlight missing data, unaligned dates, and overall coverage statistics across both price-volume and fundamental data.

## Outputs
- `data/processed/unified_daily_features.parquet`: The final, analysis-ready wide table.
- Data Quality Report (HTML/MD) generated in `reports/` summarizing the pipeline execution results.
