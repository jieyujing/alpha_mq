"""Tests for cross-section feature preprocessing."""
import numpy as np
import pandas as pd
import pytest
from pipelines.model.feature_prep import (
    cross_section_rank_normalize,
    cross_section_zscore,
    winsorize_label_by_date_quantile,
    make_rank_label_by_date,
    make_binary_label_by_date,
    FeaturePreprocessor,
)


@pytest.fixture
def multiindex_data():
    dates = pd.date_range("2020-01-01", periods=5, freq="B")
    symbols = [f"SH60000{i}" for i in range(1, 11)]  # 10 symbols per day
    index = pd.MultiIndex.from_product([dates, symbols], names=["datetime", "instrument"])
    rng = np.random.RandomState(42)
    X = pd.DataFrame({f"f{i}": rng.randn(len(index)) for i in range(3)}, index=index)
    return X


@pytest.fixture
def label_series():
    dates = pd.date_range("2020-01-01", periods=5, freq="B")
    symbols = [f"SH60000{i}" for i in range(1, 11)]
    index = pd.MultiIndex.from_product([dates, symbols], names=["datetime", "instrument"])
    rng = np.random.RandomState(99)
    y = pd.Series(rng.randn(len(index)), index=index)
    # Add extreme outliers
    y.iloc[0] = 100.0
    y.iloc[1] = -100.0
    return y


def test_rank_normalize_shape(multiindex_data):
    result = cross_section_rank_normalize(multiindex_data)
    assert result.shape == multiindex_data.shape
    assert list(result.columns) == list(multiindex_data.columns)


def test_rank_normalize_range(multiindex_data):
    result = cross_section_rank_normalize(multiindex_data)
    # Values should be in [-1, 1] approximately (after rank pct transform)
    assert result.min().min() >= -1.0 - 1e-9
    assert result.max().max() <= 1.0 + 1e-9


def test_winsorize_label_by_date(label_series):
    result = winsorize_label_by_date_quantile(label_series, lower_q=0.05, upper_q=0.95)
    assert result.shape == label_series.shape
    # Extreme outliers should be clipped (but with only 10 samples,
    # the 95th quantile is influenced by the outlier itself)
    assert result.max() < 100
    assert result.min() > -100


def test_rank_label_by_date(label_series):
    result = make_rank_label_by_date(label_series, n_bins=5, min_group_size=5)
    assert len(result) == len(label_series)
    non_null = result.dropna()
    assert set(non_null.unique()) <= {0.0, 1.0, 2.0, 3.0, 4.0}


def test_rank_label_drops_small_dates(label_series):
    result = make_rank_label_by_date(label_series, n_bins=5, min_group_size=1000)
    assert result.isna().all(), "All dates have < 1000 samples, should be all NaN"


def test_binary_label_by_date(label_series):
    y_bin, mask = make_binary_label_by_date(label_series, top_q=0.8, bottom_q=0.2)
    assert len(y_bin) == len(label_series)
    assert set(y_bin.dropna().unique()) <= {0.0, 1.0}
    assert mask.sum() <= len(label_series) * 0.4 + 10  # ~40% of samples (top 20% + bottom 20%)


def test_feature_preprocessor_pipeline(multiindex_data):
    prep = FeaturePreprocessor(
        impute="cross_section_median",
        transform_method="rank_pct",
        winsorize_enabled=True,
        winsorize_lower=0.01,
        winsorize_upper=0.99,
    )
    result = prep.transform(multiindex_data)
    assert result.shape == multiindex_data.shape
    assert not result.isna().any().any(), "No NaN after preprocessing"
