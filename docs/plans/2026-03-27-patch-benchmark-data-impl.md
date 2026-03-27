# 中证1000基准数据补充补丁实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 开发一个临时脚本 `patch_benchmark_data.py`，用于下载中证1000指数数据并同步至 Qlib 二进制存储。

**Architecture:** 独立补丁脚本，利用 `gm.api` 获取数据，通过 `pandas/polars` 规整化，并修改 `all.txt` 元数据后触发 `dump_bin.py`。

**Tech Stack:** Python 3.13, gm.api, pandas, polars, pathlib, qlib-utils.

---

### Task 1: 脚本基础结构与数据获取

**Files:**
- Create: `data/scripts/patch_benchmark_data.py`

**Step 1: 编写数据获取核心逻辑**

```python
import pandas as pd
from pathlib import Path
from gm.api import set_token, history
from data.utils.env_utils import get_gm_token

def fetch_index_data(symbol="SHSE.000852", start="2015-01-01"):
    token = get_gm_token()
    set_token(token)
    df = history(symbol=symbol, frequency='1d', start_time=start, end_time=pd.Timestamp.now().strftime('%Y-%m-%d'), df=True)
    return df
```

**Step 2: 验证数据下载（模拟测试）**

Run: `uv run python -c "from data.scripts.patch_benchmark_data import fetch_index_data; print(fetch_index_data().head())"`
Expected: 打印出中证1000指数的历史 OHLCV 数据。

---

### Task 2: CSV 转换与本地预存储

**Files:**
- Modify: `data/scripts/patch_benchmark_data.py`

**Step 1: 实现格式标准化逻辑**

```python
def process_to_csv(df, output_path: Path):
    # 格式转换
    df['date'] = pd.to_datetime(df['bob']).dt.strftime('%Y-%m-%d')
    df['symbol'] = df['symbol'].replace('SHSE.000852', 'SH000852')
    cols = ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']
    df_clean = df[cols]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_csv(output_path, index=False)
    return df_clean['date'].unique().tolist()
```

**Step 2: 运行转换并检查文件**

Run: `uv run python -c "from data.scripts.patch_benchmark_data import fetch_index_data, process_to_csv; from pathlib import Path; df=fetch_index_data(); process_to_csv(df, Path('data/csv_source/SH000852.csv'))"`
Expected: 生成 `data/csv_source/SH000852.csv`，列名正确且 symbol 为 SH000852。

---

### Task 3: 元数据（Instruments & Calendars）同步

**Files:**
- Modify: `data/scripts/patch_benchmark_data.py`

**Step 1: 编写元数据更新函数**

```python
def update_metadata(qlib_dir: Path, symbol='SH000852', dates=None):
    # 更新 instruments/all.txt
    inst_path = qlib_dir / "instruments" / "all.txt"
    if inst_path.exists():
        with open(inst_path, 'r') as f:
            lines = f.readlines()
        if not any(symbol in l for l in lines):
            start_date = dates[0]
            end_date = dates[-1]
            with open(inst_path, 'a') as f:
                f.write(f"{symbol}\t{start_date}\t{end_date}\n")
    
    # 更新 calendars/day.txt
    cal_path = qlib_dir / "calendars" / "day.txt"
    if cal_path.exists() and dates:
        with open(cal_path, 'r') as f:
            existing_dates = set(l.strip() for l in f.readlines())
        new_dates = sorted(existing_dates | set(dates))
        with open(cal_path, 'w') as f:
            for d in new_dates: f.write(f"{d}\n")
```

**Step 2: 验证 instruments 更新**

Run: `grep "SH000852" data/qlib_data/instruments/all.txt`
Expected: 能够搜索到该行。

---

### Task 4: 触发 Qlib 二进制转换

**Files:**
- Modify: `data/scripts/patch_benchmark_data.py`

**Step 1: 集成子进程调用**

```python
import subprocess
import sys

def run_dump(csv_path: Path, qlib_dir: Path):
    dump_script = Path("data/scripts/dump_bin.py")
    cmd = [
        sys.executable, str(dump_script), "dump_all",
        "--data_path", str(csv_path.parent),
        "--qlib_dir", str(qlib_dir),
        "--include_fields", "open,high,low,close,volume,amount",
        "--symbol_field_name", "symbol",
        "--limit_nums", "1" # 限制只看当前 CSV
    ]
    # 这里需要临时重命名目录以规避 dump_all 全量扫描，或者直接指定具体文件
    subprocess.run(cmd)

def main():
    qlib_dir = Path("data/qlib_data")
    csv_file = Path("data/csv_source/SH000852.csv")
    print("Fetching data...")
    df = fetch_index_data()
    print("Processing...")
    dates = process_to_csv(df, csv_file)
    print("Updating metadata...")
    update_metadata(qlib_dir, 'SH000852', dates)
    print("Dumping to binary...")
    run_dump(csv_file, qlib_dir)
    print("Done!")

if __name__ == "__main__":
    main()
```

**Step 2: 执行全流程补丁**

Run: `uv run python data/scripts/patch_benchmark_data.py`
Expected: 终端显示 "Done!"，且 `data/qlib_data/features/sh000852/` 目录下生成 bin 文件。
