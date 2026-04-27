# GM → Qlib 数据接入管道实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个配置驱动的自动化管道，将掘金 (GM) 股票数据转化为符合 Qlib 格式的 PIT 财务数据和 OHLCV 二进制数据。

**Architecture:** 采用 Template Method 模式定义 Pipeline 骨架，通过 YAML 配置驱动 Stage 执行（Download -> Validate -> Clean -> Ingest）。使用桥接模式连接 GM 数据源与 Qlib 工具链。

**Tech Stack:** Python 3.13, uv, Qlib, PyYAML, Pandas, Parquet, Pytest.

---

### Task 1: 项目骨架与目录初始化

**Files:**
- Create: `src/pipelines/__init__.py`
- Create: `src/pipelines/data_ingest/__init__.py`
- Create: `src/core/__init__.py`

**Step 1: 创建必要的包目录和初始化文件**

```bash
mkdir -p src/pipelines/data_ingest
mkdir -p src/core
touch src/pipelines/__init__.py
touch src/pipelines/data_ingest/__init__.py
touch src/core/__init__.py
```

**Step 2: 验证目录结构**

Run: `ls -R src/pipelines src/core`
Expected: 看到相应的 `__init__.py` 文件。

**Step 3: Commit**

```bash
git add src/pipelines src/core
git commit -m "chore: initialize pipeline and core package skeleton"
```

---

### Task 2: 实现 DataPipeline 抽象基类

**Files:**
- Create: `src/pipelines/base.py`
- Create: `tests/pipelines/test_base.py`

**Step 1: 编写 DataPipeline 生命周期测试**

```python
# tests/pipelines/test_base.py
import pytest
from pipelines.base import DataPipeline

class MockPipeline(DataPipeline):
    def __init__(self, config):
        super().__init__(config)
        self.called = []
    def download(self): self.called.append("download")
    def validate(self): return []
    def clean(self): self.called.append("clean")
    def ingest_to_qlib(self): self.called.append("ingest")

def test_pipeline_flow():
    config = {"pipeline": {"name": "Mock", "stages": ["download", "clean"]}}
    pipeline = MockPipeline(config)
    pipeline.run()
    assert pipeline.called == ["download", "clean"]
```

**Step 2: 运行测试并确认失败**

Run: `uv run pytest tests/pipelines/test_base.py`
Expected: FAIL (ModuleNotFoundError: No module named 'pipelines.base')

**Step 3: 实现 DataPipeline 基类**

```python
# src/pipelines/base.py
from abc import ABC, abstractmethod

class DataPipeline(ABC):
    VALID_STAGES = ["download", "validate", "clean", "ingest"]
    
    def __init__(self, config: dict):
        self.config = config
        self.stages = config["pipeline"]["stages"]
    
    def run(self) -> None:
        self.setup()
        try:
            if "download" in self.stages: self.download()
            if "validate" in self.stages: self.validate()
            if "clean" in self.stages: self.clean()
            if "ingest" in self.stages: self.ingest_to_qlib()
        finally:
            self.teardown()
            
    def setup(self): pass
    def teardown(self): pass
    @abstractmethod
    def download(self): ...
    @abstractmethod
    def validate(self): ...
    @abstractmethod
    def clean(self): ...
    @abstractmethod
    def ingest_to_qlib(self): ...
```

**Step 4: 再次运行测试并确认通过**

Run: `uv run pytest tests/pipelines/test_base.py`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pipelines/base.py tests/pipelines/test_base.py
git commit -m "feat: add DataPipeline base class and life-cycle tests"
```

---

### Task 3: 实现 SymbolAdapter (GM ↔ Qlib 转换)

**Files:**
- Create: `src/core/symbol.py`
- Create: `tests/core/test_symbol.py`

**Step 1: 编写转换测试**

```python
# tests/core/test_symbol.py
from core.symbol import SymbolAdapter

def test_symbol_conversion():
    assert SymbolAdapter.to_qlib("SHSE.600000") == "SH600000"
    assert SymbolAdapter.to_gm("SZ000001") == "SZSE.000001"
```

**Step 2: 实现 SymbolAdapter**

```python
# src/core/symbol.py
class SymbolAdapter:
    _TO_QLIB = {"SHSE": "SH", "SZSE": "SZ"}
    _TO_GM = {"SH": "SHSE", "SZ": "SZSE"}

    @staticmethod
    def to_qlib(gm_symbol: str) -> str:
        ex, code = gm_symbol.split(".")
        return f"{SymbolAdapter._TO_QLIB.get(ex, ex)}{code}"

    @staticmethod
    def to_gm(qlib_symbol: str) -> str:
        prefix, code = qlib_symbol[:2], qlib_symbol[2:]
        return f"{SymbolAdapter._TO_GM.get(prefix, prefix)}.{code}"
```

**Step 3: 验证测试通过并提交**

Run: `uv run pytest tests/core/test_symbol.py`
Commit: `git add src/core/symbol.py tests/core/test_symbol.py && git commit -m "feat: add SymbolAdapter for GM/Qlib symbol conversion"`

---

### Task 4: 实现 OhlcvConverter 与 FeatureConverter

**Files:**
- Create: `src/pipelines/data_ingest/qlib_converter.py`

**Step 1: 实现 Ohlcv 转换逻辑**
读取 exports 目录下的日频 Parquet，按 symbol 导出为 Qlib 兼容的 CSV。

**Step 2: 实现 Feature 转换逻辑**
处理估值数据（pe_ttm 等）和市场指标数据，并合并到对应的 symbol CSV 中。

**Step 3: Commit**
```bash
git add src/pipelines/data_ingest/qlib_converter.py
git commit -m "feat: add Ohlcv and Feature converters for Qlib"
```

---

### Task 5: 实现 PitConverter (严格 PIT 财务数据)

**Files:**
- Modify: `src/pipelines/data_ingest/qlib_converter.py`

**Step 1: 实现财务报表转换逻辑**
使用 `pub_date` 作为 Qlib 的 `date` 字段，实现严格 PIT。

**Step 2: 实现字段自动发现机制**
扫描 Parquet 列名，动态生成 PIT 格式 CSV (date, period, value)。

**Step 3: Commit**
```bash
git commit -am "feat: implement PitConverter with strict PIT logic"
```

---

### Task 6: 实现 QlibIngestor 编排层

**Files:**
- Modify: `src/pipelines/data_ingest/qlib_converter.py`

**Step 1: 封装 dump_bin/dump_pit 调用**
使用 `subprocess` 调用 Qlib 的原生工具脚本完成最后的二进制入库。

---

### Task 7: 实现 run_pipeline.py CLI 与注册表

**Files:**
- Create: `scripts/run_pipeline.py`
- Modify: `src/pipelines/__init__.py`

**Step 1: 在 __init__.py 中定义 PIPELINE_REGISTRY**
**Step 2: 实现 run_pipeline.py 中的配置加载与 Pipeline 实例化**

---

### Task 8: 整体集成测试

**Files:**
- Create: `tests/pipelines/test_integration.py`

**Step 1: 模拟全流程 dry-run**
使用 mock 数据运行 `CSI1000QlibPipeline`。

---
