"""
数据质量报告生成器
"""
from pathlib import Path
from datetime import datetime
import logging
import glob
import os

import pandas as pd

from pipelines.data_quality.checks import check_ohlcv_coverage, check_missing_values, check_duplicates


class QualityReporter:
    """数据质量报告生成器"""

    def __init__(self, config: dict):
        self.exports_base = Path(config.get("exports_base", "data/exports"))
        self.qlib_output = Path(config.get("qlib_output", "data/qlib_output"))
        self.qlib_bin = Path(config.get("qlib_bin", "data/qlib_bin"))
        self.report_path = self.qlib_output / "quality_report.md"

    def _check_ohlcv(self) -> dict:
        """检查 OHLCV 数据"""
        ohlcv_dir = self.exports_base / "history_1d"

        coverage = check_ohlcv_coverage(ohlcv_dir)

        # 统计缺失值和重复行（抽样检查）
        total_missing_pct = 0.0
        total_duplicates = 0

        files = glob.glob(str(ohlcv_dir / "*.csv")) + glob.glob(str(ohlcv_dir / "*.parquet"))
        sample_files = files[:10] if len(files) > 10 else files

        for f in sample_files:
            missing = check_missing_values(Path(f), ["close", "volume"])
            total_missing_pct += missing.get("close_missing_pct", 0)

            # 先读取文件检查列名
            if f.endswith(".parquet"):
                df_sample = pd.read_parquet(f)
            else:
                df_sample = pd.read_csv(f)

            subset_cols = ["date"] if "date" in df_sample.columns else ["bob"]
            dup = check_duplicates(Path(f), subset_cols)
            total_duplicates += dup.get("duplicate_count", 0)

        avg_missing_pct = round(total_missing_pct / len(sample_files), 2) if sample_files else 0

        return {
            "symbol_count": coverage["symbol_count"],
            "min_date": coverage["min_date"],
            "max_date": coverage["max_date"],
            "missing_pct": avg_missing_pct,
            "duplicate_count": total_duplicates,
        }

    def _check_features(self) -> dict:
        """检查估值/市值数据"""
        categories = ["valuation", "mktvalue", "basic"]
        ohlcv_dir = self.exports_base / "history_1d"

        # 获取 OHLCV 标的作为基准
        ohlcv_files = glob.glob(str(ohlcv_dir / "*.csv")) + glob.glob(str(ohlcv_dir / "*.parquet"))
        ohlcv_symbols = {Path(f).stem for f in ohlcv_files}

        results = {}
        for cat in categories:
            cat_dir = self.exports_base / cat
            if not cat_dir.exists():
                results[cat] = {"coverage": 0, "missing_pct": 100}
                continue

            cat_files = glob.glob(str(cat_dir / "*.csv"))
            cat_symbols = {Path(f).stem for f in cat_files}

            coverage = len(cat_symbols) / len(ohlcv_symbols) * 100 if ohlcv_symbols else 0
            results[cat] = {
                "coverage": round(coverage, 1),
                "missing_pct": 0,
            }

        return results

    def _check_pit(self) -> dict:
        """检查 PIT 数据"""
        pit_dir = self.qlib_output / "pit"

        if not pit_dir.exists():
            return {"symbol_count": 0, "period_range": None}

        # 统计标的目录数
        symbol_dirs = [d for d in pit_dir.iterdir() if d.is_dir()]

        return {
            "symbol_count": len(symbol_dirs),
            "period_range": "待计算",
        }

    def _generate_summary(self) -> dict:
        """汇总统计"""
        # 计算总文件数和大小
        total_files = 0
        total_size = 0

        for dir_path in [self.exports_base, self.qlib_output, self.qlib_bin]:
            if dir_path.exists():
                for f in dir_path.rglob("*"):
                    if f.is_file():
                        total_files += 1
                        total_size += f.stat().st_size

        # 转换为 MB
        total_size_mb = round(total_size / (1024 * 1024), 2)

        return {
            "total_files": total_files,
            "total_size_mb": total_size_mb,
            "score": "待计算",
        }

    def run_all_checks(self) -> dict:
        """执行所有检查"""
        return {
            "ohlcv": self._check_ohlcv(),
            "features": self._check_features(),
            "pit": self._check_pit(),
            "summary": self._generate_summary(),
        }