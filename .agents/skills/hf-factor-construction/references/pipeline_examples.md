# Pipeline Examples — End-to-End Factor Design Sketches

下面每个例子都按固定输出契约来写，目的是让研究员能直接开工，而不是只看概念。

---

## Example 1 — 下跌吸筹因子（A-share / crypto 通用框架）

### Mechanism
大额主动买入在下跌过程中持续出现，说明有强买方在逆势承接，短期可能带来价格支撑或后续抬升。

### Research context
- use case: short-horizon taker alpha / cross-sectional ranking
- forecast horizon: next 10–30 bars or next 1–5 minutes
- market: liquid names only

### Data contract
- required columns: `trade_price`, `trade_size`, `aggressor_side`, `mid`, `timestamp`
- market layer: trade + L1 mid
- time axis: trade event time for dimensions, clock-time bucket for aggregation
- preprocessing: remove auction / opening uncross / known bad prints

### Temporal contract
- `t_obs`: current bucket end
- `t_available`: end of bucket after all trades aligned
- `window_feature`: trailing 60s or trailing 200 trades
- `window_target`: next bucket onward

### Dimensions
| id | type | mask definition | continuous carrier |
|---|---|---|---|
| `V_side` | `A_qty` | buyer-initiated = 1 | signed notional |
| `V_size_rel` | `C_event` | size > rolling q80 | size / baseline |
| `P_dir_tick` | `C_event` | mid change > 0 | abs mid change |

Primary semantic mask:
- `V_side=1 & V_size_rel=1 & P_dir_tick=0`
- 解释：**下跌中的大额主动买入 = 逆势承接 / 吸筹迹象**

### Aggregation
```text
raw = SUM(signed_notional | buy & large & price_down, lookback)
base = SUM(abs(notional), lookback)
factor_raw = raw / max(base, eps)
```

### Normalization
- within-symbol robust z-score
- intraday seasonal adjustment on size baseline
- optional cross-sectional rank at decision times

### Smoothing
- if bucketed to 5s/10s bars: EMA
- if kept as event stream: Hawkes with 2–5s half-life

### Observability risks
- aggressor side inference quality
- mid update staleness
- large-size threshold differs by symbol liquidity

### Must-fail scenarios
1. extremely low-activity regime with few real large trades
2. auction / opening burst periods where prints are structural, not informational

### Minimal sanity gate
- support of primary mask should not be near-zero
- effect should survive within same activity bucket
- threshold q75/q80/q85 should not flip sign

---

## Example 2 — Maker toxic-flow gate

### Mechanism
maker 成交前后，如果 trade count 突升、近端 bid 快速被抽空、spread 扩大，说明 adverse selection 风险上升，此时不应继续挂单或应快速撤单。

### Research context
- use case: maker pre-fill gate or post-fill adverse-flow monitor
- forecast horizon: next 0.5s – 5s
- market: crypto perps / high-frequency L2 snapshots

### Data contract
- required columns: `timestamp`, `best_bid`, `best_ask`, `bid_depth_near`, `ask_depth_near`, `trade_count`, `signed_trade_notional`
- market layer: L2 snapshot + trade tape
- time axis: clock seconds
- preprocessing: synchronize book/trade, record snapshot interval, remove maintenance gaps

### Temporal contract
- `t_obs`: current snapshot time
- `t_available`: snapshot arrival time after alignment
- `t_action`: next cancel / quote refresh decision
- `window_feature`: trailing 1–3s
- `window_target`: next 0.5–2s adverse move or fill toxicity metric

### Dimensions
| id | type | mask definition | continuous carrier |
|---|---|---|---|
| `T_trade_count_high` | `C_state` | trade_count / baseline > k | relative trade count |
| `OB_depletion_bid` | `A_rate` | use sign convention on bid-side queue depletion | shares/sec depleted |
| `P_spread_widen` | `A_price` | spread_t - spread_{t-1}` | spread change |
| `V_side_sell` | `A_qty` | seller-initiated side | signed sell notional |

Primary semantic mask:
- `trade_count_high & bid_depletion_strong & spread_widen & sell_pressure`
- 解释：**高频卖压 + 买盘抽空 + 点差扩大 = maker 毒流风险上升**

### Aggregation
```text
toxic_score =
    z(depletion_bid_rate)
  + z(spread_change)
  + z(relative_trade_count)
  + z(sell_notional_share)
```

or masked form:

```text
mask = trade_count_high & spread_widen
factor_raw = SUM(depletion_bid_rate + sell_notional_share | mask, trailing 2s)
```

### Normalization
- intraday baseline for trade count
- symbol-level scaling by average near-touch depth
- spread change in ticks, not raw currency

### Smoothing
- Hawkes preferred if acting on raw snapshots/events
- half-life around 0.5–2s, eta around 0.3–0.5

### Observability risks
- snapshots may miss within-interval queue depletion
- replace vs cancel ambiguity
- fill timestamps and local clock skew can distort post-fill logic

### Must-fail scenarios
1. stable, low-activity mean-reverting book with no spread expansion
2. coarse snapshot feed where depletion speed is unobservable
3. symbols with unreliable side inference

### Minimal sanity gate
- compare same signal on different snapshot intervals
- check whether effect remains after controlling total activity
- verify signal is stronger pre-adverse move than same-step only

---

## Example 3 — Liquidation cascade intensity

### Mechanism
强制平仓会带来方向一致、时间簇集、流动性撤退和价格跳变；真正的级联不是“单次大跌”，而是**跳变 + burst + 方向一致 + 盘口退却**的组合。

### Research context
- use case: event-time intensity factor / regime warning
- forecast horizon: next few seconds to minutes depending venue

### Data contract
- required columns: `mid`, `trade_size`, `aggressor_side`, `timestamp`, `near_touch_depth`, `spread`
- market layer: trade + L2
- time axis: clock seconds for Hawkes interpretation

### Dimensions
| id | type | mask definition | continuous carrier |
|---|---|---|---|
| `P_jump_rel` | `C_event` | |Δmid| > rolling_vol * k | normalized jump |
| `V_cluster` | `C_event` | arrival rate above baseline | excess event intensity |
| `V_side` | `A_qty` | sell-initiated = 0 | signed sell notional |
| `OB_depletion_ask/bid` | `A_rate` | choose side-consistent depletion | depletion speed |

Primary mask:
- `jump & burst & sell & bid_depletion`
- 解释：**下行跳变伴随卖压簇集与买盘抽空 = 级联特征事件**

### Aggregation
```text
cascade_notional = SUM(sell_notional | jump & burst & bid_depletion, lookback)
total_notional = SUM(abs(notional), lookback)
raw = cascade_notional / max(total_notional, eps)
```

### Smoothing
这里 Hawkes 很合适：
- 事件天然不规则
- 簇集本身就是机制的一部分

### Must-fail scenarios
1. open/close structural burst without directional forced flow
2. low-liquidity symbols where any moderate trade looks like a jump

### Minimal sanity gate
- split by realized vol regime
- exclude session edges and see if mechanism remains
- adjacent thresholds for jump definition should keep direction stable
