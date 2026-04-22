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


import tempfile
import os
import pandas as pd


class TestCheckTimeCoverage:
    """时间覆盖检测测试"""

    def test_file_not_exists(self):
        """文件不存在时返回 covered=False"""
        from data_download.incremental import check_time_coverage

        end_date = datetime(2025, 4, 22)
        result = check_time_coverage(Path("/nonexistent/file.parquet"), end_date)

        assert result.covered is False
        assert result.last_date is None
        assert result.gap_start is None

    def test_parquet_covered(self):
        """数据已覆盖到结束日期"""
        from data_download.incremental import check_time_coverage

        # 创建临时 parquet 文件
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.parquet"
            df = pd.DataFrame({
                "bob": pd.date_range("2025-01-01", "2025-04-22", freq="D")
            })
            df.to_parquet(file_path)

            end_date = datetime(2025, 4, 22)
            result = check_time_coverage(file_path, end_date)

            assert result.covered is True
            assert result.last_date == datetime(2025, 4, 22)

    def test_parquet_has_gap(self):
        """数据有缺口，未覆盖到结束日期"""
        from data_download.incremental import check_time_coverage

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.parquet"
            df = pd.DataFrame({
                "bob": pd.date_range("2025-01-01", "2025-03-15", freq="D")
            })
            df.to_parquet(file_path)

            end_date = datetime(2025, 4, 22)
            result = check_time_coverage(file_path, end_date)

            assert result.covered is False
            assert result.last_date == datetime(2025, 3, 15)
            assert result.gap_start == datetime(2025, 3, 16)  # last_date + 1 day

    def test_csv_covered(self):
        """CSV 文件已覆盖"""
        from data_download.incremental import check_time_coverage

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.csv"
            df = pd.DataFrame({
                "bob": pd.date_range("2025-01-01", "2025-04-22", freq="D")
            })
            df.to_csv(file_path, index=False)

            end_date = datetime(2025, 4, 22)
            result = check_time_coverage(file_path, end_date)

            assert result.covered is True


class TestCheckSymbolCoverage:
    """标的覆盖检测测试"""

    def test_dir_not_exists(self):
        """目录不存在时返回全部缺失"""
        from data_download.incremental import check_symbol_coverage

        target_pool = ["SHSE.600000", "SHSE.600001", "SZSE.000001"]
        result = check_symbol_coverage(Path("/nonexistent/dir"), target_pool)

        assert result.existing == set()
        assert result.missing == target_pool

    def test_partial_missing(self):
        """部分标的缺失"""
        from data_download.incremental import check_symbol_coverage

        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建部分文件
            Path(tmpdir, "SHSE.600000.parquet").touch()
            Path(tmpdir, "SZSE.000001.parquet").touch()

            target_pool = ["SHSE.600000", "SHSE.600001", "SZSE.000001"]
            result = check_symbol_coverage(Path(tmpdir), target_pool)

            assert result.existing == {"SHSE.600000", "SZSE.000001"}
            assert result.missing == ["SHSE.600001"]

    def test_all_covered(self):
        """全部标的已存在"""
        from data_download.incremental import check_symbol_coverage

        with tempfile.TemporaryDirectory() as tmpdir:
            for symbol in ["SHSE.600000", "SHSE.600001", "SZSE.000001"]:
                Path(tmpdir, f"{symbol}.parquet").touch()

            target_pool = ["SHSE.600000", "SHSE.600001", "SZSE.000001"]
            result = check_symbol_coverage(Path(tmpdir), target_pool)

            assert result.existing == set(target_pool)
            assert result.missing == []

    def test_csv_format(self):
        """CSV 格式文件检测"""
        from data_download.incremental import check_symbol_coverage

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "SHSE.600000.csv").touch()

            target_pool = ["SHSE.600000", "SHSE.600001"]
            result = check_symbol_coverage(Path(tmpdir), target_pool, file_format="csv")

            assert "SHSE.600000" in result.existing
            assert result.missing == ["SHSE.600001"]