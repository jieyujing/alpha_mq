---
name: riskfolio-lib
description: "Skill for using the Riskfolio-Lib Python library for portfolio optimization and quantitative strategic asset allocation."
version: "0.1"
author: "Hermes Agent"
tags: ["finance", "portfolio", "optimization", "python"]
category: "data-science"
---

# Overview
Riskfolio‑Lib is a Python package that provides advanced tools for portfolio construction, risk measurement, and optimization. It implements classical mean‑variance models, Black‑Litterman, risk‑parity, hierarchical risk parity, and many modern approaches.

# Installation
```bash
pip install riskfolio-lib
```
> Requires Python ≥3.7 and the libraries `numpy`, `pandas`, `scipy`, `matplotlib`.

# Quick Start
```python
import pandas as pd
import riskfolio as rp

# 1️⃣ Load price data (e.g., daily close prices)
prices = pd.read_csv('prices.csv', index_col='Date', parse_dates=True)

# 2️⃣ Compute returns
returns = prices.pct_change().dropna()

# 3️⃣ Create a Portfolio object
port = rp.Portfolio(returns)

# 4️⃣ Estimate the risk‑return moments
port.assets_stats(method_mu='historical', method_cov='ledoit-wolf')

# 5️⃣ Choose an objective – here Minimum Variance (MV) with a risk‑budget constraint
def objective(w):
    return port.portfolio_performance(w)

# 6️⃣ Run the optimizer (different solvers are available)
weights = port.optimization(model='MV', rm='MV', obj='MinRisk', l=0, hist=True)

print('Optimized weights:', weights)

# 7️⃣ Plot the efficient frontier (optional)
port.plot_frontier()
```

# Core Concepts
- **Portfolio** – central class handling assets, moments, constraints, and solvers.
- **Risk Measures (`rm`)** – `MV` (variance), `CVaR`, `MAD`, `SemiStd`, `EVaR`, etc.
- **Objective Functions (`obj`)** – `MinRisk`, `MaxSharpe`, `Utility`, `ERC` (risk parity), `HRP` (hierarchical), etc.
- **Constraints** – you can set bounds, cardinality, sector exposure, turnover, etc. via `port.set_bounds()`, `port.set_cardinality()`, `port.set_sector_constraints()`.
- **Solvers** – default `SLSQP`; alternatives include `ECOS`, `CVXOPT`, `MOSEK` (if installed).

# Example Use Cases
## 1️⃣ Classical Mean‑Variance (Markowitz)
```python
port = rp.Portfolio(returns)
port.assets_stats(method_mu='mean', method_cov='ledoit-wolf')
weights = port.optimization(model='MV', rm='MV', obj='Sharpe', l=0.5)
```
## 2️⃣ Risk Parity (ERC)
```python
weights = port.optimization(model='ERC', rm='MV')
```
## 3️⃣ Hierarchical Risk Parity (HRP)
```python
weights = port.optimization(model='HRP', rm='MV')
```
## 4️⃣ Black‑Litterman Expected Returns
```python
port = rp.Portfolio(returns)
port.black_litterman(tau=0.025, P=None, Q=None, pi='market')
weights = port.optimization(model='BL', rm='MV', obj='Sharpe')
```

# Common Functions
| Function | Purpose |
|---|---|
| `rp.Portfolio(returns)` | Initialise with a DataFrame of asset returns |
| `assets_stats()` | Estimate mean, covariance, higher‑order moments |
| `set_bounds(lower, upper)` | Impose weight limits |
| `set_constraints()` | Add linear constraints (e.g., sector, turnover) |
| `optimization(model, rm, obj, **kwargs)` | Run the optimizer – choose model (`MV`, `ERC`, `HRP`, `BL`, …) and risk measure |
| `plot_frontier()` | Visualise efficient frontier |
| `plot_risk_contributions()` | Show each asset’s contribution to portfolio risk |

# References
- Official repository: https://github.com/dcajasn/Riskfolio-Lib
- Documentation: https://riskfolio-lib.readthedocs.io/
- Academic paper: "Riskfolio‑Lib: A Python library for portfolio optimization" (arXiv:2109.00943)
- Official repository: https://github.com/dcajasn/Riskfolio-Lib
- Documentation: https://riskfolio-lib.readthedocs.io/
- Academic paper: "Riskfolio‑Lib: A Python library for portfolio optimization" (arXiv:2109.00943)

# Tip for LLM Integration
When a downstream LLM needs to call a Riskfolio function, reference this skill and request the specific snippet. Example prompt to the model:
```
Use the `riskfolio-lib` skill to construct a minimum‑variance portfolio for the assets `AAPL`, `MSFT`, `GOOG` based on the CSV file `prices.csv`.
```
The skill will provide the exact code block and explain any required parameters.
