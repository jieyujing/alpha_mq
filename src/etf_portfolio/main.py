import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# Local imports
from src.etf_portfolio.gm_data import fetch_etf_history
from src.etf_portfolio.rolling import run_rolling_backtest
from src.etf_portfolio.report import generate_reports

try:
    from gm.api import set_token
except ImportError:
    set_token = lambda x: None

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
    # Look back 5 years
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=5*365)).strftime('%Y-%m-%d')
    
    # Models to compare
    models = ['EW', 'GMV', 'MaxSharpe', 'ERC', 'HRP', 'HERC', 'NCO']
    
    # Optional: Set token from env if available
    token = os.getenv('GM_TOKEN', '')
    if token:
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
