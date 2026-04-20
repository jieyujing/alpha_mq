import pandas as pd
import numpy as np
import alphalens
import os
import matplotlib.pyplot as plt

# Patch for Pandas 3.0 compatibility with Alphalens
if not hasattr(pd.Index, 'tz'):
    def get_tz(self):
        return self.dtype.tz if hasattr(self.dtype, 'tz') else None
    pd.Index.tz = property(get_tz)

if not hasattr(pd.Index, 'freq'):
    def get_freq(self):
        return getattr(self, 'inferred_freq', None)
    pd.Index.freq = property(get_freq)

def generate_factor_report(factor_scores: pd.Series, prices: pd.DataFrame, output_dir: str = 'reports_ml/alphalens'):
    """
    Generate Alphalens factor analysis report.
    
    Args:
        factor_scores: MultiIndex Series (date, asset)
        prices: MultiIndex DataFrame (symbol, field)
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    print(f"\n[Alphalens] Generating factor analysis report in {output_dir}...")
    
    # 1. Prepare prices (Close only, symbols as columns)
    prices_close = prices.xs('close', level='field', axis=1)
    
    # 2. Get clean factor data
    # Holding periods: 1, 5, 20 days
    try:
        # Pre-process factor_scores to ensure it's sorted and has correct names
        # Standard Alphalens format is (date, asset), but we used (date, asset) in ml_strategy.py
        # Wait, in ml_strategy.py: scores_ser = scores_df.stack().swaplevel().sort_index()
        # scores_ser.index.names = ['date', 'asset']
        # This is correct.
        
        factor_data = alphalens.utils.get_clean_factor_and_forward_returns(
            factor=factor_scores,
            prices=prices_close,
            periods=[1, 5, 20],
            quantiles=5,
            filter_zscore=None # ETFs often have high overlap, zscore might be too aggressive
        )
        
        # 3. Generate Tear Sheets
        # Plot 1: Information Coefficient
        plt.figure(figsize=(12, 8))
        alphalens.plotting.plot_ic_hist(alphalens.performance.factor_information_coefficient(factor_data))
        plt.savefig(os.path.join(output_dir, 'ic_histogram.png'))
        plt.close()
        
        # Plot 2: Cumulative Returns by Quantile
        plt.figure(figsize=(12, 8))
        alphalens.plotting.plot_cumulative_returns_by_quantile(
            alphalens.performance.mean_return_by_quantile(factor_data)[0]
        )
        plt.savefig(os.path.join(output_dir, 'quantile_returns.png'))
        plt.close()
        
        # Plot 3: IC by Time
        plt.figure(figsize=(12, 8))
        alphalens.plotting.plot_ic_ts(alphalens.performance.factor_information_coefficient(factor_data))
        plt.savefig(os.path.join(output_dir, 'ic_time_series.png'))
        plt.close()
        
        # 4. Summary Stats
        ic = alphalens.performance.factor_information_coefficient(factor_data)
        summary = pd.DataFrame({
            'IC Mean': ic.mean(),
            'IC Std': ic.std(),
            'IR': ic.mean() / ic.std(),
            'Rank IC Mean': ic.mean() # Alphalens uses spearman by default
        })
        summary.to_csv(os.path.join(output_dir, 'factor_summary.csv'))
        
        print(f"[Alphalens] Tear sheet plots saved to {output_dir}")
        
    except Exception as e:
        print(f"[Alphalens] Error generating report: {e}")
        import traceback
        traceback.print_exc()
