import polars as pl
from src.pipelines.factor_filtering.steps.step02_profiling import SingleFactorProfiler


def test_ic_computation():
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-01", "2023-01-01"],
        "instrument": ["A", "B", "C"],
        "factor1": [1.0, 2.0, 3.0],
        "label_20d": [0.01, 0.02, 0.03],
    })
    step = SingleFactorProfiler(label_col="label_20d")
    result, metrics = step.process(df)
    assert "factor1" in metrics
    assert "mean_rank_ic" in metrics["factor1"]


def test_group_returns():
    df = pl.DataFrame({
        "datetime": ["2023-01-01"] * 10,
        "instrument": [f"INST_{i}" for i in range(10)],
        "factor1": [float(i) for i in range(10)],
        "label_20d": [float(i) / 10 for i in range(10)],
    })
    step = SingleFactorProfiler(label_col="label_20d")
    _, metrics = step.process(df)
    assert "group_returns" in metrics["factor1"]
