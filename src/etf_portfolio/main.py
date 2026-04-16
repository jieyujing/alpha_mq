import sys
import os
import pandas as pd
import numpy as np
import riskfolio as rp
import quantstats as qs
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from tqdm import tqdm

try:
    from gm.api import history, set_token
except ImportError:
    history = None
    set_token = lambda x: None

# Set the default token for gm sdk
set_token("478dc4635c5198dbfcc962ac3bb209e5327edbff")

# ==========================================
# 1. DATA FETCHING (Originally gm_data.py)
# ==========================================

def fetch_etf_history(symbols: List[str], start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetch history data for a list of symbols from GM SDK and return as a pivoted MultiIndex DataFrame.
    Returns: DataFrame with MultiIndex columns (Symbol, Field) where Field is in [open, high, low, close]
    """
    data_dict = {}
    fields = 'symbol,bob,open,high,low,close,volume'
    for symbol in symbols:
        df = history(symbol=symbol, frequency='1d', start_time=start_date, end_time=end_date, fields=fields, df=True)
        if df.empty:
               continue
        df['bob'] = pd.to_datetime(df['bob'])
        df.set_index('bob', inplace=True)
        # Keep OHLCV fields
        data_dict[symbol] = df[['open', 'high', 'low', 'close', 'volume']]
    
    return align_and_ffill_prices(data_dict)

def align_and_ffill_prices(data_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Align multiple dataframes (OHLC) and fill missing values using MultiIndex.
    """
    if not data_dict:
        return pd.DataFrame()
        
    # Create the MultiIndex for columns
    symbols = sorted(data_dict.keys())
    fields = ['open', 'high', 'low', 'close', 'volume']
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

# ==========================================
# 2. PORTFOLIO OPTIMIZATION (Originally optimizer.py)
# ==========================================

def get_optimal_weights(returns: pd.DataFrame, model: str = 'EW', obj: str = 'MinRisk', rm: str = 'MV') -> pd.Series:
    """
    Get optimal weights for a given returns dataframe and model using riskfolio-lib.
    Supported models: EW, GMV, MaxSharpe, ERC, HRP, HERC, NCO.

    - EW: Equal Weight (no optimization)
    - GMV/MaxSharpe: Classic mean-variance via Portfolio.optimization()
    - ERC: Equal Risk Contribution via Portfolio.rp_optimization()
    - HRP/HERC/NCO: Hierarchical clustering via HCPortfolio.optimization()
    """
    # Robustness: Check number of assets
    n_assets = returns.shape[1]
    if n_assets == 0:
        return pd.Series(dtype=float)
    
    if n_assets == 1:
        return pd.Series([1.0], index=returns.columns, name='weights')

    try:
        if model == 'EW':
            weights = pd.Series(1.0 / n_assets, index=returns.columns)
            return weights.to_frame('weights')['weights']

        if model in ['HRP', 'HERC', 'NCO']:
            if n_assets < 3:
                # Hierarchical clustering is unstable with < 3 assets
                raise ValueError("Too few assets for hierarchical clustering")
            # Hierarchical models use a separate HCPortfolio class
            hc_port = rp.HCPortfolio(returns=returns)
            weights = hc_port.optimization(
                model=model,
                codependence='pearson',
                obj='MinRisk',
                rm='MV',
                rf=0,
                l=2,
                method_mu='hist',
                method_cov='ledoit',
                leaf_order=True,
            )
        else:
            # Classic and ERC models use Portfolio class
            port = rp.Portfolio(returns=returns)
            # Use Ledoit-Wolf shrinkage for covariance estimation
            port.assets_stats(method_mu='hist', method_cov='ledoit')

            if model == 'GMV':
                weights = port.optimization(model='Classic', rm='MV', obj='MinRisk', rf=0, l=0, hist=True)
            elif model == 'MaxSharpe':
                weights = port.optimization(model='Classic', rm='MV', obj='Sharpe', rf=0, l=0, hist=True)
            elif model == 'ERC':
                # ERC uses the dedicated risk parity optimization method
                weights = port.rp_optimization(model='Classic', rm='MV', rf=0, hist=True)
            else:
                raise ValueError(f"Unsupported model: {model}")

        if weights is None:
            raise ValueError(f"Optimization returned None for model {model}")

        return weights['weights']
    
    except Exception as e:
        # Graceful fallback mechanisms
        # print(f"  [Optimizer Warning] {model} failed: {e}. Falling back...")
        if model in ['HRP', 'HERC', 'NCO', 'ERC']:
            return get_optimal_weights(returns, model='GMV', obj=obj, rm=rm)
        elif model in ['GMV', 'MaxSharpe']:
            return get_optimal_weights(returns, model='EW', obj=obj, rm=rm)
        else:
            weights = pd.Series(1.0 / n_assets, index=returns.columns)
            return weights

# ==========================================
# 3. ROLLING BACKTEST (Originally rolling.py)
# ==========================================

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

# ==========================================
# 4. REPORT GENERATION (Originally report.py)
# ==========================================

def generate_reports(all_returns: Dict[str, pd.Series], output_dir: str = 'reports'):
    """
    Generate QuantStats HTML reports for each set of portfolio returns.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    for model_name, returns in all_returns.items():
        if returns.empty:
            print(f"Skipping report for {model_name}: No returns data.")
            continue
            
        output_file = os.path.join(output_dir, f"{model_name}_tear_sheet.html")
        print(f"Generating report for {model_name} -> {output_file}")
        
        # Ensure index is datetime
        returns.index = pd.to_datetime(returns.index)
        
        # Fix for potential quantstats issues with certain pandas versions
        # Sometimes qs needs a series with a name
        returns.name = model_name
        
        try:
            qs.reports.html(returns, output=output_file, title=f"ETF Portfolio Strategy: {model_name}")
        except Exception as e:
            print(f"Error generating report for {model_name}: {e}")
            
    # Generate Comparison Plot
    if len(all_returns) > 1:
        print("\nGenerating strategy comparison plot...")
        # Align all returns by cumulative sum
        comp_df = pd.DataFrame(all_returns)
        # Ensure index is datetime and sorted
        comp_df.index = pd.to_datetime(comp_df.index)
        comp_df = comp_df.sort_index()
        
        # Plot and save
        comparison_file = os.path.join(output_dir, "strategy_comparison.png")
        try:
            # We use quantstats to generate a comparison plot
            qs.plots.returns(comp_df, savefig=comparison_file, show=False)
            print(f"Comparison plot saved to {comparison_file}")
        except Exception as e:
            print(f"Error generating comparison plot: {e}")
            # Fallback to simple matplotlib if qs fails
            try:
                import matplotlib.pyplot as plt
                cum_returns = (1 + comp_df).cumprod()
                plt.figure(figsize=(12, 7))
                cum_returns.plot()
                plt.title("ETF Strategy Comparison - Cumulative Returns")
                plt.ylabel("Cumulative Returns")
                plt.xlabel("Date")
                plt.legend(loc='upper left', bbox_to_anchor=(1, 1))
                plt.grid(True, alpha=0.3)
                plt.tight_layout()
                plt.savefig(comparison_file)
                plt.close()
                print(f"Fallback comparison plot saved to {comparison_file}")
            except Exception as e2:
                print(f"Fallback plotting failed: {e2}")

# ==========================================
# 5. MAIN EXECUTION
# ==========================================

FULL_ETF_POOL = {
    'SHSE.513120': '港股创新药ETF',
    'SZSE.159301': '公用事业ETF',
    'SZSE.159869': '游戏ETF',
    'SHSE.511260': '10年期国债ETF',
    'SHSE.511090': '30年期国债ETF',
    'SHSE.511380': '可转债ETF',
    'SHSE.518800': '黄金ETF',
    'SHSE.510300': '沪深300ETF',
    'SZSE.159915': '创业板ETF',
    'SHSE.513920': '港股通央企红利ETF',
    'SZSE.159920': '恒生ETF',
    'SZSE.159742': '恒生科技ETF',
    'SZSE.159941': '纳指ETF',
    'SHSE.501018': '南方原油ETF',
    'SZSE.162411': '华宝油气ETF'
}

def main():
    # 1. Configuration
    symbols = list(FULL_ETF_POOL.keys())
    # Look back to 2016 as requested
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = "2020-01-01"
    
    # Models to compare
    models = ['EW', 'GMV', 'MaxSharpe', 'ERC', 'HRP', 'HERC', 'NCO']
    
    # Set token (hardcoded per user request and gm_skill guidelines)
    token = "478dc4635c5198dbfcc962ac3bb209e5327edbff"
    set_token(token)
    
    print(f"Starting ETF Portfolio Pipeline...")
    print(f"Period: {start_date} to {end_date}")
    print(f"Symbols: {len(symbols)}")
    print(f"Models: {models}")
    
    # 2. Fetch Data
    print("\n[1/3] Fetching historical data...")
    prices = fetch_etf_history(symbols, start_date, end_date)
    if prices.empty:
        print("Error: No data fetched. Check your GM SDK token and connection.")
        return
    print(f"Fetched data for {prices.shape[1]} assets across {len(prices)} trading days.")
    
    # 3. Running Rolling Backtest
    print("\n[2/3] Running rolling backtest (Window: 252, Rebalance: Monthly)...")
    results = run_rolling_backtest(prices, models=models, window=252, freq='ME')
    
    # 4. Generating Reports
    print("\n[3/3] Generating performance reports...")
    generate_reports(results, output_dir='reports')
    
    print("\nPipeline execution complete. Reports saved in 'reports/' directory.")

if __name__ == "__main__":
    main()
