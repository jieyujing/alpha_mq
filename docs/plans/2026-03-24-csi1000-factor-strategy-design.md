# 中证1000 多因子选股系统设计文档

## 概述

基于中证1000指数股票池，构建多因子选股策略。数据使用gm（掘金）接口，因子框架使用qlib，模型使用LightGBM，目标使用Triple Barrier方法。

## 需求总结

| 维度 | 选择 |
|------|------|
| 策略类型 | 多因子选股 |
| 因子来源 | qlib Alpha158 + gm 因子库 |
| 模型 | 纯树模型 (LightGBM) |
| 数据范围 | 最小可行方案 (中证1000成分股 + 日频行情) |
| 目标 | Triple Barrier 目标 |
| 回测 | qlib 回测 |

## 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                        alpha-mq 架构                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   gm 数据层   │───▶│  qlib 数据层  │───▶│   因子计算    │      │
│  │  (行情/成分股) │    │  (本地文件)   │    │  (Alpha158)  │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                   │              │
│                                                   ▼              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   qlib 回测   │◀───│   策略评估    │◀───│  LightGBM    │      │
│  │  (信号/业绩)  │    │  (IC/分组)   │    │   模型训练    │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**核心模块**：
- `data/` - 数据层：gm → qlib 格式转换
- `factor/` - 因子层：Alpha158 + 自定义因子
- `model/` - 模型层：LightGBM 训练 + Triple Barrier 目标
- `backtest/` - 回测层：qlib 内置回测引擎

**数据流**：
```
gm.get_fundamentals() → parquet 文件 → qlib.init() → Dataset → Trainer → backtest
```

## 数据层设计

### 目录结构

```
data/
├── __init__.py
├── download.py       # gm 数据下载脚本
├── converter.py      # gm → qlib 格式转换
└── scripts/
    └── build_qlib_data.py  # 构建 qlib 数据的入口脚本
```

### 数据内容

| 数据类型 | 字段 | 来源 |
|---------|------|------|
| 日K线 | open, high, low, close, volume, amount | gm |
| 成分股 | 中证1000 成分股列表（日频） | gm |
| 指数 | 中证1000 指数收盘价 | gm |

### qlib 数据格式

```
~/.qlib/qlib_data/csi1000/
├── calendars/
│   └── day.txt          # 交易日历
├── instruments/
│   └── csi1000.txt      # 股票池（含起止日期）
├── features/
│   ├── close.bin        # 收盘价
│   ├── open.bin         # 开盘价
│   ├── high.bin         # 最高价
│   ├── low.bin          # 最低价
│   ├── volume.bin       # 成交量
│   └── amount.bin       # 成交额
└── bench/
    └── csi1000_index.bin # 基准指数
```

### 下载脚本接口

```python
# data/download.py
def download_daily_kline(start_date: str, end_date: str) -> pl.DataFrame:
    """从 gm 下载中证1000 成分股日K线"""

def download_constituents(start_date: str, end_date: str) -> pl.DataFrame:
    """下载中证1000 成分股列表（历史）"""
```

## 因子层设计

### 目录结构

```
factor/
├── __init__.py
├── alpha158.py        # qlib Alpha158 配置
├── custom.py          # 自定义因子（可选扩展）
└── target.py          # 目标构建（复用 path_target.py）
```

### 因子配置

```python
# factor/alpha158.py
from qlib.contrib.data.handler import Alpha158

class Alpha158_CSI1000(Alpha158):
    """中证1000 适配的 Alpha158 因子集"""

    def __init__(self, **kwargs):
        super().__init__(
            start_time="2020-01-01",
            end_time="2024-12-31",
            fit_start_time="2020-01-01",
            fit_end_time="2022-12-31",  # 训练期
            instruments="csi1000",       # 股票池
            infer_processors=[...],      # 推理时处理器
            learn_processors=[...],      # 训练时处理器
            **kwargs
        )
```

### 目标构建

复用现有的 `path_target.py`，基于 Triple Barrier + MAE 惩罚构建路径质量目标。

