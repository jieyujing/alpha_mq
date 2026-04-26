"""ChartAdapter: Adapter pattern for alphalens plotting functions.

Provides a unified interface that routes chart generation to either:
- alphalens original implementation (for working functions)
- custom implementation (for buggy functions)

Usage:
    adapter = ChartAdapter()
    fig = adapter.plot_ic_ts(ic)  # uses alphalens
    fig = adapter.plot_monthly_ic_heatmap(monthly_ic)  # uses custom implementation
"""
from abc import ABC, abstractmethod
from typing import Protocol, Any
from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


class PlotSource(Enum):
    """Source of plotting implementation."""
    ALPHALENS = "alphalens"
    CUSTOM = "custom"


@dataclass
class PlotConfig:
    """Configuration for a specific plot type."""
    name: str
    source: PlotSource
    fig_size: tuple[float, float] | None = None
    dpi: int = 150


class PlotterProtocol(Protocol):
    """Protocol defining plotter interface."""

    def plot(self, data: Any, **kwargs) -> plt.Figure:
        """Generate plot from data."""
        ...


class BasePlotter(ABC):
    """Abstract base class for plotters."""

    @abstractmethod
    def plot(self, data: Any, **kwargs) -> plt.Figure:
        """Generate plot from data."""
        pass


class AlphaLensPlotter(BasePlotter):
    """Wrapper for alphalens plotting functions."""

    def __init__(self):
        import alphalens.plotting as plotting
        self._plotting = plotting

    def plot(self, data: Any, func_name: str, **kwargs) -> plt.Figure:
        """Call alphalens plotting function."""
        func = getattr(self._plotting, func_name)
        # Handle functions that expect multiple arguments
        if isinstance(data, tuple):
            result = func(*data, **kwargs)
        else:
            result = func(data, **kwargs)
        return self._extract_figure(result)

    def _extract_figure(self, result) -> plt.Figure | None:
        """Extract figure from alphalens result (handles arrays of axes)."""
        if result is None:
            return None
        if hasattr(result, '__len__') and not hasattr(result, 'figure'):
            if len(result) > 0 and hasattr(result[0], 'figure'):
                return result[0].figure
        elif hasattr(result, 'figure'):
            return result.figure
        return None


class CustomICHeatmapPlotter(BasePlotter):
    """Custom implementation for monthly IC heatmap (fixes alphalens bug)."""

    def plot(self, monthly_ic: pd.DataFrame, **kwargs) -> plt.Figure:
        """Generate monthly IC heatmap with proper imshow binding."""
        periods = monthly_ic.columns.tolist()
        n_periods = len(periods)

        # Determine layout
        if n_periods <= 2:
            fig, axes = plt.subplots(1, n_periods, figsize=(8 * n_periods, 6))
        else:
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        axes = np.atleast_1d(axes)

        # Color scale centered on 0
        cmap = plt.cm.RdYlGn
        vmin, vmax = -0.15, 0.15

        for i, (ax, period) in enumerate(zip(axes.flat, periods)):
            if period not in monthly_ic.columns:
                ax.set_visible(False)
                continue

            ic_data = monthly_ic[period]
            years = ic_data.index.year.unique().sort_values()
            months = range(1, 13)

            # Create year x month grid
            grid = pd.DataFrame(index=years, columns=months, dtype=float)
            for idx, val in ic_data.items():
                if idx.year in years and idx.month in months:
                    grid.loc[idx.year, idx.month] = val

            # Plot heatmap with explicit data binding
            im = ax.imshow(
                grid.values.astype(float),
                cmap=cmap,
                aspect='auto',
                vmin=vmin,
                vmax=vmax,
                interpolation='nearest'
            )

            # Labels
            ax.set_xticks(range(12))
            ax.set_xticklabels(['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'], fontsize=9)
            ax.set_yticks(range(len(years)))
            ax.set_yticklabels([str(y) for y in years], fontsize=9)
            ax.set_title(f'Monthly IC - {period}', fontsize=11)

            # Colorbar
            cbar = fig.colorbar(im, ax=ax, shrink=0.8)
            cbar.ax.tick_params(labelsize=8)

        fig.suptitle('Monthly Mean IC Heatmap', fontsize=14, y=1.02)
        plt.tight_layout()
        return fig


