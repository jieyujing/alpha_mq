# Alpha158 因子池 Pipeline 设计文档

**日期:** 2026-04-23  
**状态:** 待实现

---

## 1. 背景与目标

### 现状

- 已有 `CSI1000QlibPipeline` 完成 GM 数据 → Qlib CSV 的转换（`data/qlib_output/ohlcv/`）
- 已有 `filter.txt` 实现完整的因子过滤责任链
- 已有 `configs/alpha158_training_design.md` 描述训练配置

### 目标

构建独立的 `AlphaFactorPipeline`，串联以下流程：

1. **Qlib binary 入库** — `dump_bin` 将 CSV → 二进制格式
2. **Alpha158 因子计算** — 使用 Qlib 内置 handler 加载
3. **多周期 return 标签** — 1D/5D/10D/20D，以 5D return 为主 label
4. **责任链过滤** — 复用 filter.txt，阈值通过 YAML 配置
5. **因子池输出** — YAML 配置 + Parquet 数据

### 关键决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Pipeline 归属 | 独立新类 `AlphaFactorPipeline` | 与 ingest 解耦，便于因子实验迭代 |
| 基类 | 继承 `DataPipeline` (Template Method) | 复用现有架构模式 |
| Alpha158 计算 | Qlib 内置 `Alpha158` handler | 与 Qlib 生态一致，免维护公式 |
| 主 label | 5D return | 中期预测，噪声低于 1D |
| 过滤阈值 | YAML 配置驱动 | 方便调参实验 |

---

## 2. 数据流

```
ingest_bin
  └─ QlibIngestor.dump_bin() 
     输入: data/qlib_output/ohlcv/*.csv
     输出: data/qlib_bin/

factor_compute
  └─ qlib.init(provider_uri="data/qlib_bin/")
     Alpha158(instruments, date_range)
     输出: MultiIndex(date, instrument) × 158+ 因子列

label_compute
  └─ Qlib 表达式引擎或 pandas:
     label_5d: Ref($close, -5) / $close - 1   ← 主 label
     label_1d, label_10d, label_20d           ← 附加列

filter
  └─ FilterContext(X=factors, y=label_5d, meta=tradability)
     责任链 → 过滤后的 X, y

export
  └─ Parquet: data/factor_pool.parquet
       columns: [factors..., label_1d, label_5d, label_10d, label_20d]
     YAML: configs/factor_pool.yaml
       metadata + factor list + filter config + stats

report
  └─ FactorQualityReporter.generate()
     输出: data/quality/factor_report.md
     内容:
       1. 因子质量统计: IC/ICIR/单调性分布, 过滤链漏斗图, 按组对比
       2. Label 统计: 分布, 分位数, 因子-label 相关性热力图
```

---

## 3. 模块结构

```
src/
├── pipelines/
│   ├── factor/                          # 新增子包
│   │   ├── __init__.py
│   │   ├── alpha_pipeline.py            # AlphaFactorPipeline 类
│   │   ├── factor_loader.py             # Qlib Alpha158 加载逻辑
│   │   ├── label_builder.py             # 多周期 return label 计算
│   │   └── factor_report.py             # 因子质量报告生成
│   ├── data_quality/
│   │   ├── reporter.py                  # (已有) OHLCV/PIT 数据质量
│   │   └── checks.py                    # (已有)
│   └── data_ingest/
│       └── qlib_converter.py            # (已有) QlibIngestor 复用
│   └── base.py                          # (已有) DataPipeline 基类

configs/
└── alpha_factor.yaml                    # Pipeline 配置

scripts/
└── run_pipeline.py                      # (已有) 注册新 Pipeline
```

---

## 4. 配置 Schema

```yaml
pipeline:
  name: AlphaFactorPipeline
  stages:
    - ingest_bin
    - factor_compute
    - label_compute
    - filter
    - export

data:
  qlib_csv: data/qlib_output/ohlcv
  qlib_bin: data/qlib_bin
  instruments: "csi1000"
  start_date: "2020-01-01"
  end_date: null  # today

labels:
  primary: "label_5d"
  periods: [1, 5, 10, 20]

filter:
  drop_missing_label: {}
  drop_untradable:
    rule: "l2_tradable"  # 从 L2 数据构建 meta
  drop_high_missing:
    threshold: 0.3
  drop_high_inf:
    threshold: 0.01
  drop_low_variance:
    variance_threshold: 1.0e-8
    unique_ratio_threshold: 0.01
  leakage_audit:
    audit_fn: "auto_detect"  # 检测与 label 同构的特征
  factor_quality:
    min_abs_ic_mean: 0.005
    min_abs_icir: 0.1
    min_abs_monotonicity: 0.05
    max_sign_flip_ratio: 0.45

output:
  parquet: data/factor_pool.parquet
  yaml: configs/factor_pool.yaml
  report: data/quality/factor_report.md
```

---

## 5. 核心类设计

### 5.1 `AlphaFactorPipeline`

