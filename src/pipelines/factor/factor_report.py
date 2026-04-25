# src/pipelines/factor/factor_report.py
"""生成因子质量报告（Markdown 格式）。"""
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd


# 因子分类规则
_FACTOR_CATEGORIES = {
    "momentum": ("MA", "SUMP", "SUMN", "SUMD"),
    "volatility": ("STD", "RSQR", "RESI"),
    "volume_price": ("CORR", "CNTP", "CNTN", "CNTD", "KUP", "KMID", "KLOW", "KHIG", "VMA"),
    "quantile": ("QTL", "MIN", "MAX"),
}

_EXTRA_PREFIXES = ("pe_", "pb_", "ps_", "pcf_", "tot_", "a_mv", "turn")


def _classify_factor(col: str) -> str:
    for cat, prefixes in _FACTOR_CATEGORIES.items():
        if col.startswith(prefixes):
            return cat
    if col.startswith(_EXTRA_PREFIXES):
        return "extra"
    return "other"


class FactorQualityReporter:
    """生成因子质量报告。

    报告内容:
    1. 因子质量统计: IC/ICIR/单调性分布, 过滤链漏斗, 按组对比
    2. Label 统计: 分布, 分位数, 因子-label 相关性
    """

    def __init__(self, output_path: str):
        self.output_path = Path(output_path)

    def generate(
        self,
        X_before: pd.DataFrame,
        X_after: pd.DataFrame,
        y: pd.Series,
        filter_artifacts: dict,
        filter_logs: list[str],
        all_labels: dict[str, pd.Series],
    ) -> Path:
        """生成报告并保存。"""
        lines = []
        lines.append("# Factor Quality Report")
        lines.append("")
        lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # -- Section 1: Filter Funnel --
        lines.extend(self._section_filter_funnel(filter_logs))

        # -- Section 2: Factor Quality Stats --
        lines.extend(self._section_factor_quality(X_before, X_after, filter_artifacts))

        # -- Section 3: Top Retained Factor Details --
        lines.extend(self._section_top_factors(X_after, filter_artifacts))

        # -- Section 4: Factor Group Breakdown --
        lines.extend(self._section_factor_groups(X_after))

        # -- Section 5: Redundant Pairs --
        lines.extend(self._section_redundant_pairs(filter_artifacts))

        # -- Section 6: Label Stats --
        lines.extend(self._section_label_stats(all_labels))

        # -- Section 7: Factor-Label Correlation --
        lines.extend(self._section_factor_label_corr(X_after, y))

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text("\n".join(lines), encoding="utf-8")
        logging.info(f"Factor quality report saved: {self.output_path}")
        return self.output_path

    def _section_filter_funnel(self, logs: list[str]) -> list[str]:
        """过滤链漏斗。"""
        lines = ["---", "", "## 1. Filter Funnel (过滤链漏斗)", ""]
        lines.append("| Step | Rows | Features |")
        lines.append("|------|------|----------|")
        for log in logs:
            parts = log.split("]")
            if len(parts) < 2:
                continue
            step_name = parts[0].lstrip("[")
            rest = parts[1].strip()
            lines.append(f"| {step_name} | {rest} |")
        lines.append("")
        return lines

    def _section_factor_quality(
        self, X_before: pd.DataFrame, X_after: pd.DataFrame, artifacts: dict
    ) -> list[str]:
        """因子质量统计。"""
        lines = ["---", "", "## 2. Factor Quality Statistics (因子质量统计)", ""]

        stats_key = "FactorQualityFilterStep.factor_stats"
        if stats_key in artifacts:
            stats = artifacts[stats_key]
            lines.append("### IC/ICIR/Monotonicity Distribution")
            lines.append("")
            lines.append("| Metric | Mean | Std | P25 | Median | P75 |")
            lines.append("|--------|------|-----|-----|--------|-----|")
            for col in ["ic_mean", "icir", "monotonicity"]:
                if col in stats.columns:
                    s = stats[col].dropna()
                    lines.append(
                        f"| {col} | {s.mean():.4f} | {s.std():.4f} | "
                        f"{s.quantile(0.25):.4f} | {s.median():.4f} | "
                        f"{s.quantile(0.75):.4f} |"
                    )
            lines.append("")

        lines.append("### Factor Pool Summary")
        lines.append("")
        lines.append(f"- **Total factors before filtering**: {X_before.shape[1]}")
        lines.append(f"- **Total factors after filtering**: {X_after.shape[1]}")
        lines.append(f"- **Retained rate**: {X_after.shape[1] / max(X_before.shape[1], 1) * 100:.1f}%")
        lines.append(f"- **Total samples**: {X_after.shape[0]}")
        lines.append("")

        return lines

    def _section_top_factors(
        self, X: pd.DataFrame, artifacts: dict
    ) -> list[str]:
        """保留因子详情：Top 15 按 |IC mean| 排序。"""
        lines = ["---", "", "## 3. Top Retained Factor Details (保留因子详情 Top 15)", ""]

        stats_key = "FactorQualityFilterStep.factor_stats"
        if stats_key not in artifacts:
            lines.append("*No factor stats available.*")
            lines.append("")
            return lines

        stats = artifacts[stats_key]
        retained = [c for c in X.columns if c in stats.index]
        if not retained:
            lines.append("*No retained factors found in stats.*")
            lines.append("")
            return lines

        top = stats.loc[retained].abs().sort_values("ic_mean", ascending=False).head(15)

        lines.append("| Rank | Factor | ic_mean | icir | monotonicity | sign_flip |")
        lines.append("|------|--------|---------|------|--------------|-----------|")
        for rank, (factor, row) in enumerate(top.iterrows(), 1):
            lines.append(
                f"| {rank} | {factor} | {row.get('ic_mean', 'N/A'): .4f} | "
                f"{row.get('icir', 'N/A'): .4f} | "
                f"{row.get('monotonicity', 'N/A'): .4f} | "
                f"{row.get('sign_flip_ratio', 'N/A'):.4f} |"
            )
        lines.append("")
        return lines

    def _section_factor_groups(self, X: pd.DataFrame) -> list[str]:
        """按因子类型分组统计。"""
        lines = ["---", "", "## 4. Factor Group Breakdown (因子类型分组)", ""]

        counts = {}
        for col in X.columns:
            cat = _classify_factor(col)
            counts[cat] = counts.get(cat, 0) + 1

        category_names = {
            "momentum": "Momentum/Trend",
            "volatility": "Volatility",
            "volume_price": "Volume-Price",
            "quantile": "Quantile/Extremes",
            "extra": "Extra Features",
            "other": "Other",
        }

        lines.append("| Category | Count | Factors |")
        lines.append("|----------|-------|---------|")
        for cat in ["momentum", "volatility", "volume_price", "quantile", "extra", "other"]:
            if cat in counts:
                cols = sorted([c for c in X.columns if _classify_factor(c) == cat])
                lines.append(f"| {category_names[cat]} | {counts[cat]} | {', '.join(cols)} |")
        lines.append("")
        return lines

    def _section_redundant_pairs(self, artifacts: dict) -> list[str]:
        """高相关因子对（冗余）。"""
        lines = ["---", "", "## 5. Highly Correlated Factor Pairs (高相关因子对)", ""]

        pairs_key = "DeduplicateStep.redundant_pairs"
        if pairs_key not in artifacts:
            lines.append("*No redundancy analysis available.*")
            lines.append("")
            return lines

        pairs_df = artifacts[pairs_key]
        if pairs_df is None or len(pairs_df) == 0:
            lines.append("*No highly correlated pairs found.*")
            lines.append("")
            return lines

        top10 = pairs_df.nlargest(10, "corr")
        lines.append("| Rank | Factor A | Factor B | |Correlation| |")
        lines.append("|------|----------|----------|---------------|")
        for rank, (_, row) in enumerate(top10.iterrows(), 1):
            lines.append(f"| {rank} | {row['a']} | {row['b']} | {row['corr']:.4f} |")
        lines.append("")
        return lines

    def _section_label_stats(self, all_labels: dict[str, pd.Series]) -> list[str]:
        """Label 统计。"""
        lines = ["---", "", "## 6. Label Statistics (标签统计)", ""]

        lines.append("| Label | Count | Mean | Std | Min | P25 | Median | P75 | Max |")
        lines.append("|-------|-------|------|-----|-----|-----|--------|-----|-----|")

        for name, lbl in sorted(all_labels.items()):
            s = lbl.dropna()
            lines.append(
                f"| {name} | {len(s)} | {s.mean():.6f} | {s.std():.6f} | "
                f"{s.min():.6f} | {s.quantile(0.25):.6f} | "
                f"{s.median():.6f} | {s.quantile(0.75):.6f} | "
                f"{s.max():.6f} |"
            )
        lines.append("")
        return lines

    def _section_factor_label_corr(
        self, X: pd.DataFrame, y: pd.Series
    ) -> list[str]:
        """因子-label 相关性 (top 20)。"""
        lines = ["---", "", "## 7. Top Factor-Label Correlations (因子-label 相关性 Top 20)", ""]

        corrs = {}
        for col in X.columns:
            valid = pd.concat([X[col], y], axis=1).dropna()
            if len(valid) > 10:
                corrs[col] = valid.iloc[:, 0].corr(valid.iloc[:, 1], method="spearman")

        if corrs:
            corr_series = pd.Series(corrs).dropna()
            top20 = corr_series.abs().nlargest(20)
            lines.append("| Rank | Factor | Correlation |")
            lines.append("|------|--------|-------------|")
            for rank, factor in enumerate(top20.index, 1):
                actual_corr = corr_series[factor]
                lines.append(f"| {rank} | {factor} | {actual_corr:.4f} |")
            lines.append("")

        return lines
