# Alpha-MQ 项目指令

本项目是一个量化交易研究平台，专注于基于 Qlib 和 LightGBM 的截面因子策略（特别是 Alpha158）开发、回测与优化。

## 项目概述
- **核心框架**: [Qlib](https://github.com/microsoft/qlib) (因子管理、数据工程、回测)
- **模型**: LightGBM (分类、回归、排序任务)
- **数据源**: 掘金量化 (GM API), AKShare
- **依赖管理**: 使用 `uv` 管理 Python 环境与依赖

## 核心流程与工作流
项目采用 Pipeline 模式组织，主要流程包括：
1. **数据下载 (Data Ingest)**: 从 GM 下载 CSI1000 等成分股分钟/日线数据。
2. **因子计算 (Factor Pipeline)**: 基于 Alpha158 算子计算截面因子。
3. **因子过滤 (Factor Filtering)**: 负责因子质量评估、聚类去冗余。
4. **模型训练 (Model Pipeline)**: LightGBM 模型训练、滚动预测、超参优化。
5. **回测评估 (Backtest & Evaluation)**: 使用 Qlib 和 Alphalens 进行绩效评估，生成 Tear Sheet。

## 关键命令 (uv 驱动)
默认使用 `uv run` 执行脚本：

- **运行 Pipeline**:
  ```bash
  # 运行 CSI1000 数据下载与预处理
  uv run python scripts/run_pipeline.py --config configs/csi1000_data.yaml
  
  # 运行 Alpha158 因子管道
  uv run python scripts/run_pipeline.py --config configs/alpha158.yaml
  
  # 运行模型训练与回测
  uv run python scripts/run_pipeline.py --config configs/model_pipeline.yaml
  ```

- **数据下载**:
  ```bash
  uv run python scripts/download_gm.py
  uv run python scripts/download_fundamentals.py
  ```

- **测试**:
  ```bash
  uv run pytest
  ```

- **代码质量**:
  ```bash
  uv run ruff check .
  uv run ruff format .
  ```

## 目录结构
- `src/`: 核心源代码
  - `pipelines/`: 各种阶段的管道实现 (data, factor, model)
  - `data_download/`: 数据抓取逻辑 (GM, AKShare)
  - `core/`: 基础类与工具
  - `etf_portfolio/`: ETF 组合优化相关逻辑
- `configs/`: YAML 配置文件，定义 Pipeline 的各个阶段和参数
- `scripts/`: 入口脚本
- `docs/plans/`: 历史设计文档与执行计划

## 开发规范
- **Python 环境**: 必须使用 `uv` 管理。
- **配置驱动**: 优先通过 `configs/` 下的 YAML 文件调整参数，而非硬编码。
- **Pipeline 扩展**: 新增功能应实现在 `src/pipelines/` 下并继承相应的基类。
- **类型注解**: 遵循现代 Python 规范，使用类型注解。
- **日志**: 使用内置 `logging` 模块，级别受 `run_pipeline.py` 的 `--verbose` 控制。
