# tests/test_qlib_model.py
"""qlib Model 测试"""
from __future__ import annotations

import pytest


def test_get_model_config():
    """测试模型配置可以导入"""
    from model.qlib_model import get_model_config

    config = get_model_config()
    assert config is not None
    assert config["class"] == "LGBModel"


def test_get_model_config_fast():
    """测试快速配置"""
    from model.qlib_model import get_model_config

    config = get_model_config(fast=True)
    assert config["kwargs"]["n_estimators"] == 100