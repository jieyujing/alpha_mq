import polars as pl
from src.pipelines.factor_filtering.context import FilteringContext
from src.pipelines.factor_filtering.steps.step08_ml_importance import MLImportanceVerifier


def test_ml_importance():
    dates = []
    instruments = []
    f1 = []
    f2 = []
    label = []
    for d in range(10):
        for i in range(20):
            dates.append(f"2023-01-{d+1:02d}")
            instruments.append(f"INST_{i}")
            f1.append(float(i))
            f2.append(float(200 - i))
            label.append(float(i) / 20)

    df = pl.DataFrame({
        "datetime": dates,
        "instrument": instruments,
        "factor1": f1,
        "factor2": f2,
        "label_20d": label,
    })
    
    ctx = FilteringContext(df=df)
    
    step = MLImportanceVerifier(n_estimators=5)
    new_ctx = step.process(ctx)
    report = new_ctx.reports["ml_report"]
    assert "importance" in report
    assert "factor1" in report["importance"]
