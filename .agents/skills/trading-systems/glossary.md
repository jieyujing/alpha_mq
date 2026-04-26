# 术语表 (Glossary)

> 来源：Trading Systems by Tomasini & Jaekle

## A

### Average Trade (平均交易)
净利润除以交易次数。必须大于交易成本（滑点 + 佣金）才有实盘价值。
```
Average Trade = Net Profit / Total Number of Trades
```

### ATR (Average True Range, 平均真实波幅)
衡量价格波动性的指标，常用于动态止损计算。
```
ATR = MA(True Range, N)
True Range = max(High-Low, |High-Close_prev|, |Low-Close_prev|)
```

### Anchored WFA (锚定式前向分析)
起始点固定的前向分析方法，窗口逐渐增大。

## B

### Bollinger Bands (布林带)
由中轨（移动平均线）和上下轨（标准差倍数）组成的通道指标。
```
中轨 = SMA(Close, N)
上轨 = 中轨 + K × StdDev(Close, N)
下轨 = 中轨 - K × StdDev(Close, N)
```

### Back-test (回测)
在历史数据上测试交易策略的表现。

### Breakout (突破)
价格突破某个关键价位（如 N 日最高/最低）的信号。

## C

### Channel Breakout (通道突破)
趋势跟踪策略，在价格突破 N 日高点时买入，突破 N 日低点时卖出。

### Correlation (相关性)
两个系统权益线之间的统计关系。组合构建时应选择低相关性系统。

### Curve Fitting (曲线拟合)
过度优化导致系统只在历史数据上表现良好，失去未来预测能力。

### Continuous Contract (连续合约)
将多个到期合约拼接而成的连续价格序列，用于回测。

## D

### Drawdown (回撤)
权益曲线从峰值到谷底的跌幅。
```
Drawdown = (Peak - Trough) / Peak × 100%
```

### Degrees of Freedom (自由度)
交易系统中可优化参数的数量。自由度越高，过度拟合风险越大。

## E

### EasyLanguage
TradeStation 平台的编程语言，书中代码示例主要使用此语言。

### Equity Line (权益曲线)
账户权益随时间变化的曲线。

### Equity Line Crossover (权益线交叉)
使用移动平均线判断系统是否失效的方法。当权益线跌破均线时暂停交易。

### Entry Rule (入场规则)
定义何时开仓交易的规则。

### Exit Rule (出场规则)
定义何时平仓离场的规则。

## F

### Fixed Fractional MM (固定分数仓位管理)
每笔交易风险固定比例账户资金的方法。
```
合约数 = (账户权益 × 风险比例) / (每点价值 × 止损距离)
```

### Fixed Ratio MM (固定比率仓位管理)
根据累计盈利逐步增加仓位的方法，由 Ryan Jones 提出。
```
每增加 1 单位合约需要盈利 = Delta × 当前合约数
```

## I

### In-Sample (IS, 样本内)
用于优化的历史数据部分。

### Initial Stop Loss (初始止损)
开仓时设置的止损价位，用于限制单笔交易最大亏损。

## K

### Kelly Criterion (凯利公式)
最优仓位计算公式。
```
f* = (p × b - q) / b
其中：p=胜率，q=1-p，b=盈亏比
```

## L

### Largest Losing Streak (最大连续亏损)
连续亏损交易的最大次数，用于心理准备和资金管理。

### Largest Losing Trade (最大单笔亏损)
单笔交易的最大亏损金额。

### LUXOR System
本书 Part II 完整开发的趋势跟踪系统案例，基于双均线交叉。

## M

### Money Management (MM, 仓位管理)
决定每笔交易投入多少资金（交易多少合约）。区别于风险管理。

### Maximum Drawdown (最大回撤)
历史回测中出现的最大回撤值。

### Mean Reversion (均值回归)
基于价格会回归均值的假设进行交易的方法。

### Monte Carlo Analysis (蒙特卡洛分析)
通过随机抽样历史交易来评估策略风险的方法。

### Moving Average Crossover (均线交叉)
短期均线上穿/下穿长期均线产生交易信号。

## N

### Net Profit (净利润)
总盈利减去总亏损。

## O

### Optimisation (优化)
寻找交易系统最佳参数的过程。

### Out-of-Sample (OOS, 样本外)
未参与优化的数据，用于验证系统有效性。

## P

### Profit Factor (盈亏比)
总盈利除以总亏损。优秀标准：> 1.5。
```
Profit Factor = Gross Profit / Gross Loss
```

### Position Sizing (仓位 sizing)
同 Money Management，决定交易规模。

### Portfolio Construction (组合构建)
将多个系统和市场组合在一起的方法。

### Perpetual Contract (永续合约)
无到期日的合约，适合回测。

## R

### Risk Management (RM, 风险管理)
设置止损价位等风险控制措施。区别于仓位管理。

### RINA Index
综合评估指标，由 RINA Systems 提出。
```
RINA Index = (Net Profit × Trade Efficiency) / (Max Drawdown × Time in Market)
```

### Robustness (稳健性)
系统在不同市场条件和参数下的稳定表现能力。

### Rolling WFA (滚动式前向分析)
固定窗口大小、每次向前滚动固定步长的前向分析方法。

## S

### Stop Loss (止损)
预设的退出价位，用于限制亏损。

### Stability Diagram (稳定性图)
展示系统在不同参数组合下表现的可视化图表。

### Sharpe Ratio (夏普比率)
风险调整收益指标。
```
Sharpe = (Rp - Rf) / σp
```

### Sortino Ratio (索提诺比率)
只考虑下行风险的风险调整收益指标。

### Slippage (滑点)
实际成交价格与预期价格的差异。

## T

### Trailing Stop (跟踪止损)
随盈利扩大而调整的止损，用于保护利润。

### Trend Following (趋势跟踪)
顺势交易的策略类型，核心是"让利润奔跑，截断亏损"。

### Trade Efficiency (交易效率)
净利润与总交易金额的比率。

### Timeframe (时间周期)
K 线的时间单位（日线、小时线、分钟线等）。

## W

### Walk Forward Analysis (WFA, 前向分析)
滚动窗口优化 + 样本外测试的验证方法。

### Win Rate (胜率)
盈利交易占总交易的比例。
```
Win Rate = 盈利交易数 / 总交易数 × 100%
```

## 缩写对照表

| 缩写 | 全称 | 中文 |
|-----|------|------|
| MM | Money Management | 仓位管理 |
| RM | Risk Management | 风险管理 |
| WFA | Walk Forward Analysis | 前向分析 |
| IS | In-Sample | 样本内 |
| OOS | Out-of-Sample | 样本外 |
| ATR | Average True Range | 平均真实波幅 |
| SMA | Simple Moving Average | 简单移动平均 |
| StdDev | Standard Deviation | 标准差 |

## 相关资源

- **软件工具**: TradeStation, MultiCharts, Portfolio Maestro
- **数据提供商**: 各期货交易所数据、连续合约数据
- **参考书籍**: 见 SKILL.md 扩展阅读部分
