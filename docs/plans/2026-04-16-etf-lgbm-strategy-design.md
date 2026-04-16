# ETF Portfolio LightGBM Strategy Design

## Overview
A cross-asset style allocation strategy utilizing LightGBM for cross-sectional ranking of 15 ETFs. The strategy combines individual asset features (trend, risk, reversal) and shared macro relative-value features to predict risk-adjusted forward returns. Portfolio construction applies ReLU thresholding, normalization, and business constraints to ensure stability and risk management.

## 1. Data & Feature Engine
* **Target Label (`y`)**: `fwd_ret_20 / fwd_vol_20`. Predicting the 20-day forward risk-adjusted return.
* **Micro Features (Per ETF)**:
  * **Trend**: `ret_20`, `ret_60`, `ret_120`, `ma_gap_20`, `ma_gap_60`, `breakout_60`
  * **Risk**: `vol_20`, `vol_60`, `maxdd_60`
  * **Congestion**: `rsi_14`, `zscore_20`, `volume_z_20` (requires adding `volume` to GM data fetcher)
  * **Correlation**: `corr_to_510300_60`, `corr_to_511260_60`
* **Macro Broadcast Features (Shared)**:
  * `gold_oil_ratio`: `SHSE.518800 / SZSE.162411`
  * `growth_value_ratio`: `SZSE.159915 / SHSE.510300`
  * `long_short_bond_slope`: `SHSE.511090 / SHSE.511260`

## 2. LightGBM Rolling Engine
* **Frequency**: Monthly rebalancing.
* **Training Window**: Rolling 3 years (e.g., ~750 trading days).
* **Label Exclusion**: Exclude the most recent 20 days during training to prevent look-ahead bias from the `fwd_ret_20` calculation.
* **Model**: `LGBMRegressor` used to capture non-linear cross-asset dynamics. Trained on cross-sectional panel data.

## 3. Portfolio Construction (ReLU Assembly)
* **Screening**: Select Top 4 ETFs based on prediction score.
* **ReLU Filter**: Apply `max(0, score)`. If all Top 4 score <= 0, trigger defensive fallback.
* **Defensive Fallback**: Allocate 100% to 10Y Bond (`SHSE.511260`) or Gold (`SHSE.518800`) if the model is universally bearish.
* **Constraints**:
  1. Single asset cap: `35%`.
  2. Energy cap (Oil/Gas combined): `20%`.
* **Allocation**: Iteratively adjust weights and normalize (sum to 1) until constraints are satisfied.

## 4. Architecture Integration
* Implement purely in Pandas + LightGBM to maximize agility for the MVP.
* Create a dedicated module `src/etf_portfolio/ml_strategy.py`.
* Ensure outputs (daily portfolio returns) are compatible with the existing reporting layer to allow benchmarking against classical strategies.
