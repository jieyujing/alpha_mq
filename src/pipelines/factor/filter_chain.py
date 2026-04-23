
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Any, Tuple

import numpy as np
import pandas as pd


# =========================================================
# Context
# =========================================================

@dataclass
class FilterContext:
    """
    责任链上下文：
    - X: 特征矩阵，index 一般为 MultiIndex(date, instrument)
    - y: 标签，index 与 X 对齐
    - meta: 额外样本级信息（如是否停牌、是否涨跌停、是否可交易）
    - feature_groups: 可选，记录特征分组/聚类信息
    - logs: 每一步日志
    - removed_rows / removed_features: 各步骤删除记录
    - artifacts: 中间统计产物
    """
    X: pd.DataFrame
    y: pd.Series
    meta: Optional[pd.DataFrame] = None

    feature_groups: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    removed_rows: Dict[str, List[Any]] = field(default_factory=dict)
    removed_features: Dict[str, List[str]] = field(default_factory=dict)
    artifacts: Dict[str, Any] = field(default_factory=dict)

    def log(self, message: str) -> None:
        self.logs.append(message)

    def align(self) -> None:
        """确保 X / y / meta 索引对齐。"""
        common_index = self.X.index.intersection(self.y.index)
        self.X = self.X.loc[common_index]
        self.y = self.y.loc[common_index]
        if self.meta is not None:
            common_index = common_index.intersection(self.meta.index)
            self.X = self.X.loc[common_index]
            self.y = self.y.loc[common_index]
            self.meta = self.meta.loc[common_index]

    @property
    def n_rows(self) -> int:
        return len(self.X)

    @property
    def n_features(self) -> int:
        return self.X.shape[1]


# =========================================================
# Chain base
# =========================================================

class BaseFilterStep:
    """
    责任链基类：
    - process: 子类实现核心逻辑
    - handle: 执行当前节点，再传递到下一个节点
    """
    def __init__(self, name: Optional[str] = None):
        self.name = name or self.__class__.__name__
        self._next: Optional["BaseFilterStep"] = None

    def set_next(self, step: "BaseFilterStep") -> "BaseFilterStep":
        self._next = step
        return step

    def handle(self, ctx: FilterContext) -> FilterContext:
        before_rows, before_cols = ctx.n_rows, ctx.n_features
        ctx = self.process(ctx)
        after_rows, after_cols = ctx.n_rows, ctx.n_features
        ctx.log(
            f"[{self.name}] rows: {before_rows} -> {after_rows}, "
            f"features: {before_cols} -> {after_cols}"
        )
        if self._next is not None:
            return self._next.handle(ctx)
        return ctx

    def process(self, ctx: FilterContext) -> FilterContext:
        raise NotImplementedError


# =========================================================
# Helpers
# =========================================================

def _drop_rows(ctx: FilterContext, step_name: str, mask_keep: pd.Series, reason: str) -> FilterContext:
    """
    根据 mask_keep 保留样本。
    mask_keep: True 表示保留
    """
    if not isinstance(mask_keep, pd.Series):
        mask_keep = pd.Series(mask_keep, index=ctx.X.index)

    removed_index = ctx.X.index[~mask_keep].tolist()

    ctx.X = ctx.X.loc[mask_keep]
    ctx.y = ctx.y.loc[mask_keep]
    if ctx.meta is not None:
        ctx.meta = ctx.meta.loc[mask_keep]

    ctx.removed_rows[step_name] = removed_index
    ctx.log(f"[{step_name}] removed rows={len(removed_index)} | reason={reason}")
    return ctx


def _drop_features(ctx: FilterContext, step_name: str, features_to_drop: Sequence[str], reason: str) -> FilterContext:
    features_to_drop = [f for f in features_to_drop if f in ctx.X.columns]
    if not features_to_drop:
        ctx.removed_features[step_name] = []
        ctx.log(f"[{step_name}] removed features=0 | reason={reason}")
        return ctx

    ctx.X = ctx.X.drop(columns=features_to_drop)
    ctx.removed_features[step_name] = list(features_to_drop)
    ctx.log(f"[{step_name}] removed features={len(features_to_drop)} | reason={reason}")
    return ctx


def _safe_spearman_corr(a: pd.Series, b: pd.Series) -> float:
    df = pd.concat([a, b], axis=1).dropna()
    if len(df) < 5:
        return np.nan
    return df.iloc[:, 0].corr(df.iloc[:, 1], method="spearman")


