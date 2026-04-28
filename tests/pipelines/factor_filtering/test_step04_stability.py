import polars as pl
from src.pipelines.factor_filtering.steps.step04_stability import StabilityChecker


def test_stability_computation():
    dates = ["2020-06-01"] * 100 + ["2021-06-01"] * 100
    df = pl.DataFrame({
        "datetime": dates,
        "instrument": [f"INST_{i % 100}" for i in range(200)],
        "factor1": [float(i) for i in range(200)],
        "label_20d": [float(i) / 200 for i in range(200)],
    })
    step = StabilityChecker()
    result, stability = step.process(df)
    assert "factor1" in stability
    assert "stability_score" in stability["factor1"]
    assert "yearly_ic" in stability["factor1"]
