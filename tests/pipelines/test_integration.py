import pytest
import pandas as pd
import tempfile
from pathlib import Path
from pipelines import get_pipeline, PIPELINE_REGISTRY
from pipelines.data_ingest.csi1000_pipeline import CSI1000DataPipeline


class TestPipelineRegistry:
    def test_registry_has_csi1000(self):
        """测试注册表包含 CSI1000 管道"""
        assert "csi1000_data" in PIPELINE_REGISTRY

    def test_get_pipeline_returns_class(self):
        """测试 get_pipeline 返回正确的类"""
        pipeline_class = get_pipeline("csi1000_data")
        assert pipeline_class == CSI1000DataPipeline

    def test_get_unknown_pipeline_raises(self):
        """测试获取未知管道抛出异常"""
        with pytest.raises(ValueError):
            get_pipeline("unknown_pipeline")


class TestCSI1000DataPipelineIntegration:
    def test_pipeline_dry_run_clean_only(self):
        """测试 pipeline dry-run (仅 clean 阶段)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            exports_base = Path(tmpdir) / "exports"
            qlib_output = Path(tmpdir) / "qlib_output"
            qlib_bin = Path(tmpdir) / "qlib_bin"

            # 创建 mock 数据目录
            history_1d = exports_base / "history_1d"
            history_1d.mkdir(parents=True)

            fundamentals_balance = exports_base / "fundamentals_balance"
            fundamentals_balance.mkdir(parents=True)

            fundamentals_income = exports_base / "fundamentals_income"
            fundamentals_income.mkdir(parents=True)

            fundamentals_cashflow = exports_base / "fundamentals_cashflow"
            fundamentals_cashflow.mkdir(parents=True)

            # 创建 mock OHLCV 数据
            mock_ohlcv = pd.DataFrame({
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
            mock_ohlcv.to_parquet(history_1d / "SHSE.600000.parquet", index=False)

            # 创建 mock fundamentals 数据
            mock_fund = pd.DataFrame({
                "symbol": ["SHSE.600000"] * 2,
                "pub_date": ["2024-01-10", "2024-04-25"],
                "rpt_date": ["2023-12-31", "2024-03-31"],
                "ttl_ast": [100000, 110000],
                "net_prof": [5000, 6000]
            })
            mock_fund.to_csv(fundamentals_balance / "SHSE.600000.csv", index=False)
            mock_fund.to_csv(fundamentals_income / "SHSE.600000.csv", index=False)
            mock_fund.to_csv(fundamentals_cashflow / "SHSE.600000.csv", index=False)

            # 配置 pipeline
            config = {
                "pipeline": {"name": "csi1000_data", "stages": ["validate", "clean"]},
                "exports_base": str(exports_base),
                "qlib_output": str(qlib_output),
                "qlib_bin": str(qlib_bin)
            }

            # 运行 pipeline
            pipeline = CSI1000DataPipeline(config)
            pipeline.run()

            # 验证输出
            ohlcv_csv = qlib_output / "ohlcv" / "SH600000.csv"
            assert ohlcv_csv.exists()

            pit_data = qlib_output / "pit" / "SH600000" / "ttl_ast.data"
            assert pit_data.exists()

    def test_pipeline_validate_reports_missing_data(self):
        """测试 validate 阶段报告缺失数据"""
        with tempfile.TemporaryDirectory() as tmpdir:
            exports_base = Path(tmpdir) / "exports"
            qlib_output = Path(tmpdir) / "qlib_output"
            qlib_bin = Path(tmpdir) / "qlib_bin"

            # 不创建任何数据目录

            config = {
                "pipeline": {"name": "csi1000_data", "stages": ["validate"]},
                "exports_base": str(exports_base),
                "qlib_output": str(qlib_output),
                "qlib_bin": str(qlib_bin)
            }

            pipeline = CSI1000DataPipeline(config)
            pipeline.setup()
            errors = pipeline.validate()

            assert len(errors) > 0
            assert any("Missing OHLCV" in e for e in errors)