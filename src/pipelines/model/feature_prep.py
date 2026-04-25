"""Cross-section feature preprocessing for model training."""
import numpy as np
import pandas as pd
from dataclasses import dataclass


def cross_section_rank_normalize(X: pd.DataFrame) -> pd.DataFrame:
    """Transform features to cross-sectional rank percentiles [-1, 1]."""
    return X.groupby(level="datetime").transform(
        lambda s: s.rank(pct=True) * 2 - 1
    )


def cross_section_zscore(X: pd.DataFrame) -> pd.DataFrame:
    """Standardize features by cross-sectional z-score."""
    def _zscore(s):
        s = s.dropna()
        if len(s) < 2:
            return s
        return (s - s.mean()) / s.std()
    return X.groupby(level="datetime").transform(_zscore)


def cross_section_impute_median(X: pd.DataFrame) -> pd.DataFrame:
    """Fill NaN values with cross-sectional median."""
    return X.groupby(level="datetime").transform(
        lambda s: s.fillna(s.median())
    )


def cross_section_winsorize_quantile(
    X: pd.DataFrame, lower: float = 0.01, upper: float = 0.99,
) -> pd.DataFrame:
    """Winsorize features by cross-sectional quantiles."""
    def _clip(s):
        s = s.dropna()
        if len(s) < 2:
            return s
        return s.clip(s.quantile(lower), s.quantile(upper))
    return X.groupby(level="datetime").transform(_clip)


# --- Label transforms ---

def winsorize_label_by_date_quantile(
    y: pd.Series, lower_q: float = 0.01, upper_q: float = 0.99,
) -> pd.Series:
    """Winsorize labels by cross-sectional quantile per date."""
    def _clip(s):
        idx = s.index
        s = s.dropna()
        if len(s) < 2:
            return pd.Series(np.nan, index=idx)
        clipped = s.clip(s.quantile(lower_q), s.quantile(upper_q))
        return clipped.reindex(idx)
    return y.groupby(level="datetime").transform(_clip)


def make_rank_label_by_date(
    y: pd.Series, n_bins: int = 5, min_group_size: int = 30,
) -> pd.Series:
    """Convert continuous labels to ordinal bins for LGBMRanker.

    Uses rank(method='first') to avoid qcut failure on duplicate values.
    """
    def _rank_bin(s):
        s = s.dropna()
        if len(s) < min_group_size:
            return pd.Series(index=s.index, dtype=float)
        ranked = s.rank(method="first")
        return pd.qcut(ranked, q=n_bins, labels=False, duplicates="drop")
    return y.groupby(level="datetime", group_keys=False).apply(_rank_bin)


def make_binary_label_by_date(
    y: pd.Series, top_q: float = 0.8, bottom_q: float = 0.2,
) -> tuple[pd.Series, pd.Series]:
    """Create Top/Bottom binary labels for LGBMClassifier.

    Returns:
        (y_binary, mask): y_binary has 1 for top, 0 for bottom; mask indicates valid samples.
    """
    y_bin_all = pd.Series(dtype=float, index=y.index)
    mask_all = pd.Series(False, index=y.index)

    for _, s in y.groupby(level="datetime"):
        s_clean = s.dropna()
        if len(s_clean) < 30:
            continue
        upper = s_clean.quantile(top_q)
        lower = s_clean.quantile(bottom_q)
        y_bin = pd.Series(0, index=s.index)
        y_bin[s >= upper] = 1
        y_bin[s <= lower] = 0
        valid = (s >= upper) | (s <= lower)
        mask = valid
        y_bin_all.loc[s.index] = y_bin
        mask_all.loc[s.index] = mask

    return y_bin_all, mask_all


# --- Preprocessor ---

@dataclass
class FeaturePreprocessor:
    """Cross-section feature preprocessing pipeline.

    Steps (in order):
    1. Winsorize (quantile clipping)
    2. Impute (cross-section median)
    3. Transform (rank_pct or zscore)
    """

    impute: str = "cross_section_median"
    transform_method: str = "rank_pct"
    winsorize_enabled: bool = True
    winsorize_lower: float = 0.01
    winsorize_upper: float = 0.99

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        result = X.copy()

        # 1. Winsorize
        if self.winsorize_enabled:
            result = cross_section_winsorize_quantile(
                result, self.winsorize_lower, self.winsorize_upper
            )

        # 2. Impute
        if self.impute == "cross_section_median":
            result = cross_section_impute_median(result)

        # 3. Transform
        if self.transform_method == "rank_pct":
            result = cross_section_rank_normalize(result)
        elif self.transform_method == "zscore":
            result = cross_section_zscore(result)

        return result
