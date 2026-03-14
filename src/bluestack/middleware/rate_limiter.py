"""Token-bucket rate limiter per session."""

import json
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.bluestack.defense.defense_manager import DefenseManager


class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._buckets: dict[str, _TokenBucket] = {}

    async def dispatch(self, request: Request, call_next):
        if request.method != "POST" or request.url.path != "/chat":
            return await call_next(request)

        body = await request.body()

        async def receive():
            return {"type": "http.request", "body": body}

        request = Request(request.scope, receive, request._send)

        try:
            data = json.loads(body)
            session_id = data.get("session_id", "anonymous")
        except (json.JSONDecodeError, UnicodeDecodeError):
            session_id = "anonymous"

        dm = DefenseManager()
        rpm = dm.get_config("rate_limit_per_minute") or 100

        if session_id not in self._buckets:
            self._buckets[session_id] = _TokenBucket(rpm)
        bucket = self._buckets[session_id]
        bucket.rate = rpm

        if not bucket.consume():
            return JSONResponse(
                {"error": "Rate limit exceeded. Try again later."},
                status_code=429,
            )

        return await call_next(request)


class _TokenBucket:
    def __init__(self, rate: int):
        self.rate = rate
        self.tokens = float(rate)
        self.last_refill = time.time()

    def consume(self) -> bool:
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.rate, self.tokens + elapsed * (self.rate / 60.0))
        self.last_refill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False
