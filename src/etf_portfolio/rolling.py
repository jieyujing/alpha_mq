import pandas as pd
import numpy as np
from typing import List, Dict
from src.etf_portfolio.optimizer import get_optimal_weights
from tqdm import tqdm

def run_rolling_backtest(prices: pd.DataFrame, models: List[str], window: int = 252, freq: str = 'ME') -> Dict[str, pd.Series]:
    """
    Run rolling backtest for multiple models.
    freq: 'ME' (Month End), 'QE' (Quarter End), etc.
    """
    returns = prices.pct_change().dropna()
    dates = returns.index
    
    # Get rebalancing dates based on frequency
    # We use the index to find the end-of-period dates available in our data
    rebalance_dates = returns.resample(freq).last().index
    # Filter to only those in the range after initial window
    valid_rebalance_dates = [d for d in rebalance_dates if d >= dates[window-1]]
    
    results = {model: pd.Series(dtype=float) for model in models}
    
    # Initialize weights for each model at the start
    current_weights = {model: None for model in models}
    
    # Iterate through each day
    # Optimization happens on valid_rebalance_dates
    # Weights are applied from the next day until the next rebalance
    
    portfolio_daily_returns = {model: [] for model in models}
    portfolio_dates = []
    
    for i in tqdm(range(window, len(dates)), desc="Rolling Backtest"):
        current_date = dates[i]
        prev_date = dates[i-1]
        
        # If prev_date was a rebalance date, recalculate weights
        if prev_date in valid_rebalance_dates:
            window_returns = returns.iloc[i-window:i]
            for model in models:
                try:
                    current_weights[model] = get_optimal_weights(window_returns, model=model)
                except Exception as e:
                    print(f"Error optimizing {model} at {prev_date}: {e}")
                    # Keep previous weights if possible or Equal Weight if first time
                    if current_weights[model] is None:
                         n = returns.shape[1]
                         current_weights[model] = pd.Series(1.0/n, index=returns.columns)

        # Apply weights to current day returns
        if any(w is not None for w in current_weights.values()):
            day_return = returns.iloc[i]
            portfolio_dates.append(current_date)
            for model in models:
                if current_weights[model] is not None:
                    # dot product of weights and day returns
                    ret = (current_weights[model] * day_return).sum()
                    portfolio_daily_returns[model].append(ret)
                else:
                    portfolio_daily_returns[model].append(0.0)

    # Convert to Series
    final_results = {}
    for model in models:
        final_results[model] = pd.Series(portfolio_daily_returns[model], index=portfolio_dates)
        
    return final_results
