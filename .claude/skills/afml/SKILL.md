---
name: afml
description: Industrial-grade workflow for developing, testing, and verifying financial ML strategies based on "Advances in Financial Machine Learning" (AFML) and "Machine Learning for Asset Managers" (MLAM) by Marcos López de Prado. Use when: (1) Building Dollar/Volume/Imbalance bars, (2) Triple-barrier or meta-labeling, (3) Sample weights and uniqueness, (4) Purged/embargoed cross-validation, (5) Feature importance (MDI/MDA/Clustered MDA), (6) Trend scanning, (7) Backtest verification (DSR/PSR/CPCV), (8) HRP portfolios, (9) Fractional differentiation, (10) CUSUM filtering, (11) Market microstructure analysis. Includes causal verification framework with validation metrics and book references. For code-level implementation, see afmlkit skill.
---

# Advances in Financial Machine Learning

Industrial-grade workflow for quantitative finance strategy development.

---

## Primary Model Factory (AL9999)

**定位**: 参数搜索工厂，批量枚举 CUSUM rate × MA 窗口 × vertical barrier，用 rate-normalized 综合评分选出最优配置。

**两阶段流程**:

```
Step 0: CUSUM calibration (二分搜索 k 值)
Step 1a: 参数网格 → 90 组有效组合
Step 1b: 轻量扫描 (Recall/CPR/Coverage/Lift) → Top-20
Step 2:  深评 (Uniqueness/Turnover/Regime/OOS) → 综合评分
Step 3:  分层约束（每个 rate 至少 1 个）→ Top-5+ candidates
```

**评分公式**:

```
EffectiveRecall = Recall × Lift
z = 1.0 - (rank - 1) / (n_rate - 1)   # rank percentile z (rate 内)
Score = 0.45·EffectiveRecall_rate_z - 0.10·Turnover_z + 0.10·Uniqueness_z
```

**Lift 定义**: `base_rate = max(n_positive, n_negative) / len(trend_events)`（始终预测多数类的准确率），`Lift = CPR / base_rate`

**核心模块**: `strategies/AL9999/primary_factory/`
- `cusum_calibrator.py` - rate→k 二分搜索校准
- `param_grid.py` - 参数网格生成
- `lightweight_scorer.py` - Recall/CPR/Lift 轻量评分
- `deep_scorer.py` - Uniqueness/Turnover/Regime/OOS/avg_inter_event_time
- `scorer.py` - rate-normalized 综合评分
- `runner.py` - 主流程编排（含分层约束）

**设计文档**: `docs/superpowers/specs/2026-04-06-al9999-primary-factory-design.md`
**测试**: 19 tests，全部通过
**运行**: 见 `strategies/AL9999/run_workflow.py` 或 `runner.py` 中的 `run_primary_factory()`

---

## Core Philosophy

1.  **Stationarity is Non-Negotiable**: Financial data must be stationary (memory-preserving FracDiff) before any modeling.
2.  **No Peeking**: Strict prevention of look-ahead bias through Purged K-Fold Cross-Validation.
3.  **Honest Backtesting**: Use Deflated Sharpe Ratio (DSR) to account for multiple testing and selection bias.
4.  **Meta-Labeling**: Separate the decision of "side" (long/short) from "size" (bet sizing).

---

# Part I: Causal Verification Framework

> **终极验证框架：因果链 + 问题 + 验证指标**
>
> 每一步都按照**因果关系**串联：前一步如何影响后一步。这是开发量化策略的"超级检查清单"。

---

## 一、数据采样层（核心：消除时间扭曲与捕捉突变）

### 因果逻辑

> 传统的按时间采样（Time Bars）会导致高频交易时段和低频时段的信息量严重不均。
> **如果源头数据就是被扭曲的，后面所有的机器学习模型都会学到错误的规律。**

---

### 1. Dollar Bars / Imbalance Bars

**目标**：消除时间的非均匀性，捕捉买卖力量失衡触发的"信息事件"

**验证指标**：

| 指标 | 目标 | 说明 |
|------|------|------|
| Jarque-Bera (JB) 检验 | 正态性提升 | 越接近正态越好 |
| 自相关函数 (ACF) | 低自相关 | AC1 ≈ 0 最优 |
| Ljung-Box | 无序列相关 | p > 0.05 |
| Hurst Exponent | 接近 0.5 | 随机游走 |

**核心逻辑**：

```
时间 bars → clustering（聚集）
Dollar bars → 信息均匀 → 更接近白噪声
```

**最佳实践**：
- **Independence First**: 优先考虑低自相关，而非 JB 绝对值
- **Sample Size Sensitivity**: JB 统计量随 N 增大，高频数据高 JB 正常
- **Optimal Frequency**: 高交易量资产约 20-50 bars/day

---

### Bar 类型验证的三刀法则

> **核心目标**：将混乱的金融数据转化为机器学习可消化的"高斯过程"（I.I.D. + Normal）
>
> 通过三刀验证，系统性地检测 Bar 类型是否满足机器学习的基本假设。

---

#### 第一刀：探测"独立性"（Independence）——聆听切断历史的回声

**猎器**：序列相关性检验（Serial Correlation Test）

真正的独立，意味着每一个市场事件的生与灭，都不会在下一个事件中留下残影。时间条形往往会把一个完整的交易行为生硬劈开，导致前一秒的波动幽灵般地附体在后一秒上。

**操作模式**：
- 计算收益率序列的自相关系数（特别是评估不同条形数据的一阶序列相关性）
- 寻找这种暗流连接

