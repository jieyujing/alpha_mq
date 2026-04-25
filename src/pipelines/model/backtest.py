"""TopK backtest with signal lag, turnover, and transaction costs."""
import numpy as np
import pandas as pd


def topk_backtest(
    returns_wide: pd.DataFrame,
    signals_wide: pd.DataFrame,
    topk: int = 50,
    transaction_cost_bps: float = 10,
    shift_signal_days: int = 1,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.DataFrame]:
    """Run TopK backtest.

    Args:
        returns_wide: Daily returns, index=datetime, columns=instrument.
        signals_wide: Model signals, index=datetime, columns=instrument.
        topk: Number of stocks to hold.
        transaction_cost_bps: Transaction cost in basis points.
        shift_signal_days: Days to lag signal (T signal -> T+lag execution).

    Returns:
        (portfolio_returns, excess_returns, turnover, weights)
        All with datetime index.
    """
    # Ensure aligned dates
    common_dates = returns_wide.index.intersection(signals_wide.index)
    returns_wide = returns_wide.loc[common_dates]
    signals_wide = signals_wide.loc[common_dates]

    # Shift signals forward (lag)
    lagged_signals = signals_wide.shift(shift_signal_days)

    ew_returns = returns_wide.mean(axis=1)  # Equal-weight benchmark

    port_returns = []
    excess_returns = []
    turnovers = []
    weights_history = []

    prev_weights = pd.Series(0.0, index=returns_wide.columns)

    for date in common_dates:
        sig = lagged_signals.loc[date].dropna()
        if len(sig) < topk:
            # Not enough signals, hold cash
            w = pd.Series(0.0, index=returns_wide.columns)
            net_ret = np.nan
        else:
            top_k = sig.nlargest(topk).index
            w = pd.Series(0.0, index=returns_wide.columns)
            w[top_k] = 1.0 / topk
            # Portfolio return
            gross_ret = (w * returns_wide.loc[date]).sum()
            net_ret = gross_ret

        # Turnover
        turnover = (w - prev_weights).abs().sum() / 2
        cost = turnover * transaction_cost_bps / 10000
        if not np.isnan(net_ret):
            net_ret -= cost

        port_returns.append(net_ret)
        excess_returns.append(net_ret - ew_returns.loc[date] if not np.isnan(net_ret) else np.nan)
        turnovers.append(turnover)
        weights_history.append(w)
        prev_weights = w

    port_ret = pd.Series(port_returns, index=common_dates, name="portfolio_return")
    excess_ret = pd.Series(excess_returns, index=common_dates, name="excess_return")
    turnover = pd.Series(turnovers, index=common_dates, name="turnover")
    weights = pd.DataFrame(weights_history, index=common_dates)

    return port_ret, excess_ret, turnover, weights


def compute_backtest_metrics(
    port_ret: pd.Series,
    excess_ret: pd.Series,
    turnover: pd.Series,
    ann_factor: int = 252,
) -> dict:
    """Compute backtest performance metrics."""
    port_ret = port_ret.dropna()
    excess_ret = excess_ret.dropna()

    ann_ret = (1 + port_ret).prod() ** (ann_factor / len(port_ret)) - 1
    ann_excess = excess_ret.mean() * ann_factor
    sharpe = port_ret.mean() / port_ret.std() * np.sqrt(ann_factor) if port_ret.std() > 0 else 0
    excess_sharpe = excess_ret.mean() / excess_ret.std() * np.sqrt(ann_factor) if excess_ret.std() > 0 else 0

    cum_ret = (1 + port_ret).cumprod()
    max_dd = ((cum_ret / cum_ret.cummax()) - 1).min()

    avg_turnover = turnover.mean()
    win_rate = (port_ret > 0).mean()

    return {
        "ann_return": float(ann_ret),
        "ann_excess_return": float(ann_excess),
        "sharpe": float(sharpe),
        "excess_sharpe": float(excess_sharpe),
        "max_drawdown": float(max_dd),
        "win_rate": float(win_rate),
        "avg_turnover": float(avg_turnover),
        "n_periods": len(port_ret),
    }
