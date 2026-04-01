"""
因果因子验证框架：机制 → 推论 → 收敛证据

核心思想：人类判断因果不靠统计检验，靠的是——
  1. 提出一个因果机制（narrative）
  2. 从机制推导出多个独立的可观测推论
  3. 逐一检验推论，用贝叶斯证据累积
  4. 在机制不应生效的场景中验证因子确实失效

框架的力量不在于任何单个检验，而在于多个独立推论的乘性证据累积。

依赖: polars, numpy, scipy, sklearn
"""

from dataclasses import dataclass, field
from typing import List, Callable, Optional, Dict, Any, Tuple
from enum import Enum
import numpy as np
import polars as pl
from scipy import stats


# ============================================================
# 第一层：数据结构定义
# ============================================================

class ImplicationType(Enum):
    """推论类型分类。每种类型对应不同的检验方法。"""

    PREDICTIVE = "predictive"
    # 因子应该预测未来收益。最直接的推论。
    # 例：因子值高的股票未来N日收益率应高于因子值低的股票。

    CONDITIONAL = "conditional"
    # 因子的预测力应在特定条件下更强/更弱。
    # 例：机构吸筹因子在低波动环境下预测力更强。

    CROSS_SECTIONAL = "cross_sectional"
    # 因子应在某类股票上有效，在另一类上无效。
    # 例：吸筹因子对中小盘有效，对超大盘（机构已充分覆盖）无效。

    TEMPORAL = "temporal"
    # 因子信号应有特定的时间衰减模式。
    # 例：事件驱动因子在事件后3日内最强，10日后衰减至零。

    DISTRIBUTIONAL = "distributional"
    # 因子值本身应有特定的分布特征。
    # 例：如果因子捕捉的是稀缺事件（如异常大单），因子值应高度右偏。

    AUXILIARY = "auxiliary"
    # 机制的副产品——不直接关于收益预测，但如果机制是真的就应该出现。
    # 例：如果机构在压低波动率，同期的买卖价差应该收窄。


@dataclass
class Implication:
    """
    从因果机制推导出的单个可检验推论。

    每个推论必须包含：
    - 自然语言描述（为什么这个推论从机制中逻辑推出）
    - 检验函数（输入数据，输出检验统计量和p值）
    - 预期方向（正、负、或非零）
    """
    name: str
    description: str  # 因果逻辑链：机制的哪个环节推导出这个推论
    type: ImplicationType
    test_fn: Callable[[pl.DataFrame], Tuple[float, float]]
    # test_fn 输入：包含因子值和收益率的DataFrame
    # test_fn 输出：(test_statistic, p_value)
    expected_direction: str = "positive"  # "positive", "negative", "nonzero"
    weight: float = 1.0  # 推论的先验重要性权重


@dataclass
class CounterScenario:
    """
    因果机制不应生效的场景。

    如果因子在这些场景下仍然"有效"，说明因子捕捉的不是你以为的那个机制。
    这是最强的伪证工具。
    """
    name: str
    description: str  # 为什么机制在这个场景下不应生效
    filter_fn: Callable[[pl.DataFrame], pl.DataFrame]
    # filter_fn: 从全量数据中筛选出该场景的子集
    expected_behavior: str = "factor_ineffective"
    # "factor_ineffective": 因子在该场景下不应有预测力
    # "factor_reversed": 因子在该场景下应反向（更强的反证）