**启示火花**：
- 当序列相关系数无限逼近于零时，意味着我们成功斩断了时间的残影
- 数据从连绵不绝的泥潭中挣脱，化作了一颗颗各自封装完整信息、互不干涉的独立盲盒

**验证指标**：
| 指标 | 目标 | 方法 |
|------|------|------|
| AC1 (一阶自相关) | ≈ 0 | `np.corrcoef(returns[:-1], returns[1:])` |
| Ljung-Box Q | p > 0.05 | `statsmodels.stats.diagnostic.acorr_ljungbox` |
| ACF 图 | 快速衰减至 0 | `statsmodels.graphics.tsaplots.plot_acf` |

---

#### 第二刀：探测"同分布"（Identically Distributed）——丈量恒定的能量场

**猎器**：子集方差的方差检验（Variance of Variances / Heteroscedasticity Test）

市场有时狂风暴雨，有时死水微澜。如果数据不是从同一个能量池中抽取出来的，它就患上了"异方差性（Heteroscedasticity）"的疾病。同分布的本质，是要求数据在宏观的长河中，展现出均匀的呼吸频率。

**操作模式**：
- 将漫长的数据序列按月强行切分为多个时间子集
- 分别计算出每一个月内收益率的方差
- 将这群方差作为新的猎物，计算"这些方差的方差"

**启示火花**：
- 这是一个极其精妙的二阶透视
- 如果方差的方差极小，甚至向零坍缩，它向我们揭示了一个惊人的事实：无论外界环境如何剧变，我们提取特征的容器（如美元条形）已经在内部抹平了波动的潮汐，提取出了最为纯粹、方差恒定的同质化样本

**验证指标**：
| 指标 | 目标 | 方法 |
|------|------|------|
| 方差的方差 (VoV) | 极小 → 0 | 按月分组 → 计算 `var(monthly_vars)` |
| 异方差检验 | p > 0.05 | `statsmodels.stats.diagnostic.het_goldfeldquandt` |
| 波动率稳定性 | 恒定 | 可视化月度波动率序列 |

**实现示例**：
```python
# 计算子集方差的方差
import pandas as pd

# 按月切分
returns_monthly = returns.groupby(returns.index.to_period('M'))
monthly_vars = returns_monthly.var()
vov = monthly_vars.var()  # 方差的方差 → 目标: 趋近于 0
```

---

#### 第三刀：探测"正态性"（Normality）——凝视高斯的完美钟罩

**猎器**：雅克-贝拉检验（Jarque-Bera Test）

当数据既独立又同源之后，我们终于可以直视它的终极形态。金融噪音天生带有狰狞的面目——极端的暴涨暴跌构成了厚重的"胖尾"，而行情的僵持又造就了突兀的"尖峰"。

**操作模式**：
- 将收益率序列喂入 Jarque-Bera 正态性检验中
- 这套检验的眼睛极其锐利，它不看均值，也不看方差，而是直击数据的骨相：偏度（Skewness，面部是否扭曲歪斜）和峰度（Kurtosis，尾部是否暗藏杀机）

**启示火花**：
- 检验会返回一个统计量（Test Statistic）
- 当我们在时间条形、成交量条形和美元条形中不断对比，寻找那个取得最低 Jarque-Bera 检验统计量的序列时，我们就是在见证奇迹的发生——那是狂暴的金融混沌褪去血肉，精准地向理想中的高斯（正态）钟形曲线靠拢的瞬间

**验证指标**：
| 指标 | 目标 | 方法 |
|------|------|------|
| JB 统计量 | 最低 | `scipy.stats.jarque_bera` |
| 偏度 (Skewness) | ≈ 0 | `scipy.stats.skew` |
| 峰度 (Kurtosis) | ≈ 3 (正态) | `scipy.stats.kurtosis`（Fisher 定义） |
| Shapiro-Wilk | p > 0.05 | 小样本补充检验 |

**注意事项**：
- JB 统计量随样本量 N 增大而增大，高频数据高 JB 属正常
- **对比原则**：比较不同 Bar 类型的 JB 值，选择最低者

---

#### 三刀汇流：I.I.D. Normal 的终极验证

```
┌─────────────────────────────────────────────────────────┐
│                    三刀验证法则                           │
├─────────────────────────────────────────────────────────┤
│  第一刀：独立性 (I)    →  AC1 ≈ 0, Ljung-Box p > 0.05   │
│  第二刀：同分布 (ID)   →  VoV → 0, 异方差 p > 0.05      │
│  第三刀：正态性 (N)    →  JB 最低, Skew≈0, Kurt≈3       │
├─────────────────────────────────────────────────────────┤
│  汇流：I + ID + N → 高斯过程 → ML 模型可完美消化        │
└─────────────────────────────────────────────────────────┘
```

**只有当**：
- 序列相关性被降至最低（I）
- 方差的方差被极限压缩（ID）
- 雅克-贝拉统计量跌入谷底（N）

**这三条路径才会在深渊的上方交汇**。在那一刻，晦涩的金融市场噪音，终于化作了任何经典机器学习模型都能完美消化的极高斯过程。

---

### Bar 类型选择决策树

