# tests/test_etf_portfolio/test_decorators.py
import pytest
import time
from src.etf_portfolio.decorators import with_retry, with_rate_limit

class MockLimiter:
    def __init__(self):
        self.wait_count = 0
    def wait(self):
        self.wait_count += 1

def test_with_rate_limit_calls_limiter():
    limiter = MockLimiter()
    @with_rate_limit(limiter)
    def fetch_data():
        return "data"
    result = fetch_data()
    assert result == "data"
    assert limiter.wait_count == 1

def test_with_retry_success_no_retry():
    call_count = 0
    @with_retry(max_attempts=3)
    def success_func():
        nonlocal call_count
        call_count += 1
        return "success"
    result = success_func()
    assert result == "success"
    assert call_count == 1

def test_with_retry_failure_then_success():
    call_count = 0
    @with_retry(max_attempts=3, backoff_base=0.1)
    def flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ValueError("temporary error")
        return "success"
    result = flaky_func()
    assert result == "success"
    assert call_count == 2

def test_with_retry_max_attempts_exceeded():
    call_count = 0
    @with_retry(max_attempts=3, backoff_base=0.05)
    def always_fail():
        nonlocal call_count
        call_count += 1
        raise ValueError("always fails")
    with pytest.raises(ValueError, match="always fails"):
        always_fail()
    assert call_count == 3

def test_decorator_stack_order():
    limiter = MockLimiter()
    call_count = 0
    @with_retry(max_attempts=2, backoff_base=0.05)
    @with_rate_limit(limiter)
    def fetch():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("first fails")
        return "data"
    result = fetch()
    assert result == "data"
    assert limiter.wait_count == 2
    assert call_count == 2