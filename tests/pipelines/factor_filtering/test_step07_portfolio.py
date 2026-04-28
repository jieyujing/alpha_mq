import polars as pl
from src.pipelines.factor_filtering.steps.step07_portfolio import PortfolioValidator


def test_portfolio_validation():
    dates = []
    instruments = []
    f1 = []
    label = []
    for d in range(20):
        for i in range(50):
            dates.append(f"2023-01-{d+1:02d}")
            instruments.append(f"INST_{i}")
            f1.append(float(i))
            label.append(float(i) / 50)

    df = pl.DataFrame({
        "datetime": dates,
        "instrument": instruments,
        "factor1": f1,
        "label_20d": label,
    })
    ic_metrics = {"factor1": {"mean_rank_ic": 0.05, "icir": 0.3}}
    step = PortfolioValidator()
    result, report = step.process(df, ic_metrics)
    assert "portfolios" in report
    assert "equal_weight" in report["portfolios"]
    assert "mean_ic" in report["portfolios"]["equal_weight"]