```python
# Bar 类型验证流程
def validate_bar_type(returns, bar_name):
    """三刀验证 Bar 类型质量"""
    results = {}

    # 第一刀：独立性
    ac1 = np.corrcoef(returns[:-1], returns[1:])[0, 1]
    lb_result = acorr_ljungbox(returns, lags=[10], return_df=True)
    results['independence'] = {
        'AC1': ac1,
        'Ljung-Box p': lb_result['lb_pvalue'].values[0],
        'pass': abs(ac1) < 0.05 and lb_result['lb_pvalue'].values[0] > 0.05
    }

    # 第二刀：同分布
    monthly_vars = returns.groupby(returns.index.to_period('M')).var()
    vov = monthly_vars.var()
    results['identically_distributed'] = {
        'VoV': vov,
        'pass': vov < monthly_vars.mean() * 0.1  # VoV < 均值的10%
    }

    # 第三刀：正态性
    jb_stat, jb_p = jarque_bera(returns)
    skew = skew(returns)
    kurt = kurtosis(returns)
    results['normality'] = {
        'JB': jb_stat,
        'JB p': jb_p,
        'Skew': skew,
        'Kurt': kurt,
        'pass': jb_p > 0.05 or abs(skew) < 0.5 and abs(kurt - 3) < 1
    }

    results['overall_pass'] = all([
        results['independence']['pass'],
        results['identically_distributed']['pass'],
        results['normality']['pass']
    ])

    return results
```

**优先级排序**：
1. **独立性优先**：AC1 ≈ 0 是最关键指标
2. **同分布次之**：VoV 控制模型稳定性
3. **正态性参考**：JB 用于对比不同 Bar 类型

---

### Bar 参数优化：加权评分法

> **核心问题**：如何选择最优的 TARGET_DAILY_BARS 参数？
>
> **解决方案**：按 AFML 优先级设计加权评分，自动选出最优参数。

#### 权重分配（AFML 优先级）

| 维度 | 权重 | 指标 | 归一化方法 |
|------|------|------|-----------|
| **第一刀（独立性）** | **50%** | AC1 (35%) | `min(abs(AC1) / 0.10, 1)` (effect-size) |
| | | Multi-ACF Σ|ρ_k| (15%) | `Σ_{k=1..10} |ρ_k| / 0.50` (累积相关强度) |
| **第二刀（同分布）** | **25%** | VoV ratio | `min(VoV / 0.1, 1)` |
| **第三刀（正态性）** | **10%** | JB (10%) | `log10(JB) / 9` |
| | | Skew (5%) | `min(abs(Skew) / 2, 1)` |
| | | Kurt (5%) | `min(abs(Kurt - 3) / 47, 1)` |
| **第四刀（交易密度）** | **15%** | bars/day 偏离 | `<15` 阶梯惩罚: 15→0, 10→0.3, 5→0.7, <5→1.0 |

#### 加权评分公式（v2：统计显著性 + 可交易性）

> **核心改进**：`Ljung-Box p-value` 在大样本（N>10000）下被样本量主导，不再使用硬阈值。
> 改为 effect-size 驱动的独立性 + 多阶相关强度 + 交易密度惩罚。

```python
def _compute_multi_acf_score(returns, max_lag=10):
    """多阶相关强度: Σ_{k=1..max_lag} |ρ_k|"""
    from statsmodels.tsa.stattools import acf
    acf_vals = acf(returns, nlags=max_lag, fft=True)
    return float(np.sum(np.abs(acf_vals[1:])))  # 排除 lag 0

def compute_weighted_score(
    ac1, multi_acf_sum, vov_ratio,
    jb_stat, skew, kurt,
    actual_bars_per_day,
):
    """
    计算加权评分（越低越好）。

    权重：独立性 50% (AC1 35% + Multi-ACF 15%) + 同分布 25%
           + 正态性 10% + 交易密度 15%
    """
    # 1. independence_effect (50%)
    ac1_score = min(abs(ac1) / 0.10, 1.0)
    multi_acf_s = min(multi_acf_sum / 0.50, 1.0)
    independence = 0.35 * ac1_score + 0.15 * multi_acf_s

    # 2. distribution_stability (25%)
    vov_score = min(vov_ratio / 0.1, 1.0) if not np.isnan(vov_ratio) else 1.0
    identically_dist = 0.25 * vov_score

    # 3. normality (10%)
    jb_score = min(np.log10(max(jb_stat, 1)) / 9, 1.0)
    skew_score = min(abs(skew) / 2, 1.0)
    kurt_score = min(abs(kurt - 3) / 47, 1.0)
    normality = 0.10 * jb_score + 0.05 * skew_score + 0.05 * kurt_score

    # 4. trading_density (15%) — 新增
    min_bpd = 15  # AFML 推荐 20-50 bars/day, 15 为最低可交易阈值
    if actual_bars_per_day >= min_bpd:
        density_penalty = 0.0
    elif actual_bars_per_day >= 10:
        density_penalty = 0.3 * (min_bpd - actual_bars_per_day) / (min_bpd - 10)
    elif actual_bars_per_day >= 5:
        density_penalty = 0.3 + 0.4 * (10 - actual_bars_per_day) / 5
    else:
        density_penalty = 0.7 + 0.3 * (5 - actual_bars_per_day) / 5
    density_penalty = min(max(density_penalty, 0.0), 1.0)
    trading_density = 0.15 * density_penalty

    return independence + identically_dist + normality + trading_density
```

#### 实测案例：AL9999 铝期货（2020-04-02, 679K 条分钟线）

| Target | 日均 | AC1 | Multi_ACF | 密度惩罚 | **加权评分** |
|--------|------|-----|-----------|---------|-------------|
| 4 | 4.0 | 0.009 | 0.135 | 0.76 | 0.251 |
| 6 | 6.0 | -0.017 | 0.123 | 0.62 | 0.293 |
| 8 | 8.0 | 0.007 | 0.097 | 0.46 | 0.223 |
| 10 | 10.1 | 0.010 | 0.104 | 0.30 | 0.223 |
| 12 | 12.1 | 0.018 | 0.103 | 0.18 | 0.238 |
| **15** | **15.1** | **-0.001** | **0.089** | **0.00** | **0.160** ✅ |
| 20 | 20.1 | -0.020 | 0.108 | 0.00 | 0.251 |
| 30 | 30.2 | -0.018 | 0.109 | 0.00 | 0.263 |

