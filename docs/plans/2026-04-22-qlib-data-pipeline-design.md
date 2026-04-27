# GM → Qlib 数据接入管道设计文档

**日期:** 2026-04-22  
**状态:** 已审批，待实现

---

## 1. 背景与目标

### 现状

项目已有分层 ETL 管道（L0-L3），以及基于 Strategy + Decorator + Template Method 的 `CSI1000Workflow`，负责从掘金 (GM) API 下载中证1000数据并存为 Parquet 文件。

### 目标

在现有 L0-L3 管道基础上，增加一条**面向 Qlib 的接入支线**，实现：

1. **可配置**：通过单一 YAML 文件驱动整个 pipeline（下载 → 验证 → 清洗 → 入库）
2. **可拆分执行**：通过 `--stages` 参数单独执行任意 stage
3. **严格 PIT**：财务数据使用 `pub_date` 作为时点日期，杜绝前瞻偏差
4. **不破坏现有流程**：L1-L3 脚本的逻辑迁移进 Pipeline 类，原文件保留向后兼容入口

---

## 2. 核心设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Qlib 入库方式 | 桥接模式（CSV 中间层 + `dump_bin/dump_pit`） | 与 Qlib 原生工具链兼容，排错简单 |
| 数据频率 | 日频 | 符合当前研究场景 |
| 股票池 | 中证1000（SHSE.000852） | 已有 `CSI1000Workflow` 支撑 |
| 财务 PIT 时效 | 严格模式（`pub_date` 作为 date） | 防止前瞻偏差，保证回测真实性 |
| Pipeline 设计 | Template Method + YAML Config | 骨架固定、步骤可替换、配置驱动 |
| Clean 阶段 | 迁移进 Pipeline 类（非 subprocess） | 更内聚，便于错误传播和状态共享 |

---

## 3. 架构总览

### 数据流

```
GM API (CSI1000Workflow)
    ↓
[stage: download]
data/exports/
├── history_1d/*.parquet
├── adj_factor/*.parquet      ─→ OhlcvConverter   → data/qlib_csv/ohlcv/   → dump_bin.py
├── valuation/*.parquet       ─┐
├── basic/*.parquet            ├→ FeatureConverter → data/qlib_csv/features/ → dump_bin.py
├── mktvalue/*.parquet        ─┘
├── fundamentals_balance/      ─┐
├── fundamentals_income/        ├→ PitConverter    → data/qlib_csv/pit/{field}/ → dump_pit.py
├── fundamentals_cashflow/     ─┘
├── static/instruments.csv    ─→ InstrumentBuilder → qlib_data/instruments/csi1000.txt
└── calendar/trade_dates.csv  ─→ CalendarBuilder   → qlib_data/calendars/day.txt
    ↓
[stage: validate]
data/validation_reports/YYYY-MM-DD.md

    ↓
[stage: clean]
data/backend/
├── l1_basic.parquet      (复权价、合并)
├── l2_status.parquet     (可交易性、ST、涨跌停)
└── l3_universe.parquet   (选股域过滤)

    ↓
[stage: ingest]
~/.qlib/qlib_data/cn_stock/
├── calendars/day.txt
├── instruments/csi1000.txt
├── features/{symbol}/{field}.bin    (OHLCV + 估值)
└── financial/{symbol}/{field}.pkl   (PIT 财务数据)
```

### 执行入口

```bash
# 完整 pipeline
uv run python scripts/run_pipeline.py --config configs/pipelines/csi1000_qlib.yaml

# 只执行部分 stage
uv run python scripts/run_pipeline.py \
  --config configs/pipelines/csi1000_qlib.yaml \
  --stages validate ingest
```

---

## 4. 模块结构

```
src/
├── etf_portfolio/              # (已有) 保留现有代码，不动
│   ├── data_source.py          # GMDataSource, RateLimiter
│   ├── decorators.py           # with_rate_limit, with_retry
│   ├── workflow.py             # DownloadWorkflow, CSI1000Workflow
│   └── ...
│
├── core/                       # (新增) 从 etf_portfolio 提取的通用基础设施
│   ├── __init__.py
│   ├── data_source.py          # DataSource Protocol, RateLimiter（长期迁移目标）
│   ├── decorators.py           # with_rate_limit, with_retry（长期迁移目标）
│   └── symbol.py               # SymbolAdapter（GM ↔ Qlib 转换）
│
└── pipelines/                  # (新增) 所有 pipeline 相关代码
    ├── __init__.py
    ├── base.py                 # DataPipeline 抽象基类
    ├── validator.py            # DataValidator
    ├── clean_functions.py      # L1/L2/L3 纯函数（从独立脚本迁移）
    │
    ├── data_ingest/            # 子包：数据接入类 pipeline
    │   ├── __init__.py
    │   ├── csi1000_qlib.py     # CSI1000QlibPipeline
    │   └── qlib_converter.py   # OhlcvConverter, FeatureConverter,
    │                           # PitConverter, QlibIngestor
    │
    ├── factor/                 # 子包（占位）：因子计算 pipeline
    │   └── __init__.py
    │
    └── ml/                     # 子包（占位）：模型训练 pipeline
        └── __init__.py

scripts/
├── download_gm.py          # (已有，保留，向后兼容)
├── clean_basic_l1.py       # (已有，保留，向后兼容，逻辑迁移进 pipeline)
├── tradability_l2.py       # (已有，保留，向后兼容)
├── universe_l3.py          # (已有，保留，向后兼容)
└── run_pipeline.py         # (新增) 核心入口：加载 YAML，映射 Pipeline 类并运行

configs/pipelines/
├── csi1000_qlib.yaml       # (新增) 数据接入 pipeline 配置
└── ...                     # 未来：factor_alpha158.yaml, ml_lgbm.yaml
```

