import pandas as pd
import numpy as np
import lightgbm as lgb
from tqdm import tqdm
from typing import Tuple, Dict, List
import os
from datetime import datetime

# Import components from existing pipeline
from src.etf_portfolio.main import fetch_etf_history, generate_reports, FULL_ETF_POOL

def assemble_portfolio(scores: pd.Series, top_n=4, single_cap=0.35, energy_cap=0.20) -> pd.Series:
    """Implement the ReLU Top-N capped allocation."""
    # 1. Top N and ReLU
    s = scores.copy()
    s = s.nlargest(top_n)
    s = s.clip(lower=0) 
    
    if s.sum() <= 0:
        # Fallback to defense
        fallback = pd.Series(0.0, index=scores.index)
        if 'SHSE.511260' in scores.index:
            fallback['SHSE.511260'] = 1.0
        elif 'SHSE.518800' in scores.index:
            fallback['SHSE.518800'] = 1.0
        return fallback

    # Initialize weights
    w = s / s.sum()
    
    # Energy indices (Oil ETFs)
    energy_assets = [c for c in w.index if c in ['SZSE.162411', 'SHSE.501018']]
    
    # Iterative capping (Simple iterative approach to handle overlapping constraints)
    for _ in range(5):
        # Apply energy cap
        energy_w = w[energy_assets].sum()
        if energy_w > energy_cap:
            reduce_factor = energy_cap / energy_w
            w[energy_assets] = w[energy_assets] * reduce_factor
            
        # Apply single cap
        w = w.clip(upper=single_cap)
        
        # Normalize non-capped
        current_sum = w.sum()
        if np.isclose(current_sum, 1.0, atol=1e-8):
            break
            
        # Distribute remainder
        remainder = 1.0 - current_sum
        # Items that can receive more (not at single cap and NOT strictly capped energy assets if energy cap is hit)
        # For simplicity in this MVP, we just distribute to those under single_cap
        # but to be truly correct with energy_cap, we should be careful.
        # Given the plan's code, we follow it:
        can_receive = w.index[(w < single_cap) & (~w.index.isin(energy_assets))]
        
        if len(can_receive) == 0:
            # If nothing can receive, try distributing to all non-maxed items
            can_receive = w.index[w < single_cap]
            if len(can_receive) == 0:
                break
            
        add_per = remainder / len(can_receive)
        w[can_receive] += add_per

    # Final normalization just in case
    return w / w.sum()

