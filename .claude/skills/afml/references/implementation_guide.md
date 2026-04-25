# AFML Implementation Guide

Pseudo-code and implementation patterns for key AFML components.

## 1. Fractional Differentiation (FracDiff)

**Goal**: Find min `d` for stationarity.

```python
# Concept: Iteratively test d values
from mlfinlab.features.fracdiff import frac_diff_ffd

# Apply FracDiff to a price series
# d: differencing order (0 < d < 1)
# thres: threshold for weight cutoff
diff_series = frac_diff_ffd(prices, d=0.4, thres=1e-5)

# Then check ADF
from statsmodels.tsa.stattools import adfuller
p_val = adfuller(diff_series)[1]
if p_val < 0.05:
    print("Stationary!")
```

## 2. Triple-Barrier Labeling

**Goal**: Label events based on volatility-adjusted barriers.

```python
from mlfinlab.labeling import get_events, get_bins

# 1. Compute Daily Volatility (for dynamic barriers)
daily_vol = get_daily_vol(close_prices)

# 2. Define Barriers
# pt: Profit Taking multiplier
# sl: Stop Loss multiplier
# t1: Vertical barrier timestamps
events = get_events(close=prices,
                    t_events=timestamps,
                    pt_sl=[1, 1],
                    target=daily_vol,
                    min_ret=0.01)

# 3. Generate Labels (-1, 0, 1)
labels = get_bins(events, close_prices)
```

## 3. Purged K-Fold CV

**Goal**: Split data without leakage.

```python
from mlfinlab.cross_validation import PurgedKFold

pkf = PurgedKFold(n_splits=5,
                  embargo_pct=0.01) # 1% embargo

for train_idx, test_idx in pkf.split(X, y):
    X_train, y_train = X.iloc[train_idx], y.iloc[train_idx]
    X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]
    # Train and evaluate...
```

## 4. Deflated Sharpe Ratio (DSR)

**Goal**: Verify if SR is statistically significant given N trials.

```python
# Inputs:
# observed_sr: The SR of your best strategy
# sr_variance: Variance of SRs across all trials
# n_trials: Total number of strategies tested
# skew, kurtosis: of the returns

import numpy as np
from scipy.stats import norm

def estimated_dsr(observed_sr, sr_std, n_trials, skew, kurt, T):
    # Calculate Expected Maximum SR given N trials (false discovery benchmark)
    euler_masch = 0.5772
    exp_max_sr = sr_std * ((1 - euler_masch) * norm.ppf(1 - 1/n_trials) +
                          euler_masch * norm.ppf(1 - 1/(n_trials * np.e)))
    
    # Calculate DSR probability
    return norm.cdf((observed_sr - exp_max_sr) * np.sqrt(T-1) / 
                   np.sqrt(1 - skew * observed_sr + (kurt - 1)/4 * observed_sr**2))
```
