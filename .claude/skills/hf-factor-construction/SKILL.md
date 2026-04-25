---
name: hf-factor-construction
description: >
  Senior high-frequency factor construction workflow for turning a market
  mechanism into a causally valid, measurable, normalized, and implementable
  factor design. Trigger when the user asks to construct, formalize, document,
  or pseudo-implement microstructure / order flow / orderbook / event-time alpha
  factors, maker toxic-flow filters, liquidation cascade factors, OFI / imbalance
  signals, Hawkes smoothing design, or binary-mask factor decomposition. Do NOT
  use for pure backtest optimization, factor mining/search, label design, model
  selection, feature importance, or full strategy validation. Core output is a
  fixed research contract: mechanism, data contract, temporal contract,
  dimensions, mask semantics, aggregation, normalization, smoothing,
  observability risk, must-fail scenarios, and minimal sanity checks.
---

# HF Factor Construction — Research-to-Implementation Skill

## What this skill is for

这个 skill 的目标不是“讲一个好听的因子故事”，而是把一个高频想法压成**资深研究员可直接开工**的研究合同。

它必须产出：

1. **Mechanism** — 因子到底在捕捉什么市场机制。
2. **Data contract** — 需要哪些字段、哪个市场层级、哪些前处理。
3. **Temporal contract** — 观测时间、可用时间、预测窗口、时间轴。
4. **Dimension table** — 二值语义维度 + 连续幅度载体。
5. **Mask semantics** — 每个重点 mask 的一句话市场解释。
6. **Aggregation formula** — 聚合算子、lookback、单位。
7. **Normalization plan** — 去季节性 / 跨标的标准化 / 波动率缩放。
8. **Smoothing plan** — EMA / Hawkes / none，及参数单位。
9. **Observability risks** — 测不准、对不齐、看不见的东西。
10. **Must-fail scenarios** — 因子应该失效的场景。
11. **Minimal sanity gate** — 覆盖率、稀疏性、单调性、时序泄漏检查。
12. **Implementation sketch** — 可以直接编码的落地框架。

如果最终回答缺少这些部分，就说明这个 skill 没真正完成任务。

---

## Non-goals

这个 skill **不负责**：

- 回测参数搜索
- “尝试所有组合选最优”
- 标签设计 / meta-labeling
- 模型调参 / 特征重要性
- 组合优化 / 风控优化
- 用回测结果倒推机制

它最多只做**minimal sanity gate**，不做完整验证闭环。

---

## Core design principles

### 1) Binary semantics + continuous magnitude

高频因子不要只做二值化，也不要只做连续值堆砌。

正确做法是双层结构：

- **Binary dimensions / masks** 负责定义市场语义分区（发生在什么状态下）
- **Continuous carrier / quantity** 负责定义幅度（发生得多强、多快、多偏）

典型形式：

```text
factor_raw = Agg( Q_t | mask_t = 1 )
```

其中：
- `mask_t` = 语义条件，例如「下跌 + 大单 + 主动卖 + 高撤单」
- `Q_t` = 幅度载体，例如 volume / OFI / queue depletion speed / signed notional

### 2) Causality before cleverness

任何高频因子先看：
- 你在 `t` 时刻是否真的拿得到这些信息？
- 这些信息是否被同一时间轴定义？
- 是否把未来事件簇定义回灌到了过去？

### 3) Measurability matters

很多“维度”在理论上存在，但在真实数据里测不准。

每个维度都必须额外声明：
- 需要的数据层级
- 测量误差来源
- 哪些交易所 / 市场结构下会偏掉

### 4) Standardization is part of the factor

高频因子若不处理：
- intraday seasonality
- symbol liquidity heterogeneity
- tick size effects
- activity regime drift

那很可能只是把市场活跃度重新命名。

### 5) A good factor must know where it dies

每个构造都必须给出**must-fail scenarios**。不会死的因子，通常只是描述性统计，不是交易信号。

---

## Mandatory output contract

回答高频因子构造请求时，按下面结构输出。

