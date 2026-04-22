"""GM API 封装测试"""
import pytest
import time


class TestRateLimiter:
    """流控器测试"""

    def test_wait_blocks_when_limit_reached(self):
        """达到限制时阻塞"""
        from data_download.gm_api import RateLimiter

        limiter = RateLimiter(max_req=2)  # 每秒最多 2 次

        # 前两次应该很快
        start = time.time()
        limiter.wait()
        limiter.wait()
        elapsed = time.time() - start
        assert elapsed < 0.1

        # 第三次应该阻塞
        limiter.wait()
        elapsed = time.time() - start
        assert elapsed >= 0.5  # 至少等待 0.5 秒

    def test_request_count_reset_after_window(self):
        """窗口结束后计数重置"""
        from data_download.gm_api import RateLimiter

        limiter = RateLimiter(max_req=1)

        limiter.wait()
        time.sleep(1.1)  # 等待窗口重置

        # 应该不再阻塞
        start = time.time()
        limiter.wait()
        elapsed = time.time() - start
        assert elapsed < 0.1


class TestRetryDecorator:
    """重试装饰器测试"""

    def test_success_no_retry(self):
        """成功时不重试"""
        from data_download.gm_api import with_retry

        call_count = 0

        @with_retry(max_attempts=3, backoff_base=1.0)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = success_func()
        assert result == "ok"
        assert call_count == 1

    def test_retry_on_exception(self):
        """失败时重试"""
        from data_download.gm_api import with_retry

        call_count = 0

        @with_retry(max_attempts=3, backoff_base=0.1)
        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "ok"

        result = failing_func()
        assert result == "ok"
        assert call_count == 3

    def test_max_attempts_reached(self):
        """达到最大重试次数后抛出异常"""
        from data_download.gm_api import with_retry

        call_count = 0

        @with_retry(max_attempts=2, backoff_base=0.1)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("always fail")

        with pytest.raises(ValueError):
            always_fail()

        assert call_count == 2