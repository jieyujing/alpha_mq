"""
GM API 封装

提供流控、重试装饰器等基础设施。
"""
import time
import logging
from functools import wraps
from typing import Callable, Optional


class RateLimiter:
    """
    简单的速率限制器

    基于 sliding window 实现每秒请求限制。
    """

    def __init__(self, max_req: int = 950, window_seconds: float = 1.0):
        """
        初始化速率限制器

        Args:
            max_req: 窗口内最大请求数
            window_seconds: 窗口时间(秒)
        """
        self.max_req = max_req
        self.window_seconds = window_seconds
        self.requests: list = []  # 记录请求时间戳

    def wait(self):
        """等待直到可以发起请求"""
        now = time.time()

        # 清理过期记录
        self.requests = [t for t in self.requests if now - t < self.window_seconds]

        # 如果达到限制，等待
        if len(self.requests) >= self.max_req:
            wait_time = self.window_seconds - (now - self.requests[0])
            if wait_time > 0:
                time.sleep(wait_time)
                # 清理过期记录
                now = time.time()
                self.requests = [t for t in self.requests if now - t < self.window_seconds]

        # 记录本次请求
        self.requests.append(time.time())


def with_retry(max_attempts: int = 3, backoff_base: float = 2.0,
               exceptions: tuple = (Exception,)):
    """
    重试装饰器

    Args:
        max_attempts: 最大尝试次数
        backoff_base: 指数退避基数
        exceptions: 需要重试的异常类型

    Returns:
        装饰器函数
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts - 1:
                        raise
                    wait_time = backoff_base ** attempt
                    logging.warning(f"Retry {attempt + 1}/{max_attempts} after {wait_time}s: {e}")
                    time.sleep(wait_time)
            return None
        return wrapper
    return decorator