# Model Pipeline 设计文档

**日期**: 2026-04-25
**状态**: Review → Approved
**作者**: Claude + Developer

---

## 1. 概述

在现有因子管线基础上，新增可插拔的模型训练与回测 Pipeline。采用模板模式设计，支持通过配置参数选择不同模型和标签周期。**核心原则: 确保结果代表可交易的 alpha，而非数据泄漏的幻觉。**

### 目标

- 对因子池 + 4 种标签周期训练 4 种模型，对比 16 组 (模型 × 周期) 的预测能力
- 所有评估严格处理 forward label overlap、方向修正、成本扣除、基准对比
- 输出 Markdown 综合报告和 Alphalens Tear Sheet PDF (使用模型预测信号作为 factor)

### 非目标

- 实时交易执行
- Walk-forward 滚动训练 (Phase 2)
- 深度学习模型

---

## 2. 架构

### 2.1 Pipeline 结构

`ModelPipeline` 继承 `DataPipeline` 模板基类，扩展的 stage 职责更细:

```
STAGE_METHOD_MAP = {
    "load":      "load_data",               # 加载 factor pool
    "prepare":   "prepare_features_labels", # 缺失值/截面标准化/标签转换
    "split":     "make_time_splits",        # 带 purge 的时间切分
    "train":     "train_models",            # 训练模型 × 标签周期
    "predict":   "run_predict",             # 验证/回测期预测
    "orient":    "orient_signals",          # 根据验证集 IC 修正信号方向
    "backtest":  "run_backtest",            # 含成本/换手的 TopK 回测
    "alphalens": "generate_alphalens",      # 最佳模型信号 → Alphalens
    "report":    "generate_report"          # MD + PDF 报告
}
```

### 2.2 注册入口

在 `src/pipelines/__init__.py` 注册:

```python
from pipelines.model.model_pipeline import ModelPipeline
PIPELINE_REGISTRY["model"] = ModelPipeline
```

### 2.3 文件结构

```
src/pipelines/model/
├── __init__.py               # 注册导出
├── model_pipeline.py          # ModelPipeline 主类 (模板模式)
├── base_model.py              # BaseModel 抽象基类
├── linear_model.py            # ElasticNet / Ridge / Huber (替代 Lasso)
├── lgbm_regressor.py          # LGBMRegressor 实现
├── lgbm_ranker.py             # LGBMRanker (LambdaRank) 实现
├── lgbm_classifier.py         # LGBMClassifier (Top/Bottom) 实现
├── evaluator.py               # IC / Rank IC / 因子重要性计算
└── feature_prep.py            # 截面标准化 / winsorize / 缺失值处理
data/model_results/
├── model_report.md            # Markdown 综合报告
├── alphalens/
│   ├── tear_sheet.pdf         # 最佳模型预测信号 → Alphalens PDF
│   ├── factor_data.csv        # 清洗后的因子数据
│   └── quantile_returns.csv   # 分组收益
├── results.parquet            # 所有模型评估结果
└── models/                    # 持久化模型 (可选)
```

---

## 3. 特征与标签预处理

### 3.1 特征处理

所有特征在进入模型前按日期截面处理:

```python
# 配置
features:
  impute: "cross_section_median"    # 按日截面中位数填充缺失
  transform: "rank_pct"             # raw / zscore / rank_pct
  winsorize:
    enabled: true
    method: "quantile"
    lower: 0.01
    upper: 0.99
```

**`rank_pct` 变换** (推荐):
```python
def cross_section_rank_normalize(X: pd.DataFrame) -> pd.DataFrame:
    return X.groupby(level="datetime").transform(
        lambda s: s.rank(pct=True) * 2 - 1   # [-1, 1]
    )
```

### 3.2 标签 Winsorize

按日期截面分位数截断，不用全局均值方差:

```python
def winsorize_label_by_date_quantile(
    y: pd.Series, lower_q: float = 0.01, upper_q: float = 0.99,
) -> pd.Series:
    def _clip(s):
        return s.clip(s.quantile(lower_q), s.quantile(upper_q))
    return y.groupby(level="datetime").transform(_clip)
```

### 3.3 LGBMRanker 排名标签

按日期分组 qcut，处理重复值和最小样本:

```python
def make_rank_label_by_date(
    y: pd.Series, n_bins: int = 5, min_group_size: int = 30,
) -> pd.Series:
    def _rank_bin(s):
        s = s.dropna()
        if len(s) < min_group_size:
            return pd.Series(index=s.index, dtype=float)
        ranked = s.rank(method="first")
        return pd.qcut(ranked, q=n_bins, labels=False, duplicates="drop")
    return y.groupby(level="datetime", group_keys=False).apply(_rank_bin)
```

