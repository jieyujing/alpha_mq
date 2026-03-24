"""DataHandler 测试"""
from __future__ import annotations

import pytest


def test_csi1000_handler_import():
    """测试 CSI1000Handler 可以导入"""
    from factor.handler import CSI1000Handler

    assert CSI1000Handler is not None


def test_csi1000_handler_with_alpha158():
    """测试使用 Alpha158 因子的 Handler"""
    pytest.skip("需要 qlib 数据环境")