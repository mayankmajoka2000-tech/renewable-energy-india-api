"""
Minimal in-memory per-IP rate limiting for public deployment.

This is a research/open-data API (no signup, no API keys — matching the
"open government data" spirit of the underlying CEA/MNRE/NASA sources), so
the goal here is only to blunt abusive scraping floods, not to gate access.
A fixed-window counter per client IP is enough for that; it deliberately
doesn't need a external store (Redis etc.) since this is a single-process
deployment target.
"""
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 120  # generous for legitimate research/API use


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        hits = self._hits[client_ip]

        while hits and now - hits[0] > WINDOW_SECONDS:
            hits.popleft()

        if len(hits) >= MAX_REQUESTS_PER_WINDOW:
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded: max {MAX_REQUESTS_PER_WINDOW} requests per {WINDOW_SECONDS}s."},
            )

        hits.append(now)
        return await call_next(request)
