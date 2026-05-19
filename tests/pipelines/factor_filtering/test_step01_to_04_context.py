import polars as pl
import pytest
from src.pipelines.factor_filtering.context import FilteringContext
from src.pipelines.factor_filtering.steps.step01_preprocess import PreprocessAndNeutralize
from src.pipelines.factor_filtering.steps.step02_profiling import SingleFactorProfiler
from src.pipelines.factor_filtering.steps.step03_cs_filter import CrossSectionFilter
from src.pipelines.factor_filtering.steps.step04_stability import StabilityChecker


def test_step01_to_step04_context_flow():
    # 准备测试数据
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-01", "2023-01-02", "2023-01-02", "2023-01-03", "2023-01-03"],
        "instrument": ["A", "B", "A", "B", "A", "B"],
        "factor1": [1.0, 2.0, 1.5, 2.5, 1.2, 2.2],
        "factor2": [0.1, 0.1, 0.1, 0.1, 0.1, 0.1],  # 常数/低方差因子在之后的 CS filter 中会被干掉，或者用来测试
        "label_20d": [0.01, 0.02, 0.015, 0.025, 0.012, 0.022],
    })
    
    ctx = FilteringContext(df=df, config={"n_groups": 2, "min_abs_ic": 0.0, "min_coverage": 0.0})
    
    # 1. Step 01: Preprocess
    step01 = PreprocessAndNeutralize()
    ctx = step01.process(ctx)
    assert isinstance(ctx, FilteringContext)
    assert "preprocess_report" in ctx.reports
    
    # 2. Step 02: Profiling
    step02 = SingleFactorProfiler(label_col="label_20d", config={"n_groups": 2})
    ctx = step02.process(ctx)
    assert isinstance(ctx, FilteringContext)
    assert len(ctx.ic_metrics) > 0
    assert "factor1" in ctx.ic_metrics
    
    # 3. Step 03: CrossSectionFilter
    step03 = CrossSectionFilter(config={"min_abs_ic": 0.1, "min_coverage": 0.5})
    ctx = step03.process(ctx)
    assert isinstance(ctx, FilteringContext)
    assert "filter_report" in ctx.reports
    # factor2 因为 IC 太低或没变动，可能会被淘汰
    
    # 4. Step 04: Stability
    step04 = StabilityChecker()
    ctx = step04.process(ctx)
    assert isinstance(ctx, FilteringContext)
    assert len(ctx.stability_report) > 0
