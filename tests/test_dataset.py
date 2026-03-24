"""Dataset 测试"""
from __future__ import annotations

import pytest


def test_dataset_config_import():
    """测试 get_dataset_config 可以导入"""
    from factor.dataset import get_dataset_config

    config = get_dataset_config()
    assert config is not None


def test_dataset_config_structure():
    """测试配置结构正确"""
    from factor.dataset import get_dataset_config

    config = get_dataset_config()
    assert "class" in config
    assert "module_path" in config
    assert "kwargs" in config
    assert config["class"] == "DatasetH"