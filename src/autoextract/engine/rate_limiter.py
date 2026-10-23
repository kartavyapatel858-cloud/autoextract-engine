"""
Thread-safe Token Bucket Rate Limiter.
Prevents IP throttling and ensures ethical, polite scraping.
"""

import threading
import time
from typing import Optional


class RateLimiter:
    """
    Token-bucket rate limiter.
    
    Attributes:
        rate: Maximum allowed requests per second.
        burst: Maximum burst capacity (defaults to max(1, int(rate))).
    """

    def __init__(self, requests_per_second: float = 10.0, burst: Optional[int] = None) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")

        self.rate = float(requests_per_second)
        self.capacity = float(burst if burst is not None else max(1, int(requests_per_second)))
        self.tokens = self.capacity
        self.last_update = time.perf_counter()
        self._lock = threading.Lock()

    def _replenish(self, now: float) -> None:
        elapsed = now - self.last_update
        self.last_update = now
        self.tokens = min(self.capacity, self.tokens + (elapsed * self.rate))

    def acquire(self) -> float:
        """
        Blocks until a token is available.
        Returns the duration waited in seconds.
        """
        waited = 0.0
        while True:
            with self._lock:
                now = time.perf_counter()
                self._replenish(now)

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return waited

                # Calculate required wait time for next token
                needed = 1.0 - self.tokens
                sleep_time = needed / self.rate

            time.sleep(sleep_time)
            waited += sleep_time

    def try_acquire(self) -> bool:
        """Non-blocking attempt to acquire a rate-limiting token."""
        with self._lock:
            now = time.perf_counter()
            self._replenish(now)
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False
