# 2026-04-22 Alpha158 多周期收益率训练配置设计

## 1. 背景与目标
在完成 CSI 1000 基础数据入库后，需要构建一个 Qlib 训练配置文件，整合 Alpha158 因子、现有基本面特征（估值、市值、换手等），并预测多个周期的收益率（1D, 5D, 10D, 20D）。

## 2. 核心架构

### 2.1 数据处理器 (Data Handler)
使用 `qlib.contrib.data.handler.Alpha158` 作为基类，通过 `extra_features` 整合非价量因子。

**特征构成：**
- **Alpha158**: Qlib 自动生成的 158 个价量特征（基于 open, high, low, close, volume, factor）。
- **附加特征 (Extra Features)**: 
    - 估值：`pe_ttm`, `pb_mrq`, `ps_ttm`, `pcf_ttm_oper`
    - 市值：`tot_mv`, `a_mv`
    - 基础：`turnrate`, `ttl_shr`, `circ_shr`

### 2.2 标签 (Labels)
定义四个目标变量，均基于收盘价计算：
- `LABEL_1D`: `Ref($close, -1) / $close - 1`
- `LABEL_5D`: `Ref($close, -5) / $close - 1`
- `LABEL_10D`: `Ref($close, -10) / $close - 1`
- `LABEL_20D`: `Ref($close, -20) / $close - 1`

## 3. 详细配置设计

### 3.1 任务设置 (Task)
- **Model**: `LGBModel` (LightGBM)
- **Loss**: `mse` (由于是回归任务)
- **Data Splitting**:
    - `train`: 2020-01-01 至 2023-12-31
    - `valid`: 2024-01-01 至 2024-12-31
    - `test`: 2025-01-01 至 2026-04-20

### 3.2 预测与评估
- 每个周期将独立计算预测值。
- 评估指标：`Standard` 评估器，输出 IC, Rank IC, Win Rate 等。

## 4. 交付物
- `configs/alpha158_train.yaml`: 完整的 Qlib 训练配置文件。
