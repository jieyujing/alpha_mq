
import qlib
from qlib.contrib.data.handler import Alpha158
from qlib.data import D
from pathlib import Path

qlib_bin = "data/qlib_bin"
qlib.init(provider_uri=qlib_bin)

instruments = "csi1000"
start = "2020-01-01"
end = "2020-02-01"

handler = Alpha158(instruments=instruments, start_time=start, end_time=end)
df = handler.fetch()
print(f"Alpha158 index names: {df.index.names}")

close_df = D.features(["SH600000"], ["$close"], start_time=start, end_time=end, freq="day")
print(f"D.features index names: {close_df.index.names}")
