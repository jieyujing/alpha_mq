import polars as pl
from src.pipelines.factor_filtering.steps.step04_portfolio import PortfolioValidation


def test_portfolio_validation():
    df = pl.DataFrame({
        "datetime": ["2023-01-01"],
        "instrument": ["A"],
        "factor1": [1.0],
        "label_20d": [0.05],
    })
    step = PortfolioValidation()
    metrics = step.evaluate_portfolio(df, ["factor1"], "label_20d")
    assert "sharpe_ratio" in metrics