### 3.4 LGBMClassifier 二分类标签

Top/Bottom 分位，排除中间样本:

```python
def make_binary_label_by_date(
    y: pd.Series, top_q: float = 0.8, bottom_q: float = 0.2,
) -> tuple[pd.Series, pd.Series]:
    """返回 (binary_y, mask)"""
    def _classify(s):
        s = s.dropna()
        if len(s) < 30:
            return pd.Series(index=s.index, dtype=float), pd.Series(False, index=s.index)
        upper = s.quantile(top_q)
        lower = s.quantile(bottom_q)
        y_bin = pd.Series(0, index=s.index)
        y_bin[s >= upper] = 1
        y_bin[s <= lower] = 0
        mask = (y_bin == 1) | (y_bin == 0)
        return y_bin, mask
    return y.groupby(level="datetime", group_keys=False).apply(_classify)
```

---

## 4. 时间切分与 Purge

### 4.1 基础区间

| 分区 | 时间段 | 用途 |
|------|--------|------|
| 训练期 | 2020-01-01 ~ 2023-12-31 | 模型训练 |
| 验证期 | 2024-01-01 ~ 2024-06-30 | 模型对比/方向修正 |
| 回测期 | 2024-07-01 ~ 最新 | 最终策略评估 |

### 4.2 Forward Label Purge

每个标签周期在训练/验证/测试边界需要 purge，避免信息泄漏:

| 标签 | Horizon | Purge 天数 |
|------|---------|-----------|
| `label_1d` | 1 | 1 |
| `label_5d` | 5 | 5 |
| `label_10d` | 10 | 10 |
| `label_20d` | 20 | 20 |

对于 `label_20d`:
- 训练集结束 = `2023-12-31` − 20 个交易日 ≈ 2023-12-01
- 验证集结束 = `2024-06-30` − 20 个交易日 ≈ 2024-06-01

```python
PURGE_MAP = {
    "label_1d": 1,
    "label_5d": 5,
    "label_10d": 10,
    "label_20d": 20,
}

def make_time_splits(label_name: str, config: dict) -> dict:
    purge_days = PURGE_MAP.get(label_name, 1)
    train_end = config["train_end"] - timedelta(purge_days)
    val_end = config["val_end"] - timedelta(purge_days)
    return {
        "train": (config["train_start"], train_end),
        "val": (config["val_start"], val_end),
        "test": (config["test_start"], config["test_end"]),
    }
```

> 注意: 实际使用交易日而非日历日，通过 qlib calendar 获取交易日历计算。

### 4.3 静态切分声明

当前使用 static split，不代表滚动实盘表现。报告中须声明此限制。

---

## 5. 模型注册表

### 5.1 BaseModel 接口

```python
class BaseModel(ABC):
    name: str

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series, groups=None) -> None: ...

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> pd.Series: ...

    def feature_importance(self) -> pd.Series:
        raise NotImplementedError
```

### 5.2 模型列表

| 模型名 | 类名 | 优化目标 | 标签类型 | 说明 |
|--------|------|---------|---------|------|
| `elastic_net` | LinearModel | MSE + L1+L2 惩罚 | 连续收益率 | 基线，支持 ridge/lasso/enet/huber |
| `lgbm_regressor` | LGBMRegModel | MSE | 连续收益率 | 点预测 |
| `lgbm_ranker` | LGBMRankModel | LambdaRank (NDCG) | 分组排名 (qcut) | **主模型** |
| `lgbm_classifier` | LGBMClassModel | LogLoss | 二分类 (Top/Bottom) | 极端信号筛选 |

### 5.3 模型工厂

```python
MODEL_REGISTRY = {
    "elastic_net": LinearModel,
    "lgbm_regressor": LGBMRegModel,
    "lgbm_ranker": LGBMRankModel,
    "lgbm_classifier": LGBMClassModel,
}

def get_model(name: str, params: dict = None) -> BaseModel:
    cls = MODEL_REGISTRY[name]
    return cls(**(params or {}))
```

---

## 6. 训练流程

### 6.1 多模型 × 多周期矩阵

```
for model_name in model.names:
  for label_name in model.labels:
    splits = make_time_splits(label_name, config)  # 带 purge
    prepare(X, y, label_name)                      # 截面标准化 + winsorize
    train(model, label, splits)                    # 16 次训练
```

### 6.2 验证集用途

