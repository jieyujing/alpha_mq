# 截面因子过滤责任链设计

**日期**: 2026-04-28
**状态**: 设计已批准，待实施

## 动机

当前 `factor_filtering` 流水线是"指标收集器"而非真正的"筛选"流水线：
- 每个 step 的 `process()` 都是透传 `return df`
- 没有任何阶段执行因子剔除
- 报告列出全部 158 个因子，没有输出筛选后的因子池

截面因子筛选应从"特征重要性中心"改为"横截面排序能力中心"。

## 架构概览

```
alpha158_pool.parquet
  → [Ring 0] DataAndLabelQA (卫生检查)
  → [Ring 1] PreprocessAndNeutralize (去极值/标准化/方向统一/中性化)
  → [Ring 2] SingleFactorProfiler (单因子画像)
  → [Ring 3] CrossSectionFilter (有效性筛选)
  → [Ring 4] StabilityChecker (稳定性分层)
  → [Ring 5] FactorClustering (因子收益相关性聚类)
  → [Ring 6] RepresentativeSelector (簇内代表选择)
  → [Ring 7] PortfolioValidator (组合验证)
  → [Ring 8] MLImportanceVerifier (模型增量确认)
  → 输出: report.md + factor_pool_filtered.parquet + selection_log.json
```

责任链机制：每个 step 的 `process(df)` 返回 `(处理后的 DataFrame, 指标字典)`，前一步输出传给下一步。Ring 3 之后 DataFrame 列真实减少。

## 目标市场与配置

- **截面类型**: A 股股票（行业中性、市值中性）
- **默认 label**: `label_20d`，配置可切换其他 label
- **聚类方式**: 因子收益序列相关性（非因子值相关性）
- **筛选阈值**: 宽松（abs(IC)>0.01, coverage>0.60）
- **中性化 v1**: 仅 winsorize + z-score + 方向统一（不需外部数据）
- **中性化 v2（可选）**: 关联 fundamentals 数据做市值/行业正交化

## Ring 0: 数据与标签卫生检查

| 检查项 | 动作 |
|--------|------|
| inf/-inf | → null |
| 缺失率 | 按因子列计算 null 占比，标记覆盖率 < 50% |
| 常数/低方差 | 截面标准差 < 1e-8 标记 |
| 截面覆盖率 | 每天有多少 asset 参与排序 |
| 标签分布 | label 均值/分位数/异常值检查 |
| 标签错位 | label_1d ≈ close[t+1]/close[t] - 1 |

配置参数: `min_coverage=0.5`, `variance_threshold=1e-8`

## Ring 1: 因子预处理与中性化

| 步骤 | 方法 |
|------|------|
| Winsorize | 截面 1%/99% 分位截断 |
| 缺失处理 | 截面中位数填充 |
| 标准化 | rank_pct (映射到 [-1,1]) |
| 方向统一 | 确保正 IC = "因子值高 → 收益高" |
| 中性化(v2可选) | 对 log(market_cap) + 行业 dummy 正交化 |

配置参数: `winsorize_lower=0.01`, `winsorize_upper=0.99`, `transform_method="rank_pct"`

## Ring 2: 单因子横截面画像

按 datetime 分组计算每日 IC，聚合为：

| 指标 | 含义 |
|------|------|
| mean_rank_ic | IC 均值 |
| icir | IC均值/IC标准差 |
| ic_t_stat | t 检验统计量 |
| ic_win_rate | IC>0 的比例 |
| group_returns | Q1~Q5 分组收益 |
| long_short_return | Q5 - Q1 多空收益 |
| monotonicity | 分组收益单调性（Spearman rank corr） |
| turnover | 因子排名自相关（1 - rank_corr(t,t-1)） |
| coverage | 每日非 null 资产占比均值 |
| ic_decay | 对多周期 label 分别计算 IC |

## Ring 3: 横截面有效性筛选

