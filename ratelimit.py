from __future__ import annotations
import time
import threading


class TokenBucket:
    def __init__(self, rate: float = 2.0, burst: int = 5):
        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.last = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self, tokens: float = 1.0) -> None:
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last
            self.tokens = min(float(self.burst), self.tokens + elapsed * self.rate)
            self.last = now
            if self.tokens >= tokens:
                self.tokens -= tokens
                return
            deficit = tokens - self.tokens
            sleep = deficit / self.rate
            if sleep > 0:
                time.sleep(sleep)
            self.tokens = 0.0
            self.last = time.monotonic()
