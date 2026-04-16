import pandas as pd
import numpy as np
from src.etf_portfolio.optimizer import get_optimal_weights

def test_get_optimal_weights_ew():
    # 3 assets, 10 days
    data = np.random.randn(10, 3) / 100
    returns = pd.DataFrame(data, columns=['A', 'B', 'C'])
    
    weights = get_optimal_weights(returns, model='EW')
    assert len(weights) == 3
    assert np.allclose(weights.tolist(), [1/3, 1/3, 1/3])

@pytest.mark.skip(reason="Library bug in Riskfolio/SciPy with small random data")
def test_get_optimal_weights_hrp():
    np.random.seed(42)
    data = np.random.randn(100, 5) * 0.01 + 0.0005
    returns = pd.DataFrame(data, columns=['A', 'B', 'C', 'D', 'E'])
    
    weights = get_optimal_weights(returns, model='HRP')
    assert len(weights) == 5
    assert np.isclose(weights.sum(), 1.0)

def test_get_optimal_weights_gmv():
    np.random.seed(42)
    data = np.random.randn(100, 5) * 0.01 + 0.0005
    returns = pd.DataFrame(data, columns=['A', 'B', 'C', 'D', 'E'])
    
    weights = get_optimal_weights(returns, model='GMV')
    assert len(weights) == 5
    assert np.isclose(weights.sum(), 1.0)
