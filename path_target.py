"""
model/path_target.py
====================
基于 AFML Triple Barrier Method 的路径质量 Target（soft beta-neutral 版本）

公式：
    score = pnl_adj * exp(-λ * |mae| / vol)
    target = percentile_rank(score)

    其中 pnl_adj = pnl - α * β * pnl_m（soft 去 beta）

核心思想：
    1. 波动率自适应屏障：止盈/止损宽度 = k * vol，不同股票不同时期自动调整
       barrier 已经是 k * vol → pnl 已隐含 vol scaling，score 中不再除 vol
    2. 路径质量惩罚：MAE (Maximum Adverse Excursion) 越大，即使最终盈利也会被惩罚
       exp(-λ * |mae| / vol) 将惩罚归一化到波动率尺度
    3. Soft beta-neutral：在 pnl（线性量）上扣减 α * β * pnl_m，
       避免在非线性 score 上做减均值（数学上不合法）
    4. 持有期匹配：市场 pnl_m 按个股实际 TBM 退出时间计算，
       而非固定 max_holding，避免持有期错配导致过度/不足扣减
    5. 截面 percentile rank：(rank - 0.5) / N，输出 (0, 1)
       average rank 处理 tie，适配 GBM ranking loss (LambdaRank)

数据流：
    close panel (date × code)
        → rolling vol
        → triple barrier 路径扫描 → (pnl, mae, hold_len)
        → 市场 pnl（按个股持有期匹配）
        → pnl_adj = pnl - α * β * pnl_m
        → score = pnl_adj * exp(-λ * |mae| / vol)
        → MAD 缩尾 → percentile rank → target

使用示例：
    from data.load_data import load_kline_panel

    cfg = PathTargetConfig(
        vol_window=20,
        k_upper=2.0, k_lower=2.0,
        max_holding=10,
        lamda=1.0,
        beta_alpha=0.5,      # 0=不去beta, 1=完全去beta, 0.5=折中
    )
    builder = PathTargetBuilder(cfg)

    close_df = load_kline_panel('close', start_date='2024-01-01')
    market_close = load_kline_panel('close', codes=['000905.SH'])  # 中证500
    beta_df = ...  # wide panel, 与 close_df 同 shape，每个值为该股票的 beta

    target = builder.build(close_df, market_close, beta_df)
    # → pd.Series, MultiIndex(date, code), name='target', 值域 (0, 1)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import numba
import pandas as pd
import polars as pl

logger = logging.getLogger(__name__)


@dataclass
class PathTargetConfig:
    # ── 波动率 ──────────────────────────────────────────────
    vol_window: int = 20              # rolling std 回看窗口（交易日）
    vol_min: float = 1e-6             # 波动率下限，防止除零

    # ── Triple Barrier ──────────────────────────────────────
    k_upper: float = 2.0              # 止盈屏障 = entry * (1 + k_upper * vol)
    k_lower: float = 2.0              # 止损屏障 = entry * (1 - k_lower * vol)
    max_holding: int = 10             # 最大持有期（时间屏障，交易日）

    # ── 路径质量惩罚 ────────────────────────────────────────
    lamda: float = 1.0                # MAE 惩罚系数 λ，越大越惩罚颠簸路径

    # ── T+1 对齐 ────────────────────────────────────────────
    shift: int = 1                    # 信号日 T → T+shift 开始持有（A股 T+1）

    # ── 截面处理 ────────────────────────────────────────────
    winsor_std: Optional[float] = 3.0 # MAD 缩尾阈值（标准差倍数），None=不缩尾

    # ── Beta 中性化 ─────────────────────────────────────────
    beta_alpha: float = 0.5           # 去 beta 强度：0=不去, 1=完全去, 0.5=折中


# ──────────────────────────────────────────────────────────
# Numba JIT 优化函数
# ──────────────────────────────────────────────────────────

@numba.jit(nopython=True, parallel=True, cache=True)
def _barrier_scan_numba(close_np, vol_np, k_upper, k_lower, max_holding, shift):
    """
    Numba JIT 优化的 Triple Barrier 扫描。

    Parameters
    ----------
    close_np : np.ndarray, shape (T, N)
        收盘价矩阵 (float64)
    vol_np : np.ndarray, shape (T, N)
        波动率矩阵 (float64)
    k_upper, k_lower : float
        止盈/止损系数
    max_holding : int
        最大持有期
    shift : int
        T+1 偏移

    Returns
    -------
    pnl_arr, mae_arr, hold_len_arr : np.ndarray, shape (T, N)
    """
    T, N = close_np.shape
    pnl_arr = np.full((T, N), np.nan)
    mae_arr = np.full((T, N), np.nan)
    hold_len_arr = np.full((T, N), np.nan)

    for t in numba.prange(T - shift - 1):
        entry_idx = t + shift

        for n in range(N):
            entry_price = close_np[entry_idx, n]
            v = vol_np[t, n]

            if np.isnan(entry_price) or np.isnan(v) or entry_price <= 0 or v <= 0:
                continue

            upper = entry_price * (1 + k_upper * v)
            lower = entry_price * (1 - k_lower * v)

            pnl = np.nan
            mae = 0.0
            hold_len = max_holding
            exited = False

            for h in range(1, min(max_holding + 1, T - entry_idx)):
                price = close_np[entry_idx + h, n]
                if np.isnan(price):
                    continue

                ret = price / entry_price - 1

                if ret < mae:
                    mae = ret

                if price >= upper or price <= lower:
                    pnl = ret
                    hold_len = h
                    exited = True
                    break

            if not exited:
                final_idx = min(entry_idx + max_holding, T - 1)
                final_price = close_np[final_idx, n]
                if not np.isnan(final_price):
                    pnl = final_price / entry_price - 1
                    hold_len = final_idx - entry_idx

            pnl_arr[t, n] = pnl
            mae_arr[t, n] = mae
            hold_len_arr[t, n] = hold_len

    return pnl_arr, mae_arr, hold_len_arr


@numba.jit(nopython=True, cache=True)
def _compute_market_pnl_numba(mkt_price, hold_len_arr, shift):
    """
    Numba JIT 优化的市场收益计算。

    Parameters
    ----------
    mkt_price : np.ndarray, shape (T,)
        市场基准价格序列 (float64)
    hold_len_arr : np.ndarray, shape (T, N)
        持有期矩阵
    shift : int
        T+1 偏移

    Returns
    -------
    mkt_pnl : np.ndarray, shape (T, N)
        市场收益矩阵
    """
    T, N = hold_len_arr.shape
    mkt_pnl = np.full((T, N), np.nan)

    for t in range(T - shift - 1):
        entry = t + shift
        for n in range(N):
            h = hold_len_arr[t, n]
            if not np.isnan(h):
                exit_idx = min(int(entry + h), T - 1)
                mkt_pnl[t, n] = mkt_price[exit_idx] / mkt_price[entry] - 1

    return mkt_pnl


class PathTargetBuilder:
    """
    基于 Triple Barrier + MAE 惩罚 + Soft Beta-Neutral 的路径质量 Target 构建器。

    Parameters
    ----------
    cfg : PathTargetConfig

    Methods
    -------
    build(ohlc, market_close, beta_df) → pd.Series
        输入 close panel + 市场基准 + beta panel，输出 MultiIndex(date, code) target。
    """

    def __init__(self, cfg: Optional[PathTargetConfig] = None) -> None:
        self.cfg = cfg or PathTargetConfig()

    def build(
        self,
        ohlc: pl.DataFrame | dict[str, pl.DataFrame],
        market_close: pl.DataFrame,
        beta_df: pl.DataFrame,
    ) -> pd.Series:
        """
        构建 path-dependent target。

        Parameters
        ----------
        ohlc : pl.DataFrame 或 dict[str, pl.DataFrame]
            close panel (wide)，第一列为 date，其余列为股票代码
        market_close : pl.DataFrame
            市场基准收盘价 (wide)，第一列 date，第二列为基准价格（如中证500）
        beta_df : pl.DataFrame
            beta panel (wide)，与 close_df 同 shape，每个值为该股票当日的 beta

        Returns
        -------
        pd.Series, MultiIndex(date, code), 值域 (0, 1)
        """
        cfg = self.cfg
        close_df = ohlc["close"] if isinstance(ohlc, dict) else ohlc

        date_col = close_df.columns[0]
        codes = [c for c in close_df.columns if c != date_col]

        dates = close_df[date_col].to_list()
        close_np = close_df.select(codes).to_numpy()

        # ── Step 1: 波动率（rolling std of log return）─────────
        log_ret = np.diff(np.log(close_np), axis=0)
        log_ret = np.vstack([np.zeros((1, log_ret.shape[1])), log_ret])

        vol_np = (
            pd.DataFrame(log_ret)
            .rolling(cfg.vol_window, min_periods=cfg.vol_window // 2)
            .std()
            .values
        )
        vol_np = np.clip(vol_np, cfg.vol_min, None)

        # ── Step 2: Triple Barrier 路径扫描 ─────────────────────
        pnl_arr, mae_arr, hold_len_arr = self._barrier_scan(close_np, vol_np, cfg)

        # ── Step 3: 市场 pnl（匹配个股持有期）──────────────────
        mkt_col = market_close.columns[1]
        mkt_np = market_close.select(mkt_col).to_numpy().flatten()
        mkt_pnl_arr = self._compute_market_pnl_matched(mkt_np, hold_len_arr, cfg)

        # ── Step 4: Soft beta-neutral ───────────────────────────
        #   pnl_adj = pnl_i - α * β_i * pnl_m
        #   在线性 pnl 上扣减，保证非线性变换前语义正确
        beta_np = beta_df.select(codes).to_numpy()
        pnl_adj = pnl_arr - cfg.beta_alpha * beta_np * mkt_pnl_arr

        # ── Step 5: quality score ───────────────────────────────
        #   score = pnl_adj * exp(-λ * |mae| / vol)
        score_df = self._compute_score(dates, codes, date_col, pnl_adj, mae_arr, vol_np)

        # ── Step 6: MAD 缩尾 + percentile rank ─────────────────
        target = self._rank_cross_section(score_df, codes, date_col)
        return target.dropna()

    # ──────────────────────────────────────────────────────────
    # 内部方法
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _barrier_scan(close_np, vol_np, cfg):
        """
        Triple Barrier 路径扫描。

        对每个信号日 t，从 T+shift 开始持有，扫描未来路径：
        - 触碰上界（止盈）或下界（止损）→ 提前退出
        - 都没触碰 → 在 max_holding 到期时退出

        Returns
        -------
        pnl_arr : (T, N) 退出时的收益率
        mae_arr : (T, N) 持有期内最大不利偏移（≤0）
        hold_len_arr : (T, N) 实际持有天数
        """
        T, N = close_np.shape
        pnl_arr = np.full((T, N), np.nan)
        mae_arr = np.full((T, N), np.nan)
        hold_len_arr = np.full((T, N), np.nan)

        for t in range(T - cfg.shift - 1):
            entry_idx = t + cfg.shift
            entry_price = close_np[entry_idx]
            v = vol_np[t]                              # 信号日的 vol

            upper = entry_price * (1 + cfg.k_upper * v)
            lower = entry_price * (1 - cfg.k_lower * v)

            end_idx = min(entry_idx + cfg.max_holding, T - 1)
            if entry_idx >= end_idx:
                continue

            future = close_np[entry_idx + 1:end_idx + 1]  # (H, N)
            returns = future / entry_price - 1
            H = returns.shape[0]

            # 屏障触发检测
            hit_up = future >= upper
            hit_dn = future <= lower

            up_idx = np.where(hit_up.any(axis=0), np.argmax(hit_up, axis=0), H)
            dn_idx = np.where(hit_dn.any(axis=0), np.argmax(hit_dn, axis=0), H)

            exit_step = np.minimum(np.minimum(up_idx, dn_idx), H - 1)

            idx = np.arange(N)
            pnl_arr[t] = returns[exit_step, idx]
            hold_len_arr[t] = exit_step + 1            # 0-based → 天数

            # MAE: 只看 exit 之前的路径，无回撤时 mae=0
            mask = np.arange(H)[:, None] <= exit_step[None, :]
            masked = np.where(mask, returns, np.inf)
            mae_arr[t] = np.minimum(masked.min(axis=0), 0.0)

        return pnl_arr, mae_arr, hold_len_arr

    @staticmethod
    def _compute_market_pnl_matched(mkt_price, hold_len_arr, cfg):
        """
        计算与每支个股持有期匹配的市场收益。

        个股 t 日信号、持有 h 天 → 市场 pnl = mkt[entry+h] / mkt[entry] - 1
        这样 pnl_i - α * β * pnl_m 中两端持有期一致，避免错配。
        """
        T, N = hold_len_arr.shape
        mkt_pnl = np.full((T, N), np.nan)

        for t in range(T - cfg.shift - 1):
            entry = t + cfg.shift
            h = hold_len_arr[t]                        # (N,) 每支股票的持有天数

            valid = ~np.isnan(h)
            if not valid.any():
                continue

            exit_indices = (entry + h[valid]).astype(int)
            exit_indices = np.clip(exit_indices, 0, T - 1)

            mkt_pnl[t, valid] = mkt_price[exit_indices] / mkt_price[entry] - 1

        return mkt_pnl

    def _compute_score(self, dates, codes, date_col, pnl_arr, mae_arr, vol_np):
        """
        quality score = pnl_adj * exp(-λ * |mae| / vol)

        pnl_adj 已经过 beta 调整，mae 只取负向偏移（无回撤时为0，不惩罚）。
        """
        cfg = self.cfg

        df = pl.DataFrame({
            date_col: dates,
            **{f"pnl__{c}": pnl_arr[:, i] for i, c in enumerate(codes)},
            **{f"mae__{c}": mae_arr[:, i] for i, c in enumerate(codes)},
            **{f"vol__{c}": vol_np[:, i] for i, c in enumerate(codes)},
        })

        exprs = []
        for c in codes:
            exprs.append(
                (
                    pl.col(f"pnl__{c}") *
                    (-cfg.lamda * pl.col(f"mae__{c}").abs() / pl.col(f"vol__{c}")).exp()
                ).alias(f"score__{c}")
            )

        return df.select(pl.col(date_col), *exprs)

    def _rank_cross_section(self, score_df, codes, date_col):
        """
        截面 MAD 缩尾 + percentile rank。

        - MAD 缩尾：median ± k * 1.4826 * MAD，比 std 更鲁棒
        - rank("average")：tie 共享均值排名，适配 GBM LambdaRank
        - (rank - 0.5) / N：输出 (0, 1)，避免极端 0/1 边界
        """
        cfg = self.cfg
        cols = [f"score__{c}" for c in codes]

        # MAD 缩尾
        if cfg.winsor_std:
            k = cfg.winsor_std * 1.4826
            # 使用 horizontal 计算中位数和 MAD
            med = pl.concat_list([pl.col(c) for c in cols]).list.median()
            mad = pl.concat_list([(pl.col(c) - med).abs() for c in cols]).list.median()
            lo = med - k * mad
            hi = med + k * mad
            score_df = score_df.with_columns([pl.col(c).clip(lo, hi) for c in cols])

        # unpivot → long 格式
        score_df = score_df.with_row_index("__id")

        long = score_df.unpivot(
            on=cols,
            index=["__id", date_col],
            variable_name="k",
            value_name="score",
        ).with_columns(
            pl.col("k").str.replace("score__", "").alias("code")
        )

        # percentile rank
        long = long.with_columns(
            pl.col("score").rank("average").over("__id").alias("r"),
            pl.col("score").count().over("__id").alias("n"),
        )
        long = long.with_columns(
            ((pl.col("r") - 0.5) / pl.col("n")).alias("target")
        )

        out = (
            long.select(date_col, "code", "target")
            .sort(date_col, "code")
            .to_pandas()
        )
        out[date_col] = pd.to_datetime(out[date_col])
        return out.set_index([date_col, "code"])["target"]
