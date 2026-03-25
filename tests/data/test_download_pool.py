import pytest
import pandas as pd
from data.scripts.download_pool import build_instrument_history

def test_build_instrument_history_mocked(mocker):
    # Mock gm.get_history_constituents to avoid real network call
    mock_get = mocker.patch("data.scripts.download_pool.get_history_constituents")
    mock_get.return_value = pd.DataFrame({
        "symbol": ["SHSE.600000"], "weight": [0.01]
    })
    
    df = build_instrument_history("2015-01-01", "2015-01-02")
    assert not df.empty
    assert "symbol" in df.columns
