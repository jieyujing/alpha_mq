# tests/pipelines/test_base.py
import pytest
from pipelines.base import DataPipeline


class MockPipeline(DataPipeline):
    def __init__(self, config):
        super().__init__(config)
        self.called = []

    def download(self):
        self.called.append("download")

    def validate(self):
        return []

    def clean(self):
        self.called.append("clean")

    def ingest_to_qlib(self):
        self.called.append("ingest")


def test_pipeline_flow():
    config = {"pipeline": {"name": "Mock", "stages": ["download", "clean"]}}
    pipeline = MockPipeline(config)
    pipeline.run()
    assert pipeline.called == ["download", "clean"]


class MockFactorPipeline(DataPipeline):
    """Mock pipeline with custom stages to test dynamic dispatch."""
    STAGE_METHOD_MAP = {
        "ingest_bin": "ingest_bin",
        "factor_compute": "factor_compute",
        "export": "export",
    }

    def __init__(self, config):
        super().__init__(config)
        self.called = []

    def download(self): ...
    def validate(self): return []
    def clean(self): ...
    def ingest_to_qlib(self): ...

    def ingest_bin(self):
        self.called.append("ingest_bin")

    def factor_compute(self):
        self.called.append("factor_compute")

    def export(self):
        self.called.append("export")


def test_custom_stage_dispatch():
    config = {"pipeline": {"name": "MockFactor", "stages": ["ingest_bin", "factor_compute"]}}
    pipeline = MockFactorPipeline(config)
    pipeline.run()
    assert pipeline.called == ["ingest_bin", "factor_compute"]


def test_custom_stage_all():
    config = {"pipeline": {"name": "MockFactor", "stages": ["ingest_bin", "factor_compute", "export"]}}
    pipeline = MockFactorPipeline(config)
    pipeline.run()
    assert pipeline.called == ["ingest_bin", "factor_compute", "export"]
