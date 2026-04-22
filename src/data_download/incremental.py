"""
增量检测逻辑

提供时间覆盖和标的覆盖检测函数。
"""
import glob
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Set

import pandas as pd


@dataclass
class CoverageResult:
    """时间覆盖检测结果"""
    covered: bool               # 是否已覆盖到结束日期
    last_date: Optional[datetime]   # 已有数据最新日期 (无数据时为 None)
    gap_start: Optional[datetime]   # 缺口起始日期 (若 covered=False，无数据时为 None)


@dataclass
class SymbolGap:
    """标的覆盖检测结果"""
    existing: Set[str]      # 已有标的集合
    missing: List[str]      # 缺失标的列表


def check_time_coverage(file_path: Path, end_date: datetime, time_col: str = "bob") -> CoverageResult:
    """
    检查文件内数据是否已覆盖到请求的结束日期

    Args:
        file_path: 数据文件路径 (.parquet 或 .csv)
        end_date: 请求的结束日期
        time_col: 时间列名称 (默认 "bob")

    Returns:
        CoverageResult: 覆盖检测结果
    """
    if not file_path.exists():
        return CoverageResult(covered=False, last_date=None, gap_start=None)

    try:
        # 根据文件类型读取
        if file_path.suffix == ".parquet":
            df = pd.read_parquet(file_path, columns=[time_col])
        elif file_path.suffix == ".csv":
            df = pd.read_csv(file_path, usecols=[time_col])
        else:
            return CoverageResult(covered=False, last_date=None, gap_start=None)

        if df.empty:
            return CoverageResult(covered=False, last_date=None, gap_start=None)

        # 解析时间列
        dates = pd.to_datetime(df[time_col])
        last_date = dates.max().to_pydatetime()

        # 判断是否覆盖
        if last_date >= end_date:
            return CoverageResult(covered=True, last_date=last_date, gap_start=None)
        else:
            # 缺口起始日期 = last_date + 1 天
            gap_start = last_date + timedelta(days=1)
            return CoverageResult(covered=False, last_date=last_date, gap_start=gap_start)

    except Exception as e:
        logging.warning(f"check_time_coverage failed for {file_path}: {e}")
        return CoverageResult(covered=False, last_date=None, gap_start=None)


def check_symbol_coverage(category_dir: Path, target_pool: List[str],
                          file_format: str = "parquet") -> SymbolGap:
    """
    检查目录下缺失的标的

    Args:
        category_dir: 数据类别目录
        target_pool: 目标标的列表
        file_format: 文件格式 (parquet/csv)

    Returns:
        SymbolGap: 标的覆盖检测结果
    """
    if not category_dir.exists():
        return SymbolGap(existing=set(), missing=list(target_pool))

    # 扫描已有文件
    pattern = str(category_dir / f"*.{file_format}")
    files = glob.glob(pattern)

    # 提取已有标的
    existing = {Path(f).stem for f in files}

    # 计算缺失标的
    missing = [s for s in target_pool if s not in existing]

    return SymbolGap(existing=existing, missing=missing)