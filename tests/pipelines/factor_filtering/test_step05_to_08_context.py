import polars as pl
import pytest
from src.pipelines.factor_filtering.context import FilteringContext
from src.pipelines.factor_filtering.steps.step05_clustering import FactorClustering
from src.pipelines.factor_filtering.steps.step06_representative import RepresentativeSelector
from src.pipelines.factor_filtering.steps.step07_portfolio import PortfolioValidator
from src.pipelines.factor_filtering.steps.step08_ml_importance import MLImportanceVerifier


def test_step05_to_step08_context_flow():
    # 模拟数据
    df = pl.DataFrame({
        "datetime": ["2023-01-01"] * 5 + ["2023-01-02"] * 5 + ["2023-01-03"] * 5,
        "instrument": ["A", "B", "C", "D", "E"] * 3,
        "factor1": [1.0, 2.0, 1.5, 2.5, 1.2, 2.2, 1.1, 2.1, 1.3, 2.3, 1.4, 2.4, 1.0, 2.0, 1.5],
        "factor2": [0.5, 0.4, 0.6, 0.7, 0.5, 0.3, 0.5, 0.6, 0.4, 0.2, 0.5, 0.6, 0.7, 0.5, 0.4],
        "label_20d": [0.01, 0.02, 0.015, 0.025, 0.012, 0.022, 0.011, 0.021, 0.013, 0.023, 0.014, 0.024, 0.010, 0.020, 0.015],
    })
    
    ctx = FilteringContext(df=df)
    
    # 准备前置数据
    ctx.ic_metrics = {
        "factor1": {"mean_rank_ic": 0.05, "monotonicity": 0.5, "long_short": 0.02, "n_days": 3},
        "factor2": {"mean_rank_ic": 0.02, "monotonicity": 0.2, "long_short": 0.01, "n_days": 3},
    }
    ctx.stability_report = {
        "factor1": {"stability_score": 0.8},
        "factor2": {"stability_score": 0.4},
    }
    
    # 1. Step 05: Clustering
    step05 = FactorClustering(config={"distance_threshold": 10.0}) # 阈值超大，合并到一起
    ctx = step05.process(ctx)
    assert isinstance(ctx, FilteringContext)
    assert "cluster_report" in ctx.reports
    
    # 2. Step 06: Representative Selection
    step06 = RepresentativeSelector(config={"n_per_cluster": 1})
    ctx = step06.process(ctx)
    assert isinstance(ctx, FilteringContext)
    assert "selection_report" in ctx.reports
    
    # 3. Step 07: Portfolio
    step07 = PortfolioValidator()
    ctx = step07.process(ctx)
    assert isinstance(ctx, FilteringContext)
    assert "portfolio_report" in ctx.reports
    
    # 4. Step 08: ML Importance
    step08 = MLImportanceVerifier(n_estimators=5, random_state=42)
    ctx = step08.process(ctx)
    assert isinstance(ctx, FilteringContext)
    assert "ml_report" in ctx.reports
