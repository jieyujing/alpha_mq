"""
Qlib 数据转换器模块

提供三类转换器:
1. OhlcvConverter: 将 GM 日频行情转为 Qlib 兼容 CSV
2. FeatureConverter: 将估值/市值/基础指标合并为特征 CSV
3. PitConverter: 将财务报表转为严格 PIT 格式
"""
import os
import logging
import pandas as pd
from pathlib import Path
from typing import Optional, List
from core.symbol import SymbolAdapter


class OhlcvConverter:
    """
    将 GM history_1d Parquet 转为 Qlib 兼容 CSV 格式

    Qlib OHLCV 格式要求:
    - 文件名: {qlib_symbol}.csv (如 SH600000.csv)
    - 列: date, open, high, low, close, volume, amount, factor
    - date 格式: YYYY-MM-DD
    """

    GM_COLUMNS = ["symbol", "bob", "eob", "open", "high", "low", "close", "volume", "amount"]
    QLIB_COLUMNS = ["date", "open", "high", "low", "close", "volume", "amount", "factor"]

    def __init__(self, exports_dir: str, output_dir: str, adj_factor_dir: Optional[str] = None):
        self.exports_dir = Path(exports_dir)
        self.output_dir = Path(output_dir)
        self.adj_factor_dir = Path(adj_factor_dir) if adj_factor_dir else None
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def convert_symbol(self, gm_symbol: str) -> Optional[pd.DataFrame]:
        """转换单个标的的 OHLCV 数据"""
        parquet_path = self.exports_dir / f"{gm_symbol}.parquet"
        if not parquet_path.exists():
            logging.warning(f"Missing OHLCV data for {gm_symbol}")
            return None

        df = pd.read_parquet(parquet_path)
        if df.empty:
            return None

        # 列映射: bob -> date
        df["date"] = pd.to_datetime(df["bob"]).dt.strftime("%Y-%m-%d")

        # 合并复权因子 (默认为 1.0)
        df["factor"] = 1.0
        if self.adj_factor_dir:
            adj_path = self.adj_factor_dir / f"{gm_symbol}.csv"
            if adj_path.exists():
                adj_df = pd.read_csv(adj_path)
                if not adj_df.empty and "factor" in adj_df.columns:
                    adj_df["date"] = pd.to_datetime(adj_df["bob"]).dt.strftime("%Y-%m-%d")
                    df = df.drop(columns=["factor"])
                    df = df.merge(adj_df[["date", "factor"]], on="date", how="left")
                    df["factor"] = df["factor"].fillna(1.0)

        # 选择 Qlib 列
        result = df[self.QLIB_COLUMNS].copy()
        qlib_symbol = SymbolAdapter.to_qlib(gm_symbol)

        # 保存为 CSV
        output_path = self.output_dir / f"{qlib_symbol}.csv"
        result.to_csv(output_path, index=False)
        logging.info(f"Converted OHLCV: {gm_symbol} -> {qlib_symbol}")

        return result

    def convert_all(self) -> List[str]:
        """转换 exports 目录下所有标的"""
        converted = []
        for parquet_file in self.exports_dir.glob("*.parquet"):
            gm_symbol = parquet_file.stem
            result = self.convert_symbol(gm_symbol)
            if result is not None and not result.empty:
                converted.append(gm_symbol)
        return converted


class FeatureConverter:
    """
    将估值/市值/基础指标数据合并为 Qlib 特征 CSV

    合并 valuation, mktvalue, basic 到对应的 symbol CSV
    """

    FEATURE_DIRS = ["valuation", "mktvalue", "basic"]

    def __init__(self, exports_base: str, ohlcv_dir: str):
        self.exports_base = Path(exports_base)
        self.ohlcv_dir = Path(ohlcv_dir)

    def merge_features_for_symbol(self, gm_symbol: str) -> Optional[pd.DataFrame]:
        """合并单个标的的所有特征数据"""
        qlib_symbol = SymbolAdapter.to_qlib(gm_symbol)
        ohlcv_path = self.ohlcv_dir / f"{qlib_symbol}.csv"

        if not ohlcv_path.exists():
            return None

        base_df = pd.read_csv(ohlcv_path)
        merged = base_df.copy()

        for category in self.FEATURE_DIRS:
            cat_dir = self.exports_base / category
            gm_file = cat_dir / f"{gm_symbol}.csv"
            if not gm_file.exists():
                continue

            cat_df = pd.read_csv(gm_file)
            if cat_df.empty:
                continue

            # 标准化日期列
            if "bob" in cat_df.columns:
                cat_df["date"] = pd.to_datetime(cat_df["bob"]).dt.strftime("%Y-%m-%d")
            elif "trade_date" in cat_df.columns:
                cat_df["date"] = pd.to_datetime(cat_df["trade_date"]).dt.strftime("%Y-%m-%d")

            # 选择数值列合并
            numeric_cols = cat_df.select_dtypes(include=["number"]).columns.tolist()
            if "date" in cat_df.columns:
                merge_cols = ["date"] + [c for c in numeric_cols if c not in ["symbol", "date"]]
                merged = merged.merge(cat_df[merge_cols], on="date", how="left")

        # 保存合并后的 CSV
        merged.to_csv(ohlcv_path, index=False)
        logging.info(f"Merged features for {qlib_symbol}")

        return merged


