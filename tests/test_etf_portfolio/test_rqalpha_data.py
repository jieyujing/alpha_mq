from unittest.mock import patch, MagicMock
import pytest
import pandas as pd
import numpy as np

from src.etf_portfolio.rqalpha_data import RQAlphaDataSource

def test_symbol_translation():
    assert RQAlphaDataSource._translate_symbol("SHSE.600000") == "600000.XSHG"
    assert RQAlphaDataSource._translate_symbol("SZSE.000001") == "000001.XSHE"
    assert RQAlphaDataSource._translate_symbol("UNKNOWN.123") == "UNKNOWN.123"

@patch('src.etf_portfolio.rqalpha_data.BaseDataSource')
@patch('src.etf_portfolio.rqalpha_data.DataProxy')
@patch('os.path.exists')
def test_protocol_methods(mock_exists, mock_data_proxy, mock_local_data_source):
    mock_exists.return_value = True
    ds = RQAlphaDataSource("/fake/path")
    
    # set_token should do nothing and not raise
    ds.set_token("any_token")
    
    # fetch_basic and fetch_valuation should return empty dataframes
    df_basic = ds.fetch_basic("SHSE.600000", "2023-01-01", "2023-01-10")
    assert isinstance(df_basic, pd.DataFrame)
    assert df_basic.empty

    df_val = ds.fetch_valuation("SHSE.600000", "2023-01-01", "2023-01-10")
    assert isinstance(df_val, pd.DataFrame)
    assert df_val.empty
    
def test_init_raises_on_missing_bundle():
    with pytest.raises(FileNotFoundError):
        RQAlphaDataSource("/path/that/definitely/does/not/exist/12345")

@patch('src.etf_portfolio.rqalpha_data.BaseDataSource')
@patch('src.etf_portfolio.rqalpha_data.DataProxy')
@patch('os.path.exists')
def test_fetch_history(mock_exists, mock_data_proxy_class, mock_local_data_source):
    mock_exists.return_value = True
    mock_proxy_instance = MagicMock()
    mock_data_proxy_class.return_value = mock_proxy_instance
    
    # Mock return value of history_bars (standard structured array from rqalpha)
    dt_type = np.dtype([('datetime', 'O'), ('close', 'f8'), ('volume', 'f8')])
    mock_array = np.array([(pd.Timestamp('2023-01-01'), 10.0, 100)], dtype=dt_type)
    mock_proxy_instance.history_bars.return_value = mock_array
    
    ds = RQAlphaDataSource("/fake/path")
    df = ds.fetch_history("SHSE.600000", "2023-01-01", "2023-01-10", frequency="1d")
    
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert 'close' in df.columns
    assert 'volume' in df.columns
    # symbol should be injected/re-mapped or we at least verify datetime index/column
    
    mock_proxy_instance.history_bars.assert_called_once_with(
        order_book_id="600000.XSHG",
        bar_count=10000,
        frequency="1d",
        field=None,
        dt=pd.Timestamp("2023-01-10"),
        skip_suspended=True,
        include_now=False
    )
