import pandas as pd
import numpy as np
from src.etf_portfolio.rolling import run_rolling_backtest

def test_run_rolling_backtest():
    # 2 years of daily data (approx 504 days), 3 assets
    dates = pd.date_range('2024-01-01', periods=504, freq='B')
    data = np.random.randn(504, 3) * 0.01 + 0.0001
    prices = pd.DataFrame(data, index=dates, columns=['A', 'B', 'C']).cumsum() + 100
    
    # Run with EW only for speed in test
    results = run_rolling_backtest(prices, models=['EW'], window=252, freq='ME')
    
    assert 'EW' in results
    assert isinstance(results['EW'], pd.Series)
    # The result should start after the first window
    assert len(results['EW']) < 504
