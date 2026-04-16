import quantstats as qs
import pandas as pd
import os
from typing import Dict

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