**最优参数**：TARGET_DAILY_BARS = 15（加权评分最低 0.160，AC1 接近 0 + 信号量充足）

**为什么 T=4 不再是最佳**：旧版评分被 `Ljung-Box p=0.039` 误导（样本量导致的伪显著），新评分用 AC1 effect-size + 交易密度替代后，T=4 因信号密度惩罚（0.76）大幅下降排名。

#### 为什么独立性权重最高？

1. **因果链起点**：如果数据不独立，后续所有 ML 模型都会学到伪相关
2. **Effect-size 优于统计显著性**：`Ljung-Box p-value` 在 N>10000 时被样本量主导，`|AC1|` 和 `Σ|ρ_k|` 直接度量相关性强度
3. **Multi-ACF 补充单阶盲区**：单看 AC1 可能漏掉多阶累计相关模式
4. **信息泄露风险**：高自相关意味着当前数据包含未来信息

#### ⚠️ LB p-value 的陷阱（已修复）

> `Ljung-Box Q/N` 的 p-value 检验统计显著性，但在大样本下 **微小的 AC1 也会被 p 值放大为"显著"**。
> 例如 AC1=0.02 在 N=50000 时 p<1e-12，但经济意义上几乎无影响。
> 因此新版评分用 effect-size（AC1 + Multi-ACF）替代 p-value，交易密度取代"越稀疏越好"的偏见。

#### 自动化最佳实践

```python
# 参数优化脚本应自动：
# 1. 测试多个 TARGET_DAILY_BARS 值
# 2. 计算加权评分
# 3. 保存最优参数的 Dollar Bars
# 4. 更新配置文件

target_range = [4, 6, 8, 10, 12, 15, 20, 25, 30]
results = [evaluate_target_bars(df, t) for t in target_range]
best_target = min(results, key=lambda x: x['weighted_score'])['target_bars']
```

---

### 2. Event-Based Sampling (CUSUM Filter)

**目标**：市场并非一直在提供有用信息。CUSUM 用于检测累计偏离目标的结构性突变，只有当市场真正发生"异动"时才采样

**验证指标**：

| 指标 | 目标 |
|------|------|
| 过滤后样本波动率 | 更加平稳 |
| 事件触发频率 | 合理（非过度密集/稀疏） |

---

## 二、标签层（核心：定义真实可交易的事件）

### 因果逻辑

> 如果强行规定"3天后卖出"，这打破了市场自我演化的因果性。
> **我们需要让数据自己告诉我们"趋势何时结束"。**

---

### 3. Triple Barrier Method (TBM)

**目标**：结合动态止盈、止损和最大持仓时间，让标签反映真实的路径依赖交易结果

**验证指标**：

| 指标 | 目标 |
|------|------|
| 标签分布（±1 / 0） | 是否均衡 |
| 每类样本数量 | 避免极端不平衡 |
| 平均持仓时间 | 合理性检查 |
| Hit Ratio | 统计显著性 |
| Payoff Asymmetry | 风险收益比 |

**配置**：
- Upper barrier（止盈）
- Lower barrier（止损）
- Vertical barrier（时间到期）

---

### 4. Trend Scanning

**目标**：放弃固定时间墙，通过在不同时间窗口内寻找最大 t-value，找出最显著的趋势段

**验证指标**：

| 指标 | 说明 |
|------|------|
| t-value 最大化 | 选择最显著窗口 |
| trend duration 分布 | 趋势长度分布 |
| label stability | 标签稳定性 |

**优势**：
- 无超参数敏感性：自动选择最优窗口
- 白盒逻辑：纯 OLS，完全可解释
- 双输出：side + confidence

---

### 5. Meta-labeling

**目标**：主模型找方向（买/卖），元模型决定是否下注（头寸大小）。将"寻找机会"和"过滤风险"解耦

**验证指标**：

| 指标 | 目标 | 说明 |
|------|------|------|
| Precision | ↑ | 精确率提升 |
| Recall | 略降但不能崩 | 召回率保持 |
| F1-score | ↑ | **金融数据极度不平衡，Accuracy 会骗人，F1 才能真实反映模型找准机会的能力** |
| 策略 Sharpe | ↑ | 风险调整收益 |
| 最大回撤 | ↓ | 风险控制 |

**本质**：

```
primary：找机会
meta：筛机会
```

---

## 三、特征层（核心：保留记忆与剔除噪音）

### 因果逻辑

> 如果直接用价格，数据不平稳，模型会崩溃；
> 如果用简单收益率，数据失去了所有长期记忆（过去的趋势），模型就变成了瞎猜。
> **同时，多余的噪音特征会引发过拟合。**

---

### 6. Fractional Differentiation (FracDiff)

**目标**：在"平稳性（Stationarity）"和"记忆保留（Memory）"之间找到最佳的因果平衡点 $d^*$

**验证指标**：

| 指标 | 目标 |
|------|------|
| ADF test | p < 0.05（刚好通过 5%） |
| KPSS test | 平稳性确认 |
| 与原序列相关性 | 接近 1（最大化信息保留） |
| 自相关 | 不能完全消失 |

**核心**：

```
一阶差分 ❌（信息丢失）
frac diff ✅（保留 alpha）
```

