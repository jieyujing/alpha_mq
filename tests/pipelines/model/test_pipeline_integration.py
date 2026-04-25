"""Integration test for ModelPipeline end-to-end with mock data."""
import pytest
import numpy as np
import pandas as pd
from pathlib import Path

from pipelines.model.feature_prep import FeaturePreprocessor, winsorize_label_by_date_quantile
from pipelines.model.evaluator import compute_ic_by_date, orient_signal, compute_model_metrics
from pipelines.model.backtest import topk_backtest, compute_backtest_metrics
from pipelines.model.linear_model import LinearModel
from pipelines.model.lgbm_regressor import LGBMRegModel


@pytest.fixture
def integration_data():
    """Create realistic mock data for pipeline testing."""
    rng = np.random.RandomState(42)
    dates = pd.date_range("2020-01-01", periods=50, freq="B")
    symbols = [f"SH60000{i}" for i in range(1, 31)]  # 30 symbols
    index = pd.MultiIndex.from_product([dates, symbols], names=["datetime", "instrument"])

    n_feat = 8
    X = pd.DataFrame({f"f{i}": rng.randn(len(index)) for i in range(n_feat)}, index=index)
    y_1d = pd.Series(rng.randn(len(index)) * 0.02, index=index, name="label_1d")
    y_5d = pd.Series(rng.randn(len(index)) * 0.04, index=index, name="label_5d")

    close = pd.DataFrame(
        100 + np.cumsum(rng.randn(len(dates), len(symbols)) * 0.01, axis=0),
        index=dates, columns=symbols,
    )
    returns = close.pct_change()

    return X, {"label_1d": y_1d, "label_5d": y_5d}, returns, close


def test_model_train_predict_e2e(integration_data):
    """Test: preprocess -> train -> predict -> evaluate for one model."""
    X, labels, returns, close = integration_data

    # Preprocess
    prep = FeaturePreprocessor(impute="cross_section_median", transform_method="rank_pct")
    X_clean = prep.transform(X)

    # Train/val split
    split_idx = len(X_clean) // 2
    X_train, X_val = X_clean.iloc[:split_idx], X_clean.iloc[split_idx:]
    y_train, y_val = labels["label_1d"].iloc[:split_idx], labels["label_1d"].iloc[split_idx:]

    # Train
    model = LinearModel(alpha=0.01, l1_ratio=0.2)
    model.fit(X_train, y_train)

    # Predict
    train_pred = model.predict(X_train)
    val_pred = model.predict(X_val)

    # Evaluate
    metrics = compute_model_metrics(train_pred, y_train, val_pred, y_val)
    assert "train" in metrics
    assert "val" in metrics
    assert "ic_mean" in metrics["train"]


def test_backtest_e2e(integration_data):
    """Test: signals -> backtest with lag and cost."""
    X, labels, returns, close = integration_data

    signals = pd.DataFrame(
        np.random.randn(*returns.shape),
        index=returns.index, columns=returns.columns,
    )

    port_ret, excess, turnover, weights = topk_backtest(
        returns, signals, topk=5, transaction_cost_bps=10, shift_signal_days=1,
    )

    assert len(port_ret) == len(returns)
    assert (turnover >= 0).all()
    # First row should be NaN due to lag
    assert port_ret.iloc[0] != port_ret.iloc[0]  # NaN check


def test_orient_and_metrics_e2e(integration_data):
    """Test direction correction + backtest metrics."""
    _, labels, returns, _ = integration_data

    # Create a deliberately negative signal
    y = labels["label_1d"]
    neg_pred = -y * 0.5  # Inverse signal

    ic = compute_ic_by_date(neg_pred, y)
    metrics = {"ic_mean": ic.mean(), "icir": ic.mean() / ic.std() if ic.std() > 0 else 0}

    oriented, direction = orient_signal(metrics["ic_mean"], neg_pred)
    assert direction == -1  # Should flip

    # Verify flipped signal has positive IC
    flipped_ic = compute_ic_by_date(oriented, y)
    assert flipped_ic.mean() > 0
