# tests/pipelines/factor/test_alpha158_pipeline.py
"""Alpha158Pipeline unit tests — 测试因子生成（无过滤）"""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from pipelines.factor.alpha158_pipeline import Alpha158Pipeline


@pytest.fixture
def config(tmp_path):
    return {
        "pipeline": {
            "name": "Alpha158Pipeline",
            "stages": ["factor_compute", "label_compute", "export", "report"],
        },
        "data": {
            "qlib_csv": "data/qlib_output/ohlcv",
            "qlib_bin": str(tmp_path / "qlib_bin"),
            "instruments": "csi1000",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "extra_fields": ["pe_ttm"],
        },
        "labels": {
            "primary": "label_5d",
            "periods": [1, 5, 10, 20],
        },
        "output": {
            "parquet": str(tmp_path / "factor_pool.parquet"),
            "yaml": str(tmp_path / "factor_pool.yaml"),
            "report": str(tmp_path / "factor_report.md"),
        },
    }


def make_mock_factors(n_symbols=3, n_days=30):
    dates = pd.date_range("2020-01-01", periods=n_days, freq="B")
    symbols = [f"SH60000{i}" for i in range(n_symbols)]
    index = pd.MultiIndex.from_product([dates, symbols], names=["datetime", "instrument"])
    return pd.DataFrame({
        "KMID": np.random.randn(len(index)),
        "KLEN": np.random.randn(len(index)),
        "MA5": np.random.randn(len(index)),
    }, index=index)


def make_mock_labels(n_symbols=3, n_days=30):
    dates = pd.date_range("2020-01-01", periods=n_days, freq="B")
    symbols = [f"SH60000{i}" for i in range(n_symbols)]
    index = pd.MultiIndex.from_product([dates, symbols], names=["datetime", "instrument"])
    return {
        f"label_{p}d": pd.Series(np.random.randn(len(index)), index=index)
        for p in [1, 5, 10, 20]
    }


def test_pipeline_initialization(config):
    pipeline = Alpha158Pipeline(config)
    assert pipeline.stages == config["pipeline"]["stages"]
    assert pipeline.qlib_bin == config["data"]["qlib_bin"]


def test_stage_method_map():
    expected_map = {
        "merge_gm_data": "merge_gm_data",
        "ingest_bin": "ingest_bin",
        "factor_compute": "factor_compute",
        "data_quality_check": "data_quality_check",
        "label_compute": "label_compute",
        "export": "export",
        "report": "generate_report",
    }
    assert Alpha158Pipeline.STAGE_METHOD_MAP == expected_map


def test_export_saves_parquet_and_yaml(config, tmp_path):
    factors = make_mock_factors()
    labels = make_mock_labels()

    pipeline = Alpha158Pipeline(config)
    pipeline.factors_df = factors
    pipeline.labels_dict = labels

    pipeline.export()

    parquet_path = Path(config["output"]["parquet"])
    yaml_path = Path(config["output"]["yaml"])
    assert parquet_path.exists()
    assert yaml_path.exists()

    saved = pd.read_parquet(parquet_path)
    assert len(saved) == len(factors)
    for p in config["labels"]["periods"]:
        assert f"label_{p}d" in saved.columns


def test_generate_report(config):
    factors = make_mock_factors()
    labels = make_mock_labels()

    pipeline = Alpha158Pipeline(config)
    pipeline.factors_df = factors
    pipeline.labels_dict = labels

    pipeline.generate_report()

    report_path = Path(config["output"]["report"])
    assert report_path.exists()
    content = report_path.read_text()
    assert "# Alpha158 Factor Summary" in content
    assert "Factor Statistics" in content
    assert "Label Statistics" in content
