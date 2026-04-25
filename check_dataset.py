import qlib
from qlib.constant import REG_CN
from qlib.utils import init_instance_by_config

CSI1000_MARKET = "all"
CSI1000_GBDT_TASK = {
    "dataset": {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "Alpha158",
                "module_path": "qlib.contrib.data.handler",
                "kwargs": {
                    "start_time": "2015-01-05",
                    "end_time": "2026-03-26",
                    "fit_start_time": "2015-01-05",
                    "fit_end_time": "2022-12-31",
                    "instruments": CSI1000_MARKET,
                    "filter_pipe": [
                        {
                            "filter_type": "ExpressionDFilter",
                            "rule_expression": "$volume > 0",
                            "filter_start_time": None,
                            "filter_end_time": None,
                            "keep": False,
                        }
                    ],
                },
            },
            "segments": {
                "train": ("2015-01-05", "2022-12-31"),
                "valid": ("2023-01-01", "2023-12-31"),
                "test": ("2024-01-01", "2026-03-25"),
            },
        },
    },
}

if __name__ == "__main__":
    provider_uri = "data/qlib_data"
    qlib.init(provider_uri=provider_uri, region=REG_CN)
    dataset = init_instance_by_config(CSI1000_GBDT_TASK["dataset"])
    df_train = dataset.prepare("train")
    print(f"Train size: {len(df_train)}")
    if len(df_train) > 0:
        print(df_train.head())
    
    df_test = dataset.prepare("test")
    print(f"Test size: {len(df_test)}")
