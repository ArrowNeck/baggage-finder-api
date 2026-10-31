import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import RateLimitError


class RateLimit:
    """Per-process sliding-window limiter keyed by client IP (used as a route dependency).

    Fine for a single instance. With several replicas, or behind a proxy that hides client
    IPs, enforce limits in Azure API Management or a shared store such as Redis instead.
    """

    _hits: dict[str, deque[float]] = defaultdict(deque)

    def __init__(self, scope: str) -> None:
        self.scope = scope

    async def __call__(self, request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        key = f"{self.scope}:{ip}"
        now = time.monotonic()
        window = self._hits[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= settings.RATE_LIMIT_PER_MINUTE:
            raise RateLimitError(retry_after=max(1, int(60 - (now - window[0]))))
        window.append(now)

    @classmethod
    def reset(cls) -> None:
        cls._hits.clear()
