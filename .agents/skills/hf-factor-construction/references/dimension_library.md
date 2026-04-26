# Dimension Library — Machine-Readable Working Catalog

## How to use this library

每个维度都不是单独拿来“直接当因子”的，而是用于：

1. 定义 **binary semantic mask**
2. 指定 **continuous carrier**
3. 与其他维度做有单位约束的组合

推荐字段：

- `id`
- `family`
- `algebraic_type`
- `time_axis`
- `granularity`
- `input_columns`
- `definition`
- `continuous_carrier`
- `adaptive_threshold`
- `recommended_pairings`
- `forbidden_pairings`
- `observability_risk`
- `common_failure_modes`

> 说明：这里的“continuous_carrier”不是唯一答案，而是默认推荐的幅度载体。

---

## 1) Price / Impact family

### `P_dir_tick`
- family: price
- algebraic_type: `C_event`
- time_axis: event or clock
- granularity: tick / trade-aligned
- input_columns: `mid`, `mid_prev`
- definition: `1 if mid_t - mid_{t-1} > 0 else 0`
- continuous_carrier: `abs(mid_t - mid_{t-1})` or signed micro-return
- adaptive_threshold: none required
- recommended_pairings: `V_side`, `V_size_rel`, `OB_skew`
- forbidden_pairings: none
- observability_risk: snapshot-driven mid updates may miss intra-snapshot path
- common_failure_modes: becomes pure volatility proxy if used without side/flow conditioning

### `P_jump_rel`
- family: price
- algebraic_type: `C_event`
- time_axis: clock or event
- granularity: tick / short bar
- input_columns: `mid`, rolling volatility estimator
- definition: `1 if |Δmid| > k * rolling_vol`
- continuous_carrier: `|Δmid| / rolling_vol`
- adaptive_threshold: rolling quantile or rolling robust std
- recommended_pairings: `V_cluster`, `V_side`, `OB_depletion`
- forbidden_pairings: using same future-completed burst label to define current jump regime
- observability_risk: session open / halt reopening / auction prints must be excluded explicitly
- common_failure_modes: structurally dominated by open-close discontinuities

### `P_reversion_after_trade`
- family: price
- algebraic_type: `A_price`
- time_axis: clock
- granularity: trade-to-short-horizon
- input_columns: `trade_price`, `mid_after_h`
- definition: signed reversion after an initiating event, defined only for prediction target or sanity check
- continuous_carrier: signed bps reversion
- adaptive_threshold: N/A
- recommended_pairings: validation only
- forbidden_pairings: **do not use as live feature** for same horizon prediction
- observability_risk: future-dependent by construction
- common_failure_modes: leakage if accidentally used inside the feature window

### `P_spread_widen`
- family: price/structure
- algebraic_type: `A_price`
- time_axis: clock
- granularity: L1/L2 snapshots
- input_columns: `best_bid`, `best_ask`
- definition: `spread_t - spread_{t-1}`
- continuous_carrier: spread change in ticks or bps
- adaptive_threshold: robust z-score or intraday seasonalized threshold
- recommended_pairings: `OB_depletion`, `V_side`, `M_activity_high`
- forbidden_pairings: none
- observability_risk: wide-spread symbols require tick-size normalization
- common_failure_modes: collapses to liquidity regime proxy without flow information

---

## 2) Trade / flow family

### `V_side`
- family: trade
- algebraic_type: `A_qty`
- time_axis: trade event time
- granularity: trade
- input_columns: aggressor side tag or inferred side, `size`
- definition: `1 if buyer-initiated else 0`
- continuous_carrier: signed notional or signed size
- adaptive_threshold: none
- recommended_pairings: almost everything
- forbidden_pairings: using low-quality side inference without recording the inference method
- observability_risk: Lee-Ready / quote rule can be wrong at mid or stale quote states
- common_failure_modes: just re-labels general market trend when not normalized

### `V_size_rel`
- family: trade
- algebraic_type: `C_event`
- time_axis: trade event time
- granularity: trade
- input_columns: `size`, rolling size baseline
- definition: `1 if size > rolling q70/q80 or size / seasonal_baseline > k`
- continuous_carrier: `size / seasonal_baseline`
- adaptive_threshold: rolling quantile by symbol × session bucket
- recommended_pairings: `V_side`, `P_dir_tick`, `OB_skew`
- forbidden_pairings: fixed absolute thresholds across symbols
- observability_risk: lot size / contract multiplier heterogeneity
- common_failure_modes: becomes liquidity proxy if not normalized by ADV or local baseline

