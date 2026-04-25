# tests/pipelines/factor/test_filter_chain.py
"""Filter chain step unit tests."""
import numpy as np
import pandas as pd

from pipelines.factor.filter_chain import (
    FilterContext,
    BaseFilterStep,
    DropMissingLabelStep,
    DropLeakageStep,
    DropHighMissingFeatureStep,
    DropHighInfFeatureStep,
    DropLowVarianceFeatureStep,
    FactorQualityFilterStep,
    DeduplicateStep,
    _drop_rows,
    _drop_features,
    _rank_ic_by_date,
)


def _make_context(n=100):
    dates = pd.date_range("2020-01-01", periods=n // 4, freq="B")
    symbols = ["SH600001", "SH600002", "SH600003", "SH600004"]
    index = pd.MultiIndex.from_product([dates, symbols], names=["datetime", "instrument"])
    X = pd.DataFrame({
        "MA5": np.random.randn(len(index)),
        "MA10": np.random.randn(len(index)),
        "STD5": np.random.randn(len(index)),
        "LABEL0": np.random.randn(len(index)),  # leak
        "label_pred": np.random.randn(len(index)),  # leak
    }, index=index)
    y = pd.Series(np.random.randn(len(index)), index=index)
    return FilterContext(X=X, y=y)


def test_drop_leakage_removes_label_prefix():
    ctx = _make_context()
    assert "LABEL0" in ctx.X.columns
    assert "label_pred" in ctx.X.columns

    step = DropLeakageStep(prefixes=["LABEL", "label"])
    ctx = step.process(ctx)

    assert "LABEL0" not in ctx.X.columns
    assert "label_pred" not in ctx.X.columns
    assert "MA5" in ctx.X.columns
    assert "MA10" in ctx.X.columns
    assert "STD5" in ctx.X.columns


def test_drop_leakage_default_prefix():
    ctx = _make_context()
    step = DropLeakageStep()  # default: ["LABEL"]
    ctx = step.process(ctx)

    assert "LABEL0" not in ctx.X.columns
    assert "label_pred" in ctx.X.columns  # not removed because "label" is not in default


def test_deduplicate_removes_redundant():
    dates = pd.date_range("2020-01-01", periods=50, freq="B")
    symbols = ["SH600001", "SH600002"]
    index = pd.MultiIndex.from_product([dates, symbols], names=["datetime", "instrument"])

    # 创建高度相关的因子对
    base = np.random.randn(len(index))
    X = pd.DataFrame({
        "MA5": base,
        "MA10": base + np.random.randn(len(index)) * 0.01,  # 高度相关
        "STD5": np.random.randn(len(index)),
    }, index=index)
    y = pd.Series(np.random.randn(len(index)), index=index)
    ctx = FilterContext(X=X, y=y)

    step = DeduplicateStep(corr_threshold=0.8, corr_method="pearson")
    ctx = step.process(ctx)

    # MA5 和 MA10 高度相关，应该只保留一个
    retained = [c for c in ["MA5", "MA10"] if c in ctx.X.columns]
    assert len(retained) == 1
    assert "STD5" in ctx.X.columns  # 不相关的应该保留


def test_deduplicate_keeps_higher_ic():
    dates = pd.date_range("2020-01-01", periods=50, freq="B")
    symbols = ["SH600001", "SH600002"]
    index = pd.MultiIndex.from_product([dates, symbols], names=["datetime", "instrument"])

    base = np.random.randn(len(index))
    X = pd.DataFrame({
        "MA5": base,
        "MA10": base + np.random.randn(len(index)) * 0.01,
    }, index=index)
    y = pd.Series(np.random.randn(len(index)), index=index)
    ctx = FilterContext(X=X, y=y)

    # 注入 FactorQualityFilterStep 的 artifact，让 MA5 的 IC 更高
    ctx.artifacts["FactorQualityFilterStep.factor_stats"] = pd.DataFrame({
        "ic_mean": {"MA5": 0.05, "MA10": 0.01},
    })

    step = DeduplicateStep(corr_threshold=0.8, corr_method="pearson", keep_by="ic_mean")
    ctx = step.process(ctx)

    assert "MA5" in ctx.X.columns  # 应该保留 IC 更高的
    assert "MA10" not in ctx.X.columns


# =========================================================
# Full chain integration test
# =========================================================

def _make_full_chain_context(n_dates=200, n_symbols=10, n_factors=20):
    """
    生成模拟完整责任链测试的数据:
    - MultiIndex(date, instrument)
    - 包含泄漏因子、高缺失因子、低方差因子、有效因子
    - y 与部分因子有相关性
    """
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=n_dates, freq="B")
    symbols = [f"SH600{i}" for i in range(n_symbols)]
    index = pd.MultiIndex.from_product([dates, symbols], names=["datetime", "instrument"])
    n = len(index)

    factors = {}

    # 1. 泄漏因子 (应被 DropLeakageStep 删除)
    factors["LABEL0"] = np.random.randn(n)

    # 2. 高缺失因子 (缺失率 > 30%，应被 DropHighMissingFeatureStep 删除)
    high_missing = np.full(n, np.nan)
    valid_mask = np.random.random(n) > 0.5  # 50% 缺失
    high_missing[valid_mask] = np.random.randn(valid_mask.sum())
    factors["HIGH_MISSING"] = high_missing

    # 3. 低方差/常数列 (应被 DropLowVarianceFeatureStep 删除)
    factors["CONSTANT"] = np.ones(n)
    factors["LOW_VAR"] = np.ones(n) * 0.000000001

    # 4. 有效因子 — 与 y 有单调关系
    date_layer = index.get_level_values("datetime")
    for i in range(5):
        factors[f"GOOD_FACTOR_{i}"] = np.random.randn(n)

    # 5. 冗余因子对 (高度相关)
    base = np.random.randn(n)
    factors["REDUNDANT_A"] = base
    factors["REDUNDANT_B"] = base + np.random.randn(n) * 0.001

    # 6. 噪声因子 (随机)
    for i in range(n_factors - 10):
        factors[f"NOISE_{i}"] = np.random.randn(n)

    X = pd.DataFrame(factors, index=index)

    # y 与 GOOD_FACTOR 有正向关系
    good_cols = [c for c in X.columns if c.startswith("GOOD_FACTOR")]
    y = X[good_cols].mean(axis=1) + np.random.randn(n) * 0.5
    y = pd.Series(y, index=index, name="label")

    return FilterContext(X=X, y=y)


