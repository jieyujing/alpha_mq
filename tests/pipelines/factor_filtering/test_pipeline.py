import yaml
from src.pipelines.factor_filtering.pipeline import FactorFilteringPipeline


def test_pipeline_initialization():
    with open("configs/factor_filtering.yaml") as f:
        config = yaml.safe_load(f)
    pipeline = FactorFilteringPipeline(config)
    assert pipeline.config is not None
    assert len(pipeline.stages) == 11
    assert "ring0_qa" in pipeline.stages
    assert "ring8_ml" in pipeline.stages