### `V_cluster`
- family: trade
- algebraic_type: `C_event`
- time_axis: event or clock
- granularity: trade bursts
- input_columns: timestamps or arrivals, rolling event-rate baseline
- definition: `1 if local arrival rate > rolling baseline * k`
- continuous_carrier: event intensity excess or Hawkes intensity excess
- adaptive_threshold: rolling baseline rate / seasonal baseline
- recommended_pairings: `P_jump_rel`, `V_side`, `OB_depletion`
- forbidden_pairings: defining the current cluster using future events in the same burst
- observability_risk: depends on time-axis choice; event-time and clock-time are not interchangeable
- common_failure_modes: pure activity indicator without directional/structural conditioning

### `V_imbalance_trade`
- family: trade
- algebraic_type: `A_qty`
- time_axis: clock or event bucket
- granularity: aggregated trade bucket
- input_columns: signed size or signed notional
- definition: `buy_qty - sell_qty` over a micro-window
- continuous_carrier: signed imbalance itself
- adaptive_threshold: optional robust z-score after seasonality removal
- recommended_pairings: `M_activity_high`, `OB_skew`, `P_jump_rel`
- forbidden_pairings: none
- observability_risk: side classification quality drives everything
- common_failure_modes: mirrors short-term return without adding new information

---

## 3) Orderbook family

### `OB_skew`
- family: orderbook
- algebraic_type: `A_qty`
- time_axis: snapshot clock or event time
- granularity: L2/L3
- input_columns: bid depth ladder, ask depth ladder
- definition: depth imbalance over chosen levels, e.g. `(bid_depth - ask_depth)/(bid_depth + ask_depth)`
- continuous_carrier: imbalance ratio
- adaptive_threshold: seasonalized or rolling quantile threshold for “extreme skew” mask
- recommended_pairings: `V_side`, `V_cluster`, `P_jump_rel`
- forbidden_pairings: mixing different ladder depths without documentation
- observability_risk: snapshot frequency can miss fast queue depletion; iceberg not observed
- common_failure_modes: acts as maker risk appetite proxy only

### `OB_depletion`
- family: orderbook
- algebraic_type: `A_rate`
- time_axis: clock
- granularity: L2/L3 snapshots
- input_columns: queue depth at best/near-touch levels
- definition: negative rate of queue size change on one side
- continuous_carrier: depletion speed in shares/sec or notional/sec
- adaptive_threshold: compare to rolling depletion baseline
- recommended_pairings: `V_side`, `P_jump_rel`, `P_spread_widen`
- forbidden_pairings: using raw snapshot delta without documenting snapshot interval
- observability_risk: replace vs cancel ambiguity; missed within-snapshot cancellations
- common_failure_modes: artifact of feed sampling interval changes

### `OB_wall`
- family: orderbook
- algebraic_type: `C_state`
- time_axis: snapshot clock
- granularity: L2/L3
- input_columns: ladder sizes by level
- definition: `1 if local depth concentration exceeds threshold at one price band`
- continuous_carrier: wall size / local average depth
- adaptive_threshold: level-wise percentile by symbol/session
- recommended_pairings: `V_side`, `P_dir_tick`
- forbidden_pairings: using stale walls that vanished before action time
- observability_risk: spoofing / fleeting liquidity
- common_failure_modes: false positives from display-only liquidity

### `OB_tightness`
- family: orderbook
- algebraic_type: `A_price`
- time_axis: clock
- granularity: L1
- input_columns: `best_bid`, `best_ask`
- definition: inverse spread or negative normalized spread
- continuous_carrier: tightness metric itself
- adaptive_threshold: intraday seasonal adjustment essential
- recommended_pairings: `V_cluster`, `M_activity_high`
- forbidden_pairings: none
- observability_risk: tick-size floor causes discretization
- common_failure_modes: becomes spread proxy with no edge beyond transaction cost state

---

## 4) Regime family

