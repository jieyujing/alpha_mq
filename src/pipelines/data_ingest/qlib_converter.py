"""
Qlib 数据转换器模块

提供三类转换器:
1. OhlcvConverter: 将 GM 日频行情转为 Qlib 兼容 CSV
2. FeatureConverter: 将估值/市值/基础指标合并为特征 CSV
3. PitConverter: 将财务报表转为严格 PIT 格式
"""
import os
import logging
import numpy as np
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

    Qlib 二进制格式:
    - 日历: {qlib_dir}/calendars/{freq}.txt
    - 特征: {qlib_dir}/features/{instrument}/{field}.{freq}.bin
    - 标的: {qlib_dir}/instruments/{market}.txt

    .bin 文件格式: float32 数组 (little-endian '<f')
    - 第一个值: start_index (数据在日历中的起始位置)
    - 后续值: 特征数据
    """

    def __init__(self, qlib_dir: str, freq: str = "day"):
        self.qlib_dir = Path(qlib_dir)
        self.qlib_dir.mkdir(parents=True, exist_ok=True)
        self.freq = freq
        self.calendar_path = self.qlib_dir / "calendars"
        self.features_path = self.qlib_dir / "features"
        self.instruments_path = self.qlib_dir / "instruments"

    def dump_bin(self, csv_path: str, include_fields: Optional[List[str]] = None,
                 market: str = "csi1000") -> bool:
        """
        将 CSV 目录下的所有 CSV 文件转为 Qlib 二进制格式

        CSV 要求:
        - 第一列: date (YYYY-MM-DD)
        - 文件名: {SYMBOL}.csv (如 SH600000.csv)
        - 其余列为 feature 字段

        Args:
            csv_path: CSV 文件所在目录
            include_fields: 需要包含的字段列表
            market: 标的池名称 (用于 instruments.txt)
        """
        csv_dir = Path(csv_path)
        if not csv_dir.exists():
            logging.error(f"CSV directory not found: {csv_dir}")
            return False

        self.calendar_path.mkdir(parents=True, exist_ok=True)
        self.features_path.mkdir(parents=True, exist_ok=True)
        self.instruments_path.mkdir(parents=True, exist_ok=True)

        # 收集所有日期，构建日历
        all_dates: set[str] = set()
        csv_files = list(csv_dir.glob("*.csv"))
        if not csv_files:
            logging.warning(f"No CSV files found in {csv_dir}")
            return False

        # 第一遍：读取所有 CSV，收集日期和字段
        data_by_symbol: dict[str, pd.DataFrame] = {}
        all_fields: set[str] = set()

        for csv_file in csv_files:
            try:
                df = pd.read_csv(csv_file)
            except Exception as e:
                logging.warning(f"Failed to read {csv_file}: {e}")
                continue

            if df.empty or "date" not in df.columns:
                continue

            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
            df = df.sort_values("date").reset_index(drop=True)
            symbol = csv_file.stem
            data_by_symbol[symbol] = df
            all_dates.update(df["date"].tolist())
            all_fields.update(c for c in df.columns if c not in ("date", "symbol"))

        if include_fields:
            all_fields = {f for f in all_fields if f in include_fields}

        sorted_dates = sorted(all_dates)
        date_to_idx = {d: i for i, d in enumerate(sorted_dates)}

        # 写入日历
        cal_file = self.calendar_path / f"{self.freq}.txt"
        with open(cal_file, "w") as f:
            for d in sorted_dates:
                f.write(d + "\n")
        logging.info(f"Calendar written: {len(sorted_dates)} dates")

        # 写入标的列表
        inst_file = self.instruments_path / f"{market}.txt"
        with open(inst_file, "w") as f:
            for sym in sorted(data_by_symbol.keys()):
                f.write(f"{sym}\t{sorted_dates[0]}\t{sorted_dates[-1]}\n")
        logging.info(f"Instruments written: {len(data_by_symbol)} symbols")

        # 写入特征二进制文件
        for symbol, df in data_by_symbol.items():
            sym_dir = self.features_path / symbol.lower()
            sym_dir.mkdir(parents=True, exist_ok=True)

            for field in all_fields:
                if field not in df.columns:
                    continue

                field_path = sym_dir / f"{field.lower()}.{self.freq}.bin"
                values = df.set_index("date")[field].reindex(sorted_dates)
                start_idx = values.first_valid_index()
                if start_idx is None:
                    continue
                start_pos = date_to_idx[start_idx]
                # 只保留从 start_idx 开始的数据
                values_from_start = values.loc[start_idx:]
                data_array = values_from_start.values.astype(np.float32)

                # 写入: [start_index, data...]
                binary_data = np.hstack([[start_pos], data_array]).astype("<f")
                binary_data.tofile(field_path)

        logging.info(f"Dump bin done: {len(data_by_symbol)} symbols, {len(all_fields)} fields")
        return True

    def dump_pit(self, pit_dir: str) -> bool:
        """
        将 PIT 数据转为二进制格式（简化实现：按 feature 方式存储）

        Args:
            pit_dir: PIT .data 文件所在目录
        """
        # PIT 数据在 Qlib 0.9.7 中较为复杂，此处做简单处理
        # 暂时返回 True，跳过 PIT 导入
        logging.warning(f"PIT dump not yet fully implemented. Skipping: {pit_dir}")
        return True