class CustomICHistPlotter(BasePlotter):
    """Custom implementation for IC histogram (fixes empty axes bug)."""

    def plot(self, ic: pd.DataFrame, **kwargs) -> plt.Figure:
        """Generate IC histogram for all periods."""
        periods = ic.columns.tolist()
        n_periods = len(periods)

        # Grid layout
        n_cols = min(3, n_periods)
        n_rows = (n_periods + n_cols - 1) // n_cols

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows))
        axes = np.atleast_2d(axes)

        for i, period in enumerate(periods):
            row, col = i // n_cols, i % n_cols
            ax = axes[row, col]

            data = ic[period].dropna()

            # Histogram
            ax.hist(data, bins=30, density=True, alpha=0.7,
                   color='steelblue', edgecolor='white')

            # Normal overlay
            mean, std = data.mean(), data.std()
            x = np.linspace(data.min(), data.max(), 100)
            ax.plot(x, (1/(std * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x - mean) / std)**2),
                   'r-', linewidth=2, label=f'Normal(μ={mean:.2f}, σ={std:.2f})')

            ax.axvline(0, color='gray', linestyle='--', alpha=0.5)
            ax.set_title(f'IC Distribution - {period}', fontsize=10)
            ax.set_xlabel('IC', fontsize=9)
            ax.set_ylabel('Density', fontsize=9)
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)

        # Hide unused axes
        for i in range(len(periods), n_rows * n_cols):
            row, col = i // n_cols, i % n_cols
            axes[row, col].set_visible(False)

        fig.suptitle('IC Distribution by Period', fontsize=14, y=1.02)
        plt.tight_layout()
        return fig


class CustomICQQPlotter(BasePlotter):
    """Custom implementation for IC Q-Q plot (fixes empty axes bug)."""

    def plot(self, ic: pd.DataFrame, **kwargs) -> plt.Figure:
        """Generate Q-Q plots for all periods."""
        from scipy import stats

        periods = ic.columns.tolist()
        n_periods = len(periods)

        n_cols = min(3, n_periods)
        n_rows = (n_periods + n_cols - 1) // n_cols

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows))
        axes = np.atleast_2d(axes)

        for i, period in enumerate(periods):
            row, col = i // n_cols, i % n_cols
            ax = axes[row, col]

            data = ic[period].dropna().values

            # Q-Q plot
            stats.probplot(data, dist="norm", plot=ax)

            ax.set_title(f'Q-Q Plot - {period}', fontsize=10)
            ax.grid(True, alpha=0.3)

        # Hide unused axes
        for i in range(len(periods), n_rows * n_cols):
            row, col = i // n_cols, i % n_cols
            axes[row, col].set_visible(False)

        fig.suptitle('IC Normality Check (Q-Q Plots)', fontsize=14, y=1.02)
        plt.tight_layout()
        return fig


class PlotRegistry:
    """Registry mapping plot types to implementations."""

    # Known alphalens bugs requiring custom implementation
    BUGGY_PLOTS = {
        'plot_monthly_ic_heatmap',  # imshow not bound
        'plot_ic_hist',              # empty axes for some periods
        'plot_ic_qq',                # empty axes for some periods
    }

    def __init__(self):
        self._alphalens_plotter = AlphaLensPlotter()
        self._custom_plotters = {
            'plot_monthly_ic_heatmap': CustomICHeatmapPlotter(),
            'plot_ic_hist': CustomICHistPlotter(),
            'plot_ic_qq': CustomICQQPlotter(),
        }

    def get_plotter(self, plot_name: str) -> tuple[BasePlotter, PlotSource]:
        """Get appropriate plotter for a plot type."""
        if plot_name in self.BUGGY_PLOTS:
            return self._custom_plotters[plot_name], PlotSource.CUSTOM
        return self._alphalens_plotter, PlotSource.ALPHALENS

    def is_buggy(self, plot_name: str) -> bool:
        """Check if a plot function is known to be buggy."""
        return plot_name in self.BUGGY_PLOTS


