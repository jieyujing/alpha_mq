# Qlib 数据格式转换实施计划 (Implementation Plan)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个稳健的数据转换流水线，将掘金 Parquet 数据转换为 Qlib 二进制格式，确保财务数据填充无“未来函数”。

**Architecture:** 采用两阶段流程：首先利用 Polars 高效合并价格与基本面数据，执行严谨的披露日期对齐与前向填充，生成中间 CSV；随后调用 Qlib 的 `dump_bin` 引擎进行物理转换。

**Tech Stack:** Polars, Pandas, pyqlib, pyarrow, uv

---

### Task 1: 准备环境与辅助工具类

**Files:**
- Create: `data/utils/date_utils.py`
- Modify: `pyproject.toml`

**Step 1: 添加必要的依赖**
Run: `uv add polars pyarrow`

**Step 2: 编写日期处理工具**
确保日期转换的一致性。
```python
import pandas as pd
def to_date_str(dt):
    return pd.to_datetime(dt).strftime('%Y-%m-%d')
```

**Step 3: 提交**
```bash
git add pyproject.toml data/utils/date_utils.py
git commit -m "feat: add polars dependency and date utils"
```

---

### Task 2: 实现 QlibBinConverter 核逻辑 (数据合并与 FFill)

**Files:**
- Create: `data/qlib_converter.py`
- Test: `tests/test_qlib_converter.py`

**Step 1: 编写数据对齐测试**
编写测试用例，验证 FFill 是否正确避开了未来函数。
```python
def test_ffill_no_lookahead():
    # 模拟 4/20 披露 3/31 财报的情形
    # 验证 4/19 的数据仍为旧值，4/20 变为新值
    pass
```

**Step 2: 实现合并与填充逻辑**
使用 Polars 进行左连接，并按 `symbol` 分组执行 `ffill`。
```python
import polars as pl
class QlibBinConverter:
    def __init__(self, raw_dir, output_dir):
        self.raw_dir = raw_dir
        self.output_dir = output_dir
    
    def process_stock(self, symbol, price_df, fund_df):
        # Join on pub_date, then ffill
        pass
```

**Step 3: 运行测试并提交**
```bash
uv run pytest tests/test_qlib_converter.py
git add data/qlib_converter.py tests/test_qlib_converter.py
git commit -m "feat: implement QlibBinConverter merging and ffill logic"
```

---

### Task 3: 实现 CSV 导出与 Qlib Dump 集成

**Files:**
- Modify: `data/qlib_converter.py`
- Create: `data/scripts/build_qlib_data.py`

**Step 1: 实现 CSV 生成逻辑**
将合并后的 DataFrame 导出为 Qlib 期待的 CSV 格式（`date`, `open`, `close`...）。

**Step 2: 编写主脚本**
自动化执行：读取 Raw -> Converter -> 生成日历 -> 调用 `qlib.utils.dump_bin`。
```python
import qlib.utils.dump_bin as dump_bin
def main():
    # ... 串联流程 ...
    dump_bin.main(csv_path, qlib_dir, backup_dir=None)
```

**Step 3: 物理验证**
手动运行脚本转换一只股票，检查 `data/qlib_data/features/<symbol>/` 下是否生成了多个 `.bin` 文件。

**Step 4: 提交**
```bash
git add data/qlib_converter.py data/scripts/build_qlib_data.py
git commit -m "feat: complete qlib data conversion pipeline"
```
