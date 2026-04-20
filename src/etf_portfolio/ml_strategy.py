import pandas as pd
import numpy as np
import lightgbm as lgb
from tqdm import tqdm
from typing import Tuple, Dict, List
import os
from datetime import datetime

# Import components from existing pipeline
from src.etf_portfolio.main import fetch_etf_history, generate_reports, FULL_ETF_POOL
from src.etf_portfolio.alphalens_utils import generate_factor_report

def assemble_portfolio(scores: pd.Series, top_n=4, single_cap=0.35, energy_cap=0.20) -> pd.Series:
    """
    Implement a robust projection for ReLU Top-N capped allocation.
    Ensures weights sum to 1.0 while respecting single-asset and energy-group caps.
    """
    # 1. Top N selection and ReLU (non-negative)
    s = scores.copy()
    s = s.nlargest(top_n)
    s = s.clip(lower=0) 
    
    if s.sum() <= 1e-9:
        # Fallback to defense
        fallback = pd.Series(0.0, index=scores.index)
        if 'SHSE.511260' in scores.index:
            fallback['SHSE.511260'] = 1.0
        elif 'SHSE.518800' in scores.index:
            fallback['SHSE.518800'] = 1.0
        return fallback

    # Initialize weights
    w = s / s.sum()
    energy_assets = [c for c in w.index if c in ['SZSE.162411', 'SHSE.501018']]
    
    # 2. Iterative Projection (Clip and Redistribute)
    for _ in range(50):
        prev_w = w.copy()
        
        # A. Apply Group Cap (Energy)
        e_sum = w[energy_assets].sum()
        if e_sum > energy_cap:
            w[energy_assets] = w[energy_assets] * (energy_cap / (e_sum + 1e-9))
            
        # B. Apply Box Cap (Single Asset)
        w = w.clip(upper=single_cap)
        
        # C. Normalize (Redistribute gap to free assets)
        current_sum = w.sum()
        gap = 1.0 - current_sum
        
        if abs(gap) < 1e-7:
            break
            
        # Identify assets that are "free" (not at single cap and not in a maxed-out energy group)
        # To simplify, we'll distribute to all assets not at their single cap, 
        # but if we are at energy cap, we skip energy assets.
        is_energy_hit = w[energy_assets].sum() >= energy_cap - 1e-7
        can_receive = w.index[w < single_cap - 1e-7]
        if is_energy_hit:
            can_receive = [c for c in can_receive if c not in energy_assets]
            
        if len(can_receive) == 0:
            # Emergency: if no one can receive, we can't satisfy sum=1 with these constraints
            # This usually means constraints were too tight, but here sum(top_n * single_cap) should be > 1
            break
            
        # Distribute proportional to existing weights or equally if weights are 0
        w_can = w[can_receive]
        if w_can.sum() > 1e-9:
            w[can_receive] += gap * (w_can / w_can.sum())
        else:
            w[can_receive] += gap / len(can_receive)
            
        if np.allclose(w, prev_w, atol=1e-8):
            break

    return w / w.sum()

    # Final normalization just in case
    return w / w.sum()

