# src/pipelines/data_quality/checks.py
"""
数据质量检查函数
"""
from pathlib import Path
from typing import List, Optional
import pandas as pd
import glob


def check_ohlcv_coverage(data_dir: Path) -> dict:
    """
    检查 OHLCV 数据覆盖情况

    Returns:
        dict: symbol_count, min_date, max_date
    """
    if not data_dir.exists():
        return {"symbol_count": 0, "min_date": None, "max_date": None}

    files = glob.glob(str(data_dir / "*.csv")) + glob.glob(str(data_dir / "*.parquet"))

    if not files:
        return {"symbol_count": 0, "min_date": None, "max_date": None}

    min_dates = []
    max_dates = []

    for f in files:
        try:
            if f.endswith(".parquet"):
                df = pd.read_parquet(f)
            else:
                df = pd.read_csv(f)

            if "date" in df.columns:
                dates = pd.to_datetime(df["date"])
            elif "bob" in df.columns:
                dates = pd.to_datetime(df["bob"])
            else:
                continue

            min_dates.append(dates.min().strftime("%Y-%m-%d"))
            max_dates.append(dates.max().strftime("%Y-%m-%d"))
        except Exception:
            continue

    return {
        "symbol_count": len(files),
        "min_date": min(min_dates) if min_dates else None,
        "max_date": max(max_dates) if max_dates else None,
    }


def check_missing_values(file_path: Path, columns: List[str]) -> dict:
    """
    检查指定列的缺失值占比

    Returns:
        dict: {col_missing_pct: float}
    """
    try:
        if file_path.suffix == ".parquet":
            df = pd.read_parquet(file_path)
        else:
            df = pd.read_csv(file_path)

        total_rows = len(df)
        if total_rows == 0:
            return {f"{col}_missing_pct": 0.0 for col in columns}

        result = {}
        for col in columns:
            if col in df.columns:
                missing = df[col].isna().sum()
                result[f"{col}_missing_pct"] = round(missing / total_rows * 100, 2)
            else:
                result[f"{col}_missing_pct"] = 100.0

        return result
    except Exception:
        return {f"{col}_missing_pct": 100.0 for col in columns}


def check_duplicates(file_path: Path, subset_cols: List[str]) -> dict:
    """
    检查重复行数量

    Returns:
        dict: {duplicate_count: int}
    """
    try:
        if file_path.suffix == ".parquet":
            df = pd.read_parquet(file_path)
        else:
            df = pd.read_csv(file_path)

        if not all(col in df.columns for col in subset_cols):
            return {"duplicate_count": 0}

        duplicates = df.duplicated(subset=subset_cols).sum()
        return {"duplicate_count": int(duplicates)}
    except Exception:
        return {"duplicate_count": 0}