---

## 5. 配置文件 Schema

```yaml
# configs/pipelines/csi1000_qlib.yaml
pipeline:
  name: CSI1000QlibPipeline

  stock_pool:
    index_code: "SHSE.000852"

  date_range:
    start: "2017-01-01"
    end: "2024-12-31"

  stages:
    - download
    - validate
    - clean
    - ingest

  download:
    categories:
      - history_1d
      - valuation
      - basic
      - mktvalue
      - adj_factor
      - fundamentals_balance
      - fundamentals_income
      - fundamentals_cashflow
    output_dir: "data/exports"
    format: "parquet"
    rate_limit: 950

  validate:
    checks:
      - missing_dates
      - null_ratio
      - price_sanity
      - pit_coverage
    null_ratio_threshold: 0.05
    report_dir: "data/validation_reports"
    fail_on_error: false

  clean:
    exports_dir: "data/exports"
    backend_dir: "data/backend"
    l1:
      adj_prices: true
    l2:
      st_detection: true
      limit_detection: true
    l3:
      min_listed_days: 60
      min_amount_ma20: 10_000_000

  ingest:
    qlib_dir: "~/.qlib/qlib_data/cn_stock"
    market: "cn_stock"
    intermediate_dir: "data/qlib_csv"
    pit_strict: true
    cleanup_intermediate: false
    features:
      ohlcv:
        enabled: true
        fields: [open, high, low, close, volume, amount, factor]
      valuation:
        enabled: true
        fields: [pe_ttm, pb_mrq, ps_ttm, pcf_ttm_oper]
      basic:
        enabled: true
        fields: [turnrate, tot_mv, a_mv, is_st, is_suspended]
      fundamentals:
        enabled: true
        categories: [balance, income, cashflow]
```

---

## 6. 核心类设计

### 6.1 `DataPipeline`（抽象基类）

```python
# src/pipelines/base.py
from abc import ABC, abstractmethod

class DataPipeline(ABC):
    """
    Template Method 模式 - 数据管道骨架。
    
    固定骨架（不可覆盖）: run()
    可扩展步骤（子类实现）: download, validate, clean, ingest_to_qlib
    可选钩子（子类可选）: setup, teardown
    """
    
    VALID_STAGES = ["download", "validate", "clean", "ingest"]
    
    def __init__(self, config: dict):
        self.config = config
        self.stages = config["pipeline"]["stages"]
        self._validate_stages()
    
    def run(self) -> None:
        """骨架方法 - 不可覆盖"""
        self.setup()
        try:
            if "download" in self.stages:
                self.download()
            if "validate" in self.stages:
                errors = self.validate()
                fail_on_error = self.config["pipeline"].get("validate", {}).get("fail_on_error", False)
                if errors and fail_on_error:
                    raise RuntimeError(f"Validation failed with {len(errors)} errors")
            if "clean" in self.stages:
                self.clean()
            if "ingest" in self.stages:
                self.ingest_to_qlib()
        finally:
            self.teardown()
    
    def setup(self) -> None:
        """初始化钩子 - 可选覆盖"""
        pass
    
    def teardown(self) -> None:
        """清理钩子 - 可选覆盖"""
        pass
    
    @abstractmethod
    def download(self) -> None: ...
    
    @abstractmethod
    def validate(self) -> list[str]:
        """返回错误消息列表，空列表表示通过"""
        ...
    
    @abstractmethod
    def clean(self) -> None: ...
    
    @abstractmethod
    def ingest_to_qlib(self) -> None: ...
    
    def _validate_stages(self):
        invalid = set(self.stages) - set(self.VALID_STAGES)
        if invalid:
            raise ValueError(f"Unknown stages: {invalid}. Valid: {self.VALID_STAGES}")
```

