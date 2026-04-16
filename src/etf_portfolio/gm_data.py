import pandas as pd
from typing import Dict, List, Optional
try:
    from gm.api import history
except ImportError:
    # Facilitate testing in environments without gm sdk
    history = None

def fetch_etf_history(symbols: List[str], start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetch history data for a list of symbols from GM SDK and return as a pivoted DataFrame.
    """
    data_dict = {}
    for symbol in symbols:
        df = history(symbol=symbol, frequency='1d', start_time=start_date, end_time=end_date, fields='symbol,bob,close', df=True)
        if df.empty:
               continue
        df['bob'] = pd.to_datetime(df['bob'])
        df.set_index('bob', inplace=True)
        data_dict[symbol] = df[['close']]
    
    return align_and_ffill_prices(data_dict)

def align_and_ffill_prices(data_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Align multiple dataframes with close prices and fill missing values.
    """
    if not data_dict:
        return pd.DataFrame()
        
    # Get all unique dates
    all_dates = pd.DatetimeIndex([])
    for df in data_dict.values():
        all_dates = all_dates.union(df.index)
        
    all_dates = all_dates.sort_values()
    
    # Create an empty dataframe with all dates
    aligned_df = pd.DataFrame(index=all_dates)
    
    for symbol, df in data_dict.items():
        aligned_df[symbol] = df['close']
        
    # Forward fill missing values
    aligned_df = aligned_df.ffill().dropna()
    
    return aligned_df
