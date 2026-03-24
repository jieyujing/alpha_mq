# 中证1000多因子选股系统

基于 qlib 因子框架的中证1000指数增强策略。

## 快速开始

### 1. 安装依赖

```bash
pip install -e ".[dev]"
```

### 2. 构建数据集

```bash
python data/scripts/build_qlib_data.py --start-date 2020-01-01 --end-date 2024-12-31
```

### 3. 运行策略

```bash
# 使用 qlib 工作流
qrun configs/workflow_config.yaml

# 或使用 Python API
python run_pipeline.py

# 快速调试模式
python run_pipeline.py --fast
```

## 项目结构

```
alpha_mq/
├── configs/              # qlib YAML 工作流配置
├── data/                 # 数据下载和转换
├── factor/               # 因子模块
│   ├── handler.py        # Alpha158 DataHandler
│   ├── dataset.py        # Dataset 配置
│   └── triple_barrier.py # Triple Barrier DataLoader
├── model/                # 模型模块
│   ├── config.py         # 自定义模型配置
│   └── qlib_model.py     # qlib LGBModel 配置
├── backtest/             # 回测模块
│   └── config.py         # 策略和执行器配置
└── run_pipeline.py       # 主入口脚本
```

## 技术栈

- **pyqlib**: 因子框架和回测引擎
- **gm (掘金 SDK)**: 行情数据源
- **lightgbm**: 梯度提升模型
- **polars/pandas**: 数据处理