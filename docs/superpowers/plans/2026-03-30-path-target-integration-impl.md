# Path Target Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 path_target 集成到 qlib workflow，替换默认收益率 label 为路径质量评分。

**Architecture:** 继承 Alpha158 Handler，重写 fetch() 方法合并自定义 label。从 qlib provider 获取 close/benchmark 数据，计算滚动 beta，调用 PathTargetBuilder 生成 target。

**Tech Stack:** qlib, polars, pandas, numpy, pytest

---

## File Structure

| 文件 | 操作 | 说明 |
|------|------|------|
| `data/handler.py` | 修复 + 完善 | Alpha158PathTargetHandler 实现 |
| `workflow_by_code.py` | 修改 | 更新 CSI1000_GBDT_TASK handler 配置 |
| `tests/test_handler.py` | 扩展 | Handler 验证测试 |
| `path_target.py` | 不改动 | 路径质量计算核心 |

---

### Task 1: 修复 data/handler.py 导入路径

**Files:**
- Modify: `data/handler.py:1-7`

- [ ] **Step 1: 检查当前导入问题**

当前代码:
```python
from path_target import PathTargetBuilder, PathTargetConfig
```

问题: `path_target.py` 在项目根目录，`data/handler.py` 在子目录，需要相对导入。

- [ ] **Step 2: 修复导入路径**

将第 5 行改为:
```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from path_target import PathTargetBuilder, PathTargetConfig
```

或者更简洁的方式 - 在文件顶部添加:
```python
from pathlib import Path
import sys
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from path_target import PathTargetBuilder, PathTargetConfig
```

---

### Task 2: 重命名 Handler 类并添加 benchmark 参数

**Files:**
- Modify: `data/handler.py:8-12`

- [ ] **Step 1: 重命名类为 Alpha158PathTargetHandler**

将第 8 行改为:
```python
class Alpha158PathTargetHandler(Alpha158):
    """
    继承 Alpha158，替换 label 为 path_target。

    Parameters
    ----------
    benchmark : str
        市场基准代码，默认 "SH000852" (中证1000)
    path_target_config : PathTargetConfig
        路径质量配置，默认 None 使用默认配置
    beta_window : int
        beta 计算滚动窗口，默认 60 日
    """

    def __init__(
        self,
        benchmark: str = "SH000852",
        path_target_config: PathTargetConfig = None,
        beta_window: int = 60,
        **kwargs
    ):
        self.benchmark = benchmark
        self.target_cfg = path_target_config or PathTargetConfig()
        self.beta_window = beta_window
        super().__init__(**kwargs)
```

- [ ] **Step 2: 更新 builder 实例化**

将第 59 行改为使用 self.target_cfg:
```python
builder = PathTargetBuilder(self.target_cfg)
```

---

### Task 3: 修复 fetch 方法中的 benchmark 参数

**Files:**
- Modify: `data/handler.py:34`

- [ ] **Step 1: 将硬编码 benchmark 改为参数化**

将第 34 行改为:
```python
bench_close = D.features([self.benchmark], ["$close"], start_time, end_time)
```

- [ ] **Step 2: 修复 bench_wide 列名提取**

将第 36 行改为动态获取基准代码:
```python
bench_wide.columns = [self.benchmark]
```

- [ ] **Step 3: 修复 bench_ret 计算**

将第 42 行改为:
```python
bench_ret = bench_wide.set_index("date")[self.benchmark].pct_change()
```

---

### Task 4: 添加数据缺失处理

**Files:**
- Modify: `data/handler.py:28-51`

- [ ] **Step 1: 在 fetch 方法添加空数据检查**

在第 27 行后添加:
```python
# 检查数据是否为空
if raw_close.empty:
    raise ValueError(f"No close data found for instruments {instruments} between {start_time} and {end_time}")
```

- [ ] **Step 2: 在 beta 计算后添加 NaN 处理**

