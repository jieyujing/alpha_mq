"""
Parquet 数据合并模块

将 data/exports 下的所有数据类别合并为统一的 Parquet 文件:
- 日频行情 + 复权因子 + 估值 + 市值 + 基础指标 -> 单文件宽表
- 财务报表 -> 独立 Parquet 文件
"""
import logging
import pandas as pd
from pathlib import Path
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed


class ParquetIngestor:
    """
    将 exports 数据合并为 Parquet 宽表

    输出结构:
    - data/parquet/daily/{symbol}.parquet    # OHLCV + 复权 + 估值 + 市值 + 基础指标
    - data/parquet/fundamentals/{symbol}.parquet  # 利润表 + 资产负债表 + 现金流
    """

    DAILY_OUTPUT_FIELDS = [
        "date", "open", "high", "low", "close", "volume", "amount",
        "pre_close", "factor",
        "pe_ttm", "pb_mrq", "ps_ttm", "pcf_ttm_oper",
        "tot_mv", "a_mv",
        "tclose", "turnrate", "ttl_shr", "circ_shr",
    ]

    def __init__(self, exports_base: str, output_dir: str, max_workers: int = 8):
        self.exports_base = Path(exports_base)
        self.output_dir = Path(output_dir)
        self.daily_dir = self.output_dir / "daily"
        self.fund_dir = self.output_dir / "fundamentals"
        self.max_workers = max_workers

    def setup(self):
        self.daily_dir.mkdir(parents=True, exist_ok=True)
        self.fund_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"Parquet ingestor setup: daily={self.daily_dir}, fundamentals={self.fund_dir}")

    @staticmethod
    def _load_file(path: Path, **kwargs) -> pd.DataFrame | None:
        """Load CSV or Parquet based on extension."""
        if not path.exists():
            return None
        if path.suffix == ".parquet":
            return pd.read_parquet(path, **kwargs)
        return pd.read_csv(path, **kwargs)

    def merge_daily_for_symbol(self, symbol: str) -> bool:
        """合并单只股票的日频数据为宽表"""
        try:
            # 1. 加载 history_1d (主表) - 支持 csv 或 parquet
            history_path = self.exports_base / "history_1d" / f"{symbol}.parquet"
            if not history_path.exists():
                history_path = self.exports_base / "history_1d" / f"{symbol}.csv"
            history = self._load_file(history_path)
            if history is None or history.empty:
                return False
            history["date"] = pd.to_datetime(history["bob"]).dt.strftime("%Y-%m-%d")

            # 2. 合并复权因子
            adj_path = self.exports_base / "adj_factor" / f"{symbol}.csv"
            if adj_path.exists():
                adj = pd.read_csv(adj_path)
                adj["date"] = pd.to_datetime(adj["trade_date"]).dt.strftime("%Y-%m-%d")
                history = history.merge(
                    adj[["date", "adj_factor_fwd"]], on="date", how="left"
                )
                history["factor"] = history.get("adj_factor_fwd", 1.0).fillna(1.0)
            else:
                history["factor"] = 1.0

            # 3. 合并 valuation
            val_path = self.exports_base / "valuation" / f"{symbol}.csv"
            if val_path.exists():
                val = pd.read_csv(val_path, encoding="gbk")
                val["date"] = pd.to_datetime(val["trade_date"]).dt.strftime("%Y-%m-%d")
                merge_cols = ["date"] + [c for c in ["pe_ttm", "pb_mrq", "ps_ttm", "pcf_ttm_oper"] if c in val.columns]
                history = history.merge(val[merge_cols], on="date", how="left")

            # 4. 合并 mktvalue
            mv_path = self.exports_base / "mktvalue" / f"{symbol}.csv"
            if mv_path.exists():
                mv = pd.read_csv(mv_path, encoding="gbk")
                mv["date"] = pd.to_datetime(mv["trade_date"]).dt.strftime("%Y-%m-%d")
                merge_cols = ["date"] + [c for c in ["tot_mv", "a_mv"] if c in mv.columns]
                history = history.merge(mv[merge_cols], on="date", how="left")

            # 5. 合并 basic
            basic_path = self.exports_base / "basic" / f"{symbol}.csv"
            if basic_path.exists():
                basic = pd.read_csv(basic_path, encoding="gbk")
                basic["date"] = pd.to_datetime(basic["trade_date"]).dt.strftime("%Y-%m-%d")
                merge_cols = ["date"] + [c for c in ["tclose", "turnrate", "ttl_shr", "circ_shr"] if c in basic.columns]
                history = history.merge(basic[merge_cols], on="date", how="left")

            # 6. 前值填充：将季度/不定期发布的数据对齐到每个交易日
            ffill_cols = [c for c in self.DAILY_OUTPUT_FIELDS if c not in (
                "date", "open", "high", "low", "close", "volume", "amount", "pre_close"
            )]
            for col in ffill_cols:
                if col in history.columns:
                    history[col] = history[col].ffill()

            # 7. 选择最终列并去重排序
            available = [c for c in self.DAILY_OUTPUT_FIELDS if c in history.columns]
            result = history[available].copy()
            result = result.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)

            # 7. 写 Parquet
            out_path = self.daily_dir / f"{symbol}.parquet"
            result.to_parquet(out_path, index=False)
            return True

        except Exception as e:
            logging.warning(f"Error merging daily for {symbol}: {e}")
            return False

    def merge_fundamentals_for_symbol(self, symbol: str) -> bool:
        """合并单只股票的三大财务报表"""
        try:
            frames = []
            for cat in ["fundamentals_income", "fundamentals_balance", "fundamentals_cashflow"]:
                cat_path = self.exports_base / cat / f"{symbol}.csv"
                if cat_path.exists():
                    df = pd.read_csv(cat_path)
                    if not df.empty:
                        # Tag each row with its source category
                        df["_source"] = cat
                        frames.append(df)

            if not frames:
                return False

            # Concatenate all tables vertically (they share rpt_date/pub_date but different fields)
            merged = pd.concat(frames, ignore_index=True)
            merged = merged.drop_duplicates(subset=["symbol", "pub_date", "rpt_date", "_source"])

            out_path = self.fund_dir / f"{symbol}.parquet"
            merged.to_parquet(out_path, index=False)
            return True

        except Exception as e:
            logging.warning(f"Error merging fundamentals for {symbol}: {e}")
            return False

    def process_all(self, symbols: List[str]) -> dict:
        """并行处理所有标的"""
        stats = {"daily_ok": 0, "daily_fail": 0, "fund_ok": 0, "fund_fail": 0}

        # 并行合并日频数据
        logging.info(f"Merging daily data for {len(symbols)} symbols...")
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.merge_daily_for_symbol, s): s for s in symbols}
            for i, future in enumerate(as_completed(futures)):
                if future.result():
                    stats["daily_ok"] += 1
                else:
                    stats["daily_fail"] += 1
                if (i + 1) % 100 == 0:
                    logging.info(f"  Daily: [{i + 1}/{len(symbols)}] processed")

        # 并行合并财务数据
        logging.info(f"Merging fundamentals for {len(symbols)} symbols...")
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.merge_fundamentals_for_symbol, s): s for s in symbols}
            for i, future in enumerate(as_completed(futures)):
                if future.result():
                    stats["fund_ok"] += 1
                else:
                    stats["fund_fail"] += 1
                if (i + 1) % 100 == 0:
                    logging.info(f"  Fundamentals: [{i + 1}/{len(symbols)}] processed")

        logging.info(f"Parquet merge complete: {stats}")
        return stats
