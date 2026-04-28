# src/pipelines/factor/factor_loader.py
import logging
import os
import numpy as np
import pandas as pd
import polars as pl
from typing import Optional, List


def _rolling_percentile_rank(s: pl.Series) -> pl.Series:
    """Percentile rank of last value in rolling window (Qlib Rank with pct=True)."""
    n = len(s)
    last_val = s[-1]
    if pd.isna(last_val):
        return pl.Series([np.nan] * n, dtype=pl.Float64)
    valid = s.drop_nulls()
    if len(valid) == 0:
        return pl.Series([np.nan] * n, dtype=pl.Float64)
    rank_pct = (valid <= last_val).sum() / len(valid)
    return pl.Series([rank_pct] * n, dtype=pl.Float64)


def _rolling_imax(s: pl.Series) -> pl.Series:
    """1-based index of max value divided by window size (Qlib IdxMax / w)."""
    return pl.Series([(s.arg_max() + 1) / len(s)] * len(s), dtype=pl.Float64)


def _rolling_imin(s: pl.Series) -> pl.Series:
    """1-based index of min value divided by window size (Qlib IdxMin / w)."""
    return pl.Series([(s.arg_min() + 1) / len(s)] * len(s), dtype=pl.Float64)


def _rolling_imxd(high: pl.Series, low: pl.Series) -> pl.Series:
    """(IdxMax(high) - IdxMin(low)) / w (Qlib IMXD / w)."""
    n = len(high)
    val = ((high.arg_max() + 1) - (low.arg_min() + 1)) / n
    return pl.Series([val] * n, dtype=pl.Float64)


