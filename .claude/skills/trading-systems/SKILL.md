---
name: trading-systems
description: 交易系统开发知识库，基于《Trading Systems》(Tomasini & Jaekle 2009)。支持：(1) 趋势跟踪/均值回归策略设计；(2) Walk Forward Analysis 参数优化；(3) 仓位管理（固定分数、固定比率）；(4) 组合构建（权益线交叉、相关性管理）。触发于：开发交易系统、设计量化策略、参数优化验证、回测评估、仓位管理方法、多策略组合。
---

# Trading Systems

基于《Trading Systems: A new approach to system development and portfolio optimisation》的知识库。

## 快速开始

### 策略开发

查询策略类型：
- "什么是通道突破策略？" → [trend_following.md](references/trend_following.md)
- "布林带系统怎么设计？" → [mean_reversion.md](references/mean_reversion.md)

### 系统评估

查看评估标准：
- "如何判断系统是否过度拟合？" → [system_development.md](references/system_development.md)
- "RINA Index 是什么？" → [risk_management.md](references/risk_management.md)

### 仓位与组合

- "固定分数仓位管理怎么用？" → [position_sizing.md](references/position_sizing.md)
- "如何构建多策略组合？" → [portfolio_construction.md](references/portfolio_construction.md)

## 核心流程

```
想法 → 编程 → 回测 → 评估 → 优化 → Walk Forward → 仓位管理 → 组合构建
```

详见 [system_development.md](references/system_development.md) 完整流程。

## 评估指标标准

| 指标 | 优秀标准 |
|-----|---------|
| Profit Factor | > 1.5 |
| Average Trade | > 滑点 + 佣金 |
| RINA Index | > 30 |
| Max Drawdown | 尽可能低 |

## 可用资源

### References（按需加载）

| 文件 | 内容 |
|-----|------|
| [trend_following.md](references/trend_following.md) | 通道突破、均线交叉、LUXOR 案例 |
| [mean_reversion.md](references/mean_reversion.md) | 布林带、三角形系统 |
| [position_sizing.md](references/position_sizing.md) | 固定分数、固定比率、Monte Carlo |
| [risk_management.md](references/risk_management.md) | 止损、跟踪止损、评估指标 |
| [system_development.md](references/system_development.md) | 设计→测试→优化→Walk Forward |
| [portfolio_construction.md](references/portfolio_construction.md) | 分散化、权益线交叉法 |

### 代码示例

- `examples/python/trend_following.py` - 趋势跟踪系统
- `examples/python/position_sizing.py` - 仓位管理方法
- `examples/python/walk_forward.py` - Walk Forward Analysis

### 完整文档

- `Full_doc/full_content.md` - 全文（含 Figure 描述）
- `Full_doc/figures/` - 135 张原图
- `Full_doc/figures_metadata.json` - Figure 元数据索引
- `index.json` - 35+ 词条索引
- `glossary.md` - 250+ 条术语表（ATR、WFA、Kelly公式等）

## 查询方式

**概念查询**：先查 `index.json` 定位文件，再读对应 reference。

**代码生成**：参考 `examples/python/` 目录下的示例。

**流程指导**：读 [system_development.md](references/system_development.md) 获取步骤清单。

## 注意事项

1. 本书出版于 2009 年，部分工具可能已更新
2. 保持系统简单，参数不宜过多
3. 实盘前验证 Walk Forward 结果
4. 平均交易必须覆盖交易成本