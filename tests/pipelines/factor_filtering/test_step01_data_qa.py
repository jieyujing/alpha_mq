import polars as pl
from src.pipelines.factor_filtering.context import FilteringContext
from src.pipelines.factor_filtering.steps.step00_data_qa import DataAndLabelQA


def test_inf_replacement():
    df = pl.DataFrame({
        "datetime": ["2023-01-01"],
        "instrument": ["000001.SZ"],
        "factor1": [float("inf")],
        "label_20d": [0.05],
    })
    ctx = FilteringContext(df=df, config={"min_coverage": 0.0})
    step = DataAndLabelQA(config={"min_coverage": 0.0})
    new_ctx = step.process(ctx)
    assert new_ctx.df.filter(pl.col("factor1").is_infinite()).height == 0


def test_constant_factor_detection():
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-02", "2023-01-03"],
        "instrument": ["A", "B", "C"],
        "factor_const": [1.0, 1.0, 1.0],
        "factor_var": [1.0, 2.0, 3.0],
        "label_20d": [0.01, 0.02, 0.03],
    })
    ctx = FilteringContext(df=df)
    step = DataAndLabelQA()
    new_ctx = step.process(ctx)
    report = new_ctx.reports["qa_report"]
    assert "factor_const" in report["constant_factors"]
    assert "factor_var" not in report["constant_factors"]


def test_low_coverage_rejection():
    df = pl.DataFrame({
        "datetime": ["2023-01-01"] * 10 + ["2023-01-02"] * 10,
        "instrument": ["A", "B", "C", "D", "E"] * 4,
        "factor_good": [1.0] * 20,
        "factor_bad": [1.0] * 10 + [None] * 10,
        "label_20d": [0.01] * 20,
    })
    ctx = FilteringContext(df=df, config={"min_coverage": 0.8})
    step = DataAndLabelQA(config={"min_coverage": 0.8})
    new_ctx = step.process(ctx)
    assert "factor_bad" not in new_ctx.df.columns
    assert "factor_good" in new_ctx.df.columns