**执行陷阱**：
- FracDiff 会压缩方差，需注意 CUSUM 阈值的"量纲错位"
- 解决方案：确保 CUSUM 输入与阈值在同一尺度空间

---

### 7. Feature Importance (MDI/MDA)

**目标**：找出真正对预测有因果贡献的特征，剔除伪相关或被替代效应掩盖的噪音特征

> ⚠️ **极易被忽略的致命点**

**验证指标**：

| 指标 | 说明 |
|------|------|
| MDI | 基于树分裂的不纯度下降 |
| MDA | 样本外打乱特征后的准确率下降程度 |
| Clustered MDA | 解决共线性特征的替代效应 |

**为什么不用 Vanilla MDA**：
- 金融特征高度共线性
- Vanilla MDA 存在"替代效应"——重要特征因被替代而得分低

**步骤**：
1. **Feature Clustering**: 距离矩阵 $D = \sqrt{0.5 \times (1 - \rho)}$ → 层次聚类
2. **Clustered MDA**: 对整个 cluster 置换，测量 log-loss 下降

---

### 8. PCA

**目标**：消除金融特征之间极高的共线性

**验证指标**：

| 指标 | 说明 |
|------|------|
| explained variance ratio | 解释方差比例 |
| eigenvalue decay | 特征值衰减率 |
| condition number | 条件数 |

---

## 四、样本权重与数据清洗（核心：打破样本重叠导致的非独立性）

### 因果逻辑

> 如果两个标签对应的时间段重叠了，它们就包含了相同的未来信息（非独立同分布）。
> **如果在交叉验证时不清洗它们，模型就会发生严重的"信息泄露（Data Leakage）"，导致回测完美、实盘破产。**

---

### 9. Label Uniqueness & Sample Weights

**目标**：计算每个样本在时间上的重叠度，重叠越多的样本权重越低，让重要且独立的样本主导训练

**验证指标**：

| 指标 | 目标 |
|------|------|
| Uniqueness $\bar{u}_i$ | ∈ (0, 1) |
| 平均 uniqueness | > 0.5 理想 |
| overlap matrix | 可视化重叠 |

---

### 10. Sequential Bootstrap

**目标**：在随机抽样时，动态降低已抽出重叠样本被再次抽中的概率

**验证指标**：

| 指标 | 目标 |
|------|------|
| Bootstrap 后平均 Uniqueness | 显著提升至 > 原始 avgU |
| 模型稳定性 | ↑ |
| Variance | ↓ |

**实现要点**：

```python
from afmlkit.sampling import sequential_bootstrap_indices, avg_uniqueness_of_sample

# Numba 加速版本 — 首次调用有 JIT 编译开销，后续运行极快
# 当 NUMBA_DISABLE_JIT=1 时自动降级为纯 Python 实现
# _use_numba_jit() 函数根据环境变量自动选择路径
```

**实测结果：AL9999 铝期货 RF Primary Model（2026-04-05）**：

| 指标 | 值 | 说明 |
|------|------|------|
| 原始 avg_uniqueness | 0.4721 | 未重采样前的事件重叠度基准 |
| **SB 采样 avgU (mean)** | **0.700** | 1000 棵子树的平均唯一性 |
| SB 采样 avgU (median) | 0.700 | 分布中心与均值一致 |
| SB 采样 avgU (Q25/Q75) | 0.691 / 0.709 | 分布集中，方差小 |
| **Uplift vs 基线 0.47** | **+0.230** | 信息重叠显著降低 |
| **Gap to target 0.632** | **-0.068** | 超额完成 AFML 推荐目标 |
| max_samples | 0.472 | 由 avgU 自动确定 |

**模型表现对比（Sequential Bootstrap vs 旧 avgU 原生 Bagging）**：

| 指标 | 旧 avgU Bagging | Sequential Bootstrap | 变化 |
|------|-----------------|---------------------|------|
| OOF F1 | 0.541 | 0.554 | +2.3% |
| OOF Log Loss | 0.695 | 0.692 | -0.35% |
| Holdout Log Loss | 0.740 | 0.739 | 持平 |

**经验教训**：

1. **avgU=0.47 不代表采样后也是 0.47** — 原始事件重叠度高时（avgU<0.5），Sequential Bootstrap 可将每棵子树的 avgU 提升至 0.70 以上，大幅减少泄漏
2. **gap_to_target 0.632 为负是好事** — 说明采样质量已超越 AFML 理论推荐的 0.632 目标线
3. **Numba 加速至关重要** — 779 样本 × 15 组超参 × 5 折 CV × 500~1000 棵树 × 每次采样数百步 → 纯 Python 可能数小时，Numba JIT 加速后可在合理时间内完成
4. **OOF F1 提升但 Accuracy 未改善** — SB 主要帮助模型更好地识别少数类（金融数据核心诉求），对整体准确率提升有限
5. **Holdout 差距未显著扩大** — 说明 SB 提升的是泛化力本身，而非单纯过拟合训练集

---

### 11. Purging & Embargo

**目标**：在划分训练集/测试集时，删除与测试集在时间上重叠的训练样本（Purging），并在测试集后留出一段空白期（Embargo）以应对序列相关性

**验证指标**：

| 指标 | 目标 |
|------|------|
| Train/Test Overlap | **严格等于 0** |
| performance drop | 合理下降 |
| out-of-sample 稳定性 | ↑ |

---

## 五、模型层（核心：非线性与集成的力量）

### 因果逻辑

> 金融市场极度复杂且信噪比极低，
> **线性模型无法捕捉非线性交互，而单棵决策树极易过拟合。**

---

### 12. Ensemble Methods (Random Forest / Bagging)

