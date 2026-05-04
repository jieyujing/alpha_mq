from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _load_research_dependencies() -> tuple[Any, Any, Any, Any]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from alphalens import performance, plotting, utils
    except ImportError as exc:  # pragma: no cover - exercised via CLI in real env
        raise RuntimeError(
            "Alphalens analysis requires the research dependency group. "
            "Install or run with `uv sync --group research`."
        ) from exc
    return plt, performance, plotting, utils


@dataclass(slots=True)
class AlphalensAnalysisConfig:
    output_dir: Path | str
    factor_path: Path | str = "data/output/cross_section_factors.parquet"
    symbol_factor_path: Path | str = "data/output/symbol_factors.parquet"
    factor_column: str = "carry_rank_pct"
    periods: tuple[int, ...] = (1, 5, 10, 20)
    quantiles: int = 5
    max_loss: float = 0.35
    demeaned: bool = False


@dataclass(slots=True)
class AlphalensAnalysisResult:
    factor_data: pd.DataFrame
    factor_returns: pd.DataFrame
    information_coefficient: pd.DataFrame
    mean_return_by_quantile: pd.DataFrame
    mean_return_by_quantile_ts: pd.DataFrame
    quantile_turnover: dict[int, pd.DataFrame]
    output_dir: Path
    generated_files: list[Path] = field(default_factory=list)


