"""Alphalens tear sheet generation from model prediction signals."""
import logging
from pathlib import Path

import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import alphalens.performance as perf
import alphalens.plotting as plotting


def _save_plot(axes, pdf):
    """Save a plotting function's result to PDF, handling both single Axes and arrays."""
    if hasattr(axes, "__len__") and not hasattr(axes, "figure"):
        fig = axes[0].figure
    elif hasattr(axes, "figure"):
        fig = axes.figure
    else:
        return False
    if fig:
        fig.set_size_inches(16, 10)
        pdf.savefig(fig)
        plt.close(fig)
        return True
    return False


def generate_alphalens_tear_sheet(
    factor: pd.Series,
    prices: pd.DataFrame,
    output_dir: Path,
    periods: tuple = (1, 5, 10, 20),
    quantiles: int = 5,
) -> Path | None:
    """Generate Alphalens tear sheet PDF for model prediction signals.

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

    # Ensure prices index is datetime
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

    # Save factor data CSV
    factor_data.to_csv(output_dir / "factor_data.csv")

    # Save quantile returns CSV
    mean_ret, _ = perf.mean_return_by_quantile(factor_data)
    mean_ret.to_csv(output_dir / "quantile_returns.csv")

    # Generate PDF with all available plots
    pdf_path = output_dir / "tear_sheet.pdf"
    figs_saved = 0

    with PdfPages(str(pdf_path)) as pdf:
        ic = perf.factor_information_coefficient(factor_data)

        if _save_plot(plotting.plot_ic_ts(ic), pdf):
            figs_saved += 1
        if _save_plot(plotting.plot_ic_hist(ic), pdf):
            figs_saved += 1
        if _save_plot(plotting.plot_ic_qq(ic), pdf):
            figs_saved += 1

        mean_ret, std_ret = perf.mean_return_by_quantile(factor_data)
        if _save_plot(plotting.plot_mean_quantile_returns_spread_time_series(mean_ret, std_ret), pdf):
            figs_saved += 1
        if _save_plot(plotting.plot_quantile_returns_bar(mean_ret), pdf):
            figs_saved += 1
        if _save_plot(plotting.plot_quantile_returns_violin(mean_ret[["5D"]]), pdf):
            figs_saved += 1

        try:
            mean_monthly_ic = perf.mean_information_coefficient(factor_data, by_time="ME")
            if _save_plot(plotting.plot_monthly_ic_heatmap(mean_monthly_ic), pdf):
                figs_saved += 1
        except Exception as e:
            logging.warning(f"Monthly IC heatmap failed: {e}")

        try:
            factor_autocorr = perf.factor_rank_autocorrelation(factor_data)
            if _save_plot(plotting.plot_factor_rank_auto_correlation(factor_autocorr), pdf):
                figs_saved += 1
        except Exception as e:
            logging.warning(f"Autocorrelation plot failed: {e}")

        if _save_plot(plotting.plot_top_bottom_quantile_turnover(mean_ret, period=5), pdf):
            figs_saved += 1

    if figs_saved > 0:
        logging.info(f"Alphalens tear sheet saved to {pdf_path} ({figs_saved} pages)")
        return pdf_path
    logging.warning("No figures were saved to tear sheet.")
    return None
