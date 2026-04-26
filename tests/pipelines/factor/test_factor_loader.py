# tests/pipelines/factor/test_factor_loader.py
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock
from pipelines.factor.factor_loader import FactorLoader


@pytest.fixture
def loader():
    return FactorLoader(qlib_bin_path="data/qlib_bin")


def make_mock_index(n=10):
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.MultiIndex.from_product(
        [dates, ["SH600000"]], names=["datetime", "instrument"]
    )


def test_load_alpha158_returns_dataframe(loader):
    """Alpha158 handler should return a MultiIndex DataFrame with factors."""
    idx = make_mock_index()
    mock_data = pd.DataFrame({
        "KMID": np.random.randn(len(idx)),
        "KLEN": np.random.randn(len(idx)),
    }, index=idx)

    mock_handler = MagicMock()
    mock_handler.fetch.return_value = mock_data

    with patch("pipelines.factor.factor_loader.qlib") as mock_qlib:
        with patch("pipelines.factor.factor_loader.Alpha158", return_value=mock_handler):
            df = loader.load_alpha158(
                instruments="csi1000",
                start="2020-01-01",
                end="2020-12-31",
            )

    assert isinstance(df, pd.DataFrame)
    assert isinstance(df.index, pd.MultiIndex)
    assert "KMID" in df.columns
    assert "KLEN" in df.columns
    mock_qlib.init.assert_called_once()


def test_load_alpha158_drops_multiindex_label_columns(loader):
    """Alpha158 MultiIndex label columns should be removed without breaking."""
    idx = make_mock_index()
    columns = pd.MultiIndex.from_tuples([
        ("feature", "KMID"),
        ("feature", "KLEN"),
        ("label", "LABEL0"),
    ])
    mock_data = pd.DataFrame(np.random.randn(len(idx), len(columns)), index=idx, columns=columns)

    mock_handler = MagicMock()
    mock_handler.fetch.return_value = mock_data

    with patch("pipelines.factor.factor_loader.qlib") as mock_qlib:
        with patch("pipelines.factor.factor_loader.Alpha158", return_value=mock_handler):
            df = loader.load_alpha158(
                instruments="csi1000",
                start="2020-01-01",
                end="2020-12-31",
            )

    assert ("feature", "KMID") in df.columns
    assert ("feature", "KLEN") in df.columns
    assert ("label", "LABEL0") not in df.columns
    mock_qlib.init.assert_called_once()


def test_load_with_extra_fields(loader):
    """Extra fields should be appended to Alpha158 factors."""
    idx = make_mock_index()
    mock_alpha = pd.DataFrame({"f0": np.ones(len(idx))}, index=idx)
    mock_extra = pd.DataFrame({"pe_ttm": np.full(len(idx), 10.0)}, index=idx)

    mock_handler = MagicMock()
    mock_handler.fetch.return_value = mock_alpha

    # Mock the D.features call at the module level where it's imported
    mock_d = MagicMock()
    mock_d.features.return_value = mock_extra

    with patch("pipelines.factor.factor_loader.qlib") as mock_qlib:
        with patch("pipelines.factor.factor_loader.Alpha158", return_value=mock_handler):
            with patch("qlib.data.D", mock_d):
                df = loader.load_alpha158(
                    instruments="csi1000",
                    start="2020-01-01",
                    end="2020-12-31",
                    extra_fields=["pe_ttm"],
                )

    assert "f0" in df.columns
    assert "pe_ttm" in df.columns
    assert df.shape[1] == 2
