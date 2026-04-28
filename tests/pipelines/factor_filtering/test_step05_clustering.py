import polars as pl
from src.pipelines.factor_filtering.steps.step05_clustering import FactorClustering


def test_factor_clustering():
    dates = []
    instruments = []
    f1_vals = []
    f2_vals = []
    label_vals = []
    for d in range(30):
        for i in range(10):
            dates.append(f"2023-01-{d+1:02d}")
            instruments.append(f"INST_{i}")
            f1_vals.append(float(i))
            f2_vals.append(float(i) + 0.1)
            label_vals.append(float(i) / 10)

    df = pl.DataFrame({
        "datetime": dates,
        "instrument": instruments,
        "factor1": f1_vals,
        "factor2": f2_vals,
        "label_20d": label_vals,
    })
    step = FactorClustering()
    result, report = step.process(df)
    assert len(report["clusters"]) == 2
    assert report["n_clusters"] >= 1