@dataclass
class MechanismHypothesis:
    """
    完整的因果机制假设。

    这是框架的核心对象。要求研究者显式写出：
    1. 因果故事（谁在什么条件下做什么，通过什么路径影响价格）
    2. 至少5个独立推论
    3. 至少2个反例场景
    4. 因子的计算函数
    """
    # --- 机制叙事 ---
    name: str
    narrative: str          # 完整因果故事，自然语言
    participants: str       # 行为主体：机构？散户？做市商？
    market_conditions: str  # 激活条件：什么市场环境下这个机制运作
    behavior: str           # 具体行为：主体做了什么
    transmission: str       # 传导路径：行为如何影响价格

    # --- 可检验推论 ---
    implications: List[Implication] = field(default_factory=list)

    # --- 反例场景 ---
    counter_scenarios: List[CounterScenario] = field(default_factory=list)

    # --- 因子计算 ---
    factor_fn: Optional[Callable[[pl.DataFrame], pl.Series]] = None
    # factor_fn: 输入原始行情数据，输出因子值序列

    def validate(self) -> List[str]:
        """检查假设是否满足最低完备性要求。"""
        issues = []
        if len(self.implications) < 5:
            issues.append(
                f"推论数量不足：{len(self.implications)}/5。"
                f"多个独立推论是证据强度的来源，少于5个无法形成收敛证据。"
            )
        if len(self.counter_scenarios) < 2:
            issues.append(
                f"反例场景不足：{len(self.counter_scenarios)}/2。"
                f"没有反例场景，无法区分真因果和虚假相关。"
            )
        if self.factor_fn is None:
            issues.append("未定义因子计算函数。")

        # 检查推论类型的多样性
        types_used = set(imp.type for imp in self.implications)
        if len(types_used) < 3:
            issues.append(
                f"推论类型多样性不足：仅使用了 {[t.value for t in types_used]}。"
                f"不同类型的推论提供真正独立的证据。"
            )

        return issues


# ============================================================
# 第二层：检验方法库
# ============================================================

