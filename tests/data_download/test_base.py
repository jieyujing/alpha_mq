"""GMDownloader 基类测试"""
import pytest
from abc import ABC


class TestGMDownloaderBase:
    """基类结构测试"""

    def test_is_abstract(self):
        """验证是抽象基类"""
        from data_download.base import GMDownloader

        assert ABC in GMDownloader.__bases__

    def test_abstract_methods(self):
        """验证抽象方法定义"""
        from data_download.base import GMDownloader

        # 尝试直接实例化应失败
        with pytest.raises(TypeError):
            GMDownloader({})

    def test_subclass_must_implement(self):
        """子类必须实现抽象方法"""
        from data_download.base import GMDownloader

        class IncompleteDownloader(GMDownloader):
            pass

        with pytest.raises(TypeError):
            IncompleteDownloader({})

    def test_config_attribute(self):
        """验证 config 属性"""
        from data_download.base import GMDownloader

        # 创建完整实现用于测试
        class CompleteDownloader(GMDownloader):
            def get_target_pool(self):
                return []

            def get_categories(self):
                return {}

            def run(self):
                pass

        config = {"test_key": "test_value"}
        downloader = CompleteDownloader(config)
        assert downloader.config == config

    def test_setup_creates_directories(self, tmp_path):
        """验证 setup 创建目录"""
        from data_download.base import GMDownloader

        class TestDownloader(GMDownloader):
            def get_target_pool(self):
                return []

            def get_categories(self):
                return {"cat1": {}, "cat2": {}}

            def run(self):
                pass

        exports_base = tmp_path / "exports"
        config = {"exports_base": str(exports_base)}
        downloader = TestDownloader(config)
        downloader.setup()

        assert exports_base.exists()
        assert (exports_base / "cat1").exists()
        assert (exports_base / "cat2").exists()