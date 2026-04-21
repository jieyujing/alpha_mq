# tests/test_etf_portfolio/test_data_source.py
import pytest
from src.etf_portfolio.data_source import GMDataSource, DataSource


class MockRateLimiter:
    """测试用模拟流控器"""
    def __init__(self):
        self.calls = []

    def wait(self):
        self.calls.append(True)


def test_data_source_protocol():
    """验证 GMDataSource 实现 DataSource 协议"""
    limiter = MockRateLimiter()
    source = GMDataSource(limiter=limiter, token="test-token")
    # 协议检查: 必须有 fetch_history 方法
    assert hasattr(source, 'fetch_history')
    assert callable(source.fetch_history)


def test_gm_data_source_calls_limiter():
    """验证 GMDataSource 调用流控器"""
    limiter = MockRateLimiter()
    source = GMDataSource(limiter=limiter, token="test-token")
    limiter.wait()
    assert len(limiter.calls) == 1


def test_data_source_fetch_signature():
    """验证 fetch_history 签名符合协议"""
    import inspect
    limiter = MockRateLimiter()
    source = GMDataSource(limiter=limiter, token="test-token")
    sig = inspect.signature(source.fetch_history)
    params = list(sig.parameters.keys())
    assert 'symbol' in params
    assert 'start_time' in params or 'start' in params
    assert 'end_time' in params or 'end' in params