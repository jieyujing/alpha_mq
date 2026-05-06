"""
Unified Data Pipeline

Orchestrates downloading, cleaning, and aligning daily market data with fundamental data
using Polars for high performance and anti-lookahead as-of joins.
"""
import logging
import os
import polars as pl
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from pipelines.base import DataPipeline

class UnifiedDataPipeline(DataPipeline):
    """
    Unified Data Ingest Pipeline
    
    Stages:
    - download: Fetch data from GM API using CSI1000Downloader and FundamentalsDownloader.
    - clean: Basic cleaning of raw data.
    - align: Align daily market data with quarterly fundamentals using join_asof.
    """

    STAGE_METHOD_MAP = {
        "download": "download",
        "clean": "clean",
        "align": "align",
    }

    def __init__(self, config: dict):
        super().__init__(config)
        self.exports_base = Path(config.get("exports_base", "data/exports"))
        self.processed_output = Path(config.get("processed_output", "data/processed"))
        self.output_file = self.processed_output / config.get("output_file", "unified_daily_features.parquet")
        
        # Directories for different data types
        self.daily_dirs = {
            "history_1d": self.exports_base / "history_1d",
            "valuation": self.exports_base / "valuation",
            "mktvalue": self.exports_base / "mktvalue",
            "basic": self.exports_base / "basic",
            "adj_factor": self.exports_base / "adj_factor"
        }
        
        self.fundamental_dirs = {
            "income": self.exports_base / "fundamentals_income",
            "balance": self.exports_base / "fundamentals_balance",
            "cashflow": self.exports_base / "fundamentals_cashflow"
        }

    def setup(self):
        """Pipeline setup: create directories"""
        self.processed_output.mkdir(parents=True, exist_ok=True)
        logging.info(f"Pipeline setup complete. Output: {self.output_file}")

    def download(self):
        """Download phase: run registered downloaders"""
        modules = self.config.get("download_modules", ["csi1000", "fundamentals"])
        
        token = self.config.get("token") or os.environ.get("GM_TOKEN")
        if not token:
            logging.warning("Download stage requires GM token. Set token in config or GM_TOKEN env var.")
            return

        download_config = {
            "token": token,
            "index_code": self.config.get("index_code", "SHSE.000852"),
            "exports_base": str(self.exports_base),
            "start_date": self.config.get("start_date", "2020-01-01"),
            "end_date": self.config.get("end_date") or datetime.now().strftime("%Y-%m-%d"),
        }

        if "csi1000" in modules:
            from src.data_download.csi1000_downloader import CSI1000Downloader
            logging.info("Starting CSI1000 incremental download...")
            downloader = CSI1000Downloader(download_config)
            downloader.run()

        if "fundamentals" in modules:
            from src.data_download.fundamentals_downloader import FundamentalsDownloader
            logging.info("Starting Fundamentals incremental download...")
            downloader = FundamentalsDownloader(download_config)
            downloader.run()
            
        logging.info("Download stage completed")

    def clean(self):
        """Clean phase: placeholder for specific cleaning logic if needed"""
        logging.info("Clean stage: verifying data directory structure...")
        for name, path in self.daily_dirs.items():
            if not path.exists():
                logging.warning(f"Daily directory missing: {path}")
        for name, path in self.fundamental_dirs.items():
            if not path.exists():
                logging.warning(f"Fundamental directory missing: {path}")

    def validate(self) -> List[str]:
        """Validate phase: check if essential data exists"""
        errors = []
        if not self.daily_dirs["history_1d"].exists():
            errors.append(f"Missing history_1d: {self.daily_dirs['history_1d']}")
        
        # Check if there are any CSV files in history_1d
        if self.daily_dirs["history_1d"].exists():
            csv_files = list(self.daily_dirs["history_1d"].glob("*.csv"))
            if not csv_files:
                errors.append(f"No CSV files in {self.daily_dirs['history_1d']}")
                
        if errors:
            logging.warning(f"Validation found {len(errors)} issues")
        else:
            logging.info("Validation passed")
        return errors

    def align(self):
        """
        Align phase:
        1. Create daily spine from history_1d.
        2. Merge daily extras (valuation, basic, etc.).
        3. Merge quarterly fundamentals using as-of join on pub_date.
        """
        logging.info("Starting alignment using Polars...")
        
        # 1. Get daily spine with all daily-frequency data
        daily_df = self._get_daily_spine()
        
        # 2. Get fundamental base table
        fund_df = self._get_fundamentals_base()
        
        # 3. Perform As-Of Join to prevent lookahead bias
        # We join on daily.date >= fund.pub_date
        logging.info("Performing join_asof to align fundamentals with daily spine...")
        final_df = daily_df.join_asof(
            fund_df,
            left_on="date",
            right_on="pub_date",
            by="symbol",
            strategy="backward"
        )
        
        # 4. Save result
        logging.info(f"Saving aligned data to {self.output_file}...")
        final_df.sink_parquet(self.output_file)
        logging.info("Alignment stage completed successfully")

    def _get_daily_spine(self) -> pl.LazyFrame:
        """Collect and join all daily frequency data into a single LazyFrame"""
        history_dir = self.daily_dirs["history_1d"]
        if not history_dir.exists():
            raise FileNotFoundError(f"History 1d directory not found: {history_dir}")
            
        # Scan history files individually due to potential header mismatches
        logging.info("Scanning history_1d files...")
        history_files = list(history_dir.glob("*.csv")) + list(history_dir.glob("*.parquet"))
        if not history_files:
            raise FileNotFoundError(f"No CSV or Parquet files found in {history_dir}")
            
        history_frames = []
        reference_cols = None
        for f in history_files:
            if f.suffix == ".csv":
                df = pl.scan_csv(f, infer_schema_length=1000)
            else:
                df = pl.scan_parquet(f)
            
            # GM history data usually has 'bob' (timestamp)
            schema = df.collect_schema()
            df_cols = schema.names()
            if "bob" in df_cols:
                dtype = schema["bob"]
                if dtype == pl.String:
                    df = df.with_columns(pl.col("bob").str.slice(0, 10).alias("date"))
                else:
                    df = df.with_columns(pl.col("bob").dt.date().alias("date"))
            
            df = df.with_columns([
                pl.col("date").str.to_date("%Y-%m-%d") if df.collect_schema()["date"] == pl.String else pl.col("date"),
                pl.col("symbol").cast(pl.String)
            ])
            
            if reference_cols is None:
                reference_cols = df.collect_schema().names()
            else:
                df = df.select(reference_cols)
            history_frames.append(df)
        
        spine = pl.concat(history_frames)
        
        # Join other daily tables
        numeric_cols = {
            "valuation": ["pe_ttm", "pb_mrq", "ps_ttm", "pcf_ttm_oper"],
            "mktvalue": ["tot_mv", "a_mv"],
            "basic": ["tclose", "turnrate", "ttl_shr", "circ_shr"],
            "adj_factor": ["adj_factor_fwd"]
        }
        
        for name, d_dir in self.daily_dirs.items():
            if name == "history_1d" or not d_dir.exists():
                continue
                
            logging.info(f"Merging {name} files...")
            files = list(d_dir.glob("*.csv")) + list(d_dir.glob("*.parquet"))
            if not files:
                continue
                
            supplement_frames = []
            reference_supp_cols = None
            for f in files:
                if f.suffix == ".csv":
                    df_lazy = pl.scan_csv(f, infer_schema_length=1000)
                else:
                    df_lazy = pl.scan_parquet(f)
                
                schema = df_lazy.collect_schema()
                df_cols = schema.names()
                
                if "trade_date" in df_cols:
                    dtype = schema["trade_date"]
                    if dtype == pl.String:
                        df_lazy = df_lazy.with_columns(pl.col("trade_date").str.slice(0, 10).alias("date"))
                    else:
                        df_lazy = df_lazy.with_columns(pl.col("trade_date").dt.date().alias("date"))
                
                df_lazy = df_lazy.with_columns([
                    pl.col("date").str.to_date("%Y-%m-%d") if df_lazy.collect_schema()["date"] == pl.String else pl.col("date"),
                    pl.col("symbol").cast(pl.String)
                ])
                
                # Cast numeric columns
                if name in numeric_cols:
                    cols_to_cast = [c for c in numeric_cols[name] if c in df_cols]
                    df_lazy = df_lazy.with_columns([pl.col(c).cast(pl.Float64) for c in cols_to_cast])
                    df_lazy = df_lazy.select(["date", "symbol"] + cols_to_cast)
                
                if reference_supp_cols is None:
                    reference_supp_cols = df_lazy.collect_schema().names()
                else:
                    df_lazy = df_lazy.select(reference_supp_cols)
                supplement_frames.append(df_lazy)
            
            combined_supplement = pl.concat(supplement_frames)
            spine = spine.join(combined_supplement, on=["date", "symbol"], how="left")
            
        return spine.sort("date")

    def _get_fundamentals_base(self) -> pl.LazyFrame:
        """Merge quarterly fundamentals into a single base table"""
        logging.info("Scanning fundamental files...")
        statement_frames = []
        for name, f_dir in self.fundamental_dirs.items():
            if not f_dir.exists():
                continue
            
            files = list(f_dir.glob("*.csv")) + list(f_dir.glob("*.parquet"))
            if not files:
                continue
                
            cat_frames = []
            reference_cat_cols = None
            for f in files:
                if f.suffix == ".csv":
                    df = pl.scan_csv(f, infer_schema_length=1000)
                else:
                    df = pl.scan_parquet(f)
                
                schema = df.collect_schema()
                df_cols = schema.names()
                
                # Cast non-key columns to Float64
                keys = ["symbol", "pub_date", "rpt_date", "rpt_type", "data_type"]
                non_key_cols = [c for c in df_cols if c not in keys]
                df = df.with_columns([pl.col(c).cast(pl.Float64) for c in non_key_cols])
                
                # Normalize date columns
                date_keys = ["pub_date", "rpt_date"]
                for dk in date_keys:
                    if dk in df_cols:
                        if schema[dk] == pl.String:
                            df = df.with_columns(pl.col(dk).str.to_date("%Y-%m-%d"))
                        elif schema[dk] != pl.Date:
                            df = df.with_columns(pl.col(dk).dt.date())
                
                # Basic cleaning: remove duplicates
                df = df.unique(subset=["symbol", "pub_date", "rpt_date"])
                
                if reference_cat_cols is None:
                    reference_cat_cols = df.collect_schema().names()
                else:
                    # Align columns: missing columns as nulls
                    curr_cols = df.collect_schema().names()
                    missing_cols = [c for c in reference_cat_cols if c not in curr_cols]
                    if missing_cols:
                        df = df.with_columns([pl.lit(None).cast(pl.Float64).alias(c) for c in missing_cols])
                    df = df.select(reference_cat_cols)
                    
                cat_frames.append(df)
            
            statement_frames.append(pl.concat(cat_frames))
            
        if not statement_frames:
            # Return an empty LazyFrame with basic structure if no data
            return pl.LazyFrame({
                "symbol": pl.Series([], dtype=pl.String),
                "pub_date": pl.Series([], dtype=pl.Date)
            })
            
        # Outer join all statements
        base = statement_frames[0]
        # Common keys for fundamental data
        keys = ["symbol", "pub_date", "rpt_date"]
        
        for next_df in statement_frames[1:]:
            # Identify overlapping columns that are NOT keys
            base_cols = set(base.collect_schema().names())
            next_cols = set(next_df.collect_schema().names())
            overlapping = (base_cols & next_cols) - set(keys)
            
            if overlapping:
                logging.info(f"Overlapping columns in fundamental join: {overlapping}")
                # For fundamentals, we might have 'rpt_type' or 'data_type' in multiple statements.
                # We can either drop them from next_df or let them be suffixed.
                # Here we drop them to keep only one copy.
                next_df = next_df.drop(list(overlapping))
            
            # Use modern full join with coalesce
            base = base.join(next_df, on=keys, how="full", coalesce=True)
            
        return base.sort("pub_date")

    def on_success(self):
        """Pipeline completion: generate quality report"""
        try:
            from src.pipelines.data_quality.reporter import QualityReporter
            reporter = QualityReporter(self.config)
            report_path = reporter.save_report()
            logging.info(f"Pipeline completed. Quality report: {report_path}")
        except Exception as e:
            logging.warning(f"Quality report failed: {e}")
        logging.info("Pipeline completed successfully.")
