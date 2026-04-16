import os
import polars as pl
import logging
import glob

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def process_l3():
    backend_dir = "data/backend"
    
    l2_path = os.path.join(backend_dir, "l2_status.parquet")
    if not os.path.exists(l2_path):
        logging.error(f"L2 data not found at {l2_path}. Run tradability_l2.py first.")
        return

    logging.info("Loading L2 data...")
    df = pl.read_parquet(l2_path)
    
    # --- Join Market Value & Industry ---
    export_dir = "data/exports"
    
    logging.info("Loading market value data...")
    mktvalue_pattern = os.path.join(export_dir, "mktvalue", "*.csv")
    def _read_mkt():
        dfs = []
        for f in glob.glob(mktvalue_pattern):
            symbol = os.path.basename(f).replace(".csv", "")
            dfs.append(pl.read_csv(f).with_columns(pl.lit(symbol).alias("symbol")))
        return pl.concat(dfs, how="diagonal_relaxed").with_columns(
            pl.col("trade_date").str.to_datetime("%Y-%m-%d").alias("date")
        ).select(["symbol", "date", "a_mv", "tot_mv"])
    
    df_mkt = _read_mkt()
    
    logging.info("Loading industry data...")
    df_ind = pl.read_csv(os.path.join(export_dir, "static", "industry.csv")).select([
        "symbol", "industry_code", "industry_name"
    ])
    
    logging.info("Merging additional features to universe...")
    df = df.join(df_mkt, on=["symbol", "date"], how="left")
    df = df.join(df_ind, on="symbol", how="left")
    # ------------------------------------
    
    # 1. Rolling Liquidity (e.g., 20-day average amount)
    logging.info("Computing rolling liquidity...")
    df = df.sort(["symbol", "date"])
    
    df = df.with_columns(
        pl.col("amount").rolling_mean(window_size=20).over("symbol").alias("amount_ma20")
    )
    
    # 2. Strategy Universe Filters
    # Filter 1: Not ST
    # Filter 2: Listed > 60 days
    # Filter 3: Liquidity (e.g., amount_ma20 > 10M) - adjustable
    # Filter 4: Not suspended today
    
    logging.info("Applying universe filters...")
    df = df.with_columns(
        (
            (~pl.col("is_st")) & 
            (pl.col("listed_days") > 60) & 
            (pl.col("amount_ma20") > 1e7) & # 10 million RMB
            (~pl.col("is_suspended"))
        ).alias("in_universe")
    )

    # 3. Next-Day Tradability Logic (Critical for Backtesting)
    # can_buy_next_open: Can we buy at tomorrow's open?
    # Usually we check if it's not suspended tomorrow and not limit-up at tomorrow's open.
    # Since we only have daily data, we often use today's status as a proxy or shift tomorrow's tradability.
    
    # Let's shift tomorrow's "is_tradable" to today's row to know if we can trade tomorrow.
    df = df.with_columns(
        pl.col("is_tradable").shift(-1).over("symbol").alias("can_trade_next_day")
    )
    
    # More specific: can_buy_tomorrow if tomorrow is not suspended and tomorrow open is not limit-up.
    # Since we don't have tomorrow's open limit status easily, we use is_tradable as proxy.
    df = df.with_columns(
        (pl.col("in_universe") & pl.col("can_trade_next_day").fill_null(False)).alias("target_universe")
    )

    out_path = os.path.join(backend_dir, "l3_universe.parquet")
    logging.info(f"Saving L3 data to {out_path}...")
    df.write_parquet(out_path, compression="zstd")
    logging.info(f"L3 Saved ({df.height} rows)")

if __name__ == "__main__":
    process_l3()
