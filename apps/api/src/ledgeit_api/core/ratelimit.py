"""Tiny in-process sliding-window rate limiter for unauthenticated endpoints (public verify)."""

# no `from __future__ import annotations`: FastAPI must resolve `Request` on this callable instance

import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from .errors import ApiError


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float):
        self.limit, self.window = limit, window_seconds
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def __call__(self, request: Request) -> None:
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                raise ApiError(429, "RATE_LIMITED", "too many verification requests; try again in a minute")
            q.append(now)


public_limiter = RateLimiter(limit=30, window_seconds=60)
