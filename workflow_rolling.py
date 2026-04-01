import qlib
import pandas as pd
from qlib.constant import REG_CN
from qlib.workflow import R
from qlib.utils import exists_qlib_data, init_instance_by_config
from qlib.contrib.model.gbdt import LGBModel
from qlib.contrib.strategy import TopkDropoutStrategy
from qlib.backtest import backtest, executor
from data.handler import EnhancedAlpha158Handler
from path_target import PathTargetConfig
import fire

class SignalModel:
    def __init__(self, signal):
        self.signal = signal
    def predict(self, dataset, segment="test"):
        return self.signal

def run_rolling(
    start_time="2020-01-01",
    end_time="2026-03-25",
    rolling_months=6,
    train_years=2,
    instruments="all",
    provider_uri="data/qlib_data",
):
    # 1. Init Qlib
    qlib.init(provider_uri=provider_uri, region=REG_CN)
    
    # Define rolling windows
    all_dates = pd.date_range(start=start_time, end=end_time, freq=f"{rolling_months}MS")
    all_predictions = []
    
    model_params = {
        "loss": "lambdarank",
        "objective": "lambdarank",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "verbosity": -1,
        "n_estimators": 500,
        "early_stopping_rounds": 50,
    }
    
    experiment_name = f"rolling_workflow_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}"
    
    for i, test_start in enumerate(all_dates):
        test_end = test_start + pd.DateOffset(months=rolling_months) - pd.DateOffset(days=1)
        train_end = test_start - pd.DateOffset(days=1)
        train_start = train_end - pd.DateOffset(years=train_years)
        
        if train_start < pd.to_datetime(start_time):
            train_start = pd.to_datetime(start_time)
            
        if test_start >= pd.to_datetime(end_time):
            break
            
        print(f"--- Rolling Window {i} ---")
        print(f"Train: {train_start.date()} to {train_end.date()}")
        print(f"Test:  {test_start.date()} to {test_end.date()}")
        
        # 2. Setup Handler
        target_cfg = PathTargetConfig(max_holding=10)
        handler = EnhancedAlpha158Handler(
            target_cfg=target_cfg,
            start_time=train_start.strftime('%Y-%m-%d'),
            end_time=test_end.strftime('%Y-%m-%d'),
            instruments=instruments
        )
        
        # 3. Setup Dataset
        dataset_config = {
            "class": "DatasetH",
            "module_path": "qlib.data.dataset",
            "kwargs": {
                "handler": handler,
                "segments": {
                    "train": (train_start.strftime('%Y-%m-%d'), train_end.strftime('%Y-%m-%d')),
                    "test": (test_start.strftime('%Y-%m-%d'), test_end.strftime('%Y-%m-%d')),
                },
            },
        }
        dataset = init_instance_by_config(dataset_config)
        
        # 4. Model Training
        model = LGBModel(**model_params)
        with R.start(experiment_name=experiment_name, recorder_name=f"window_{i}"):
            model.fit(dataset)
            pred = model.predict(dataset, segment="test")
            all_predictions.append(pred)
            
    # 5. Combined Predictions
    if not all_predictions:
        print("No predictions generated.")
        return
        
    full_pred = pd.concat(all_predictions).sort_index()
    full_pred = full_pred[~full_pred.index.duplicated(keep='first')]
    
    # 6. Backtesting
    print("Starting Backtest...")
    
    strategy_config = {
        "class": "TopkDropoutStrategy",
        "module_path": "qlib.contrib.strategy",
        "kwargs": {
            "model": SignalModel(full_pred),
            "topk": 50,
            "n_drop": 5,
        },
    }
    
    executor_config = {
        "class": "SimulatorExecutor",
        "module_path": "qlib.backtest.executor",
        "kwargs": {
            "time_per_step": "day",
            "generate_report": True,
        },
    }
    
    bt_start = all_dates[0].strftime('%Y-%m-%d')
    bt_end = end_time
    
    with R.start(experiment_name=experiment_name, recorder_name="backtest"):
        report_normal, positions_normal = backtest(
            server_config=None,
            strategy=strategy_config,
            executor=executor_config,
            start_time=bt_start,
            end_time=bt_end,
            account=100000000,
            benchmark="SH000852",
        )
        
        # 7. Analysis
        from qlib.contrib.report import analysis_model
        analysis_df = analysis_model.analyze_model_performance(full_pred, dataset, "test")
        print("Analysis Summary:")
        print(analysis_df.head())
        
        full_pred.to_pickle("predictions.pkl")
        report_normal.to_pickle("report.pkl")
        print("Workflow Complete.")

if __name__ == "__main__":
    fire.Fire(run_rolling)
