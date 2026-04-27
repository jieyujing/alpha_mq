"""
数据质量报告生成器
"""
from pathlib import Path
from datetime import datetime
import logging
import glob
import os

import pandas as pd

from pipelines.data_quality.checks import check_ohlcv_coverage


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
            # 单次读取文件，复用 DataFrame
            if f.endswith(".parquet"):
                df_sample = pd.read_parquet(f)
            else:
                df_sample = pd.read_csv(f)

            # 计算缺失值
            total_rows = len(df_sample)
            if total_rows > 0 and "close" in df_sample.columns:
                missing = df_sample["close"].isna().sum()
                total_missing_pct += round(missing / total_rows * 100, 2)

            # 检查重复行
            subset_cols = ["date"] if "date" in df_sample.columns else ["bob"]
            if all(col in df_sample.columns for col in subset_cols):
                total_duplicates += int(df_sample.duplicated(subset=subset_cols).sum())

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
                "missing_pct": None,
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
            "period_range": None,
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
            "score": None,
        }

    def run_all_checks(self) -> dict:
        """执行所有检查"""
        results = {
            "ohlcv": self._check_ohlcv(),
            "features": self._check_features(),
            "pit": self._check_pit(),
            "summary": self._generate_summary(),
        }

        # 计算整体评分
        results["summary"]["score"] = self._calculate_score(results)

        return results

    def _calculate_score(self, results: dict) -> int:
        """计算整体数据质量评分 (0-100)

        评分维度：
        - OHLCV 标的覆盖率：40%
        - Features 平均覆盖率：30%
        - PIT 标的覆盖率：20%
        - 数据质量（缺失值）：10%
        """
        # 1. OHLCV 覆盖率 (预期 1000 个标的)
        ohlcv_count = results["ohlcv"]["symbol_count"]
        ohlcv_score = min(ohlcv_count / 1000 * 100, 100)

        # 2. Features 平均覆盖率
        features = results["features"]
        feature_scores = [data["coverage"] for data in features.values()]
        avg_feature_score = sum(feature_scores) / len(feature_scores) if feature_scores else 0

        # 3. PIT 覆盖率
        pit_count = results["pit"]["symbol_count"]
        pit_score = min(pit_count / 1000 * 100, 100)

        # 4. 数据质量（缺失值占比越低越好）
        missing_pct = results["ohlcv"]["missing_pct"]
        quality_score = 100 - missing_pct

        # 综合评分
        total_score = (
            ohlcv_score * 0.4 +
            avg_feature_score * 0.3 +
            pit_score * 0.2 +
            quality_score * 0.1
        )

        return round(total_score)

    def generate_markdown(self, results: dict) -> str:
        """生成 Markdown 报告"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            "# CSI 1000 数据质量报告",
            "",
            f"**生成时间**: {now}",
            f"**数据目录**: {self.exports_base}, {self.qlib_output}",
            "",
            "---",
            "",
            "## 1. OHLCV 数据",
            "",
            "| 指标 | 值 |",
            "|------|-----|",
        ]

        ohlcv = results.get("ohlcv", {})
        lines.append(f"| 标的数量 | {ohlcv.get('symbol_count', 0)} |")
        lines.append(f"| 时间范围 | {ohlcv.get('min_date', '-')} ~ {ohlcv.get('max_date', '-')} |")
        lines.append(f"| 缺失值占比 | {ohlcv.get('missing_pct', 0)}% |")
        lines.append(f"| 重复行数 | {ohlcv.get('duplicate_count', 0)} |")

        lines.extend(["", "---", "", "## 2. Features 数据", "", "| 类别 | 标的覆盖率 |", "|------|-----------|"])

        features = results.get("features", {})
        for cat, data in features.items():
            lines.append(f"| {cat} | {data.get('coverage', 0)}% |")

        lines.extend(["", "---", "", "## 3. PIT 数据", "", "| 指标 | 值 |", "|------|-----|"])

        pit = results.get("pit", {})
        lines.append(f"| 标的数量 | {pit.get('symbol_count', 0)} |")

        lines.extend(["", "---", "", "## 4. Summary", "", "| 指标 | 值 |", "|------|-----|"])

        summary = results.get("summary", {})
        lines.append(f"| 总文件数 | {summary.get('total_files', 0)} |")
        lines.append(f"| 总大小 | {summary.get('total_size_mb', 0)} MB |")
        score = summary.get('score', '-')
        if score:
            lines.append(f"| 整体评分 | **{score}** |")
        else:
            lines.append(f"| 整体评分 | - |")

        lines.extend(["", "---", "", "*Generated by QualityReporter v1.0*"])

        return "\n".join(lines)

    def save_report(self) -> Path:
        """执行检查并保存报告"""
        self.qlib_output.mkdir(parents=True, exist_ok=True)

        results = self.run_all_checks()
        md_content = self.generate_markdown(results)

        self.report_path.write_text(md_content, encoding="utf-8")
        logging.info(f"Quality report saved: {self.report_path}")

        return self.report_path