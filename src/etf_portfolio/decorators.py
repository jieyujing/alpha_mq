"""
横切关注点装饰器 - 流控、重试等。
"""
import functools
import time
import logging
from typing import Callable, TypeVar, Any

T = TypeVar('T')


def with_rate_limit(limiter: Any) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """流控装饰器 - 在函数执行前调用 limiter.wait()"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            limiter.wait()
            return func(*args, **kwargs)
        return wrapper
    return decorator


def with_retry(
    max_attempts: int = 3,
    backoff_base: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """重试装饰器 - 指数退避重试"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = backoff_base ** attempt
                        logging.warning(f"{func.__name__} failed (attempt {attempt+1}/{max_attempts}): {e}. Retrying in {wait_time:.1f}s")
                        time.sleep(wait_time)
            raise last_exception
        return wrapper
    return decorator


def compose_decorators(*decorators: Callable) -> Callable:
    """装饰器组合器"""
    def composed(func: Callable) -> Callable:
        for dec in reversed(decorators):
            func = dec(func)
        return func
    return composed