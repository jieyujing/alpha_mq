# 中证1000数据下载脚本 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 编写一个支持断点续传、严格流控的 Python 脚本，以批量拉取中证 1000 最新成分股及其指数基准的日行情、日频估值指标以及季度财务报表数据，分类存档到本地 CSV 中。

**Architecture:** 底层由一个带抖动机制的 `RateLimiter` 负责频控（1000次/5分），业务层则分解为解析器、进度跟踪器、核心拉取循环以及落地清洗器。模块将放置在 `data/scripts/download_gm.py` 内部或以该脚本为主入口，并使用 pandas 完成数据装配和存储。

**Tech Stack:** Python 3.13, Pandas, GM SDK (掘金), tenacity, uv

---

### Task 1: 项目基础库安装与目录搭建

**Files:**
- Create: `tests/test_imports.py`
- Modify: `pyproject.toml` (由 uv 隐式修改)

**Step 1: Write the failing test**
```python
# tests/test_imports.py
def test_dependencies():
    import gm.api
    import pandas
    import tenacity
    import tqdm
    assert True
```

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_imports.py -v`
Expected: FAIL due to missing modules like tenacity/tqdm/gm.

**Step 3: Write minimal implementation (Install deps & Create Dirs)**
```bash
uv add gm pandas tenacity tqdm
mkdir -p data/exports
```

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_imports.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add pyproject.toml uv.lock tests/test_imports.py
git commit -m "chore: setup dependencies and test imports"
```

---

### Task 2: 实现流控拦截器 (Rate Limiter)

由于直接测试真实 API 有限且慢，我们通过模拟时间推移或使用 dummy 延时测试。这里我们将 RateLimiter 作为 `download_gm.py` 的组件。

**Files:**
- Modify: `data/scripts/download_gm.py`
- Create: `tests/test_limiter.py`

**Step 1: Write the failing test**
```python
# tests/test_limiter.py
import time
from data.scripts.download_gm import RateLimiter

def test_rate_limiter_min_interval():
    limiter = RateLimiter(max_req=5, window=1)
    start = time.time()
    limiter.wait()
    limiter.wait()
    # 第二次调用应当有一定的间隔，至少需要 0.35s
    assert time.time() - start >= 0.35
```

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_limiter.py -v`
Expected: FAIL due to ImportError (download_gm.py doesn't have RateLimiter yet)

**Step 3: Write minimal implementation**
```python
# data/scripts/download_gm.py
import time
import collections
import random

class RateLimiter:
    def __init__(self, max_req=950, window=300):
        self.max_req = max_req
        self.window = window
        self.history = collections.deque()
        self.min_interval = 0.35

    def wait(self):
        now = time.time()
        while self.history and now - self.history[0] > self.window:
            self.history.popleft()
            
        if len(self.history) >= self.max_req:
            sleep_time = self.window - (now - self.history[0]) + 0.1
            time.sleep(sleep_time)
            
        now = time.time()
        if self.history and now - self.history[-1] < self.min_interval:
            jitter = random.uniform(0.05, 0.15)
            time.sleep(self.min_interval - (now - self.history[-1]) + jitter)
            
        self.history.append(time.time())
```

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_limiter.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add data/scripts/download_gm.py tests/test_limiter.py
git commit -m "feat: implement rate limiter for gm api"
```

---

### Task 3: 进度持久化管理器 (Checkpoint Manager)

帮助记录哪些 symbol 已经成功保存为对应的单独文件，从而实现断点跳过。

**Files:**
- Modify: `data/scripts/download_gm.py`
- Create: `tests/test_checkpoint.py`

**Step 1: Write the failing test**
```python
# tests/test_checkpoint.py
import os
from data.scripts.download_gm import get_downloaded_symbols

def test_get_downloaded(tmp_path):
    category_dir = tmp_path / "valuation"
    category_dir.mkdir()
    (category_dir / "SHSE.600000.csv").touch()
    (category_dir / "SZSE.000001.csv").touch()
    
    symbols = get_downloaded_symbols(str(category_dir))
    assert "SHSE.600000" in symbols
    assert "SZSE.000001" in symbols
    assert "SZSE.000002" not in symbols
```

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_checkpoint.py -v`
Expected: FAIL 

**Step 3: Write minimal implementation**
```python
# append to data/scripts/download_gm.py
import os
import glob

def get_downloaded_symbols(category_dir: str) -> set:
    if not os.path.isdir(category_dir):
        return set()
    csv_files = glob.glob(os.path.join(category_dir, "*.csv"))
    # 从文件名提取 symbol (剔除 .csv)
    symbols = {os.path.basename(f).replace('.csv', '') for f in csv_files}
    return symbols
```

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_checkpoint.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add data/scripts/download_gm.py tests/test_checkpoint.py
git commit -m "feat: add checkpoint checker for downloaded symbols from file directory"
```
---

### Task 4: 补齐掘金数据获取与清洗逻辑 (Fetch & Clean)

包括获取指数本身和成分股、以及按类型下载的主逻辑函数。针对真实接口只能用 integration test 手动跑验证，不强行写单测跑假接口，我们直接补全主体代码。

**Files:**
- Modify: `data/scripts/download_gm.py`

**Step 1: Write the Core Functions**
```python
# Append/Modify in data/scripts/download_gm.py
import logging
from tqdm import tqdm
from tenacity import retry, wait_exponential, stop_after_attempt
from gm.api import set_token, stk_get_index_constituents, history
from gm.api import stk_get_daily_valuation, stk_get_daily_basic, stk_get_daily_mktvalue
from gm.api import stk_get_fundamentals_balance, stk_get_fundamentals_income, stk_get_fundamentals_cashflow

# 设置您的 token 在顶部或者通过 env 读取
# TOKEN = "YOUR_TOKEN"

def clean_df_tz(df):
    if df is None or df.empty:
        return df
    # 删除时间戳列中的时区信息
    for col in df.select_dtypes(include=['datetime64[ns, Asia/Shanghai]', 'datetime64[ns, UTC]', 'datetimetz']).columns:
        df[col] = df[col].dt.tz_localize(None)
    return df

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_safe(func, *args, **kwargs):
    df = func(*args, **kwargs)
    return clean_df_tz(df)
```

**Step 2&3: Append Fetcher Loops** (代码会在执行环节详细分片粘贴，包含日行情、衍生变量、财务报表的循环逻辑和对于 benchmark symbol 的特殊处理) 

**Step 4: Commit**
```bash
git add data/scripts/download_gm.py
git commit -m "feat: data fetching functions and tz cleaning implemented"
```

---

### Task 5: 最终 Orchestration & CLI 入口

将以上的组件组装进行一键式执行。分为四个区块调用：

1. `set_token(...)`
2. 拉取成分股 & 构建 Base Pool = Constituents + `SHSE.000852`
3. 使用 `to_csv(..., mode='a')` 进行跳过过滤。
4. 加入全局日志捕捉。

---