**目标**：通过对特征和样本的随机抽样生成大量弱分类器，再进行投票，大幅降低方差（Variance）

**验证指标**：

| 指标 | 说明 |
|------|------|
| Out-of-Bag (OOB) Error | 袋外误差 |
| Recall | 召回率（关键指标） |
| ROC-AUC | 整体判别能力 |

**执行陷阱**：
- 对于特征重要性，**必须设置 `max_features=1`**
- 避免 dominant features "masking" 弱信号

---

### 13. High Recall Model

**目标**：不错过交易机会（Recall 优先）

**验证指标**：

| 指标 | 目标 |
|------|------|
| Recall | ↑（关键） |
| False Negative | ↓ |
| ROC-AUC | 监控 |
| Precision-Recall curve | 分析 |

---

## 六、策略与回测评估层（核心：防范回测过拟合）

### 因果逻辑

> 只要你尝试的参数组合足够多（Multiple Testing），
> 你总能"偶然"撞上一个夏普比率极高的完美策略。
> **我们必须用统计学把这种水分挤干。**

---

### 14. PSR (Probabilistic Sharpe Ratio)

**目标**：针对收益率的非正态性（负偏度、厚尾）和样本长度进行惩罚，计算真实 Sharpe 大于目标的概率

**验证指标**：

| 指标 | 目标 |
|------|------|
| PSR | **> 95%** |
| 收益偏度 | 输入 |
| 收益峰度 | 输入 |
| 样本长度 | 输入 |

---

### 15. DSR (Deflated Sharpe Ratio)

**目标**：惩罚过度参数寻优。你回测的次数越多，DSR 要求的达标门槛就越高

**验证指标**：

| 指标 | 目标 |
|------|------|
| DSR Probability | **> 95%** |
| 试验次数 | 记录 |
| 收益偏度/峰度 | 输入 |
| 回测长度 | 输入 |

**原则**：拒绝高 Sharpe 但低 DSR 的策略（幸运结果）

---

### 16. CPCV (Combinatorial Purged Cross-Validation)

**目标**：生成多条非重叠的历史演化路径，得出一个"Sharpe Ratio 分布"，而不是单一的虚假点估计

**验证指标**：

| 指标 | 说明 |
|------|------|
| Sharpe 分布均值 | OOS 性能 |
| PBO（回测过拟合概率） | 越低越好 |
| Sharpe 分布方差 | 稳定性 |

---

### 17. 策略综合评估

**目标**：是否真实可交易

**验证指标**：

| 指标 | 说明 |
|------|------|
| Sharpe Ratio | 风险调整收益 |
| Sortino Ratio | 下行风险调整 |
| Maximum Drawdown | 最大回撤 |
| Calmar Ratio | 年化收益/最大回撤 |
| Turnover | 换手率 |
| Capacity | 容量 |

---

# Part II: Workflow Decision Tree

> 操作级别的执行指南

## Phase 1: Data Engineering

**Goal**: Transform raw market data into information-rich, stationary features.

1. **Sampling**:
   * **Check**: Are you using Time Bars?
   * **Action**: If YES -> STOP. Switch to **Dollar Bars** or **Volume Bars**.
   * **Event Trigger**: Apply **CUSUM Filter** to trigger sampling.
   * **Frequency Selection**: Prioritize **Low Autocorrelation** over JB absolute value. Aim for 20-50 bars/day.

2. **Stationarity**:
   * **Check**: Run ADF test. Is p-value < 0.05?
   * **Action**: If NO -> Apply **Fractional Differentiation (FracDiff)**. Find minimum `d` such that p < 0.05 while maximizing memory preservation. *Never use integer differencing (d=1).*
   * **🚨 Pitfall (Variance Collapse)**: FracDiff compresses variance. Ensure CUSUM threshold matches the compressed scale.

## Phase 1.5: Primary Model (Side Determination)

**Goal**: Determine the directional bias (Long/Short) for each CUSUM event using a statistically rigorous, parameter-free method.

1. **Method**: **Trend Scanning** (MLAM Ch.3.5) for label definition.
   * For each event, backward-scan over multiple window lengths.
   * Fit OLS regression in each window, compute t-statistic.
   * Select the window $L^*$ that maximizes $|t_{\text{value}}|$.
   * **Output**: `side = sign(t_value)` (+1 = Long, -1 = Short) and `|t_value|` as confidence score.

2. **Parameter Optimization**: Use **Primary Model Factory** to search optimal configurations.
   * Factory: `strategies/AL9999/primary_factory/`
   * Grid: CUSUM rate × (fast, slow) windows × vertical barrier
   * Scoring: Recall-First with rate-normalized EffectiveRecall
   * See **Primary Model Factory** section above for details.

3. **🚨 Anti-Pattern**: Do NOT use dual moving average crossover in isolation. These exhibit catastrophic parameter fragility without systematic search.

## Phase 2: Labeling & Weighting

**Goal**: Scientifically define "success" and handle data overlap.

1. **Labeling**: Use **Triple-Barrier Method**. Set upper barrier (take profit), lower barrier (stop loss), and vertical barrier (time expiration).

2. **Sample Weights**: Calculate **Average Uniqueness**. Down-weight samples with low uniqueness.

## Phase 3: Modeling & Feature Selection

**Goal**: Train models that generalize, not memorize.

1. **Cross-Validation**: Use **Purged K-Fold CV** with **Embargo** period.

2. **Feature Importance**: Use **Clustered MDA**.
   * **Step 1**: Feature Clustering via distance matrix $D = \sqrt{0.5 \times (1 - \rho)}$
   * **Step 2**: Permute entire clusters, measure log-loss drop
   * **Pitfall**: Force `max_features=1` in tree-based models to avoid masking effects.

