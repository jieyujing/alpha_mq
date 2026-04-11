import os
import polars as pl
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def process_l2():
    backend_dir = "data/backend"
    static_dir = "data/exports/static"
    
    l1_path = os.path.join(backend_dir, "l1_basic.parquet")
    if not os.path.exists(l1_path):
        logging.error(f"L1 data not found at {l1_path}. Run clean_basic_l1.py first.")
        return

    logging.info("Loading L1 data...")
    df = pl.read_parquet(l1_path)
    
    # 1. Load Static Data for ST detection
    industry_path = os.path.join(static_dir, "industry.csv")
    if os.path.exists(industry_path):
        logging.info("Loading industry/sec_name data...")
        df_ind = pl.read_csv(industry_path).select(["symbol", "sec_name"])
        df = df.join(df_ind, on="symbol", how="left")
    else:
        logging.warning("industry.csv not found, is_st may be inaccurate.")
        df = df.with_columns(pl.lit(None).alias("sec_name"))

    # 2. Logic for Tradability
    logging.info("Calculating tradability features...")
    
    # Heuristic for ST: name contains ST
    df = df.with_columns(
        pl.col("sec_name").fill_null("").str.contains(r"(?i)ST").alias("is_st")
    )
    
    # Suspended: volume is 0
    df = df.with_columns(
        (pl.col("volume") == 0).alias("is_suspended")
    )

    # Limit Up/Down logic (Simplified for now, as limits can vary by board)
    # Standard 10% limit. We use 0.098/1.098 to be safer with rounding.
    df = df.with_columns([
        (pl.col("close") >= (pl.col("pre_close") * 1.097).round(2)).alias("is_limit_up"),
        (pl.col("close") <= (pl.col("pre_close") * 0.903).round(2)).alias("is_limit_down"),
    ])

    # 3. Listed Days (Heuristic if list_date is missing)
    # We'll try to find the first appearing date for each symbol in our dataset as a proxy if we can't find list_date
    df = df.with_columns(
        pl.col("date").min().over("symbol").alias("first_trade_date")
    )
    df = df.with_columns(
        ((pl.col("date") - pl.col("first_trade_date")).dt.total_days()).alias("listed_days")
    )

    # 4. Final Tradability Mask
    # A stock is "tradable" today if it's not suspended and not at limit
    # (Actually, you can buy at limit down and sell at limit up, but usually "tradable" refers to normal execution)
    df = df.with_columns(
        (~pl.col("is_suspended") & ~pl.col("is_limit_up") & ~pl.col("is_limit_down")).alias("is_tradable")
    )

    out_path = os.path.join(backend_dir, "l2_status.parquet")
    logging.info(f"Saving L2 data to {out_path}...")
    df.write_parquet(out_path, compression="zstd")
    logging.info(f"L2 Saved ({df.height} rows)")

if __name__ == "__main__":
    process_l2()