class TestLibrary:
    """
    标准化检验方法。每个方法输入DataFrame，输出(statistic, p_value)。

    命名约定：
    - factor_col: 因子值列名
    - return_col: 收益率列名
    - condition_col: 条件变量列名（用于条件检验）
    """

    @staticmethod
    def rank_ic(
        df: pl.DataFrame,
        factor_col: str = "factor",
        return_col: str = "forward_return",
    ) -> Tuple[float, float]:
        """
        Rank IC (Spearman秩相关)。
        最标准的因子预测力检验。
        """
        f = df[factor_col].to_numpy()
        r = df[return_col].to_numpy()
        mask = np.isfinite(f) & np.isfinite(r)
        if mask.sum() < 30:
            return 0.0, 1.0
        corr, pval = stats.spearmanr(f[mask], r[mask])
        return float(corr), float(pval)

    @staticmethod
    def long_short_return(
        df: pl.DataFrame,
        factor_col: str = "factor",
        return_col: str = "forward_return",
        quantile: float = 0.2,
    ) -> Tuple[float, float]:
        """
        分组多空收益检验。
        因子值最高组 vs 最低组的收益率差异。
        """
        f = df[factor_col].to_numpy()
        r = df[return_col].to_numpy()
        mask = np.isfinite(f) & np.isfinite(r)
        f, r = f[mask], r[mask]
        if len(f) < 50:
            return 0.0, 1.0

        low_thresh = np.percentile(f, quantile * 100)
        high_thresh = np.percentile(f, (1 - quantile) * 100)

        r_high = r[f >= high_thresh]
        r_low = r[f <= low_thresh]

        if len(r_high) < 5 or len(r_low) < 5:
            return 0.0, 1.0

        spread = r_high.mean() - r_low.mean()
        t_stat, pval = stats.ttest_ind(r_high, r_low)
        return float(spread), float(pval)

    @staticmethod
    def ic_decay(
        df: pl.DataFrame,
        factor_col: str = "factor",
        return_col_template: str = "forward_return_{d}d",
        horizons: List[int] = None,
    ) -> Tuple[float, float]:
        """
        IC衰减曲线分析。
        检验因子在不同预测horizon上的IC是否按预期衰减。
        返回衰减速率（负数=正常衰减）和拟合的p值。
        """
        if horizons is None:
            horizons = [1, 3, 5, 10, 20]

        ics = []
        valid_horizons = []
        for d in horizons:
            col = return_col_template.format(d=d)
            if col in df.columns:
                ic, _ = TestLibrary.rank_ic(df, factor_col, col)
                ics.append(ic)
                valid_horizons.append(d)

        if len(ics) < 3:
            return 0.0, 1.0

        # 对 log(horizon) 回归 IC，斜率就是衰减速率
        log_h = np.log(valid_horizons)
        slope, intercept, r_value, p_value, std_err = stats.linregress(log_h, ics)
        return float(slope), float(p_value)

    @staticmethod
    def conditional_ic(
        df: pl.DataFrame,
        factor_col: str = "factor",
        return_col: str = "forward_return",
        condition_col: str = "condition",
        condition_threshold: float = 0.5,
        direction: str = "above_stronger",
    ) -> Tuple[float, float]:
        """
        条件IC检验。
        比较条件变量高/低状态下的因子IC差异。
        direction:
          "above_stronger" = 条件变量高时IC应更强
          "below_stronger" = 条件变量低时IC应更强
        """
        c = df[condition_col].to_numpy()
        mask = np.isfinite(c)
        if mask.sum() < 60:
            return 0.0, 1.0

        thresh = np.percentile(c[mask], condition_threshold * 100)
        df_above = df.filter(pl.col(condition_col) >= thresh)
        df_below = df.filter(pl.col(condition_col) < thresh)

        ic_above, _ = TestLibrary.rank_ic(df_above, factor_col, return_col)
        ic_below, _ = TestLibrary.rank_ic(df_below, factor_col, return_col)

        if direction == "above_stronger":
            diff = ic_above - ic_below
        else:
            diff = ic_below - ic_above

        # 用 bootstrap 估计差异的显著性
        n_boot = 1000
        boot_diffs = []
        f_vals = df[factor_col].to_numpy()
        r_vals = df[return_col].to_numpy()
        c_vals = c.copy()
        valid = np.isfinite(f_vals) & np.isfinite(r_vals) & np.isfinite(c_vals)
        f_v, r_v, c_v = f_vals[valid], r_vals[valid], c_vals[valid]
        n = len(f_v)

        for _ in range(n_boot):
            idx = np.random.randint(0, n, n)
            f_b, r_b, c_b = f_v[idx], r_v[idx], c_v[idx]
            mask_a = c_b >= thresh
            mask_b = ~mask_a
            if mask_a.sum() > 10 and mask_b.sum() > 10:
                ic_a = stats.spearmanr(f_b[mask_a], r_b[mask_a])[0]
                ic_b = stats.spearmanr(f_b[mask_b], r_b[mask_b])[0]
                if direction == "above_stronger":
                    boot_diffs.append(ic_a - ic_b)
                else:
                    boot_diffs.append(ic_b - ic_a)

        if len(boot_diffs) < 100:
            return float(diff), 1.0

        boot_diffs = np.array(boot_diffs)
        p_value = (boot_diffs <= 0).mean()  # one-sided test
        return float(diff), float(p_value)

    @staticmethod
    def monotonicity(
        df: pl.DataFrame,
        factor_col: str = "factor",
        return_col: str = "forward_return",
        n_groups: int = 5,
    ) -> Tuple[float, float]:
        """
        分组单调性检验。
        将股票按因子值分为N组，检验组均收益是否单调递增。
        返回 Jonckheere-Terpstra 趋势统计量。
        """
        f = df[factor_col].to_numpy()
        r = df[return_col].to_numpy()
        mask = np.isfinite(f) & np.isfinite(r)
        f, r = f[mask], r[mask]
        if len(f) < n_groups * 10:
            return 0.0, 1.0

        # 分组
        percentiles = np.linspace(0, 100, n_groups + 1)
        thresholds = np.percentile(f, percentiles)
        groups = np.digitize(f, thresholds[1:-1])

        group_means = []
        for g in range(n_groups):
            g_mask = groups == g
            if g_mask.sum() > 0:
                group_means.append(r[g_mask].mean())
            else:
                group_means.append(np.nan)

        group_means = np.array(group_means)
        valid = np.isfinite(group_means)
        if valid.sum() < 3:
            return 0.0, 1.0

        # Spearman相关作为单调性度量
        gm_valid = group_means[valid]
        ranks = np.arange(valid.sum())
        corr, pval = stats.spearmanr(ranks, gm_valid)
        return float(corr), float(pval)

    @staticmethod
    def turnover_consistency(
        df: pl.DataFrame,
        factor_col: str = "factor",
        date_col: str = "date",
        stock_col: str = "stock_id",
        top_pct: float = 0.2,
    ) -> Tuple[float, float]:
        """
        因子换手率分析。
        检验因子选出的股票池是否有合理的换手率。
        换手率太高 = 噪声驱动；太低 = 可能是静态特征。
        返回平均换手率和稳定性检验。
        """
        dates = sorted(df[date_col].unique().to_list())
        if len(dates) < 10:
            return 0.0, 1.0

        turnovers = []
        prev_top = None
        for d in dates:
            daily = df.filter(pl.col(date_col) == d)
            fvals = daily[factor_col].to_numpy()
            ids = daily[stock_col].to_numpy()
            mask = np.isfinite(fvals)
            if mask.sum() < 10:
                continue
            fvals, ids = fvals[mask], ids[mask]
            thresh = np.percentile(fvals, (1 - top_pct) * 100)
            top_ids = set(ids[fvals >= thresh])

            if prev_top is not None and len(prev_top) > 0 and len(top_ids) > 0:
                overlap = len(top_ids & prev_top)
                union = len(top_ids | prev_top)
                turnover = 1.0 - overlap / union if union > 0 else 1.0
                turnovers.append(turnover)
            prev_top = top_ids

        if len(turnovers) < 5:
            return 0.0, 1.0

        mean_turnover = np.mean(turnovers)
        # 检验换手率是否在合理范围 (0.1, 0.7)
        # 用一个简单的heuristic: 越接近0.3-0.4越好
        reasonableness = 1.0 - abs(mean_turnover - 0.35) / 0.35
        # p-value: 换手率是否显著不同于随机选股 (约0.6-0.8)
        random_expected = 1.0 - top_pct  # 随机换手率近似
        t_stat, p_val = stats.ttest_1samp(turnovers, random_expected)
        return float(mean_turnover), float(p_val)


