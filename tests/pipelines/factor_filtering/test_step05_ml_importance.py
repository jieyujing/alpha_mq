import polars as pl
from src.pipelines.factor_filtering.steps.step05_ml_importance import MLImportance


def test_ml_importance():
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04"],
        "factor1": [1.0, 2.0, 3.0, 4.0],
        "factor2": [0.1, 0.2, 0.3, 0.4],
        "label_20d": [1.0, 0.0, 1.0, 0.0],
    })
    step = MLImportance()
    importance = step.evaluate_importance(df, ["factor1", "factor2"], "label_20d")
    assert "factor1" in importance
