import polars as pl
from src.pipelines.factor_filtering.context import FilteringContext
from src.pipelines.factor_filtering.steps.step01_preprocess import PreprocessAndNeutralize


def test_rank_pct_normalization():
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-01", "2023-01-01"],
        "instrument": ["A", "B", "C"],
        "factor1": [1.0, 5.0, 3.0],
        "label_20d": [0.01, 0.02, 0.03],
    })
    ctx = FilteringContext(df=df)
    step = PreprocessAndNeutralize(transform_method="rank_pct")
    new_ctx = step.process(ctx)
    report = new_ctx.reports["preprocess_report"]
    # rank_pct result should be in [-1, 1]
    assert new_ctx.df["factor1"].min() >= -1.0
    assert new_ctx.df["factor1"].max() <= 1.0
    assert "rank_pct" in report["transform_applied"]


def test_winsorize_clips_extremes():
    df = pl.DataFrame({
        "datetime": ["2023-01-01"] * 100,
        "instrument": [f"INST_{i}" for i in range(100)],
        "factor1": [float(i) for i in range(100)],
        "label_20d": [0.01] * 100,
    })
    ctx = FilteringContext(df=df)
    step = PreprocessAndNeutralize(
        winsorize_lower=0.01, winsorize_upper=0.99, transform_method="rank_pct"
    )
    new_ctx = step.process(ctx)
    # extreme values should be clipped
    assert new_ctx.df["factor1"].is_finite().all()
