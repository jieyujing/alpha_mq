import pandas as pd
import numpy as np
import pytest
from src.etf_portfolio.ml_strategy import assemble_portfolio

def test_assemble_portfolio():
    # Mock scores
    scores = pd.Series({
        'SHSE.518800': 0.5, # Gold
        'SZSE.162411': 0.4, # Oil
        'SHSE.501018': 0.3, # Oil
        'SHSE.510300': 0.2, # HS300
        'SZSE.159915': 0.1, # ChiNext
    })
    
    weights = assemble_portfolio(scores, top_n=4, single_cap=0.40, energy_cap=0.20)
    
    # Check max 4 selected
    assert (weights > 0).sum() <= 4
    
    # Check single cap
    assert weights.max() <= 0.40 + 1e-6
    
    # Check energy cap
    assert weights.get('SZSE.162411', 0) + weights.get('SHSE.501018', 0) <= 0.20 + 1e-6
    
    # Check sum to 1
    np.testing.assert_almost_equal(weights.sum(), 1.0)
