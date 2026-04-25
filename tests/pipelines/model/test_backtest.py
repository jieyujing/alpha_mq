"""Tests for TopK backtest with lag, turnover, cost, and benchmark."""
import numpy as np
import pandas as pd
import pytest
from pipelines.model.backtest import topk_backtest


@pytest.fixture
def returns_and_signals():
    """Create returns matrix and signals for backtest."""
    dates = pd.date_range("2020-01-01", periods=30, freq="B")
    symbols = [f"SH60000{i}" for i in range(1, 21)]
    rng = np.random.RandomState(42)

    returns_wide = pd.DataFrame(
        rng.randn(len(dates), len(symbols)) * 0.02,
        index=dates, columns=symbols,
    )
    signals_wide = pd.DataFrame(
        rng.randn(len(dates), len(symbols)),
        index=dates, columns=symbols,
    )
    return returns_wide, signals_wide


def test_backtest_returns_length(returns_and_signals):
    ret_wide, sig_wide = returns_and_signals
    port_ret, excess, turnover, weights = topk_backtest(ret_wide, sig_wide, topk=5)
    assert len(port_ret) == len(ret_wide)
    assert len(excess) == len(ret_wide)
    assert len(turnover) == len(ret_wide)


def test_backtest_excess_reasonable(returns_and_signals):
    ret_wide, sig_wide = returns_and_signals
    port_ret, excess, turnover, weights = topk_backtest(ret_wide, sig_wide, topk=5)
    # Excess should be portfolio - benchmark (equal weight)
    ew_ret = ret_wide.mean(axis=1)
    assert (excess + ew_ret - port_ret).abs().max() < 1e-10


def test_backtest_costs_applied(returns_and_signals):
    ret_wide, sig_wide = returns_and_signals
    port_ret, excess, turnover, weights = topk_backtest(ret_wide, sig_wide, topk=5, transaction_cost_bps=100)
    port_ret_no_cost, _, _, _ = topk_backtest(ret_wide, sig_wide, topk=5, transaction_cost_bps=0)
    # With 100bps cost, net returns should be lower
    assert (port_ret - port_ret_no_cost).sum() < 0


def test_backtest_lag_signal_shift(returns_and_signals):
    ret_wide, sig_wide = returns_and_signals
    port_ret, excess, turnover, weights = topk_backtest(ret_wide, sig_wide, topk=5, shift_signal_days=1)
    # First row of weights should be all zeros (no prior signal)
    assert weights.iloc[0].sum() == 0


def test_backtest_turnover_positive(returns_and_signals):
    ret_wide, sig_wide = returns_and_signals
    port_ret, excess, turnover, weights = topk_backtest(ret_wide, sig_wide, topk=5)
    assert (turnover >= 0).all()
