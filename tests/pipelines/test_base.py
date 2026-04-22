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