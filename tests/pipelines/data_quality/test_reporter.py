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


def test_check_ohlcv_method():
    """测试 _check_ohlcv 方法"""
    from pipelines.data_quality.reporter import QualityReporter

    config = {
        "exports_base": "data/exports",
        "qlib_output": "data/qlib_output",
    }

    reporter = QualityReporter(config)
    result = reporter._check_ohlcv()

    assert "symbol_count" in result
    assert "min_date" in result
    assert "max_date" in result


def test_run_all_checks():
    """测试 run_all_checks 返回完整结构"""
    from pipelines.data_quality.reporter import QualityReporter

    config = {
        "exports_base": "data/exports",
        "qlib_output": "data/qlib_output",
    }

    reporter = QualityReporter(config)
    results = reporter.run_all_checks()

    assert "ohlcv" in results
    assert "features" in results
    assert "pit" in results
    assert "summary" in results


def test_generate_markdown():
    """测试 Markdown 报告生成"""
    from pipelines.data_quality.reporter import QualityReporter

    config = {"exports_base": "data/exports", "qlib_output": "data/qlib_output"}
    reporter = QualityReporter(config)

    results = {
        "ohlcv": {"symbol_count": 100, "min_date": "2025-01-01", "max_date": "2025-04-22", "missing_pct": 0.1},
        "features": {"valuation": {"coverage": 99.5}},
        "pit": {"symbol_count": 98},
        "summary": {"total_files": 500, "total_size_mb": 100, "score": "A"},
    }

    md = reporter.generate_markdown(results)

    assert "# CSI 1000 数据质量报告" in md
    assert "OHLCV 数据" in md
    assert "标的数量" in md