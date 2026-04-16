from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence, Dict, Any

import numpy as np
import pandas as pd


@dataclass
class AlphalensData:
    """
    Prepare Alphalens-ready factor data.

    Parameters
    ----------
    factor : pd.Series
        MultiIndex(date, asset) factor series.
    prices : pd.DataFrame
        Wide price table. index=date, columns=asset.
    groupby : Optional[pd.Series | dict]
        Optional industry/group mapping.
        Supported forms:
        1) MultiIndex(date, asset) Series
        2) asset-level Series
        3) dict[asset -> group]
    periods : Sequence[int]
        Forward return horizons.
    quantiles : Optional[int]
        Number of quantiles for binning.
    bins : Optional[int]
        Alternative to quantiles.
    groupby_labels : Optional[Dict[Any, str]]
        Optional group label mapping.
    binning_by_group : bool
        Whether to bin within group.
    filter_zscore : Optional[float]
        Z-score filter for outlier forward returns.
    max_loss : float
        Allowed row loss in Alphalens preprocessing.
    zero_aware : bool
        Whether to split positive/negative values separately in quantization.
    cumulative_returns : bool
        Whether forward returns are cumulative.
    """

    factor: pd.Series
    prices: pd.DataFrame
    groupby: Optional[pd.Series | Dict[str, Any]] = None

    periods: Sequence[int] = (1, 5, 10)
    quantiles: Optional[int] = 5
    bins: Optional[int] = None
    groupby_labels: Optional[Dict[Any, str]] = None

    binning_by_group: bool = False
    filter_zscore: Optional[float] = 20.0
    max_loss: float = 0.35
    zero_aware: bool = False
    cumulative_returns: bool = True

    clean_factor_data: Optional[pd.DataFrame] = field(default=None, init=False)
    diagnostics: Dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.factor = self._prepare_factor(self.factor)
        self.prices = self._prepare_prices(self.prices)
        self.groupby = self._prepare_groupby(self.groupby)
        self._build_diagnostics()

    @staticmethod
    def _prepare_factor(factor: pd.Series) -> pd.Series:
        if not isinstance(factor, pd.Series):
            raise TypeError("factor must be a pandas Series")

        if not isinstance(factor.index, pd.MultiIndex):
            raise TypeError("factor index must be MultiIndex(date, asset)")

        if factor.index.nlevels != 2:
            raise ValueError("factor index must have exactly 2 levels")

        factor = factor.copy()
        factor.index = factor.index.set_names(["date", "asset"])
        factor = factor.sort_index()
        factor = factor.astype(float)
        factor = factor.replace([np.inf, -np.inf], np.nan).dropna()

        if factor.index.has_duplicates:
            factor = factor[~factor.index.duplicated(keep="last")]

        if factor.empty:
            raise ValueError("factor is empty after cleaning")

        return factor

    @staticmethod
    def _prepare_prices(prices: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(prices, pd.DataFrame):
            raise TypeError("prices must be a pandas DataFrame")

        if prices.empty:
            raise ValueError("prices is empty")

        prices = prices.copy()
        prices.index = pd.to_datetime(prices.index)
        prices = prices.sort_index()
        prices = prices.apply(pd.to_numeric, errors="coerce")
        prices = prices.replace([np.inf, -np.inf], np.nan)

        if prices.index.has_duplicates:
            raise ValueError("prices index contains duplicate dates")

        return prices

    def _prepare_groupby(
        self, groupby: Optional[pd.Series | Dict[str, Any]]
    ) -> Optional[pd.Series]:
        if groupby is None:
            return None

        # dict: asset -> group
        if isinstance(groupby, dict):
            mapped = self.factor.index.get_level_values("asset").map(groupby)
            return pd.Series(mapped, index=self.factor.index, name="group")

        if not isinstance(groupby, pd.Series):
            raise TypeError("groupby must be None, dict, or pandas Series")

        groupby = groupby.copy()

        # MultiIndex(date, asset) -> directly align
        if isinstance(groupby.index, pd.MultiIndex):
            if groupby.index.nlevels != 2:
                raise ValueError("groupby MultiIndex must have 2 levels")
            groupby.index = groupby.index.set_names(["date", "asset"])
            groupby = groupby.sort_index().reindex(self.factor.index)
            return groupby

        # asset-level Series -> broadcast to factor index
        mapped = self.factor.index.get_level_values("asset").map(groupby.to_dict())
        return pd.Series(mapped, index=self.factor.index, name=groupby.name or "group")

    def _build_diagnostics(self) -> None:
        idx = self.factor.index
        dates = idx.get_level_values("date")
        assets = idx.get_level_values("asset")

        self.diagnostics = {
            "factor_rows": int(len(self.factor)),
            "factor_n_dates": int(dates.nunique()),
            "factor_n_assets": int(assets.nunique()),
            "factor_date_min": dates.min(),
            "factor_date_max": dates.max(),
            "prices_shape": tuple(self.prices.shape),
            "prices_date_min": self.prices.index.min(),
            "prices_date_max": self.prices.index.max(),
            "has_groupby": self.groupby is not None,
        }

    def build(self) -> pd.DataFrame:
        """
        Build Alphalens-ready factor_data.
        """
        import alphalens as al

        kwargs = {
            "factor": self.factor,
            "prices": self.prices,
            "periods": tuple(self.periods),
            "binning_by_group": self.binning_by_group,
            "max_loss": self.max_loss,
            "zero_aware": self.zero_aware,
            "cumulative_returns": self.cumulative_returns,
        }

        if self.quantiles is not None:
            kwargs["quantiles"] = self.quantiles
        if self.bins is not None:
            kwargs["bins"] = self.bins
        if self.groupby is not None:
            kwargs["groupby"] = self.groupby
        if self.groupby_labels is not None:
            kwargs["groupby_labels"] = self.groupby_labels
        if self.filter_zscore is not None:
            kwargs["filter_zscore"] = self.filter_zscore

        self.clean_factor_data = al.utils.get_clean_factor_and_forward_returns(**kwargs)
        return self.clean_factor_data

    def get_factor_data(self) -> pd.DataFrame:
        if self.clean_factor_data is None:
            return self.build()
        return self.clean_factor_data

    def summary(self) -> pd.Series:
        out = dict(self.diagnostics)
        if self.clean_factor_data is not None:
            out["clean_rows"] = int(len(self.clean_factor_data))
            out["clean_columns"] = list(self.clean_factor_data.columns)
            out["loss_ratio_vs_factor"] = 1.0 - len(self.clean_factor_data) / len(self.factor)
        return pd.Series(out, name="alphalens_summary")

    def create_full_tear_sheet(
        self,
        long_short: bool = True,
        group_neutral: bool = False,
        by_group: bool = False,
    ) -> None:
        import alphalens as al

        al.tears.create_full_tear_sheet(
            self.get_factor_data(),
            long_short=long_short,
            group_neutral=group_neutral,
            by_group=by_group,
        )