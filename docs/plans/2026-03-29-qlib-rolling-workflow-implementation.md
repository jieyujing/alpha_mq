# Qlib Rolling Workflow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个基于 Qlib 的代码内工作流，集成 `Alpha158` 特征、`path_target` 自定义标签以及半年的滚动模型重训逻辑。

**Architecture:** 
1. 继承 `Alpha158` 构建 `EnhancedAlpha158Handler`，在内部调用 `PathTargetBuilder` 生成路径质量标签。
2. 编写 `workflow_rolling.py` 脚本，手动迭代 6 个月时间窗口，完成数据切分、`LightGBM (lambdarank)` 训练及预测分合并。
3. 对接 Qlib 回测模块进行中证 1000 基准评估。

**Tech Stack:** Python 3.13, PyQlib, LightGBM, Polars (用于标签加速), Pandas.

---

### Task 1: 实现 EnhancedAlpha158Handler

在 `data/handler.py` 中实现自定义处理器，整合特征与路径标签。

**Files:**
- Create: `data/handler.py`
- Test: `tests/test_handler.py`

**Step 1: 编写基础测试**
验证 Handler 能成功初始化并加载 Alpha158 特征。

```python
def test_handler_init():
    from data.handler import EnhancedAlpha158Handler
    handler = EnhancedAlpha158Handler(instruments="csi1000", start_time="2024-01-01", end_time="2024-02-01")
    df = handler.fetch()
    assert "FEATURE" in df.columns.levels[0]
    assert "LABEL" in df.columns.levels[0]
```

**Step 2: 运行测试验证失败**
Run: `uv run pytest tests/test_handler.py`
Expected: FAIL (ModuleNotFoundError)

**Step 3: 编写核心实现**
实现继承逻辑，并调用 `PathTargetBuilder` 生成标签。

```python
from qlib.contrib.data.handler import Alpha158
from path_target import PathTargetBuilder, PathTargetConfig
import qlib.data.dataset.loader as loader

class EnhancedAlpha158Handler(Alpha158):
    def __init__(self, target_cfg: PathTargetConfig = None, **kwargs):
        self.target_cfg = target_cfg or PathTargetConfig()
        super().__init__(**kwargs)

    def _get_label_config(self):
        # 覆盖 Alpha158 默认标签，通过 PathTargetBuilder 注入
        # 这里返回一个空的配置，我们在 fetch 阶段手动合并
        return [], []

    def fetch(self, *args, **kwargs):
        df = super().fetch(*args, **kwargs)
        # 获取 close, market_close 和 beta 用于计算标签
        # 此处省略具体 Qlib Data 提取代码，实际实现需补全
        return df
```

**Step 4: 运行测试验证通过**
Run: `uv run pytest tests/test_handler.py`
Expected: PASS

**Step 5: Commit**
```bash
git add data/handler.py tests/test_handler.py
git commit -m "feat: add EnhancedAlpha158Handler with custom label integration"
```

---

### Task 2: 编写半年滚动训练脚本 (Rolling Workflow)

实现 `workflow_rolling.py`，负责时间窗口的轴向推进。

**Files:**
- Create: `workflow_rolling.py`

**Step 1: 编写滚动逻辑框架**
定义 6 个月步长的滑动窗口。

```python
import qlib
from qlib.workflow import R
from qlib.utils import exists_qlib_data

def rolling_task(start_val, end_test):
    # 手动计算窗口：train_start, train_end, test_start, test_end
    # retrain every 6 months
    pass
```

**Step 2: 集成 LightGBM LambdaRank**
配置模型参数。

```python
model_params = {
    "loss": "lambdarank",
    "objective": "lambdarank",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "verbosity": -1,
}
```

**Step 3: 串联测试集预测结果**
将多个 6 个月窗口的预测分合并成全样本。

**Step 4: Commit**
```bash
git add workflow_rolling.py
git commit -m "feat: implement semi-annual rolling workflow with LambdaRank"
```

---

### Task 3: 策略回测与评估

将预测分送入 Qlib 的回测系统。

**Files:**
- Modify: `workflow_rolling.py` (增加回测部分)

**Step 1: 配置 Strategy 与 Executor**
```python
from qlib.contrib.strategy import TopkDropoutStrategy
from qlib.backtest import backtest, executor
strategy_config = {
    "class": "TopkDropoutStrategy",
    "kwargs": {"model": model, "topk": 50, "n_drop": 5},
}
```

**Step 2: 执行回测并输出指标**
运行脚本，检查 `analysis_position.png` 和指标输出。

**Step 3: Commit**
```bash
git commit -am "feat: add portfolio analysis and backtesting to workflow"
```
