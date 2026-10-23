"""Unit tests for token-bucket rate limiter."""

import time
import pytest
from autoextract.engine.rate_limiter import RateLimiter


def test_rate_limiter_init_invalid():
    with pytest.raises(ValueError):
        RateLimiter(requests_per_second=0)

    with pytest.raises(ValueError):
        RateLimiter(requests_per_second=-5)


def test_rate_limiter_burst_and_try_acquire():
    limiter = RateLimiter(requests_per_second=5.0, burst=2)
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is True
    # Capacity exhausted
    assert limiter.try_acquire() is False


def test_rate_limiter_acquire_replenishes():
    limiter = RateLimiter(requests_per_second=20.0, burst=1)
    t0 = time.perf_counter()
    w1 = limiter.acquire()
    w2 = limiter.acquire()
    elapsed = time.perf_counter() - t0
    # Second acquisition must have waited ~0.05s
    assert elapsed >= 0.04
