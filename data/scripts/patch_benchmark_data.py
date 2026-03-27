import pandas as pd
from pathlib import Path
from gm.api import set_token, history
from data.utils.env_utils import get_gm_token

def fetch_index_data(symbol="SHSE.000852", start="2015-01-01"):
    """
    使用掘金 API 下载中证1000指数数据。
    """
    token = get_gm_token()
    set_token(token)
    # 获取当前日期作为结束日期
    end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
    print(f"正在从掘金下载 {symbol} 行情数据 ({start} 至 {end_date})...")
    df = history(
        symbol=symbol, 
        frequency='1d', 
        start_time=start, 
        end_time=end_date, 
        df=True
    )
    if df is None or df.empty:
        raise ValueError(f"未能获取到 {symbol} 的行情数据，请检查 Token 或网络。")
    return df
