"""
数据质量报告生成器
"""
from pathlib import Path
from datetime import datetime
import logging


class QualityReporter:
    """数据质量报告生成器"""

    def __init__(self, config: dict):
        self.exports_base = Path(config.get("exports_base", "data/exports"))
        self.qlib_output = Path(config.get("qlib_output", "data/qlib_output"))
        self.qlib_bin = Path(config.get("qlib_bin", "data/qlib_bin"))
        self.report_path = self.qlib_output / "quality_report.md"