将第 51 行改为:
```python
beta_df = beta_df.fillna(1.0).clip(0.1, 3.0).reset_index()  # Fill NaN with 1.0, clip extreme values
```

---

### Task 5: 完善 fetch 方法返回格式

**Files:**
- Modify: `data/handler.py:64-76`

- [ ] **Step 1: 确保 target 列名符合 qlib 规范**

将第 65-68 行改为:
```python
target_df = target_series.to_frame("target")
target_df.index.names = ["datetime", "instrument"]

# qlib expects LABEL level in MultiIndex columns
target_df.columns = pd.MultiIndex.from_tuples([("LABEL", "target")])
```

- [ ] **Step 2: 确保 FEATURE 列正确设置**

将第 71-72 行改为:
```python
if not isinstance(df.columns, pd.MultiIndex):
    # Alpha158 features need MultiIndex columns
    df.columns = pd.MultiIndex.from_product([["FEATURE"], df.columns])
```

- [ ] **Step 3: 合并时处理列名冲突**

将第 75 行改为:
```python
# Align index before concat
target_df = target_df.reindex(df.index)
result = pd.concat([df, target_df], axis=1)
return result.sort_index(axis=1)
```

---

### Task 6: 更新 workflow_by_code.py handler 配置

**Files:**
- Modify: `workflow_by_code.py:45-76`

- [ ] **Step 1: 修改 handler 配置**

将 `CSI1000_GBDT_TASK["dataset"]["kwargs"]["handler"]` 部分修改为:

```python
CSI1000_GBDT_TASK = {
    "model": {
        "class": "LGBModel",
        "module_path": "qlib.contrib.model.gbdt",
        "kwargs": {
            "loss": "mse",
            "colsample_bytree": 0.8879,
            "learning_rate": 0.0421,
            "subsample": 0.8789,
            "lambda_l1": 205.6999,
            "lambda_l2": 580.9768,
            "max_depth": 8,
            "num_leaves": 210,
            "num_threads": 20,
        },
    },
    "dataset": {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "Alpha158PathTargetHandler",
                "module_path": "data.handler",
                "kwargs": {
                    "start_time": "2015-01-05",
                    "end_time": "2026-03-26",
                    "fit_start_time": "2015-01-05",
                    "fit_end_time": "2022-12-31",
                    "instruments": CSI1000_MARKET,
                    "benchmark": CSI1000_BENCH,
                    "filter_pipe": [
                        {
                            "filter_type": "ExpressionDFilter",
                            "rule_expression": "$volume > 0",
                            "filter_start_time": None,
                            "filter_end_time": None,
                            "keep": True,
                        }
                    ],
                },
            },
            "segments": {
                "train": ("2015-01-05", "2022-12-31"),
                "valid": ("2023-01-01", "2023-12-31"),
                "test": ("2024-01-01", "2026-03-25"),
            },
        },
    },
}
```

- [ ] **Step 2: 在文件顶部添加导入（可选）**

如果需要显式导入 Handler，在 import 区域添加:
```python
from data.handler import Alpha158PathTargetHandler
```

---

### Task 7: 扩展测试验证 Handler 功能

**Files:**
- Modify: `tests/test_handler.py`

- [ ] **Step 1: 检查现有测试文件**

```bash
cat tests/test_handler.py
```

- [ ] **Step 2: 添加 Handler 导入和初始化测试**

```python
import pytest
import pandas as pd
import polars as pl
from pathlib import Path
import sys

_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from data.handler import Alpha158PathTargetHandler
from path_target import PathTargetConfig


class TestAlpha158PathTargetHandler:
    """测试 Alpha158PathTargetHandler 类"""

    def test_handler_init_with_defaults(self):
        """测试默认参数初始化"""
        handler = Alpha158PathTargetHandler(
            start_time="2024-01-01",
            end_time="2024-12-31",
            instruments="all",
        )
        assert handler.benchmark == "SH000852"
        assert handler.beta_window == 60
        assert handler.target_cfg is not None

    def test_handler_init_with_custom_config(self):
        """测试自定义参数初始化"""
        custom_config = PathTargetConfig(
            vol_window=30,
            k_upper=1.5,
            k_lower=1.5,
            max_holding=5,
        )
        handler = Alpha158PathTargetHandler(
            benchmark="SH000300",
            path_target_config=custom_config,
            beta_window=40,
            start_time="2024-01-01",
            end_time="2024-12-31",
            instruments="all",
        )
        assert handler.benchmark == "SH000300"
        assert handler.beta_window == 40
        assert handler.target_cfg.vol_window == 30
```