def _rank_ic_by_date(
    X: pd.DataFrame,
    y: pd.Series,
    min_obs: int = 5
) -> pd.DataFrame:
    """
    计算每个特征按日期的截面 Rank IC。
    要求 X.index / y.index 为 MultiIndex(date, instrument) 或至少第 0 层是 date。
    返回:
        index=date
        columns=features
    """
    if not isinstance(X.index, pd.MultiIndex):
        raise ValueError("X.index must be MultiIndex(date, instrument) for cross-sectional Rank IC.")

    date_level = 0
    feature_names = list(X.columns)
    ic_records = []

    for dt, xg in X.groupby(level=date_level):
        yg = y.loc[xg.index]
        row = {}
        for col in feature_names:
            df = pd.concat([xg[col], yg], axis=1).dropna()
            if len(df) < min_obs:
                row[col] = np.nan
            else:
                row[col] = df.iloc[:, 0].corr(df.iloc[:, 1], method="spearman")
        ic_records.append(pd.Series(row, name=dt))

    ic_df = pd.DataFrame(ic_records).sort_index()
    return ic_df


def _compute_monotonicity_proxy(
    X: pd.DataFrame,
    y: pd.Series,
    n_bins: int = 5,
    min_obs: int = 20
) -> pd.Series:
    """
    一个轻量版“单调性代理指标”：
    对每个特征，逐日按因子值分箱，计算各箱 label 均值，
    再对 [bin_id, mean_label] 做 Spearman 相关，最后对所有日期取平均。

    返回每个特征的 monotonicity score。
    """
    if not isinstance(X.index, pd.MultiIndex):
        raise ValueError("X.index must be MultiIndex(date, instrument).")

    results = {}
    date_level = 0

    for col in X.columns:
        scores = []
        for dt, xg in X[[col]].groupby(level=date_level):
            yg = y.loc[xg.index]
            df = pd.concat([xg[col], yg.rename("label")], axis=1).dropna()
            if len(df) < min_obs:
                continue

            try:
                # duplicates='drop' 避免离散值导致 qcut 失败
                df["bin"] = pd.qcut(df[col], q=n_bins, labels=False, duplicates="drop")
            except ValueError:
                continue

            grp = df.groupby("bin")["label"].mean()
            if len(grp) < 3:
                continue

            s = grp.reset_index()
            score = s["bin"].corr(s["label"], method="spearman")
            scores.append(score)

        results[col] = np.nanmean(scores) if len(scores) > 0 else np.nan

    return pd.Series(results, name="monotonicity")


# =========================================================
# Step 1: 删除 label 缺失样本
# =========================================================

class DropMissingLabelStep(BaseFilterStep):
    def process(self, ctx: FilterContext) -> FilterContext:
        mask_keep = ~ctx.y.isna()
        return _drop_rows(ctx, self.name, mask_keep, "label is not null")


# =========================================================
# Step 2: 删除不可交易样本
# =========================================================

class DropUntradableSampleStep(BaseFilterStep):
    """
    通过可注入规则决定哪些样本不可交易。
    rule(ctx) -> pd.Series[bool], True 表示可保留
    """
    def __init__(
        self,
        tradable_rule: Callable[[FilterContext], pd.Series],
        name: Optional[str] = None
    ):
        super().__init__(name)
        self.tradable_rule = tradable_rule

    def process(self, ctx: FilterContext) -> FilterContext:
        mask_keep = self.tradable_rule(ctx)
        return _drop_rows(ctx, self.name, mask_keep, "sample is tradable")


# =========================================================
# Step 3: 删除缺失率 > threshold 的特征
# =========================================================

class DropHighMissingFeatureStep(BaseFilterStep):
    def __init__(self, threshold: float = 0.3, name: Optional[str] = None):
        super().__init__(name)
        self.threshold = threshold

    def process(self, ctx: FilterContext) -> FilterContext:
        missing_ratio = ctx.X.isna().mean()
        to_drop = missing_ratio[missing_ratio > self.threshold].index.tolist()
        ctx.artifacts[f"{self.name}.missing_ratio"] = missing_ratio.sort_values(ascending=False)
        return _drop_features(ctx, self.name, to_drop, f"missing_ratio > {self.threshold}")


# =========================================================
# Step 4: 删除 inf 占比异常特征
# =========================================================

class DropHighInfFeatureStep(BaseFilterStep):
    def __init__(self, threshold: float = 0.01, name: Optional[str] = None):
        super().__init__(name)
        self.threshold = threshold

    def process(self, ctx: FilterContext) -> FilterContext:
        inf_ratio = np.isinf(ctx.X.to_numpy(dtype=float)).mean(axis=0)
        inf_ratio = pd.Series(inf_ratio, index=ctx.X.columns)
        to_drop = inf_ratio[inf_ratio > self.threshold].index.tolist()

        # 顺便把 inf 替换成 nan，方便后续流程
        ctx.X = ctx.X.replace([np.inf, -np.inf], np.nan)

        ctx.artifacts[f"{self.name}.inf_ratio"] = inf_ratio.sort_values(ascending=False)
        return _drop_features(ctx, self.name, to_drop, f"inf_ratio > {self.threshold}")


# =========================================================
# Step 5: 删除常数列 / 低方差列
# =========================================================

