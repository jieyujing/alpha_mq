"""增量检测逻辑测试"""
import pytest
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass


# 先定义期望的数据类结构（测试将验证这些类存在）
def test_coverage_result_dataclass():
    """测试 CoverageResult 数据类定义"""
    from data_download.incremental import CoverageResult

    result = CoverageResult(
        covered=True,
        last_date=datetime(2025, 4, 22),
        gap_start=datetime(2025, 4, 23)
    )
    assert result.covered is True
    assert result.last_date == datetime(2025, 4, 22)


def test_symbol_gap_dataclass():
    """测试 SymbolGap 数据类定义"""
    from data_download.incremental import SymbolGap

    gap = SymbolGap(
        existing={"SHSE.600000", "SZSE.000001"},
        missing=["SHSE.600001"]
    )
    assert "SHSE.600000" in gap.existing
    assert "SHSE.600001" in gap.missing