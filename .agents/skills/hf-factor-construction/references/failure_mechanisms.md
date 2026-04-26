# Failure Mechanisms Library

## Why keep this file

真正能交易的高频因子，不只是解释“为什么会有效”，还要预先写出“它什么时候应该失效”。

---

## 1. Activity proxy masquerading as alpha

症状：
- 因子几乎和 trade count / volume / notional 同向
- 高值区间只对应“市场很热闹”

拆解方式：
- 对 total activity 做归一化
- 在同 activity 分层内再看因子
- 检查去季节性前后是否还存在

---

## 2. Spread proxy masquerading as alpha

症状：
- 因子好坏几乎只由 spread 状态决定
- 一旦控制 spread bucket，效果显著衰减

常见来源：
- tightness / widen 类变量未与 flow 联动

---

## 3. Volatility proxy masquerading as alpha

症状：
- 高因子值总出现在高波动期
- 控制 realized vol 后几乎消失

拆解方式：
- vol-scaled normalization
- 在 vol 分层内检查单调性

---

## 4. Session effect masquerading as alpha

症状：
- 只在开盘 / 收盘 / 午后回流某个时段有效
- 换到别的时段完全失效

拆解方式：
- 明确加入 `M_session_edge` 作为控制
- 分时段报告统计

---

## 5. Trade classification artifact

症状：
- 用 direct aggressor side 时有效，用 Lee-Ready 就大幅变化
- 中间价成交附近最不稳定

拆解方式：
- 报告 side inference 方法
- 在 ambiguous trades 上单独剔除再看

---

## 6. Snapshot artifact

症状：
- 换更高频 book 数据后信号消失或反转
- 因子主要依赖“没看到变化”

拆解方式：
- 记录 snapshot interval
- 对不同 sampling interval 做稳定性检查

---

## 7. Queue-unaware illusion

症状：
- maker alpha 在理想回测中存在，一加 queue reality / latency 就衰减

拆解方式：
- 把 queue position uncertainty 写进 observability risk
- 对 maker only 因子明确说明 fill-conditioned 或 pre-fill use case

---

## 8. Venue-rule dependence

症状：
- 换撮合规则、手续费结构、最小价位后效果明显变化

拆解方式：
- 记录 venue assumptions
- 把 portability 当成最小 sanity gate 的一部分

---

## 9. Threshold fragility

症状：
- 阈值从 q80 改到 q75 / q85 后因子分布或方向大变

拆解方式：
- 对 2~3 个邻近阈值做鲁棒性检查
- 少用魔术常数，多用相对分位数与基线比值

---

## Must-fail template

```yaml
must_fail_1:
  condition: low-activity, tight-spread, no directional flow regime
  rationale: without flow imbalance or liquidity withdrawal, mechanism should be absent
must_fail_2:
  condition: side tags unavailable and quote staleness too high
  rationale: signal depends on reliable aggressor direction inference
must_fail_3:
  condition: venue switches to coarse snapshots only
  rationale: depletion / cancel dynamics become unobservable
```
