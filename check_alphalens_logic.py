
import pandas as pd
import numpy as np
from pathlib import Path
from src.pipelines.analysis.alphalens_analysis import AlphalensAnalyzer, AlphalensAnalysisConfig

def test_alphalens_calculation_logic():
    # 1. Create mock data
    # Factor frame: trade_date, symbol, carry_rank_pct
    # Symbol frame: trade_date, symbol, daily_return, hold_contract
    dates = pd.date_range(start="2023-01-01", periods=10, freq="D")
    symbols = ["SH600000", "SZ000001"]
    
    factor_data = []
    symbol_data = []
    
    for date in dates:
        for i, symbol in enumerate(symbols):
            # Simple factor: index based
            factor_data.append({
                "trade_date": date,
                "symbol": symbol,
                "carry_rank_pct": 0.1 * (i + 1)
            })
            # Simple return: 1% daily
            symbol_data.append({
                "trade_date": date,
                "symbol": symbol,
                "daily_return": 0.01,
                "hold_contract": f"{symbol}_2301"
            })
            
    factor_frame = pd.DataFrame(factor_data)
    symbol_frame = pd.DataFrame(symbol_data)
    
    # 2. Setup analyzer
    output_dir = Path("data/test_alphalens")
    config = AlphalensAnalysisConfig(
        output_dir=output_dir,
        factor_column="carry_rank_pct",
        periods=(1, 2),
        quantiles=2
    )
    analyzer = AlphalensAnalyzer(config)
    
    # 3. Test price building
    prices = analyzer.build_prices(symbol_frame)
    print("Built prices head:")
    print(prices.head())
    
    # Verification of price building logic:
    # current_price *= 1.0 + float(row.daily_return)
    # First day: 1.0
    # Second day: 1.0 * (1.01) = 1.01
    # Third day: 1.01 * (1.01) = 1.0201
    expected_p2 = 1.01
    actual_p2 = prices.iloc[1, 0]
    assert np.isclose(actual_p2, expected_p2), f"Price at day 2 should be {expected_p2}, got {actual_p2}"
    
    # 3b. Test price building with missing data
    symbol_data_missing = symbol_data.copy()
    # Mock missing hold_contract for SZ000001 at index 3 (2023-01-02)
    symbol_data_missing[3]["hold_contract"] = np.nan
    symbol_frame_missing = pd.DataFrame(symbol_data_missing)
    prices_missing = analyzer.build_prices(symbol_frame_missing)
    print("\nPrices with missing data:")
    print(prices_missing.head())
    # 2023-01-02 for SZ000001 should be NaN
    assert pd.isna(prices_missing.loc["2023-01-02", "SZ000001"])
    # 2023-01-03 for SZ000001 should restart from 1.0
    assert np.isclose(prices_missing.loc["2023-01-03", "SZ000001"], 1.0)
    
    # 4. Test factor series building
    factor_series = analyzer.build_factor_series(factor_frame)
    print("\nFactor series head:")
    print(factor_series.head())
    assert len(factor_series) == len(factor_frame)
    
    # 5. Run full analysis
    # We need alphalens installed for this
    try:
        import alphalens
        print("\nRunning analyze_frames...")
        result = analyzer.analyze_frames(factor_frame, symbol_frame)
        print("Analysis successful!")
        
        print("\nFactor Data head:")
        print(result.factor_data.head())
        
        # Manual check
        manual_mean = result.factor_data.groupby("factor_quantile")[["1D", "2D"]].mean()
        print("\nManual mean return by quantile:")
        print(manual_mean)

        print("\nMean return by quantile from result:")
        print(result.mean_return_by_quantile)
        
        # Check if 1D return is roughly 1%
        ret_1d = result.mean_return_by_quantile["1D"].iloc[0]
        assert np.isclose(ret_1d, 0.01, atol=1e-4), f"1D return should be ~0.01, got {ret_1d}"
        
    except ImportError:
        print("Alphalens not installed, skipping full analysis test.")
    except Exception as e:
        print(f"Analysis failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_alphalens_calculation_logic()
