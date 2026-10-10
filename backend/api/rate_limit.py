"""In-process sliding-window rate limiting.

Good enough for a single-instance deployment (Render, one Docker container). If the app
is ever scaled horizontally, move these counters to a shared store such as Redis.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional, Tuple


@dataclass(frozen=True)
class Limit:
    requests: int
    per_seconds: int


# (bucket name, limit). Checked in order; the first exceeded limit wins.
IP_LIMIT = Limit(240, 60)               # any /api/ call, per client IP
UNAUTHENTICATED_LIMIT = Limit(30, 60)   # requests with a missing/invalid token, per IP
USER_LIMIT = Limit(180, 60)             # any /api/ call, per signed-in user
UPLOAD_LIMITS = (Limit(10, 60), Limit(60, 3600))   # running checks, per user
ASK_LIMIT = Limit(20, 60)               # "Ask about this check", per user
WRITE_LIMIT = Limit(60, 60)             # other POST/DELETE calls, per user

UPLOAD_PATHS = ("/api/v1/cases/files", "/api/v1/cases/text", "/api/v1/cases")


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: Dict[Tuple[str, int, int], Deque[float]] = {}
        self._lock = threading.Lock()
        self._last_sweep = time.monotonic()

    def hit(self, key: str, limit: Limit) -> Optional[int]:
        """Records a hit. Returns seconds to wait if the limit is exceeded, else None."""
        now = time.monotonic()
        bucket_key = (key, limit.requests, limit.per_seconds)
        with self._lock:
            self._maybe_sweep(now)
            q = self._hits.setdefault(bucket_key, deque())
            cutoff = now - limit.per_seconds
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= limit.requests:
                return max(1, int(q[0] + limit.per_seconds - now) + 1)
            q.append(now)
            return None

    def _maybe_sweep(self, now: float) -> None:
        if now - self._last_sweep < 300:
            return
        self._last_sweep = now
        for k in [k for k, q in self._hits.items() if not q or q[-1] < now - k[2]]:
            del self._hits[k]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def client_ip(scope) -> str:
    """Client IP, honouring the first X-Forwarded-For hop set by the hosting proxy."""
    headers = dict(scope.get("headers") or [])
    fwd = headers.get(b"x-forwarded-for", b"").decode().split(",")[0].strip()
    if fwd:
        return fwd
    client = scope.get("client")
    return client[0] if client else "unknown"


def user_limits_for(path: str, method: str):
    if method == "POST" and path in UPLOAD_PATHS:
        return [("upload", l) for l in UPLOAD_LIMITS]
    if method == "POST" and path.endswith("/controller/explain"):
        return [("ask", ASK_LIMIT)]
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        return [("write", WRITE_LIMIT)]
    return []
