# Model Pipeline 设计文档

**日期**: 2026-04-25
**状态**: Draft → Pending Review
**作者**: Claude + Developer

---

## 1. 概述

在现有因子管线基础上，新增可插拔的模型训练与回测 Pipeline。采用模板模式设计，支持通过配置参数选择不同模型和标签周期，输出 Markdown 综合报告和 Alphalens Tear Sheet PDF。

### 目标

- 对 111 个因子 + 4 种标签周期训练 4 种模型
- 对比 16 组 (模型 × 周期) 的预测能力
- 输出可解释的因子重要性和 Alphalens 分析

### 非目标

- 实时交易执行
- Walk-forward 滚动训练 (留给后续迭代)
- 深度学习模型

---

## 2. 架构

### 2.1 Pipeline 结构

`ModelPipeline` 继承 `DataPipeline` 模板基类，定义自己的 `STAGE_METHOD_MAP`:

```
STAGE_METHOD_MAP = {
    "load": "load_data",        # 加载 factor pool + labels
    "train": "train_models",    # 训练指定模型 × 标签周期
    "predict": "run_predict",   # 在验证/回测期生成信号
    "backtest": "run_backtest", # 计算组合收益
    "report": "generate_report" # MD + PDF 报告
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
├── __init__.py              # 注册导出
├── model_pipeline.py         # ModelPipeline 主类 (模板模式)
├── base_model.py             # BaseModel 抽象基类
├── lasso.py                  # Lasso 实现
├── lgbm_regressor.py         # LGBMRegressor 实现
├── lgbm_ranker.py            # LGBMRanker (LambdaRank) 实现
├── lgbm_classifier.py        # LGBMClassifier (Top/Bottom) 实现
└── evaluator.py              # IC / Rank IC / 因子重要性计算
data/model_results/
├── model_report.md           # Markdown 综合报告
├── alphalens/
│   ├── tear_sheet.pdf        # Alphalens 综合图 PDF
│   ├── factor_data.csv       # 清洗后的因子数据
│   └── quantile_returns.csv  # 分组收益
└── models/                   # 持久化模型 (可选)
```

---

## 3. 数据切分策略

### 3.1 时间区间

| 分区 | 时间段 | 用途 |
|------|--------|------|
| 训练期 | 2020-01-01 ~ 2023-12-31 | 模型训练 |
| 验证期 | 2024-01-01 ~ 2024-06-30 | 超参选择/模型对比 |
| 回测期 | 2024-07-01 ~ 最新 | 最终策略评估 |

### 3.2 标签

4 个周期，已在 `AlphaFactorPipeline` 中计算:

| 标签名 | 含义 |
|--------|------|
| `label_1d` | 次日收益率 |
| `label_5d` | 5日收益率 (默认主标签) |
| `label_10d` | 10日收益率 |
| `label_20d` | 20日收益率 |

所有标签均为 forward return: `future_close / current_close - 1`

### 3.3 Label Winsorize

在训练前对标签做 3σ 截断 (winsorize)，消除异常值影响:

```python
def winsorize_label(y: pd.Series, sigma: float = 3.0) -> pd.Series:
    mean, std = y.mean(), y.std()
    upper, lower = mean + sigma * std, mean - sigma * std
    return y.clip(lower=lower, upper=upper)
```

---

## 4. 模型注册表

所有模型继承 `BaseModel` 抽象基类，统一接口:

| 方法 | 说明 |
|------|------|
| `fit(X, y, groups)` | 训练模型 |
| `predict(X)` | 生成预测信号 (返回 pd.Series) |
| `feature_importance()` | 返回因子重要性排名 |

### 4.1 模型列表

| 模型名 | 类名 | 优化目标 | 标签类型 |
|--------|------|---------|---------|
| `lasso` | LassoModel | MSE + L1 惩罚 | 连续收益率 |
| `lgbm_regressor` | LGBMRegModel | MSE | 连续收益率 |
| `lgbm_ranker` | LGBMRankModel | LambdaRank (NDCG) | 分组排名 (qcut) |
| `lgbm_classifier` | LGBMClassModel | LogLoss | 二分类 (Top/Bottom) |

### 4.2 BaseModel 接口

```python
class BaseModel(ABC):
    name: str

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series, groups=None) -> None: ...

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> pd.Series: ...

    def feature_importance(self) -> pd.Series: ...
```

### 4.3 各模型实现要点

**LassoModel**: 使用 `sklearn.linear_model.Lasso`，标准化输入后训练，输出系数作为因子重要性。

**LGBMRegModel**: 使用 `lightgbm.LGBMRegressor` (loss='mse')，直接预测收益率数值。

**LGBMRankModel**: 使用 `lightgbm.LGBMRanker` (objective='lambdarank', metric='ndcg')，标签按日期分组 qcut 为 5 档，训练时传入 group 参数。

**LGBMClassModel**: 使用 `lightgbm.LGBMClassifier` (objective='binary')，按截面将收益率分 Top20% 和 Bottom20% 为 1/0，排除中间 60% 样本，输出预测概率。

### 4.4 模型工厂

