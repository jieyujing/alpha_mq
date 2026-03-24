# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

中证1000多因子选股系统，使用 qlib 因子框架 + LightGBM 模型 + Triple Barrier 目标构建。

## 常用命令

```bash
# 安装依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 运行单个测试文件
pytest tests/test_trainer.py

# 运行演示模式（使用模拟数据）
python main.py --demo

# 构建 qlib 数据集（需要 gm SDK）
python data/scripts/build_qlib_data.py --start-date 2020-01-01 --end-date 2024-12-31
```

## 架构

```
gm数据 → qlib格式 → Alpha158因子 → LightGBM训练 → 回测评估
   ↓          ↓           ↓              ↓           ↓
data/     data/      factor/       model/     backtest/
```

**数据流**：`gm.get_fundamentals()` → parquet → qlib.init() → Dataset → Trainer → backtest

## 核心模块

### data/ - 数据层
- `download.py`: 从 gm SDK 下载中证1000成分股日K线
- `converter.py`: 转换为 qlib 二进制格式
- `scripts/build_qlib_data.py`: 数据构建入口脚本

### factor/ - 因子层
- `alpha158.py`: qlib Alpha158 因子集适配中证1000股票池
- `target.py`: Triple Barrier 目标构建

### model/ - 模型层
- `config.py`: LightGBM 模型配置（`ModelConfig.fast()` / `.production()`）
- `trainer.py`: FactorModel 训练器，支持 early stopping 和模型保存

### backtest/ - 回测层
- `strategy.py`: TopkDropoutStrategy 策略配置
- `executor.py`: 交易执行器配置
- `analyze.py`: 组合业绩分析

## 关键文件

- `path_target.py`: 基于 AFML Triple Barrier Method 的路径质量 Target 构建，包含 soft beta-neutral 和 MAE 惩罚
- `factor_framework.py`: 因果因子验证框架，用于机制推论检验和贝叶斯证据累积

## 数据格式

qlib 数据目录结构：
```
data/qlib_data/csi1000/
├── calendars/day.txt       # 交易日历
├── instruments/csi1000.txt # 股票池
├── features/*.bin          # OHLCV 数据
└── bench/csi1000_index.bin # 基准指数
```

## 依赖

- **pyqlib**: 因子框架和回测引擎
- **gm (掘金 SDK)**: 行情数据源，需要单独配置账户
- **lightgbm**: 梯度提升模型
- **polars**: 高性能数据处理

## qlib 集成

### 核心组件

- `factor/handler.py`: CSI1000Handler，继承 qlib Alpha158
- `factor/dataset.py`: Dataset 配置，定义数据划分
- `factor/triple_barrier.py`: 自定义 Triple Barrier DataLoader
- `model/qlib_model.py`: qlib LGBModel 配置
- `backtest/config.py`: 回测策略和执行器配置

### 工作流

```bash
# 方式1: 使用 qrun 命令（推荐）
qrun configs/workflow_config.yaml

# 方式2: 使用 Python API
python run_pipeline.py

# 快速调试模式
python run_pipeline.py --fast
```

### 数据流

```
gm API → parquet → qlib Dataset → Alpha158 → LGBModel → TopkDropoutStrategy → 回测
```