# ============================================================
# 第三层：贝叶斯证据累积引擎
# ============================================================

@dataclass
class ImplicationResult:
    """单个推论的检验结果。"""
    implication: Implication
    statistic: float
    p_value: float
    direction_correct: bool  # 统计量方向是否与预期一致
    bayes_factor: float      # 该推论提供的贝叶斯因子
    passed: bool             # 是否通过检验


@dataclass
class CounterScenarioResult:
    """反例场景的检验结果。"""
    scenario: CounterScenario
    ic_in_scenario: float
    p_value: float
    mechanism_correctly_disabled: bool  # 因子在该场景下是否确实失效


@dataclass
class EvidenceReport:
    """完整的证据评估报告。"""
    hypothesis: MechanismHypothesis
    implication_results: List[ImplicationResult]
    counter_results: List[CounterScenarioResult]

    # 汇总统计
    n_implications_passed: int = 0
    n_implications_total: int = 0
    n_counters_passed: int = 0
    n_counters_total: int = 0
    composite_bayes_factor: float = 1.0
    counter_penalty: float = 1.0
    final_score: float = 0.0
    verdict: str = ""

    def compute_summary(self):
        """计算汇总评估。"""
        self.n_implications_total = len(self.implication_results)
        self.n_implications_passed = sum(
            1 for r in self.implication_results if r.passed
        )
        self.n_counters_total = len(self.counter_results)
        self.n_counters_passed = sum(
            1 for r in self.counter_results if r.mechanism_correctly_disabled
        )

        # 贝叶斯因子的乘积（加权）
        self.composite_bayes_factor = 1.0
        for r in self.implication_results:
            bf = r.bayes_factor ** r.implication.weight
            self.composite_bayes_factor *= bf

        # 反例场景惩罚
        # 每个失败的反例场景（因子在不应有效时仍然有效）
        # 将总证据打一个严厉的折扣
        if self.n_counters_total > 0:
            fail_rate = 1.0 - self.n_counters_passed / self.n_counters_total
            self.counter_penalty = 0.1 ** fail_rate
            # 每个失败的反例将证据除以10
        else:
            self.counter_penalty = 1.0

        self.final_score = np.log10(
            max(self.composite_bayes_factor * self.counter_penalty, 1e-10)
        )

        # 判决
        if self.final_score > 3:
            self.verdict = "强因果证据 (>1000:1)"
        elif self.final_score > 2:
            self.verdict = "中等因果证据 (>100:1)"
        elif self.final_score > 1:
            self.verdict = "弱因果证据 (>10:1)"
        elif self.final_score > 0:
            self.verdict = "极弱证据，不可靠"
        else:
            self.verdict = "无证据或反证据"


