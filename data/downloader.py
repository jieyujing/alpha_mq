"""
中证1000数据下载器

从 gm SDK 下载行情、估值、市值、财务等数据。
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

# 延迟导入 gm 以避免导入时的依赖问题
gm = None  # type: ignore

logger = logging.getLogger(__name__)

CSI1000_INDEX = "SHSE.000852"
# 从环境变量获取 token，未设置时使用默认值（仅用于开发环境）
GM_TOKEN = os.environ.get("GM_TOKEN", "478dc4635c5198dbfcc962ac3bb209e5327edbff")


def _init_gm():
    """初始化 gm SDK。"""
    global gm
    if gm is not None:
        return gm
    try:
        import gm.api as _gm
    except ImportError:
        raise ImportError("gm 模块未安装，请执行 pip install gm")
    else:
        _gm.set_token(GM_TOKEN)
        gm = _gm
        return gm


class CSI1000Downloader:
    """
    中证1000数据下载器。

    Parameters
    ----------
    start_date : str
        开始日期，格式 "YYYY-MM-DD"
    end_date : str
        结束日期，格式 "YYYY-MM-DD"
    """

    def __init__(
        self,
        start_date: str,
        end_date: str,
    ) -> None:
        self._validate_date(start_date, "start_date")
        self._validate_date(end_date, "end_date")

        self.start_date = start_date
        self.end_date = end_date
        self.constituents = self._get_constituents()

    def _validate_date(self, date_str: str, field: str) -> None:
        """验证日期格式。"""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"{field} 日期格式错误: {date_str}，应为 YYYY-MM-DD")

    def _get_constituents(self) -> list[str]:
        """获取中证1000成分股列表。"""
        _gm = _init_gm()

        constituents = _gm.stk_get_index_constituents(index=CSI1000_INDEX)
        if constituents is None or len(constituents) == 0:
            raise ValueError("无法获取中证1000成分股列表")

        return constituents["symbol"].tolist()