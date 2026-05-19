import polars as pl
from src.pipelines.factor_filtering.context import FilteringContext
from src.pipelines.factor_filtering.steps.step03_cs_filter import CrossSectionFilter


def test_filter_weak_factors():
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-02"],
        "instrument": ["A", "B"],
        "strong_factor": [1.0, 2.0],
        "weak_factor": [0.0, 0.0],
        "label_20d": [0.01, 0.02],
    })
    ic_metrics = {
        "strong_factor": {"mean_rank_ic": 0.05, "n_days": 2},
        "weak_factor": {"mean_rank_ic": 0.001, "n_days": 2},
    }
    ctx = FilteringContext(df=df)
    ctx.ic_metrics = ic_metrics
    
    step = CrossSectionFilter(min_abs_ic=0.02)
    new_ctx = step.process(ctx)
    report = new_ctx.reports["filter_report"]
    assert "weak_factor" not in new_ctx.df.columns
    assert "strong_factor" in new_ctx.df.columns
    assert report["rejected_count"] == 1


def test_no_filter_when_all_strong():
    df = pl.DataFrame({
        "datetime": ["2023-01-01"],
        "instrument": ["A"],
        "f1": [1.0],
        "label_20d": [0.01],
    })
    ic_metrics = {"f1": {"mean_rank_ic": 0.05, "n_days": 1}}
    ctx = FilteringContext(df=df)
    ctx.ic_metrics = ic_metrics
    
    step = CrossSectionFilter(min_abs_ic=0.02)
    new_ctx = step.process(ctx)
    report = new_ctx.reports["filter_report"]
    assert "f1" in new_ctx.df.columns
    assert report["retained_count"] == 1