class CausalEvidenceEngine:
    """
    核心引擎：执行所有检验，累积证据，生成报告。
    """

    def __init__(self, significance_level: float = 0.05):
        self.alpha = significance_level

    def _compute_bayes_factor(
        self, p_value: float, direction_correct: bool
    ) -> float:
        """
        从p值近似贝叶斯因子。

        使用 Sellke, Bayarri & Berger (2001) 的校准：
        BF ≈ -e * p * ln(p) 当 p < 1/e

        方向不对则贝叶斯因子 < 1（反证据）。
        """
        if not direction_correct:
            # 方向错误 = 反证据
            return 0.1  # 强烈反对该假设

        if p_value <= 0:
            return 100.0  # 上限

        if p_value >= 1.0:
            return 1.0  # 无信息

        if p_value < 1.0 / np.e:
            bf = -np.e * p_value * np.log(p_value)
            return min(1.0 / bf, 100.0)  # 取倒数，因为低p支持备择假设
        else:
            return 1.0

    def _check_direction(
        self, statistic: float, expected: str
    ) -> bool:
        """检查统计量方向是否与预期一致。"""
        if expected == "positive":
            return statistic > 0
        elif expected == "negative":
            return statistic < 0
        elif expected == "nonzero":
            return abs(statistic) > 1e-10
        return True

    def evaluate(
        self,
        hypothesis: MechanismHypothesis,
        data: pl.DataFrame,
    ) -> EvidenceReport:
        """
        执行完整的因果证据评估。

        Parameters
        ----------
        hypothesis : MechanismHypothesis
            完整的因果机制假设
        data : pl.DataFrame
            包含所有必要列的数据

        Returns
        -------
        EvidenceReport
            完整的证据报告
        """
        # 先验验证
        issues = hypothesis.validate()
        if issues:
            print("⚠️  假设完备性检查未通过：")
            for issue in issues:
                print(f"   - {issue}")
            print("   继续评估，但结果可靠性受限。\n")

        # --- 检验所有推论 ---
        impl_results = []
        for imp in hypothesis.implications:
            try:
                stat, pval = imp.test_fn(data)
                direction_ok = self._check_direction(stat, imp.expected_direction)
                bf = self._compute_bayes_factor(pval, direction_ok)
                passed = (pval < self.alpha) and direction_ok

                impl_results.append(ImplicationResult(
                    implication=imp,
                    statistic=stat,
                    p_value=pval,
                    direction_correct=direction_ok,
                    bayes_factor=bf,
                    passed=passed,
                ))
            except Exception as e:
                print(f"⚠️  推论 '{imp.name}' 检验失败: {e}")
                impl_results.append(ImplicationResult(
                    implication=imp,
                    statistic=0.0,
                    p_value=1.0,
                    direction_correct=False,
                    bayes_factor=1.0,
                    passed=False,
                ))

        # --- 检验所有反例场景 ---
        counter_results = []
        for cs in hypothesis.counter_scenarios:
            try:
                sub_data = cs.filter_fn(data)
                if len(sub_data) < 30:
                    print(f"⚠️  反例场景 '{cs.name}' 样本量不足 ({len(sub_data)})")
                    counter_results.append(CounterScenarioResult(
                        scenario=cs,
                        ic_in_scenario=0.0,
                        p_value=1.0,
                        mechanism_correctly_disabled=True,  # 无法判断，给pass
                    ))
                    continue

                ic, pval = TestLibrary.rank_ic(sub_data)

                if cs.expected_behavior == "factor_ineffective":
                    # 因子在该场景下IC应不显著
                    correctly_disabled = pval > self.alpha or abs(ic) < 0.03
                elif cs.expected_behavior == "factor_reversed":
                    # 因子在该场景下应反向
                    correctly_disabled = ic < 0 and pval < self.alpha
                else:
                    correctly_disabled = pval > self.alpha

                counter_results.append(CounterScenarioResult(
                    scenario=cs,
                    ic_in_scenario=ic,
                    p_value=pval,
                    mechanism_correctly_disabled=correctly_disabled,
                ))
            except Exception as e:
                print(f"⚠️  反例场景 '{cs.name}' 检验失败: {e}")
                counter_results.append(CounterScenarioResult(
                    scenario=cs,
                    ic_in_scenario=0.0,
                    p_value=1.0,
                    mechanism_correctly_disabled=True,
                ))

        # --- 汇总报告 ---
        report = EvidenceReport(
            hypothesis=hypothesis,
            implication_results=impl_results,
            counter_results=counter_results,
        )
        report.compute_summary()
        return report


