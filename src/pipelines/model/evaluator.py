"""Model evaluation metrics: IC, Rank IC, ICIR, factor importance."""
import numpy as np
import pandas as pd


def compute_ic(
    predictions: pd.Series, actuals: pd.Series
) -> tuple[float, float, float, float]:
    """Compute IC (Spearman correlation) between predictions and actuals.

    Returns:
        (ic_mean, ic_std, icir, rank_ic_mean)
    """
    df = pd.DataFrame({"pred": predictions, "actual": actuals}).dropna()
    if len(df) < 5:
        return (np.nan, np.nan, np.nan, np.nan)

    ic = df["pred"].corr(df["actual"], method="spearman")
    return (ic, np.nan, np.nan, ic)


def compute_ic_by_date(
    predictions: pd.Series, actuals: pd.Series, min_obs: int = 5
) -> pd.Series:
    """Compute daily cross-sectional IC (Spearman).

    Expects MultiIndex(datetime, instrument).
    """
    df = pd.DataFrame({"pred": predictions, "actual": actuals})
    records = []
    for dt, grp in df.groupby(level=0):
        grp = grp.dropna()
        if len(grp) >= min_obs:
            ic = grp["pred"].corr(grp["actual"], method="spearman")
            records.append((dt, ic))

    if not records:
        return pd.Series(dtype=float, name="ic")

    ic_series = pd.DataFrame(records, columns=["datetime", "ic"]).set_index("datetime")["ic"]
    return ic_series


def compute_metrics_from_ic_series(ic_series: pd.Series) -> dict:
    """Compute summary metrics from daily IC series."""
    ic_mean = ic_series.mean()
    ic_std = ic_series.std()
    icir = ic_mean / ic_std if ic_std and ic_std > 0 else np.nan
    positive_ratio = (ic_series > 0).mean()
    return {
        "ic_mean": float(ic_mean),
        "ic_std": float(ic_std),
        "icir": float(icir),
        "rank_ic_mean": float(ic_mean),   # Same as ic_mean since we use Spearman
        "positive_ratio": float(positive_ratio),
    }


def compute_model_metrics(
    train_pred: pd.Series,
    train_actual: pd.Series,
    val_pred: pd.Series | None = None,
    val_actual: pd.Series | None = None,
    test_pred: pd.Series | None = None,
    test_actual: pd.Series | None = None,
) -> dict:
    """Compute evaluation metrics for train/val/test splits.

    Returns dict with keys: train_ic, train_icir, val_ic, val_icir, test_ic, test_icir, etc.
    """
    metrics = {}

    train_ic = compute_ic_by_date(train_pred, train_actual)
    metrics["train"] = compute_metrics_from_ic_series(train_ic)

    if val_pred is not None and val_actual is not None:
        val_ic = compute_ic_by_date(val_pred, val_actual)
        metrics["val"] = compute_metrics_from_ic_series(val_ic)

    if test_pred is not None and test_actual is not None:
        test_ic = compute_ic_by_date(test_pred, test_actual)
        metrics["test"] = compute_metrics_from_ic_series(test_ic)

    return metrics


def orient_signal(val_mean_ic: float, predictions: pd.Series) -> tuple[pd.Series, int]:
    """Flip signal direction if validation IC is negative.

    Returns:
        (oriented_signal, direction) where direction is +1 or -1.
    """
    if val_mean_ic < 0:
        return -predictions, -1
    return predictions, 1
