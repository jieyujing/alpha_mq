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
    # Extract close prices for return and SMA calculation
    # prices is now a MultiIndex DataFrame (Symbol, Field)
    prices_close = prices.xs('close', level='field', axis=1)
    prices_open = prices.xs('open', level='field', axis=1)
    prices_low = prices.xs('low', level='field', axis=1)
    
    # Calculate returns but DO NOT dropna() globally
    returns = prices_close.pct_change()
    # Pre-calculate SMA20 for trend filtering (more responsive than SMA60)
    sma_trend = prices_close.rolling(20).mean()
    # Use dates where we have at least one return
    dates = returns.index[1:]
    returns = returns.iloc[1:]
    
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
            # --- Trend Filtering Logic (Optimization Gate) ---
            current_prices = prices_close.loc[prev_date]
            current_sma = sma_trend.loc[prev_date]
            
            # Signal: Price > SMA
            trend_signals = current_prices > current_sma
            eligible_assets = trend_signals[trend_signals].index.tolist()
            
            # Fallback: If no assets are in uptrend, hold cash (10Y Bond ETF)
            # Make sure the fallback asset is in our price data
            fallback_asset = 'SHSE.511260'
            if not eligible_assets:
                if fallback_asset in returns.columns:
                    eligible_assets = [fallback_asset]
                    # print(f"[{prev_date}] All assets in downtrend. Falling back to {fallback_asset}")
                else:
                    # If even fallback is missing (unlikely), EW across all
                    eligible_assets = returns.columns.tolist()
            
            window_returns = returns.iloc[i-window:i]
            # Filter assets: listed in window AND in uptrend
            # dropna(axis=1) handles listing status
            window_returns = window_returns.dropna(axis=1)
            
            # Intersect with eligible_assets
            window_returns = window_returns[window_returns.columns.intersection(eligible_assets)]
            
            if window_returns.shape[1] > 0:
                for model in models:
                    try:
                        opt_weights = get_optimal_weights(window_returns, model=model)
                        # Re-align weights with all assets (unselected assets get 0)
                        current_weights[model] = pd.Series(0.0, index=returns.columns)
                        current_weights[model].update(opt_weights)
                    except Exception as e:
                        print(f"Error optimizing {model} at {prev_date}: {e}")
                        # Keep previous weights if possible or Equal Weight if first time
                        if current_weights[model] is None:
                             n = returns.shape[1]
                             current_weights[model] = pd.Series(1.0/n, index=returns.columns)
            else:
                print(f"Warning: No valid assets in window at {prev_date}")

        # Apply weights to current day returns
        if any(w is not None for w in current_weights.values()):
            # Decision for TODAY (T) must be based on information available YESTERDAY (T-1).
            # We check if assets satisfied the trend condition at the previous close.
            trigger_line = sma_trend.loc[prev_date]
            prev_close = prices_close.loc[prev_date]
            
            # Intraday information for TODAY
            day_open = prices_open.loc[current_date]
            day_low = prices_low.loc[current_date]
            day_close = prices_close.loc[current_date]
            
            portfolio_dates.append(current_date)
            for model in models:
                if current_weights[model] is not None:
                    # Current allocation weights from last rebalance
                    w = current_weights[model]
                    
                    # 1. Check if we even want to enter/hold today (Yesterday's Close > Yesterday's SMA)
                    is_trending = (prev_close > trigger_line).fillna(False)
                    
                    # 2. Calculate actual return for today considering Intraday Exit (Stop-Order)
                    # For assets we intended to hold (is_trending):
                    # - If day_low < trigger_line: Exit at max(day_open, trigger_line)
                    # - Else: regular close-to-close return
                    
                    actual_day_returns = pd.Series(0.0, index=w.index)
                    for sym in w.index[w > 0]:
                        if not is_trending.get(sym, False):
                            actual_day_returns[sym] = 0.0 # Don't hold if trend was already broken
                        else:
                            # We held it. Did it break trend DURING the day?
                            limit = trigger_line.get(sym, 0.0)
                            if day_low.get(sym, 0.0) < limit:
                                # INTRADAY EXIT TRIGGERED
                                exit_p = max(day_open.get(sym, 0.0), limit)
                                actual_day_returns[sym] = (exit_p / prev_close.get(sym, 1.0)) - 1.0
                            else:
                                # Normal holding
                                actual_day_returns[sym] = (day_close.get(sym, 0.0) / prev_close.get(sym, 1.0)) - 1.0
                    
                    # Weighted portfolio return
                    ret = (w * actual_day_returns.fillna(0.0)).sum()
                    portfolio_daily_returns[model].append(ret)
                else:
                    portfolio_daily_returns[model].append(0.0)

    # Convert to Series
    final_results = {}
    for model in models:
        final_results[model] = pd.Series(portfolio_daily_returns[model], index=portfolio_dates)
        
    return final_results