class AlphalensAnalyzer:
    def __init__(self, config: AlphalensAnalysisConfig) -> None:
        self.config = config
        self.output_dir = Path(config.output_dir)

    def load_frames(
        self,
        factor_path: str | Path,
        symbol_factor_path: str | Path,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        factor_frame = pd.read_parquet(factor_path)
        symbol_frame = pd.read_parquet(symbol_factor_path)
        return factor_frame, symbol_frame

    def build_factor_series(self, factor_frame: pd.DataFrame) -> pd.Series:
        frame = factor_frame.copy()
        frame["trade_date"] = pd.to_datetime(frame["trade_date"])
        if "quality_status" in frame.columns:
            frame = frame[frame["quality_status"].fillna("valid") != "invalid"]
        frame = frame.dropna(subset=["trade_date", "symbol", self.config.factor_column])
        frame["symbol"] = frame["symbol"].astype(str)
        series = frame.set_index(["trade_date", "symbol"])[self.config.factor_column].astype(float)
        series.index = series.index.set_names(["date", "asset"])
        return series.sort_index()

    def build_prices(self, symbol_frame: pd.DataFrame) -> pd.DataFrame:
        frame = symbol_frame.copy()
        frame["trade_date"] = pd.to_datetime(frame["trade_date"])
        if "quality_status" in frame.columns:
            frame = frame[frame["quality_status"].fillna("valid") != "invalid"]
        frame["symbol"] = frame["symbol"].astype(str)
        frame = frame.sort_values(["symbol", "trade_date"])

        price_rows: list[dict[str, object]] = []
        for symbol, group in frame.groupby("symbol", sort=True):
            current_price = 1.0
            active_path = False
            for row in group.itertuples(index=False):
                missing_path = pd.isna(row.hold_contract) or pd.isna(row.daily_return)
                if missing_path:
                    active_path = False
                    price_rows.append(
                        {"trade_date": row.trade_date, "symbol": symbol, "price": np.nan}
                    )
                    continue

                if not active_path:
                    current_price = 1.0
                    active_path = True
                else:
                    current_price *= 1.0 + float(row.daily_return)

                price_rows.append(
                    {"trade_date": row.trade_date, "symbol": symbol, "price": current_price}
                )

        if not price_rows:
            return pd.DataFrame()

        prices = (
            pd.DataFrame(price_rows)
            .pivot(index="trade_date", columns="symbol", values="price")
            .sort_index()
            .sort_index(axis=1)
        )
        prices.index.name = "date"
        return prices

    def analyze_frames(
        self,
        factor_frame: pd.DataFrame,
        symbol_frame: pd.DataFrame,
    ) -> AlphalensAnalysisResult:
        _, performance, _, utils = _load_research_dependencies()

        factor = self.build_factor_series(factor_frame)
        prices = self.build_prices(symbol_frame)
        if factor.empty:
            raise ValueError("No valid factor rows available for Alphalens analysis.")
        if prices.empty:
            raise ValueError("No valid hold-contract price path available for Alphalens analysis.")

        factor = self._trim_factor_to_available_horizon(factor, prices)
        if factor.empty:
            raise ValueError("No factor rows remain after trimming to the available price horizon.")

        factor_data = utils.get_clean_factor_and_forward_returns(
            factor=factor,
            prices=prices,
            quantiles=self.config.quantiles,
            periods=self.config.periods,
            max_loss=self.config.max_loss,
        )
        factor_returns = performance.factor_returns(factor_data)
        information_coefficient = performance.factor_information_coefficient(factor_data)
        mean_return_by_quantile, _ = performance.mean_return_by_quantile(
            factor_data,
            by_date=False,
            demeaned=self.config.demeaned,
        )
        mean_return_by_quantile_ts, _ = performance.mean_return_by_quantile(
            factor_data,
            by_date=True,
            demeaned=self.config.demeaned,
        )

        turnover = {}
        quantile_series = factor_data["factor_quantile"]
        for period in self.config.periods:
            period_turnover = {}
            for quantile in range(1, self.config.quantiles + 1):
                period_turnover[f"quantile_{quantile}"] = performance.quantile_turnover(
                    quantile_series,
                    quantile=quantile,
                    period=period,
                )
            turnover[period] = pd.DataFrame(period_turnover)

        return AlphalensAnalysisResult(
            factor_data=factor_data,
            factor_returns=factor_returns,
            information_coefficient=information_coefficient,
            mean_return_by_quantile=mean_return_by_quantile,
            mean_return_by_quantile_ts=mean_return_by_quantile_ts,
            quantile_turnover=turnover,
            output_dir=self.output_dir,
        )

    def write_outputs(self, result: AlphalensAnalysisResult) -> AlphalensAnalysisResult:
        plt, performance, plotting, _ = _load_research_dependencies()

        self.output_dir.mkdir(parents=True, exist_ok=True)
        plots_dir = self.output_dir / "plots"
        plots_dir.mkdir(parents=True, exist_ok=True)

        files: list[Path] = []

        clean_factor_path = self.output_dir / "clean_factor_data.parquet"
        result.factor_data.reset_index().to_parquet(clean_factor_path, index=False)
        files.append(clean_factor_path)

        factor_returns_path = self.output_dir / "factor_returns.csv"
        result.factor_returns.to_csv(factor_returns_path)
        files.append(factor_returns_path)

        information_path = self.output_dir / "information_coefficient.csv"
        result.information_coefficient.to_csv(information_path)
        files.append(information_path)

        mean_return_path = self.output_dir / "mean_return_by_quantile.csv"
        result.mean_return_by_quantile.to_csv(mean_return_path)
        files.append(mean_return_path)

        mean_return_ts_path = self.output_dir / "quantile_returns_ts.csv"
        result.mean_return_by_quantile_ts.to_csv(mean_return_ts_path)
        files.append(mean_return_ts_path)

        # Calculate and export quantile cumulative returns (Net Value)
        quantile_cumulative_returns = (
            (1.0 + result.mean_return_by_quantile_ts).groupby(level="factor_quantile").cumprod()
        )
        quantile_cumulative_path = self.output_dir / "quantile_cumulative_returns.csv"
        quantile_cumulative_returns.to_csv(quantile_cumulative_path)
        files.append(quantile_cumulative_path)

        # Calculate and export long-short cumulative returns (Spread Qmax - Q1)
        # Note: mean_return_by_quantile_ts has (quantile, date) as index and (periods) as columns.
        # Unstacking 'factor_quantile' creates MultiIndex columns: (Period, factor_quantile)
        returns_unstacked = result.mean_return_by_quantile_ts.unstack(level="factor_quantile")
        q_max = result.mean_return_by_quantile_ts.index.get_level_values("factor_quantile").max()

        # Calculate returns for top and bottom quantiles across all periods
        top_q_ret = returns_unstacked.xs(q_max, axis=1, level="factor_quantile")
        bottom_q_ret = returns_unstacked.xs(1, axis=1, level="factor_quantile")

        ls_ret = top_q_ret - bottom_q_ret
        ls_cum_ret = (1.0 + ls_ret).cumprod()
        ls_cum_path = self.output_dir / "long_short_cumulative_returns.csv"
        ls_cum_ret.to_csv(ls_cum_path)
        files.append(ls_cum_path)

        for period, turnover_frame in result.quantile_turnover.items():
            turnover_path = self.output_dir / f"quantile_turnover_{period}d.csv"
            turnover_frame.to_csv(turnover_path)
            files.append(turnover_path)

        self._write_plots(result, plotting, performance, plt, plots_dir, files)
        result.generated_files = files
        return result

    def run(
        self,
        factor_path: str | Path,
        symbol_factor_path: str | Path,
    ) -> AlphalensAnalysisResult:
        factor_frame, symbol_frame = self.load_frames(factor_path, symbol_factor_path)
        result = self.analyze_frames(factor_frame, symbol_frame)
        return self.write_outputs(result)

    def _trim_factor_to_available_horizon(
        self,
        factor: pd.Series,
        prices: pd.DataFrame,
    ) -> pd.Series:
        max_period = max(self.config.periods)
        if len(prices.index) <= max_period:
            return factor.iloc[0:0]

        last_valid_date = prices.index[-(max_period + 1)]
        valid_symbols = set(prices.columns)
        valid_dates = factor.index.get_level_values("date") <= last_valid_date
        valid_assets = factor.index.get_level_values("asset").isin(valid_symbols)
        return factor[valid_dates & valid_assets]

    def _write_plots(
        self,
        result: AlphalensAnalysisResult,
        plotting: Any,
        performance: Any,
        plt: Any,
        plots_dir: Path,
        files: list[Path],
    ) -> None:
        num_ic_axes = len(result.information_coefficient.columns)
        ic_fig, ic_axes = plt.subplots(num_ic_axes, 1, figsize=(10, max(4, 3 * num_ic_axes)))
        plotting.plot_ic_ts(result.information_coefficient, ax=np.atleast_1d(ic_axes))
        ic_fig.tight_layout()
        ic_path = plots_dir / "ic_ts.png"
        ic_fig.savefig(ic_path)
        plt.close(ic_fig)
        files.append(ic_path)

        ic_hist_fig, ic_hist_axes = plt.subplots(
            num_ic_axes,
            1,
            figsize=(8, max(4, 3 * num_ic_axes)),
        )
        plotting.plot_ic_hist(result.information_coefficient, ax=np.atleast_1d(ic_hist_axes))
        ic_hist_fig.tight_layout()
        ic_hist_path = plots_dir / "ic_hist.png"
        ic_hist_fig.savefig(ic_hist_path)
        plt.close(ic_hist_fig)
        files.append(ic_hist_path)

        qret_fig, qret_ax = plt.subplots(figsize=(10, 4))
        plotting.plot_quantile_returns_bar(result.mean_return_by_quantile, ax=qret_ax)
        qret_fig.tight_layout()
        qret_path = plots_dir / "quantile_returns_bar.png"
        qret_fig.savefig(qret_path)
        plt.close(qret_fig)
        files.append(qret_path)

        # Cumulative quantile returns plot
        for period in self.config.periods:
            period_col = f"{period}D"
            if period_col not in result.mean_return_by_quantile_ts.columns:
                continue

            # Include individual quantiles and the Long-Short spread so Alphalens
            # applies cumulative scaling consistently for all lines.
            period_ts = result.mean_return_by_quantile_ts[period_col]
            q_max = period_ts.index.get_level_values("factor_quantile").max()
            unstacked = period_ts.unstack(level="factor_quantile")
            ls_diff = unstacked[q_max] - unstacked[1]

            # Create LS series with a dummy quantile label 'L-S'
            ls_series = pd.Series(ls_diff, name=period_ts.name)
            ls_series.index = pd.MultiIndex.from_product(
                [["L-S"], ls_series.index], names=["factor_quantile", "date"]
            )

            combined_ts = pd.concat([period_ts, ls_series]).sort_index()

            q_cum_fig, q_cum_ax = plt.subplots(figsize=(10, 6))
            plotting.plot_cumulative_returns_by_quantile(
                combined_ts,
                period=period_col,
                ax=q_cum_ax,
            )
            # Set Y-axis to log scale as requested
            q_cum_ax.set_yscale("log")

            q_cum_fig.tight_layout()
            q_cum_path = plots_dir / f"cumulative_returns_by_quantile_{period}d.png"
            q_cum_fig.savefig(q_cum_path)
            plt.close(q_cum_fig)
            files.append(q_cum_path)

        mean_returns_by_date = result.mean_return_by_quantile_ts
        # Recalculate stderr for the spread plot because it is not stored on the result.
        _, std_err_by_date = performance.mean_return_by_quantile(
            result.factor_data,
            by_date=True,
        )
        spread, spread_err = performance.compute_mean_returns_spread(
            mean_returns_by_date,
            upper_quant=self.config.quantiles,
            lower_quant=1,
            std_err=std_err_by_date,
        )
        num_spread_axes = len(spread.columns)
        spread_fig, spread_axes = plt.subplots(
            num_spread_axes,
            1,
            figsize=(10, max(4, 3 * num_spread_axes)),
        )
        plotting.plot_mean_quantile_returns_spread_time_series(
            spread,
            std_err=spread_err,
            ax=np.atleast_1d(spread_axes),
        )
        spread_fig.tight_layout()
        spread_path = plots_dir / "mean_return_spread.png"
        spread_fig.savefig(spread_path)
        plt.close(spread_fig)
        files.append(spread_path)

        first_period = self.config.periods[0]
        turnover_fig, turnover_ax = plt.subplots(figsize=(10, 4))
        plotting.plot_top_bottom_quantile_turnover(
            result.quantile_turnover[first_period],
            period=first_period,
            ax=turnover_ax,
        )
        turnover_fig.tight_layout()
        turnover_path = plots_dir / f"turnover_{first_period}d.png"
        turnover_fig.savefig(turnover_path)
        plt.close(turnover_fig)
        files.append(turnover_path)

        # Generate Premium PDF Report
        from pipelines.analysis.report_generator import AlphalensReportGenerator

        report_gen = AlphalensReportGenerator(self.output_dir)
        try:
            report_path = report_gen.generate_report(
                result.factor_data,
                result.information_coefficient,
                result.factor_returns,
                periods=self.config.periods,
            )
            files.append(report_path)
        except Exception as e:
            # Don't fail the whole analysis if report generation fails, but log it
            print(f"Warning: Failed to generate premium report: {e}")