class ChartAdapter:
    """Adapter providing unified interface for chart generation.

    Routes to alphalens for working functions, custom implementations for buggy ones.

    Usage:
        adapter = ChartAdapter()

        # Uses alphalens (working)
        fig = adapter.plot_ic_ts(ic)
        fig = adapter.plot_quantile_returns_bar(mean_ret_q)

        # Uses custom implementation (fixing bugs)
        fig = adapter.plot_monthly_ic_heatmap(monthly_ic)
        fig = adapter.plot_ic_hist(ic)
    """

    # Plot functions known to work in alphalens
    WORKING_ALPHALENS = {
        'plot_ic_ts',
        'plot_mean_quantile_returns_spread_time_series',
        'plot_quantile_returns_bar',
        'plot_factor_rank_auto_correlation',
    }

    def __init__(self):
        self._registry = PlotRegistry()

    def plot_ic_ts(self, ic: pd.DataFrame) -> plt.Figure:
        """Plot IC time series."""
        plotter, source = self._registry.get_plotter('plot_ic_ts')
        if source == PlotSource.ALPHALENS:
            return plotter.plot(ic, 'plot_ic_ts')
        return plotter.plot(ic)

    def plot_ic_hist(self, ic: pd.DataFrame) -> plt.Figure:
        """Plot IC histogram (custom implementation to fix bug)."""
        plotter, source = self._registry.get_plotter('plot_ic_hist')
        if source == PlotSource.ALPHALENS:
            return plotter.plot(ic, 'plot_ic_hist')
        return plotter.plot(ic)

    def plot_ic_qq(self, ic: pd.DataFrame) -> plt.Figure:
        """Plot IC Q-Q plot (custom implementation to fix bug)."""
        plotter, source = self._registry.get_plotter('plot_ic_qq')
        if source == PlotSource.ALPHALENS:
            return plotter.plot(ic, 'plot_ic_qq')
        return plotter.plot(ic)

    def plot_mean_quantile_returns_spread(
        self,
        mean_ret_q: pd.DataFrame,
        std_ret_q: pd.DataFrame
    ) -> plt.Figure:
        """Plot quantile returns spread time series."""
        plotter, source = self._registry.get_plotter('plot_mean_quantile_returns_spread_time_series')
        if source == PlotSource.ALPHALENS:
            return plotter.plot((mean_ret_q, std_ret_q), 'plot_mean_quantile_returns_spread_time_series')
        return plotter.plot(mean_ret_q, std_ret_q)

    def plot_quantile_returns_bar(self, mean_ret_q: pd.DataFrame) -> plt.Figure:
        """Plot quantile returns bar chart."""
        plotter, source = self._registry.get_plotter('plot_quantile_returns_bar')
        if source == PlotSource.ALPHALENS:
            return plotter.plot(mean_ret_q, 'plot_quantile_returns_bar')
        return plotter.plot(mean_ret_q)

    def plot_monthly_ic_heatmap(self, monthly_ic: pd.DataFrame) -> plt.Figure:
        """Plot monthly IC heatmap (custom implementation to fix bug)."""
        plotter, source = self._registry.get_plotter('plot_monthly_ic_heatmap')
        if source == PlotSource.ALPHALENS:
            return plotter.plot(monthly_ic, 'plot_monthly_ic_heatmap')
        return plotter.plot(monthly_ic)

    def plot_factor_rank_auto_correlation(self, autocorr: pd.Series) -> plt.Figure:
        """Plot factor rank autocorrelation."""
        plotter, source = self._registry.get_plotter('plot_factor_rank_auto_correlation')
        if source == PlotSource.ALPHALENS:
            return plotter.plot(autocorr, 'plot_factor_rank_auto_correlation')
        return plotter.plot(autocorr)

    def get_status(self) -> dict[str, str]:
        """Get status of all plot functions."""
        status = {}
        for name in self.WORKING_ALPHALENS | PlotRegistry.BUGGY_PLOTS:
            status[name] = 'custom' if self._registry.is_buggy(name) else 'alphalens'
        return status