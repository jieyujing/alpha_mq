import pandas as pd
import riskfolio as rp
from typing import Optional

def get_optimal_weights(returns: pd.DataFrame, model: str = 'EW', obj: str = 'MinRisk', rm: str = 'MV') -> pd.Series:
    """
    Get optimal weights for a given returns dataframe and model using riskfolio-lib.
    Supported models: EW, GMV, MaxSharpe, ERC, HRP, HERC, NCO.

    - EW: Equal Weight (no optimization)
    - GMV/MaxSharpe: Classic mean-variance via Portfolio.optimization()
    - ERC: Equal Risk Contribution via Portfolio.rp_optimization()
    - HRP/HERC/NCO: Hierarchical clustering via HCPortfolio.optimization()
    """
    # Robustness: Check number of assets
    n_assets = returns.shape[1]
    if n_assets == 0:
        return pd.Series(dtype=float)
    
    if n_assets == 1:
        return pd.Series([1.0], index=returns.columns, name='weights')

    if model == 'EW':
        weights = pd.Series(1.0 / n_assets, index=returns.columns)
        return weights.to_frame('weights')['weights']

    if model in ['HRP', 'HERC', 'NCO']:
        # Hierarchical models use a separate HCPortfolio class
        hc_port = rp.HCPortfolio(returns=returns)
        weights = hc_port.optimization(
            model=model,
            codependence='pearson',
            obj='MinRisk',
            rm='MV',
            rf=0,
            l=2,
            method_mu='hist',
            method_cov='ledoit',
            leaf_order=True,
        )
    else:
        # Classic and ERC models use Portfolio class
        port = rp.Portfolio(returns=returns)
        # Use Ledoit-Wolf shrinkage for covariance estimation
        port.assets_stats(method_mu='hist', method_cov='ledoit')

        if model == 'GMV':
            weights = port.optimization(model='Classic', rm='MV', obj='MinRisk', rf=0, l=0, hist=True)
        elif model == 'MaxSharpe':
            weights = port.optimization(model='Classic', rm='MV', obj='Sharpe', rf=0, l=0, hist=True)
        elif model == 'ERC':
            # ERC uses the dedicated risk parity optimization method
            weights = port.rp_optimization(model='Classic', rm='MV', rf=0, hist=True)
        else:
            raise ValueError(f"Unsupported model: {model}")

    if weights is None:
        raise ValueError(f"Optimization returned None for model {model}")

    return weights['weights']