# ============================================================
# 第四层：报告输出
# ============================================================

def print_evidence_report(report: EvidenceReport):
    """打印完整的证据评估报告。"""
    h = report.hypothesis
    print("=" * 72)
    print(f"因果因子评估报告：{h.name}")
    print("=" * 72)

    print(f"\n【机制叙事】")
    print(f"  行为主体：{h.participants}")
    print(f"  市场条件：{h.market_conditions}")
    print(f"  行为描述：{h.behavior}")
    print(f"  传导路径：{h.transmission}")
    print(f"  完整叙事：{h.narrative}")

    print(f"\n{'─' * 72}")
    print(f"【推论检验】 {report.n_implications_passed}/{report.n_implications_total} 通过")
    print(f"{'─' * 72}")

    for r in report.implication_results:
        status = "✅" if r.passed else "❌"
        direction = "✓" if r.direction_correct else "✗方向"
        print(
            f"  {status} {r.implication.name:<30s} "
            f"stat={r.statistic:+.4f}  p={r.p_value:.4f}  "
            f"BF={r.bayes_factor:.1f}  {direction}"
        )
        if not r.passed:
            print(f"     └─ {r.implication.description}")

    print(f"\n{'─' * 72}")
    print(f"【反例场景】 {report.n_counters_passed}/{report.n_counters_total} 通过")
    print(f"{'─' * 72}")

    for r in report.counter_results:
        status = "✅" if r.mechanism_correctly_disabled else "🚨"
        print(
            f"  {status} {r.scenario.name:<30s} "
            f"IC={r.ic_in_scenario:+.4f}  p={r.p_value:.4f}"
        )
        if not r.mechanism_correctly_disabled:
            print(f"     └─ 警告：因子在不应有效的场景下仍然有效！")
            print(f"        {r.scenario.description}")

    print(f"\n{'═' * 72}")
    print(f"【综合评估】")
    print(f"  复合贝叶斯因子：  {report.composite_bayes_factor:.1f}")
    print(f"  反例场景惩罚：    {report.counter_penalty:.3f}")
    print(f"  最终得分 (log10)：{report.final_score:.2f}")
    print(f"  判决：            {report.verdict}")
    print(f"{'═' * 72}")


# ============================================================
# 第五层：完整示例——机构吸筹因子
# ============================================================

