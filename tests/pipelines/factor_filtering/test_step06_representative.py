import polars as pl
from src.pipelines.factor_filtering.steps.step06_representative import RepresentativeSelector


def test_representative_selection():
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-02"],
        "instrument": ["A", "B"],
        "f1": [1.0, 2.0],
        "f2": [1.1, 2.1],
        "f3": [5.0, 6.0],
        "label_20d": [0.01, 0.02],
    })
    clusters = {"f1": 0, "f2": 0, "f3": 1}
    ic_metrics = {
        "f1": {"icir": 0.5, "monotonicity": 0.3, "long_short": 0.01},
        "f2": {"icir": 0.3, "monotonicity": 0.2, "long_short": 0.005},
        "f3": {"icir": 0.8, "monotonicity": 0.6, "long_short": 0.03},
    }
    stability = {
        "f1": {"stability_score": 0.7},
        "f2": {"stability_score": 0.4},
        "f3": {"stability_score": 0.9},
    }

    step = RepresentativeSelector(n_per_cluster=1)
    result, report = step.process(df, clusters, ic_metrics, stability)
    assert report["selected_count"] == 2  # 2 clusters, 1 each
    assert "f1" in result.columns or "f2" in result.columns  # one from cluster 0
    assert "f3" in result.columns  # cluster 1's only factor