## Phase 4: Strategy & Verification

**Goal**: Deploy only strategies that are statistically significant.

1. **Architecture**: **Meta-Labeling**.
   * *Primary Model*: **Trend Scan** — determines side.
   * *Secondary (Meta) Model*: Determines confidence.

2. **Final Acceptance**:
   * **Metric**: **Deflated Sharpe Ratio (DSR)**.
   * **Threshold**: DSR Probability > 0.95.
   * *Reject strategies with high Sharpe but low DSR.*

---

# Part III: Quick Reference

## Bar Types (Chapter 2)

Use information-driven bars instead of time bars:

| Type | Trigger | Use Case |
|------|---------|----------|
| Tick bars | Every N ticks | High-frequency analysis |
| Volume bars | Every N shares | Volume-sensitive strategies |
| Dollar bars | Every $N traded | **Recommended for ML** |
| Imbalance bars | Volume imbalance | Order flow analysis |

## Feature Importance Methods (Chapter 8)

| Method | Source | Use Case |
|--------|--------|----------|
| MDI | In-sample impurity | Fast, biased toward high-cardinality |
| MDA | OOS permutation | Robust, detects generalization |
| SFI | Single-feature CV | Detects substitution effects |

## Hierarchical Risk Parity (Chapter 16)

Portfolio construction without matrix inversion:
1. Hierarchical clustering on correlation
2. Quasi-diagonalization (reorder by cluster)
3. Recursive bisection (inverse-variance weights)

## Best Practices Summary

### Data Preparation
1. Never use time bars—use volume/dollar bars
2. Apply CUSUM filter for sampling
3. Fractionally differentiate to preserve memory

### Modeling
1. Use triple-barrier labeling for path dependency
2. Apply meta-labeling to separate signal from sizing
3. Always purge and embargo cross-validation

### Backtesting
1. Deflate Sharpe ratio for multiple testing
2. Compute PBO to estimate overfitting
3. Validate with synthetic data

---

# Part IV: 实战案例与经验总结

## 案例：棕榈油期货策略优化

**背景**：使用棕榈油期货 1分钟数据（2023-2026），初始策略表现不佳（夏普 0.49，胜率 46.7%，Meta Model 预测力弱）。

### 关键优化措施

#### 1. FracDiff 特征（核心优化）

```python
from afmlkit.feature.core.frac_diff import optimize_d, frac_diff_ffd

# 自动寻优差分阶数（保留90%相关性）
d_opt = optimize_d(close_prices, thres=1e-4, min_corr=0.9)  # 输出: 0.20

# 生成 FracDiff 特征
frac_diff = frac_diff_ffd(close_prices, d=d_opt)
features['frac_diff_close'] = frac_diff
features['frac_diff_ma20'] = frac_diff.rolling(20).mean()
features['frac_diff_std20'] = frac_diff.rolling(20).std()
```

**为什么重要**：分数阶差分在平稳性（ADF p<0.05）和记忆保留（与原序列相关>0.9）间取得平衡，比整数差分（d=1）保留更多信息。

#### 2. TBM 参数调优（关键优化）

```python
# 原始参数（表现不佳）
# min_ret=0.0, barriers=(1.0, 1.0), vertical=2d

# 优化后参数（夏普提升86%）
tbm = TBMLabel(
    features=features,
    target_ret_col='daily_vol_est',
    min_ret=0.001,              # 提高收益门槛，过滤噪音
    horizontal_barriers=(2.0, 2.0),  # 扩大止盈止损距离
    vertical_barrier=pd.Timedelta(days=1),  # 缩短持有期
    is_meta=True,
)
```

**经验**：`min_ret=0` 会产生过多低质量标签，适当提高（0.001-0.002）能显著改善 Meta Model 学习效果。

#### 3. Bet Size 改进（风险管理）

```python
# 原始：仅依赖 Meta Model 概率
# bet_size = 2 * meta_prob - 1

# 改进：结合 Primary Model 置信度
def compute_bet_size(meta_prob, trend_confidence, max_bet=1.0):
    meta_signal = 2 * meta_prob - 1  # [-1, 1]
    conf_normalized = trend_confidence / trend_confidence.max()  # [0, 1]
    return np.clip(meta_signal * conf_normalized, -max_bet, max_bet)

# 使用 Trend Scanning 的 |t_value| 作为置信度
bet_size = compute_bet_size(
    meta_prob=predictions,
    trend_confidence=trend_df['t_value'].abs()
)
```

**经验**：Meta Model 概率分布常过于集中（std~0.01），结合 Primary Model 的置信度能得到更合理的仓位分配。

### 优化成果

| 指标 | 优化前 | 优化后 | 改善 |
|------|--------|--------|------|
| 年化夏普比率 | 0.49 | **0.91** | +86% |
| 最大回撤 | -7.95% | **-5.83%** | +27% |
| 胜率 | 46.7% | **51.1%** | +4.4% |
| 总收益 | 1.25% | **1.89%** | +51% |

### 关键教训

1. **TBM 参数至关重要**：不要接受默认值，系统搜索 `min_ret` 和 `barriers` 能显著提升策略表现
2. **FracDiff 是必需品**：对于非平稳金融时间序列，分数阶差分比整数差分更能保留预测信息
3. **Bet Size 多因子化**：单一依赖 Meta Model 概率过于简单，应整合 Primary Model 置信度、波动率等多维度信息
4. **标签质量 > 模型复杂度**：在改进标签生成（TBM 参数）前，不要盲目增加模型复杂度