### 6.2 `CSI1000QlibPipeline`

```python
# src/pipelines/data_ingest/csi1000_qlib.py
from pipelines.base import DataPipeline
from pipelines.validator import DataValidator
from pipelines.data_ingest.qlib_converter import QlibIngestor
from pipelines.clean_functions import process_l1, process_l2, process_l3

class CSI1000QlibPipeline(DataPipeline):
    
    def setup(self):
        # 初始化 GMDataSource, RateLimiter, 设置 token, 创建目录
        ...
    
    def download(self):
        # 委托给 CSI1000Workflow
        workflow = CSI1000Workflow(token=..., index_code=self.index_code)
        workflow.run(self.start_date, self.end_date)
    
    def validate(self) -> list[str]:
        validator = DataValidator(self.config["pipeline"]["validate"])
        return validator.run(exports_dir=self.exports_dir)
    
    def clean(self) -> None:
        cfg = self.config["pipeline"]["clean"]
        process_l1(exports_dir=cfg["exports_dir"], backend_dir=cfg["backend_dir"])
        process_l2(backend_dir=cfg["backend_dir"], exports_dir=cfg["exports_dir"])
        process_l3(backend_dir=cfg["backend_dir"], exports_dir=cfg["exports_dir"],
                   min_listed_days=cfg["l3"]["min_listed_days"],
                   min_amount_ma20=cfg["l3"]["min_amount_ma20"])
    
    def ingest_to_qlib(self) -> None:
        ingestor = QlibIngestor(self.config["pipeline"]["ingest"])
        ingestor.run(symbol_pool=self._get_symbol_pool())
```

### 6.3 `SymbolAdapter`

```python
class SymbolAdapter:
    """GM symbol ↔ Qlib symbol 双向转换"""
    
    _TO_QLIB = {"SHSE": "SH", "SZSE": "SZ"}
    _TO_GM   = {"SH": "SHSE", "SZ": "SZSE"}
    
    @staticmethod
    def to_qlib(gm_symbol: str) -> str:
        """SHSE.600000 → SH600000"""
        exchange, code = gm_symbol.split(".")
        return f"{SymbolAdapter._TO_QLIB.get(exchange, exchange)}{code}"
    
    @staticmethod
    def to_gm(qlib_symbol: str) -> str:
        """SH600000 → SHSE.600000"""
        prefix, code = qlib_symbol[:2], qlib_symbol[2:]
        return f"{SymbolAdapter._TO_GM.get(prefix, prefix)}.{code}"
```

### 6.4 `PitConverter`（严格 PIT）

```python
class PitConverter:
    """
    将 GM 财务报表 Parquet 转换为 Qlib PIT 格式 CSV。
    
    严格 PIT: 使用 pub_date（实际公告日）作为 Qlib date 字段。
    
    输出格式 (per symbol per field):
        date       | period   | value
        2023-04-28 | 20230331 | 0.152
    
    输出路径: {intermediate_dir}/pit/{field}/{qlib_symbol}.csv
    
    调用示例:
        converter = PitConverter(intermediate_dir="data/qlib_csv")
        converter.convert("balance", exports_dir="data/exports", symbol_pool=[...])
    """
    
    def convert(
        self,
        category: str,          # "balance" | "income" | "cashflow"
        exports_dir: str,
        symbol_pool: list[str]
    ) -> None:
        """
        按 symbol 读取财务 Parquet，按字段拆分输出 PIT CSV。
        字段列表从 Parquet 列名自动发现（排除 pub_date, rpt_date, symbol 系统列）。
        """
        ...
```

### 6.5 `DataValidator`

```python
class DataValidator:
    """
    数据完整性检查器。
    
    检查项:
    - missing_dates: 对照交易日历，检查每个 symbol 的日期缺口
    - null_ratio: 关键字段空值率 > threshold
    - price_sanity: high >= low, close > 0, volume >= 0
    - pit_coverage: 财务数据是否覆盖所有 symbol
    
    输出:
    - list[str]: 错误消息（空=通过）
    - Markdown 报告写入 report_dir
    """
    
    def run(self, exports_dir: str) -> list[str]: ...
```

---

## 7. PIT 格式与入库

### 文件格式

```
date,period,value
2023-04-28,20230331,0.152
2023-08-30,20230630,0.161
2024-04-25,20231231,0.178
```

### 字段映射

| GM 字段 | Qlib 字段 | 说明 |
|---------|-----------|------|
| `pub_date` | `date` | 公告发布日（实际可用时间，严格 PIT） |
| `rpt_date` | `period` | 报表会计期末（YYYYMMDD 整数） |
| `{metric}` | `value` | 财务指标数值 |

### 入库命令（由 QlibIngestor 自动生成并调用）