def build_features(prices: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build multi-index features, labels, and macro features."""
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
        df['atr_norm_20'] = tr.rolling(20).mean() / (s_close + 1e-9)
        
        # Volume Z-score 20
        df['vol_z_20'] = (s_vol - s_vol.rolling(20).mean()) / (s_vol.rolling(20).std() + 1e-9)
        
        df.columns = [f"{symbol}_{col}" for col in df.columns]
        all_features.append(df)
        
        # Target: 20-day forward return / 20-day volatility (Sharpe-like)
        fwd_ret = s_close.pct_change(20).shift(-20)
        fwd_vol = returns[symbol].rolling(20).std().shift(-20)
        label = fwd_ret / (fwd_vol * np.sqrt(20) + 1e-9)
        all_labels.append(label.rename(symbol))

    X = pd.concat(all_features, axis=1).astype(float)
    y = pd.concat(all_labels, axis=1).astype(float)
    
    # Separate Macro Features (shared across assets)
    macro_df = pd.DataFrame(index=close.index)
    if 'SHSE.518800' in close.columns and 'SZSE.162411' in close.columns:
        macro_df['gold_oil_ratio'] = close['SHSE.518800'] / (close['SZSE.162411'] + 1e-9)
    
    return X, y, macro_df

def run_ml_rolling_backtest(prices: pd.DataFrame, train_window=750, test_gap=20) -> Tuple[pd.Series, pd.Series]:
    """Run the rolling ML backtest pipeline."""
    # Ensure all inputs are float and naive timestamps to avoid issues
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    prices = prices.astype(float)
    X, y, macro = build_features(prices)
    close = prices.xs('close', level='field', axis=1)
    
    # Filter rebalance dates (Actual Trading Days: Last available per month)
    rebalance_dates = prices.index.to_series().groupby(prices.index.to_period('M')).max().values
    rebalance_dates = [pd.Timestamp(d) for d in rebalance_dates if pd.Timestamp(d) > prices.index[train_window + test_gap]]
    
    all_weights = []
    all_scores = []
    
    for t in tqdm(rebalance_dates, desc="ML Rolling Backtest"):
        # Training data: from T-train_window to T-test_gap
        train_start = prices.index[prices.index.get_loc(t) - train_window]
        train_end = prices.index[prices.index.get_loc(t) - test_gap]
        
        X_train_wide = X.loc[train_start:train_end]
        y_train_wide = y.loc[train_start:train_end]
        
        # Convert wide to long (Panel) for training
        train_data = []
        X_train_wide = pd.concat([X_train_wide, macro.loc[train_start:train_end]], axis=1)
        
        for symbol in y.columns:
            sym_feat_cols = [c for c in X_train_wide.columns if c.startswith(f"{symbol}_")]
            macro_cols = list(macro.columns)
            
            temp_X = X_train_wide[sym_feat_cols + macro_cols].copy()
            temp_X.columns = [c.replace(f"{symbol}_", "") for c in temp_X.columns]
            temp_y = y_train_wide[symbol]
            
            combined = pd.concat([temp_X, temp_y.rename('target')], axis=1).dropna()
            train_data.append(combined)
            
        if not train_data:
            continue
            
        train_panel = pd.concat(train_data).sort_index()
        if train_panel.empty:
            continue
            
        # Target Discretization: Convert continuous Sharpe to Quintiles (0-4) per date
        # This is required for LGBMRanker's lambdarank objective
        train_panel['target'] = train_panel.groupby(train_panel.index)['target'].transform(
            lambda x: pd.qcut(x, 5, labels=False, duplicates='drop')
        ).fillna(0).astype(int)
        
        # Model Training (Ranking)
        model = lgb.LGBMRanker(
            objective="lambdarank",
            n_estimators=100, 
            max_depth=5, 
            learning_rate=0.05, 
            verbosity=-1,
            random_state=42
        )
        
        # Calculate group counts (number of assets per date)
        groups = train_panel.index.value_counts().sort_index().values
        
        model.fit(
            train_panel.drop('target', axis=1), 
            train_panel['target'], 
            group=groups
        )
        
        # Prediction for T
        X_test_wide = pd.concat([X.loc[[t]], macro.loc[[t]]], axis=1)
        scores = {}
        for symbol in y.columns:
            sym_feat_cols = [c for c in X_test_wide.columns if c.startswith(f"{symbol}_")]
            macro_cols = list(macro.columns)
            
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
        
        # Save scores for factor analysis
        s_ser = pd.Series(scores).rename(t)
        all_scores.append(s_ser)

    if not all_weights:
        return pd.Series(), pd.Series()
        
    weights_df = pd.concat(all_weights, axis=1).T
    weights_df.index = pd.to_datetime(weights_df.index)
    
    # Compute returns
    daily_rets = close.pct_change().shift(-1) # return from T to T+1
    # Realign weights to apply from T+1 onwards
    portfolio_rets = (weights_df.reindex(daily_rets.index).ffill() * daily_rets).sum(axis=1)
    
    # Format scores for Alphalens (MultiIndex Series: [date, asset])
    scores_df = pd.concat(all_scores, axis=1).T
    scores_df.index = pd.to_datetime(scores_df.index)
    scores_ser = scores_df.stack().swaplevel().sort_index()
    scores_ser.index.names = ['date', 'asset'] # Standard Alphalens format
    
    return portfolio_rets.loc[rebalance_dates[0]:], scores_ser

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
    ml_returns, ml_scores = run_ml_rolling_backtest(prices)
    
    # 4. Generating Reports
    if not ml_returns.empty:
        print("\n[3/3] Generating performance reports...")
        # Ensure float dtype for QuantStats
        ml_returns = ml_returns.astype(float)
        all_results = {'LightGBM_MVP': ml_returns}
        generate_reports(all_results, output_dir='reports_ml')
        
        # New: Generate Alphalens Factor Analysis
        if not ml_scores.empty:
            generate_factor_report(ml_scores, prices)
            
        print("\nPipeline execution complete. Reports saved in 'reports_ml/' directory.")
    else:
        print("\nError: ML backtest produced no returns. Check train_window and data availability.")

if __name__ == "__main__":
    main()