def _build_full_chain(config):
    """从配置字典构建完整责任链。"""
    steps = []

    if "drop_missing_label" in config:
        steps.append(DropMissingLabelStep())
    if "drop_leakage" in config:
        steps.append(DropLeakageStep(prefixes=config["drop_leakage"].get("prefixes", ["LABEL"])))
    if "drop_high_missing" in config:
        steps.append(DropHighMissingFeatureStep(threshold=config["drop_high_missing"].get("threshold", 0.3)))
    if "drop_high_inf" in config:
        steps.append(DropHighInfFeatureStep(threshold=config["drop_high_inf"].get("threshold", 0.01)))
    if "drop_low_variance" in config:
        c = config["drop_low_variance"]
        steps.append(DropLowVarianceFeatureStep(
            variance_threshold=c.get("variance_threshold", 1e-8),
            unique_ratio_threshold=c.get("unique_ratio_threshold", 0.01),
        ))
    if "factor_quality" in config:
        c = config["factor_quality"]
        steps.append(FactorQualityFilterStep(
            min_abs_ic_mean=c.get("min_abs_ic_mean", 0.005),
            min_abs_icir=c.get("min_abs_icir", 0.1),
            min_abs_monotonicity=c.get("min_abs_monotonicity", 0.05),
            max_sign_flip_ratio=c.get("max_sign_flip_ratio", 0.45),
        ))
    if "deduplicate" in config:
        c = config["deduplicate"]
        steps.append(DeduplicateStep(
            corr_threshold=c.get("corr_threshold", 0.8),
            corr_method=c.get("corr_method", "spearman"),
            keep_by=c.get("keep_by", "ic_mean"),
        ))

    head = steps[0]
    for step in steps[1:]:
        head.set_next(step)
        head = step

    return steps[0]


def test_full_chain_removes_leakage_first():
    """责任链第一步就应删除泄漏因子，后续步骤不再处理它。"""
    ctx = _make_full_chain_context()
    assert "LABEL0" in ctx.X.columns

    config = {
        "drop_missing_label": {},
        "drop_leakage": {"prefixes": ["LABEL"]},
        "drop_high_missing": {"threshold": 0.9},  # 宽松
        "drop_high_inf": {"threshold": 0.9},
        "drop_low_variance": {"variance_threshold": 1e-15, "unique_ratio_threshold": 0.001},
        "factor_quality": {"min_abs_ic_mean": 0.0, "min_abs_icir": 0.0, "min_abs_monotonicity": 0.0, "max_sign_flip_ratio": 1.0},
        "deduplicate": {"corr_threshold": 0.99},
    }
    chain = _build_full_chain(config)
    ctx = chain.handle(ctx)

    assert "LABEL0" not in ctx.X.columns
    assert ctx.n_rows > 0  # 应该有样本保留