class DropLowVarianceFeatureStep(BaseFilterStep):
    def __init__(
        self,
        variance_threshold: float = 1e-8,
        unique_ratio_threshold: float = 0.01,
        name: Optional[str] = None
    ):
        super().__init__(name)
        self.variance_threshold = variance_threshold
        self.unique_ratio_threshold = unique_ratio_threshold

    def process(self, ctx: FilterContext) -> FilterContext:
        nunique_ratio = ctx.X.nunique(dropna=True) / max(len(ctx.X), 1)
        variance = ctx.X.var(numeric_only=True)

        low_unique = nunique_ratio[nunique_ratio <= self.unique_ratio_threshold].index.tolist()
        low_var = variance[variance <= self.variance_threshold].index.tolist()

        to_drop = sorted(set(low_unique) | set(low_var))

        ctx.artifacts[f"{self.name}.nunique_ratio"] = nunique_ratio.sort_values()
        ctx.artifacts[f"{self.name}.variance"] = variance.sort_values()

        return _drop_features(
            ctx,
            self.name,
            to_drop,
            (
                f"nunique_ratio <= {self.unique_ratio_threshold} "
                f"or variance <= {self.variance_threshold}"
            ),
        )


# =========================================================
# Step 6: label 同构 / 泄漏审计
# =========================================================

class LeakageAuditStep(BaseFilterStep):
    """
    这里不强行写死规则，而是注入一个审计函数：
    audit_fn(ctx) -> List[str]
    返回需要删除的特征名
    """
    def __init__(
        self,
        audit_fn: Callable[[FilterContext], List[str]],
        name: Optional[str] = None
    ):
        super().__init__(name)
        self.audit_fn = audit_fn

    def process(self, ctx: FilterContext) -> FilterContext:
        to_drop = self.audit_fn(ctx)
        return _drop_features(ctx, self.name, to_drop, "leakage / label-isomorphic features")


# =========================================================
# Step 7-8: 单因子 Rank IC / ICIR / 单调性过滤
# =========================================================

class FactorQualityFilterStep(BaseFilterStep):
    def __init__(
        self,
        min_abs_ic_mean: float = 0.005,
        min_abs_icir: float = 0.1,
        min_abs_monotonicity: float = 0.05,
        max_sign_flip_ratio: float = 0.45,
        min_obs_per_date: int = 5,
        name: Optional[str] = None
    ):
        super().__init__(name)
        self.min_abs_ic_mean = min_abs_ic_mean
        self.min_abs_icir = min_abs_icir
        self.min_abs_monotonicity = min_abs_monotonicity
        self.max_sign_flip_ratio = max_sign_flip_ratio
        self.min_obs_per_date = min_obs_per_date

    def process(self, ctx: FilterContext) -> FilterContext:
        if not isinstance(ctx.X.index, pd.MultiIndex):
            raise ValueError(
                f"[{self.name}] requires MultiIndex(date, instrument) to compute cross-sectional IC."
            )

        ic_df = _rank_ic_by_date(ctx.X, ctx.y, min_obs=self.min_obs_per_date)
        ic_mean = ic_df.mean(axis=0)
        ic_std = ic_df.std(axis=0)
        icir = ic_mean / ic_std.replace(0, np.nan)

        # 方向不稳定：IC 符号翻转比例
        sign_flip_ratio = {}
        for col in ic_df.columns:
            s = ic_df[col].dropna()
            if len(s) < 3:
                sign_flip_ratio[col] = np.nan
                continue
            signs = np.sign(s)
            flips = (signs != signs.shift(1)).sum()
            sign_flip_ratio[col] = flips / max(len(signs) - 1, 1)
        sign_flip_ratio = pd.Series(sign_flip_ratio, name="sign_flip_ratio")

        monotonicity = _compute_monotonicity_proxy(ctx.X, ctx.y)

        stats = pd.DataFrame({
            "ic_mean": ic_mean,
            "ic_std": ic_std,
            "icir": icir,
            "sign_flip_ratio": sign_flip_ratio,
            "monotonicity": monotonicity,
        })

        ctx.artifacts[f"{self.name}.factor_stats"] = stats.sort_values("ic_mean")

        bad_mask = (
            (stats["ic_mean"].abs() < self.min_abs_ic_mean)
            | (stats["icir"].abs() < self.min_abs_icir)
            | (stats["monotonicity"].abs() < self.min_abs_monotonicity)
            | (stats["sign_flip_ratio"] > self.max_sign_flip_ratio)
        )

        to_drop = stats.index[bad_mask.fillna(True)].tolist()

        return _drop_features(
            ctx,
            self.name,
            to_drop,
            (
                f"|ic_mean| < {self.min_abs_ic_mean} or "
                f"|icir| < {self.min_abs_icir} or "
                f"|monotonicity| < {self.min_abs_monotonicity} or "
                f"sign_flip_ratio > {self.max_sign_flip_ratio}"
            ),
        )

