import pytest
import pandas as pd
import tempfile
from pathlib import Path
from pipelines.data_ingest.qlib_converter import OhlcvConverter, FeatureConverter, PitConverter, QlibIngestor


class TestOhlcvConverter:
    def test_gm_to_qlib_symbol_conversion(self):
        """测试 GM symbol 转 Qlib symbol"""
        from core.symbol import SymbolAdapter
        assert SymbolAdapter.to_qlib("SHSE.600000") == "SH600000"

    def test_ohlcv_conversion_with_mock_data(self):
        """测试 OHLCV 转换"""
        with tempfile.TemporaryDirectory() as tmpdir:
            exports_dir = Path(tmpdir) / "exports"
            exports_dir.mkdir()
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            # 创建 mock GM 数据
            mock_df = pd.DataFrame({
                "symbol": ["SHSE.600000"] * 3,
                "bob": ["2024-01-01 09:00:00", "2024-01-02 09:00:00", "2024-01-03 09:00:00"],
                "eob": ["2024-01-01 15:00:00", "2024-01-02 15:00:00", "2024-01-03 15:00:00"],
                "open": [10.0, 10.5, 11.0],
                "high": [10.5, 11.0, 11.5],
                "low": [9.8, 10.2, 10.8],
                "close": [10.2, 10.8, 11.2],
                "volume": [1000000, 1100000, 1200000],
                "amount": [10000000, 11000000, 12000000]
            })
            mock_df.to_parquet(exports_dir / "SHSE.600000.parquet", index=False)

            converter = OhlcvConverter(str(exports_dir), str(output_dir))
            result = converter.convert_symbol("SHSE.600000")

            assert result is not None
            assert "date" in result.columns
            assert "SH600000.csv" in [f.name for f in output_dir.glob("*.csv")]

    def test_missing_symbol_returns_none(self):
        """测试缺失标的返回 None"""
        with tempfile.TemporaryDirectory() as tmpdir:
            exports_dir = Path(tmpdir) / "exports"
            exports_dir.mkdir()
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            converter = OhlcvConverter(str(exports_dir), str(output_dir))
            result = converter.convert_symbol("SHSE.999999")

            assert result is None


class TestPitConverter:
    def test_pit_conversion_with_mock_data(self):
        """测试 PIT 财务数据转换"""
        with tempfile.TemporaryDirectory() as tmpdir:
            exports_base = Path(tmpdir) / "exports"
            exports_base.mkdir()
            output_dir = Path(tmpdir) / "pit_output"
            output_dir.mkdir()

            # 创建 mock fundamentals 数据
            fund_dir = exports_base / "fundamentals_balance"
            fund_dir.mkdir()

            mock_df = pd.DataFrame({
                "symbol": ["SHSE.600000"] * 3,
                "pub_date": ["2024-01-10", "2024-04-25", "2024-08-20"],
                "rpt_date": ["2023-12-31", "2024-03-31", "2024-06-30"],
                "ttl_ast": [100000, 110000, 120000],
                "ttl_liab": [50000, 55000, 60000]
            })
            mock_df.to_csv(fund_dir / "SHSE.600000.csv", index=False)

            converter = PitConverter(str(exports_base), str(output_dir))
            fields = converter.convert_symbol("SHSE.600000")

            assert "ttl_ast" in fields
            assert "ttl_liab" in fields

            # 验证 PIT 格式文件
            pit_file = output_dir / "SH600000" / "ttl_ast.data"
            assert pit_file.exists()

            pit_df = pd.read_csv(pit_file)
            assert "date" in pit_df.columns
            assert "period" in pit_df.columns
            assert "value" in pit_df.columns


class TestQlibIngestor:
    def test_ingestor_init(self):
        """测试 Ingestor 初始化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            qlib_dir = Path(tmpdir) / "qlib_bin"
            ingestor = QlibIngestor(str(qlib_dir))
            assert qlib_dir.exists()