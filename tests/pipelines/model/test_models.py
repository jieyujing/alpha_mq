"""Tests for model wrappers and factory."""
import pytest
import numpy as np
import pandas as pd
from pipelines.model.base_model import get_model


@pytest.fixture
def sample_data():
    """Create sample (X, y) with MultiIndex. At least 10 symbols per date for IC computation."""
    dates = pd.date_range("2020-01-01", periods=20, freq="B")
    symbols = [f"SH60000{i:02d}" for i in range(1, 16)]  # 15 symbols per date (> min_obs=5)
    index = pd.MultiIndex.from_product([dates, symbols], names=["datetime", "instrument"])
    rng = np.random.RandomState(42)
    X = pd.DataFrame({f"f{i}": rng.randn(len(index)) for i in range(5)}, index=index)
    y = pd.Series(rng.randn(len(index)), index=index, name="label")
    return X, y


def test_get_model_unknown():
    with pytest.raises(ValueError, match="Unknown model"):
        get_model("nonexistent_model")


# === Evaluator tests ===
from pipelines.model.evaluator import (
    compute_ic_by_date,
    compute_metrics_from_ic_series,
    orient_signal,
)


def test_ic_by_date_returns_series(sample_data):
    X, y = sample_data
    ic = compute_ic_by_date(y, y)  # Perfect correlation
    assert isinstance(ic, pd.Series)
    assert ic.mean() == pytest.approx(1.0, abs=0.01)


def test_ic_by_date_random_low(sample_data):
    X, y = sample_data
    rng = np.random.RandomState(123)
    random_pred = pd.Series(rng.randn(len(y)), index=y.index, name="pred")
    ic = compute_ic_by_date(random_pred, y)
    # Random predictions should have low mean IC
    assert abs(ic.mean()) < 0.2


def test_orient_signal_positive(sample_data):
    X, y = sample_data
    oriented, direction = orient_signal(0.05, y)
    assert direction == 1
    assert oriented.equals(y)


def test_orient_signal_negative(sample_data):
    X, y = sample_data
    oriented, direction = orient_signal(-0.05, y)
    assert direction == -1
    assert oriented.equals(-y)


def test_compute_metrics_from_ic_series():
    ic = pd.Series([0.05, 0.03, -0.01, 0.04, 0.06], name="ic")
    metrics = compute_metrics_from_ic_series(ic)
    assert "ic_mean" in metrics
    assert "icir" in metrics
    assert metrics["ic_mean"] > 0
    assert metrics["positive_ratio"] == pytest.approx(0.8)