```bash
# OHLCV + 日频特征
python scripts/dump_bin.py dump_update \
  --csv_path data/qlib_csv/ohlcv \
  --qlib_dir ~/.qlib/qlib_data/cn_stock \
  --include_fields open,high,low,close,volume,amount,factor

# 财务 PIT（每个字段独立调用）
python scripts/dump_pit.py dump_update \
  --csv_path data/qlib_csv/pit/roe \
  --qlib_dir ~/.qlib/qlib_data/cn_stock
```

---

## 8. 实现任务顺序

| # | 任务 | 新增文件 | 依赖 |
|---|------|----------|------|
| 1 | `src/pipelines/` 包骨架（含空子包） | `src/pipelines/__init__.py` 等 | 无 |
| 2 | `DataPipeline` 抽象基类 + 单元测试 | `src/pipelines/base.py` | 1 |
| 3 | `SymbolAdapter` + 单元测试 | `src/core/symbol.py` | 无 |
| 4 | `OhlcvConverter` + `FeatureConverter` + 测试 | `src/pipelines/data_ingest/qlib_converter.py` | 3 |
| 5 | `PitConverter`（严格 PIT）+ 测试 | `src/pipelines/data_ingest/qlib_converter.py` | 3 |
| 6 | `QlibIngestor` 编排层（调用 dump_bin/dump_pit）| `src/pipelines/data_ingest/qlib_converter.py` | 4, 5 |
| 7 | `DataValidator` + 测试 | `src/pipelines/validator.py` | 无 |
| 8 | 迁移 L1/L2/L3 为纯函数 | `src/pipelines/clean_functions.py` | 无 |
| 9 | `CSI1000QlibPipeline` 具体实现 | `src/pipelines/data_ingest/csi1000_qlib.py` | 2, 6, 7, 8 |
| 10 | YAML 配置文件 + `run_pipeline.py` CLI | `configs/pipelines/`, `scripts/run_pipeline.py` | 9 |
| 11 | 集成测试（dry-run，mock GM API） | `tests/pipelines/` | 10 |

---

## 10. 配置驱动与执行逻辑

### 10.1 配置加载流程

`run_pipeline.py` 负责将 YAML 配置文件转化为具体的 Pipeline 实例。

1.  **参数解析**: 解析 `--config` (路径) 和 `--stages` (可选覆盖)。
2.  **YAML 加载**: 使用 `yaml.safe_load()` 读取配置。
3.  **Pipeline 工厂**: 根据 `pipeline.name` 字段查找对应的 Pipeline 类。
    *   方案 A (简单): 手动维护一个 `NAME_TO_CLASS` 映射。
    *   方案 B (灵活): 动态 import (例如 `pipelines.data_ingest.csi1000_qlib.CSI1000QlibPipeline`)。
4.  **初始化与执行**: 实例化 `Pipeline(config)` 并调用 `.run()`。

### 10.2 Pipeline 注册机制

为了保持解耦，建议在 `src/pipelines/__init__.py` 中统一暴露或注册 Pipeline 类：

```python
# src/pipelines/__init__.py
from .data_ingest.csi1000_qlib import CSI1000QlibPipeline

PIPELINE_REGISTRY = {
    "CSI1000QlibPipeline": CSI1000QlibPipeline,
}
```

### 10.3 CLI 入口实现伪代码

```python
# scripts/run_pipeline.py
import yaml
import argparse
from pipelines import PIPELINE_REGISTRY

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to YAML config")
    parser.add_argument("--stages", nargs="+", help="Override stages in config")
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = yaml.safe_load(f)

    # 覆盖 stages (如果提供了命令行参数)
    if args.stages:
        config["pipeline"]["stages"] = args.stages

    # 实例化并运行
    pipeline_cls = PIPELINE_REGISTRY[config["pipeline"]["name"]]
    pipeline = pipeline_cls(config)
    pipeline.run()

if __name__ == "__main__":
    main()
```

---

## 11. 关键约束

1. **配置即文档**：YAML 文件应包含运行该 pipeline 所需的所有超参数和路径，避免在代码中硬编码。
2. **不破坏现有流程**：`clean_basic_l1.py`, `tradability_l2.py`, `universe_l3.py` 的 `__main__` 入口保留可独立运行。
3. **增量优先**：日常更新使用 `dump_update`，全量初始化使用 `dump_all`，通过 config `mode: incremental|full` 控制。
4. **财务字段自动发现**：`PitConverter` 从 Parquet 列名自动扫描可用字段，无需手动维护字段列表。
5. **中间文件可选清理**：`cleanup_intermediate: true` 时 ingest 完成后删除 `data/qlib_csv/`。
6. **pyqlib 已在依赖中**：`pyqlib >= 0.9.7` 已在 `pyproject.toml`，无需额外安装。