验证集仅用于:
1. 模型间横向对比 (选择最优模型 × 周期组合)
2. 计算验证集 IC/ICIR 作为样本外性能指标
3. **方向修正** (见 Section 7)

### 6.3 TrainingResult

```python
@dataclass
class TrainingResult:
    model_name: str
    label_name: str
    model: BaseModel
    train_metrics: dict                  # IC, ICIR, Rank IC, R²
    val_metrics: dict                    # IC, ICIR, Rank IC, R²
    test_metrics: dict                   # IC, ICIR, Rank IC, R²
    val_mean_ic: float                   # 验证集平均 IC (用于方向修正)
    train_predictions: pd.Series
    val_predictions: pd.Series
    test_predictions: pd.Series
    oriented_test_signal: pd.Series      # 方向修正后的测试信号
    backtest_returns: pd.Series          # TopK 日收益
    backtest_excess: pd.Series           # 超额收益 (vs benchmark)
    backtest_metrics: dict               # AnnRet, Sharpe, MaxDD, Turnover, CostAdjSharpe
    turnover: pd.Series                  # 日换手率
    feature_importance: pd.Series
    metadata: dict                       # 额外信息
```

---

## 7. 信号方向修正

### 7.1 问题

如果模型的验证集 IC 为负且绝对值很大，说明它学到了稳定的反向信号。直接使用 TopK 会导致反向持仓。

### 7.2 方向修正

```python
def orient_signal(val_mean_ic: float, predictions: pd.Series) -> tuple[pd.Series, int]:
    if val_mean_ic < 0:
        return -predictions, -1   # 反向
    return predictions, 1          # 正向

# 在 Pipeline 中
result.oriented_test_signal, result.oriented_direction = orient_signal(
    result.val_mean_ic, result.test_predictions
)
```

### 7.3 最佳模型选择

使用 **oriented_val_icir** (方向修正后的验证集 ICIR) 最大:

```python
oriented_val_icir = abs(val_icir)   # 方向已修正，保证为正
best_result = max(all_results, key=lambda r: r.oriented_val_icir)
```

报告须同时展示:
- 原始 IC / 原始 ICIR / 方向
- 方向修正后 ICIR
- 方向修正后回测结果

---

## 8. 回测

### 8.1 TopK 策略

- 每日选择 **方向修正后信号** 最高的 K 只股票等权持有
- K 值可配置，默认 50
- 每日调仓
- **信号滞后 1 天**: 今天信号 → 明天开仓

### 8.2 收益计算

```python
# returns: 截面收益率矩阵 (datetime × instrument)
# signals: 模型预测信号 (datetime × instrument)
# 信号 shift 1 天，模拟 T 日计算 → T+1 日成交
signals_shifted = signals.unstack().shift(1).stack()

for each date:
    top_k = signals_shifted[date].nlargest(K).index
    daily_return = returns[date][top_k].mean()
```

### 8.3 成本与换手

```python
backtest:
  transaction_cost_bps: 10    # 单边 10bps

# 换手率
turnover_t = abs(weights_t - weights_{t-1}).sum() / 2
cost_t = turnover_t * cost_bps / 10000
net_return_t = gross_return_t - cost_t
```

### 8.4 Benchmark 对比

至少提供:
- **等权全市场** (universe equal weight) 作为基准
- 超额收益: `excess = topk_return - benchmark_return`
- 报告中展示超额夏普

### 8.5 持有期与换仓对齐

统一每日换仓，但报告中明确这是 **daily rebalanced overlapping portfolio**。

### 8.6 TopK 稳定性

报告展示不同 K 值 (10/30/50/100) 下的年化收益，评估排序边界的稳健性。

---

## 9. Alphalens 接入

### 9.1 使用模型预测信号作为 factor

Alphalens 的 factor 是最佳模型的 **方向修正后预测信号**，不是原始因子:

```python
factor = best_model.oriented_test_signal   # MultiIndex (datetime, instrument)
prices = close_price_matrix                # datetime × instrument

factor_data = alphalens.utils.get_clean_factor_and_forward_returns(
    factor=factor,
    prices=prices,
    periods=(1, 5, 10, 20),
    quantiles=5,
)
```

这回答: 模型综合信号作为一个新因子，它的分组收益、IC、换手、衰减表现如何？

### 9.2 输出

- `tear_sheet.pdf` — `alphalens.create_full_tear_sheet(factor_data)`，通过 PdfPages 导出
- `factor_data.csv` — 清洗后的因子数据
- `quantile_returns.csv` — 分组收益

---

## 10. 报告输出

