"""测试 CSI1000 数据下载器"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

from data.downloader import CSI1000Downloader


class TestCSI1000Downloader:
    def test_init_with_valid_dates(self):
        """测试使用有效日期初始化"""
        mock_gm = MagicMock()
        mock_gm.stk_get_index_constituents.return_value = pd.DataFrame({
            "symbol": ["SHSE.600000", "SZSE.000001"]
        })
        with patch("data.downloader._init_gm", return_value=mock_gm):
            downloader = CSI1000Downloader(
                start_date="2020-01-01",
                end_date="2024-12-31"
            )
            assert downloader.start_date == "2020-01-01"
            assert downloader.end_date == "2024-12-31"

    def test_init_with_invalid_date_format(self):
        """测试无效日期格式抛出异常"""
        with pytest.raises(ValueError, match="日期格式"):
            CSI1000Downloader(
                start_date="2020/01/01",
                end_date="2024-12-31"
            )

    def test_get_constituents(self):
        """测试获取成分股列表"""
        mock_gm = MagicMock()
        mock_gm.stk_get_index_constituents.return_value = pd.DataFrame({
            "symbol": ["SHSE.600000", "SZSE.000001", "SZSE.002815"]
        })
        with patch("data.downloader._init_gm", return_value=mock_gm):
            downloader = CSI1000Downloader(
                start_date="2024-01-01",
                end_date="2024-12-31"
            )
            constituents = downloader.constituents
            assert len(constituents) > 0
            assert all("." in code for code in constituents)  # 格式: EXCHANGE.CODE