### A. Mechanism
- 一句话说明微观机制
- 说明谁在被迫交易 / 提供流动性 / 清库存 / 吃冲击

### B. Research context
- use case: maker gate / taker alpha / cross-sectional / time-series / regime filter
- forecast horizon
- holding logic assumptions
- market / venue / instrument scope

### C. Data contract
- required columns
- market layer: trade / L1 / L2 / L3 / bar
- sampling axis: clock / event / volume / dollar / trade-count
- preprocessing: dedup, session cut, auction handling, outlier handling

### D. Temporal contract
每个构造必须明确：
- `t_obs`: 特征观测时刻
- `t_available`: 数据对策略真实可用的时刻
- `window_feature`: 特征使用的历史窗口
- `window_target`: 要预测的未来窗口
- `time_axis`: 秒 / 毫秒 / event index / volume time / dollar time
- `latency assumption`: 若涉及撮合/网络/快照延迟，明确写出

禁止默认省略。

### E. Dimension table
至少包含：
- id
- algebraic type
- mask definition
- continuous carrier
- input columns
- granularity
- time axis
- adaptive threshold
- observability risk

### F. Mask semantics
- 只列重点 mask，不要机械列满所有组合
- 每个重点 mask 必须一句话解释
- 如果某个组合不可能出现，明确标记 impossible mask

### G. Aggregation
- operator
- formula
- lookback
- denominator / baseline
- units

### H. Normalization
明确说明下列哪些要做：
- within-symbol normalization
- cross-symbol normalization
- intraday seasonal adjustment
- volatility scaling
- activity-rate scaling
- ADV / notional scaling

### I. Smoothing
- none / EMA / Hawkes
- 参数单位
- 何时平滑：**聚合后**
- 何时不用 Hawkes

### J. Observability & implementation risk
至少列 3 个：
- trade side 判定偏差
- book/trade 对齐误差
- snapshot 漏掉簇内动态
- hidden liquidity / iceberg
- venue-specific matching rule
- queue position 不可见

### K. Must-fail scenarios
至少 2 个，并说明为什么该失效。

### L. Minimal sanity gate
最少要检查：
- coverage / support
- mask frequency collapse
- class imbalance / 稀疏性
- same-step vs next-step 信息泄漏
- threshold sensitivity
- monotonic bucket sanity
- session dependence
- portability across symbols/venues

### M. Implementation sketch
给出伪代码 / Polars / Python 实现骨架即可，不做参数搜索。

---

## Algebraic typing system

不要只区分 `A / C`。实际工作时用下面 5 类：

| 类型 | 含义 | 例子 | 合法操作 |
|---|---|---|---|
| `A_qty` | 可加总的数量 | volume, signed volume, cancel size | SUM, DIFF, RATIO |
| `A_rate` | 速率/强度 | trade intensity, cancel intensity | RATE, ZSCORE, RELATIVE RATE |
| `A_price` | 价格/价差/冲击量 | return, spread change, impact slope | DIFF, SCALE, STANDARDIZE |
| `C_state` | 市场状态过滤器 | high vol, trend regime, auction state | FILTER, COUNT, FREQ |
| `C_event` | 事件发生指示 | burst, gap, wall detected | COUNT, HAZARD, DURATION |

### Combination rules

```text
A_* × A_*     -> amplitude composition allowed if units remain interpretable
A_* × C_*     -> filtered amplitude
C_* × C_*     -> only event/state counting or hazard style aggregation
```

若单位解释不清，默认非法。

---

## Time-axis contract

高频因子必须显式说明在哪个时间轴定义：

- **clock time**: 秒 / 毫秒
- **event time**: 每笔事件序号
- **trade-count time**
- **volume time**
- **dollar time**

并明确：
- 维度在哪个时间轴计算
- 聚合在哪个时间轴滚动
- 平滑在哪个时间轴衰减
- 最终输出落到哪个栅格

禁止把 event-time 特征和 second-based Hawkes 参数混成一个未说明的系统。

---

