# ETF Portfolio Optimization: Trend Filtering (Hard Signal)
**Date:** 2026-04-16

## 1. 目标 (Objectives)
针对目前多资产 ETF 组合在滚动回测中表现波动剧烈、夏普比率低、回撤大的问题，引入“动量过滤（Trend Following）”机制。核心思想是：**只在资产处于上升趋势时进行配置，在下跌趋势时强制空仓。**

## 2. 核心逻辑 (Core Logic)
### 2.1 趋势信号计算
- **指标**：60日简单移动平均线 (SMA60)。
- **信号 (Signal)**：
    - $Price_t > SMA60_t \implies Signal = 1$ (多头，可参与配置)
    - $Price_t \leq SMA60_t \implies Signal = 0$ (空头，强制剔除)
- **执行时间**：在每次调仓日（Rebalance Date）的前一交易日收盘后计算，用于指引当期的权重分配。

### 2.2 优化流程集成
1. **预处理**：在调用 `riskfolio-lib` 之前，计算当前池中 15 只 ETF 的 SMA60 信号。
2. **资产掩码 (Masking)**：
    - 仅保留 $Signal=1$ 的资产进入收益率矩阵（Returns Matrix）。
    - 被剔除资产的权重直接归零。
3. **极端情况处理 (Fallback)**：
    - 如果所有资产均被剔除（所有 $Signal=0$），则全额持有现金（或流动性极佳的货币基金标的，例如 `SHSE.511260` 国债 ETF 作为代位标的）。

## 3. 架构组件 (Components)
- **`src/etf_portfolio/rolling.py`**: 
    - 修改 `run_rolling_backtest` 循环，注入信号计算与过滤逻辑。
    - 增加掩码处理，确保优化器只处理“可交易”资产。
- **`src/etf_portfolio/optimizer.py`**:
    - 增强稳健性，确保在输入资产数量动态变化时（甚至只有 1 只或 0 只时）不会报错。

## 4. 预期效果 (Expected Outcomes)
- **回撤控制**：在市场普遍下跌（如 2022 年或 2024 年初）时，及时退出风险资产，显著降低最大回撤。
- **夏普比提升**：剔除负 Alpha 资产（处于单边下跌中的标的），提高剩余配置资金的效率。
- **鲁棒性**：作为多资产配置的“第一道防线”，防止模型在熊市中强行寻找分散化而导致的无效持有。
