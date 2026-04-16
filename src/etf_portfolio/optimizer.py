import pandas as pd
import riskfolio as rp
from typing import Optional

def get_optimal_weights(returns: pd.DataFrame, model: str = 'EW', obj: str = 'MinRisk', rm: str = 'MV') -> pd.Series:
    """
    Get optimal weights for a given returns dataframe and model using riskfolio-lib.
    Supported models: EW, GMV, MaxSharpe, ERC, HRP, HERC, NCO.
    """
    if model == 'EW':
        n = returns.shape[1]
        weights = pd.Series(1.0 / n, index=returns.columns)
        return weights.to_frame('weights')['weights']

    # For other models, use riskfolio
    port = rp.Portfolio(returns=returns)
    
    # Estimate assets stats
    port.assets_stats()
    
    if model == 'GMV':
        weights = port.optimization(model='Classic', rm='MV', obj='MinRisk', rf=0, l=0, hist=True)
    elif model == 'MaxSharpe':
        weights = port.optimization(model='Classic', rm='MV', obj='Sharpe', rf=0, l=0, hist=True)
    elif model in ['ERC', 'HRP', 'HERC', 'NCO']:
        if model == 'ERC':
             weights = port.optimization(model='ERC', rm='MV', rf=0, l=0, hist=True)
        else:
             weights = port.optimization(model=model, rm='MV', rf=0, l=0, hist=True)
    else:
        raise ValueError(f"Unsupported model: {model}")

    return weights['weights']
