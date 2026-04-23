# tests/pipelines/factor/test_label_builder.py
import pytest
import numpy as np
import pandas as pd
from pipelines.factor.label_builder import LabelBuilder


@pytest.fixture
def builder():
    return LabelBuilder(qlib_bin_path="data/qlib_bin")


def test_compute_labels_returns_dict(builder):
    """Should return a dict of label Series keyed by label name."""
    dates = pd.date_range("2020-01-01", periods=10, freq="B")
    index = pd.MultiIndex.from_product(
        [dates, ["SH600000"]], names=["datetime", "instrument"]
    )
    close_data = pd.DataFrame({"close": [100.0 + i for i in range(10)]}, index=index)

    labels = builder.compute_labels(close_data, periods=[1, 5])
    assert "label_1d" in labels
    assert "label_5d" in labels
    assert isinstance(labels["label_1d"], pd.Series)
    assert len(labels["label_1d"]) == len(close_data)


def test_label_1d_values(builder):
    """1D label = close(t+1) / close(t) - 1."""
    close_data = pd.DataFrame({
        "close": [100.0, 105.0, 110.0],
    }, index=pd.MultiIndex.from_tuples([
        ("2020-01-01", "SH600000"),
        ("2020-01-02", "SH600000"),
        ("2020-01-03", "SH600000"),
    ], names=["datetime", "instrument"]))

    labels = builder.compute_labels(close_data, periods=[1])
    label_1d = labels["label_1d"].values
    # 100->105 = 5%, 105->110 = 4.76%, last = NaN
    assert abs(label_1d[0] - 0.05) < 1e-6
    assert abs(label_1d[1] - (110.0 / 105.0 - 1)) < 1e-6
    assert np.isnan(label_1d[2])
