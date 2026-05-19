# tests/pipelines/factor/test_factor_loader.py
import pytest
import numpy as np
import pandas as pd
import polars as pl
from unittest.mock import patch
from pipelines.factor.factor_loader import FactorLoader


@pytest.fixture
def dummy_lazyframe():
    # 构造足够的样本（比如 70 天）以支持 rolling 60 的特征计算
    dates = pd.date_range("2020-01-01", periods=100, freq="B").strftime("%Y-%m-%d").tolist()
    n = len(dates)
    
    # 模拟真实价量数据，防止 std 等除以 0 或计算产生 NaN
    np.random.seed(42)
    close_prices = 10.0 + np.cumsum(np.random.randn(n) * 0.1)
    open_prices = close_prices + np.random.randn(n) * 0.05
    high_prices = np.maximum(open_prices, close_prices) + np.random.rand(n) * 0.1
    low_prices = np.minimum(open_prices, close_prices) - np.random.rand(n) * 0.1
    volume = np.random.randint(100, 1000, size=n).astype(float)
    amount = volume * close_prices

    data = {
        "date": dates,
        "open": open_prices.tolist(),
        "close": close_prices.tolist(),
        "high": high_prices.tolist(),
        "low": low_prices.tolist(),
        "volume": volume.tolist(),
        "amount": amount.tolist(),
        "filepath": ["/path/to/daily/SH600000.parquet"] * n
    }
    return pl.LazyFrame(data)


def test_load_alpha158_returns_dataframe(dummy_lazyframe):
    """Alpha158 Polars pipeline should compute exactly 158 features without errors."""
    loader = FactorLoader(parquet_input="/dummy/path")

    with patch("polars.scan_parquet", return_value=dummy_lazyframe):
        df = loader.load_alpha158(
            universe="csi1000",
            start="2020-01-01",
            end="2020-05-01",
        )

    assert isinstance(df, pd.DataFrame)
    assert isinstance(df.index, pd.MultiIndex)
    assert df.index.names == ["datetime", "instrument"]
    
    # 验证是否返回了 158 个因子（除去 datetime 和 instrument 物理主键后列数为 158）
    assert df.shape[1] == 158
    assert "KMID" in df.columns
    assert "ROC5" in df.columns
    assert "IMXD5" in df.columns