### `M_activity_high`
- family: regime
- algebraic_type: `C_state`
- time_axis: clock
- granularity: short bucket
- input_columns: event count / volume / notional baseline
- definition: `1 if activity > seasonal baseline * k`
- continuous_carrier: relative activity
- adaptive_threshold: yes, by session bucket
- recommended_pairings: almost all microstructure factors
- forbidden_pairings: fixed thresholds across sessions
- observability_risk: lunch break / open / close distortions
- common_failure_modes: if factor only works here, maybe it is just activity itself

### `M_vol_high`
- family: regime
- algebraic_type: `C_state`
- time_axis: clock
- granularity: short bucket
- input_columns: short-horizon realized vol or microprice variance
- definition: `1 if realized vol exceeds rolling/seasonal threshold`
- continuous_carrier: volatility z-score
- adaptive_threshold: yes
- recommended_pairings: `P_jump_rel`, `OB_depletion`, `V_cluster`
- forbidden_pairings: same measure also serving as target without separation
- observability_risk: estimator choice matters heavily at high frequency
- common_failure_modes: factor is nothing but high-vol regime exposure

### `M_session_edge`
- family: regime
- algebraic_type: `C_state`
- time_axis: clock
- granularity: session bucket
- input_columns: exchange-local timestamp
- definition: `1` in explicitly defined open/close/auction/pre-funding windows
- continuous_carrier: N/A
- adaptive_threshold: not applicable
- recommended_pairings: as control or falsification split
- forbidden_pairings: treating session effect as alpha without mechanism
- observability_risk: timezone / DST / maintenance windows
- common_failure_modes: alpha disappears outside a single session slice

---

## 5) Maker / toxicity family

### `T_trade_count_high`
- family: toxicity
- algebraic_type: `C_state`
- time_axis: clock or event bucket
- granularity: short bucket
- input_columns: trade count, seasonal baseline
- definition: `1 if trade_count > rolling or seasonal threshold`
- continuous_carrier: trade_count / baseline
- adaptive_threshold: required
- recommended_pairings: `OB_depletion`, `P_jump_rel`, `V_side`
- forbidden_pairings: fixed count threshold across symbols/venues
- observability_risk: sensitive to tape fragmentation and aggregation rules
- common_failure_modes: just an activity proxy unless tied to adverse selection logic

### `T_post_fill_adverse_flow`
- family: toxicity
- algebraic_type: `A_rate`
- time_axis: clock
- granularity: post-fill snapshot stream
- input_columns: bid depth change, ask depth change, trade flow after fill
- definition: adverse-flow score after a maker fill, e.g. ask retreat < bid depletion or sell pressure persists
- continuous_carrier: adverse-flow score
- adaptive_threshold: compare to post-fill baseline by venue / symbol
- recommended_pairings: maker gating only
- forbidden_pairings: pre-trade alpha use without conditioning on fill state
- observability_risk: depends on fill-conditioned state, snapshot latency, and queue invisibility
- common_failure_modes: collapses if fill timestamps are noisy or if snapshots are too sparse

---

## Pairing heuristics

### Good pairings
- `V_side` + `V_size_rel` + `P_dir_tick`
- `P_jump_rel` + `V_cluster` + `OB_depletion`
- `OB_skew` + `V_imbalance_trade` + `M_activity_high`
- `T_trade_count_high` + `OB_depletion` + `P_spread_widen`

### Bad / risky pairings
- `P_jump_rel` + `M_vol_high` without any flow variable
- `V_cluster` + `M_activity_high` without directional or structural variable
- Any pair that uses the same noisy input twice and then interprets agreement as confirmation

---

## Custom dimension template

```yaml
id: custom_dimension_id
family: trade / orderbook / price / regime / toxicity
algebraic_type: A_qty | A_rate | A_price | C_state | C_event
time_axis: clock | event | volume | dollar | trade_count
granularity: trade | snapshot | bar | bucket
input_columns:
  - ...
definition: >
  Binary mask definition (historical-only, real-time computable).
continuous_carrier: >
  Recommended magnitude variable used after mask filtering.
adaptive_threshold: >
  Rolling quantile / seasonal baseline / robust z-score / none.
recommended_pairings:
  - ...
forbidden_pairings:
  - ...
observability_risk:
  - ...
common_failure_modes:
  - ...
notes: >
  Unit conventions, venue caveats, and preprocessing assumptions.
```
