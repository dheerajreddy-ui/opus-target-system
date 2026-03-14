"""Audit logging middleware — logs every request/response to JSONL."""

import json
import time
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, log_path: str = "logs/audit_log.jsonl"):
        super().__init__(app)
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        body = b""
        if request.method == "POST":
            body = await request.body()
            # Reset body stream for downstream handlers
            from starlette.requests import Request as _Req

            async def receive():
                return {"type": "http.request", "body": body}

            request = _Req(request.scope, receive, request._send)

        response = await call_next(request)

        # Capture response body
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk if isinstance(chunk, bytes) else chunk.encode()
        response = Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

        duration_ms = (time.time() - start) * 1000
        session_id = ""
        try:
            req_json = json.loads(body) if body else {}
            session_id = req_json.get("session_id", "")
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

        entry = {
            "timestamp": time.time(),
            "method": request.method,
            "path": str(request.url.path),
            "status_code": response.status_code,
            "session_id": session_id,
            "request_body": body.decode("utf-8", errors="replace")[:500],
            "response_body": response_body.decode("utf-8", errors="replace")[:500],
            "duration_ms": round(duration_ms, 2),
        }
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

        return response
