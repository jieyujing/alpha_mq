# tests/test_triple_barrier.py
"""Triple Barrier DataLoader 测试"""
from __future__ import annotations

import pandas as pd
import pytest


def test_triple_barrier_dataloader_import():
    """测试 TripleBarrierDataLoader 可以导入"""
    from factor.triple_barrier import TripleBarrierDataLoader

    loader = TripleBarrierDataLoader()
    assert loader is not None


def test_triple_barrier_config_defaults():
    """测试默认配置"""
    from factor.triple_barrier import TripleBarrierConfig

    config = TripleBarrierConfig()
    assert config.vol_window == 20
    assert config.k_upper == 2.0
    assert config.k_lower == 2.0
    assert config.max_holding == 10


def test_triple_barrier_load_returns_dataframe():
    """测试 load 方法返回 DataFrame"""
    from factor.triple_barrier import TripleBarrierDataLoader

    loader = TripleBarrierDataLoader()
    # 使用模拟数据测试
    # 实际测试需要 mock qlib 数据
    pytest.skip("需要 qlib 数据环境")