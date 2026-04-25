# tests/pipelines/factor/test_alpha_pipeline.py
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock
from pipelines.factor.alpha_pipeline import AlphaFactorPipeline


@pytest.fixture
def config():
    return {
        "pipeline": {
            "name": "AlphaFactorPipeline",
            "stages": ["ingest_bin", "factor_compute", "label_compute", "filter", "export"],
        },
        "data": {
            "qlib_csv": "data/qlib_output/ohlcv",
            "qlib_bin": "data/qlib_bin",
            "instruments": "csi1000",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
        },
        "labels": {
            "primary": "label_5d",
            "periods": [1, 5, 10, 20],
        },
        "filter": {
            "drop_missing_label": {},
            "drop_high_missing": {"threshold": 0.3},
            "drop_high_inf": {"threshold": 0.01},
            "drop_low_variance": {
                "variance_threshold": 1e-8,
                "unique_ratio_threshold": 0.01,
            },
            "factor_quality": {
                "min_abs_ic_mean": 0.005,
                "min_abs_icir": 0.1,
                "min_abs_monotonicity": 0.05,
                "max_sign_flip_ratio": 0.45,
            },
        },
        "output": {
            "parquet": "data/factor_pool.parquet",
            "yaml": "configs/factor_pool.yaml",
            "report": "data/quality/factor_report.md",
        },
    }


def test_pipeline_initialization(config):
    """Pipeline should initialize with correct config."""
    pipeline = AlphaFactorPipeline(config)
    assert pipeline.stages == config["pipeline"]["stages"]
    assert pipeline.qlib_csv == "data/qlib_output/ohlcv"
    assert pipeline.qlib_bin == "data/qlib_bin"


def test_stage_method_map(config):
    """Pipeline should have correct stage mapping."""
    expected_map = {
        "ingest_bin": "ingest_bin",
        "factor_compute": "factor_compute",
        "label_compute": "label_compute",
        "filter": "run_filter",
        "export": "export",
        "report": "generate_report",
    }
    assert AlphaFactorPipeline.STAGE_METHOD_MAP == expected_map


def test_build_filter_chain_with_leakage_and_dedup(config):
    """Pipeline should include DropLeakageStep and DeduplicateStep when configured."""
    config["filter"]["drop_leakage"] = {"prefixes": ["LABEL"]}
    config["filter"]["deduplicate"] = {"corr_threshold": 0.8}

    pipeline = AlphaFactorPipeline(config)
    chain = pipeline._build_filter_chain(config["filter"])

    step_names = []
    current = chain
    while current is not None:
        step_names.append(current.name)
        current = current._next

    assert "DropLeakageStep" in step_names
    assert "DeduplicateStep" in step_names