---

## 案例：IF9999 Dollar Bars 参数优化

**背景**：沪深300股指期货主力合约（2020-2026），1 分钟数据，构建 Dollar Bars。

### 参数优化流程

1. **测试范围**：TARGET_DAILY_BARS = [4, 6, 8, 10, 12, 15, 20, 25, 30]
2. **评分方法**：加权评分（独立性 50% + 同分布 30% + 正态性 20%）
3. **自动保存**：最优参数的 Dollar Bars 数据

### 优化结果 (v1: 旧版 LB p-value 评分)

| Target | AC1 | JB | Skew | Kurt | **旧评分** | **新评分(v2)** |
|--------|-----|-----|------|------|----------|--------------|
| 4 | -0.018 | 84K | 0.37 | 21.3 | 0.367 | 0.251 |
| 6 | 0.006 | 144K | 0.27 | 22.6 | **0.114** | 0.293 |
| 15 | -0.003 | 3.1M | 0.39 | 60.5 | 0.145 | **0.160** ✅ |
| 30 | -0.007 | 23.4M | 0.51 | 114.7 | 0.178 | 0.263 |

**旧版最优**：TARGET_DAILY_BARS = 6（LB p-value 误导）
**新版(v2)最优**：TARGET_DAILY_BARS = 15（effect-size + 可交易性，信号量 3.7× 提升）

### 关键发现

1. **更少 bars/day ≠ 更好**：虽然 4 bars/day 的 JB 最低，但 AC1 较高且信号密度惩罚大
2. **15 bars/day 最优(v2)**：AC1 ≈ 0 (multi-acf 最低 0.089) + 信号密度达标无惩罚
3. **LB p-value 误导**：旧版被 N>50K 样本量主导，新版用 effect-size 更稳健

### 实现代码

```python
# strategies/AL9999/01_dollar_bar_builder.py

def compute_weighted_score(ac1, multi_acf_sum, vov_ratio, jb_stat, skew, kurt, bars_per_day):
    """v2: effect-size 独立性 + 可交易性，非纯 LB p-value"""
    # 独立性 50%: AC1 35% + Multi-ACF 15%
    ac1_score = min(abs(ac1) / 0.10, 1.0)
    multi_acf_s = min(multi_acf_sum / 0.50, 1.0)
    independence = 0.35 * ac1_score + 0.15 * multi_acf_s

    # 同分布 25%
    vov_score = min(vov_ratio / 0.1, 1.0) if not np.isnan(vov_ratio) else 1.0
    identically_dist = 0.25 * vov_score

    # 正态性 10%
    jb_score = min(np.log10(max(jb_stat, 1)) / 9, 1.0)
    skew_score = min(abs(skew) / 2, 1.0)
    kurt_score = min(abs(kurt - 3) / 47, 1.0)
    normality = 0.10 * jb_score + 0.05 * skew_score + 0.05 * kurt_score

    # 交易密度 15%
    min_bpd = 15
    if bars_per_day >= min_bpd:
        density_penalty = 0.0
    elif bars_per_day >= 10:
        density_penalty = 0.3 * (min_bpd - bars_per_day) / (min_bpd - 10)
    elif bars_per_day >= 5:
        density_penalty = 0.3 + 0.4 * (10 - bars_per_day) / 5
    else:
        density_penalty = 0.7 + 0.3 * max(5 - bars_per_day, 0) / 5
    trading_density = 0.15 * min(max(density_penalty, 0.0), 1.0)

    return independence + identically_dist + normality + trading_density
```

### 教训总结

1. **参数优化必须量化**：主观选择参数容易陷入"越多越好"或"越少越好"的误区
2. **评分权重体现方法论**：AFML 明确指出独立性优先，评分权重应反映这一点
3. **自动化是关键**：每次数据更新后，应重新运行参数优化

---

# References

## Core Documentation

- **[glossary.md](references/glossary.md)** - AFML term definitions (FracDiff, Triple-Barrier, etc.)
- **[implementation_guide.md](references/implementation_guide.md)** - Python code snippets and mlfinlab usage

## By Topic

**Data Structures & Labeling**:
- `references/part_1.md` - Data analysis fundamentals
- `references/3_form_labels_using_the_triple_barrier_method_with_symmetric.md` - Triple barrier implementation
- `references/1_sample_bars_using_the_cusum_filter_where_y_t_are_absolute_returns_and_h_.md` - CUSUM filtering

**Cross-Validation & Feature Importance**:
- `references/5_the_cv_must_be_purged_and_embargoed_for_the_reasons_explained_in.md` - Purged CV
- `references/1_masking_effects_take_place_when_some_features_are_systematically_ignored.md` - Feature masking

**Backtesting**:
- `references/part_3.md` - Backtesting methodology
- `references/part_3_backtesting.md` - Backtesting deep dive
- `references/1_survivorship_bias_using_as_investment_universe_the_current_one_hence.md` - Bias detection
- `references/chapter_15_understanding_strategy_risk.md` - Risk metrics

**High-Performance Computing**:
- `references/1_chapter_20_multiprocessing_and_vectorization.md` - Parallel processing

**Bibliography**:
- `references/index.md` - Complete structure
- `references/9_bibliography.md` - Academic references

## Related Libraries

- **mlfinlab**: Python implementation of book techniques
- **afmlkit**: Project-specific implementation (see project CLAUDE.md)
- **sklearn**: ML algorithms
- **pandas/numpy**: Data structures

---

**Source**: "Advances in Financial Machine Learning" by Marcos López de Prado (Wiley, 2018)