```python
MODEL_REGISTRY = {
    "lasso": LassoModel,
    "lgbm_regressor": LGBMRegModel,
    "lgbm_ranker": LGBMRankModel,
    "lgbm_classifier": LGBMClassModel,
}

def get_model(name: str, params: dict = None) -> BaseModel:
    cls = MODEL_REGISTRY[name]
    return cls(**(params or {}))
```

---

## 5. 训练流程

### 5.1 多模型 × 多周期矩阵

对配置中 `model.names` 列表和 `model.target_labels` 做笛卡尔积:

```
for model_name in model.names:       # 4 个模型
  for label_name in model.labels:    # 4 个标签
    train(model, label)              # = 16 次训练
```

每次训练产生:
- 训练集评估指标 (IC, Rank IC, R²/准确率)
- 验证集评估指标
- 回测期预测信号
- 因子重要性排名

### 5.2 验证集用途

验证集不用于超参调优，仅用于:
1. 模型间横向对比 (选择最优模型 × 周期组合)
2. 计算验证集 IC/ICIR 作为样本外性能指标

最佳模型选择标准: 验证期 ICIR 绝对值最大。

### 5.3 数据存储

训练结果存入 `TrainingResult` dataclass:

```python
@dataclass
class TrainingResult:
    model_name: str
    label_name: str
    model: BaseModel                     # 训练好的模型
    train_metrics: dict                  # 训练集指标
    val_metrics: dict                    # 验证集指标
    predictions: pd.Series               # 回测期预测
    backtest_returns: pd.Series          # 组合日收益
    feature_importance: pd.Series        # 因子重要性
```

---

## 6. 回测

### 6.1 Topk 策略

使用简单的 TopK-Drop 策略:

- **TopK**: 每日选择预测值最高的 K 只股票等权持有
- **K 值**: 可配置，默认 50
- **换仓**: 每日调仓

> 注意: 此回测不包含手续费和滑点，仅用于模型信号对比。

### 6.2 收益计算

```python
# returns: 截面收益率矩阵 (datetime × instrument)
# signals: 模型预测信号 (datetime × instrument)
for each date:
    top_k_stocks = signals[date].nlargest(K).index
    daily_return = returns[date][top_k_stocks].mean()
```

---

## 7. 报告输出

### 7.1 Markdown 报告 (model_report.md)

1. **训练摘要表**: 模型 × 标签的 IC/ICIR/Rank IC 对比矩阵
2. **模型详情**: 每个模型的训练指标、验证指标、因子重要性 Top 20
3. **回测对比**: 年化收益、夏普比率、最大回撤、胜率、Calmar Ratio
4. **周期衰减分析**: 同一模型在 1d→5d→10d→20d 的 IC 衰减趋势
5. **Alphalens 摘要**: IC 均值、ICIR、单调性、分组收益

### 7.2 Alphalens Tear Sheet PDF

对最佳模型 (按验证期 ICIR 排序) 生成完整的 Alphalens Tear Sheet:

- 调用 `alphalens.create_full_tear_sheet(factor_data)`
- 通过 `matplotlib.use('pdf')` + `PdfPages` 导出为 PDF
- 文件路径: `data/model_results/alphalens/tear_sheet.pdf`

同时保存清洗后的 `factor_data` CSV 供后续分析。

---

## 8. 配置文件

```yaml
# configs/model_pipeline.yaml
pipeline:
  name: model
  stages:
    - load
    - train
    - predict
    - backtest
    - report

data:
  factor_pool: data/factor_pool_relaxed.parquet
  instruments: "csi1000"

model:
  names: ["lasso", "lgbm_regressor", "lgbm_ranker", "lgbm_classifier"]
  target_labels: ["label_1d", "label_5d", "label_10d", "label_20d"]
  primary_label: "label_5d"
  params:
    lasso:
      alpha: 0.01
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

time_split:
  train_start: "2020-01-01"
  train_end: "2023-12-31"
  val_start: "2024-01-01"
  val_end: "2024-06-30"
  test_start: "2024-07-01"
  test_end: null

backtest:
  topk: 50
  quantiles: 5

label:
  winsorize_sigma: 3.0

output:
  dir: data/model_results
  report: data/model_results/model_report.md
  alphalens: data/model_results/alphalens
```

---

## 9. 命令行入口

通过现有 `scripts/run_pipeline.py` 直接调用:

```bash
uv run python scripts/run_pipeline.py --config configs/model_pipeline.yaml
```

或独立脚本:

```bash
uv run python scripts/run_model_pipeline.py --config configs/model_pipeline.yaml
```

---

## 10. 依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| lightgbm | >=4.6.0 | 回归/排名/分类模型 |
| sklearn (scikit-learn) | — | Lasso 回归 |
| alphalens | gitee fork | 因子分析 + Tear Sheet |
| matplotlib | >=3.10.8 | PDF 导出 |
| pandas | >=3.0.2 | 数据处理 |
| numpy | — | 数值计算 |

已在 pyproject.toml 中可用 (alphalens, lightgbm)。需要确认 sklearn 是否已安装。
