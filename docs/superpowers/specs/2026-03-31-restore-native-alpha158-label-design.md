---
name: restore-native-alpha158-label
description: 将 workflow_by_code.py 的 handler 从自定义 Alpha158FixedBetaHandler 切换为 qlib 原生 Alpha158
type: project
---

# 恢复原生 Alpha158 Label

## 背景

当前 `workflow_by_code.py` 使用自定义 `Alpha158FixedBetaHandler`，label 由 `PathTargetBuilder` 计算（基于路径目标的自定义策略）。

用户希望恢复使用 qlib 原生 Alpha158 的 label：

- 原生 label: `Ref($close, -2)/Ref($close, -1) - 1`
- 即未来 2 天相对于未来 1 天的收益率

## 设计方案

修改 `CSI1000_GBDT_TASK` 配置中的 handler：

| 项目 | 当前值 | 新值 |
|------|--------|------|
| class | `Alpha158FixedBetaHandler` | `Alpha158` |
| module_path | `data.handler_fixed_beta` | `qlib.contrib.data.handler` |
| kwargs | 包含 benchmark, beta_alpha, filter_pipe | 仅保留 start_time, end_time, fit_start_time, fit_end_time, instruments |

## 实施范围

- 仅修改 `workflow_by_code.py` 第 74-95 行的 handler 配置
- 不修改模型、segments、回测等其他配置
- 不删除 `data/handler_fixed_beta.py`（保留供其他 workflow 使用）