| 阈值 | 默认值 | 说明 |
|------|--------|------|
| abs(mean_rank_ic) | > 0.01 | 宽松阈值 |
| coverage | > 0.60 | 60% 截面覆盖率 |

**关键行为**: 首次 drop DataFrame 列。输出 `rejected` 字典记录剔除原因。

## Ring 4: 稳定性与状态分层

| 维度 | 方法 |
|------|------|
| 年度 IC | 每年单独算 mean IC |
| 滚动 IC | 60 日滚动 IC 序列 |
| 分期对比 | 训练(2020-2022) vs 验证(2023) vs 测试(2024) |
| 市值分层 | 大/中/小盘按 instrument 排名分位 |
| 输出 | 综合稳定性得分 |

## Ring 5: 相关结构聚类

| 步骤 | 方法 |
|------|------|
| 因子收益序列 | `factor_return_t = mean(signal_t * label_t)` 即每日 IC 序列 |
| 相关性 | Pearson 相关矩阵（因子收益 × 因子收益） |
| 距离 | d = sqrt(0.5 * (1 - corr)) |
| 聚类 | AgglomerativeClustering, complete linkage, threshold=0.5 |

## Ring 6: 簇内代表选择

```
score = 0.30*ICIR_norm + 0.20*monotonicity + 0.20*long_short_tstat
      + 0.15*coverage - 0.15*turnover_penalty
```

每簇按 score 取 top 2。

## Ring 7: 组合层验证

| 组合 | 权重 |
|------|------|
| 等权 | mean(selected_factors) |
| IC 加权 | sum(factor_i * |IC_i|) / sum(|IC_i|) |
| ICIR 加权 | sum(factor_i * ICIR_i) / sum(ICIR_i) |

每种组合计算: IC 序列、分层收益、Top-Bottom spread、换手率、年化 Sharpe。

## Ring 8: 模型增量验证

1. LightGBM 回归（筛选后因子 → label）
2. SHAP 值 / Permutation Importance
3. 确认 IC 有效但 ML 贡献为 0 的因子（非线性冗余）

## 最终产物

| 产物 | 内容 |
|------|------|
| `factor_filter_report.md` | 完整 8 环报告 |
| `factor_pool_filtered.parquet` | 筛选后因子池（代表因子 + label） |
| `factor_selection_log.json` | 每个因子保留/剔除原因 |

## 现有代码复用

| 现有文件 | 新位置 | 改动 |
|----------|--------|------|
| `step01_data_qa.py` | `step00_data_qa.py` | 扩展为标签检查 |
| `step02_profiling.py` | `step02_profiling.py` | 扩展为完整画像 |
| `step03_clustering.py` | `step05_clustering.py` | 从因子值改为因子收益相关性 |
| `step04_portfolio.py` | `step07_portfolio.py` | 从 stub 改为真实计算 |
| `step05_ml_importance.py` | `step08_ml_importance.py` | 扩展 SHAP/permutation |

新增: `step01_preprocess.py`, `step03_cs_filter.py`, `step04_stability.py`, `step06_representative.py`

## 配置

```yaml
pipeline:
  name: factor_filtering
  stages: ["load", "ring0_qa", "ring1_preprocess", "ring2_profile",
           "ring3_filter", "ring4_stability", "ring5_cluster",
           "ring6_select", "ring7_portfolio", "ring8_ml", "report"]
  output_dir: "data/reports/factor_filtering"

data:
  factor_path: "data/alpha158_pool.parquet"
  label_col: "label_20d"
  fundamentals_path: "data/parquet/fundamentals"  # 可选，用于中性化

filter:
  min_abs_ic: 0.01
  min_coverage: 0.60
  representatives_per_cluster: 2

clustering:
  distance_threshold: 0.5
  method: "factor_return_correlation"  # factor_return | ic_series | factor_value

preprocess:
  winsorize_lower: 0.01
  winsorize_upper: 0.99
  transform_method: "rank_pct"
  neutralize: []  # 可选: ["market_cap", "industry"]
```
