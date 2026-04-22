"""
增量检测逻辑

提供时间覆盖和标的覆盖检测函数。
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Set
import pandas as pd


@dataclass
class CoverageResult:
    """时间覆盖检测结果"""
    covered: bool           # 是否已覆盖到结束日期
    last_date: datetime     # 已有数据最新日期
    gap_start: datetime     # 缺口起始日期 (若 covered=False)


@dataclass
class SymbolGap:
    """标的覆盖检测结果"""
    existing: Set[str]      # 已有标的集合
    missing: List[str]      # 缺失标的列表