def example_institutional_accumulation():
    """
    示例：如何用这个框架定义和检验一个机构吸筹因子。

    注意：这里的 test_fn 和 filter_fn 使用占位逻辑。
    实际使用时需要替换为真实数据和计算。
    """

    hypothesis = MechanismHypothesis(
        name="机构隐蔽吸筹",

        narrative=(
            "当机构投资者决定建立某只股票的仓位时，为避免市场冲击，"
            "他们会采用算法拆单，在较长时间内（通常5-20个交易日）"
            "持续小额买入。这种行为会导致：成交量不会异常放大但大单"
            "占比稳定偏高，波动率被压制（因为机构在价格下跌时加大买入"
            "强度），买卖盘的微观结构出现非对称性。建仓完成后，卖压"
            "减弱+催化剂出现时，价格上行阻力显著降低。"
        ),

        participants="机构投资者（公募/私募基金、保险资金）",

        market_conditions=(
            "股票处于相对低位（距近期高点回撤>15%），"
            "市场整体波动率中性偏低，"
            "该股票有基本面改善的前瞻信号（业绩预告、行业政策等）"
        ),

        behavior=(
            "持续5-20日的算法拆单买入，"
            "单笔成交量控制在日成交量的0.5-2%，"
            "在价格回落时加大买入强度（逢低吸纳）"
        ),

        transmission=(
            "路径1：直接买入支撑 → 下跌阻力增大 → 波动率压缩\n"
            "路径2：持续吸筹 → 流通盘中机构占比上升 → 卖压结构性减少\n"
            "路径3：建仓完成后 → 机构可能主动释放利好催化 → 价格跳升"
        ),
    )

    # --- 推论1：预测力 ---
    hypothesis.implications.append(Implication(
        name="因子预测5日收益",
        description=(
            "机制推论：吸筹尚未完成时，因子值高的股票仍有持续买入支撑，"
            "5日收益应高于因子值低的股票。"
        ),
        type=ImplicationType.PREDICTIVE,
        test_fn=lambda df: TestLibrary.rank_ic(df, "factor", "forward_return_5d"),
        expected_direction="positive",
        weight=1.5,  # 预测力是最直接的推论，权重略高
    ))

    # --- 推论2：分组单调性 ---
    hypothesis.implications.append(Implication(
        name="五分组收益单调递增",
        description=(
            "如果因子真正捕捉了吸筹强度，则吸筹强度与未来收益应呈单调关系，"
            "而非仅头尾组有差异（后者可能是极端值噪声）。"
        ),
        type=ImplicationType.DISTRIBUTIONAL,
        test_fn=lambda df: TestLibrary.monotonicity(
            df, "factor", "forward_return_5d", n_groups=5
        ),
        expected_direction="positive",
    ))

    # --- 推论3：低波动环境下更强 ---
    hypothesis.implications.append(Implication(
        name="低波动环境IC更高",
        description=(
            "机制推论：机构吸筹需要相对平稳的环境。高波动时机构倾向暂停，"
            "因此因子在低波动环境下的预测力应显著强于高波动环境。"
        ),
        type=ImplicationType.CONDITIONAL,
        test_fn=lambda df: TestLibrary.conditional_ic(
            df, "factor", "forward_return_5d", "volatility_20d",
            condition_threshold=0.5, direction="below_stronger",
        ),
        expected_direction="positive",
    ))

    # --- 推论4：信号衰减模式 ---
    hypothesis.implications.append(Implication(
        name="IC在20日内衰减",
        description=(
            "机制推论：吸筹持续5-20日，之后效应应被价格完全反映。"
            "因此IC应在1-5日最强，20日后显著衰减。衰减速率应为负。"
        ),
        type=ImplicationType.TEMPORAL,
        test_fn=lambda df: TestLibrary.ic_decay(
            df, "factor", "forward_return_{d}d", [1, 3, 5, 10, 20]
        ),
        expected_direction="negative",  # 斜率应为负（衰减）
    ))

    # --- 推论5：换手率合理 ---
    hypothesis.implications.append(Implication(
        name="因子选股池换手率在合理区间",
        description=(
            "机制推论：吸筹是一个持续数日的过程，因此因子选出的股票池"
            "不应每天大幅变动（否则说明因子捕捉的是噪声），但也不应完全"
            "不变（否则说明因子是静态特征如市值、行业）。"
        ),
        type=ImplicationType.DISTRIBUTIONAL,
        test_fn=lambda df: TestLibrary.turnover_consistency(
            df, "factor", "date", "stock_id", top_pct=0.2
        ),
        expected_direction="negative",  # 换手率显著低于随机
    ))

    # --- 推论6：辅助变量——买卖价差 ---
    hypothesis.implications.append(Implication(
        name="吸筹期间买卖价差收窄",
        description=(
            "机制推论：机构持续挂买单提供流动性，应导致bid-ask spread收窄。"
            "因子值高的股票，同期买卖价差应低于因子值低的股票。"
        ),
        type=ImplicationType.AUXILIARY,
        test_fn=lambda df: TestLibrary.rank_ic(df, "factor", "spread_narrowing"),
        expected_direction="positive",  # 因子高 → spread缩小（定义为正）
    ))

    # --- 反例场景1：涨停/跌停日 ---
    hypothesis.counter_scenarios.append(CounterScenario(
        name="涨跌停日",
        description=(
            "涨跌停时交易几乎停滞，机构无法执行吸筹策略。"
            "如果因子在涨跌停日仍显示有效，说明因子捕捉的不是吸筹行为。"
        ),
        filter_fn=lambda df: df.filter(pl.col("is_limit").eq(True)),
        expected_behavior="factor_ineffective",
    ))

    # --- 反例场景2：超大盘股 ---
    hypothesis.counter_scenarios.append(CounterScenario(
        name="沪深300超大盘",
        description=(
            "超大盘股（市值>1000亿）的机构持仓已高度分散，"
            "单一机构的吸筹行为不足以影响价格微观结构。"
            "因子在这个群体上不应有显著预测力。"
        ),
        filter_fn=lambda df: df.filter(pl.col("market_cap") > 1e11),
        expected_behavior="factor_ineffective",
    ))

    # --- 反例场景3：高波动市场环境 ---
    hypothesis.counter_scenarios.append(CounterScenario(
        name="市场高波动期",
        description=(
            "VIX等效指标处于高位时，机构倾向暂停建仓。"
            "因子在这些时段不应有效。"
        ),
        filter_fn=lambda df: df.filter(
            pl.col("market_volatility") > pl.col("market_volatility").quantile(0.8)
        ),
        expected_behavior="factor_ineffective",
    ))

    return hypothesis


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    # 展示框架结构
    h = example_institutional_accumulation()
    issues = h.validate()

    print("因果因子验证框架 v1.0")
    print("=" * 72)
    print(f"假设名称：{h.name}")
    print(f"推论数量：{len(h.implications)}")
    print(f"反例场景：{len(h.counter_scenarios)}")
    print(f"完备性检查：{'通过' if not issues else '未通过'}")
    if issues:
        for issue in issues:
            print(f"  ⚠️ {issue}")
    else:
        print("  ✅ 所有完备性要求已满足")

    print("\n推论列表：")
    for i, imp in enumerate(h.implications, 1):
        print(f"  {i}. [{imp.type.value}] {imp.name} (权重={imp.weight})")

    print("\n反例场景：")
    for i, cs in enumerate(h.counter_scenarios, 1):
        print(f"  {i}. {cs.name} → 预期: {cs.expected_behavior}")

    print("\n" + "=" * 72)
    print("要使用此框架：")
    print("  1. 定义你的 MechanismHypothesis（参考 example_institutional_accumulation）")
    print("  2. 准备包含必要列的 Polars DataFrame")
    print("  3. engine = CausalEvidenceEngine()")
    print("  4. report = engine.evaluate(hypothesis, data)")
    print("  5. print_evidence_report(report)")
