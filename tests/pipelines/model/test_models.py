"""Tests for model wrappers and factory."""
import pytest
import numpy as np
import pandas as pd
from pipelines.model.base_model import get_model


@pytest.fixture
def sample_data():
    """Create sample (X, y) with MultiIndex."""
    dates = pd.date_range("2020-01-01", periods=100, freq="B")
    symbols = ["SH600000", "SZ000001", "SH600010"]
    index = pd.MultiIndex.from_product([dates, symbols], names=["datetime", "instrument"])
    rng = np.random.RandomState(42)
    X = pd.DataFrame({f"f{i}": rng.randn(len(index)) for i in range(5)}, index=index)
    y = pd.Series(rng.randn(len(index)), index=index, name="label")
    return X, y


def test_get_model_unknown():
    with pytest.raises(ValueError, match="Unknown model"):
        get_model("nonexistent_model")