- [ ] **Step 3: 添加 fetch 方法测试（需要 qlib 数据）**

```python
    @pytest.mark.integration
    def test_handler_fetch_returns_multiindex(self):
        """测试 fetch 返回 MultiIndex DataFrame"""
        import qlib
        from qlib.constant import REG_CN

        provider_uri = Path(__file__).parent.parent / "data" / "qlib_data"
        qlib.init(provider_uri=str(provider_uri), region=REG_CN)

        handler = Alpha158PathTargetHandler(
            start_time="2024-01-01",
            end_time="2024-01-31",
            instruments="all",
        )

        df = handler.fetch(col_set=["feature", "label"])

        # 检查返回格式
        assert isinstance(df, pd.DataFrame)
        assert isinstance(df.columns, pd.MultiIndex)

        # 检查包含 FEATURE 和 LABEL
        column_levels = df.columns.get_level_values(0).unique()
        assert "FEATURE" in column_levels
        assert "LABEL" in column_levels

        # 检查 label 值范围 (0, 1)
        label_values = df[("LABEL", "target")].dropna()
        assert label_values.min() >= 0
        assert label_values.max() <= 1
```

- [ ] **Step 4: 运行测试验证**

```bash
pytest tests/test_handler.py -v
```

Expected: PASS (基础测试), SKIP (integration 测试需要数据)

---

### Task 8: 集成测试 - 运行完整 workflow

**Files:**
- None (验证性测试)

- [ ] **Step 1: 运行 workflow 确认无错误**

```bash
cd /Users/link/Documents/alpha_mq
python workflow_by_code.py
```

Expected:
- qlib 初始化成功
- Handler 加载成功
- Dataset prepare 成功
- Model fit 开始

- [ ] **Step 2: 检查生成的 label 分布**

在 workflow 运行后，添加检查代码:
```python
# 在 R.start 块内，model.fit 后添加
recorder = R.get_recorder()
label_df = recorder.load_object("label.pkl")
print(f"Label statistics:\n{label_df.describe()}")
print(f"Label range: [{label_df.min().min():.4f}, {label_df.max().max():.4f}]")
```

Expected: label 值在 (0, 1) 范围内

- [ ] **Step 3: Commit 完成的集成**

```bash
git add data/handler.py workflow_by_code.py tests/test_handler.py
git commit -m "feat: integrate path_target into qlib workflow

- Rename handler to Alpha158PathTargetHandler
- Add benchmark parameter for dynamic beta calculation
- Fix import path for path_target module
- Update workflow_by_code.py handler config
- Add unit tests for handler initialization and fetch

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review Checklist

**1. Spec Coverage:**
- ✅ Task 1-5: Handler 实现 (data/handler.py)
- ✅ Task 6: workflow 配置更新
- ✅ Task 7-8: 测试验证

**2. Placeholder Scan:**
- ✅ 无 TBD/TODO
- ✅ 所有步骤有具体代码

**3. Type Consistency:**
- ✅ `Alpha158PathTargetHandler` 类名一致
- ✅ `benchmark` 参数名一致
- ✅ `PathTargetConfig` 类型一致

---

## Execution Notes

**依赖检查**:
- qlib 已安装
- polars 已安装
- pandas 已安装
- pytest 已安装

**风险提示**:
- qlib provider 需正确指向 `data/qlib_data`
- path_target 计算耗时约 1-2 分钟（全量数据）