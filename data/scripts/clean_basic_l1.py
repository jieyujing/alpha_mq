import os
import glob
import polars as pl
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def safe_scan_csv(pattern, with_symbol_from_filename=False):
    files = glob.glob(pattern)
    if not files:
        raise ValueError(f"No files found for pattern: {pattern}")
    dfs = []
    for f in files:
        df = pl.read_csv(f)
        if with_symbol_from_filename and "symbol" not in df.columns:
            symbol = os.path.basename(f).replace(".csv", "")
            df = df.with_columns(pl.lit(symbol).alias("symbol"))
        dfs.append(df)
    return pl.concat(dfs, how="diagonal_relaxed").lazy()

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
        pl.col("trade_date").str.to_datetime("%Y-%m-%d").alias("date")
    ).select("date")
    
    # 2. Lazy load history_1d
    logging.info("Scanning history_1d...")
    df_history = safe_scan_csv(os.path.join(base_dir, "history_1d", "*.csv"), with_symbol_from_filename=True).with_columns(
        pl.col("bob").str.slice(0, 10).str.to_datetime("%Y-%m-%d").alias("date")
    )
    
    # 3. Lazy load adj_factor
    logging.info("Scanning adj_factor...")
    df_adj = safe_scan_csv(os.path.join(base_dir, "adj_factor", "*.csv"), with_symbol_from_filename=True).with_columns([
        pl.col("trade_date").str.slice(0, 10).str.to_datetime("%Y-%m-%d").alias("date"),
        pl.col("adj_factor_bwd").alias("adj_factor")
    ])
    
    # 4. Lazy load basic
    logging.info("Scanning basic...")
    df_basic = safe_scan_csv(os.path.join(base_dir, "basic", "*.csv"), with_symbol_from_filename=True).with_columns(
        pl.col("trade_date").str.slice(0, 10).str.to_datetime("%Y-%m-%d").alias("date")
    )
    
    # Combine everything via join
    df_l1 = (
        df_history.join(df_adj, on=["symbol", "date"], how="left", validate="m:1")
        .join(df_basic, on=["symbol", "date"], how="left", validate="m:1")
        .sort(["symbol", "date"])
        .with_columns(
            pl.col("adj_factor").forward_fill().over("symbol")
        )
    )
    
    # Calculate adjusted prices
    df_l1 = df_l1.with_columns([
        (pl.col("open") * pl.col("adj_factor")).alias("open_adj"),
        (pl.col("high") * pl.col("adj_factor")).alias("high_adj"),
        (pl.col("low") * pl.col("adj_factor")).alias("low_adj"),
        (pl.col("close") * pl.col("adj_factor")).alias("close_adj"),
    ])
    
    # basic cleaning mask
    # For missing volume/amount fields from some API calls, we use strict fill logic or assume null handling
    df_l1 = df_l1.with_columns(
        ((pl.col("volume") > 0) & (pl.col("amount") > 0) & (pl.col("low") > 0) & (pl.col("high") >= pl.col("open"))).alias("is_valid_bar")
    )
    
    logging.info("Collecting and saving to Parquet (This may take a moment)...")
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
