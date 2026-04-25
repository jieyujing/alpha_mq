from qlib.data import D
from qlib.contrib.data.handler import Alpha158
from qlib.constant import REG_CN
import qlib
import pandas as pd

qlib.init(provider_uri='data/qlib_data', region=REG_CN)
try:
    handler = Alpha158(instruments=['SH600006'], start_time='2024-01-01', end_time='2024-01-15')
    df = handler.fetch()
    print('---Alpha158 Fetch Index Names---')
    print(df.index.names)
    print('---Alpha158 Fetch Columns---')
    print(df.columns.levels[0])
except Exception as e:
    print(f"Error: {e}")
