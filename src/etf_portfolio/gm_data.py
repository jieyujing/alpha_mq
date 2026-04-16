import pandas as pd
from typing import Dict, List, Optional
try:
    from gm.api import history, set_token
except ImportError:
    # Facilitate testing in environments without gm sdk
    history = None
    set_token = lambda x: None

set_token("478dc4635c5198dbfcc962ac3bb209e5327edbff")

def fetch_etf_history(symbols: List[str], start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetch history data for a list of symbols from GM SDK and return as a pivoted MultiIndex DataFrame.
    Returns: DataFrame with MultiIndex columns (Symbol, Field) where Field is in [open, high, low, close]
    """
    data_dict = {}
    fields = 'symbol,bob,open,high,low,close'
    for symbol in symbols:
        df = history(symbol=symbol, frequency='1d', start_time=start_date, end_time=end_date, fields=fields, df=True)
        if df.empty:
               continue
        df['bob'] = pd.to_datetime(df['bob'])
        df.set_index('bob', inplace=True)
        # Keep OHLC fields
        data_dict[symbol] = df[['open', 'high', 'low', 'close']]
    
    return align_and_ffill_prices(data_dict)

def align_and_ffill_prices(data_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Align multiple dataframes (OHLC) and fill missing values using MultiIndex.
    """
    if not data_dict:
        return pd.DataFrame()
        
    # Create the MultiIndex for columns
    symbols = sorted(data_dict.keys())
    fields = ['open', 'high', 'low', 'close']
    col_index = pd.MultiIndex.from_product([symbols, fields], names=['symbol', 'field'])
    
    # Get all unique dates
    all_dates = pd.DatetimeIndex([])
    for df in data_dict.values():
        all_dates = all_dates.union(df.index)
    all_dates = all_dates.sort_values()
    
    # Create empty MultiIndex DataFrame
    aligned_df = pd.DataFrame(index=pd.to_datetime(all_dates), columns=col_index)
    
    for symbol, df in data_dict.items():
        for field in fields:
            if field in df.columns:
                aligned_df.loc[:, (symbol, field)] = df[field]
        
    # Forward fill missing values (if any gaps in existing series)
    aligned_df = aligned_df.sort_index().ffill()
    
    return aligned_df