## Standard normalization rules

默认优先考虑：

1. **同标的去季节性**
   - trade count / volume / cancel / spread 的日内 U-shape
2. **同标的时间标准化**
   - rolling z-score / robust z-score / percentile rank
3. **跨标的对齐**
   - ADV / notional / volatility / average spread scaling
4. **活跃度归一化**
   - 用 total events / total volume / baseline rate 做分母
5. **波动率归一化**
   - 适用于 impact / jump / excursion 类量

如果明确不做，必须解释为什么。

---

## Minimal sanity gate

这个 skill 虽不做 full validation，但必须做最小卫生检查：

1. **Coverage** — 有多少时间点 / 事件能产生值
2. **Support** — 主 mask 占比是否太稀疏或太泛
3. **Mask collapse** — 是否大部分 mask 永远不出现
4. **Threshold stability** — 阈值轻微扰动后是否完全变脸
5. **Leakage gap** — same-step 显著好于 next-step 时要警惕泄漏
6. **Monotonic bucket sanity** — 幅度越强是否在统计上更符合机制方向
7. **Session dependence** — 是否只在开盘/收盘/特定时段成立
8. **Portability** — 是否只在一个标的 / 一个 venue 存在

---

## Common failure mechanisms

回答里优先检查这些“伪 alpha 马甲”：

- 只是活跃度 proxy
- 只是 spread proxy
- 只是 volatility proxy
- 只是 session effect
- 只是 trade classification artifact
- 只是 snapshot sampling artifact
- 只在特定 fee / queue rule 下有效
- 一旦加上 latency / queue reality 就消失

---

## Anti-patterns

| 反模式 | 为什么错 | 正确做法 |
|---|---|---|
| 维度购物 | 先试再讲故事 | 先机制后维度 |
| 全部离散化 | 丢失强度信息 | mask + continuous carrier |
| 只堆连续量 | 没有清晰语义边界 | 先定义状态分区 |
| 用未来定义当前 burst | 时间泄漏 | burst 必须由历史窗口实时定义 |
| 对 Type C 做加减 | 单位不成立 | Type C 只做过滤/计数 |
| 平滑前聚合缺失 | 把价格平滑伪装成因子 | 先聚合，再平滑 |
| 粒度混用 | time axis 不一致 | 写清采样与对齐规则 |
| 默认参数无单位 | 无法迁移 | 参数必须带时间单位 / 半衰期 |

---

## Working procedure

1. 写一句**机制句子**。
2. 写 **data contract**。
3. 写 **temporal contract**。
4. 选 2–4 个维度，优先 3 个。
5. 为每个维度指定 **algebraic type** 与 **continuous carrier**。
6. 写重点 mask 的一句话解释。
7. 指定聚合公式和单位。
8. 指定 normalization。
9. 指定 smoothing 及参数单位。
10. 列 observability risks。
11. 列 must-fail scenarios。
12. 跑 minimal sanity gate。
13. 最后再给实现草图。

---

## File references

```text
scripts/
├── dimension_validator.py   # schema / temporal / sparsity / mask collapse 检查
├── factor_template.py       # 生成固定输出契约模板
└── hawkes_smooth.py         # 单变量/多变量 Hawkes 平滑实现（单位明确）

references/
├── dimension_library.md     # machine-readable 风格维度库
├── temporal_causality.md    # 时间因果与可得性检查
├── failure_mechanisms.md    # 常见伪 alpha / 失效机制库
├── pipeline_examples.md     # 3 个完整因子设计范例
└── hawkes_smoothing.md      # Hawkes 使用与调参指南
```

## How to answer with this skill

默认输出结构：

1. 机制与使用场景
2. data / temporal contract
3. 维度表
4. 重点 mask 与语义
5. 聚合 + 标准化 + 平滑
6. 观测误差 / 实现风险
7. must-fail scenarios
8. minimal sanity gate
9. implementation sketch

若用户只要一个简短版本，也至少保留：
**机制、temporal contract、维度表、聚合公式、must-fail**。
