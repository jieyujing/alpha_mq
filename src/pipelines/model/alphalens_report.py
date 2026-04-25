"""Alphalens tear sheet generation with factor analysis and backtest visualization."""
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import alphalens.performance as perf
import alphalens.plotting as plotting


def _get_fig(result):
    """Extract figure from plotting result (handles both single Axes and arrays)."""
    if hasattr(result, "__len__") and not hasattr(result, "figure"):
        return result[0].figure
    elif hasattr(result, "figure"):
        return result.figure
    return None


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
    except Exception as e:
        logging.warning(f"Alphalens get_clean_factor failed: {e}. Skipping tear sheet.")
        return None

    factor_data.to_csv(output_dir / "factor_data.csv")
    mean_ret, _ = perf.mean_return_by_quantile(factor_data)
    mean_ret.to_csv(output_dir / "quantile_returns.csv")

    # Compute portfolio returns from quantile data (using 1D for daily compounding)
    dates = sorted(factor_data.index.get_level_values("date").unique())
    n_q = int(factor_data["factor_quantile"].max())
    q_series = {}
    ew_s = pd.Series(dtype=float)

    for qi in range(1, n_q + 1):
        rets = []
        for dt in dates:
            dt_data = factor_data.xs(dt, level="date")
            q = dt_data["factor_quantile"]
            ret = dt_data["1D"].dropna()
            rets.append(ret[q == qi].mean())
        q_series[qi] = pd.Series(rets, index=dates, name=f"Q{qi}")

    ew_rets = []
    for dt in dates:
        dt_data = factor_data.xs(dt, level="date")
        ew_rets.append(dt_data["1D"].dropna().mean())
    ew_s = pd.Series(ew_rets, index=dates, name="EW")

    q_cum = {qi: (1 + q_series[qi].dropna()).cumprod() for qi in range(1, n_q + 1)}
    ew_cum = (1 + ew_s.dropna()).cumprod()
    ls_cum = q_cum[n_q] / q_cum[1]
    colors = plt.cm.RdYlGn(np.linspace(0.1, 0.9, n_q))

    # Generate PDF
    pdf_path = output_dir / "tear_sheet.pdf"
    figs_saved = 0

    with PdfPages(str(pdf_path)) as pdf:
        # ========== BACKTEST SECTION ==========

        # 1. Cumulative Returns (All Quantiles)
        fig, ax = plt.subplots(figsize=(16, 8))
        for qi in range(1, n_q + 1):
            ax.plot(q_cum[qi].index, q_cum[qi].values, label=f"Q{qi}", color=colors[qi - 1], linewidth=1.5)
        ax.plot(ew_cum.index, ew_cum.values, label="EW", color="black", linewidth=2, linestyle="--")
        ax.set_title("Cumulative Returns by Factor Quantile (1D Forward Returns)", fontsize=14)
        ax.legend(fontsize=9); ax.grid(True, alpha=0.3); fig.autofmt_xdate(); plt.tight_layout()
        pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

        # 2. Long-Short vs Equal Weight
        fig, ax = plt.subplots(figsize=(16, 6))
        ax.plot(ls_cum.index, ls_cum.values, label=f"Long-Short (Q{n_q}/Q1)", color="red", linewidth=2)
        ax.plot(ew_cum.index, ew_cum.values, label="Equal Weight", color="blue", linewidth=2)
        ax.axhline(y=1, color="gray", linestyle=":", alpha=0.5)
        ax.set_title("Portfolio Cumulative Returns", fontsize=14)
        ax.legend(fontsize=10); ax.grid(True, alpha=0.3); fig.autofmt_xdate(); plt.tight_layout()
        pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

        # 3. Drawdown
        fig, ax = plt.subplots(figsize=(16, 6))
        for qi in range(1, n_q + 1):
            dd = _max_dd(q_cum[qi])
            ax.fill_between(dd.index, dd.values, 0, alpha=0.3, color=colors[qi - 1], label=f"Q{qi}")
        ax.plot(_max_dd(ew_cum).index, _max_dd(ew_cum).values, label="EW", color="black", linewidth=1.5)
        ax.set_title("Drawdown by Quantile", fontsize=14)
        ax.legend(fontsize=9); ax.grid(True, alpha=0.3); fig.autofmt_xdate(); plt.tight_layout()
        pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

        # 4. Monthly Returns Heatmap
        fig, axes = plt.subplots(2, 2, figsize=(20, 12))
        positions = [(0, 0, "Q1"), (0, 1, f"Q{n_q}"), (1, 0, "Long-Short"), (1, 1, "Equal Weight")]
        for r, c, name in positions:
            ax = axes[r, c]
            if "Long-Short" in name:
                data = (q_series[n_q].groupby([q_series[n_q].index.year, q_series[n_q].index.month]).apply(lambda x: (1 + x.dropna()).prod() - 1) / q_series[1].groupby([q_series[1].index.year, q_series[1].index.month]).apply(lambda x: (1 + x.dropna()).prod() - 1) - 1).unstack()
            elif "Equal Weight" in name:
                data = ew_s.groupby([ew_s.index.year, ew_s.index.month]).apply(lambda x: (1 + x.dropna()).prod() - 1).unstack()
            else:
                qi = int(name[1:])
                data = q_series[qi].groupby([q_series[qi].index.year, q_series[qi].index.month]).apply(lambda x: (1 + x.dropna()).prod() - 1).unstack()
            years = range(data.index.min(), data.index.max() + 1)
            grid = pd.DataFrame(index=years, columns=range(1, 13), dtype=float)
            for y, row in data.iterrows():
                for m, v in row.items():
                    grid.loc[y, m] = v
            vmin, vmax = grid.stack().quantile(0.05), grid.stack().quantile(0.95)
            im = ax.imshow(grid.values, cmap="RdYlGn", vmin=vmin, vmax=vmax, aspect="auto")
            ax.set_xticks(range(12))
            ax.set_xticklabels(["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"], fontsize=8)
            ax.set_yticks(range(len(years)))
            ax.set_yticklabels(list(years), fontsize=8)
            ax.set_title(name, fontsize=11)
            fig.colorbar(im, ax=ax, shrink=0.8)
        fig.suptitle("Monthly Returns Heatmap", fontsize=14, y=1.01)
        plt.tight_layout()
        pdf.savefig(fig, dpi=150, bbox_inches="tight"); figs_saved += 1; plt.close(fig)

        # 5. Annual Returns Bar Chart
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
        ax.set_xticklabels(list(annual_years))
        ax.set_title("Annual Returns by Quantile", fontsize=14)
        ax.legend(fontsize=9); ax.grid(True, alpha=0.3, axis="y")
        ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
        plt.tight_layout()
        pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

        # ========== FACTOR ANALYSIS SECTION ==========

        ic = perf.factor_information_coefficient(factor_data)

        fig = _get_fig(plotting.plot_ic_ts(ic))
        if fig:
            fig.set_size_inches(16, 10)
            pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

        fig = _get_fig(plotting.plot_ic_hist(ic))
        if fig:
            fig.set_size_inches(16, 10)
            pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

        fig = _get_fig(plotting.plot_ic_qq(ic))
        if fig:
            fig.set_size_inches(16, 10)
            pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

        mean_ret_q, std_ret_q = perf.mean_return_by_quantile(factor_data)
        fig = _get_fig(plotting.plot_mean_quantile_returns_spread_time_series(mean_ret_q, std_ret_q))
        if fig:
            fig.set_size_inches(16, 6)
            pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

        fig = _get_fig(plotting.plot_quantile_returns_bar(mean_ret_q))
        if fig:
            fig.set_size_inches(16, 10)
            pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

        try:
            mean_monthly_ic = perf.mean_information_coefficient(factor_data, by_time="ME")
            fig = _get_fig(plotting.plot_monthly_ic_heatmap(mean_monthly_ic))
            if fig:
                fig.set_size_inches(16, 8)
                pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)
        except Exception as e:
            logging.warning(f"Monthly IC heatmap failed: {e}")

        fig = _get_fig(plotting.plot_factor_rank_auto_correlation(perf.factor_rank_autocorrelation(factor_data)))
        if fig:
            fig.set_size_inches(16, 6)
            pdf.savefig(fig, dpi=150); figs_saved += 1; plt.close(fig)

    if figs_saved > 0:
        logging.info(f"Alphalens tear sheet saved to {pdf_path} ({figs_saved} pages)")
        return pdf_path
    logging.warning("No figures were saved to tear sheet.")
    return None
