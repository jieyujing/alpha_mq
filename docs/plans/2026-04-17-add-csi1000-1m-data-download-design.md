# Design: Add CSI 1000 1-Minute Data Download

## Context
The current `download_gm.py` script downloads daily bars (1d), valuations, market values, basic metrics, and fundamental data for the CSI 1000 index constituents. The user wants to add 1-minute (1m) data for the most recent week for the same stock pool.

## Goals
- Add 1-minute bar download functionality to `download_gm.py`.
- Restrict 1m data to the "last 7 days" to manage data volume and API quotas.
- Integrate it into the existing workflow as an optional step.

## Proposed Design

### 1. Refactor `download_category_data`
Modify `download_category_data(base_pool, category_name, fetch_func, limiter, start_date, end_date, fields=None)` to accept an optional `frequency='1d'` parameter.
- When `fetch_func` is `history`, use this `frequency` in the API call.

### 2. Update `run_download_workflow`
Add logic to handle 1m data:
- New parameter: `include_1m` (bool, default False).
- If `include_1m` is True:
    - Calculate `m1_start` (Current Time - 7 Days).
    - Call `download_category_data` for `history_1m` category.

### 3. CLI Integration
Update `argparse` to include a new flag.
- `--history-1m`: Boolean flag to enable the 1m download.

### 4. Storage
Data will be stored in `data/exports/history_1m/` as CSV files, following the existing pattern of one CSV per symbol.

## Considerations
- **API Limits**: 1m data fetches more records per call. The existing `RateLimiter` should handle the request frequency, but the total volume might take longer to process.
- **Data Volume**: 1 week of 1m data for 1000 stocks is approximately 1000 * 240 * 5 = 1.2M rows. CSV is acceptable for this volume.
