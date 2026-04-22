"""
GM 数据下载模块

提供增量下载能力：
- 时间覆盖检测：只下载缺失时间段
- 标的覆盖检测：只下载缺失标的
"""
from data_download.incremental import CoverageResult, SymbolGap, check_time_coverage, check_symbol_coverage
from data_download.gm_api import RateLimiter, with_retry
from data_download.base import GMDownloader
from data_download.csi1000_downloader import CSI1000Downloader

__all__ = [
    "CoverageResult",
    "SymbolGap",
    "check_time_coverage",
    "check_symbol_coverage",
    "RateLimiter",
    "with_retry",
    "GMDownloader",
    "CSI1000Downloader",
]