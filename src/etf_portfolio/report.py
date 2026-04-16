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
