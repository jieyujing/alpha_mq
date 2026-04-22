"""
GM 数据下载模块

提供增量下载能力：
- 时间覆盖检测：只下载缺失时间段
- 标的覆盖检测：只下载缺失标的
"""
from data_download.incremental import CoverageResult, SymbolGap

__all__ = [
    "CoverageResult",
    "SymbolGap",
]