import pandas as pd
from gm.api import set_token, get_history_constituents
from data.utils.env_utils import get_gm_token

def build_instrument_history(start_date: str, end_date: str) -> pd.DataFrame:
    # 实际环境需要在外层 set_token，此处只保留核心逻辑提取
    df = get_history_constituents(index='SHSE.000852', start_date=start_date, end_date=end_date) # 仅简单实现供测试
    return df
