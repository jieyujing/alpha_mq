import polars as pl
import pytest
from src.pipelines.factor_filtering.context import FilteringContext
from src.pipelines.factor_filtering.steps.step00_data_qa import DataAndLabelQA


def test_filtering_context_initialization():
    df = pl.DataFrame({
        "datetime": ["2023-01-01"],
        "instrument": ["000001.SZ"],
        "factor1": [1.0],
        "label_20d": [0.05],
    })
    config = {"min_coverage": 0.8}
    ctx = FilteringContext(df=df, config=config)
    assert ctx.df.height == 1
    assert ctx.config["min_coverage"] == 0.8
    assert isinstance(ctx.reports, dict)


def test_data_qa_with_context():
    # 测试有无穷大 (inf) 和全常数因子
    df = pl.DataFrame({
        "datetime": ["2023-01-01", "2023-01-02", "2023-01-03"],
        "instrument": ["A", "B", "C"],
        "factor_const": [1.0, 1.0, 1.0],
        "factor_inf": [float("inf"), 2.0, 3.0],
        "label_20d": [0.01, 0.02, 0.03],
    })
    
    ctx = FilteringContext(df=df, config={"min_coverage": 0.0})
    step = DataAndLabelQA(config={"min_coverage": 0.0})
    
    # 统一接口调用
    new_ctx = step.process(ctx)
    
    # 断言返回值是 FilteringContext 实例
    assert isinstance(new_ctx, FilteringContext)
    
    # 验证 inf 已经被清理
    assert new_ctx.df.filter(pl.col("factor_inf").is_infinite()).height == 0
    
    # 验证 QA 报告存在于 ctx.reports 中
    assert "qa_report" in new_ctx.reports
    assert "factor_const" in new_ctx.reports["qa_report"]["constant_factors"]
