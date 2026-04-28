import polars as pl
from src.pipelines.factor_filtering.steps.step02_profiling import FactorProfiler


def test_factor_profiler():
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-01"],
        "instrument": ["A", "B"],
        "factor1": [1.0, 2.0],
        "label_20d": [0.05, 0.10],
    })
    step = FactorProfiler(label_col="label_20d")
    metrics = step.compute_ic(df, "factor1")
    assert "rank_ic" in metrics
