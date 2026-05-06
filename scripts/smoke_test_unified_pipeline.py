import polars as pl
from pathlib import Path

def main():
    out_path = Path("data/processed/unified_daily_features.parquet")
    if out_path.exists():
        try:
            df = pl.read_parquet(out_path)
            print(f"Success! Shape: {df.shape}")
            print("Columns:", df.columns)
            print(df.head())
            
            # 检查关键列
            required_cols = ["date", "symbol", "open", "close", "high", "low", "volume"]
            missing = [col for col in required_cols if col not in df.columns]
            if missing:
                print(f"Warning: Missing columns: {missing}")
            else:
                print("All required columns present.")
                
        except Exception as e:
            print(f"Error reading parquet: {e}")
    else:
        print(f"Failed: Output file not found at {out_path}")

if __name__ == "__main__":
    main()
