"""Alphalens tear sheet generation from model prediction signals."""
import logging
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import alphalens


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
    mean_ret = alphalens.performance.mean_return_by_quantile(factor_data)[0]
    mean_ret.to_csv(output_dir / "quantile_returns.csv")

    # Generate PDF
    pdf_path = output_dir / "tear_sheet.pdf"
    with PdfPages(str(pdf_path)) as pdf:
        matplotlib.rcParams["figure.figsize"] = (16, 10)

        # Page 1: IC Analysis
        ic = alphalens.performance.factor_information_coefficient(factor_data)
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        try:
            alphalens.plotting.plot_ic_ts(ic, ax=axes[0, 0])
        except Exception:
            axes[0, 0].text(0.5, 0.5, "IC Time Series: N/A", ha="center", va="center")
        try:
            alphalens.plotting.plot_ic_hist(ic, ax=axes[0, 1])
        except Exception:
            axes[0, 1].text(0.5, 0.5, "IC Histogram: N/A", ha="center", va="center")
        try:
            alphalens.plotting.plot_ic_monthly(ic, ax=axes[1, 0])
        except Exception:
            axes[1, 0].text(0.5, 0.5, "IC Monthly: N/A", ha="center", va="center")
        fig.suptitle("Information Coefficient Analysis", fontsize=16)
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # Page 2: Quantile Analysis
        mean_ret_q, std_q = alphalens.performance.mean_return_by_quantile(factor_data)
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        try:
            alphalens.plotting.plot_quantile_average_cumulative_return(
                mean_ret_q, ax=axes[0, 0]
            )
        except Exception:
            axes[0, 0].text(0.5, 0.5, "Cumulative Returns: N/A", ha="center", va="center")
        try:
            alphalens.plotting.plot_cumulative_returns_by_quantile(
                mean_ret_q, ax=axes[0, 1]
            )
        except Exception:
            axes[0, 1].text(0.5, 0.5, "Quantile Returns: N/A", ha="center", va="center")
        try:
            alphalens.plotting.plot_mean_quantile_returns_spread_time_series(
                mean_ret_q, std_q, ax=axes[1, 0]
            )
        except Exception:
            axes[1, 0].text(0.5, 0.5, "Spread Returns: N/A", ha="center", va="center")
        fig.suptitle("Quantile Analysis", fontsize=16)
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # Page 3: Turnover
        fig, ax = plt.subplots(1, 1, figsize=(16, 6))
        try:
            quantile_turnover = alphalens.performance.quantile_turnover(
                alphalens.utils.get_clean_factor_and_forward_returns(
                    factor=factor, prices=prices, periods=periods, quantiles=quantiles,
                    filter_zscore=None,
                ),
                quantiles,
            )
            quantile_turnover.plot(ax=ax, title="Quantile Turnover")
        except Exception:
            ax.text(0.5, 0.5, "Turnover: N/A", ha="center", va="center")
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

    logging.info(f"Alphalens tear sheet saved to {pdf_path}")
    return pdf_path
