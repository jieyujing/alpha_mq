"""Alphalens tear sheet generation with factor analysis and backtest visualization."""
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import alphalens.performance as perf
from pipelines.model.chart_adapter import ChartAdapter


def _max_dd(cum: pd.Series) -> pd.Series:
    """Compute max drawdown from cumulative returns."""
    return (cum / cum.cummax()) - 1


def generate_alphalens_tear_sheet(
    factor: pd.Series,
    prices: pd.DataFrame,
    output_dir: Path,
    periods: tuple = (1, 5, 10, 20),
    quantiles: int = 5,
) -> Path | None:
    """Generate comprehensive tear sheet PDF with factor analysis and backtest charts.

    Sections:
    1. Backtest: cumulative returns, drawdown, monthly heatmap, annual returns
    2. Factor Analysis: IC, returns spread, quantile analysis, autocorrelation

    Args:
        factor: MultiIndex Series (datetime, instrument) - model predictions.
        prices: DataFrame (datetime x instrument) - close prices.
        output_dir: Directory to save outputs.
        periods: Forward return periods for Alphalens.
        quantiles: Number of quantile groups.

    Returns:
        Path to the PDF file, or None if generation failed.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Prepare factor data
    factor = factor.copy()
    factor.index = factor.index.rename(["date", "asset"])
    factor = factor.sort_index()

    prices.index = pd.to_datetime(prices.index)
    prices = prices.sort_index()

    try:
        import alphalens
        factor_data = alphalens.utils.get_clean_factor_and_forward_returns(
            factor=factor,
            prices=prices,
            periods=periods,
            quantiles=quantiles,
            filter_zscore=None,
        )
        # Ensure date index is datetime type for alphalens functions
        factor_data.index = pd.MultiIndex.from_tuples(
            [(pd.Timestamp(d), a) for d, a in factor_data.index],
            names=['date', 'asset']
        )
    except Exception as e:
        logging.warning(f"Alphalens get_clean_factor failed: {e}. Skipping tear sheet.")
        return None

    factor_data.to_csv(output_dir / "factor_data.csv")
    mean_ret, _ = perf.mean_return_by_quantile(factor_data)
    mean_ret.to_csv(output_dir / "quantile_returns.csv")

    # Compute portfolio returns from quantile data. Only 1D forward returns are
    # daily-compoundable; longer forward returns are overlapping holding periods.
    dates = sorted(factor_data.index.get_level_values("date").unique())
    n_q = int(factor_data["factor_quantile"].max())
    colors = plt.cm.RdYlGn(np.linspace(0.1, 0.9, n_q))
    factor_periods = [p for p in ['1D', '5D', '10D', '20D'] if p in factor_data.columns]

    # Compute cumulative returns for all periods.
    # For non-daily periods, returns are overlapping holding periods.
    # We still compute cumulative product to show trend direction.
    q_cum_by_period = {}  # {period: {qi: cum_series}}
    ew_cum_by_period = {}
    ls_cum_by_period = {}

    for period in factor_periods:
        q_series = {}
        ew_rets = []

        for qi in range(1, n_q + 1):
            rets = []
            for dt in dates:
                dt_data = factor_data.xs(dt, level="date")
                q = dt_data["factor_quantile"]
                ret = dt_data[period].dropna()
                rets.append(ret[q == qi].mean())
            q_series[qi] = pd.Series(rets, index=dates, name=f"Q{qi}")

        for dt in dates:
            dt_data = factor_data.xs(dt, level="date")
            ew_rets.append(dt_data[period].dropna().mean())
        ew_s = pd.Series(ew_rets, index=dates, name="EW")

        q_cum_by_period[period] = {qi: (1 + q_series[qi].dropna()).cumprod() for qi in range(1, n_q + 1)}
        ew_cum_by_period[period] = (1 + ew_s.dropna()).cumprod()
        ls_cum_by_period[period] = q_cum_by_period[period][n_q] / q_cum_by_period[period][1]

    # Generate PDF
    pdf_path = output_dir / "tear_sheet.pdf"
    figs_saved = 0

    with PdfPages(str(pdf_path)) as pdf:
        # ========== BACKTEST SECTION ==========

        # 1. Cumulative Returns for all forward return periods
        for period in factor_periods:
            q_cum = q_cum_by_period[period]
            ew_cum = ew_cum_by_period[period]

            fig, ax = plt.subplots(figsize=(16, 8))
            for qi in range(1, n_q + 1):
                ax.plot(q_cum[qi].index, q_cum[qi].values, label=f"Q{qi}",
                       color=colors[qi - 1], linewidth=1.5)
            ax.plot(ew_cum.index, ew_cum.values, label="EW",
                   color="black", linewidth=2, linestyle="--")
            ax.set_title(f"Cumulative Returns by Factor Quantile ({period} Forward Returns)", fontsize=14)
            ax.legend(fontsize=9, loc='upper left')
            ax.grid(True, alpha=0.3)
            ax.set_ylabel("Cumulative Return")
            fig.autofmt_xdate()
            plt.tight_layout()
            pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

        # 2. Long-Short vs Equal Weight for all forward return periods
        for period in factor_periods:
            ls_cum = ls_cum_by_period[period]
            ew_cum = ew_cum_by_period[period]

            fig, ax = plt.subplots(figsize=(16, 6))
            ax.plot(ls_cum.index, ls_cum.values, label=f"Long-Short (Q{n_q}/Q1)",
                   color="red", linewidth=2)
            ax.plot(ew_cum.index, ew_cum.values, label="Equal Weight",
                   color="blue", linewidth=2)
            ax.axhline(y=1, color="gray", linestyle=":", alpha=0.5)
            ax.set_title(f"Portfolio Cumulative Returns ({period})", fontsize=14)
            ax.legend(fontsize=10)
            ax.grid(True, alpha=0.3)
            ax.set_ylabel("Cumulative Return")
            fig.autofmt_xdate()
            plt.tight_layout()
            pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

        # 3. Drawdown for 1D only (keep single page)
        period = '1D'
        if period in q_cum_by_period:
            q_cum = q_cum_by_period[period]
            ew_cum = ew_cum_by_period[period]

            fig, ax = plt.subplots(figsize=(16, 6))
            for qi in range(1, n_q + 1):
                dd = _max_dd(q_cum[qi])
                ax.fill_between(dd.index, dd.values, 0, alpha=0.3,
                               color=colors[qi - 1], label=f"Q{qi}")
            ax.plot(_max_dd(ew_cum).index, _max_dd(ew_cum).values,
                   label="EW", color="black", linewidth=1.5)
            ax.set_title("Drawdown by Quantile (1D)", fontsize=14)
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3)
            fig.autofmt_xdate()
            plt.tight_layout()
            pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

        # 4. Monthly Returns Heatmap for 1D (keep single page)
        period = '1D'
        if period in factor_data.columns:
            # Recompute q_series for monthly heatmap
            q_series = {}
            for qi in range(1, n_q + 1):
                rets = []
                for dt in dates:
                    dt_data = factor_data.xs(dt, level="date")
                    q = dt_data["factor_quantile"]
                    ret = dt_data[period].dropna()
                    rets.append(ret[q == qi].mean())
                q_series[qi] = pd.Series(rets, index=dates, name=f"Q{qi}")

            ew_rets = []
            for dt in dates:
                dt_data = factor_data.xs(dt, level="date")
                ew_rets.append(dt_data[period].dropna().mean())
            ew_s = pd.Series(ew_rets, index=dates, name="EW")

            fig, axes = plt.subplots(2, 2, figsize=(20, 12))
            positions = [(0, 0, "Q1"), (0, 1, f"Q{n_q}"), (1, 0, "Long-Short"), (1, 1, "Equal Weight")]
            for r, c, name in positions:
                ax = axes[r, c]
                if "Long-Short" in name:
                    ls_monthly = q_series[n_q].groupby([q_series[n_q].index.year, q_series[n_q].index.month]).apply(lambda x: (1 + x.dropna()).prod() - 1)
                    q1_monthly = q_series[1].groupby([q_series[1].index.year, q_series[1].index.month]).apply(lambda x: (1 + x.dropna()).prod() - 1)
                    data = (ls_monthly - q1_monthly).unstack()
                elif "Equal Weight" in name:
                    data = ew_s.groupby([ew_s.index.year, ew_s.index.month]).apply(lambda x: (1 + x.dropna()).prod() - 1).unstack()
                else:
                    qi = int(name[1:])
                    data = q_series[qi].groupby([q_series[qi].index.year, q_series[qi].index.month]).apply(lambda x: (1 + x.dropna()).prod() - 1).unstack()
                years = range(int(data.index.min()), int(data.index.max()) + 1)
                grid = pd.DataFrame(index=years, columns=range(1, 13), dtype=float)
                for y, row in data.iterrows():
                    for m, v in row.items():
                        if int(y) in years and int(m) in range(1, 13):
                            grid.loc[int(y), int(m)] = v
                vmin, vmax = float(grid.stack().quantile(0.05)), float(grid.stack().quantile(0.95))
                im = ax.imshow(grid.values, cmap="RdYlGn", vmin=vmin, vmax=vmax, aspect="auto")
                ax.set_xticks(range(12))
                ax.set_xticklabels(["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"], fontsize=8)
                ax.set_yticks(range(len(years)))
                ax.set_yticklabels([str(y) for y in years], fontsize=8)
                ax.set_title(name, fontsize=11)
                fig.colorbar(im, ax=ax, shrink=0.8)
            fig.suptitle("Monthly Returns Heatmap (1D)", fontsize=14, y=1.01)
            plt.tight_layout()
            pdf.savefig(fig, dpi=150, bbox_inches="tight"); figs_saved += 1; plt.close(fig)

        # 5. Annual Returns Bar Chart for 1D (keep single page)
        period = '1D'
        if period in factor_data.columns:
            # Use same q_series from above
            fig, ax = plt.subplots(figsize=(12, 6))
            annual_years = sorted(q_series[1].groupby(q_series[1].index.year).groups.keys())
            x = np.arange(len(annual_years))
            width = 0.15
            for i, qi in enumerate(range(1, n_q + 1)):
                vals = [q_series[qi].groupby(q_series[qi].index.year).apply(lambda x: (1 + x.dropna()).prod() - 1).get(y, 0) for y in annual_years]
                ax.bar(x + i * width, vals, width, label=f"Q{qi}", color=colors[i])
            ew_vals = [ew_s.groupby(ew_s.index.year).apply(lambda x: (1 + x.dropna()).prod() - 1).get(y, 0) for y in annual_years]
            ax.bar(x + n_q * width, ew_vals, width, label="EW", color="black", alpha=0.7)
            ax.set_xticks(x + n_q * width / 2)
            ax.set_xticklabels([str(y) for y in annual_years])
            ax.set_title("Annual Returns by Quantile (1D)", fontsize=14)
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3, axis="y")
            ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
            plt.tight_layout()
            pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

        # 6. Average forward returns by quantile for all available horizons
        non_daily_periods = [p for p in factor_periods if p != '1D']
        if non_daily_periods:
            mean_forward = pd.DataFrame(index=range(1, n_q + 1), columns=non_daily_periods, dtype=float)
            for period in non_daily_periods:
                for qi in range(1, n_q + 1):
                    q_mask = factor_data["factor_quantile"] == qi
                    mean_forward.loc[qi, period] = factor_data.loc[q_mask, period].mean()

            fig, ax = plt.subplots(figsize=(12, 6))
            x = np.arange(n_q)
            width = 0.8 / len(non_daily_periods)
            for i, period in enumerate(non_daily_periods):
                ax.bar(
                    x + (i - (len(non_daily_periods) - 1) / 2) * width,
                    mean_forward[period].values,
                    width,
                    label=period,
                )
            ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
            ax.set_xticks(x)
            ax.set_xticklabels([f"Q{qi}" for qi in range(1, n_q + 1)])
            ax.set_title("Average Forward Returns by Quantile", fontsize=14)
            ax.set_ylabel("Mean Forward Return")
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3, axis="y")
            plt.tight_layout()
            pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

        # ========== FACTOR ANALYSIS SECTION ==========

        ic = perf.factor_information_coefficient(factor_data)
        mean_ret_q, std_ret_q = perf.mean_return_by_quantile(factor_data)

        # Use ChartAdapter for bug-free plotting
        adapter = ChartAdapter()
        logging.info(f"ChartAdapter status: {adapter.get_status()}")

        # IC time series (alphalens - working)
        fig = adapter.plot_ic_ts(ic)
        if fig:
            pdf.savefig(fig, dpi=150, bbox_inches="tight"); figs_saved += 1; plt.close(fig)

        # IC histogram (custom - fixes empty axes bug)
        fig = adapter.plot_ic_hist(ic)
        if fig:
            pdf.savefig(fig, dpi=150, bbox_inches="tight"); figs_saved += 1; plt.close(fig)

        # IC Q-Q plot (custom - fixes empty axes bug)
        fig = adapter.plot_ic_qq(ic)
        if fig:
            pdf.savefig(fig, dpi=150, bbox_inches="tight"); figs_saved += 1; plt.close(fig)

        # Quantile returns spread (alphalens - working)
        fig = adapter.plot_mean_quantile_returns_spread(mean_ret_q, std_ret_q)
        if fig:
            pdf.savefig(fig, dpi=150, bbox_inches="tight"); figs_saved += 1; plt.close(fig)

        # Quantile returns bar (alphalens - working)
        fig = adapter.plot_quantile_returns_bar(mean_ret_q)
        if fig:
            pdf.savefig(fig, dpi=150, bbox_inches="tight"); figs_saved += 1; plt.close(fig)

        # Monthly IC heatmap (custom - fixes imshow bug)
        try:
            mean_monthly_ic = perf.mean_information_coefficient(factor_data, by_time="ME")
            fig = adapter.plot_monthly_ic_heatmap(mean_monthly_ic)
            if fig:
                pdf.savefig(fig, dpi=150, bbox_inches="tight"); figs_saved += 1; plt.close(fig)
        except Exception as e:
            logging.warning(f"Monthly IC heatmap failed: {e}")

        # Factor rank autocorrelation (alphalens - working)
        autocorr = perf.factor_rank_autocorrelation(factor_data)
        fig = adapter.plot_factor_rank_auto_correlation(autocorr)
        if fig:
            pdf.savefig(fig, dpi=150, bbox_inches="tight"); figs_saved += 1; plt.close(fig)

    if figs_saved > 0:
        logging.info(f"Alphalens tear sheet saved to {pdf_path} ({figs_saved} pages)")
        return pdf_path
    logging.warning("No figures were saved to tear sheet.")
    return None


# ============================================================================
# Multi-model tear sheet: one PDF per label, all models included
# ============================================================================


def _compute_quantile_series(factor_data: pd.DataFrame, dates: list, period: str, n_q: int):
    """Compute per-quantile daily returns, EW returns, and cumulative products.

    Returns:
        q_series: {qi: pd.Series of mean returns for quantile qi}
        ew_s: pd.Series of equal-weight mean returns
    """
    q_series = {}
    ew_rets = []

    for qi in range(1, n_q + 1):
        rets = []
        for dt in dates:
            dt_data = factor_data.xs(dt, level="date")
            q = dt_data["factor_quantile"]
            ret = dt_data[period].dropna()
            rets.append(ret[q == qi].mean())
        q_series[qi] = pd.Series(rets, index=dates, name=f"Q{qi}")

    for dt in dates:
        dt_data = factor_data.xs(dt, level="date")
        ew_rets.append(dt_data[period].dropna().mean())
    ew_s = pd.Series(ew_rets, index=dates, name="EW")

    return q_series, ew_s


def _generate_model_section(
    pdf: PdfPages,
    factor_data: pd.DataFrame,
    factor_name: str,
    model_name: str,
    label_name: str,
    quantiles: int = 5,
) -> dict:
    """Generate all tear sheet pages for one model factor within a multi-model PDF.

    Returns dict with factor_data, ic, mean_ret_q, std_ret_q, and backtest metrics.
    """
    figs_saved = 0
    dates = sorted(factor_data.index.get_level_values("date").unique())
    n_q = int(factor_data["factor_quantile"].max())
    colors = plt.cm.RdYlGn(np.linspace(0.1, 0.9, n_q))
    factor_periods = [p for p in ['1D', '5D', '10D', '20D'] if p in factor_data.columns]

    # Compute cumulative returns for all periods
    q_cum_by_period = {}
    ew_cum_by_period = {}
    ls_cum_by_period = {}

    for period in factor_periods:
        q_series, ew_s = _compute_quantile_series(factor_data, dates, period, n_q)
        q_cum_by_period[period] = {qi: (1 + q_series[qi].dropna()).cumprod() for qi in range(1, n_q + 1)}
        ew_cum_by_period[period] = (1 + ew_s.dropna()).cumprod()
        ls_cum_by_period[period] = q_cum_by_period[period][n_q] / q_cum_by_period[period][1]

    # ========== BACKTEST SECTION ==========

    # 1. Cumulative Returns for all forward return periods
    for period in factor_periods:
        q_cum = q_cum_by_period[period]
        ew_cum = ew_cum_by_period[period]

        fig, ax = plt.subplots(figsize=(16, 8))
        for qi in range(1, n_q + 1):
            ax.plot(q_cum[qi].index, q_cum[qi].values, label=f"Q{qi}",
                   color=colors[qi - 1], linewidth=1.5)
        ax.plot(ew_cum.index, ew_cum.values, label="EW",
               color="black", linewidth=2, linestyle="--")
        ax.set_title(f"[{factor_name}] Cumulative Returns by Factor Quantile ({period})", fontsize=14)
        ax.legend(fontsize=9, loc='upper left')
        ax.grid(True, alpha=0.3)
        ax.set_ylabel("Cumulative Return")
        fig.autofmt_xdate()
        plt.tight_layout()
        pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

    # 2. Long-Short vs Equal Weight for all forward return periods
    for period in factor_periods:
        ls_cum = ls_cum_by_period[period]
        ew_cum = ew_cum_by_period[period]

        fig, ax = plt.subplots(figsize=(16, 6))
        ax.plot(ls_cum.index, ls_cum.values, label=f"Long-Short (Q{n_q}/Q1)",
               color="red", linewidth=2)
        ax.plot(ew_cum.index, ew_cum.values, label="Equal Weight",
               color="blue", linewidth=2)
        ax.axhline(y=1, color="gray", linestyle=":", alpha=0.5)
        ax.set_title(f"[{factor_name}] Portfolio Cumulative Returns ({period})", fontsize=14)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.set_ylabel("Cumulative Return")
        fig.autofmt_xdate()
        plt.tight_layout()
        pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

    # 3. Drawdown for 1D only
    period = '1D'
    if period in q_cum_by_period:
        q_cum = q_cum_by_period[period]
        ew_cum = ew_cum_by_period[period]

        fig, ax = plt.subplots(figsize=(16, 6))
        for qi in range(1, n_q + 1):
            dd = _max_dd(q_cum[qi])
            ax.fill_between(dd.index, dd.values, 0, alpha=0.3,
                           color=colors[qi - 1], label=f"Q{qi}")
        ax.plot(_max_dd(ew_cum).index, _max_dd(ew_cum).values,
               label="EW", color="black", linewidth=1.5)
        ax.set_title(f"[{factor_name}] Drawdown by Quantile (1D)", fontsize=14)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        fig.autofmt_xdate()
        plt.tight_layout()
        pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

    # 4. Monthly Returns Heatmap for 1D
    period = '1D'
    if period in factor_data.columns:
        q_series, ew_s = _compute_quantile_series(factor_data, dates, period, n_q)

        fig, axes = plt.subplots(2, 2, figsize=(20, 12))
        positions = [(0, 0, "Q1"), (0, 1, f"Q{n_q}"), (1, 0, "Long-Short"), (1, 1, "Equal Weight")]
        for r, c, name in positions:
            ax = axes[r, c]
            if "Long-Short" in name:
                ls_monthly = q_series[n_q].groupby([q_series[n_q].index.year, q_series[n_q].index.month]).apply(lambda x: (1 + x.dropna()).prod() - 1)
                q1_monthly = q_series[1].groupby([q_series[1].index.year, q_series[1].index.month]).apply(lambda x: (1 + x.dropna()).prod() - 1)
                data = (ls_monthly - q1_monthly).unstack()
            elif "Equal Weight" in name:
                data = ew_s.groupby([ew_s.index.year, ew_s.index.month]).apply(lambda x: (1 + x.dropna()).prod() - 1).unstack()
            else:
                qi = int(name[1:])
                data = q_series[qi].groupby([q_series[qi].index.year, q_series[qi].index.month]).apply(lambda x: (1 + x.dropna()).prod() - 1).unstack()
            years = range(int(data.index.min()), int(data.index.max()) + 1)
            grid = pd.DataFrame(index=years, columns=range(1, 13), dtype=float)
            for y, row in data.iterrows():
                for m, v in row.items():
                    if int(y) in years and int(m) in range(1, 13):
                        grid.loc[int(y), int(m)] = v
            vmin, vmax = float(grid.stack().quantile(0.05)), float(grid.stack().quantile(0.95))
            im = ax.imshow(grid.values, cmap="RdYlGn", vmin=vmin, vmax=vmax, aspect="auto")
            ax.set_xticks(range(12))
            ax.set_xticklabels(["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"], fontsize=8)
            ax.set_yticks(range(len(years)))
            ax.set_yticklabels([str(y) for y in years], fontsize=8)
            ax.set_title(name, fontsize=11)
            fig.colorbar(im, ax=ax, shrink=0.8)
        fig.suptitle(f"[{factor_name}] Monthly Returns Heatmap (1D)", fontsize=14, y=1.01)
        plt.tight_layout()
        pdf.savefig(fig, dpi=150, bbox_inches="tight"); figs_saved += 1; plt.close(fig)

    # 5. Annual Returns Bar Chart for 1D
    period = '1D'
    if period in factor_data.columns:
        q_series, ew_s = _compute_quantile_series(factor_data, dates, period, n_q)

        fig, ax = plt.subplots(figsize=(12, 6))
        annual_years = sorted(q_series[1].groupby(q_series[1].index.year).groups.keys())
        x = np.arange(len(annual_years))
        width = 0.15
        for i, qi in enumerate(range(1, n_q + 1)):
            vals = [q_series[qi].groupby(q_series[qi].index.year).apply(lambda x: (1 + x.dropna()).prod() - 1).get(y, 0) for y in annual_years]
            ax.bar(x + i * width, vals, width, label=f"Q{qi}", color=colors[i])
        ew_vals = [ew_s.groupby(ew_s.index.year).apply(lambda x: (1 + x.dropna()).prod() - 1).get(y, 0) for y in annual_years]
        ax.bar(x + n_q * width, ew_vals, width, label="EW", color="black", alpha=0.7)
        ax.set_xticks(x + n_q * width / 2)
        ax.set_xticklabels([str(y) for y in annual_years])
        ax.set_title(f"[{factor_name}] Annual Returns by Quantile (1D)", fontsize=14)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis="y")
        ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
        plt.tight_layout()
        pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

    # 6. Average forward returns by quantile for non-daily periods
    non_daily_periods = [p for p in factor_periods if p != '1D']
    if non_daily_periods:
        mean_forward = pd.DataFrame(index=range(1, n_q + 1), columns=non_daily_periods, dtype=float)
        for period in non_daily_periods:
            for qi in range(1, n_q + 1):
                q_mask = factor_data["factor_quantile"] == qi
                mean_forward.loc[qi, period] = factor_data.loc[q_mask, period].mean()

        fig, ax = plt.subplots(figsize=(12, 6))
        x = np.arange(n_q)
        width = 0.8 / len(non_daily_periods)
        for i, period in enumerate(non_daily_periods):
            ax.bar(
                x + (i - (len(non_daily_periods) - 1) / 2) * width,
                mean_forward[period].values,
                width,
                label=period,
            )
        ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
        ax.set_xticks(x)
        ax.set_xticklabels([f"Q{qi}" for qi in range(1, n_q + 1)])
        ax.set_title(f"[{factor_name}] Average Forward Returns by Quantile", fontsize=14)
        ax.set_ylabel("Mean Forward Return")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis="y")
        plt.tight_layout()
        pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

    # ========== FACTOR ANALYSIS SECTION ==========

    ic = perf.factor_information_coefficient(factor_data)
    mean_ret_q, std_ret_q = perf.mean_return_by_quantile(factor_data)

    adapter = ChartAdapter()

    # IC time series
    fig = adapter.plot_ic_ts(ic)
    if fig:
        fig.suptitle(f"[{factor_name}] IC Time Series", fontsize=14, y=1.01)
        pdf.savefig(fig, dpi=150, bbox_inches="tight"); figs_saved += 1; plt.close(fig)

    # IC histogram
    fig = adapter.plot_ic_hist(ic)
    if fig:
        fig.suptitle(f"[{factor_name}] IC Distribution", fontsize=14, y=1.01)
        pdf.savefig(fig, dpi=150, bbox_inches="tight"); figs_saved += 1; plt.close(fig)

    # IC Q-Q plot
    fig = adapter.plot_ic_qq(ic)
    if fig:
        fig.suptitle(f"[{factor_name}] IC Normality Check", fontsize=14, y=1.01)
        pdf.savefig(fig, dpi=150, bbox_inches="tight"); figs_saved += 1; plt.close(fig)

    # Quantile returns spread
    fig = adapter.plot_mean_quantile_returns_spread(mean_ret_q, std_ret_q)
    if fig:
        fig.suptitle(f"[{factor_name}] Quantile Returns Spread", fontsize=14, y=1.01)
        pdf.savefig(fig, dpi=150, bbox_inches="tight"); figs_saved += 1; plt.close(fig)

    # Quantile returns bar
    fig = adapter.plot_quantile_returns_bar(mean_ret_q)
    if fig:
        fig.suptitle(f"[{factor_name}] Quantile Returns", fontsize=14, y=1.01)
        pdf.savefig(fig, dpi=150, bbox_inches="tight"); figs_saved += 1; plt.close(fig)

    # Monthly IC heatmap
    try:
        mean_monthly_ic = perf.mean_information_coefficient(factor_data, by_time="ME")
        fig = adapter.plot_monthly_ic_heatmap(mean_monthly_ic)
        if fig:
            fig.suptitle(f"[{factor_name}] Monthly IC Heatmap", fontsize=14, y=1.01)
            pdf.savefig(fig, dpi=150, bbox_inches="tight"); figs_saved += 1; plt.close(fig)
    except Exception as e:
        logging.warning(f"Monthly IC heatmap failed for {factor_name}: {e}")

    # Factor rank autocorrelation
    autocorr = perf.factor_rank_autocorrelation(factor_data)
    fig = adapter.plot_factor_rank_auto_correlation(autocorr)
    if fig:
        fig.suptitle(f"[{factor_name}] Factor Rank Autocorrelation", fontsize=14, y=1.01)
        pdf.savefig(fig, dpi=150, bbox_inches="tight"); figs_saved += 1; plt.close(fig)

    logging.info(f"[{factor_name}] alphalens section: {figs_saved} pages")

    # Compute summary metrics
    ic_mean = ic.mean() if hasattr(ic, 'mean') else {}
    metrics_summary = {}
    if hasattr(ic_mean, 'to_dict'):
        metrics_summary['ic_mean'] = ic_mean.to_dict()

    return {
        "factor_data": factor_data,
        "ic": ic,
        "mean_ret_q": mean_ret_q,
        "std_ret_q": std_ret_q,
        "metrics": metrics_summary,
        "figs_saved": figs_saved,
        "ew_cum_by_period": ew_cum_by_period,
    }


def _generate_title_page(pdf: PdfPages, label_name: str, results_with_data: list):
    """Generate the title/summary page for the multi-model tear sheet PDF."""
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.axis("off")

    lines = []
    lines.append(f"AlphaLens Tear Sheet")
    lines.append(f"Label: {label_name}")
    lines.append(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("Models Analyzed:")
    lines.append("")

    # Collect metrics for each model
    for r in results_with_data:
        sharpe = r.backtest_metrics.get("sharpe", np.nan)
        icir = abs(r.val_metrics.get("icir", np.nan))
        val_ic = r.val_mean_ic

        sharpe_str = f"{sharpe:.2f}" if not np.isnan(sharpe) else "N/A"
        icir_str = f"{icir:.2f}" if not np.isnan(icir) else "N/A"
        val_ic_str = f"{val_ic:.4f}"

        lines.append(f"  {r.model_name}")
        lines.append(f"    Val IC={val_ic_str}  ICIR={icir_str}  OOS Sharpe={sharpe_str}")
        lines.append("")

    text = "\n".join(lines)
    ax.text(0.05, 0.95, text, transform=ax.transAxes, fontsize=12,
            verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.3))
    plt.tight_layout()
    pdf.savefig(fig, dpi=150); plt.close(fig)


def _plot_model_comparison_ic(model_names: list[str], ic_means: list[float], label_name: str) -> plt.Figure:
    """Bar chart comparing IC means across models."""
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(model_names))
    bars = ax.bar(x, ic_means, color=plt.cm.RdYlGn(np.linspace(0.2, 0.8, len(model_names))), edgecolor='white')
    for i, (bar, v) in enumerate(zip(bars, ic_means)):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.002,
                f"{v:.4f}", ha='center', va='bottom', fontsize=9)
    ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(model_names, rotation=15, ha='right')
    ax.set_title(f"[{label_name}] Mean IC Comparison", fontsize=14)
    ax.set_ylabel("Mean IC")
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    return fig


def _plot_model_comparison_sharpe(model_names: list[str], sharpes: list[float], label_name: str) -> plt.Figure:
    """Bar chart comparing OOS Sharpe ratios across models."""
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(model_names))
    colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(model_names)))
    bars = ax.bar(x, sharpes, color=colors, edgecolor='white')
    for i, (bar, v) in enumerate(zip(bars, sharpes)):
        if not np.isnan(v):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                    f"{v:.2f}", ha='center', va='bottom', fontsize=9)
        else:
            ax.text(bar.get_x() + bar.get_width() / 2, 0, "N/A",
                    ha='center', va='top', fontsize=9, color='red')
    ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(model_names, rotation=15, ha='right')
    ax.set_title(f"[{label_name}] OOS Sharpe Comparison", fontsize=14)
    ax.set_ylabel("Sharpe Ratio")
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    return fig


def _plot_model_comparison_ew_overlay(all_ew_cum: dict[str, dict[str, pd.Series]], label_name: str, period: str = '1D') -> plt.Figure:
    """Overlay EW cumulative returns from all models on one chart."""
    fig, ax = plt.subplots(figsize=(14, 6))
    colors = plt.cm.tab10(np.linspace(0, 1, len(all_ew_cum)))
    for i, (name, data) in enumerate(all_ew_cum.items()):
        if period in data and len(data[period]) > 0:
            ax.plot(data[period].index, data[period].values, label=name,
                   color=colors[i], linewidth=2)
    ax.axhline(y=1, color="gray", linestyle=":", alpha=0.5)
    ax.set_title(f"[{label_name}] EW Cumulative Returns Comparison ({period})", fontsize=14)
    ax.set_ylabel("Cumulative Return")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    plt.tight_layout()
    return fig


def generate_multi_model_tear_sheet(
    label_name: str,
    results: list,
    prices: pd.DataFrame,
    output_dir: Path,
    periods: tuple = (1, 5, 10, 20),
    quantiles: int = 5,
) -> Optional[Path]:
    """Generate one comprehensive tear sheet PDF for all models of a given label.

    Args:
        label_name: Label identifier (e.g. "label_5d").
        results: List of TrainingResult objects for this label.
        prices: DataFrame (datetime x instrument) of close prices.
        output_dir: Directory to save outputs.
        periods: Forward return periods for Alphalens.
        quantiles: Number of quantile groups.

    Returns:
        Path to the PDF file, or None if generation failed.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Filter valid results
    valid_results = [r for r in results if not r.oriented_test_signal.empty]
    if not valid_results:
        logging.warning(f"No valid results for {label_name}. Skipping alphalens.")
        return None

    prices.index = pd.to_datetime(prices.index)
    prices = prices.sort_index()

    # Prepare each model's factor_data
    model_sections = []  # List of (factor_name, factor_data, result) tuples
    for r in valid_results:
        factor_name = f"{r.model_name}"
        factor = r.oriented_test_signal.copy()
        factor.index = factor.index.rename(["date", "asset"])
        factor = factor.sort_index()

        try:
            import alphalens
            factor_data = alphalens.utils.get_clean_factor_and_forward_returns(
                factor=factor,
                prices=prices,
                periods=periods,
                quantiles=quantiles,
                filter_zscore=None,
            )
            factor_data.index = pd.MultiIndex.from_tuples(
                [(pd.Timestamp(d), a) for d, a in factor_data.index],
                names=['date', 'asset']
            )
            model_sections.append((factor_name, factor_data, r))
        except Exception as e:
            logging.warning(f"Alphalens get_clean_factor failed for {factor_name}: {e}. Skipping.")

    if not model_sections:
        logging.warning(f"All alphalens computations failed for {label_name}.")
        return None

    pdf_path = output_dir / f"tear_sheet_{label_name}.pdf"
    total_figs = 0

    with PdfPages(str(pdf_path)) as pdf:
        # Title page
        _generate_title_page(pdf, label_name, valid_results)
        total_figs += 1

        # Per-model sections
        all_ew_cum = {}  # {factor_name: {period: cum_series}}
        ic_means = []
        sharpes = []
        model_names = []

        for factor_name, factor_data, r in model_sections:
            section_result = _generate_model_section(
                pdf, factor_data, factor_name, r.model_name, label_name, quantiles
            )
            total_figs += section_result["figs_saved"]
            all_ew_cum[factor_name] = section_result["ew_cum_by_period"]

            # Collect comparison data
            model_names.append(factor_name)
            ic_mean_dict = section_result["metrics"].get("ic_mean", {})
            ic_mean_val = ic_mean_dict.get('1D', np.nan) if isinstance(ic_mean_dict, dict) else np.nan
            ic_means.append(ic_mean_val)
            sharpe = r.backtest_metrics.get("sharpe", np.nan)
            sharpes.append(sharpe)

        # Cross-model comparison pages (only if 2+ models)
        if len(model_names) >= 2:
            # IC comparison
            if any(not np.isnan(v) for v in ic_means):
                fig = _plot_model_comparison_ic(model_names, ic_means, label_name)
                pdf.savefig(fig, dpi=150); total_figs += 1; plt.close(fig)

            # Sharpe comparison
            if any(not np.isnan(v) for v in sharpes):
                fig = _plot_model_comparison_sharpe(model_names, sharpes, label_name)
                pdf.savefig(fig, dpi=150); total_figs += 1; plt.close(fig)

            # EW overlay
            if all_ew_cum:
                fig = _plot_model_comparison_ew_overlay(all_ew_cum, label_name)
                pdf.savefig(fig, dpi=150); total_figs += 1; plt.close(fig)

    logging.info(f"Multi-model tear sheet saved to {pdf_path} ({total_figs} pages)")
    return pdf_path
