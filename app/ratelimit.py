"""In-memory sliding-window rate limits.

ponytail: state lives in this process, so it resets on restart and is not shared between workers.
Run one worker, or move the counters to Redis, if that ever matters.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import get_settings


class Limiter:
    def __init__(self):
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def check(self, key: str, limit: int, window: float, what: str = "requests") -> None:
        """Count a hit for `key`; 429 with Retry-After once `limit` hits fall within `window` s."""
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= limit:
                wait = int(q[0] + window - now) + 1
                raise HTTPException(
                    429,
                    f"Too many {what}. Try again in {max(1, round(wait / 60))} min.",
                    headers={"Retry-After": str(wait)},
                )
            q.append(now)
            if len(self._hits) > 10_000:  # forget keys idle for longer than any window in use
                for k in [k for k, v in self._hits.items() if not v or v[-1] <= now - 86_400]:
                    del self._hits[k]


limiter = Limiter()


def client_ip(request: Request) -> str:
    """The peer address. Behind your own reverse proxy (TRUST_PROXY=1): the last X-Forwarded-For
    entry, which the proxy added; earlier entries are client-supplied and can be forged."""
    if get_settings().trust_proxy:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"