```python
class AlphaFactorPipeline(DataPipeline):
    """独立因子计算与过滤 Pipeline。
    
    Stages:
    - ingest_bin: 将 CSV 转为 Qlib binary
    - factor_compute: Alpha158 handler 计算因子
    - label_compute: 多周期 return 标签
    - filter: 责任链过滤
    - export: 输出 YAML + Parquet
    """
    VALID_STAGES = ["ingest_bin", "factor_compute", "label_compute", "filter", "export"]
    
    def ingest_bin(self):
        """调用 QlibIngestor.dump_bin()"""
    
    def factor_compute(self):
        """qlib.init() → Alpha158 → DataFrame"""
    
    def label_compute(self):
        """基于 close 计算 1/5/10/20D return"""
    
    def run_filter(self):
        """构建 FilterContext → 执行责任链"""
    
    def export(self):
        """保存 Parquet + YAML"""
```

### 5.2 `FactorLoader`

```python
class FactorLoader:
    """加载 Qlib Alpha158 因子。"""
    
    def load_alpha158(
        self,
        instruments: str,
        start: str,
        end: str,
        extra_fields: list[str] = None,
    ) -> pd.DataFrame:
        """
        qlib.init() → Alpha158 handler → to_dataframe()
        
        返回 MultiIndex(date, instrument) × (158 + len(extra_fields)) DataFrame。
        extra_fields 从 Qlib 数据中加载非 Alpha158 特征（估值、市值等）。
        """
```

### 5.3 `LabelBuilder`

```python
class LabelBuilder:
    """构建多周期收益率标签。"""
    
    def compute_labels(
        self,
        data: pd.DataFrame,  # 含 close 列
        periods: list[int] = [1, 5, 10, 20],
    ) -> dict[str, pd.Series]:
        """
        对每个 period N:
            label_Nd = Ref(close, -N) / close - 1
        
        返回 {"label_1d": Series, "label_5d": Series, ...}
        """
```

### 5.5 `FactorQualityReporter`

```python
class FactorQualityReporter:
    """生成因子质量报告（Markdown 格式）。
    
    报告内容:
    1. 因子质量统计:
       - IC/ICIR/单调性 分布 (均值/中位数/P25/P75)
       - 过滤链漏斗图 (每步保留率)
       - 按组对比 (Alpha158 vs extra_features)
    
    2. Label 统计:
       - label 分布 (均值/方差/分位数)
       - 因子-label 相关性热力图 (top 20)
       - 按 label 周期对比 IC
    """
    
    def __init__(self, output_path: str):
        self.output_path = Path(output_path)
    
    def generate(
        self,
        X_before: pd.DataFrame,       # 过滤前因子
        X_after: pd.DataFrame,        # 过滤后因子
        y: pd.Series,                 # 主 label
        filter_artifacts: dict,       # 责任链中间统计
        filter_logs: list[str],       # 责任链日志
        all_labels: dict[str, pd.Series],  # 所有 label
    ) -> Path:
        """生成报告并保存。"""
```

### 5.6 Filter 责任链集成

复用 `filter.txt` 中的类，通过 YAML 配置构建责任链：

```python
def build_chain_from_config(config: dict, ctx: FilterContext) -> FilterContext:
    """从 YAML 配置构建责任链并执行。"""
    steps = []
    
    # Step 1: DropMissingLabel
    steps.append(DropMissingLabelStep())
    
    # Step 2: DropUntradable (需要 meta)
    if "drop_untradable" in config:
        steps.append(DropUntradableSampleStep(tradable_rule=build_tradable_rule(config)))
    
    # Step 3-7: 按配置依次添加...
    
    # 链接
    head = steps[0]
    for step in steps[1:]:
        head.set_next(step)
        head = step
    
    return steps[0].handle(ctx)
```

---

## 6. 实现任务顺序

| # | 任务 | 新增文件 | 依赖 |
|---|------|----------|------|
| 1 | `src/pipelines/factor/` 包骨架 | `__init__.py` | 无 |
| 2 | `FactorLoader` 实现 | `factor_loader.py` | 1 |
| 3 | `LabelBuilder` 实现 | `label_builder.py` | 1 |
| 4 | `AlphaFactorPipeline` 骨架 | `alpha_pipeline.py` | 2, 3 |
| 5 | filter.txt 责任链配置化集成 | `alpha_pipeline.py` 或独立模块 | 1 |
| 6 | `FactorQualityReporter` 实现 | `factor_report.py` | 1 |
| 7 | `configs/alpha_factor.yaml` | 配置文件 | 4 |
| 8 | `scripts/run_pipeline.py` 注册 | 修改已有文件 | 7 |
| 9 | 集成测试（dry-run） | `tests/pipelines/` | 8 |

---

## 7. 关键约束

1. **主 label 为 5D return** — filter 阶段使用 label_5d
2. **过滤阈值完全配置化** — 所有阈值从 YAML 读取
3. **复用 filter.txt 责任链** — 不复制代码，import 复用
4. **复用 QlibIngestor** — 从已有 `qlib_converter.py` import
5. **输出三格式** — Parquet（数据）+ YAML（元信息）+ Markdown 质量报告
6. **pyqlib 已在依赖中** — 无需额外安装
7. **质量报告内容** — 包含因子质量统计（IC/ICIR/单调性分布、过滤漏斗、分组对比）和 label 统计（分布、分位数、因子-label 相关性）
