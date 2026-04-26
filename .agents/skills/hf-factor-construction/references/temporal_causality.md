# Temporal Causality & Availability Contract

高频因子最容易死在“定义得很漂亮，但用到了未来”。这份清单专门用来防这件事。

## Required fields

每个因子设计必须写清：

- `t_obs`: 特征观测时刻
- `t_available`: 数据真实可用时刻
- `t_action`: 策略可采取动作时刻
- `window_feature`: 历史特征窗口
- `window_target`: 未来预测窗口
- `time_axis`: clock / event / volume / dollar
- `latency_assumption`: feed latency / decision latency / order latency

必须满足：

```text
t_obs <= t_available <= t_action < window_target.start
```

## Common leakage patterns

### 1. Future-completed burst leakage
错误：用未来 1 秒内总成交数定义“当前 burst”。

正确：burst 只能由 `[t-L, t]` 的历史到达率决定。

### 2. Bar close leakage
错误：用当前 bar close 构造特征，再预测同一 bar 后半段。

正确：若 feature 使用 close，则目标必须从下一 bar 开始。

### 3. Trade/quote stale alignment
错误：用未对齐 quote 给 trade 打 side，再把这个当精确信号。

正确：记录 quote staleness，并在报告中写 side inference 方法。

### 4. Post-event path encoded as current state
错误：把交易后的回撤、反弹、后续 impact 直接作为当前特征。

正确：这类量只能用于 target / sanity / validation，不能回流进 feature。

### 5. Snapshot undersampling masquerading as structure
错误：把 200ms snapshot 之间未观察到的细节当作真实“没有发生”。

正确：在 observability risk 里写清：未观测 ≠ 未发生。

## Time-axis selection

### Use clock time when
- 事件间隔本身带信息
- 需要真实衰减时间
- 要用 EMA/Hawkes 的秒级半衰期解释

### Use event time when
- 你关心“每发生几笔”而非“过了几秒”
- 时段活跃度差异太大，想先消掉 activity seasonality

### Use volume/dollar time when
- 你要控制不同活跃度下的信息流尺度
- 你不希望固定秒数对应完全不同的市场参与度

## Availability checklist

- 数据时间戳是 exchange time 还是 receive time？
- side 是直给还是推断？
- book 是 snapshot 还是 incremental？
- snapshot 间隔是否稳定？
- 是否包含 auction / funding / halt / maintenance windows？
- 对齐时是否使用 forward fill？若使用，最长 stale time 是多少？

## Minimal writeup template

```yaml
t_obs: feature bucket end
t_available: feed arrival + alignment complete
t_action: next decision tick / next bar open / immediate after fill
time_axis: clock seconds
window_feature: [t-30s, t]
window_target: (t, t+10s]
latency_assumption:
  feed_ms: 120
  decision_ms: 5
  order_ms: 20
notes:
  - side inferred by quote rule with stale quote filter <= 50ms
  - auction prints removed
  - session open first 60s excluded
```
