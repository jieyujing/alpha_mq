import polars as pl
from src.pipelines.factor_filtering.steps.step05_clustering import FactorClustering


def test_factor_clustering():
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-01", "2023-01-02", "2023-01-02", "2023-01-03", "2023-01-03"],
        "instrument": ["A", "B", "A", "B", "A", "B"],
        "label": [0.1, -0.1, 0.2, -0.2, 0.3, -0.3],
        "factor1": [1.0, -1.0, 2.0, -2.0, 3.0, -3.0],
        "factor2": [1.1, -1.1, 2.1, -2.1, 3.1, -3.1],
    })
    step = FactorClustering()
    clusters = step.fit_predict(df, ["factor1", "factor2"], "label")
    assert len(clusters) == 2
    assert "factor1" in clusters
    assert "factor2" in clusters
