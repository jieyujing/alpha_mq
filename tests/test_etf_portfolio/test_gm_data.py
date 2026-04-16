import pandas as pd
import pytest
from src.etf_portfolio.gm_data import align_and_ffill_prices

def test_align_and_ffill_prices():
    # Create dummy data with gaps
    df1 = pd.DataFrame({'close': [10.0, 11.0]}, index=pd.to_datetime(['2026-01-01', '2026-01-03']))
    df2 = pd.DataFrame({'close': [20.0, 22.0]}, index=pd.to_datetime(['2026-01-01', '2026-01-02']))
    
    # Symbols to align
    data_dict = {
        'T1': df1,
        'T2': df2
    }
    
    # Expected: 2026-01-01 to 2026-01-03
    aligned = align_and_ffill_prices(data_dict)
    
    assert aligned.shape == (3, 2)
    assert 'T1' in aligned.columns
    assert 'T2' in aligned.columns
    assert aligned.loc['2026-01-02', 'T1'] == 10.0  # ffill
    assert aligned.loc['2026-01-03', 'T2'] == 22.0  # ffill
