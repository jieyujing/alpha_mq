import qlib
import pandas as pd
from qlib.constant import REG_CN
from qlib.workflow import R
from qlib.workflow.record_temp import PortAnaRecord

if __name__ == "__main__":
    provider_uri = "data/qlib_data"
    qlib.init(provider_uri=provider_uri, region=REG_CN)
    
    # Load prediction from latest run
    pred = pd.read_pickle("mlruns/1/8bbaf397375744d2a350d6c5461fdee3/artifacts/pred.pkl")
    
    # Configure backtest same as workflow_by_code.py
    port_analysis_config = {
        "executor": {
            "class": "SimulatorExecutor",
            "module_path": "qlib.backtest.executor",
            "kwargs": {
                "time_per_step": "day",
                "generate_portfolio_metrics": True,
            },
        },
        "strategy": {
            "class": "TopkDropoutStrategy",
            "module_path": "qlib.contrib.strategy.signal_strategy",
            "kwargs": {
                "signal": pred,  # Pass prediction directly
                "topk": 3,
                "n_drop": 1,
                "rebalance_period": 5,
            },
        },
        "backtest": {
            "start_time": "2024-01-01",
            "end_time": "2026-03-25",
            "account": 100000000,
            "benchmark": "SH000852",
            "exchange_kwargs": {
                "freq": "day",
                "limit_threshold": 0.095,
                "deal_price": "close",
                "open_cost": 0.0005,
                "close_cost": 0.0015,
                "min_cost": 5,
            },
        },
    }

    # Use a dummy recorder to capture artifacts
    with R.start(experiment_name="debug_backtest"):
        recorder = R.get_recorder()
        par = PortAnaRecord(recorder, port_analysis_config, "day")
        print("Starting Portfolio Analysis Record...")
        par.generate()
        print("Done!")