class PitConverter:
    """
    将财务报表转为严格 PIT 格式 (Qlib dump_pit 兼容)

    PIT 格式要求:
    - date: 公告披露日期 (pub_date)
    - period: 报表截止日期 (rpt_date)
    - value: 指标值
    - 每个字段单独一个文件: {qlib_symbol}/{field_name}.data
    """

    FUNDAMENTAL_DIRS = ["fundamentals_balance", "fundamentals_income", "fundamentals_cashflow"]

    def __init__(self, exports_base: str, output_dir: str):
        self.exports_base = Path(exports_base)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def convert_symbol(self, gm_symbol: str) -> dict:
        """转换单个标的的财务数据"""
        qlib_symbol = SymbolAdapter.to_qlib(gm_symbol)
        symbol_dir = self.output_dir / qlib_symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)

        fields_written = {}

        for category in self.FUNDAMENTAL_DIRS:
            cat_dir = self.exports_base / category
            gm_file = cat_dir / f"{gm_symbol}.csv"

            if not gm_file.exists():
                continue

            df = pd.read_csv(gm_file)
            if df.empty:
                continue

            # 遍历所有数值字段
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            for field in numeric_cols:
                if field in ["pub_date", "rpt_date"]:
                    continue

                # 构建 PIT 格式: date(pub_date), period(rpt_date), value
                pit_df = pd.DataFrame({
                    "date": pd.to_datetime(df["pub_date"]).dt.strftime("%Y-%m-%d"),
                    "period": pd.to_datetime(df["rpt_date"]).dt.strftime("%Y-%m-%d"),
                    "value": df[field]
                }).dropna()

                if pit_df.empty:
                    continue

                # 保存为 .data 文件 (Qlib PIT 格式)
                pit_path = symbol_dir / f"{field}.data"
                pit_df.to_csv(pit_path, index=False)
                fields_written[field] = len(pit_df)

        if fields_written:
            logging.info(f"Converted PIT for {qlib_symbol}: {len(fields_written)} fields")

        return fields_written

    def convert_all(self) -> dict:
        """转换所有标的"""
        results = {}
        for category in self.FUNDAMENTAL_DIRS:
            cat_dir = self.exports_base / category
            for csv_file in cat_dir.glob("*.csv"):
                gm_symbol = csv_file.stem
                fields = self.convert_symbol(gm_symbol)
                if fields:
                    results[gm_symbol] = fields
        return results


class QlibIngestor:
    """
    Qlib 二进制入库编排层

    封装 Qlib 的 dump_bin 和 dump_pit 工具调用
    """

    def __init__(self, qlib_dir: str):
        self.qlib_dir = Path(qlib_dir)
        self.qlib_dir.mkdir(parents=True, exist_ok=True)

    def dump_bin(self, csv_path: str, include_fields: Optional[List[str]] = None) -> bool:
        """
        调用 Qlib dump_bin 将 OHLCV CSV 转为二进制格式

        Args:
            csv_path: CSV 文件所在目录
            include_fields: 需要包含的字段列表
        """
        import subprocess

        cmd = [
            "python", "-m", "qlib.utils.dump_bin",
            "--csv_path", csv_path,
            "--qlib_dir", str(self.qlib_dir),
            "--date_field", "date",
            "--symbol_field", "symbol"
        ]

        if include_fields:
            cmd.extend(["--include_fields", ",".join(include_fields)])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logging.info(f"dump_bin completed: {csv_path}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"dump_bin failed: {e.stderr}")
            return False

    def dump_pit(self, pit_dir: str) -> bool:
        """
        调用 Qlib dump_pit 将 PIT 数据转为二进制格式

        Args:
            pit_dir: PIT .data 文件所在目录
        """
        import subprocess

        cmd = [
            "python", "-m", "qlib.utils.dump_pit",
            "--pit_path", pit_dir,
            "--qlib_dir", str(self.qlib_dir)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logging.info(f"dump_pit completed: {pit_dir}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"dump_pit failed: {e.stderr}")
            return False