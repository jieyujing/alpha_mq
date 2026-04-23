# tests/pipelines/factor/test_integration.py
"""AlphaFactorPipeline 集成测试 — mock Qlib 依赖。"""
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch
from pathlib import Path
from pipelines.factor.alpha_pipeline import AlphaFactorPipeline


def make_mock_data(n_symbols=3, n_days=60):
    """生成 mock 因子和价格数据。"""
    dates = pd.date_range("2020-01-01", periods=n_days, freq="B")
    symbols = [f"SH60000{i}" for i in range(n_symbols)]
    index = pd.MultiIndex.from_product([dates, symbols],
                                        names=["datetime", "instrument"])
    n = len(index)

    factors = pd.DataFrame({
        f"factor_{j}": np.random.randn(n) * 0.1 + j * 0.01
        for j in range(5)
    }, index=index)

    close = pd.DataFrame({
        "close": np.random.uniform(10, 100, n),
    }, index=index)

    return factors, close


@pytest.fixture
def mock_config(tmp_path):
    """使用宽松过滤阈值，确保大多数因子能保留。"""
    return {
        "pipeline": {
            "name": "AlphaFactorPipeline",
            "stages": ["factor_compute", "label_compute", "filter", "export", "report"],
        },
        "data": {
            "qlib_csv": "data/qlib_output/ohlcv",
            "qlib_bin": str(tmp_path / "qlib_bin"),
            "instruments": "csi1000",
            "start_date": "2020-01-01",
            "end_date": "2020-06-30",
        },
        "labels": {
            "primary": "label_5d",
            "periods": [1, 5, 10, 20],
        },
        "filter": {
            "drop_missing_label": {},
            "drop_high_missing": {"threshold": 0.9},
            "drop_high_inf": {"threshold": 0.5},
            "drop_low_variance": {
                "variance_threshold": 1e-12,
                "unique_ratio_threshold": 0.001,
            },
            "factor_quality": {
                "min_abs_ic_mean": 0.0,
                "min_abs_icir": 0.0,
                "min_abs_monotonicity": 0.0,
                "max_sign_flip_ratio": 1.0,
            },
        },
        "output": {
            "parquet": str(tmp_path / "factor_pool.parquet"),
            "yaml": str(tmp_path / "factor_pool.yaml"),
            "report": str(tmp_path / "factor_report.md"),
        },
    }


def test_pipeline_dry_run_with_report(mock_config):
    """全链路 mock 测试：因子计算 -> 标签 -> 过滤 -> 导出 -> 报告。"""
    factors_df, close_df = make_mock_data()

    pipeline = AlphaFactorPipeline(mock_config)

    # 直接注入 mock 数据（绕过 factor_compute 和 label_compute）
    pipeline.factors_df = factors_df.copy()

    # 构造 label dict
    periods = mock_config["labels"]["periods"]
    labels = {}
    for period in periods:
        shifted = close_df.groupby(level="instrument")["close"].shift(-period)
        labels[f"label_{period}d"] = shifted / close_df["close"] - 1
    pipeline.labels_dict = labels

    pipeline.run_filter()
    pipeline.export()
    pipeline.generate_report()

    # 验证过滤结果
    assert pipeline.filtered_X is not None
    assert pipeline.filtered_y is not None
    assert len(pipeline.filtered_X) > 0

    # 验证 Parquet 文件
    parquet_path = Path(mock_config["output"]["parquet"])
    assert parquet_path.exists()
    saved = pd.read_parquet(parquet_path)
    assert len(saved) > 0

    # 验证所有 label 列存在
    for period in periods:
        assert f"label_{period}d" in saved.columns

    # 验证 YAML 文件
    yaml_path = Path(mock_config["output"]["yaml"])
    assert yaml_path.exists()

    # 验证报告文件
    report_path = Path(mock_config["output"]["report"])
    assert report_path.exists()
    content = report_path.read_text()
    assert "# Factor Quality Report" in content
