# tests/test_triple_barrier.py
"""Triple Barrier DataLoader 测试"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from factor.triple_barrier import TripleBarrierConfig, TripleBarrierDataLoader


def test_triple_barrier_dataloader_import():
    """测试 TripleBarrierDataLoader 可以导入"""
    loader = TripleBarrierDataLoader()
    assert loader is not None


def test_triple_barrier_config_defaults():
    """测试默认配置"""
    config = TripleBarrierConfig()
    assert config.vol_window == 20
    assert config.k_upper == 2.0
    assert config.k_lower == 2.0
    assert config.max_holding == 10
    assert config.mae_penalty == 1.0
    assert config.shift == 1
    assert config.winsor_std == 3.0


def test_triple_barrier_load_returns_series():
    """测试 load 方法返回正确格式的 Series"""
    # 创建模拟数据：10天 x 5只股票
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    codes = ["A", "B", "C", "D", "E"]
    close_df = pd.DataFrame(
        100 * (1 + np.random.randn(30, 5).cumsum(axis=0) * 0.02),
        index=dates,
        columns=codes,
    )

    loader = TripleBarrierDataLoader()
    result = loader.load(close_df)

    # 验证返回类型
    assert isinstance(result, pd.Series)
    assert result.name == "target"

    # 验证 MultiIndex
    assert isinstance(result.index, pd.MultiIndex)
    # index.names 可能是 [None, None] 或 ["date", "code"]，取决于 stack() 行为
    assert result.index.nlevels == 2


def test_barrier_scan_basic():
    """测试 _barrier_scan 方法的屏障触发逻辑"""
    # 构造一个价格一定会触及上屏障的场景
    # 假设 vol = 0.02, k_upper = 2.0, 上屏障 = entry * (1 + 0.04)
    # 让价格在第二天直接跳涨 5%，触发上屏障

    cfg = TripleBarrierConfig(k_upper=2.0, k_lower=2.0, max_holding=10, shift=1)

    # 构造价格数据：T=5, N=2
    close_np = np.array([
        [100.0, 100.0],  # t=0
        [100.0, 100.0],  # t=1 (entry point for t=0)
        [105.0, 95.0],   # t=2: A 涨5%触发上屏障, B 跌5%触发下屏障
        [106.0, 94.0],   # t=3
        [107.0, 93.0],   # t=4
    ])

    # 固定波动率
    vol_np = np.full((5, 2), 0.02)  # 2% 波动率

    pnl_arr, mae_arr, hold_len_arr = TripleBarrierDataLoader._barrier_scan(close_np, vol_np, cfg)

    # 验证形状
    assert pnl_arr.shape == (5, 2)
    assert mae_arr.shape == (5, 2)
    assert hold_len_arr.shape == (5, 2)

    # 验证 t=0 的结果（entry 在 t=1, 未来价格在 t=2 触发屏障）
    # 上屏障: 100 * (1 + 2.0 * 0.02) = 104
    # 下屏障: 100 * (1 - 2.0 * 0.02) = 96
    # A: 价格 105 > 104, 触发上屏障, pnl ≈ 5%, hold_len = 1
    # B: 价格 95 < 96, 触发下屏障, pnl ≈ -5%, hold_len = 1

    # 验证持有期
    assert hold_len_arr[0, 0] == 1.0  # A 在第2天触发
    assert hold_len_arr[0, 1] == 1.0  # B 在第2天触发

    # 验证 pnl 方向
    assert pnl_arr[0, 0] > 0  # A 盈利
    assert pnl_arr[0, 1] < 0  # B 亏损

    # 验证 MAE
    # A 的 MAE 应该是 0 或很小的负值（一路涨）
    # B 的 MAE 应该是负值
    assert mae_arr[0, 1] < 0  # B 有 MAE


def test_barrier_scan_max_holding():
    """测试 _barrier_scan 方法的最大持有期限制"""
    cfg = TripleBarrierConfig(k_upper=10.0, k_lower=10.0, max_holding=3, shift=1)
    # 设置很宽的屏障，不会触发，应该持有到 max_holding

    close_np = np.array([
        [100.0, 100.0],  # t=0
        [100.0, 100.0],  # t=1 (entry)
        [100.5, 99.5],   # t=2
        [101.0, 99.0],   # t=3 (max_holding limit)
        [101.5, 98.5],   # t=4
    ])

    vol_np = np.full((5, 2), 0.01)

    pnl_arr, mae_arr, hold_len_arr = TripleBarrierDataLoader._barrier_scan(close_np, vol_np, cfg)

    # 验证最大持有期限制
    assert hold_len_arr[0, 0] == 3.0  # max_holding
    assert hold_len_arr[0, 1] == 3.0

    # pnl 应该是最后一天（t=4）的收益
    # future = close_np[2:5] = [[100.5, 99.5], [101.0, 99.0], [101.5, 98.5]]
    # exit_step = 2 (H-1), 所以 pnl = returns[2] = [0.015, -0.015]
    assert abs(pnl_arr[0, 0] - 0.015) < 0.001  # 101.5/100 - 1 = 1.5%
    assert abs(pnl_arr[0, 1] - (-0.015)) < 0.001  # 98.5/100 - 1 = -1.5%


def test_rank_cross_section():
    """测试 _rank_cross_section 方法的 MAD 缩尾和百分位排名"""
    loader = TripleBarrierDataLoader()

    # 构造测试数据：3天 x 4只股票
    data = {
        "A": [1.0, 10.0, 100.0],
        "B": [2.0, 20.0, 200.0],
        "C": [3.0, 30.0, 300.0],
        "D": [4.0, 40.0, 400.0],
    }
    score_df = pd.DataFrame(data, index=pd.date_range("2024-01-01", periods=3))

    result = loader._rank_cross_section(score_df)

    # 验证返回类型
    assert isinstance(result, pd.Series)
    assert result.name == "target"

    # 验证 MultiIndex
    assert isinstance(result.index, pd.MultiIndex)

    # 验证排名逻辑
    # 第1天: A=1, B=2, C=3, D=4, 排名 1,2,3,4
    # percentile = (rank - 0.5) / count = (rank - 0.5) / 4
    # A: (1-0.5)/4 = 0.125, B: 0.375, C: 0.625, D: 0.875

    day1_result = result.loc["2024-01-01"]
    assert abs(day1_result["A"] - 0.125) < 0.001
    assert abs(day1_result["B"] - 0.375) < 0.001
    assert abs(day1_result["C"] - 0.625) < 0.001
    assert abs(day1_result["D"] - 0.875) < 0.001


def test_rank_cross_section_with_outliers():
    """测试 _rank_cross_section 方法对极端值的处理"""
    cfg = TripleBarrierConfig(winsor_std=3.0)
    loader = TripleBarrierDataLoader(cfg)

    # 构造包含极端值的数据
    np.random.seed(42)
    data = np.random.randn(10, 100)  # 10天 x 100只股票
    data[0, 0] = 1000.0  # 极端正值
    data[0, 1] = -1000.0  # 极端负值

    score_df = pd.DataFrame(data, index=pd.date_range("2024-01-01", periods=10))

    result = loader._rank_cross_section(score_df)

    # 验证没有 NaN（缩尾后应该有值）
    assert not result.isna().any()

    # 验证值在合理范围内
    assert result.min() > 0
    assert result.max() < 1


def test_rank_cross_section_value_range():
    """测试 _rank_cross_section 返回值的范围"""
    loader = TripleBarrierDataLoader()

    np.random.seed(42)
    score_df = pd.DataFrame(
        np.random.randn(5, 50),
        index=pd.date_range("2024-01-01", periods=5),
    )

    result = loader._rank_cross_section(score_df)

    # 验证值在 (0.5/count, 1 - 0.5/count) 范围内
    # count = 50, 所以范围约为 (0.01, 0.99)
    assert result.min() > 0
    assert result.max() < 1

    # 验证值域接近均匀分布
    assert result.min() >= 0.5 / 50
    assert result.max() <= 1 - 0.5 / 50