def test_full_chain_end_to_end():
    """完整责任链端到端测试：验证所有步骤都执行并记录日志。"""
    ctx = _make_full_chain_context()
    initial_factors = list(ctx.X.columns)
    initial_rows = ctx.n_rows

    config = {
        "drop_missing_label": {},
        "drop_leakage": {"prefixes": ["LABEL"]},
        "drop_high_missing": {"threshold": 0.3},
        "drop_high_inf": {"threshold": 0.01},
        "drop_low_variance": {"variance_threshold": 1e-8, "unique_ratio_threshold": 0.01},
        "factor_quality": {"min_abs_ic_mean": 0.005, "min_abs_icir": 0.1, "min_abs_monotonicity": 0.05, "max_sign_flip_ratio": 0.45},
        "deduplicate": {"corr_threshold": 0.8},
    }
    chain = _build_full_chain(config)
    ctx = chain.handle(ctx)

    # 验证所有步骤都执行了
    step_names = [log.split("]")[0].lstrip("[") for log in ctx.logs if "]" in log]
    assert "DropMissingLabelStep" in step_names
    assert "DropLeakageStep" in step_names
    assert "DropHighMissingFeatureStep" in step_names
    assert "DropHighInfFeatureStep" in step_names
    assert "DropLowVarianceFeatureStep" in step_names
    assert "FactorQualityFilterStep" in step_names
    assert "DeduplicateStep" in step_names

    # 验证泄漏因子被删除
    assert "LABEL0" not in ctx.X.columns

    # 验证高缺失因子被删除
    assert "HIGH_MISSING" not in ctx.X.columns

    # 验证常数列被删除
    assert "CONSTANT" not in ctx.X.columns
    assert "LOW_VAR" not in ctx.X.columns

    # 验证样本数不增加
    assert ctx.n_rows <= initial_rows

    # 验证因子数减少
    assert ctx.n_features < len(initial_factors)


def test_chain_artifacts_populated():
    """责任链执行后，artifacts 应包含各步骤的统计信息。"""
    ctx = _make_full_chain_context()

    config = {
        "drop_missing_label": {},
        "drop_leakage": {"prefixes": ["LABEL"]},
        "drop_high_missing": {"threshold": 0.3},
        "drop_high_inf": {"threshold": 0.01},
        "drop_low_variance": {"variance_threshold": 1e-8, "unique_ratio_threshold": 0.01},
        "factor_quality": {"min_abs_ic_mean": 0.0, "min_abs_icir": 0.0, "min_abs_monotonicity": 0.0, "max_sign_flip_ratio": 1.0},
    }
    chain = _build_full_chain(config)
    ctx = chain.handle(ctx)

    # DropHighMissingFeatureStep 应记录 missing_ratio
    missing_keys = [k for k in ctx.artifacts if "missing_ratio" in k]
    assert len(missing_keys) > 0

    # DropLowVarianceFeatureStep 应记录 variance
    var_keys = [k for k in ctx.artifacts if "variance" in k]
    assert len(var_keys) > 0

    # FactorQualityFilterStep 应记录 factor_stats
    assert "FactorQualityFilterStep.factor_stats" in ctx.artifacts


def test_chain_redundant_pairs_recorded():
    """DeduplicateStep 应记录冗余因子对。"""
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=100, freq="B")
    symbols = ["SH6001", "SH6002"]
    index = pd.MultiIndex.from_product([dates, symbols], names=["datetime", "instrument"])
    n = len(index)

    base = np.random.randn(n)
    X = pd.DataFrame({
        "REDUNDANT_A": base,
        "REDUNDANT_B": base + np.random.randn(n) * 0.0001,  # 几乎完全相同
        "UNIQUE": np.random.randn(n),
    }, index=index)
    y = pd.Series(np.random.randn(n), index=index)
    ctx = FilterContext(X=X, y=y)

    config = {
        "drop_missing_label": {},
        "factor_quality": {"min_abs_ic_mean": 0.0, "min_abs_icir": 0.0, "min_abs_monotonicity": 0.0, "max_sign_flip_ratio": 1.0},
        "deduplicate": {"corr_threshold": 0.8},
    }
    chain = _build_full_chain(config)
    ctx = chain.handle(ctx)

    pairs_key = "DeduplicateStep.redundant_pairs"
    assert pairs_key in ctx.artifacts
    pairs_df = ctx.artifacts[pairs_key]
    assert len(pairs_df) >= 1  # 至少有一对冗余


def test_chain_step_order_matters():
    """验证责任链按正确顺序执行：泄漏过滤在质量过滤之前。"""
    ctx = _make_full_chain_context()

    config = {
        "drop_missing_label": {},
        "drop_leakage": {"prefixes": ["LABEL"]},
        "drop_high_missing": {"threshold": 0.9},
        "drop_high_inf": {"threshold": 0.9},
        "drop_low_variance": {"variance_threshold": 1e-15, "unique_ratio_threshold": 0.001},
        "factor_quality": {"min_abs_ic_mean": 0.0, "min_abs_icir": 0.0, "min_abs_monotonicity": 0.0, "max_sign_flip_ratio": 1.0},
    }
    chain = _build_full_chain(config)
    ctx = chain.handle(ctx)

    # 验证 DropLeakageStep 在 FactorQualityFilterStep 之前
    leakage_log_idx = None
    quality_log_idx = None
    for i, log in enumerate(ctx.logs):
        if "DropLeakageStep" in log and "rows:" in log:
            leakage_log_idx = i
        if "FactorQualityFilterStep" in log and "rows:" in log:
            quality_log_idx = i

    assert leakage_log_idx is not None
    assert quality_log_idx is not None
    assert leakage_log_idx < quality_log_idx
