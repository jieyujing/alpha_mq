# Expected CSV format for price data

The `prices.csv` file should contain daily (or any periodic) closing prices for each asset.

```csv
Date,AAPL,MSFT,GOOG,AMZN
2023-01-01,150.12,310.45,2790.84,3325.55
2023-01-02,152.33,312.10,2805.20,3340.10
...
```

- **Date**: ISO‑8601 date string (`YYYY‑MM‑DD`).
- **Columns**: One column per ticker symbol.
- **Values**: Adjusted closing prices (or raw close, but be consistent).
- No missing values; if a ticker is missing on a date, forward‑fill or drop that row before feeding to Riskfolio‑Lib.

The skill assumes the file is located in the current working directory or you provide the path when calling the script.