def build_features(prices: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Build multi-index features and labels for the ETF pool."""
    close = prices.xs('close', level='field', axis=1)
    high = prices.xs('high', level='field', axis=1)
    low = prices.xs('low', level='field', axis=1)
    volume = prices.xs('volume', level='field', axis=1)
    
    returns = close.pct_change()
    
    all_features = []
    all_labels = []
    
    for symbol in close.columns:
        s_close = close[symbol]
        s_high = high[symbol]
        s_low = low[symbol]
        s_vol = volume[symbol]
        
        # Features for this symbol
        df = pd.DataFrame(index=s_close.index)
        df['ema_diff_20'] = s_close.ewm(span=20).mean() / s_close - 1
        df['ema_diff_60'] = s_close.ewm(span=60).mean() / s_close - 1
        df['roc_20'] = s_close.pct_change(20)
        
        # RSI 14
        delta = s_close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        df['rsi_14'] = 100 - (100 / (1 + rs))
        
        # ATR 20
        tr = pd.concat([
            s_high - s_low,
            abs(s_high - s_close.shift()),
            abs(s_low - s_close.shift())
        ], axis=1).max(axis=1)
        df['atr_norm_20'] = tr.rolling(20).mean() / s_close
        
        # Volume Z-score 20
        df['vol_z_20'] = (s_vol - s_vol.rolling(20).mean()) / (s_vol.rolling(20).std() + 1e-9)
        
        # Macro indicator (common to all, but added to each row for panel)
        if 'SHSE.518800' in close.columns and 'SZSE.162411' in close.columns:
             df['gold_oil_ratio'] = close['SHSE.518800'] / close['SZSE.162411']
        
        df.columns = [f"{symbol}_{col}" for col in df.columns]
        all_features.append(df)
        
        # Target: 20-day forward return / 20-day volatility (Sharpe-like)
        fwd_ret = s_close.pct_change(20).shift(-20)
        fwd_vol = returns[symbol].rolling(20).std().shift(-20)
        label = fwd_ret / (fwd_vol * np.sqrt(20) + 1e-9)
        all_labels.append(label.rename(symbol))

    X = pd.concat(all_features, axis=1).astype(float)
    y = pd.concat(all_labels, axis=1).astype(float)
    
    return X, y

def run_ml_rolling_backtest(prices: pd.DataFrame, train_window=750, test_gap=20) -> pd.Series:
    """Run the rolling ML backtest pipeline."""
    # Ensure all inputs are float to avoid object dtype issues in pipeline
    prices = prices.astype(float)
    X, y = build_features(prices)
    close = prices.xs('close', level='field', axis=1)
    
    # Filter rebalance dates (Monthly)
    rebalance_dates = prices.index[prices.index.isin(prices.resample('ME').last().index)]
    rebalance_dates = [d for d in rebalance_dates if d > prices.index[train_window + test_gap]]
    
    all_weights = []
    
    for t in tqdm(rebalance_dates, desc="ML Rolling Backtest"):
        # Training data: from T-train_window to T-test_gap
        train_start = prices.index[prices.index.get_loc(t) - train_window]
        train_end = prices.index[prices.index.get_loc(t) - test_gap]
        
        X_train_wide = X.loc[train_start:train_end]
        y_train_wide = y.loc[train_start:train_end]
        
        # Convert wide to long (Panel) for training
        train_data = []
        for symbol in y.columns:
            sym_feat_cols = [c for c in X_train_wide.columns if c.startswith(f"{symbol}_")]
            # Also include macro features that don't start with symbol
            macro_cols = [c for c in X_train_wide.columns if not any(c.startswith(f"{s}_") for s in y.columns)]
            
            temp_X = X_train_wide[sym_feat_cols + macro_cols].copy()
            temp_X.columns = [c.replace(f"{symbol}_", "") for c in temp_X.columns]
            temp_y = y_train_wide[symbol]
            
            combined = pd.concat([temp_X, temp_y.rename('target')], axis=1).dropna()
            train_data.append(combined)
            
        if not train_data:
            continue
            
        train_panel = pd.concat(train_data)
        if train_panel.empty:
            continue
            
        # Model Training
        model = lgb.LGBMRegressor(
            n_estimators=100, 
            max_depth=5, 
            learning_rate=0.05, 
            verbosity=-1,
            random_state=42
        )
        model.fit(train_panel.drop('target', axis=1), train_panel['target'])
        
        # Prediction for T
        X_test_wide = X.loc[[t]]
        scores = {}
        for symbol in y.columns:
            sym_feat_cols = [c for c in X_test_wide.columns if c.startswith(f"{symbol}_")]
            macro_cols = [c for c in X_test_wide.columns if not any(c.startswith(f"{s}_") for s in y.columns)]
            
            temp_X_test = X_test_wide[sym_feat_cols + macro_cols].copy()
            temp_X_test.columns = [c.replace(f"{symbol}_", "") for c in temp_X_test.columns]
            
            if temp_X_test.isnull().values.any():
                scores[symbol] = -999 # Penalty for missing data
            else:
                pred = model.predict(temp_X_test)[0]
                scores[symbol] = pred
                
        # Portfolio Assembly
        weights = assemble_portfolio(pd.Series(scores))
        all_weights.append(weights.rename(t))

    if not all_weights:
        return pd.Series()
        
    weights_df = pd.concat(all_weights, axis=1).T
    weights_df.index = pd.to_datetime(weights_df.index)
    
    # Compute returns
    daily_rets = close.pct_change().shift(-1) # return from T to T+1
    # Realign weights to apply from T+1 onwards
    portfolio_rets = (weights_df.reindex(daily_rets.index).ffill() * daily_rets).sum(axis=1)
    
    return portfolio_rets.loc[rebalance_dates[0]:]

def main():
    # 1. Configuration
    symbols = list(FULL_ETF_POOL.keys())
    # Start date 2020 to leave enough for train_window=750
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = "2018-01-01" 
    
    print(f"Starting ETF ML Portfolio Pipeline (LightGBM)...")
    print(f"Period: {start_date} to {end_date}")
    
    # 2. Fetch Data
    print("\n[1/3] Fetching historical data (including volume)...")
    prices = fetch_etf_history(symbols, start_date, end_date)
    if prices.empty:
        print("Error: No data fetched.")
        return
        
    # 3. Running ML Rolling Backtest
    print("\n[2/3] Running rolling ML backtest...")
    ml_returns = run_ml_rolling_backtest(prices)
    
    # 4. Generating Reports
    if not ml_returns.empty:
        print("\n[3/3] Generating performance reports...")
        # Ensure float dtype for QuantStats
        ml_returns = ml_returns.astype(float)
        all_results = {'LightGBM_MVP': ml_returns}
        generate_reports(all_results, output_dir='reports_ml')
        print("\nPipeline execution complete. Reports saved in 'reports_ml/' directory.")
    else:
        print("\nError: ML backtest produced no returns. Check train_window and data availability.")

if __name__ == "__main__":
    main()
