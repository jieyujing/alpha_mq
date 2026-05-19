from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from scipy.stats import spearmanr


class AlphalensReportGenerator:
    """
    Generates a premium research-style PDF report for Alphalens analysis results.
    """

    def __init__(self, output_dir: Path | str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Deep blue professional palette
        self.colors = {
            "primary": "#1f77b4",
            "secondary": "#aec7e8",
            "accent": "#ff7f0e",
            "positive": "#d62728",  # Red for high quantile usually means short if factor is neg
            "negative": "#2ca02c",  # Green
            "table_header": "#1f77b4",
            "table_row_even": "#f2f2f2",
            "table_row_odd": "#ffffff",
            "text": "#333333",
        }
        # Thresholds for Viability
        self.thresholds = {
            "ic_ir": 0.4,
            "ic_mean": 0.02,
            "monotonicity": 0.7,
            "net_ic": 0.02,
            "sharpe": 1.0,
        }

    def generate_report(
        self,
        factor_data: pd.DataFrame,
        ic: pd.DataFrame,
        returns: pd.DataFrame,
        periods: list[int] | tuple[int, ...],
    ) -> Path:
        """
        Main entry point to generate the PDF report for multiple periods.
        """
        pdf_path = self.output_dir / "alphalens_premium_report.pdf"

        with PdfPages(pdf_path) as pdf:
            for p in periods:
                period_col = f"{p}D"
                if period_col not in ic.columns:
                    continue

                # 1. Preparations & Calculations for this period
                metrics = self._calculate_all_metrics(factor_data, ic, returns, period_col)
                linear_analysis = self._calculate_linear_analysis(
                    factor_data, period_col, metrics["direction"]
                )

                # Page 1: Summary Table
                self._draw_summary_page(pdf, metrics, p)

                # Page 2: IC Performance
                self._draw_ic_page(pdf, ic[period_col], metrics, p)

                # Page 3: Group Returns
                self._draw_returns_page(pdf, factor_data, period_col, metrics, p)

                # Page 4: Linear Analysis
                self._draw_linear_page(pdf, linear_analysis, p)

        return pdf_path

    def _calculate_all_metrics(
        self, factor_data: pd.DataFrame, ic: pd.DataFrame, returns: pd.DataFrame, period_col: str
    ) -> dict[str, Any]:
        """Calculates custom metrics for the summary table."""
        ic_series = ic[period_col]
        ic_mean = ic_series.mean()
        direction = 1 if ic_mean >= 0 else -1

        # Aligned IC
        aligned_ic = ic_series * direction
        ic_ir = aligned_ic.mean() / aligned_ic.std()
        t_stat = ic_ir * np.sqrt(len(aligned_ic))

        # Win Rate (Sym)
        # Returns for factor direction
        f_ret = returns[period_col]
        win_rate_sym = (f_ret * direction > 0).mean()
        win_rate_orig = (f_ret > 0).mean() if direction == 1 else (f_ret < 0).mean()

        # Monotonicity
        # mean return by quantile
        q_mean_ret = factor_data.groupby("factor_quantile")[period_col].mean()
        mono_score, _ = spearmanr(q_mean_ret.index, q_mean_ret.values)
        if direction == -1:
            mono_score = -mono_score

        # L/S Sharpe
        # Cumulative spread return
        q_max = factor_data["factor_quantile"].max()
        factor_data.reset_index().pivot(
            index="date", columns="asset", values=period_col
        )  # Simplified
        # Actually Alphalens factor_returns is already calculated
        # Let's use factor_data to compute long-short daily returns
        daily_q_ret = factor_data.groupby(["date", "factor_quantile"])[period_col].mean().unstack()
        ls_daily = (daily_q_ret[q_max] - daily_q_ret[1]) * direction
        ls_ann_ret = ls_daily.mean() * 252
        ls_sharpe = (ls_daily.mean() / ls_daily.std()) * np.sqrt(252) if ls_daily.std() != 0 else 0

        # Net IC
        net_ic = aligned_ic.mean()

        # Viable
        viable = (
            abs(ic_ir) > self.thresholds["ic_ir"]
            and abs(ic_mean) > self.thresholds["ic_mean"]
            and mono_score > self.thresholds["monotonicity"]
            and net_ic > self.thresholds["net_ic"]
            and ls_sharpe > self.thresholds["sharpe"]
        )

        return {
            "ic_mean": ic_mean,
            "abs_ic_mean": abs(ic_mean),
            "ic_ir": ic_ir,
            "abs_ic_ir": abs(ic_ir),
            "t_stat": t_stat,
            "win_rate": win_rate_orig,
            "win_rate_sym": win_rate_sym,
            "direction": direction,
            "ic_gt_02": (aligned_ic.abs() > 0.02).mean(),
            "n_periods": len(aligned_ic),
            "monotonicity": mono_score,
            "ls_ann_ret": ls_ann_ret,
            "ls_sharpe": ls_sharpe,
            "avg_turnover": 0,  # Placeholder if not provided
            "net_ic": net_ic,
            "viable": "✓ Yes" if viable else "✗ No",
            "period_col": period_col,
        }

    def _calculate_linear_analysis(
        self, factor_data: pd.DataFrame, period_col: str, direction: int
    ) -> pd.DataFrame:
        """Bins |factor| and calculates metrics per bin."""
        df = factor_data.copy()
        df["abs_factor"] = df["factor"].abs()

        # Dynamically get the number of quantiles from the data
        n_bins = int(df["factor_quantile"].max())

        # Bins of absolute factor strength
        df["abs_bin"] = df.groupby(level="date")["abs_factor"].transform(
            lambda x: pd.qcut(x, n_bins, labels=False, duplicates="drop") + 1
        )

        results = []
        # 'All' bin
        results.append(self._get_bin_metrics(df, period_col, direction, "All"))

        # Per bin - dynamically loop through detected bins
        for b in range(1, n_bins + 1):
            bin_data = df[df["abs_bin"] == b]
            if not bin_data.empty:
                results.append(self._get_bin_metrics(bin_data, period_col, direction, f"bin_{b}"))

        return pd.DataFrame(results)

    def _get_bin_metrics(
        self, data: pd.DataFrame, period_col: str, direction: int, name: str
    ) -> dict[str, Any]:
        # IC
        pearson = data["factor"].corr(data[period_col])
        rank_ic = data["factor"].corr(data[period_col], method="spearman")

        # Win% (Aligned)
        aligned_ret = data[period_col] * direction
        win_rate = (aligned_ret > 0).mean()

        # Realized(bp)
        realized_bp = aligned_ret.mean() * 10000

        # Odds (Profit Factor)
        pos_sum = aligned_ret[aligned_ret > 0].sum()
        neg_sum = abs(aligned_ret[aligned_ret < 0].sum())
        odds = pos_sum / neg_sum if neg_sum != 0 else np.inf

        return {
            "Bin": name,
            "IC": pearson,
            "RankIC": rank_ic,
            "Win%": win_rate * 100,
            "Realized(bp)": realized_bp,
            "Odds": odds,
        }

    def _draw_summary_page(self, pdf: PdfPages, m: dict[str, Any], period: int):
        fig = plt.figure(figsize=(11.69, 8.27))  # A4 Landscape
        plt.axis("off")

        # Title
        plt.text(
            0.05,
            0.95,
            f"Summary Analysis ({period}D Horizon)",
            fontsize=24,
            fontweight="bold",
            color=self.colors["primary"],
        )

        # Table data
        data = [
            ["IC Mean", f"{m['ic_mean']:.4f}", "|IC Mean|", f"{m['abs_ic_mean']:.4f}"],
            ["ICIR", f"{m['ic_ir']:.4f}", "|ICIR|", f"{m['abs_ic_ir']:.4f}"],
            ["t-stat", f"{m['t_stat']:.2f}", "Win Rate", f"{m['win_rate'] * 100:.1f}%"],
            [
                "Win Rate(sym)",
                f"{m['win_rate_sym'] * 100:.1f}%",
                "Direction",
                f"{m['direction']} ({'long' if m['direction'] == 1 else 'short'})",
            ],
            ["|IC|>0.02", f"{m['ic_gt_02'] * 100:.1f}%", "n_periods", f"{m['n_periods']}"],
            [
                "Monotonicity",
                f"{m['monotonicity']:.3f}",
                "L/S Ann.Ret",
                f"{m['ls_ann_ret'] * 100:.1f}%",
            ],
            ["L/S Sharpe", f"{m['ls_sharpe']:.3f}", "Avg Turnover", "N/A"],
            ["Net IC", f"{m['net_ic']:.4f}", "Viable", m["viable"]],
        ]

        # Render table
        # [left, bottom, width, height] - use more conservative margins
        table_ax = fig.add_axes([0.1, 0.1, 0.8, 0.7])
        table_ax.axis("off")

        # Explicit column widths to ensure it fits (total should be <= 1.0)
        col_widths = [0.22, 0.28, 0.22, 0.28]

        table = table_ax.table(
            cellText=data,
            colLabels=["Metric", "Value", "Metric", "Value"],
            loc="center",
            cellLoc="left",
            colColours=[self.colors["table_header"]] * 4,
            colWidths=col_widths,
        )

        table.auto_set_font_size(False)
        table.set_fontsize(11)
        # Reduced width scale from 1.2 to 1.0, and height scale slightly
        table.scale(1.0, 2.2)

        # Style headers
        for (row, col), cell in table.get_celld().items():
            if row == 0:
                cell.set_text_props(color="white", fontweight="bold")
                cell.set_edgecolor("white")
            else:
                cell.set_edgecolor("#dddddd")
                if row % 2 == 0:
                    cell.set_facecolor(self.colors["table_row_even"])

        pdf.savefig(fig)
        plt.close(fig)

    def _draw_ic_page(self, pdf: PdfPages, ic_series: pd.Series, m: dict[str, Any], period: int):
        fig = plt.figure(figsize=(11.69, 8.27))
        gs = gridspec.GridSpec(2, 1, height_ratios=[1, 1], hspace=0.3)

        # Header
        plt.figtext(
            0.05,
            0.95,
            f"IC Performance ({period}D)",
            fontsize=20,
            fontweight="bold",
            color=self.colors["primary"],
            ha="left",
        )
        plt.figtext(
            0.5, 0.92, f"IC Series ({period}D)", fontsize=14, fontweight="bold", ha="center"
        )
        plt.figtext(
            0.5,
            0.89,
            f"ICIR={m['ic_ir']:.3f}  WinRate={m['win_rate_sym'] * 100:.1f}%  t={m['t_stat']:.2f}",
            fontsize=11,
            ha="center",
        )

        # 1. IC Time Series
        ax_ts = fig.add_subplot(gs[0])
        dates = ic_series.index
        # Bars: Positive Red, Negative Blue (matching theme)
        colors = [self.colors["positive"] if x > 0 else self.colors["primary"] for x in ic_series]
        ax_ts.bar(dates, ic_series, color=colors, alpha=0.3, width=2)

        # Rolling Mean
        rolling_ic = ic_series.rolling(window=12).mean()
        ax_ts.plot(dates, rolling_ic, color="black", label="Rolling 12d", linewidth=1.5)

        # Mean line
        mean_val = ic_series.mean()
        ax_ts.axhline(
            mean_val, color="red", linestyle="-.", label=f"Mean={mean_val:.4f}", alpha=0.7
        )
        ax_ts.axhline(0, color="gray", linestyle="--", linewidth=0.8)

        ax_ts.set_ylabel("RankIC")
        ax_ts.legend(loc="upper left", fontsize=9)
        ax_ts.grid(True, alpha=0.2)

        # 2. Cumulative IC
        ax_cum = fig.add_subplot(gs[1], sharex=ax_ts)
        cum_ic = ic_series.cumsum()
        ax_cum.plot(dates, cum_ic, color=self.colors["primary"], linewidth=2)
        ax_cum.fill_between(dates, 0, cum_ic, color=self.colors["primary"], alpha=0.1)
        ax_cum.axhline(0, color="gray", linestyle="--", linewidth=0.8)
        ax_cum.set_ylabel("Cumulative IC")
        ax_cum.grid(True, alpha=0.2)

        pdf.savefig(fig)
        plt.close(fig)

    def _draw_returns_page(
        self,
        pdf: PdfPages,
        factor_data: pd.DataFrame,
        period_col: str,
        m: dict[str, Any],
        period: int,
    ):
        fig = plt.figure(figsize=(11.69, 8.27))
        gs = gridspec.GridSpec(2, 1, height_ratios=[1, 1], hspace=0.4)

        plt.figtext(
            0.05,
            0.95,
            f"Group Returns ({period}D)",
            fontsize=20,
            fontweight="bold",
            color=self.colors["primary"],
            ha="left",
        )
        plt.figtext(
            0.5, 0.92, f"Group Returns ({period}D)", fontsize=14, fontweight="bold", ha="center"
        )
        plt.figtext(0.5, 0.89, "Cumulative Group Returns", fontsize=10, ha="center")

        # 1. Cumulative Returns
        ax_cum = fig.add_subplot(gs[0])
        daily_q_ret = factor_data.groupby(["date", "factor_quantile"])[period_col].mean().unstack()
        cum_q_ret = (1 + daily_q_ret).cumprod() - 1

        for q in daily_q_ret.columns:
            ax_cum.plot(cum_q_ret.index, cum_q_ret[q] * 100, label=f"G{q}", alpha=0.8)

        # Long/Short on secondary axis
        ax_ls = ax_cum.twinx()
        q_max = daily_q_ret.columns.max()
        ls_daily = (daily_q_ret[q_max] - daily_q_ret[1]) * m["direction"]
        ls_cum = (1 + ls_daily).cumprod() - 1
        ax_ls.plot(
            ls_cum.index,
            ls_cum * 100,
            color="black",
            linestyle="--",
            label="L/S(G1-GN)",
            linewidth=2,
        )

        ax_cum.set_ylabel("Cumulative Return (%)")
        ax_ls.set_ylabel("Long/Short Return (%)")
        ax_cum.axhline(0, color="gray", linestyle="--", alpha=0.5)

        # Combined legend - Adjust ncol for more groups (e.g. 10 groups + spread)
        lines1, labels1 = ax_cum.get_legend_handles_labels()
        lines2, labels2 = ax_ls.get_legend_handles_labels()
        ncol = min(8, len(labels1) + len(labels2))
        ax_cum.legend(lines1 + lines2, labels1 + labels2, loc="lower left", ncol=ncol, fontsize=7)
        ax_cum.grid(True, alpha=0.2)

        # 2. Annualized Return Bar Chart
        ax_bar = fig.add_subplot(gs[1])
        ann_ret = daily_q_ret.mean() * 252 * 100
        ls_ann = m["ls_ann_ret"] * 100

        x_labels = [f"G{q}" for q in ann_ret.index] + ["long_short"]
        x_values = list(ann_ret.values) + [ls_ann]
        colors = [
            self.colors["primary"] if i < len(ann_ret) else "#333333" for i in range(len(x_values))
        ]
        # Special color for negative return
        for i, val in enumerate(x_values):
            if val < 0:
                colors[i] = self.colors["positive"]

        bars = ax_bar.bar(x_labels, x_values, color=colors, alpha=0.8, width=0.6)
        ax_bar.axhline(0, color="gray", linestyle="--", alpha=0.5)
        ax_bar.set_ylabel("Ann. Return (%)")
        ax_bar.set_title(f"Monotonicity = {m['monotonicity']:.3f}", fontsize=10)

        # Add values on top
        for bar in bars:
            height = bar.get_height()
            ax_bar.text(
                bar.get_x() + bar.get_width() / 2.0,
                height + 0.1 if height > 0 else height - 0.5,
                f"{height:.1f}%",
                ha="center",
                va="bottom" if height > 0 else "top",
                fontsize=8,
            )

        pdf.savefig(fig)
        plt.close(fig)

    def _draw_linear_page(self, pdf: PdfPages, df: pd.DataFrame, period: int):
        fig = plt.figure(figsize=(11.69, 8.27))

        plt.figtext(
            0.05,
            0.95,
            f"Linear Analysis ({period}D)",
            fontsize=20,
            fontweight="bold",
            color=self.colors["primary"],
            ha="left",
        )
        plt.figtext(0.5, 0.92, f"Linear Analysis ({period}D Horizon)", fontsize=10, ha="center")

        gs = gridspec.GridSpec(2, 3, height_ratios=[1, 1], hspace=0.4, wspace=0.3)

        # 1. Pearson IC
        ax1 = fig.add_subplot(gs[0, 0])
        colors = ["gray"] + [
            self.colors["positive"] if v < 0 else self.colors["primary"] for v in df["IC"][1:]
        ]
        ax1.bar(df["Bin"], df["IC"], color=colors)
        ax1.set_title("Pearson IC", fontsize=10)
        ax1.tick_params(axis="x", rotation=45, labelsize=7)
        ax1.grid(alpha=0.2)

        # 2. Rank IC
        ax2 = fig.add_subplot(gs[0, 1])
        colors_rank = ["gray"] + [
            self.colors["positive"] if v < 0 else self.colors["primary"] for v in df["RankIC"][1:]
        ]
        ax2.bar(df["Bin"], df["RankIC"], color=colors_rank)
        ax2.set_title("Rank IC", fontsize=10)
        ax2.tick_params(axis="x", rotation=45, labelsize=7)
        ax2.grid(alpha=0.2)

        # 3. Win Rate
        ax3 = fig.add_subplot(gs[0, 2])
        ax3.bar(df["Bin"], df["Win%"], color=self.colors["primary"], alpha=0.8)
        ax3.set_title("Win Rate (%)", fontsize=10)
        ax3.tick_params(axis="x", rotation=45, labelsize=7)
        ax3.grid(alpha=0.2)

        # 4. Detailed Table
        table_ax = fig.add_subplot(gs[1, :])
        table_ax.axis("off")

        # Format values for table
        table_data = []
        for _, row in df.iterrows():
            table_data.append(
                [
                    row["Bin"],
                    f"{row['IC']:.3f}",
                    f"{row['RankIC']:.3f}",
                    f"{row['Win%']:.3f}",
                    f"{row['Realized(bp)']:.3f}",
                    f"{row['Odds']:.3f}",
                ]
            )

        table = table_ax.table(
            cellText=table_data,
            colLabels=["Bin", "IC", "RankIC", "Win%", "Realized(bp)", "Odds"],
            loc="center",
            cellLoc="center",
            colColours=[self.colors["table_header"]] * 6,
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)  # Slightly smaller font for more rows
        # Dynamic height scale: more rows need smaller vertical scaling
        h_scale = max(1.2, 2.5 - (len(df) * 0.1))
        table.scale(1, h_scale)

        # Style table
        for (row, col), cell in table.get_celld().items():
            if row == 0:
                cell.set_text_props(color="white", fontweight="bold")
            elif row % 2 == 0:
                cell.set_facecolor(self.colors["table_row_even"])

        pdf.savefig(fig)
        plt.close(fig)
