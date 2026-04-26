# Hawkes Process Smoothing — Practical Guide for Factor Research

## When Hawkes is the right tool

用 Hawkes 的前提不是“我想让曲线更平滑”，而是：

1. 原始事件流是**不规则时间间隔**的
2. 时间间隔本身带信息
3. 你希望捕捉**事件簇集 / 自激效应**

如果你的因子已经落在规则 bar 上，且机制不依赖 event clustering，优先用 EMA。

---

## Post-event recursion (recommended for factor smoothing)

这里采用**事件发生后立即更新**的定义。

设 `R_n` 表示在第 `n` 个事件刚发生之后的激发状态，
第 `n` 个事件时间为 `t_n`，权重为 `w_n`。

### Univariate form

```text
R_n = exp(-beta * (t_n - t_{n-1})) * R_{n-1} + alpha * w_n
factor(t_n+) = mu + R_n
```

其中：
- `mu >= 0` 基线水平
- `alpha >= 0` 每个事件的跳跃贡献
- `beta > 0` 衰减率
- `eta = alpha / beta < 1` 为近似单变量分支比条件

### Between-event query

对任意 `t > t_n`：

```text
factor(t) = mu + exp(-beta * (t - t_n)) * R_n
```

### Why this definition

这样第一笔事件会立刻产生跳跃：

```text
R_1 = alpha * w_1
factor(t_1+) = mu + alpha * w_1
```

这比“第一笔事件后仍然等于 mu”的实现更符合平滑器直觉。

---

## Parameterization with units

不要直接写“alpha=0.4, beta=0.8”而不说单位。

更实用的是：
- 指定 `half_life_seconds`
- 指定 `eta`
- 再反推出 `beta, alpha`

### Conversion

```text
beta = ln(2) / half_life_seconds
alpha = eta * beta
```

### Typical half-life ranges

| half-life | use case |
|---|---|
| 0.2s – 1s | ultra-HFT burst detection |
| 1s – 5s | microstructure pressure / toxicity |
| 5s – 30s | short-term order-flow persistence |
| 30s+ | slower intraday event clustering |

### Typical eta ranges

| eta | interpretation |
|---|---|
| 0.1 – 0.3 | weak excitation |
| 0.3 – 0.6 | practical sweet spot |
| 0.6 – 0.8 | strong clustering, use carefully |
| > 0.8 | near-critical, fragile |

---

## When NOT to use Hawkes

- 因子已经是规则 bar 序列
- 你不关心事件簇集，只关心值本身
- 数据只有粗糙 snapshot，簇内动态严重缺失
- 你无法说明参数单位和时间轴

---

## Multivariate Hawkes for factor work

对于多事件类型：

```text
lambda_k(t) = mu_k + Σ_j excitation_{j->k}(t)
```

在实现上更推荐维护一个 `R[j, k]` 状态矩阵：
- 每个事件先让整个矩阵按 `exp(-beta * dt)` 衰减
- 再把当前事件类型 `j` 对各 `k` 的激发加进去
- 当前各类型强度 = `mu + R.sum(axis=0)`

查询时也必须对**整个矩阵**衰减后再汇总，不能只衰减汇总后的向量。

---

## Normalization after Hawkes

Hawkes 输出经常会随市场活跃度改变尺度，因此建议在平滑后再考虑：

1. excess over baseline: `(lambda - mu)`
2. relative excess: `(lambda - mu) / max(mu, eps)`
3. rolling robust z-score
4. rolling percentile rank

---

## Minimal usage notes

- 保证时间戳单调不减
- 明确时间单位（秒 / 毫秒）
- 不要把 event-time 数据拿秒级 half-life 直接套上而不说明换算
- 对第一笔事件要有即时 jump
- 查询时若 `t < last_event_time` 应报错

---

## Suggested preset style

与其写死市场名 preset，不如写成：

```python
params_from_half_life(mu=0.0, half_life_seconds=2.0, eta=0.4)
```

或者保存为：

```python
{
  "maker_toxicity_short": {
    "mu": 0.0,
    "half_life_seconds": 1.5,
    "eta": 0.35,
    "time_unit": "seconds"
  }
}
```

这样迁移到别的市场时不容易误用。
