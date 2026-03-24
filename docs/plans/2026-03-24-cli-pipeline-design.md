# CLI Pipeline 工程化设计文档

## 概述

将现有 MVP 扩展为完整的 CLI 工具，支持训练、回测、评估的自动化流水线。

## 需求总结

| 维度 | 选择 |
|------|------|
| 优先方向 | 工程化与自动化 |
| 训练模式 | 单次训练 |
| 参数调优 | 不需要 |
| 输出形式 | CLI 命令行 |

## CLI 接口设计

### 命令结构

```bash
# 一键运行全流程
python main.py run

# 分步执行
python main.py train          # 训练模型
python main.py backtest       # 回测
python main.py evaluate       # 生成评估报告
```

### 参数设计

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--train-start` | 2020-01-01 | 训练集开始日期 |
| `--train-end` | 2022-12-31 | 训练集结束日期 |
| `--test-start` | 2023-01-01 | 测试集开始日期 |
| `--test-end` | 2024-12-31 | 测试集结束日期 |
| `--output-dir` | output/run_{timestamp} | 输出目录 |

### 输出目录结构

```
output/run_20260324_120000/
├── model.joblib          # 训练好的模型
├── predictions.parquet   # 预测信号
├── backtest_result.json  # 回测结果数据
└── report.md             # 评估报告
```

## 模块设计

### 目录结构

```
alpha_mq/
├── main.py              # CLI 入口（新增）
├── pipeline/
│   ├── __init__.py      # 模块初始化
│   ├── trainer.py       # 训练流程封装
│   ├── backtester.py    # 回测流程封装
│   └── evaluator.py     # 评估报告生成
└── output/              # 输出目录（新增）
```

### 模块职责

| 模块 | 职责 | 输入 | 输出 |
|------|------|------|------|
| `main.py` | CLI 参数解析、流程调度 | 命令行参数 | 执行结果 |
| `pipeline/trainer.py` | 数据加载、特征构建、模型训练 | 训练时间范围 | model.joblib |
| `pipeline/backtester.py` | qlib 回测执行 | 模型、测试数据 | backtest_result.json |
| `pipeline/evaluator.py` | 计算指标、生成报告 | 回测结果 | report.md |

## 核心流程

### train 子命令

1. 初始化 qlib（加载 csi1000 数据）
2. 构建 Alpha158 因子 + Triple Barrier 目标
3. 划分训练集（默认 2020-2022）
4. 训练 LightGBM 模型
5. 保存模型到 output/exp001/model.joblib

### backtest 子命令

1. 加载模型
2. 在测试集（默认 2023-2024）上生成预测信号
3. 使用 TopkDropoutStrategy 执行回测
4. 保存回测结果到 backtest_result.json

### evaluate 子命令

1. 计算因子 IC、ICIR
2. 计算分组收益率（五分组）
3. 计算策略业绩（年化收益、夏普、最大回撤）
4. 生成 Markdown 报告

### run 子命令

串联执行：train → backtest → evaluate

## 评估指标设计

### 因子预测能力

| 指标 | 说明 |
|------|------|
| Rank IC 均值 | 因子与收益的秩相关系数均值 |
| Rank ICIR | IC 的信息比率（IC均值/IC标准差） |
| IC > 0 占比 | IC 为正的比例 |

### 分组收益

| 组别 | 年化收益 | 最大回撤 |
|------|---------|---------|
| Q1 (因子最低) | - | - |
| Q2 | - | - |
| Q3 | - | - |
| Q4 | - | - |
| Q5 (因子最高) | - | - |
| 多空 (Q5-Q1) | - | - |

### 策略业绩

| 指标 | 策略 | 基准 |
|------|------|------|
| 年化收益 | - | - |
| 最大回撤 | - | - |
| 夏普比率 | - | - |
| 卡玛比率 | - | - |

## 默认参数

### 模型参数

复用现有 `ModelConfig.fast()`：

| 参数 | 值 |
|------|-----|
| `num_leaves` | 31 |
| `learning_rate` | 0.05 |
| `n_estimators` | 1000 |
| `early_stopping_rounds` | 50 |

### 策略参数

复用现有 `strategy.py`：

| 参数 | 值 |
|------|-----|
| `topk` | 50 |
| `n_drop` | 5 |
| 交易成本 | 买入 0.1%，卖出 0.1% |

## 实现计划

1. **创建 `pipeline/` 模块**：trainer.py、backtester.py、evaluator.py
2. **创建 CLI 入口**：main.py，实现参数解析和流程调度
3. **完善评估逻辑**：IC 计算、分组收益、业绩指标
4. **集成测试**：运行完整流程验证

## 技术依赖

现有依赖，无需新增：
- pyqlib
- lightgbm
- polars
- pandas
- click（或 argparse）