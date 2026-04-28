import pytest
from src.pipelines.factor_filtering.pipeline import FactorFilteringPipeline


def test_pipeline_initialization():
    pipeline = FactorFilteringPipeline(config_path="configs/factor_filtering.yaml")
    assert pipeline.config is not None
    assert len(pipeline.steps) == 0
