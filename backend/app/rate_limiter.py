"""
Lightweight in-memory rate limiter, keyed by client IP.

No external dependency (Redis, slowapi, etc) needed -- Render's free tier
runs a single process, so in-memory state is safe and consistent here.
If this ever scales to multiple instances, this would need to move to a
shared store (Redis) since each instance would otherwise track its own
separate counts.

reason: multiple requests can arrive concurrently
(FastAPI runs sync endpoints in a thread pool) and the check-then-update
sequence needs to be atomic to be correct.
"""

import threading
import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, client_id: str) -> tuple[bool, int]:
        """
        Returns (allowed, seconds_until_retry).
        seconds_until_retry is 0 if allowed.
        """
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            timestamps = [t for t in self._requests[client_id] if t > cutoff]

            if len(timestamps) >= self.max_requests:
                oldest = min(timestamps)
                retry_after = int(oldest + self.window_seconds - now) + 1
                self._requests[client_id] = timestamps
                return False, retry_after

            timestamps.append(now)
            self._requests[client_id] = timestamps
            return True, 0

    def get_client_id(self, request) -> str:
        """
        Extract the real visitor IP. Render (and most PaaS providers) sit
        behind a proxy, so request.client.host would just be the proxy's
        internal IP -- the real visitor IP is in X-Forwarded-For instead.
        """
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"