```python
# factor/target.py
from path_target import PathTargetBuilder, PathTargetConfig

def build_triple_barrier_target(close_df, market_close, beta_df):
    """构建 Triple Barrier 目标"""
    builder = PathTargetBuilder(PathTargetConfig(
        vol_window=20,
        k_upper=2.0,
        k_lower=2.0,
        max_holding=10,
        lamda=1.0,
        beta_alpha=0.5,
    ))
    return builder.build(close_df, market_close, beta_df)
```

### 因子列表 (Alpha158 核心因子)

| 类别 | 因子示例 | 说明 |
|------|---------|------|
| 价格动量 | Ref($close, -5)/$close - 1 | 5日收益率 |
| 波动率 | Std($close, 20) / Mean($close, 20) | 20日波动率 |
| 成交量 | $volume / Mean($volume, 20) | 成交量相对均值 |
| 技术指标 | MACD, RSI, KDJ | 经典技术因子 |

## 模型层设计

### 目录结构

```
model/
├── __init__.py
├── trainer.py         # 模型训练器
├── config.py          # 模型配置
└── predictor.py       # 预测器
```

### 模型配置

```python
# model/config.py
from dataclasses import dataclass

@dataclass
class ModelConfig:
    # LightGBM 参数
    boosting_type: str = "gbdt"
    num_leaves: int = 31
    max_depth: int = -1
    learning_rate: float = 0.05
    n_estimators: int = 1000
    objective: str = "regression"  # 或 "lambdarank"

    # 训练参数
    early_stopping_rounds: int = 50
    validation_fraction: float = 0.1
```

### 训练器

```python
# model/trainer.py
from qlib.contrib.model.gbdt import LGBModel

class FactorModel:
    def __init__(self, config: ModelConfig):
        self.config = config
        self.model = None

    def train(self, dataset):
        """训练模型"""
        self.model = LGBModel(
            loss="mse",  # 或 "ic" for IC loss
            colsample_bytree=0.8,
            subsample=0.8,
            **self.config.__dict__
        )
        self.model.fit(dataset)

    def predict(self, dataset):
        """生成预测信号"""
        return self.model.predict(dataset)
```

### 目标标签

- 使用 Triple Barrier 目标（复用 `path_target.py`）
- 标签范围：(0, 1)，表示截面排名百分位
- 模型目标：MSE（回归）或 LambdaRank（排序）

## 回测层设计

### 目录结构

```
backtest/
├── __init__.py
├── strategy.py        # 策略定义
├── executor.py        # 执行器配置
└── analyze.py         # 业绩分析
```

### 策略配置

```python
# backtest/strategy.py
from qlib.contrib.strategy.strategy import TopkDropoutStrategy

strategy_config = {
    "topk": 50,            # 持仓前50只股票
    "n_drop": 5,           # 每次调仓剔除5只
    "signal": "<PREDICTION>",  # 使用模型预测信号
}
```

### 执行器配置

```python
# backtest/executor.py
from qlib.contrib.executor.simulator_executor import SimulatorExecutor

executor_config = {
    "time_per_step": "day",
    "generate_portfolio_metrics": True,
    "trade_cost": {
        "buy": 0.001,  # 买入成本0.1%
        "sell": 0.001, # 卖出成本0.1%
    },
}
```

### 业绩分析指标

| 指标 | 说明 |
|------|------|
| 累计收益 | 策略 vs 基准 |
| 年化收益 | 几何年化 |
| 最大回撤 | 从高点到低点最大跌幅 |
| 夏普比率 | 风险调整收益 |
| IC均值 | 因子预测能力 |
| ICIR | IC的稳定性 |

### 回测入口

```python
# main.py
def run_backtest():
    # 1. 初始化 qlib
    qlib.init(provider_uri="~/.qlib/qlib_data/csi1000")

    # 2. 训练模型
    model = FactorModel(config)
    model.train(dataset)

    # 3. 回测
    portfolio_metric = backtest(
        executor=executor_config,
        strategy=strategy_config,
        model=model,
    )

    # 4. 分析
    analyze(portfolio_metric)
```

## 实现优先级

1. **P0 - 数据层**：gm 数据下载 + qlib 格式转换
2. **P1 - 因子层**：Alpha158 配置 + 目标构建
3. **P2 - 模型层**：LightGBM 训练器
4. **P3 - 回测层**：qlib 回测 + 业绩分析

## 技术依赖

```
pyqlib
gm (掘金 SDK)
lightgbm
polars
pandas
numpy
```