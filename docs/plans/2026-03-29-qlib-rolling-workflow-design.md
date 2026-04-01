# 2026-03-29 Qlib Rolling Workflow Design

## 概述 (Overview)
本项目旨在基于 Qlib 框架构建一个“代码内工作流 (Workflow by Code)”，用于中证 1000 指数成分股的多因子 Alpha 模型。核心亮点是集成了基于路径质量（Triple Barrier + MAE 惩罚 + Beta 中性化）的自定义标签，并采用每半年滚动重训 (Semi-annual Rolling) 的策略以适应市场风格变化。

## 架构设计 (Architecture)

### 1. 数据处理器 (Data Management)
我们将实现一个自定义的 `EnhancedAlpha158Handler` 类，继承自 `qlib.contrib.data.handler.Alpha158`：
- **特征 (Features):** 使用 Qlib 的 `Alpha158` 算子库，提供 158 个技术驱动型因子。
- **自定义标签 (Custom Label):** 
  - 集成 `path_target.py` 中的 `PathTargetBuilder`。
  - 输入：`close` 价格、市场基准（`SH000852`）及预计算的 `beta` 字段。
  - 参数：注入 `PathTargetConfig` 作为 Handler 的初始化参数。
- **数据源:** 加载位于 `data/qlib_data` 的二进制数据集。

### 2. 模型逻辑 (Model Development)
- **模型类型:** `LightGBM` (通过 `qlib.contrib.model.gbdt.LGBModel` 实现)。
- **目标函数:** `objective='lambdarank'`。
- **训练方式:** 
  - 核心标签为路径质量的截面 Rank 百分比 (0, 1)。
  - `lambdarank` 会基于交易日期作为 Group ID 进行局部排序优化。

### 3. 滚动训练策略 (Rolling Strategy)
- **重训周期:** 每 6 个月（约 125 个交易日）进行一次模型更新。
- **滑动窗口:** 
  - **训练窗:** 过去 5 年数据。
  - **预测窗:** 未来 6 个月数据。
- **逻辑实现:** 在 Python 脚本中手动遍历时间窗口，串接各窗期的预测分值。

### 4. 收益评估与回测 (Backtesting)
- **基准 (Benchmark):** `SH000852` (中证 1000)。
- **选股策略:** `TopkDropoutStrategy` (Top K=100)。
- **手续费:** A股标准设置（印花税 0.1%，两边佣金 0.03%）。

## 数据流 (Data Flow)
1. `qlib.init()` 初始化本地数据路径。
2. `EnhancedAlpha158Handler` 从磁盘读取原始字段，计算特征，并调用 `PathTargetBuilder` 生成标签。
3. `DatasetH` 包装 Handler，按滚动窗口切分训练、验证和测试集。
4. `LGBModel` 训练。
5. 获取预测结果，串联后进行 `PortfolioAnalysis` 评估指标。

## 成功标准 (Success Criteria)
- 模型能成功生成基于 `path_target` 逻辑的预测排名指标。
- 滚动预测序列在全样本测试集上表现稳定。
- 回测指标（Sharpe, MDD, Win Rate）优于单纯基于单日收益率（Return）标签的基准模型。

---
> [!NOTE]
> 该设计文档由 Antigravity 根据用户决策生成，旨在规范中证 1000 路径模型的工作流开发。
