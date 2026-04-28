import polars as pl
from src.pipelines.factor_filtering.steps.step01_data_qa import DataQA


def test_data_qa_processing():
    df = pl.DataFrame({
        "datetime": ["2023-01-01"],
        "instrument": ["000001.SZ"],
        "factor1": [float("inf")],
        "label_20d": [0.05],
    })
    step = DataQA()
    result = step.process(df)
    assert result.filter(pl.col("factor1").is_infinite()).height == 0