### 10.1 Markdown 报告 (model_report.md)

1. **训练摘要表**: 模型 × 标签的 IC/ICIR/Rank IC 对比矩阵
2. **模型 × 周期方向表**:

| Model | Label | Val IC | Direction | Oriented IC | Oriented ICIR |
|-------|-------|--------|-----------|-------------|---------------|

3. **OOS TopK Excess 表**:

| Model | Label | Ann Ret | Excess Ann Ret | Sharpe | Max DD | Turnover | Cost Adj Sharpe |
|-------|-------|---------|----------------|--------|--------|----------|-----------------|

4. **IC Decay 表**:

| Model | Label | IC@1D | IC@5D | IC@10D | IC@20D |
|-------|-------|-------|-------|--------|--------|

5. **TopK 稳定性表**:

| Model | Label | Top10 | Top30 | Top50 | Top100 |
|-------|-------|-------|-------|-------|--------|

6. **模型详情**: 每个模型的因子重要性 Top 20
7. **Alphalens 摘要**: 最佳模型信号的 IC、单调性、分组收益
8. **静态切分声明**: 当前结果不代表滚动实盘表现

### 10.2 PDF 输出

- Alphalens full tear sheet PDF
- 包含: Returns Analysis, Quantile Analysis, IC Analysis, Turnover Analysis

---

## 11. 配置文件

```yaml
# configs/model_pipeline.yaml
pipeline:
  name: model
  stages:
    - load
    - prepare
    - split
    - train
    - predict
    - orient
    - backtest
    - alphalens
    - report

data:
  factor_pool: data/factor_pool_relaxed.parquet
  instruments: "csi1000"
  datetime_col: "datetime"
  instrument_col: "instrument"

features:
  impute: "cross_section_median"
  transform: "rank_pct"      # raw / zscore / rank_pct
  winsorize:
    enabled: true
    method: "quantile"
    lower: 0.01
    upper: 0.99

label:
  winsorize:
    enabled: true
    method: "cross_section_quantile"
    lower: 0.01
    upper: 0.99
  rank_bins: 5
  ranker_min_group_size: 30
  classifier:
    top_quantile: 0.8
    bottom_quantile: 0.2

split:
  purge_by_label: true
  train_start: "2020-01-01"
  train_end: "2023-12-31"
  val_start: "2024-01-01"
  val_end: "2024-06-30"
  test_start: "2024-07-01"
  test_end: null

model:
  names: ["elastic_net", "lgbm_regressor", "lgbm_ranker", "lgbm_classifier"]
  target_labels: ["label_1d", "label_5d", "label_10d", "label_20d"]
  primary_label: "label_5d"
  params:
    elastic_net:
      alpha: 0.01
      l1_ratio: 0.2
    lgbm_regressor:
      num_leaves: 31
      learning_rate: 0.05
      n_estimators: 200
      min_child_samples: 50
      feature_fraction: 0.8
      bagging_fraction: 0.8
      bagging_freq: 5
      seed: 42
    lgbm_ranker:
      num_leaves: 31
      learning_rate: 0.05
      n_estimators: 200
      min_child_samples: 50
      seed: 42
    lgbm_classifier:
      num_leaves: 31
      learning_rate: 0.05
      n_estimators: 200
      min_child_samples: 50
      seed: 42

selection:
  metric: "oriented_val_icir"

backtest:
  topk: 50
  shift_signal_days: 1
  transaction_cost_bps: 10
  benchmark: "universe_equal_weight"
  quantiles: 5
  topk_range: [10, 30, 50, 100]

output:
  dir: data/model_results
  report: data/model_results/model_report.md
  alphalens: data/model_results/alphalens
```

---

## 12. 命令行入口

```bash
uv run python scripts/run_pipeline.py --config configs/model_pipeline.yaml
```

---

## 13. 依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| lightgbm | >=4.6.0 | 回归/排名/分类模型 |
| scikit-learn | — | ElasticNet / Ridge / Huber |
| alphalens | gitee fork | 因子分析 + Tear Sheet |
| matplotlib | >=3.10.8 | PDF 导出 |
| pandas | >=3.0.2 | 数据处理 |
| numpy | — | 数值计算 |

已在 pyproject.toml 中可用 (alphalens, lightgbm)。需要确认 scikit-learn 是否已安装 (lightgbm 通常自带依赖)。

---

## 14. Phase 2 展望

- Purged Walk-forward 滚动训练
- Ensemble 模型 (rank average)
- 行业中性化
- 真实交易成本建模 (滑点、冲击成本)