class FactorLoader:
    """
    适配器模式：Qlib Alpha158 加载器。
    通过 Polars 表达式树完整复刻 Qlib Alpha158 的 158 条因子定义。
    """

    def __init__(self, parquet_input: str, **kwargs):
        self.parquet_input = parquet_input

    def _build_all_alpha158_exprs(self):
        """
        全量复刻 Alpha158 定义。
        包含: KBAR(9), PRICE(4), ROLLING(145) = 158 features.
        """
        windows = [5, 10, 20, 30, 60]
        c_close, c_open, c_high, c_low, c_vol = pl.col("close"), pl.col("open"), pl.col("high"), pl.col("low"), pl.col("volume")

        # 1. KBAR (9)
        exprs = [
            ((c_close - c_open) / (c_open + 1e-8)).alias("KMID"),
            ((c_high - c_low) / (c_open + 1e-8)).alias("KLEN"),
            ((c_close - c_open) / (c_high - c_low + 1e-8)).alias("KMID2"),
            ((c_high - pl.max_horizontal(c_open, c_close)) / (c_open + 1e-8)).alias("KUP"),
            ((c_high - pl.max_horizontal(c_open, c_close)) / (c_high - c_low + 1e-8)).alias("KUP2"),
            ((pl.min_horizontal(c_open, c_close) - c_low) / (c_open + 1e-8)).alias("KLOW"),
            ((pl.min_horizontal(c_open, c_close) - c_low) / (c_high - c_low + 1e-8)).alias("KLOW2"),
            ((c_close - c_low) / (c_high - c_low + 1e-8)).alias("KSFT"),
            ((2 * c_close - c_high - c_low) / (c_high - c_low + 1e-8)).alias("KSFT2"),
        ]

        # 2. PRICE (4)
        exprs += [
            (c_open / c_close - 1).alias("OPEN0"),
            (c_high / c_close - 1).alias("HIGH0"),
            (c_low / c_close - 1).alias("LOW0"),
            (pl.col("amount") / (c_vol * 100 + 1e-8) / c_close - 1).alias("VWAP0"),
        ]

        # 3. ROLLING (145)
        for w in windows:
            # 收益率与偏离 (5)
            exprs.append((c_close / c_close.shift(w).over("instrument") - 1).alias(f"ROC{w}"))
            exprs.append((c_close.rolling_mean(window_size=w).over("instrument") / c_close - 1).alias(f"MA{w}"))
            exprs.append((c_close.rolling_std(window_size=w).over("instrument") / c_close).alias(f"STD{w}"))

            # 极值与分位数 (10)
            exprs.append((c_close.rolling_max(window_size=w).over("instrument") / c_close - 1).alias(f"MAX{w}"))
            exprs.append((c_close.rolling_min(window_size=w).over("instrument") / c_close - 1).alias(f"MIN{w}"))
            # QTLU: Quantile($close, w, 0.8)/$close
            exprs.append((c_close.rolling_quantile(quantile=0.8, window_size=w, min_samples=1).over("instrument") / c_close).alias(f"QTLU{w}"))
            # QTLD: Quantile($close, w, 0.2)/$close
            exprs.append((c_close.rolling_quantile(quantile=0.2, window_size=w, min_samples=1).over("instrument") / c_close).alias(f"QTLD{w}"))
            # RANK: Rank($close, w) — percentile rank within window
            exprs.append(
                c_close.rolling_map(_rolling_percentile_rank, window_size=w, min_samples=1)
                .over("instrument").alias(f"RANK{w}")
            )

            # 线性回归 (BETA, RSQR, RESI) (10)
            x = np.arange(w)
            x_mean = x.mean()
            x_var = ((x - x_mean)**2).sum()
            y_mean = c_close.rolling_mean(window_size=w).over("instrument")
            xy_mean = (pl.col("t") * c_close).rolling_mean(window_size=w).over("instrument")
            slope = (xy_mean - x_mean * y_mean) * w / (x_var + 1e-8)
            exprs.append(slope.alias(f"BETA{w}"))

            if hasattr(pl, "rolling_corr"):
                corr = pl.rolling_corr(pl.col("t"), c_close, window_size=w).over("instrument")
                exprs.append((corr**2).alias(f"RSQR{w}"))
                exprs.append((c_close.rolling_std(window_size=w).over("instrument") * (1 - corr**2).sqrt()).alias(f"RESI{w}"))
            else:
                exprs.append(pl.lit(0).alias(f"RSQR{w}"))
                exprs.append(pl.lit(0).alias(f"RESI{w}"))

            # RSV
            exprs.append(((c_close - c_close.rolling_min(window_size=w).over("instrument")) /
                          (c_close.rolling_max(window_size=w).over("instrument") - c_close.rolling_min(window_size=w).over("instrument") + 1e-8)).alias(f"RSV{w}"))

            # 极值位置 (IdxMax/IdxMin 对应 Qlib 原始定义，1-based 索引 / w)
            exprs.append(
                c_high.rolling_map(_rolling_imax, window_size=w, min_samples=1)
                .over("instrument").alias(f"IMAX{w}")
            )
            exprs.append(
                c_low.rolling_map(_rolling_imin, window_size=w, min_samples=1)
                .over("instrument").alias(f"IMIN{w}")
            )
            # IMXD = (IdxMax(high) - IdxMin(low)) / w — 在后续 with_columns 中计算
            # 此处留占位，在 load_alpha158 中二次计算
            exprs.append(pl.lit(0).alias(f"IMXD{w}"))

            # 相关性
            if hasattr(pl, "rolling_corr"):
                exprs.append(pl.rolling_corr(c_close, (c_vol + 1).log(), window_size=w).over("instrument").alias(f"CORR{w}"))
                exprs.append(pl.rolling_corr(c_close / c_close.shift(1).over("instrument"),
                                            (c_vol / c_vol.shift(1).over("instrument") + 1).log(),
                                            window_size=w).over("instrument").alias(f"CORD{w}"))

            # 资金流向计数
            is_up = (c_close > c_close.shift(1).over("instrument")).cast(pl.Float32)
            is_down = (c_close < c_close.shift(1).over("instrument")).cast(pl.Float32)
            exprs.append(is_up.rolling_mean(window_size=w).over("instrument").alias(f"CNTP{w}"))
            exprs.append(is_down.rolling_mean(window_size=w).over("instrument").alias(f"CNTN{w}"))
            exprs.append((is_up.rolling_mean(window_size=w).over("instrument") - is_down.rolling_mean(window_size=w).over("instrument")).alias(f"CNTD{w}"))

            # 收益率累加
            diff = (c_close - c_close.shift(1).over("instrument"))
            abs_diff_sum = diff.abs().rolling_sum(window_size=w).over("instrument") + 1e-12
            exprs.append((pl.max_horizontal(0, diff).rolling_sum(window_size=w).over("instrument") / abs_diff_sum).alias(f"SUMP{w}"))
            exprs.append((pl.max_horizontal(0, -diff).rolling_sum(window_size=w).over("instrument") / abs_diff_sum).alias(f"SUMN{w}"))
            exprs.append(((pl.max_horizontal(0, diff).rolling_sum(window_size=w).over("instrument") - pl.max_horizontal(0, -diff).rolling_sum(window_size=w).over("instrument")) / abs_diff_sum).alias(f"SUMD{w}"))

            # 成交量滚动特征
            exprs.append((c_vol.rolling_mean(window_size=w).over("instrument") / (c_vol + 1e-8)).alias(f"VMA{w}"))
            exprs.append((c_vol.rolling_std(window_size=w).over("instrument") / (c_vol + 1e-8)).alias(f"VSTD{w}"))

            v_diff = (c_vol - c_vol.shift(1).over("instrument"))
            v_abs_diff_sum = v_diff.abs().rolling_sum(window_size=w).over("instrument") + 1e-12
            exprs.append((pl.max_horizontal(0, v_diff).rolling_sum(window_size=w).over("instrument") / v_abs_diff_sum).alias(f"VSUMP{w}"))
            exprs.append((pl.max_horizontal(0, -v_diff).rolling_sum(window_size=w).over("instrument") / v_abs_diff_sum).alias(f"VSUMN{w}"))
            exprs.append(((pl.max_horizontal(0, v_diff).rolling_sum(window_size=w).over("instrument") - pl.max_horizontal(0, -v_diff).rolling_sum(window_size=w).over("instrument")) / v_abs_diff_sum).alias(f"VSUMD{w}"))

            # WVMA: Std(Abs($close/Ref($close,1)-1)*$volume, w) / (Mean(..., w) + 1e-12)
            ret_abs_vol = (c_close / c_close.shift(1).over("instrument") - 1).abs() * c_vol
            exprs.append(
                (ret_abs_vol.rolling_std(window_size=w).over("instrument") /
                 (ret_abs_vol.rolling_mean(window_size=w).over("instrument") + 1e-12)).alias(f"WVMA{w}")
            )

        return exprs

    def _build_imxd_exprs(self):
        """构建 IMXD 表达式 — 需要引用已计算的 IMAX/IMIN 列。"""
        windows = [5, 10, 20, 30, 60]
        return [(pl.col(f"IMAX{w}") - pl.col(f"IMIN{w}")).alias(f"IMXD{w}") for w in windows]

    def load_alpha158(
        self,
        instruments: str,
        start: str,
        end: str,
        **kwargs
    ) -> pd.DataFrame:
        import qlib
        from qlib.data.dataset.handler import DataHandlerLP
        from qlib.data.dataset.loader import StaticDataLoader

        logging.info("Engine: Qlib Adapter (Full 158 Features Implementation)")

        # 1. Polars 预计算 158 因子
        daily_path = os.path.join(self.parquet_input, "daily", "*.parquet")
        lf = pl.scan_parquet(daily_path, include_file_paths="filepath").with_columns(
            pl.col("filepath").str.split("/").list.last().str.split(r"\\").list.last().str.replace(".parquet", "").alias("instrument")
        ).filter((pl.col("date") >= start) & (pl.col("date") <= end)).sort(["instrument", "date"])

        # 生成时间序号 t，用于线性回归
        lf = lf.with_columns(pl.int_range(0, pl.count()).over("instrument").alias("t"))

        # 应用全量表达式
        all_exprs = self._build_all_alpha158_exprs()
        # 记录因子的输出名称，确保最后过滤准确
        alpha_names = [expr.meta.output_name() for expr in all_exprs]

        # 第一次 with_columns: 计算所有因子 (IMAX/IMIN 用占位值 0 代表 IMXD)
        lf = lf.with_columns(all_exprs)

        # 第二次 with_columns: 用 IMAX/IMIN 计算真实的 IMXD
        imxd_exprs = self._build_imxd_exprs()
        lf = lf.with_columns(imxd_exprs)

        df_pd = lf.collect().to_pandas()

        # 整理索引并严格限制输出仅为 158 个因子
        df_pd["datetime"] = pd.to_datetime(df_pd["date"])
        df_pd = df_pd.set_index(["datetime", "instrument"]).sort_index()
        df_pd = df_pd[alpha_names]

        # 2. 包装进 Qlib Handler
        qlib.init(log_level=logging.ERROR)
        data_loader = StaticDataLoader(df_pd)

        handler = DataHandlerLP(
            instruments=None,
            start_time=start,
            end_time=end,
            data_loader=data_loader,
            learn_processors=[],
            infer_processors=[],
        )

        factors = handler.fetch()
        logging.info(f"Successfully computed {factors.shape[1]} factors and adapted to Qlib.")
        return factors
