# tests/test_limiter.py
import time
from data.scripts.download_gm import RateLimiter

def test_rate_limiter_min_interval():
    # 测试最小间隔控制
    limiter = RateLimiter(max_req=5, window=1)
    start = time.time()
    limiter.wait() # 第一次
    limiter.wait() # 第二次，应触发 min_interval
    interval = time.time() - start
    # min_interval=0.35, plus jitter ~0.1
    assert interval >= 0.35
