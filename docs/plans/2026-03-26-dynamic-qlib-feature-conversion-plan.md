# 动态全字段 Qlib 转换实施计划 (Implementation Plan)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 升级数据转换流水线，实现 Parquet 数值特征的自动发现与二进制转换。

**Architecture:** 修改 `QlibBinConverter` 以动态提取数值列并维护全局字段全集，同时更新 `build_qlib_data.py` 以动态构建 `dump_bin` 命令参数。

**Tech Stack:** Polars, pyqlib, uv

---

### Task 1: 升级 `preprocess_fundamentals` 实现动态特征发现

**Files:**
- Modify: `data/qlib_converter.py`

**Step 1: 修改预处理逻辑**
在该方法中增加自动识别数值列的逻辑，并应用黑名单过滤。

```python
# data/qlib_converter.py 中的修改建议
def preprocess_fundamentals(self, df, value_columns=None, ...):
    ...
    if value_columns is None:
        # 自动发现数值列
        blacklist = {"rpt_type", "data_type", "is_audit"}
        exclude = {"symbol", "pub_date", "trade_date", "bob", "rpt_date"} | blacklist
        value_columns = [
            c for c in df.columns 
            if df[c].dtype.is_numeric() and c not in exclude
        ]
    ...
```

**Step 2: 验证单表提取**
运行测试脚本确保能提取出 `mny_cptl` 等新字段。

**Step 3: 提交**
```bash
git add data/qlib_converter.py
git commit -m "feat: implement dynamic numeric feature discovery in fundamentals preprocessing"
```

---

### Task 2: 升级 `convert_all_stocks` 实现全局 Schema 对齐

**Files:**
- Modify: `data/qlib_converter.py`

**Step 1: 全局字段收集**
修改 `convert_all_stocks`，首先扫描所有 Parquet 文件以确定所有股票公用的字段全集（Union set）。

**Step 2: 处理 diagonal join 后的空值**
确保在导出 CSV 前，所有字段都存在于 DataFrame 中（Polars join 会自动处理，但需确保顺序一致）。

**Step 3: 提交**
```bash
git add data/qlib_converter.py
git commit -m "feat: ensure global schema consistency across all converted stocks"
```

---

### Task 3: 升级 `build_qlib_data.py` 实现动态 Dump

**Files:**
- Modify: `data/scripts/build_qlib_data.py`

**Step 1: 动态读取 CSV 表头**
在调用 `run_dump_bin` 之前，读取生成的第一个 CSV 文件的表头。

**Step 2: 修改 `dump_bin` 命令行参数**
将表头中的所有列（排除 `symbol` 和 `date`）拼接到 `--include_fields`。

**Step 3: 提交**
```bash
git add data/scripts/build_qlib_data.py
git commit -m "feat: dynamic include_fields generation for dump_bin"
```

---

### Task 4: 最终物理验证

**Step 1: 运行全量构建**
Run: `uv run python data/scripts/build_qlib_data.py --years 2015 2016` (先用两年数据测试速度)

**Step 2: 检查二进制文件**
检查 `data/qlib_data/features/sh600006/` 目录下是否出现了 `mny_cptl.day.bin` 等新文件。

**Step 3: 提交**
```bash
git commit -am "chore: verify dynamic feature conversion results"
```
