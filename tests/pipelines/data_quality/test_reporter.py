"""QualityReporter 测试"""
import pytest
from pathlib import Path


def test_quality_reporter_init():
    """测试 QualityReporter 初始化"""
    from pipelines.data_quality.reporter import QualityReporter

    config = {
        "exports_base": "data/exports",
        "qlib_output": "data/qlib_output",
        "qlib_bin": "data/qlib_bin",
    }

    reporter = QualityReporter(config)

    assert reporter.exports_base == Path("data/exports")
    assert reporter.qlib_output == Path("data/qlib_output")
    assert reporter.qlib_bin == Path("data/qlib_bin")
    assert reporter.report_path == Path("data/qlib_output/quality_report.md")