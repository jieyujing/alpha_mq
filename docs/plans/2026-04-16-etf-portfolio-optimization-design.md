# ETF Portfolio Optimization Comparison Using Riskfolio-Lib
**Date:** 2026-04-16

## 1. Overview
The goal is to fetch historical price data for 15 core ETFs using the `gm` (掘金量化) API, and use `riskfolio-lib` to run a rolling backtest comparing the performance of various portfolio optimization algorithms. Finally, comprehensive quantstats tear sheets will be generated for each strategy to analyze its historical risk/return profile.

## 2. ETF Pool
The target universe includes 15 ETFs capturing stocks (A-share, HK, US), bonds, and commodities (gold, crude oil) to provide a broadly diversified universe:
- `SHSE.513120` (港股创新药ETF)
- `SZSE.159301` (公用事业ETF)
- `SZSE.159869` (游戏ETF)
- `SHSE.511260` (10年期国债ETF)
- `SHSE.511090` (30年期国债ETF)
- `SHSE.511380` (可转债ETF)
- `SHSE.518800` (黄金ETF)
- `SHSE.510300` (沪深300ETF)
- `SZSE.159915` (创业板ETF)
- `SHSE.513920` (港股通央企红利ETF)
- `SZSE.159920` (恒生ETF)
- `SZSE.159742` (恒生科技ETF)
- `SZSE.159941` (纳指ETF)
- `SHSE.501018` (南方原油ETF)
- `SZSE.162411` (华宝油气ETF)

## 3. Data Engineering (GM SDK)
- **Data Source**: Fetch historical daily close prices using `gm.api.history`.
- **Lookback Period**: Default 5 years to present.
- **Alignment**: Forward fill missing data (`ffill`) on a unified daily trading calendar to account for non-overlapping trading holidays between different markets.

## 4. Rolling Backtest Engine
- **Lookback Window**: 252 trading days (~1 year).
- **Rebalance Frequency**: Monthly (resample to end of month calculating weights).
- **Execution Assumption**: Use end of day closing prices for return calculations and portfolio weighting logic. 

## 5. Portfolio Construction Matrix (Riskfolio-lib)
Run parallel optimizations to compute weights at every rebalance point for the following strategies:
1. **Equal Weight (EW)**: Baseline equal distribution.
2. **Global Minimum Variance (GMV)**: `Model='MV', Obj='MinRisk'`.
3. **Maximum Sharpe Ratio (MaxSharpe)**: `Model='MV', Obj='MaxSharpe'`.
4. **Equal Risk Contribution / Risk Parity (ERC)**: `Model='ERC'`.
5. **Hierarchical Risk Parity (HRP)**: `Model='HRP'`.
6. **Hierarchical Equal Risk Contribution (HERC)**: `Model='HERC'`.
7. **Nested Clustered Optimization (NCO)**: `Model='NCO'`.

## 6. Evaluation & Reporting
- Generate daily portfolio return series natively from the rolling engine.
- Integrate with `quantstats.reports.html`.
- For each optimization algorithm, output a comprehensive HTML analysis tear sheet (Underwater plot, heatmap, Max Drawdown, Calmar, Sortino, rolling volatility) into a designated `reports/` folder.
