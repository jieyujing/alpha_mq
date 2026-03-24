# factor/triple_barrier.py
"""
Triple Barrier 目标 DataLoader

基于 AFML Triple Barrier Method 的路径质量 Target 构建。
继承 qlib 的 QlibDataLoader，将 Triple Barrier 逻辑封装在 loader 内部。

数据流:
    close panel (date × code)
        → rolling vol
        → triple barrier 路径扫描 → (pnl, mae, hold_len)
        → score = pnl_adj * exp(-λ * |mae| / vol)
        → MAD 缩尾 → percentile rank → target
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TripleBarrierConfig:
    """Triple Barrier 配置参数"""

    # 波动率参数
    vol_window: int = 20
    vol_min: float = 1e-6

    # Triple Barrier 参数
    k_upper: float = 2.0  # 止盈屏障系数
    k_lower: float = 2.0  # 止损屏障系数
    max_holding: int = 10  # 最大持有期

    # 路径质量惩罚
    lamda: float = 1.0  # MAE 惩罚系数

    # T+1 对齐
    shift: int = 1

    # 截面处理
    winsor_std: Optional[float] = 3.0

    # Beta 中性化
    beta_alpha: float = 0.5


class TripleBarrierDataLoader:
    """
    Triple Barrier 目标数据加载器。

    生成基于 Triple Barrier Method 的路径质量 Target。
    输出格式: pd.Series, MultiIndex(date, code), 值域 (0, 1)
    """

    def __init__(self, config: Optional[TripleBarrierConfig] = None) -> None:
        self.config = config or TripleBarrierConfig()

    def load(
        self,
        close_df: pd.DataFrame,
        market_close: Optional[pd.Series] = None,
        beta_df: Optional[pd.DataFrame] = None,
    ) -> pd.Series:
        """
        构建 Triple Barrier Target。

        Parameters
        ----------
        close_df : pd.DataFrame
            收盘价面板，index=date, columns=code
        market_close : pd.Series, optional
            市场基准收盘价，index=date
        beta_df : pd.DataFrame, optional
            Beta 面板，index=date, columns=code

        Returns
        -------
        pd.Series
            MultiIndex(date, code), 值域 (0, 1)
        """
        cfg = self.config

        # Step 1: 计算波动率
        log_ret = np.log(close_df).diff()
        vol = log_ret.rolling(cfg.vol_window, min_periods=cfg.vol_window // 2).std()
        vol = vol.clip(lower=cfg.vol_min)

        # Step 2: Triple Barrier 路径扫描
        pnl_arr, mae_arr, hold_len_arr = self._barrier_scan(close_df.values, vol.values, cfg)

        # Step 3: 计算 score
        # score = pnl * exp(-λ * |mae| / vol)
        mae_normalized = np.abs(mae_arr) / vol.values
        score_arr = pnl_arr * np.exp(-cfg.lamda * mae_normalized)

        # Step 4: 转换为 DataFrame
        score_df = pd.DataFrame(score_arr, index=close_df.index, columns=close_df.columns)

        # Step 5: 截面 percentile rank
        target = self._rank_cross_section(score_df)

        return target.dropna()

    @staticmethod
    def _barrier_scan(close_np: np.ndarray, vol_np: np.ndarray, cfg: TripleBarrierConfig):
        """
        Triple Barrier 路径扫描。

        Returns
        -------
        pnl_arr : (T, N) 退出时的收益率
        mae_arr : (T, N) 持有期内最大不利偏移
        hold_len_arr : (T, N) 实际持有天数
        """
        T, N = close_np.shape
        pnl_arr = np.full((T, N), np.nan)
        mae_arr = np.full((T, N), np.nan)
        hold_len_arr = np.full((T, N), np.nan)

        for t in range(T - cfg.shift - 1):
            entry_idx = t + cfg.shift
            entry_price = close_np[entry_idx]
            v = vol_np[t]

            upper = entry_price * (1 + cfg.k_upper * v)
            lower = entry_price * (1 - cfg.k_lower * v)

            end_idx = min(entry_idx + cfg.max_holding, T - 1)
            if entry_idx >= end_idx:
                continue

            future = close_np[entry_idx + 1:end_idx + 1]
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
            hold_len_arr[t] = exit_step + 1

            # MAE
            mask = np.arange(H)[:, None] <= exit_step[None, :]
            masked = np.where(mask, returns, np.inf)
            mae_arr[t] = np.minimum(masked.min(axis=0), 0.0)

        return pnl_arr, mae_arr, hold_len_arr

    def _rank_cross_section(self, score_df: pd.DataFrame) -> pd.Series:
        """
        截面 MAD 缩尾 + percentile rank。
        """
        cfg = self.config

        # MAD 缩尾
        if cfg.winsor_std:
            median = score_df.median(axis=1)
            mad = (score_df.sub(median, axis=0)).abs().median(axis=1)
            lo = median - cfg.winsor_std * 1.4826 * mad
            hi = median + cfg.winsor_std * 1.4826 * mad
            score_df = score_df.clip(lower=lo, upper=hi, axis=0)

        # Percentile rank
        rank = score_df.rank(axis=1, method="average")
        count = score_df.notna().sum(axis=1)
        target = (rank.sub(0.5)).div(count, axis=0)

        # 转换为 long format
        target = target.stack()
        target.name = "target"

        return target