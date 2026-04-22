# tests/pipelines/data_quality/test_checks.py
"""数据检查函数测试"""
import pytest
import tempfile
import pandas as pd
from pathlib import Path


class TestCheckOhlcv:
    """OHLCV 检查测试"""

    def test_check_ohlcv_coverage_empty_dir(self):
        """空目录返回空结果"""
        from pipelines.data_quality.checks import check_ohlcv_coverage

        with tempfile.TemporaryDirectory() as tmpdir:
            result = check_ohlcv_coverage(Path(tmpdir))

            assert result["symbol_count"] == 0
            assert result["min_date"] is None
            assert result["max_date"] is None

    def test_check_ohlcv_coverage_with_data(self):
        """有数据时返回正确统计"""
        from pipelines.data_quality.checks import check_ohlcv_coverage

        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试数据
            df = pd.DataFrame({
                "date": pd.date_range("2025-01-01", "2025-04-22", freq="D"),
                "open": [10.0] * 112,
                "high": [11.0] * 112,
                "low": [9.0] * 112,
                "close": [10.5] * 112,
                "volume": [1000] * 112,
            })
            df.to_csv(Path(tmpdir) / "SHSE.600000.csv", index=False)

            result = check_ohlcv_coverage(Path(tmpdir))

            assert result["symbol_count"] == 1
            assert result["min_date"] == "2025-01-01"
            assert result["max_date"] == "2025-04-22"

    def test_check_missing_values(self):
        """缺失值检查"""
        from pipelines.data_quality.checks import check_missing_values

        with tempfile.TemporaryDirectory() as tmpdir:
            df = pd.DataFrame({
                "date": ["2025-01-01", "2025-01-02", "2025-01-03"],
                "close": [10.0, None, 11.0],
                "volume": [1000, 2000, None],
            })
            df.to_csv(Path(tmpdir) / "test.csv", index=False)

            result = check_missing_values(Path(tmpdir) / "test.csv", ["close", "volume"])

            assert result["close_missing_pct"] == 33.33
            assert result["volume_missing_pct"] == 33.33

    def test_check_duplicates(self):
        """重复行检查"""
        from pipelines.data_quality.checks import check_duplicates

        with tempfile.TemporaryDirectory() as tmpdir:
            df = pd.DataFrame({
                "date": ["2025-01-01", "2025-01-01", "2025-01-02"],
                "close": [10.0, 10.0, 11.0],
            })
            df.to_csv(Path(tmpdir) / "test.csv", index=False)

            result = check_duplicates(Path(tmpdir) / "test.csv", ["date"])

            assert result["duplicate_count"] == 1