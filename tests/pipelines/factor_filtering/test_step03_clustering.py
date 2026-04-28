import polars as pl
from src.pipelines.factor_filtering.steps.step03_clustering import FactorClustering


def test_factor_clustering():
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-02", "2023-01-03"],
        "factor1": [1.0, 2.0, 3.0],
        "factor2": [1.1, 2.1, 3.1],
    })
    step = FactorClustering()
    clusters = step.fit_predict(df, ["factor1", "factor2"])
    assert len(clusters) == 2
