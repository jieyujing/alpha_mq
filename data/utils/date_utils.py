"""日期处理工具模块

提供统一的日期转换和处理函数，确保数据转换过程中日期格式的一致性。
"""

from datetime import datetime
from typing import Union

import pandas as pd


def to_date_str(dt: Union[str, datetime, pd.Timestamp]) -> str:
    """将日期转换为标准字符串格式 (YYYY-MM-DD)

    Args:
        dt: 输入日期，支持字符串、datetime或pd.Timestamp格式

    Returns:
        标准格式的日期字符串
    """
    return pd.to_datetime(dt).strftime("%Y-%m-%d")


def to_datetime(dt: Union[str, datetime, pd.Timestamp]) -> pd.Timestamp:
    """将日期转换为pd.Timestamp格式

    Args:
        dt: 输入日期

    Returns:
        pd.Timestamp对象
    """
    return pd.to_datetime(dt)


def extract_date_from_datetime(dt: Union[str, datetime, pd.Timestamp]) -> str:
    """从datetime对象中提取日期部分

    用于处理带有时间戳的datetime对象（如bob/eob字段），
    只保留日期部分。

    Args:
        dt: 带有时间戳的日期

    Returns:
        仅包含日期部分的字符串 (YYYY-MM-DD)
    """
    ts = pd.to_datetime(dt)
    if ts.tzinfo is not None:
        # 如果有时区信息，转换为naive datetime
        ts = ts.tz_convert(None).tz_localize(None)
    return ts.strftime("%Y-%m-%d")